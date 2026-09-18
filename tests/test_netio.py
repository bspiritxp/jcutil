import asyncio
import json
import threading
from email import policy
from email.parser import BytesParser

import aiofiles.threadpool
import httpx
import pytest
from websockets.asyncio.server import serve

from jcutil.netio import HttpClient, SseEvent, websocket


async def _body(*chunks, error=None):
    for chunk in chunks:
        yield chunk
    if error is not None:
        raise error


class _ResponseStream(httpx.AsyncByteStream):
    def __init__(self, body):
        self.body = body
        self.closed = False

    async def __aiter__(self):
        async for chunk in self.body:
            yield chunk

    async def aclose(self):
        self.closed = True
        await self.body.aclose()


@pytest.mark.asyncio
async def test_injected_client_is_immediately_usable_but_wrapper_closes():
    async def handler(request):
        assert request.method == 'POST'
        assert request.url.path == '/events'
        assert json.loads(request.content) == {'event': 'created'}
        return httpx.Response(200, json={'ok': True})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url='https://example.test'
    ) as external:
        client = HttpClient(external)
        assert await client.json('/events', method='POST', json={'event': 'created'}) == {
            'ok': True
        }
        await client.aclose()
        await client.aclose()
        with pytest.raises(RuntimeError):
            await client.request('GET', '/closed')
        with pytest.raises(RuntimeError):
            async with client:
                pytest.fail('A closed wrapper must not reopen')
        assert (await external.post('/events', json={'event': 'created'})).json() == {
            'ok': True
        }


@pytest.mark.asyncio
async def test_context_does_not_close_borrowed_pool_on_exception():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text='alive')),
        base_url='https://example.test',
    ) as external:
        with pytest.raises(LookupError):
            async with HttpClient(external) as client:
                assert (await client.request('GET', '/')).text == 'alive'
                raise LookupError('application failure')
        assert (await external.get('/')).text == 'alive'
        with pytest.raises(RuntimeError):
            await client.request('GET', '/')


@pytest.mark.asyncio
async def test_owned_client_requires_context_and_closes_transport():
    class Transport(httpx.AsyncBaseTransport):
        closed = False

        async def handle_async_request(self, request):
            return httpx.Response(200, text='ready')

        async def aclose(self):
            self.closed = True

    transport = Transport()
    client = HttpClient(transport=transport, base_url='https://example.test')
    with pytest.raises(RuntimeError):
        await client.request('GET', '/')
    async with client:
        assert (await client.request('GET', '/')).text == 'ready'
        assert (await client.request('GET', '/again')).text == 'ready'
    assert transport.closed
    with pytest.raises(RuntimeError):
        async with client:
            pytest.fail('An owned client cannot reopen its closed pool')


@pytest.mark.asyncio
async def test_request_buffers_response_and_rejects_error_status():
    body = _ResponseStream(_body(b'first', b'second'))

    async def handler(request):
        if request.url.path == '/missing':
            return httpx.Response(404, text='missing')
        return httpx.Response(200, stream=body)

    async with HttpClient(
        transport=httpx.MockTransport(handler), base_url='https://example.test'
    ) as client:
        response = await client.request('GET', '/')
        assert response.content == b'firstsecond'
        assert body.closed
        with pytest.raises(httpx.HTTPStatusError) as error:
            await client.json('/missing')
        assert error.value.response.status_code == 404


@pytest.mark.asyncio
async def test_stream_closes_response_after_early_consumer_exit():
    pulled = []

    async def body():
        pulled.append('first')
        yield b'first'
        pulled.append('second')
        yield b'second'

    source = _ResponseStream(body())
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=source))
    ) as client:
        async with client.stream('https://example.test/') as response:
            async for chunk in response.aiter_bytes():
                assert chunk == b'first'
                break
            assert not source.closed
        assert response.is_closed
        assert source.closed
        assert pulled == ['first']


@pytest.mark.asyncio
async def test_stream_error_status_closes_response_without_yielding():
    source = _ResponseStream(_body(b'forbidden'))
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(403, stream=source))
    ) as client:
        with pytest.raises(httpx.HTTPStatusError):
            async with client.stream('https://example.test/'):
                pytest.fail('Error responses must not reach the consumer')
    assert source.closed


