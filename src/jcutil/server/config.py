import logging

from jcutil import chalk
from jcutil import consul as kv
from jcutil.drivers import smart_load
from jcutil.server.envars import global_envars

context = {}

__all__ = [
    "load_config",
    "context",
]


def load_config(*args, config_path=global_envars.CONFIG_PATH, v=True):
    """
    初始化配置，并自动加载配置中的各种底层驱动

    **如只需要读取配置信息，请勿使用此方法**
    Parameters
    ----------
    v
    args

    Returns
    -------

    """
    conf = kv.fetch_key(config_path, fmt=kv.ConfigFormat.Yaml)
    if len(args) > 0:
        needed_conf = {}
        for key in ["server", *args]:
            assert key in conf, f"not found [{key}] in kv server."
            needed_conf[key] = conf[key]
        conf = needed_conf
    if v:
        print(config_path, ":", chalk.GreenChalk(conf))
    try:
        smart_load(conf)
        context["conf"] = conf
    except Exception as err:
        logging.error("read config failed: %s", err)
