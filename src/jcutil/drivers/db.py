"""Tagged SQLAlchemy 2.x engine registry.

The registry owns engines, not transactions. Register an engine at application startup,
open connections at the call site, and dispose engines at application shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, Literal

try:
    from sqlalchemy import create_engine
    from sqlalchemy.engine import Connection, Engine
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False
    Connection = Engine = AsyncConnection = AsyncEngine = Any

__all__ = (
    'SQLALCHEMY_AVAILABLE',
    'register_sync',
    'register_async',
    'get_sync_engine',
    'get_async_engine',
    'connect',
    'async_connect',
    'load',
    'instances',
    'dispose_sync',
    'dispose_async',
    'init_engine',
    'new_client',
    'get_client',
    'conn',
    'close_engine',
    'close_all_engines',
)

_sync_engines: dict[str, Engine] = {}
_async_engines: dict[str, AsyncEngine] = {}


def _require_sqlalchemy() -> None:
    if not SQLALCHEMY_AVAILABLE:
        raise ImportError(
            'jcutil.drivers.db requires SQLAlchemy. Install it with `pip install sqlalchemy`.'
        )


def _ensure_unused(tag: str) -> None:
    if tag in _sync_engines or tag in _async_engines:
        raise ValueError(f"Database tag '{tag}' is already registered")


def register_sync(tag: str, url: str, **engine_options: Any) -> Engine:
    """Create and register a synchronous SQLAlchemy engine.

    ``url`` must name a synchronous dialect and driver. Pool and dialect options are
    passed unchanged to :func:`sqlalchemy.create_engine`.
    """
    _require_sqlalchemy()
    _ensure_unused(tag)
    engine = create_engine(url, **engine_options)
    _sync_engines[tag] = engine
    return engine


def register_async(tag: str, url: str, **engine_options: Any) -> AsyncEngine:
    """Create and register an asynchronous SQLAlchemy engine.

    ``url`` must name an asyncio-capable dialect and driver, for example
    ``postgresql+asyncpg://`` or ``sqlite+aiosqlite://``.
    """
    _require_sqlalchemy()
    _ensure_unused(tag)
    engine = create_async_engine(url, **engine_options)
    _async_engines[tag] = engine
    return engine


def get_sync_engine(tag: str) -> Engine:
    """Return the synchronous engine registered under ``tag``."""
    try:
        return _sync_engines[tag]
    except KeyError as error:
        if tag in _async_engines:
            raise TypeError(f"Database tag '{tag}' is asynchronous; use async_connect()") from error
        raise KeyError(f"Synchronous database tag '{tag}' is not registered") from error


def get_async_engine(tag: str) -> AsyncEngine:
    """Return the asynchronous engine registered under ``tag``."""
    try:
        return _async_engines[tag]
    except KeyError as error:
        if tag in _sync_engines:
            raise TypeError(f"Database tag '{tag}' is synchronous; use connect()") from error
        raise KeyError(f"Asynchronous database tag '{tag}' is not registered") from error


def connect(tag: str) -> Connection:
    """Open a synchronous connection for ``with`` usage.

    The caller owns transaction handling and closes the returned connection by leaving
    its context manager.
    """
    return get_sync_engine(tag).connect()


@asynccontextmanager
async def async_connect(tag: str) -> AsyncIterator[AsyncConnection]:
    """Yield an asynchronous connection for ``async with`` usage."""
    async with get_async_engine(tag).connect() as connection:
        yield connection


def load(conf: Mapping[str, Mapping[str, Any]]) -> None:
    """Register engines from tagged configuration.

    Each tag maps to a mapping containing ``url`` and a required ``mode`` of ``sync``
    or ``async``. Other keys are passed to SQLAlchemy's engine constructor.
    """
    for tag, settings in conf.items():
        if not isinstance(settings, Mapping):
            raise TypeError(f"Database configuration for '{tag}' must be a mapping")

        try:
            url = settings['url']
            mode: Literal['sync', 'async'] = settings['mode']
        except KeyError as error:
            raise ValueError(
                f"Database configuration for '{tag}' requires 'url' and 'mode'"
            ) from error

        if not isinstance(url, str):
            raise TypeError(f"Database URL for '{tag}' must be a string")
        if mode not in ('sync', 'async'):
            raise ValueError(f"Database mode for '{tag}' must be 'sync' or 'async'")

        engine_options = {key: value for key, value in settings.items() if key not in {'url', 'mode'}}
        if mode == 'sync':
            register_sync(tag, url, **engine_options)
        else:
            register_async(tag, url, **engine_options)


def instances() -> tuple[str, ...]:
    """Return all registered tags in registration order."""
    return tuple((*_sync_engines, *_async_engines))


def dispose_sync(tag: str) -> None:
    """Dispose and unregister a synchronous engine."""
    engine = get_sync_engine(tag)
    engine.dispose()
    del _sync_engines[tag]


async def dispose_async(tag: str) -> None:
    """Dispose and unregister an asynchronous engine."""
    engine = get_async_engine(tag)
    await engine.dispose()
    del _async_engines[tag]


def init_engine(tag: str, url: str, **engine_options: Any) -> Engine:
    """Compatibility name for :func:`register_sync`.

    This adapter keeps the historic synchronous entry point while delegating all
    registration and validation to the v3 registry.
    """
    return register_sync(tag, url, **engine_options)


new_client = init_engine


def _compat_tag(tag: str | int) -> str:
    if isinstance(tag, str):
        return tag
    try:
        return instances()[tag]
    except IndexError as error:
        raise KeyError(f'Database registry index {tag} is not registered') from error


def get_client(name: str | int = 0) -> Engine:
    """Compatibility name for :func:`get_sync_engine`.

    Integer registry indices remain supported only by this compatibility function;
    new code must use explicit tags.
    """
    return get_sync_engine(_compat_tag(name))


def conn(name: str | int = 0) -> Connection:
    """Compatibility name for :func:`connect`."""
    return connect(_compat_tag(name))


def close_engine(tag: str | int) -> None:
    """Compatibility name for :func:`dispose_sync`."""
    dispose_sync(_compat_tag(tag))


def close_all_engines() -> None:
    """Dispose every registered synchronous engine through :func:`dispose_sync`."""
    for tag in tuple(_sync_engines):
        dispose_sync(tag)
