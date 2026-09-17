from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import consul as py_consul
import hcl
import yaml
from jcramda import decode, identity


def _hcl_load(raw_value):
    return hcl.loads(raw_value)


__all__ = (
    "Consul",
    "ConsulClient",
    "AsyncConsulClient",
    "path_join",
    "fetch_key",
    "register_service",
    "deregister",
    "get_services",
    "find_service",
    "register_check",
    "deregister_check",
    "create_session",
    "destroy_session",
    "renew_session",
    "acquire_lock",
    "release_lock",
    "list_keys",
)

Consul = py_consul.Consul
_UNSET = object()


class ConsulClient:
    """Synchronous Consul client wrapper.

    ``ConsulClient()`` keeps py-consul's default environment handling. If any
    constructor option is provided, that explicit option is forwarded while
    omitted options continue to use upstream defaults. Use ``close()`` or a
    ``with`` block to close the underlying requests session.
    """

    def __init__(
        self,
        host=_UNSET,
        port=_UNSET,
        token=_UNSET,
        scheme=_UNSET,
        consistency="default",
        dc=_UNSET,
        verify=_UNSET,
        cert=_UNSET,
    ):
        """Initialize a synchronous Consul client.

        With no arguments this is equivalent to ``consul.Consul()`` and honors
        upstream ``CONSUL_HTTP_*`` environment variables exactly as py-consul
        does. Passing any option switches to explicit construction and forwards
        only supplied options, so ``ConsulClient(host=None, port=8501)`` keeps
        the default host while using the explicit port.
        """
        self.params = {}
        options = {
            "host": host,
            "port": port,
            "token": token,
            "scheme": scheme,
            "consistency": consistency,
            "dc": dc,
            "verify": verify,
            "cert": cert,
        }
        no_explicit_options = all(
            value is _UNSET for key, value in options.items() if key != "consistency"
        ) and consistency == "default"

        if no_explicit_options:
            self._client = Consul()
        else:
            self.params = {key: value for key, value in options.items() if value is not _UNSET}
            if host is not _UNSET and host is not None:
                # Preserve defaults used by legacy explicit-host construction.
                for key, value in (("port", 8500), ("scheme", "http"), ("verify", True)):
                    self.params.setdefault(key, value)
            self._client = Consul(**self.params)
            if token is not _UNSET:
                # py-consul lets CONSUL_HTTP_TOKEN override the token argument.
                # For the wrapper, an explicitly supplied token should remain explicit.
                self._client.token = token

    @property
    def client(self) -> py_consul.Consul:
        """Return the native synchronous ``consul.Consul`` instance."""
        return self._client

    def close(self) -> None:
        """Close the owned requests session (upstream HTTPClient.close is a no-op)."""
        self._client.http.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def kv_get(self, key: str, **kwargs) -> Any:
        """获取键值，返回 py-consul 原生 ``(index, data)`` 元组。"""
        return self._client.kv.get(key, **kwargs)

    def kv_put(self, key: str, value: str, **kwargs) -> bool:
        """设置键值"""
        return self._client.kv.put(key, value, **kwargs)

    def kv_list(self, prefix: str, **kwargs) -> Tuple[int, List[Dict]]:
        """列出指定前缀下的所有键"""
        return self._client.kv.get(prefix, recurse=True, **kwargs)

    def kv_delete(self, key: str, **kwargs) -> bool:
        """删除键值"""
        return self._client.kv.delete(key, **kwargs)

    def service_register(self, name: str, **kwargs) -> None:
        """注册本地 agent 服务"""
        self._client.agent.service.register(name, **kwargs)

    def service_deregister(self, service_id: str) -> None:
        """注销本地 agent 服务"""
        self._client.agent.service.deregister(service_id)

    def services(self) -> Dict:
        """获取本地 agent 的服务字典，不查询 catalog。"""
        return self._client.agent.services()

    def check_register(self, name: str, check: Dict, **kwargs) -> None:
        """注册本地 agent 健康检查"""
        self._client.agent.check.register(name, check=check, **kwargs)

    def check_deregister(self, check_id: str) -> None:
        """注销本地 agent 健康检查"""
        self._client.agent.check.deregister(check_id)

    def checks(self) -> Dict:
        """获取本地 agent 健康检查"""
        return self._client.agent.checks()

    def session_create(self, name: str = None, **kwargs) -> str:
        """创建会话"""
        if isinstance(kwargs.get("ttl"), str):
            kwargs["ttl"] = int(kwargs["ttl"].removesuffix("s"))
        session_id = self._client.session.create(name=name, **kwargs)
        return session_id

    def session_destroy(self, session_id: str) -> bool:
        """销毁会话"""
        return self._client.session.destroy(session_id)

    def session_renew(self, session_id: str) -> bool:
        """续约会话，保持旧行为：异常转为 ``False``。"""
        try:
            self._client.session.renew(session_id)
            return True
        except Exception:
            return False

    def lock_acquire(self, key: str, session_id: str, value: str = None) -> bool:
        """获取分布式锁"""
        return self._client.kv.put(key, value, acquire=session_id)

    def lock_release(self, key: str, session_id: str) -> bool:
        """释放分布式锁"""
        return self._client.kv.put(key, None, release=session_id)


