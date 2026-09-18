"""Async HTTP requests, streaming file transfers, SSE, and WebSocket connections.

Reuse an application-scoped HttpClient. No import-time I/O, implicit retries, or
synchronous networking API; local file operations run outside the event loop.
"""

from __future__ import annotations

import asyncio
import os
import re
import stat
import sys
from collections.abc import AsyncGenerator, AsyncIterable, AsyncIterator, Awaitable, Mapping
from contextlib import aclosing, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, TypeVar
from uuid import uuid4

import aiofiles
import httpx
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as websocket_connect

__all__ = ('HttpClient', 'SseEvent', 'websocket')

_T = TypeVar('_T')
_CHUNK_SIZE = 1024 * 1024


async def _finish(operation: Awaitable[_T]) -> _T:
    """Join in-flight disk I/O before cancellation permits resource cleanup."""
    task = asyncio.ensure_future(operation)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # A second cancellation must not abandon a thread still using the file.
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except Exception:
                break
        if not task.cancelled():
            task.exception()
        raise


@asynccontextmanager
async def _file(path: Path, mode: Literal['rb', 'xb']) -> AsyncIterator[Any]:
    opening = asyncio.ensure_future(aiofiles.open(path, mode))
    try:
        file = await asyncio.shield(opening)
    except asyncio.CancelledError:
        # Opening creates a resource: recover and close it even if cancelled.
        try:
            file = await _finish(asyncio.shield(opening))
        except asyncio.CancelledError:
            file = opening.result()
        await _finish(file.close())
        raise
    try:
        yield file
    finally:
        primary = sys.exception()
        try:
            await _finish(file.close())
        except Exception:
            if primary is None:
                raise


def _chunk_size(value: int) -> None:
    if type(value) is not int or value <= 0:
        raise ValueError('chunk_size must be a positive integer')


