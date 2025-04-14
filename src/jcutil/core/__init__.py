import asyncio
import base64
import hmac
import os
from concurrent.futures.thread import ThreadPoolExecutor
from contextvars import copy_context
from functools import partial
from importlib import import_module

from jcramda import compose, curry, decode, encode, flatten, has_attr

from .jsonfy import (
    SafeJsonDecoder,
    SafeJsonEncoder,
    fix_document,
    from_json_file,
    pp_json,
    to_json,
    to_json_file,
    to_obj,
)
from .pdtools import TYPE_REGS, col_value, df_dt, df_to_dict, df_to_json, ser_to_json

__all__ = (
    "SafeJsonEncoder",
    "SafeJsonDecoder",
    "to_json",
    "to_json_file",
    "pp_json",
    "fix_document",
    "to_obj",
    "from_json_file",
    "col_value",
    "df_dt",
    "df_to_json",
    "ser_to_json",
    "df_to_dict",
    "TYPE_REGS",
    "host_mac",
    "hmac_sha256",
    "uri_encode",
    "uri_decode",
    "nl_print",
    "c_write",
    "clear",
    "async_run",
    "load_fc",
    "obj_dumps",
    "obj_loads",
    "init_event_loop",
    "get_running_loop",
    "map_async",
    "utcnow",
)


def init_event_loop():
    try:
        # In Python 3.13+, get_event_loop() is deprecated
        # Use get_running_loop() or new_event_loop() instead
        try:
            # Try to get the running loop first
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # If no running loop, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # Fallback for older Python versions
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def get_running_loop():
    """
    Get the current running loop or create and set a new one if none exists.
    This function is designed to be safely used in async test environments,
    as it doesn't close the loop.
    """
    try:
        loop = asyncio.get_running_loop()
        # Check if the loop is closed
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        # No running loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def host_mac():
    import uuid

    return hex(uuid.getnode())[2:].upper()


@curry
def hmac_sha256(key, s):
    cipher = hmac.new(key, s, digestmod="SHA256")
    return base64.b64encode(cipher.digest())


uri_encode = compose(decode, base64.urlsafe_b64decode, encode)
uri_decode = compose(decode, base64.urlsafe_b64decode)


# console cmd
nl_print = partial(print, end="\n\n")  # 多空一行的输出
c_write = partial(print, flush=False, end="")  # 不立刻输出的print
clear = partial(os.system, "clear")


# async run
async def async_run(sync_func, *args, with_context=False, **kwargs):
    """
    Run a synchronous function in a thread executor asynchronously.

    Parameters
    ----------
    with_context : bool
        Whether to copy the current process context, default: False
    sync_func : callable
        The synchronous function to run
    args : tuple
        Positional arguments to pass to the function
    kwargs : dict
        Keyword arguments to pass to the function

    Returns
    -------
    Any
        The result of the function call
    """
    loop = get_running_loop()
    fn = partial(sync_func, *args, **kwargs)
    if with_context:
        fn = partial(copy_context().run, fn)
    try:
        return await loop.run_in_executor(None, fn)
    except RuntimeError as e:
        # If event loop is closed, get a new one and try again
        if "Event loop is closed" in str(e):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return await loop.run_in_executor(None, fn)
        raise


def load_fc(fc_name, module_name=None):
    package = None
    if ":" in fc_name:
        package = module_name
        module_name, fc_name = fc_name.rsplit(":", 1)
    assert module_name, "module_name is not empty"
    if package and not module_name.startswith("."):
        module_name = "." + module_name
    w = import_module(module_name, package=package)
    return getattr(w, fc_name) if has_attr(fc_name)(w) else None


def obj_dumps(obj):
    from base64 import b64encode
    from pickle import dumps

    return b64encode(dumps(obj))


def obj_loads(raw):
    import base64
    import pickle

    return pickle.loads(base64.b64decode(raw))


def _splitor(data, start, limit):
    return data[start : start + limit]


def map_async(func, data, limit=None, splitor=_splitor):
    if limit is None:
        cpu_count = os.cpu_count() or 1
        data_len = len(data)
        # If data is smaller than CPU count, use 1 as limit
        # to ensure we process at least one item per chunk
        limit = max(1, int(data_len / cpu_count))
    loop = get_running_loop()
    tasks = []
    start = 0
    block = splitor(data, start, limit)
    with ThreadPoolExecutor() as pool:
        while len(block) > 0:
            tasks.append(
                loop.run_in_executor(pool, lambda d: [func(x) for x in d], block)
            )
            start += limit
            block = splitor(data, start, limit)

    result = loop.run_until_complete(asyncio.gather(*tasks))
    return flatten(result)


def utcnow():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)
