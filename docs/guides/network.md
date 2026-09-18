# HTTP、SSE 与 WebSocket

`jcutil.netio` 只提供异步 API，公开导出为 `HttpClient`、`SseEvent` 和 `websocket`。围绕应用任务选择方法：

| 任务 | 调用 | 结果 |
| --- | --- | --- |
| 获取 JSON | `await client.json(url, ...)` | 解码后的 Python 值，类型为 `Any` |
| 获取状态、响应头、文本或小型二进制响应 | `await client.request(method, url, ...)` | 已缓冲响应体的 `httpx.Response` |
| 分块处理响应 | `async with client.stream(url, ...) as response` | 流式 `httpx.Response` |
| 下载到磁盘 | `await client.download(url, destination, ...)` | 目标 `pathlib.Path` |
| 上传路径、字节或异步字节流 | `await client.upload(url, source, ...)` | 已检查状态的 `httpx.Response`，不自动解码 JSON |
| 读取 SSE | `async with client.events(url, ...) as events` | `AsyncIterator[SseEvent]` |
| 双向 WebSocket 消息 | `async with websocket(url, ...) as socket` | 原生 `websockets.asyncio.client.ClientConnection` |

以下示例放在异步函数或支持顶层 `await` 的环境中运行。HTTP 方法的请求选项（如 `params`、`headers`、`timeout`）传给 HTTPX；连接池选项在构造 `HttpClient` 时设置。库不提供同步入口，也不自动重试、断点续传或重连。

## 管理连接池生命周期

在应用生命周期内复用客户端，不要为每个请求新建连接池。没有注入客户端时，`HttpClient` 拥有连接池，必须先进入 `async with` 才能请求；退出时关闭连接池：

```python
from jcutil.netio import HttpClient

async with HttpClient(base_url='https://api.example', timeout=10) as client:
    profile = await client.json('/users/42')
    health = await client.json('/health')
```

框架已经管理 HTTPX 连接池时，可以注入 `httpx.AsyncClient`。该包装器立即可用，无须先进入上下文；也可以使用 `async with`。退出上下文或调用 `await client.aclose()` 只关闭包装器，不关闭借用的连接池：

```python
import httpx

from jcutil.netio import HttpClient

async with httpx.AsyncClient(base_url='https://api.example') as pool:
    client = HttpClient(pool)
    try:
        health = await client.json('/health')
    finally:
        await client.aclose()

    # 包装器已经关闭，外部连接池仍归调用方管理。
    response = await pool.get('/health')
```

不要同时传入已有客户端和新连接池的构造选项。无论连接池来自何处，关闭后的 `HttpClient` 都不能继续请求或重新进入上下文；需要新生命周期时创建新包装器。已注入连接池本身的关闭仍由其所有者负责。

## JSON、文本、响应头和空响应

`json(url, *, method='GET', **options)` 用于**响应确定为 JSON** 的请求。发送 JSON 请求体时使用 `json=` 请求选项，而不是位置参数：

```python
from jcutil.netio import HttpClient

async with HttpClient(base_url='https://api.example') as client:
    profile = await client.json('/users/42', params={'include': 'teams'})
    created = await client.json(
        '/events', method='POST', json={'type': 'login'}
    )
    updated = await client.json(
        '/users/42', method='PUT', json={'display_name': 'Jochen'}
    )
```

需要响应元数据、文本、字节或 `204 No Content` 时使用 `request(method, url, **options)`。它缓冲响应体，但不解析 JSON：

```python
from jcutil.netio import HttpClient

async with HttpClient(base_url='https://api.example') as client:
    response = await client.request('GET', '/status.txt')
    print(response.status_code, response.headers.get('content-type'))
    print(response.text)

    deleted = await client.request('DELETE', '/events/42')
    if deleted.status_code == 204:
        print('删除成功，无响应正文')
    else:
        print(deleted.text)
```

HTTP 响应会先经过 `raise_for_status()`：非 2xx 状态抛出 `httpx.HTTPStatusError`，不会转成 `None` 或 `False`。HTTPX 的连接、超时等异常原样传播。`json()` 额外执行响应 JSON 解码，因此空正文、HTML 或无效 JSON 会抛出解码异常；不能用它代替任意成功响应的处理。重定向是否跟随由 HTTPX 配置决定，未跟随的 3xx 同样不能当作成功结果。

