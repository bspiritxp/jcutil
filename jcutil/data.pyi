from typing import Callable, NoReturn, Union, Any, TypeVar
from datetime import timedelta

from jcutil.defines import Writable


T = TypeVar('T')


def mem_cache(cache_dir: str = ...) -> Callable: ...

def clear_mem(path: str = ..., cache_dir: str = ...) -> NoReturn: ...

def redis_cache(expires: Union[int, timedelta], prefix: str = ...,
                redis_connector: Callable = ...,
                result_assert: Callable[[Any], bool] = ...,
                ) -> Callable[[Callable], Any]: ...

def persistence(fs: Union[Writable, Callable[[], Writable]], f: Callable[..., T]) \
        -> Callable[..., T]: ...
