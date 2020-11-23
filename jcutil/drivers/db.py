from sqlalchemy import create_engine, engine
from typing import Union
from jcramda import loc


__all__ = [
    'connect',
    'conn',
    'init_engine',
 ]

__engines = dict()


def init_engine(tag: str, **kwargs):
    """Init a oracle engine

    :param tag: a flag with connection engine
    :param kwargs: oracle connection config

    **Options**
     * schema: default is 'oracle', can is ['oracle', 'mysql', 'sqlite', 'postgres', etc...]
     * user: database connection username
     * password: database connection password
     * dsn: database host and port dsn string
     * url: database connection url, like that: "oracle://username:password@10.0.0.5:1521/sid?encoding=utf-8

    :return:
    """
    schema = kwargs.get('schema', 'oracle')
    url = '{schema}://{user}:{password}@{dsn}?encoding=utf-8'\
        .format(schema=schema, user=kwargs['user'], password=kwargs['password'], dsn=kwargs['dsn']) \
        if 'url' not in kwargs else kwargs['url']
    current_engine = create_engine(url, pool_size=10, encoding='utf-8')
    __engines[tag] = current_engine
    return current_engine


def new_client(tag, url, **kwargs):
    __engines[tag] = create_engine(url, **kwargs)
    return __engines[tag]


def connect(n: Union[str, int] = 0) -> engine.Connection:
    if len(__engines) > 0:
        return loc(n, __engines).connect()
    raise RuntimeError('no any host can connect.')


def load(conf: dict):
    if conf and len(conf) > 0:
        for key in conf:
            init_engine(key, url=conf[key])
            # print(f'database [{key}] connected')


conn = connect


def instances():
    return [*__engines.keys()]
