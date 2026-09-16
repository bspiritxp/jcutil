import json

import httpx
import pytest
from websockets.asyncio.server import serve

from jcutil.netio import EventSource, HttpClient, WebSocketClient


@pytest.mark.asyncio
async def test_http_client_reuses_injected_client_without_closing_it():
    async def handler(request):
        assert request.method == 'POST'
        assert request.url.path == '/events'
        assert json.loads(request.content) == {'event': 'created'}
        return httpx.Response(200, json={'ok': True})

    external_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url='https://example.test'
    )
    try:
        async with HttpClient(external_client) as client:
            assert await client.post_json('/events', {'event': 'created'}) == {'ok': True}
        assert not external_client.is_closed
    finally:
        await external_client.aclose()


@pytest.mark.asyncio
async def test_http_client_raises_for_unsuccessful_response():
    async def handler(request):
        return httpx.Response(404)

    async with HttpClient(transport=httpx.MockTransport(handler), base_url='https://example.test') as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_json('/missing')


@pytest.mark.asyncio
async def test_event_source_yields_decoded_event():
    async def handler(request):
        return httpx.Response(200, content=b'event: update\nid: 7\ndata: first\ndata: second\nretry: 1500\n\n')

    async with HttpClient(transport=httpx.MockTransport(handler), base_url='https://example.test') as client:
        events = [event async for event in EventSource(client, '/stream').events()]

    assert [(event.event, event.data, event.id, event.retry) for event in events] == [
        ('update', 'first\nsecond', '7', 1.5)
    ]


@pytest.mark.asyncio
async def test_websocket_client_uses_current_header_parameter():
    async def echo(connection):
        assert connection.request.headers['X-Test'] == 'modern'
        await connection.send(await connection.recv())

    async with serve(echo, '127.0.0.1', 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with WebSocketClient(
            f'ws://127.0.0.1:{port}', additional_headers={'X-Test': 'modern'}
        ) as client:
            await client.send_json({'status': 'ok'})
            assert await client.receive() == '{"status": "ok"}'
