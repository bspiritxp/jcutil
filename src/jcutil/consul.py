from decimal import Decimal
from enum import Enum
from typing import Any, Callable, Dict, Optional

import consul as py_consul
import hcl
import yaml
from jcramda import decode, identity


def _hcl_load(raw_value):
    return hcl.loads(raw_value)


__all__ = (
    'Consul',
    'ConsulClient',
    'path_join',
    'fetch_key',
    'register_service',
    'deregister',
)

Consul = py_consul.Consul


class ConsulClient:
    """Consul客户端，提供同步API封装"""

    def __init__(self, host='127.0.0.1', port=8500, token=None, scheme='http', consistency='default', dc=None, verify=True):
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
        self.params = {
            'host': host,
            'port': port,
            'token': token,
            'scheme': scheme,
            'consistency': consistency,
            'dc': dc,
            'verify': verify
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

    def service_register(self, name: str, **kwargs) -> None:
        """注册服务"""
        self._client.agent.service.register(name, **kwargs)

    def service_deregister(self, service_id: str) -> None:
        """注销服务"""
        self._client.agent.service.deregister(service_id)

    def services(self) -> Dict:
        """获取所有服务"""
        return self._client.agent.services()


# 全局客户端实例
_default_client = ConsulClient()


def path_join(*args):
    return '/'.join(args)


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


def fetch_key(key_path, fmt: Callable = None, client: Optional[ConsulClient] = None) -> Any:
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
    assert raw, f'not found any content in {key_path}'
    # noinspection PyCallingNonCallable
    values = raw.get('Value')
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


class KvProperty:
    """Consul键值属性描述符"""

    def __init__(self, key, /, prefix=None, namespace=None, format=None, cached=None):
        self.key = key
        self._prefix = '/'.join(filter(None, (namespace or 'properties', prefix)))
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
        value = func(fetch_key('/'.join([self._prefix, instance.__class__.__name__, name]), self._fmt))
        if self._cached:
            setattr(instance, name, value)
        return value
