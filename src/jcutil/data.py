"""Function-result caches and observable background persistence.

Pickle/joblib storage must be writable only by trusted principals. Redis caches
use a versioned key namespace; legacy keys are intentionally not read.
"""

import asyncio
import base64
import binascii
import hashlib
import inspect
import json
import math
import os
import pickle
import shutil
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from contextvars import copy_context
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from functools import update_wrapper, wraps
from pathlib import Path
from uuid import UUID

from joblib import Memory, dump

from .defines import DEFAULT_CACHE_TIME
from .drivers import redis

__all__ = ["mem_cache", "clear_mem", "redis_cache", "persistence", "Persistence"]

_MISS = object()


def _cache_directory(cache_dir):
    if cache_dir is not None:
        return Path(cache_dir).expanduser()
    # Private per-user location, never the old shared /tmp/joblib directory.
    return Path.home() / ".cache" / "jcutil"


def mem_cache(cache_dir=None):
    """Return joblib's cache decorator, using a private user directory by default."""
    directory = _cache_directory(cache_dir)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return Memory(os.fspath(directory), verbose=0).cache


def clear_mem(path="", cache_dir=None):
    """Remove only a subtree of ``cache_dir/joblib``; reject traversal and symlinks.

    Dotted function paths remain supported. Missing directories are harmless;
    other filesystem errors propagate. Do not share writable cache roots with
    untrusted users (path validation is not a concurrent adversary sandbox).
    """
    raw = os.fspath(path)
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("cache path must be relative and cannot contain '..'")
    if "." in raw and "/" not in raw and "\\" not in raw and raw != ".":
        relative = Path(*raw.split("."))
    directory = _cache_directory(cache_dir).resolve()
    root = directory / "joblib"
    target = root / relative
    current = root
    for component in (None, *relative.parts):
        if component is not None:
            current /= component
        if current.is_symlink():
            raise ValueError("cache cleanup cannot follow symlinks")
    if not target.resolve().is_relative_to(root):
        raise ValueError("cache path escapes the joblib directory")
    try:
        shutil.rmtree(target)
    except FileNotFoundError:
        pass


def _typed_key(value):
    """Lossless tags for supported key values; never fall back to str/repr."""
    kind = type(value)
    if value is None:
        return ["none"]
    if isinstance(value, Enum):
        return ["enum", kind.__module__, kind.__qualname__, value.name]
    if kind in (bool, int, str):
        return [kind.__name__, value]
    if kind is float:
        return ["float", value.hex()]
    if kind is bytes:
        return ["bytes", base64.b64encode(value).decode("ascii")]
    if kind in (list, tuple):
        return [kind.__name__, [_typed_key(item) for item in value]]
    if kind is dict:
        # Dictionary order can affect the wrapped function's result.
        return ["dict", [[_typed_key(key), _typed_key(item)] for key, item in value.items()]]
    if kind in (set, frozenset):
        items = [_typed_key(item) for item in value]
        return [kind.__name__, sorted(items, key=_key_json)]
    if kind in (datetime, date):
        return [kind.__name__, value.isoformat(), getattr(value, "fold", 0)]
    if kind is timedelta:
        return ["timedelta", value.days, value.seconds, value.microseconds]
    if kind in (Decimal, UUID):
        return [kind.__name__, str(value)]
    raise TypeError(f"Unsupported cache key type {kind.__qualname__}; supply key_fn")


def _key_json(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"))


def _ttl_milliseconds(expires):
    if expires is None:
        return None
    seconds = expires.total_seconds() if isinstance(expires, timedelta) else expires
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise TypeError("expires must be seconds, timedelta, or None")
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("expires must be finite and positive, or None")
    return math.ceil(seconds * 1000)


def _json_value(value):
    # JSON mode must not silently turn tuples into lists or stringify dict keys.
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item)
        return
    raise TypeError("JSON cache values must contain only JSON-compatible types")


