from enum import Enum
from typing import ClassVar, Any, NoReturn
from consul import *


ConfigFormat: ClassVar[Enum]

def path_join(*args: str) -> str: ...

def fetch_key(key_path: str, fmt: ConfigFormat) -> Any: ...

def register_service(service_name: str, **kwargs) -> NoReturn: ...

def deregister(service_id) -> NoReturn: ...
