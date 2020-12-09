import logging
from importlib import import_module


def smart_load(conf):
    for key in conf:
        try:
            m = import_module(f'.{key}', package=__name__)
            m.load(conf[key])
        except ModuleNotFoundError as err:
            logging.warning(err)


__all__ = ('smart_load',)
