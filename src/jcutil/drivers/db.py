import logging
from importlib import import_module
from typing import Any, Dict, List, Union, Optional, Callable

try:
    from sqlalchemy.engine import Engine  # pyright: ignore [reportMissingImports]
    from sqlalchemy.ext.asyncio import AsyncEngine  # pyright: ignore [reportMissingImports]
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Engine = Any
    AsyncEngine = Any

from jcramda import loc

__all__ = [
    "connect",
    "conn",
    "init_engine",
    "new_client",
    "get_client",
    "load",
    "instances",
    "close_engine",
    "close_all_engines",
]

__engines = dict()


def init_engine(tag: str, *args, create_engine: Optional[Callable] = None, **kwargs: Any) -> Engine:  # pyright: ignore [reportInvalidTypeForm]
    """Initialize a database engine

    :param tag: identifier for the connection engine
    :param create_engine: function to create database connection engine
    :param kwargs: database connection configuration

    **Options**
     * schema: default is 'oracle', supports ['oracle', 'mysql', 'sqlite', 'postgres', etc...]
     * user: database connection username
     * password: database connection password
     * dsn: database host and port dsn string
     * url: database connection url, e.g.: "oracle://username:password@10.0.0.5:1521/sid?encoding=utf-8"

    :return: configured database engine
    """
    schema = kwargs.get("schema", "oracle")
    if create_engine is None:
        sqlmodule = import_module("sqlalchemy")
        url = (
            "{schema}://{user}:{password}@{dsn}?encoding=utf-8".format(
                schema=schema,
                user=kwargs["user"],
                password=kwargs["password"],
                dsn=kwargs["dsn"],
            )
            if "url" not in kwargs
            else kwargs.pop("url")
        )
        if "async" in schema:
            current_engine = sqlmodule.create_async_engine(url, pool_size=20, **kwargs)
        else:
            current_engine = sqlmodule.create_engine(
                url, pool_size=20, **kwargs
            )
    else:
        current_engine = create_engine(*args, **kwargs)
    __engines[tag] = current_engine
    return current_engine


def new_client(tag: str, *args: Any, create_engine: Optional[Callable] = None, **kwargs: Any) -> Engine:  # pyright: ignore [reportInvalidTypeForm]
    """Create and register a new database client
    
    :param tag: identifier for the client
    :param create_engine: engine creation function
    :param kwargs: engine configuration
    :return: created database engine
    """
    if create_engine is None:
        try:
            module = import_module("sqlalchemy")
            create_engine = getattr(module, "create_engine")
        except ModuleNotFoundError as err:
            logging.error(f"SQLAlchemy not found: {err}")
            raise ImportError("SQLAlchemy is required for database operations") from err
    else:
        __engines[tag] = create_engine(*args, **kwargs)
    return __engines[tag]


def get_client(name: Union[str, int] = 0) -> Engine:  # pyright: ignore [reportInvalidTypeForm]
    """Get database engine by name or index
    
    :param name: engine identifier or index
    :return: database engine
    :raises RuntimeError: if no engines available or engine not found
    """
    if len(__engines) > 0:
        try:
            return loc(name, __engines)
        except (KeyError, IndexError) as err:
            raise RuntimeError(f"Database engine '{name}' not found") from err
    raise RuntimeError("No database engines available")


def connect(n: Union[str, int] = 0):
    """Get database connection
    
    :param n: engine identifier or index
    :return: database connection
    """
    engine = get_client(n)
    if hasattr(engine, 'connect'):
        return engine.connect()
    else:
        raise RuntimeError(f"Engine {n} does not support connection")


def load(conf: dict[str, str]) -> None:
    """
    一次性读取配置文件，生成数据库链接
    配置文件格式：dict(dbname="{dburl}")
    ```
    {
      "db1": "mysql://username:password@127.0.0.1:3306/dbname?encoding=utf8mb",
      "myoracle": "oracle://...",
    }
    ```
    @param conf: Dict[str, str]
    """
    if conf and len(conf) > 0:
        for key in conf:
            try:
                init_engine(key, url=conf[key])
            except Exception as err:
                logging.warning(f"load database [{key}] failed: {err}")
            # print(f'database [{key}] connected')


conn = connect


def instances() -> list[str]:
    """Get all registered engine identifiers
    
    :return: list of engine names
    """
    return [*__engines.keys()]


def close_engine(tag: Union[str, int]) -> None:
    """Close and remove a specific database engine
    
    :param tag: engine identifier or index
    """
    try:
        engine = get_client(tag)
        if hasattr(engine, 'dispose'):
            engine.dispose()
        if isinstance(tag, int):
            tag = instances()[tag]
        __engines.pop(tag, None)
    except Exception as err:
        logging.warning(f"Failed to close engine {tag}: {err}")


def close_all_engines() -> None:
    """Close and remove all database engines""" 
    for tag in list(instances()):
        close_engine(tag)