def _encode_value(value, codec):
    if codec == "pickle":
        return base64.b64encode(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
    _json_value(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf8")


def _decode_value(raw, codec):
    if raw is None:
        return _MISS
    try:
        if codec == "pickle":
            return pickle.loads(base64.b64decode(raw, validate=True))
        value = json.loads(raw)
        _json_value(value)
        return value
    except (EOFError, pickle.UnpicklingError, binascii.Error, ValueError,
            TypeError, UnicodeError, ImportError, AttributeError):
        return _MISS


def _sync_value(value):
    if inspect.isawaitable(value):
        if inspect.iscoroutine(value):
            value.close()
        raise TypeError("Expected a synchronous operation; use the matching client or callback type")
    return value


def redis_cache(
    expires=DEFAULT_CACHE_TIME, prefix=None, redis_connector=None, result_assert=None,
    *, namespace=None, version="1", key_fn=None, codec="pickle", cache_none=False,
):
    """Cache a function using native sync/async Redis according to its declaration.

    ``key_fn(*args, **kwargs)`` returns a supported key value. Closures require
    an explicit namespace or key_fn; callers must include any result-affecting
    captured/instance/external state. ``codec='pickle'`` preserves Python result
    types but requires trusted Redis writers. ``codec='json'`` is strict JSON.
    Redis and business errors propagate; malformed payloads are cache misses.
    Returned wrappers expose ``cache_key(...)`` and sync/async ``invalidate(...)``.
    """
    ttl = _ttl_milliseconds(expires)
    if codec not in ("pickle", "json"):
        raise ValueError("codec must be 'pickle' or 'json'")
    for name, value in (("prefix", prefix), ("namespace", namespace), ("version", version)):
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{name} must be a string")
    if result_assert is not None and not callable(result_assert):
        raise TypeError("result_assert must be callable")
    if key_fn is not None and not callable(key_fn):
        raise TypeError("key_fn must be callable")

    def decorate(function):
        signature = inspect.signature(function)
        if getattr(function, "__closure__", None) and namespace is None and key_fn is None:
            raise ValueError("Closures require an explicit namespace or key_fn")
        identity = [prefix, namespace, function.__module__, function.__qualname__, version, codec]
        scope = hashlib.sha256(_key_json(identity).encode("ascii")).hexdigest()
        is_async = inspect.iscoroutinefunction(function)

        def cache_key(*args, **kwargs):
            bound = signature.bind(*args, **kwargs)
            bound.apply_defaults()
            value = key_fn(*args, **kwargs) if key_fn is not None else dict(bound.arguments)
            try:
                encoded = _key_json(_typed_key(value)).encode("ascii")
            except RecursionError as exc:
                raise TypeError("Cyclic cache arguments require key_fn") from exc
            return f"jcutil:fc:v2:{scope}:{hashlib.sha256(encoded).hexdigest()}"

        def client():
            instance = (
                redis_connector() if redis_connector is not None
                else redis.get_async_client() if is_async else redis.get_sync_client()
            )
            if instance is None:
                raise RuntimeError("No Redis client registered for this function's sync/async mode")
            if inspect.iscoroutine(instance):
                instance.close()
                raise TypeError("redis_connector must return a client, not a coroutine")
            return instance if is_async else _sync_value(instance)

        def acceptable(value):
            if value is _MISS:
                return False
            return result_assert is None or bool(_sync_value(result_assert(value)))

        def write_options():
            return {} if ttl is None else {"px": ttl}

        if is_async:
            @wraps(function)
            async def async_wrapped(*args, update_cache=False, **kwargs):
                key = cache_key(*args, **kwargs)
                connection = client()
                if not update_cache:
                    value = _decode_value(await connection.get(key), codec)
                    if acceptable(value):
                        return value
                value = await function(*args, **kwargs)
                if value is not None or cache_none:
                    await connection.set(key, _encode_value(value, codec), **write_options())
                elif update_cache:
                    await connection.delete(key)
                return value

            async def async_invalidate(*args, **kwargs):
                return await client().delete(cache_key(*args, **kwargs))

            wrapped = async_wrapped
            invalidate = async_invalidate
        else:
            @wraps(function)
            def wrapped(*args, update_cache=False, **kwargs):
                key = cache_key(*args, **kwargs)
                connection = client()
                if not update_cache:
                    value = _decode_value(_sync_value(connection.get(key)), codec)
                    if acceptable(value):
                        return value
                value = function(*args, **kwargs)
                if inspect.isawaitable(value):
                    if inspect.iscoroutine(value):
                        value.close()
                    raise TypeError("A sync cached function must not return an awaitable; use async def")
                if value is not None or cache_none:
                    _sync_value(connection.set(key, _encode_value(value, codec), **write_options()))
                elif update_cache:
                    _sync_value(connection.delete(key))
                return value

            def invalidate(*args, **kwargs):
                return _sync_value(client().delete(cache_key(*args, **kwargs)))

        wrapped.cache_key = cache_key
        wrapped.invalidate = invalidate
        return wrapped

    return decorate


def _copy_bytes(source, destination):
    while block := source.read(1024 * 1024):
        view = memoryview(block)
        while view:
            written = _sync_value(destination.write(view))
            if type(written) is not int or not 0 < written <= len(view):
                raise OSError("binary destination.write must return a positive byte count")
            view = view[written:]


def _cleanup(action):
    """Do not replace a primary serialization/write exception with a cleanup error."""
    primary = sys.exception()
    try:
        action()
    except Exception:
        if primary is None:
            raise


def _write_snapshot(destination, snapshot, write_mode):
    """Owned factories are closed; borrowed streams remain open; paths replace atomically."""
    try:
        if isinstance(destination, (str, os.PathLike)):
            path = Path(destination)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=path.parent, prefix=f".{path.name}.", delete=False
                ) as temp:
                    temporary = Path(temp.name)
                    _copy_bytes(snapshot, temp)
                    temp.flush()
                    os.fsync(temp.fileno())
                os.replace(temporary, path)
            finally:
                if temporary is not None:
                    _cleanup(lambda: temporary.unlink(missing_ok=True))
        else:
            owned = callable(destination)
            target = _sync_value(destination()) if owned else destination
            try:
                if write_mode == "file":
                    _sync_value(target.write(snapshot))
                else:
                    _copy_bytes(snapshot, target)
                if hasattr(target, "flush"):
                    _sync_value(target.flush())
            except BaseException:
                if owned:
                    _cleanup(lambda: _sync_value(target.close()))
                raise
            else:
                if owned:
                    _sync_value(target.close())
    finally:
        _cleanup(snapshot.close)


class Persistence:
    """Callable persistence wrapper with completion futures and explicit shutdown.

    Calls return the function result as before. ``submit`` instead returns a
    concurrent Future that completes with that result after the write succeeds;
    for async functions await ``submit`` to obtain that future. ``flush`` waits
    for queued writes and raises failures; use ``aflush`` from an event loop.
    Snapshot serialization happens before returning so later mutations cannot
    alter queued data. Only destination I/O runs in a serial background worker.
    """

    def __init__(self, fs, function, *, write_mode="bytes"):
        if write_mode not in ("bytes", "file"):
            raise ValueError("write_mode must be 'bytes' or 'file'")
        if write_mode == "file" and isinstance(fs, (str, os.PathLike)):
            raise ValueError("file-object mode requires an upload destination, not a path")
        self._destination = fs
        self._function = function
        self._write_mode = write_mode
        self._async = inspect.iscoroutinefunction(function)
        self._executor = None
        self._pending = []
        self._lock = threading.Lock()
        self._closed = False
        update_wrapper(self, function, updated=())

    def _check_open(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("Persistence wrapper is closed")

    def _enqueue(self, result):
        from concurrent.futures import Future

        if inspect.isawaitable(result):
            if inspect.iscoroutine(result):
                result.close()
            raise TypeError("Use async def for a persistence function returning an awaitable")
        if result is None:
            completed = Future()
            completed.set_result(None)
            return completed
        snapshot = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
        try:
            dump(result, snapshot)
            snapshot.seek(0)
            context = copy_context()

            def save():
                _write_snapshot(self._destination, snapshot, self._write_mode)
                return result

            with self._lock:
                if self._closed:
                    raise RuntimeError("Persistence wrapper is closed")
                if self._executor is None:
                    self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jcutil-save")
                future = self._executor.submit(context.run, save)
                self._pending.append(future)
                future.add_done_callback(lambda done: snapshot.close() if done.cancelled() else None)
            return future
        except BaseException:
            _cleanup(snapshot.close)
            raise

    def __call__(self, *args, **kwargs):
        if self._async:
            return self._async_call(args, kwargs, submit=False)
        self._check_open()
        result = self._function(*args, **kwargs)
        self._enqueue(result)
        return result

    async def _async_call(self, args, kwargs, submit):
        self._check_open()
        result = await self._function(*args, **kwargs)
        future = self._enqueue(result)
        return future if submit else result

    def submit(self, *args, **kwargs):
        """Compute and queue a snapshot; return a completion Future (await for async f)."""
        if self._async:
            return self._async_call(args, kwargs, submit=True)
        self._check_open()
        return self._enqueue(self._function(*args, **kwargs))

    def flush(self):
        """Wait for writes submitted before this call; propagate their first error."""
        with self._lock:
            pending, self._pending = self._pending, []
        if pending:
            wait(pending)
            for future in pending:
                future.result()

    async def aflush(self):
        await asyncio.to_thread(self.flush)

    def close(self):
        with self._lock:
            self._closed = True
            executor = self._executor
        if executor is not None:
            executor.shutdown(wait=True)
        self.flush()

    async def aclose(self):
        await asyncio.to_thread(self.close)

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    async def __aenter__(self):
        self._check_open()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()


def persistence(fs, f, *, write_mode="bytes"):
    """Wrap a sync/async function; paths replace atomically, streams are borrowed.

    Factories return a fresh owned destination per result. For legacy upload
    sinks accepting a file object, explicitly select ``write_mode='file'``.
    Always use a context manager or close/aclose to observe background errors.
    """
    return Persistence(fs, f, write_mode=write_mode)