## 流式处理与安全发布下载文件

### 自己消费响应流

`stream(url, *, method='GET', **options)` 必须通过异步上下文管理器使用。进入时检查 HTTP 状态，退出时关闭响应，即使中途 `break`、抛出异常或任务被取消也会执行关闭流程：

```python
from jcutil.netio import HttpClient

async with HttpClient() as client:
    async with client.stream('https://example.test/large.log') as response:
        print(response.headers.get('content-type'))
        async for line in response.aiter_lines():
            print(line)
            if line == 'END':
                break
```

二进制流可改用 `response.aiter_bytes(chunk_size=1024 * 1024)`。不要为大文件调用 `request()`、`response.aread()`，或收集全部分块再拼接。流式响应在读取前没有完整的 `.content` 或 `.text`；也不要在上下文之外继续消费它。

### 直接下载到磁盘

`download(url, destination, *, overwrite=False, chunk_size=1024 * 1024, **options)` 流式执行 GET，并返回目标 `Path`，而不是内存中的 `BytesIO`：

```python
from pathlib import Path

from jcutil.netio import HttpClient

async with HttpClient(timeout=60) as client:
    saved = await client.download(
        'https://example.test/archive.tar',
        Path('downloads/archive.tar'),
        chunk_size=1024 * 1024,
    )
    print(saved)
```

下载先写入目标旁的临时文件，传输成功并关闭文件后才原子发布到目标路径。缺失的父目录会创建；文件读写及目录、文件发布等阻塞文件系统操作使用异步接口或卸载到线程执行，不在事件循环中直接执行大文件同步 I/O。

- 默认 `overwrite=False`：目标存在时抛出 `FileExistsError`，发布阶段也不会覆盖并发创建的目标。
- 显式 `overwrite=True`：下载成功后才原子替换原有文件，不会先截断它。
- 发布前发生 HTTP 错误、传输错误或取消：清理临时文件，已有目标保持不变；下载不会以目标名称暴露半个文件。
- `chunk_size` 必须为正整数，默认 1 MiB；这控制分块大小，不代表文件大小上限。

默认禁止覆盖的发布通过同目录硬链接保证竞争安全，要求文件系统支持硬链接；不支持时传播文件系统错误，不降级为存在覆盖竞态的检查后写入。原子发布不是断点续传，也没有 `fsync` 掉电持久性保证。取消若恰好发生在最终原子发布期间，目标可能已经是完整下载的新文件，但不会是半个文件；库不会回滚已经完成的发布。创建的父目录也不属于下载失败后的回滚范围。

## 统一上传：路径、字节、异步流

`upload()` 接受 `str | Path | bytes | AsyncIterable[bytes]`，其中字符串始终表示**本地路径**，不是待发送文本。默认是 `method='POST'`、`multipart=True`、`field_name='file'`、`content_type='application/octet-stream'`，`chunk_size` 默认为 1 MiB 且必须为正整数。

返回值是经过状态检查的 `httpx.Response`，响应体已缓冲，但**不要求服务端返回 JSON**。这适用于纯文本和 204 响应；只有确定服务端契约为 JSON 时才调用 `response.json()`。

### 路径上传与表单字段

文件按块异步读取，不将整个文件载入内存。multipart 文件名默认取路径的 basename；`filename=` 可覆盖它。`data` 是附加文本字段，类型为 `Mapping[str, str]`：

```python
from pathlib import Path

from jcutil.netio import HttpClient

async with HttpClient(base_url='https://api.example', timeout=60) as client:
    response = await client.upload(
        '/files',
        Path('exports/large.csv'),
        field_name='attachment',
        content_type='text/csv',
        data={'scope': 'reports', 'year': '2026'},
    )
    print(response.status_code, response.headers.get('location'))
```

### 已有字节与异步字节流

对于 multipart 字节或异步字节流，必须显式提供 `filename`；每个异步流分块必须为 `bytes`。字节适合已经在内存中的小内容，异步流适合边生成边发送：

