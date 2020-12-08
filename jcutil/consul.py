from enum import Enum
import consul


__all__ = (
    *consul.__all__,
    'path_join',
    'fetch_key',
    'register_service',
    'deregister',
)


def path_join(*args):
    return '/'.join(args)


def _yaml_load(raw_value):
    import yaml
    return yaml.safe_load(raw_value)


def _json_load(raw_value):
    import json
    return json.loads(raw_value)


class ConfigFormat(Enum):
    Text = lambda r: str(r)
    Json = _json_load
    Yaml = _yaml_load


def fetch_key(key_path, fmt: ConfigFormat):
    raw = consul.Consul().agent.kv.get(key_path).get('Value')
    assert raw, f'not found any content in {key_path}'
    return fmt.value(raw)
    

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
    c = consul.Consul()
    c.agent.service.register(service_name, **kwargs)


def deregister(service_id):
    consul.Consul().agent.service.deregister(service_id)
