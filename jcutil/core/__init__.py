import asyncio
import base64
import hmac
import os
from _contextvars import copy_context
from functools import partial
from importlib import import_module

from jcramda import curry, compose, has_attr, encode, decode

from .jsonfy import *
from .pdtools import *

__all__ = jsonfy.__all__ + pdtools.__all__ + (
    'host_mac',
    'hmac_sha256',
    'uri_encode',
    'uri_decode',
    'nl_print',
    'c_write',
    'clear',
    'async_run',
    'load_fc',
    'obj_dumps',
    'obj_loads',
)


def host_mac():
    import uuid
    return hex(uuid.getnode())[2:].upper()


@curry
def hmac_sha256(key, s):
    cipher = hmac.new(key, s, digestmod='SHA256')
    return base64.b64encode(cipher.digest())


uri_encode = compose(decode, base64.urlsafe_b64decode, encode)
uri_decode = compose(decode, base64.urlsafe_b64decode)


# console cmd
nl_print = partial(print, end='\n\n')  # 多空一行的输出
c_write = partial(print, flush=False, end='')  # 不立刻输出的print
clear = partial(os.system, 'clear')


# async run
async def async_run(sync_func, *args, with_context=False, **kwargs):
    """

    Parameters
    ----------
    with_context:bool
            是否要copy当前进程的context， 默认：False
    sync_func
    args
    kwargs:

    Returns
    -------

    """
    loop = asyncio.get_running_loop()
    if loop.is_closed() or not loop.is_running():
        loop = asyncio.new_event_loop()
    fn = partial(sync_func, *args, **kwargs)
    if with_context:
        fn = partial(copy_context().run, fn)
    return await loop.run_in_executor(None, fn)


def load_fc(fc_name, module_name=None):
    package = None
    if ':' in fc_name:
        package = module_name
        module_name, fc_name = fc_name.rsplit(':', 1)
    assert module_name, 'module_name is not empty'
    if package and not module_name.startswith('.'):
        module_name = '.' + module_name
    w = import_module(module_name, package=package)
    return getattr(fc_name, w) if has_attr(fc_name)(w) else None


def obj_dumps(obj):
    from pickle import dumps
    from base64 import b64encode
    return b64encode(dumps(obj))


def obj_loads(raw):
    import pickle, base64
    return pickle.loads(base64.b64decode(raw))
