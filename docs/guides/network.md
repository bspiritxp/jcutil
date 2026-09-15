# HTTP、SSE 与 WebSocket

`jcutil.netio` 是围绕 `httpx.AsyncClient`、`aiofiles` 和 `websockets` 的异步轻封装。每个函数都必须在协程中 `await`。

## JSON 请求

```python
from jcutil.netio import get_json, post_json

profile = await get_json('https://api.example/users/42', headers={'Authorization': 'Bearer token'})
created = await post_json('https://api.example/events', {'type': 'login'}, timeout=5)
```

`get_json`、`post_json`、`put_json`、`delete_json` 每次调用创建并关闭一个 `httpx.AsyncClient`。请求参数通过 `**kwargs` 传给 httpx；非 2xx 响应会由 `response.raise_for_status()` 抛出 `httpx.HTTPStatusError`。

## 下载和上传

```python
from pathlib import Path

from jcutil.netio import download, download_to_file, upload_bytes

stream, content_type = await download('https://example.test/report.csv')
if stream is not None:
    Path('report.csv').write_bytes(stream.getvalue())

saved = await download_to_file('https://example.test/report.csv', 'downloads/report.csv')
assert saved is True

response = await upload_bytes(
    'https://example.test/files', b'hello', 'greeting.txt', additional_data={'scope': 'demo'}
)
```

`download()` 在 HTTP 失败时返回 `(None, None)`；`download_to_file()` 在目标文件存在且未传 `overwrite=True` 时返回 `False`，HTTP 失败时也返回 `False`。它会创建父目录。`upload_file()` 对文件不存在抛出 `FileNotFoundError`，其他 HTTP 失败继续抛异常。

## SSE

使用 async context manager 保证连接关闭。`on(event_name, callback)` 为每个事件名注册一个回调；回调可同步也可异步，接收 `(data, last_event_id)`。

```python
from jcutil.netio import EventSourceClient


async def on_message(data, event_id):
    print(event_id, data)


async with EventSourceClient('https://example.test/events') as events:
    events.on('message', on_message)
    await events.connect()  # 持续运行，直到外部调用 close()
```

连接失败会等待 `reconnection_time` 后重连；服务器发送 SSE `retry:` 字段会更新该延迟。`connect()` 是长期循环，通常应作为 task 启动并由应用生命周期调用 `close()` 停止。

## WebSocket

```python
from jcutil.netio import WebSocketClient

async with WebSocketClient('wss://example.test/socket') as ws:
    ws.on('message', lambda payload, kind: print(kind, payload))
    await ws.send_json({'op': 'ping'})
    reply = await ws.receive()
```

支持 `message`、`connect`、`disconnect` 和 `error` 回调。`send_text()`、`send_json()`、`send_bytes()`、`receive()`、`listen()` 都要求已连接，否则抛 `ConnectionError`。`listen()` 会持续读取直至连接关闭，适合放在单独 task 中。

更多签名见[安全、缓存与网络 API](../reference/security-cache-network.md)。