class AsyncConsulClient:
    """Independent asynchronous Consul wrapper using ``consul.aio``.

    Install ``jcutil[consul-async]`` (``py-consul[asyncio]>=1.7.1``) to use this
    class. Async imports are delayed so synchronous ``jcutil.consul`` imports do
    not require aiohttp. Use ``await close()`` or ``async with`` to close the
    aiohttp session. Additional native APIs are available via ``client``.
    """

    def __init__(
        self,
        host=_UNSET,
        port=_UNSET,
        token=_UNSET,
        scheme=_UNSET,
        consistency="default",
        dc=_UNSET,
        verify=_UNSET,
        cert=_UNSET,
    ):
        try:
            import consul.aio as aio_consul
        except ImportError as exc:
            raise ImportError(
                "AsyncConsulClient requires the optional Consul async extra: "
                "install with `jcutil[consul-async]` (py-consul[asyncio]>=1.7.1)."
            ) from exc

        self.params = {}
        options = {
            "host": host,
            "port": port,
            "token": token,
            "scheme": scheme,
            "consistency": consistency,
            "dc": dc,
            "verify": verify,
            "cert": cert,
        }
        no_explicit_options = all(
            value is _UNSET for key, value in options.items() if key != "consistency"
        ) and consistency == "default"
        if no_explicit_options:
            self._client = aio_consul.Consul()
        else:
            self.params = {key: value for key, value in options.items() if value is not _UNSET}
            self._client = aio_consul.Consul(**self.params)
            if token is not _UNSET:
                self._client.token = token

    @property
    def client(self):
        """Return the native asynchronous ``consul.aio.Consul`` instance."""
        return self._client

    async def close(self) -> None:
        """Close the native aiohttp transport session."""
        await self._client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        return False

    async def kv_get(self, key: str, **kwargs) -> Any:
        return await self._client.kv.get(key, **kwargs)

    async def kv_put(self, key: str, value: str, **kwargs) -> bool:
        return await self._client.kv.put(key, value, **kwargs)

    async def kv_list(self, prefix: str, **kwargs) -> Tuple[int, List[Dict]]:
        return await self._client.kv.get(prefix, recurse=True, **kwargs)

    async def kv_delete(self, key: str, **kwargs) -> bool:
        return await self._client.kv.delete(key, **kwargs)

    async def service_register(self, name: str, **kwargs) -> None:
        return await self._client.agent.service.register(name, **kwargs)

    async def service_deregister(self, service_id: str) -> None:
        return await self._client.agent.service.deregister(service_id)

    async def services(self) -> Dict:
        return await self._client.agent.services()

    async def check_register(self, name: str, check: Dict, **kwargs) -> None:
        return await self._client.agent.check.register(name, check=check, **kwargs)

    async def check_deregister(self, check_id: str) -> None:
        return await self._client.agent.check.deregister(check_id)

    async def checks(self) -> Dict:
        return await self._client.agent.checks()

    async def session_create(self, name: str = None, **kwargs) -> str:
        if isinstance(kwargs.get("ttl"), str):
            kwargs["ttl"] = int(kwargs["ttl"].removesuffix("s"))
        return await self._client.session.create(name=name, **kwargs)

    async def session_destroy(self, session_id: str) -> bool:
        return await self._client.session.destroy(session_id)

    async def session_renew(self, session_id: str) -> bool:
        try:
            await self._client.session.renew(session_id)
            return True
        except Exception:
            return False

    async def lock_acquire(self, key: str, session_id: str, value: str = None) -> bool:
        return await self._client.kv.put(key, value, acquire=session_id)

    async def lock_release(self, key: str, session_id: str) -> bool:
        return await self._client.kv.put(key, None, release=session_id)


# 全局客户端实例
_default_client = ConsulClient()


def path_join(*args):
    return "/".join(args)


def _yaml_load(raw_value):
    return yaml.safe_load(raw_value)


def _json_load(raw_value):
    import json

    return json.loads(raw_value)


