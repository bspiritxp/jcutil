"""Async HTTP, Server-Sent Events, and WebSocket clients.

The module exposes explicit client lifecycles. Reuse :class:`HttpClient` inside an
application scope to retain HTTP connection pooling; no module-level client is created.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import aiofiles
import httpx
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.client import connect as websocket_connect

__all__ = ('HttpClient', 'EventSource', 'SseEvent', 'WebSocketClient')


class HttpClient:
    """An HTTPX client with explicit ownership and connection-pool lifecycle.

    Pass an existing :class:`httpx.AsyncClient` to share an application-managed pool,
    or pass HTTPX constructor options and use this class as an async context manager.
    """

    def __init__(self, client: httpx.AsyncClient | None = None, **client_options: Any) -> None:
        if client is not None and client_options:
            raise ValueError('Pass either an AsyncClient or client options, not both')
        self._client = client
        self._client_options = client_options
        self._owns_client = client is None

    async def __aenter__(self) -> HttpClient:
        if self._client is None:
            self._client = httpx.AsyncClient(**self._client_options)
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        await self.close()

    @property
    def client(self) -> httpx.AsyncClient:
        """Return the active HTTPX client.

        A caller-provided client is usable immediately. An owned client becomes usable
        after entering this object's async context manager.
        """
        if self._client is None:
            raise RuntimeError('Enter HttpClient with `async with` before making requests')
        return self._client

    async def close(self) -> None:
        """Close an owned client without closing a caller-provided client."""
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    async def request_json(
        self, method: str, url: str, *, json: Any = None, **request_options: Any
    ) -> Any:
        """Send a request, raise for non-success status, and decode its JSON body."""
        response = await self.client.request(method, url, json=json, **request_options)
        response.raise_for_status()
        return response.json()

    async def get_json(self, url: str, *, params: Mapping[str, Any] | None = None, **options: Any) -> Any:
        """GET and decode a JSON response."""
        return await self.request_json('GET', url, params=params, **options)

    async def post_json(self, url: str, body: Any, **options: Any) -> Any:
        """POST a JSON body and decode a JSON response."""
        return await self.request_json('POST', url, json=body, **options)

    async def put_json(self, url: str, body: Any, **options: Any) -> Any:
        """PUT a JSON body and decode a JSON response."""
        return await self.request_json('PUT', url, json=body, **options)

    async def delete_json(self, url: str, **options: Any) -> Any:
        """DELETE and decode a JSON response."""
        return await self.request_json('DELETE', url, **options)

    async def download(self, url: str, **options: Any) -> tuple[BytesIO, str | None]:
        """Download a response body into memory and return it with its content type."""
        response = await self.client.get(url, **options)
        response.raise_for_status()
        return BytesIO(response.content), response.headers.get('content-type')

    async def download_to_file(
        self,
        url: str,
        destination_path: str | Path,
        *,
        overwrite: bool = False,
        chunk_size: int = 1024 * 1024,
        **options: Any,
    ) -> Path:
        """Stream a successful response to ``destination_path`` and return that path."""
        destination = Path(destination_path)
        if destination.exists() and not overwrite:
            raise FileExistsError(destination)

        destination.parent.mkdir(parents=True, exist_ok=True)
        async with self.client.stream('GET', url, **options) as response:
            response.raise_for_status()
            async with aiofiles.open(destination, 'wb') as file:
                async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                    await file.write(chunk)
        return destination

    async def upload_file(
        self,
        url: str,
        file_path: str | Path,
        *,
        field_name: str = 'file',
        content_type: str = 'application/octet-stream',
        data: Mapping[str, Any] | None = None,
        **options: Any,
    ) -> Any:
        """Upload a local file as multipart form data and decode the JSON response."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(path)

        with path.open('rb') as file:
            response = await self.client.post(
                url,
                files={field_name: (path.name, file, content_type)},
                data=data,
                **options,
            )
        response.raise_for_status()
        return response.json()

    async def upload_bytes(
        self,
        url: str,
        file_bytes: bytes | BytesIO,
        filename: str,
        *,
        field_name: str = 'file',
        content_type: str = 'application/octet-stream',
        data: Mapping[str, Any] | None = None,
        **options: Any,
    ) -> Any:
        """Upload in-memory bytes as multipart form data and decode the JSON response."""
        if isinstance(file_bytes, BytesIO):
            file_bytes = file_bytes.getvalue()
        response = await self.client.post(
            url,
            files={field_name: (filename, file_bytes, content_type)},
            data=data,
            **options,
        )
        response.raise_for_status()
        return response.json()


