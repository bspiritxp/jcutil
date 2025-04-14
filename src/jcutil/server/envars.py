import logging
import os
import socket
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


@lru_cache()
def local_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect(("180.76.76.76", 80))
        r = s.getsockname()[0]
    return r


def hostname():
    return socket.gethostname()


def str_bool(raw):
    if raw and raw.lower() in ("true", "t", "1"):
        return True
    return False


class Envars:
    def __init__(self):
        load_dotenv()
        self.SCHEMA = os.getenv("APP_SCHEMA", "public")
        self.APP_ENV = os.getenv("APP_ENV", "prod")
        self.APP_DEBUG = str_bool(os.getenv("APP_DEBUG"))
        self.APP_PORT = int(os.getenv("APP_PORT", 5000))
        self.CLIENT_ID = os.getenv("CLIENT_ID", hostname())
        self.CLIENT_IP = os.getenv("CLIENT_IP", local_ip())
        self.APP_NAME = os.getenv("APP_NAME", "app")
        self.IS_WORKER = str_bool(os.getenv("IS_WORKER"))
        self.CONFIG_PATH = "/".join(
            [
                os.getenv("CONSUL_KV_PATH", "config"),
                self.APP_NAME.lower(),
                self.APP_ENV.lower(),
            ]
        )
        self.CACHE_PATH = Path(os.getenv("CACHE_PATH", "/tmp")).resolve()
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        logging.basicConfig(level=self.LOG_LEVEL)


# 兼容旧版本
global_envars = Envars()
# 兼容旧版本的全局变量
SCHEMA = global_envars.SCHEMA
APP_ENV = global_envars.APP_ENV
APP_DEBUG = global_envars.APP_DEBUG
APP_PORT = global_envars.APP_PORT
CLIENT_ID = global_envars.CLIENT_ID
CLIENT_IP = global_envars.CLIENT_IP
APP_NAME = global_envars.APP_NAME
IS_WORKER = global_envars.IS_WORKER
CONFIG_PATH = global_envars.CONFIG_PATH
CACHE_PATH = global_envars.CACHE_PATH
LOG_LEVEL = global_envars.LOG_LEVEL


__all__ = (
    "Envars",
    "load_dotenv",
    "global_envars",
    "SCHEMA",
    "APP_ENV",
    "APP_DEBUG",
    "APP_PORT",
    "CLIENT_ID",
    "CLIENT_IP",
    "APP_NAME",
    "IS_WORKER",
    "CONFIG_PATH",
    "CACHE_PATH",
    "LOG_LEVEL",
)
