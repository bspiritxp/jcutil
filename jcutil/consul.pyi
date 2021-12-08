from enum import Enum
from typing import Callable, Any, NoReturn
from consul import *


class ConfigFormat(Enum):
    Text: Callable
    Number: Callable
    Int: Callable
    Float: Callable
    Json: Callable
    Yaml: Callable
    Hcl: Callable

def path_join(*args: str) -> str: ...

def fetch_key(key_path: str, fmt: Callable) -> Any: ...

def register_service(service_name: str, **kwargs) -> NoReturn: ...

def deregister(service_id) -> NoReturn: ...

class KvProperty:
  def __init__(self, key: str, /, prefix: str = None, namespace: str = None, format: callable = None, cached: bool = None) -> None: ...