@dataclass(frozen=True, slots=True)
class SseEvent:
    """A Server-Sent Event decoded from an event stream."""

    event: str
    data: str
    id: str | None
    retry: float | None


class EventSource:
    """Iterate Server-Sent Events over an already active :class:`HttpClient`.

    The caller owns reconnection policy and the HTTP client lifecycle. This class does
    not perform invisible retries or create a second connection pool.
    """

    def __init__(
        self, client: HttpClient, url: str, *, headers: Mapping[str, str] | None = None
    ) -> None:
        self._client = client
        self._url = url
        self._headers = {'Accept': 'text/event-stream', **(headers or {})}

    async def events(self) -> AsyncIterator[SseEvent]:
        """Yield parsed events until the server closes the stream or a request fails."""
        event = 'message'
        data: list[str] = []
        event_id: str | None = None
        retry: float | None = None

        async with self._client.client.stream('GET', self._url, headers=self._headers) as response:
            response.raise_for_status()
            async for raw_line in response.aiter_lines():
                if raw_line == '':
                    if data:
                        yield SseEvent(event, '\n'.join(data), event_id, retry)
                    event = 'message'
                    data = []
                    retry = None
                    continue
                if raw_line.startswith(':') or ':' not in raw_line:
                    continue

                field, value = raw_line.split(':', 1)
                if value.startswith(' '):
                    value = value[1:]
                if field == 'event':
                    event = value
                elif field == 'data':
                    data.append(value)
                elif field == 'id':
                    event_id = value
                elif field == 'retry':
                    try:
                        retry = int(value) / 1000
                    except ValueError:
                        pass


class WebSocketClient:
    """A minimal client for the current ``websockets.asyncio`` API."""

    def __init__(
        self,
        url: str,
        *,
        additional_headers: Mapping[str, str] | None = None,
        **connect_options: Any,
    ) -> None:
        self._url = url
        self._additional_headers = additional_headers
        self._connect_options = connect_options
        self._connection: ClientConnection | None = None

    async def __aenter__(self) -> WebSocketClient:
        return await self.connect()

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        await self.close()

    async def connect(self) -> WebSocketClient:
        """Open the connection once and return this client."""
        if self._connection is not None:
            raise RuntimeError('WebSocket is already connected')
        self._connection = await websocket_connect(
            self._url,
            additional_headers=self._additional_headers,
            **self._connect_options,
        )
        return self

    async def close(self) -> None:
        """Close the active connection, if any."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> ClientConnection:
        """Return the active connection."""
        if self._connection is None:
            raise RuntimeError('WebSocket is not connected')
        return self._connection

    async def send_text(self, message: str) -> None:
        """Send a text message."""
        await self.connection.send(message)

    async def send_json(self, data: Any) -> None:
        """Encode and send a JSON text message."""
        await self.send_text(json.dumps(data, ensure_ascii=False))

    async def send_bytes(self, data: bytes) -> None:
        """Send a binary message."""
        await self.connection.send(data)

    async def receive(self) -> str | bytes:
        """Receive a single text or binary message."""
        return await self.connection.recv()

    async def messages(self) -> AsyncIterator[str | bytes]:
        """Yield messages until the peer closes the connection."""
        async for message in self.connection:
            yield message
