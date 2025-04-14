import asyncio
import logging
from importlib import import_module


def smart_load(conf):
    """智能加载配置"""
    for key in conf:
        try:
            m = import_module(f".{key}", package=__name__)
            if hasattr(m, "load"):
                r = m.load(conf[key])
                if asyncio.iscoroutine(r):
                    asyncio.get_running_loop().create_task(r)
        except ModuleNotFoundError as err:
            logging.debug("load %s failed: %s", key, err)


__all__ = ("smart_load",)