class ConfigFormat(Enum):
    Text = decode
    Number = Decimal
    Int = int
    Float = float
    Json = _json_load
    Yaml = _yaml_load
    Hcl = _hcl_load


def _resolve_format(fmt):
    if isinstance(fmt, ConfigFormat):
        return fmt.value
    return fmt


def fetch_key(key_path, fmt: Callable = None, client: Optional[ConsulClient] = None) -> Any:
    """获取配置键值。

    ``fmt`` may be a ``ConfigFormat`` member or a callable. Numeric enum
    members are unwrapped before invocation so ``Int``/``Float``/``Number`` keep
    their enum identities while still converting values.
    """
    client = client or _default_client
    __, raw = client.kv_get(key_path)
    assert raw, f"not found any content in {key_path}"
    values = raw.get("Value")
    parser = _resolve_format(fmt)
    if callable(parser):
        if isinstance(fmt, ConfigFormat) and isinstance(values, (bytes, bytearray)):
            return parser(values.decode())
        return parser(values)
    return values.decode()


def register_service(service_name, *, client: Optional[ConsulClient] = None, **kwargs):
    """注册本地 agent 服务。``client`` 为向后兼容的关键字注入。"""
    (client or _default_client).service_register(service_name, **kwargs)


def deregister(service_id, *, client: Optional[ConsulClient] = None):
    """注销本地 agent 服务。"""
    (client or _default_client).service_deregister(service_id)


def get_services(client: Optional[ConsulClient] = None) -> Dict:
    """获取本地 agent 已注册服务，格式为 ``{service_id: service_info}``。"""
    client = client or _default_client
    return client.services()


def find_service(query: str, by_id: bool = False, client: Optional[ConsulClient] = None) -> Dict:
    """按名称或ID查找本地 agent 服务，不查询 catalog。"""
    client = client or _default_client
    services = client.services()

    if by_id:
        return {k: v for k, v in services.items() if k == query}
    return {k: v for k, v in services.items() if v.get("Service") == query}


def register_check(name: str, check: Dict, *, client: Optional[ConsulClient] = None, **kwargs) -> None:
    """注册本地 agent 健康检查。"""
    (client or _default_client).check_register(name, check, **kwargs)


def deregister_check(check_id: str, *, client: Optional[ConsulClient] = None) -> None:
    """注销本地 agent 健康检查。"""
    (client or _default_client).check_deregister(check_id)


def create_session(
    name: str = None, ttl: str = "30s", *, client: Optional[ConsulClient] = None, **kwargs
) -> str:
    """创建Consul会话。"""
    return (client or _default_client).session_create(name=name, ttl=ttl, **kwargs)


def destroy_session(session_id: str, *, client: Optional[ConsulClient] = None) -> bool:
    """销毁Consul会话。"""
    return (client or _default_client).session_destroy(session_id)


def renew_session(session_id: str, *, client: Optional[ConsulClient] = None) -> bool:
    """续约Consul会话，异常返回 ``False``。"""
    return (client or _default_client).session_renew(session_id)


def acquire_lock(
    key: str, session_id: str, value: str = None, *, client: Optional[ConsulClient] = None
) -> bool:
    """获取分布式锁。"""
    return (client or _default_client).lock_acquire(key, session_id, value)


def release_lock(key: str, session_id: str, *, client: Optional[ConsulClient] = None) -> bool:
    """释放分布式锁。"""
    return (client or _default_client).lock_release(key, session_id)


def list_keys(prefix: str, client: Optional[ConsulClient] = None) -> List[Dict]:
    """列出指定前缀下的 KV 记录列表。"""
    client = client or _default_client
    index, data = client.kv_list(prefix)
    return data or []


class KvProperty:
    """Consul键值属性描述符。

    Remote path remains ``<namespace>/<prefix>/<ClassName>/<key>``. When cached,
    the value is written to the bound descriptor attribute name, not necessarily
    the remote key (``bar = KvProperty('foo')`` caches on ``bar``).
    """

    def __init__(self, key, /, prefix=None, namespace=None, format=None, cached=None):
        self.key = key
        self._prefix = "/".join(filter(None, (namespace or "properties", prefix)))
        self._fmt = format or ConfigFormat.Text
        self._cached = cached
        self._attr_name = None

    def __set_name__(self, owner, name):
        self._attr_name = name

    def __get__(self, instance, cls):
        if instance is None:
            return self
        if callable(self.key):
            name = self.key.__name__
            func = self.key
        else:
            name = self.key
            func = identity
        value = func(fetch_key("/".join([self._prefix, instance.__class__.__name__, name]), self._fmt))
        if self._cached:
            setattr(instance, self._attr_name or name, value)
        return value