@pytest.mark.asyncio
async def test_download_creates_parents_and_atomically_replaces_existing_file(tmp_path):
    destination = tmp_path / 'nested' / 'payload.bin'
    async with HttpClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=_ResponseStream(_body(b'first', b' file')))
        )
    ) as client:
        assert await client.download('https://example.test/', destination, chunk_size=3) == destination
    assert destination.read_bytes() == b'first file'

    async def replacement():
        assert destination.read_bytes() == b'first file'
        yield b'new '
        assert destination.read_bytes() == b'first file'
        yield b'contents'

    source = _ResponseStream(replacement())
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=source))
    ) as client:
        await client.download('https://example.test/', destination, overwrite=True, chunk_size=2)
    assert source.closed
    assert destination.read_bytes() == b'new contents'
    assert set(destination.parent.iterdir()) == {destination}


@pytest.mark.asyncio
async def test_download_does_not_overwrite_destination_created_during_transfer(tmp_path):
    destination = tmp_path / 'payload.bin'

    async def body():
        yield b'first'
        destination.write_bytes(b'concurrent writer')
        yield b'second'

    source = _ResponseStream(body())
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=source))
    ) as client:
        with pytest.raises(FileExistsError):
            await client.download('https://example.test/', destination, chunk_size=2)
    assert destination.read_bytes() == b'concurrent writer'
    assert source.closed
    assert set(tmp_path.iterdir()) == {destination}


@pytest.mark.asyncio
async def test_download_default_preserves_existing_file(tmp_path):
    destination = tmp_path / 'payload.bin'
    destination.write_bytes(b'keep')
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'replace'))
    ) as client:
        with pytest.raises(FileExistsError):
            await client.download('https://example.test/', destination)
    assert destination.read_bytes() == b'keep'
    assert set(tmp_path.iterdir()) == {destination}


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['status', 'transport'])
async def test_failed_download_preserves_previous_destination(tmp_path, failure):
    destination = tmp_path / 'payload.bin'
    destination.write_bytes(b'previous')
    error = httpx.ReadError('connection lost') if failure == 'transport' else None
    source = _ResponseStream(_body(b'partial', error=error))
    status = 200 if failure == 'transport' else 503
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, stream=source))
    ) as client:
        with pytest.raises(httpx.ReadError if error else httpx.HTTPStatusError):
            await client.download('https://example.test/', destination, overwrite=True, chunk_size=2)
    assert destination.read_bytes() == b'previous'
    assert source.closed
    assert set(tmp_path.iterdir()) == {destination}


@pytest.mark.asyncio
async def test_cancelled_download_closes_response_and_removes_partial_file(tmp_path):
    destination = tmp_path / 'payload.bin'
    destination.write_bytes(b'previous')
    waiting = asyncio.Event()

    async def body():
        yield b'partial'
        waiting.set()
        await asyncio.Future()

    source = _ResponseStream(body())
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, stream=source))
    ) as client:
        task = asyncio.create_task(
            client.download('https://example.test/', destination, overwrite=True, chunk_size=2)
        )
        try:
            await asyncio.wait_for(waiting.wait(), timeout=5)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert destination.read_bytes() == b'previous'
    assert source.closed
    assert set(tmp_path.iterdir()) == {destination}


@pytest.mark.asyncio
async def test_transfers_reject_zero_chunk_size(tmp_path):
    chunk_size = 0
    async with HttpClient(transport=httpx.MockTransport(lambda request: httpx.Response(200))) as client:
        with pytest.raises(ValueError):
            await client.download('https://example.test/', tmp_path / 'file', chunk_size=chunk_size)
        with pytest.raises(ValueError):
            await client.upload(
                'https://example.test/', b'content', filename='file', chunk_size=chunk_size
            )
    assert not (tmp_path / 'file').exists()