```python
from collections.abc import AsyncIterator

from jcutil.netio import HttpClient


async def rows() -> AsyncIterator[bytes]:
    yield b'number,value\n'
    for number in range(100_000):
        yield f'{number},{number * 2}\n'.encode('utf-8')


async with HttpClient(base_url='https://api.example', timeout=60) as client:
    small = await client.upload(
        '/files', b'hello\n', filename='greeting.txt', content_type='text/plain'
    )
    print(small.status_code)

    generated = await client.upload(
        '/files', rows(), filename='rows.csv', content_type='text/csv'
    )
    print(generated.status_code)
```

### 原始请求体 PUT

`multipart=False` 将源字节直接用作请求体，不添加 multipart 边界；`content_type` 设置请求的 `Content-Type`。路径仍然按块读取。此模式不接受 `filename`、附加表单 `data` 或自定义表单字段名：

```python
from pathlib import Path

from jcutil.netio import HttpClient

async with HttpClient(timeout=60) as client:
    response = await client.upload(
        'https://storage.example/objects/archive.tar',
        Path('exports/archive.tar'),
        method='PUT',
        multipart=False,
        content_type='application/octet-stream',
    )
    print(response.status_code)
```

上传过程中由库打开的文件会在完成、失败或取消时关闭；调用方传入的异步可迭代对象不会由库关闭，其资源生命周期仍由调用方管理。上传流没有预先完整缓冲或重放能力，尤其异步生成器应视为一次性数据源。

上传的媒体类型和传输分帧由库管理，不接受调用方显式设置 `Content-Type`、`Content-Length` 或 `Transfer-Encoding` 请求头；连接池默认请求头中也不能预设 `Content-Length` 或 `Transfer-Encoding`。请使用 `content_type` 参数，multipart 时它描述文件部分的类型。

`bytes` 和普通文件会自动提供准确的 `Content-Length`，包含 multipart 元数据长度；只读取文件大小，不提前读取文件内容。上传期间不要修改源文件。长度未知的异步流或特殊文件在 HTTP/1.1 下使用 chunked transfer encoding，服务端和代理必须支持；要求预先给出完整长度的接口应使用普通文件或 bytes。库不会为了计算长度而把大文件或异步流全部读取进内存，也不会自动重试已消费的请求体。取消本地上传不能保证服务端尚未保存部分数据或完成业务操作。

## Server-Sent Events

`client.events(url, **options)` 是**异步上下文管理器**，不是直接迭代的方法。它以 GET 打开流、检查 HTTP 状态，并要求响应的媒体类型为 `text/event-stream`。在上下文内迭代事件，提前退出时上下文负责关闭 HTTP 响应：

```python
from jcutil.netio import HttpClient

async with HttpClient(headers={'Authorization': 'Bearer token'}) as client:
    async with client.events('https://example.test/events', timeout=None) as events:
        async for event in events:
            print(event.event, event.id, event.data, event.retry)
            if event.event == 'done':
                break
```

`timeout=None` 在这里是调用方显式选择等待长期连接，不是默认值；生产环境应根据心跳和故障检测需要配置超时。

每个结果是不可变的 `SseEvent(event: str, data: str, id: str | None, retry: float | None)`：

- 数据按 UTF-8 解码，处理流起始处的 BOM。
- 同一事件的多条 `data:` 用换行拼接；注释忽略，无冒号的字段视为空值。
- 默认事件类型为 `message`，空 `event:` 也恢复为 `message`。
- `id` 跨事件保留；包含 NUL 的 `id` 被忽略，空 `id:` 将其设为空字符串。
- `retry` 跨事件保留；仅接受 ASCII 数字表示的毫秒值，转换为秒数输出，无效字段被忽略。它只是事件元数据，不会触发库内重连。
- 只有遇到空行结束、且存在 `data` 字段的事件才发出；流在未完成的事件中结束时，不会补发 EOF 事件。

错误状态、非 SSE 响应、传输错误和取消不会被转换为普通事件。库不自动解析 `event.data` 为 JSON、不重连，也不保存跨连接的 last-event-id。应用如果需要这些行为，必须自己决定重连、重复事件去重和请求头策略。

## 原生 WebSocket

`websocket(url, **connect_options)` 管理连接生命周期，返回原生 `ClientConnection`，不另造消息包装层。握手请求头使用 `additional_headers`，不是旧的 `extra_headers`：

