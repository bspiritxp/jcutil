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


class ConsulClient:
    """Consul客户端，提供同步API封装"""

    def __init__(
        self,
        host=None,
        port=8500,
        token=None,
        scheme="http",
        consistency="default",
        dc=None,
        verify=True,
    ):
        """初始化Consul客户端

        Args:
            host: Consul主机地址
            port: Consul端口
            token: ACL token
            scheme: 协议(http/https)
            consistency: 一致性模式
            dc: 数据中心
            verify: SSL验证
        """
        if host is None:
            self._client = Consul()
        else:
            self.params = {
                "host": host,
                "port": port,
                "token": token,
                "scheme": scheme,
                "consistency": consistency,
                "dc": dc,
                "verify": verify,
            }
            self._client = Consul(**self.params)

    @property
    def client(self) -> py_consul.Consul:
        """获取客户端"""
        return self._client

    def kv_get(self, key: str, **kwargs) -> Any:
        """获取键值"""
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
        """注册服务"""
        self._client.agent.service.register(name, **kwargs)

    def service_deregister(self, service_id: str) -> None:
        """注销服务"""
        self._client.agent.service.deregister(service_id)

    def services(self) -> Dict:
        """获取所有服务"""
        return self._client.agent.services()

    def check_register(self, name: str, check: Dict, **kwargs) -> None:
        """注册健康检查"""
        self._client.agent.check.register(name, check=check, **kwargs)

    def check_deregister(self, check_id: str) -> None:
        """注销健康检查"""
        self._client.agent.check.deregister(check_id)

    def checks(self) -> Dict:
        """获取所有健康检查"""
        return self._client.agent.checks()

    def session_create(self, name: str = None, **kwargs) -> str:
        """创建会话

        Args:
            name: 会话名称
            **kwargs: 其他参数，如ttl、lock_delay等

        Returns:
            会话ID
        """
        session_id = self._client.session.create(name=name, **kwargs)
        return session_id

    def session_destroy(self, session_id: str) -> bool:
        """销毁会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        return self._client.session.destroy(session_id)

    def session_renew(self, session_id: str) -> bool:
        """续约会话

        Args:
            session_id: 会话ID

        Returns:
            是否成功
        """
        try:
            self._client.session.renew(session_id)
            return True
        except Exception:
            return False

    def lock_acquire(self, key: str, session_id: str, value: str = None) -> bool:
        """获取分布式锁

        Args:
            key: 锁键值
            session_id: 会话ID
            value: 锁的值，默认为None

        Returns:
            是否成功获取锁
        """
        return self._client.kv.put(key, value, acquire=session_id)

    def lock_release(self, key: str, session_id: str) -> bool:
        """释放分布式锁

        Args:
            key: 锁键值
            session_id: 会话ID

        Returns:
            是否成功释放锁
        """
        return self._client.kv.put(key, None, release=session_id)


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


def fetch_key(
    key_path, fmt: Callable = None, client: Optional[ConsulClient] = None
) -> Any:
    """获取配置键值

    Args:
        key_path: 键路径
        fmt: 格式化函数
        client: Consul客户端实例，默认使用全局实例

    Returns:
        解析后的值
    """
    client = client or _default_client
    __, raw = client.kv_get(key_path)
    assert raw, f"not found any content in {key_path}"
    # noinspection PyCallingNonCallable
    values = raw.get("Value")
    return fmt(values) if callable(fmt) else values.decode()


def register_service(service_name, **kwargs):
    """注册服务

    Args:
        service_name: 服务名称
        **kwargs: 其他参数

    See Also:
        consul.base.Service
    """
    _default_client.service_register(service_name, **kwargs)


def deregister(service_id):
    """注销服务

    Args:
        service_id: 服务ID
    """
    _default_client.service_deregister(service_id)


def get_services(client: Optional[ConsulClient] = None) -> Dict:
    """获取所有已注册的服务

    Args:
        client: Consul客户端实例，默认使用全局实例

    Returns:
        包含所有已注册服务的字典，格式为 {service_id: service_info}
    """
    client = client or _default_client
    return client.services()


def find_service(
    query: str, by_id: bool = False, client: Optional[ConsulClient] = None
) -> Dict:
    """按名称或ID查找服务

    Args:
        query: 服务名称或ID
        by_id: 是否按ID查找，默认为False（按名称查找）
        client: Consul客户端实例，默认使用全局实例

    Returns:
        匹配的服务字典，如果未找到则返回空字典
    """
    client = client or _default_client
    services = client.services()

    if by_id:
        # 直接按ID查找
        return {k: v for k, v in services.items() if k == query}
    else:
        # 按服务名称查找
        return {k: v for k, v in services.items() if v.get("Service") == query}


def register_check(name: str, check: Dict, **kwargs) -> None:
    """注册健康检查

    Args:
        name: 检查名称
        check: 检查配置
        **kwargs: 其他参数

    See Also:
        consul.agent.check.register
    """
    _default_client.check_register(name, check, **kwargs)


def deregister_check(check_id: str) -> None:
    """注销健康检查

    Args:
        check_id: 检查ID
    """
    _default_client.check_deregister(check_id)


def create_session(name: str = None, ttl: str = "30s", **kwargs) -> str:
    """创建Consul会话

    Args:
        name: 会话名称
        ttl: 会话超时时间
        **kwargs: 其他参数

    Returns:
        会话ID
    """
    return _default_client.session_create(name=name, ttl=ttl, **kwargs)


def destroy_session(session_id: str) -> bool:
    """销毁Consul会话

    Args:
        session_id: 会话ID

    Returns:
        是否成功
    """
    return _default_client.session_destroy(session_id)


def renew_session(session_id: str) -> bool:
    """续约Consul会话

    Args:
        session_id: 会话ID

    Returns:
        是否成功
    """
    return _default_client.session_renew(session_id)


def acquire_lock(key: str, session_id: str, value: str = None) -> bool:
    """获取分布式锁

    Args:
        key: 锁键值
        session_id: 会话ID
        value: 锁的值，默认为None

    Returns:
        是否成功获取锁
    """
    return _default_client.lock_acquire(key, session_id, value)


def release_lock(key: str, session_id: str) -> bool:
    """释放分布式锁

    Args:
        key: 锁键值
        session_id: 会话ID

    Returns:
        是否成功释放锁
    """
    return _default_client.lock_release(key, session_id)


def list_keys(prefix: str, client: Optional[ConsulClient] = None) -> List[Dict]:
    """列出指定前缀下的所有键

    Args:
        prefix: 键前缀
        client: Consul客户端实例，默认使用全局实例

    Returns:
        键值列表
    """
    client = client or _default_client
    index, data = client.kv_list(prefix)
    return data or []


class KvProperty:
    """Consul键值属性描述符"""

    def __init__(self, key, /, prefix=None, namespace=None, format=None, cached=None):
        self.key = key
        self._prefix = "/".join(filter(None, (namespace or "properties", prefix)))
        self._fmt = format or ConfigFormat.Text
        self._cached = cached

    def __get__(self, instance, cls):
        if instance is None:
            print(cls)
            return cls
        if callable(self.key):
            name = self.key.__name__
            func = self.key
        else:
            name = self.key
            func = identity
        value = func(
            fetch_key(
                "/".join([self._prefix, instance.__class__.__name__, name]), self._fmt
            )
        )
        if self._cached:
            setattr(instance, name, value)
        return value