@pytest.mark.asyncio
@pytest.mark.parametrize('source_kind', ['path', 'bytes', 'async'])
async def test_multipart_upload_contains_exact_file_and_text_fields(tmp_path, source_kind):
    payload = b'\x00binary\r\ncontent\xff'
    filename = 'payload.bin'
    if source_kind == 'path':
        source = tmp_path / filename
        source.write_bytes(payload)
        options = {}
    elif source_kind == 'bytes':
        source = payload
        options = {'filename': filename}
    else:
        source = _body(payload[:4], payload[4:])
        options = {'filename': filename}

    async def handler(request):
        if source_kind != 'async':
            assert int(request.headers['content-length']) == len(request.content)
            assert 'transfer-encoding' not in request.headers
        message = BytesParser(policy=policy.default).parsebytes(
            f'Content-Type: {request.headers["content-type"]}\r\nMIME-Version: 1.0\r\n\r\n'.encode()
            + request.content
        )
        assert message.is_multipart()
        parts = {part.get_param('name', header='content-disposition'): part for part in message.iter_parts()}
        assert set(parts) == {'attachment', 'title'}
        assert parts['attachment'].get_filename() == filename
        assert parts['attachment'].get_content_type() == 'application/octet-stream'
        assert parts['attachment'].get_payload(decode=True) == payload
        assert parts['title'].get_payload(decode=True).decode('utf-8') == 'résumé'
        return httpx.Response(201, content=b'accepted', headers={'content-type': 'text/plain'})

    async with HttpClient(transport=httpx.MockTransport(handler)) as client:
        response = await client.upload(
            'https://example.test/', source, field_name='attachment',
            data={'title': 'résumé'}, chunk_size=3, **options,
        )
    assert response.status_code == 201
    assert response.content == b'accepted'


@pytest.mark.asyncio
async def test_multipart_disposition_cannot_inject_headers():
    async def handler(request):
        message = BytesParser(policy=policy.default).parsebytes(
            f'Content-Type: {request.headers["content-type"]}\r\n\r\n'.encode() + request.content
        )
        parts = list(message.iter_parts())
        assert len(parts) == 1
        assert parts[0].get_payload(decode=True) == b'payload'
        assert parts[0].get('X-Injected') is None
        assert parts[0].get_content_type() == 'application/octet-stream'
        disposition = parts[0]['content-disposition']
        assert disposition.content_disposition == 'form-data'
        assert 'filename' in disposition.params
        assert 'name' in disposition.params
        return httpx.Response(200)

    async with HttpClient(transport=httpx.MockTransport(handler)) as client:
        await client.upload(
            'https://example.test/', b'payload',
            filename='file"\r\nX-Injected: true\r\n.bin',
            field_name='upload"\r\nX-Injected: true',
        )


@pytest.mark.asyncio
async def test_upload_validates_metadata_and_status():
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(422, text='rejected'))
    ) as client:
        with pytest.raises(ValueError):
            await client.upload('https://example.test/', b'payload')
        with pytest.raises(ValueError):
            await client.upload('https://example.test/', _body(b'payload'))
        with pytest.raises(ValueError):
            await client.upload(
                'https://example.test/', b'payload', filename='file',
                content_type='text/plain\r\nX-Injected: true',
            )
        with pytest.raises(ValueError):
            await client.upload('https://example.test/', b'payload', multipart=False, filename='file')
        with pytest.raises(ValueError):
            await client.upload('https://example.test/', b'payload', multipart=False, data={'a': 'b'})
        with pytest.raises(httpx.HTTPStatusError) as error:
            await client.upload('https://example.test/', b'payload', multipart=False)
    assert error.value.response.status_code == 422


@pytest.mark.asyncio
async def test_raw_async_upload_is_consumer_driven_and_exhausts_source():
    produced = []
    received = []
    first_received = asyncio.Event()
    resume = asyncio.Event()
    source_closed = asyncio.Event()

    async def source():
        try:
            for chunk in (b'first', b'second'):
                produced.append(chunk)
                yield chunk
        finally:
            source_closed.set()

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            async for chunk in request.stream:
                received.append(chunk)
                if len(received) == 1:
                    first_received.set()
                    await resume.wait()
            return httpx.Response(200, json={'received': b''.join(received).decode()})

    async with HttpClient(transport=Transport()) as client:
        task = asyncio.create_task(client.upload('https://example.test/', source(), multipart=False))
        try:
            await asyncio.wait_for(first_received.wait(), timeout=5)
            assert produced == [b'first']
            assert not source_closed.is_set()
            resume.set()
            response = await asyncio.wait_for(task, timeout=5)
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
    assert response.json() == {'received': 'firstsecond'}
    assert source_closed.is_set()


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['transport', 'cancellation'])
async def test_interrupted_upload_leaves_async_source_owned_by_caller(failure):
    first_received = asyncio.Event()
    source = _body(b'first', b'second')

    class Transport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            assert await anext(request.stream.__aiter__()) == b'first'
            first_received.set()
            if failure == 'transport':
                raise httpx.WriteError('upload interrupted')
            await asyncio.Future()

    async with HttpClient(transport=Transport()) as client:
        task = asyncio.create_task(client.upload('https://example.test/', source, multipart=False))
        try:
            await asyncio.wait_for(first_received.wait(), timeout=5)
            if failure == 'cancellation':
                task.cancel()
            expected = asyncio.CancelledError if failure == 'cancellation' else httpx.WriteError
            with pytest.raises(expected):
                await asyncio.wait_for(task, timeout=5)
            # The library must not close or eagerly consume a caller-owned iterator.
            assert await anext(source) == b'second'
        finally:
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            await source.aclose()