```python
import json

from jcutil.netio import websocket

async with websocket(
    'wss://example.test/socket',
    additional_headers={'Authorization': 'Bearer token'},
) as socket:
    await socket.send(json.dumps({'op': 'ping'}))
    reply = await socket.recv()  # str 或 bytes，按对端消息类型返回
    print(reply)
```

持续读取使用原生异步迭代；发送 `str` 是文本消息，发送 `bytes` 是二进制消息。JSON 编码和解码由应用显式完成：

```python
from jcutil.netio import websocket

async with websocket('wss://example.test/socket') as socket:
    async for message in socket:
        print(message)
        if message == 'done':
            break
```

退出上下文会关闭连接，包括提前结束循环、异常和取消。握手、网络、协议和异常关闭等错误遵循 `websockets` 的原生语义；正常关闭时异步迭代结束。库不自动重连或重发消息，也没有同步版本或回调注册接口。

## 信任边界与异常处理

这些工具负责传输和资源生命周期，不负责业务安全策略：

- URL、请求头、代理和认证信息由调用方决定。不要把不可信 URL 直接交给能访问内网的客户端；按应用需求防范 SSRF，并检查重定向目的地。
- 下载目标路径和上传源路径都是调用方授权的本地路径。原子发布不会把任意路径变成安全路径，也不构成抵御恶意目录或符号链接的沙箱。
- multipart 的字段名、文件名经过 disposition 参数转义，`content_type` 会验证以避免头部换行注入；这不代表文件内容安全，也不代替服务端文件名、类型、大小和权限校验。
- 分块避免大文件整体驻留内存，但不设置总下载大小、总上传大小或 SSE 事件大小上限；需要限制时由应用制定策略。不要把收到的内容默认视为可信 HTML、JSON 或可执行文件。
- HTTP 状态异常、传输异常、文件系统异常和取消向调用方传播。上下文负责清理资源，不把错误伪装为成功；重试涉及幂等性、一次性请求体和服务端副作用，应由业务决定。

## 从旧 API 迁移

旧入口已删除，不提供兼容别名：

| 旧调用或行为 | 新调用或处理方式 |
| --- | --- |
| `client.get_json(url, ...)` | `await client.json(url, ...)` |
| `client.post_json(url, body, ...)` | `await client.json(url, method='POST', json=body, ...)` |
| `client.put_json(url, body, ...)` | `await client.json(url, method='PUT', json=body, ...)` |
| `client.delete_json(url, ...)` | JSON 响应用 `await client.json(url, method='DELETE', ...)`；204 用 `await client.request('DELETE', url, ...)` |
| `client.request_json(method, url, ...)` | `await client.json(url, method=method, ...)` |
| `client.download(url)` 返回 `(BytesIO, content_type)` | 小响应使用 `await client.request('GET', url)` 的 `.content`、`.headers`；大响应使用 `stream()` 或磁盘下载 |
| `client.download_to_file(url, path, ...)` | `await client.download(url, path, ...)`；默认不覆盖，完成后原子发布 |
| `client.upload_file(url, path, ...)` | `await client.upload(url, path, ...)` |
| `client.upload_bytes(url, payload, filename, ...)` | `await client.upload(url, payload, filename=filename, ...)`；源为 `bytes`，不再接受 `BytesIO` |
| 上传后自动解码 JSON | 返回 `httpx.Response`；确认响应契约后才调用 `.json()` |
| `await client.close()` 或关闭后重新使用 | `await client.aclose()`；关闭后创建新包装器 |
| `client.client` 访问底层连接池 | 需要直接使用 HTTPX 时，自己持有并注入 `httpx.AsyncClient` |
| `async for event in EventSource(client, url).events()` | `async with client.events(url) as events:`，再在块内 `async for event in events` |
| `async with WebSocketClient(url) as socket` | `async with websocket(url) as socket` |
| `socket.send_text(text)` / `socket.send_bytes(data)` | `await socket.send(text)` / `await socket.send(data)` |
| `socket.send_json(value)` | `await socket.send(json.dumps(value))` |
| `socket.receive()` / `socket.messages()` | `await socket.recv()` / `async for message in socket` |
| WebSocket 包装器的 `connect()` / `connection` | 使用 `websocket()` 上下文，得到的对象本身就是原生连接 |

完整签名见[安全、缓存与网络 API](../reference/security-cache-network.md)。
