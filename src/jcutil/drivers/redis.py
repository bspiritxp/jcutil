"""Tagged synchronous and asyncio Redis clients backed by redis-py."""

import asyncio
import time
from datetime import timedelta
from functools import wraps
from typing import Any, Optional, Union
from uuid import uuid4

from redis import Redis as SyncRedis
from redis import RedisCluster as SyncRedisCluster
from redis.asyncio import Redis as AsyncRedis
from redis.asyncio.cluster import RedisCluster as AsyncRedisCluster

from jcutil.core import get_running_loop

SyncRedisClient = Union[SyncRedis, SyncRedisCluster]
AsyncRedisClient = Union[AsyncRedis, AsyncRedisCluster]

__sync_clients: dict[object, SyncRedisClient] = {}
__async_clients: dict[object, AsyncRedisClient] = {}


def _client_options(uri: str) -> tuple[str, bool]:
    """Translate jcutil's legacy ``cluster://`` URI to a redis-py URI."""
    if uri.startswith('cluster://'):
        return f'redis://{uri.removeprefix("cluster://")}', True
    return uri, False


def _client_tag(tag: Optional[Union[str, int]]) -> object:
    return uuid4() if tag is None else tag


def new_sync_client(uri: str, tag: Optional[Union[str, int]] = None) -> SyncRedisClient:
    """Create and register a synchronous redis-py client under ``tag``."""
    key = _client_tag(tag)
    normalized_uri, is_cluster = _client_options(uri)
    client = (
        SyncRedisCluster.from_url(normalized_uri)
        if is_cluster
        else SyncRedis.from_url(normalized_uri)
    )
    __sync_clients[key] = client
    return client


async def new_async_client(uri: str, tag: Optional[Union[str, int]] = None) -> AsyncRedisClient:
    """Create and register an asyncio redis-py client under ``tag``."""
    key = _client_tag(tag)
    normalized_uri, is_cluster = _client_options(uri)
    client = (
        AsyncRedisCluster.from_url(normalized_uri)
        if is_cluster
        else AsyncRedis.from_url(normalized_uri)
    )
    __async_clients[key] = client
    return client


new_client = new_async_client


def get_sync_client(tag: Optional[Union[str, int]] = None) -> Optional[SyncRedisClient]:
    """Return a registered synchronous client, or ``None`` when unavailable."""
    if tag is None:
        return next(iter(__sync_clients.values()), None)
    return __sync_clients.get(tag)


def get_async_client(tag: Optional[Union[str, int]] = None) -> Optional[AsyncRedisClient]:
    """Return a registered asyncio client, or ``None`` when unavailable."""
    if tag is None:
        return next(iter(__async_clients.values()), None)
    return __async_clients.get(tag)


get_client = get_async_client
connect = conn = get_client
connect_sync = sync_conn = get_sync_client


def load_sync(conf: dict[str, Any]) -> None:
    """Register synchronous clients for every tagged URI in ``conf``."""
    for key, uri in conf.items():
        new_sync_client(uri, key)


async def _load_async_clients(conf: dict[str, Any]) -> None:
    await asyncio.gather(*(new_async_client(uri, key) for key, uri in conf.items()))


def load(conf: dict[str, Any]):
    """Register asynchronous clients, preserving the legacy ``smart_load`` contract."""
    if not conf:
        return None

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        loop = get_running_loop()
        loop.run_until_complete(_load_async_clients(conf))
        return None
    return _load_async_clients(conf)


def close_sync_client(tag: Optional[Union[str, int]] = None) -> None:
    """Close and unregister one synchronous client, or every registered client."""
    if tag is not None:
        client = __sync_clients.pop(tag, None)
        if client is not None:
            client.close()
        return

    clients = tuple(__sync_clients.values())
    __sync_clients.clear()
    for client in clients:
        client.close()


async def aclose_async_client(tag: Optional[Union[str, int]] = None) -> None:
    """Close and unregister one asyncio client, or every registered client."""
    if tag is not None:
        client = __async_clients.pop(tag, None)
        if client is not None:
            await client.aclose()
        return

    clients = tuple(__async_clients.values())
    __async_clients.clear()
    await asyncio.gather(*(client.aclose() for client in clients))


class Lock:
    """Distributed lock implemented with the registered asynchronous client."""

    def __init__(self, tag, lock_flg):
        client = connect(tag)
        if client is None:
            raise RuntimeError(f'Redis client not found: {tag}')
        self._client = client
        self._flg = lock_flg
        self._owner = False

    async def acquire(self, blocking=True, timeout=None):
        """Acquire the lock, optionally waiting up to ``timeout`` seconds."""
        if self._owner:
            return True
        if not blocking and timeout is not None:
            raise ValueError("can't specify timeout for non-blocking acquire")
        start_time = int(time.time())
        while await self._client.exists(self._flg):
            if not blocking:
                break
            await asyncio.sleep(0.5)
            curr_time = int(time.time())
            if isinstance(timeout, int) and curr_time - start_time > timeout:
                return False
        acquired = await self._client.setnx(self._flg, int(time.time()))
        if acquired:
            self._owner = True
            return True
        return False

    async def release(self):
        if self._owner:
            await self._client.delete(self._flg)
            self._owner = False

    @property
    def locked(self):
        return self._owner


class SpinLock(Lock):
    """Async context-manager wrapper around :class:`Lock`."""

    def __init__(self, tag, flag, blocking=True, timeout=None):
        super().__init__(tag, flag)
        self._blocking = blocking
        self._timeout = timeout

    async def __aenter__(self):
        acquired = await self.acquire(self._blocking, self._timeout)
        if not acquired:
            raise RuntimeError(f'Cannot acquire lock: {self._flg}')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()


class IntervalLimitError(RuntimeError):
    pass


def interval_lock(flg, name, timeout=timedelta(seconds=3)):
    """Reject calls made while the asynchronous Redis interval key exists."""

    def limit_ann(fn):
        @wraps(fn)
        async def wrapped(*args, **kwargs):
            client = connect(flg)
            if client is None:
                raise RuntimeError(f'Redis client not found: {flg}')
            time_limit = int(timeout.total_seconds())
            if await client.exists(name):
                raise IntervalLimitError(f'time interval limit in {time_limit}s')
            await client.setnx(name, time.time())
            await client.expire(name, time_limit)
            return await fn(*args, **kwargs)

        return wrapped

    return limit_ann
