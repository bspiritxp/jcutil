# HTTP、SSE 与 WebSocket

jcutil 3.0 的 `jcutil.netio` 使用显式生命周期：HTTP 连接池由 `HttpClient` 拥有或由调用方注入；SSE 与 WebSocket 不再隐式重连或注册回调。调用方拥有应用生命周期与重试策略。

## 复用 HTTP 连接池

将一个 `HttpClient` 放在应用的生命周期内，避免每次请求重新建立 TCP/TLS 连接：

```python
from jcutil.netio import HttpClient


async with HttpClient(base_url='https://api.example', timeout=5) as client:
    profile = await client.get_json('/users/42')
    created = await client.post_json('/events', {'type': 'login'})
```

`get_json`、`post_json`、`put_json`、`delete_json` 与通用的 `request_json()` 都在 HTTP 非 2xx 响应时抛出 `httpx.HTTPStatusError`。它们不会将失败转换为 `None` 或 `False`。

框架已管理 HTTPX 生命周期时，注入该客户端；jcutil 不会关闭它：

```python
import httpx

from jcutil.netio import HttpClient

external = httpx.AsyncClient(base_url='https://api.example')
try:
    async with HttpClient(external) as client:
        payload = await client.get_json('/health')
finally:
    await external.aclose()
```

## 文件下载和上传

```python
from jcutil.netio import HttpClient

async with HttpClient() as client:
    # 返回 Path；目标已存在时默认抛 FileExistsError。
    path = await client.download_to_file(
        'https://example.test/report.csv', 'downloads/report.csv', overwrite=True
    )
    uploaded = await client.upload_bytes(
        'https://example.test/files', b'hello', 'greeting.txt', data={'scope': 'demo'}
    )
```

`download()` 将内容放入内存并返回 `(BytesIO, content_type)`；`download_to_file()` 流式写入并返回目标 `Path`。`upload_file()` 使用上下文管理器打开文件，因此无论请求成功或失败，文件描述符都会关闭。

## Server-Sent Events

`EventSource` 以异步迭代器输出不可变的 `SseEvent(event, data, id, retry)`；它不重连。将重连和 last-event-id 策略放在应用层，避免库猜测业务语义。

```python
from jcutil.netio import EventSource, HttpClient

async with HttpClient(headers={'Authorization': 'Bearer token'}) as client:
    async for event in EventSource(client, 'https://example.test/events').events():
        print(event.event, event.id, event.data)
```

## WebSocket

`WebSocketClient` 使用 `websockets.asyncio` 的当前 API。请求头使用该库的 `additional_headers`，而不是已移除的 `extra_headers`。

```python
from jcutil.netio import WebSocketClient

async with WebSocketClient(
    'wss://example.test/socket', additional_headers={'Authorization': 'Bearer token'}
) as socket:
    await socket.send_json({'op': 'ping'})
    reply = await socket.receive()
```

需要持续读取时迭代 `socket.messages()`；连接关闭或网络错误由调用方捕获并决定是否重试：

```python
async for message in socket.messages():
    process(message)
```

完整签名见[安全、缓存与网络 API](../reference/security-cache-network.md)。