def _disposition(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError('Multipart names and filenames must be strings')
    if '\x00' in value:
        raise ValueError('Multipart names and filenames cannot contain NUL')
    return value.replace('\\', '%5C').replace('\r', '%0D').replace('\n', '%0A').replace('"', '%22')


@dataclass(frozen=True, slots=True)
class SseEvent:
    """One SSE event; id and retry (seconds) retain stream-level state."""

    event: str
    data: str
    id: str | None
    retry: float | None


async def _sse_lines(response: httpx.Response) -> AsyncGenerator[str, None]:
    # HTTPX's aiter_lines also splits Unicode separators; SSE permits only CR/LF.
    parts: list[str] = []
    skip_lf = False
    async for text in response.aiter_text():
        if skip_lf:
            text = text.removeprefix('\n')
        start = 0
        for ending in re.finditer(r'\r\n|\r|\n', text):
            parts.append(text[start:ending.start()])
            yield ''.join(parts)
            parts.clear()
            start = ending.end()
        if start < len(text):
            parts.append(text[start:])
        skip_lf = text.endswith('\r')
    if parts:
        yield ''.join(parts)


async def _events(response: httpx.Response) -> AsyncGenerator[SseEvent, None]:
    event = ''
    data: list[str] = []
    event_id = None
    retry = None
    first = True
    async for line in _sse_lines(response):
        if first:
            line = line.removeprefix('\ufeff')
            first = False
        if not line:
            if data:
                yield SseEvent(event or 'message', '\n'.join(data), event_id, retry)
            event, data = '', []
            continue
        if line.startswith(':'):
            continue
        field, _, value = line.partition(':')
        if value.startswith(' '):
            value = value[1:]
        if field == 'data':
            data.append(value)
        elif field == 'event':
            event = value
        elif field == 'id' and '\x00' not in value:
            event_id = value
        elif field == 'retry' and value.isascii() and value.isdigit():
            try:
                retry = int(value) / 1000
            except (ValueError, OverflowError):
                pass


class HttpClient:
    """Task-oriented async HTTP using an owned or borrowed HTTPX connection pool.

    An owned pool requires ``async with``. An injected AsyncClient is immediately
    usable and is never closed by this wrapper. ``aclose`` is terminal for the
    wrapper in either case. HTTPX options, timeouts, and exceptions are preserved.
    """

    def __init__(self, client: httpx.AsyncClient | None = None, **client_options: Any) -> None:
        if client is not None and not isinstance(client, httpx.AsyncClient):
            raise TypeError('client must be an httpx.AsyncClient')
        if client is not None and client_options:
            raise ValueError('Pass either an AsyncClient or client options, not both')
        self._client = client
        self._client_options = client_options
        self._owns_client = client is None
        self._closed = False
        self._entered = False

    async def __aenter__(self) -> HttpClient:
        if self._closed or self._entered:
            raise RuntimeError('HttpClient is closed or already entered')
        if self._client is None:
            self._client = httpx.AsyncClient(**self._client_options)
        self._entered = True
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        await self.aclose()

    def _active(self) -> httpx.AsyncClient:
        if self._closed:
            raise RuntimeError('HttpClient is closed')
        if self._client is None:
            raise RuntimeError('Enter HttpClient with `async with` before making requests')
        return self._client

    async def aclose(self) -> None:
        """Close this wrapper and its owned pool, never a borrowed pool."""
        if self._closed:
            return
        self._closed = True
        if self._owns_client and self._client is not None:
            await _finish(self._client.aclose())

    async def request(self, method: str, url: str, **options: Any) -> httpx.Response:
        """Return a buffered response, raising HTTPStatusError for non-2xx status."""
        response = await self._active().request(method, url, **options)
        response.raise_for_status()
        return response

    async def json(self, url: str, *, method: str = 'GET', **options: Any) -> Any:
        """Request and decode JSON; use request() for empty/non-JSON responses."""
        return (await self.request(method, url, **options)).json()

    @asynccontextmanager
    async def stream(
        self, url: str, *, method: str = 'GET', **options: Any
    ) -> AsyncIterator[httpx.Response]:
        """Yield a streaming response; close it on error, cancellation, or early exit."""
        async with self._active().stream(method, url, **options) as response:
            response.raise_for_status()
            yield response

    async def download(
        self, url: str, destination: str | Path, *, overwrite: bool = False,
        chunk_size: int = _CHUNK_SIZE, **options: Any,
    ) -> Path:
        """Stream GET to a sibling temporary file and atomically publish its Path.

        Existing destinations are never replaced unless overwrite=True. Failures
        before publication preserve them. Cancellation during publication may leave
        a fully downloaded file, never a partial destination. No resume or fsync
        durability guarantee. HTTPX content decoding is applied to downloaded bytes.
        """
        _chunk_size(chunk_size)
        self._active()
        path = Path(destination)
        if not overwrite and await asyncio.to_thread(os.path.lexists, path):
            raise FileExistsError(path)
        temporary = path.with_name(f'.{path.name}.{uuid4().hex}.part')
        async with self.stream(url, **options) as response:
            await _finish(asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True))
            try:
                async with _file(temporary, 'xb') as file:
                    async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                        await _finish(file.write(chunk))
                if overwrite:
                    await _finish(asyncio.to_thread(os.replace, temporary, path))
                else:
                    # Unlike an exists()+replace() sequence, link is race-safe.
                    await _finish(asyncio.to_thread(os.link, temporary, path))
            finally:
                primary = sys.exception()
                try:
                    await _finish(asyncio.to_thread(temporary.unlink, missing_ok=True))
                except OSError:
                    if primary is None:
                        raise
        return path

    async def upload(
        self, url: str, source: str | Path | bytes | AsyncIterable[bytes], *,
        filename: str | None = None, field_name: str = 'file',
        content_type: str = 'application/octet-stream', data: Mapping[str, str] | None = None,
        multipart: bool = True, method: str = 'POST', chunk_size: int = _CHUNK_SIZE,
        **options: Any,
    ) -> httpx.Response:
        """Stream a path, bytes, or async byte iterable and return the HTTP response.

        Multipart is the default; bytes/iterables need an explicit filename. Raw
        uploads use multipart=False (e.g. object-store PUT). Bytes and regular files
        include Content-Length without buffering; unknown lengths use HTTP/1.1
        chunked framing, which the server must support. No implicit retry
        or rewind. Caller-owned iterables aren't closed; manage their lifetime.
        """
        _chunk_size(chunk_size)
        self._active()
        if not isinstance(source, (str, Path, bytes, AsyncIterable)):
            raise TypeError('source must be a path, bytes, or an async byte iterable')
        if any(key in options for key in ('content', 'files', 'json')):
            raise ValueError('upload owns the request body; do not pass content, files, or json')
        if not content_type or any(c in content_type for c in '\r\n\x00'):
            raise ValueError('content_type must be a nonempty header value')
        path = Path(source) if isinstance(source, (str, Path)) else None
        prefix: list[bytes] = []
        suffix = b''
        if multipart:
            filename = filename if filename is not None else (path.name if path else None)
            if filename is None:
                raise ValueError('Multipart bytes/streams require filename')
            boundary = uuid4().hex
            for name, value in (data or {}).items():
                if not isinstance(value, str):
                    raise TypeError('Multipart field values must be strings')
                prefix.append(
                    f'--{boundary}\r\nContent-Disposition: form-data; '
                    f'name="{_disposition(name)}"\r\n\r\n{value}\r\n'.encode()
                )
            prefix.append((
                f'--{boundary}\r\nContent-Disposition: form-data; '
                f'name="{_disposition(field_name)}"; filename="{_disposition(filename)}"\r\n'
                f'Content-Type: {content_type}\r\n\r\n'
            ).encode())
            suffix = f'\r\n--{boundary}--\r\n'.encode()
            header = f'multipart/form-data; boundary={boundary}'
        else:
            if filename is not None or data is not None or field_name != 'file':
                raise ValueError('Raw uploads do not accept filename or form fields')
            header = content_type

        headers = httpx.Headers(options.pop('headers', None))
        if any(name in headers for name in ('content-type', 'content-length', 'transfer-encoding')):
            raise ValueError('upload controls Content-Type and body framing headers')
        if any(name in self._active().headers for name in ('content-length', 'transfer-encoding')):
            raise ValueError('Upload pools must not define fixed body framing headers')
        headers['Content-Type'] = header

        async def chunks(file: Any = None) -> AsyncGenerator[bytes, None]:
            if file is not None:
                while chunk := await _finish(file.read(chunk_size)):
                    yield chunk
            elif isinstance(source, bytes):
                for offset in range(0, len(source), chunk_size):
                    yield source[offset:offset + chunk_size]
            elif isinstance(source, AsyncIterable):
                async for chunk in source:
                    if not isinstance(chunk, bytes):
                        raise TypeError('Upload stream must yield bytes')
                    yield chunk

        async def body(file: Any = None) -> AsyncGenerator[bytes, None]:
            for part in prefix:
                yield part
            async with aclosing(chunks(file)) as content:
                async for chunk in content:
                    yield chunk
            if suffix:
                yield suffix

        async def send(file: Any = None) -> httpx.Response:
            size = len(source) if isinstance(source, bytes) else None
            if file is not None:
                info = await _finish(asyncio.to_thread(os.fstat, file.fileno()))
                if stat.S_ISREG(info.st_mode):
                    size = info.st_size
            if size is not None:
                headers['Content-Length'] = str(size + sum(map(len, prefix)) + len(suffix))
            async with aclosing(body(file)) as content:
                return await self.request(method, url, content=content, headers=headers, **options)

        if path is not None:
            async with _file(path, 'rb') as file:
                return await send(file)
        return await send()

    @asynccontextmanager
    async def events(self, url: str, **options: Any) -> AsyncIterator[AsyncIterator[SseEvent]]:
        """Yield an SSE iterator with deterministic early-exit cleanup, no reconnect.

        Last-Event-ID, request timeouts, and reconnection policy belong to callers.
        Only blank-line-completed events are emitted, per the SSE protocol.
        """
        headers = httpx.Headers(options.pop('headers', None))
        headers.setdefault('Accept', 'text/event-stream')
        async with self.stream(url, headers=headers, **options) as response:
            if response.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'text/event-stream':
                raise ValueError('SSE requires a text/event-stream response')
            response.encoding = 'utf-8'
            async with aclosing(_events(response)) as events:
                yield events


@asynccontextmanager
async def websocket(url: str, **options: Any) -> AsyncIterator[ClientConnection]:
    """Open a native async WebSocket; use send(), recv(), or async iteration.

    Connection options pass to websockets.asyncio.client.connect, including
    additional_headers. Leaving the context closes the connection; no reconnect.
    """
    async with websocket_connect(url, **options) as connection:
        yield connection
