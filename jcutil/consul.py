from enum import Enum
from typing import Callable
import consul
try:
    import hcl
    HasHcl = True
except ModuleNotFoundError:
    HasHcl = False


__all__ = (
    'Consul',
    'path_join',
    'fetch_key',
    'register_service',
    'deregister',
)

Consul = consul.Consul


def path_join(*args):
    return '/'.join(args)


def _yaml_load(raw_value):
    import yaml
    return yaml.safe_load(raw_value)


def _json_load(raw_value):
    import json
    return json.loads(raw_value)

if HasHcl:
    def _hcl_load(raw_value):
        import hcl
        return hcl.loads(raw_value)


class ConfigFormat(Enum):
    Json = _json_load
    Yaml = _yaml_load
    Hcl = _hcl_load if HasHcl else lambda _: None


def fetch_key(key_path, fmt: Callable = None):
    __, raw = Consul().kv.get(key_path)
    assert raw, f'not found any content in {key_path}'
    # noinspection PyCallingNonCallable
    values = raw.get('Value')
    return fmt(values) if callable(fmt) else values.decode()
    

def register_service(service_name, **kwargs):
    """

    Parameters
    ----------
    service_name
    kwargs

    See Also
    -----------
    consul.base.Service
    """
    c = Consul()
    c.agent.service.register(service_name, **kwargs)


def deregister(service_id):
    Consul().agent.service.deregister(service_id)