@pytest.mark.asyncio
async def test_sse_handles_framing_utf8_and_persistent_metadata():
    payload = (
        '\ufeff: comment\r\n'
        'id: 7\r\nretry: 1500\r\n\r\n'
        'event: update\r\ndata: first\r\ndata: café\r\n\r\n'
        'id: bad\x00id\nretry: +2000\nevent:\ndata\n\n'
        'retry: １２３\ndata:  leading space\n\n'
        'id\nretry: 0\ndata: last\nunknown: ignored\n\n'
        'data: preserved\vseparator\u2028text\r\r'
        'data: incomplete'
    ).encode('utf-8')
    # Byte-sized chunks split CRLF, the BOM, and a multibyte UTF-8 character.
    source = _ResponseStream(_body(*(payload[index:index + 1] for index in range(len(payload)))))
    async with HttpClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={'content-type': 'text/event-stream; charset=iso-8859-1'}, stream=source
            )
        )
    ) as client:
        async with client.events('https://example.test/') as events:
            actual = [event async for event in events]
    assert actual == [
        SseEvent(event='update', data='first\ncafé', id='7', retry=1.5),
        SseEvent(event='message', data='', id='7', retry=1.5),
        SseEvent(event='message', data=' leading space', id='7', retry=1.5),
        SseEvent(event='message', data='last', id='', retry=0.0),
        SseEvent(event='message', data='preserved\vseparator\u2028text', id='', retry=0.0),
    ]
    assert source.closed


@pytest.mark.asyncio
async def test_sse_context_closes_after_early_exit():
    source = _ResponseStream(_body(b'data: first\n\n', b'data: second\n\n'))
    async with HttpClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, headers={'content-type': 'text/event-stream'}, stream=source
            )
        )
    ) as client:
        async with client.events('https://example.test/') as events:
            assert (await anext(events)).data == 'first'
            assert not source.closed
        assert source.closed


@pytest.mark.asyncio
async def test_sse_rejects_non_event_content_and_closes_response():
    source = _ResponseStream(_body(b'data: not actually an event stream\n\n'))
    async with HttpClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, headers={'content-type': 'text/plain'}, stream=source)
        )
    ) as client:
        with pytest.raises(ValueError):
            async with client.events('https://example.test/') as events:
                await anext(events)
    assert source.closed


@pytest.mark.asyncio
async def test_websocket_exposes_native_connection_and_closes_on_context_exit():
    disconnected = asyncio.Event()

    async def echo(connection):
        assert connection.request.headers['X-Test'] == 'modern'
        await connection.send(await connection.recv())
        await connection.send('next message')
        await connection.wait_closed()
        disconnected.set()

    async with serve(echo, '127.0.0.1', 0) as server:
        port = server.sockets[0].getsockname()[1]
        async with websocket(
            f'ws://127.0.0.1:{port}', additional_headers={'X-Test': 'modern'}
        ) as connection:
            await connection.send(b'binary payload')
            assert await connection.recv() == b'binary payload'
            async for message in connection:
                assert message == 'next message'
                break
        await asyncio.wait_for(disconnected.wait(), timeout=5)


@pytest.mark.asyncio
async def test_download_cancellation_during_open_joins_and_closes_file(tmp_path, monkeypatch):
    started = asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    opened = []
    original_open = aiofiles.threadpool.sync_open

    def slow_open(*args, **kwargs):
        loop.call_soon_threadsafe(started.set)
        if not release.wait(timeout=5):
            raise TimeoutError('Test failed to release file open')
        file = original_open(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(aiofiles.threadpool, 'sync_open', slow_open)
    destination = tmp_path / 'download.bin'
    destination.write_bytes(b'previous')
    async with HttpClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'new'))
    ) as client:
        task = asyncio.create_task(
            client.download('https://example.test/', destination, overwrite=True)
        )
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        finally:
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
    assert opened[0].closed
    assert destination.read_bytes() == b'previous'
    assert set(tmp_path.iterdir()) == {destination}
