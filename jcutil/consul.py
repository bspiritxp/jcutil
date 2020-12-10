from enum import Enum
import consul


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


class ConfigFormat(Enum):
    Text = lambda r: str(r)
    Json = _json_load
    Yaml = _yaml_load


def fetch_key(key_path, fmt: ConfigFormat):
    raw = Consul().kv.get(key_path).get('Value')
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
    c = Consul()
    c.agent.service.register(service_name, **kwargs)


def deregister(service_id):
    Consul().agent.service.deregister(service_id)
