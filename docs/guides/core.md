# 核心、JSON 与并发

`jcutil.core` 集中放置无需服务端的 JSON、编码、事件循环和并发辅助函数。它不是包根 API；请直接从 `jcutil.core` 导入。

## JSON 编解码

`to_json` 使用 `SafeJsonEncoder`，`to_obj` 使用 `SafeJsonDecoder`。编码器支持 `UUID`、`datetime`、`date`、`bytes` 与已安装 pandas 的常见值；未知类型会抛出 `TypeError`，不会静默转为字符串。

```python
from datetime import datetime
from uuid import uuid4

from jcutil.core import to_json, to_obj

raw = to_json({'request_id': uuid4(), 'created_at': datetime(2026, 9, 15, 8, 30)})
assert 'request_id' in raw
assert to_obj(raw)['created_at'] == '2026-09-15 08:30:00'
```

`to_json_file(obj, fp)` 接受路径或已经打开、具有 `write()` 的文本流。`from_json_file(path)` 从文件读取。`fix_document()` 是 decoder 的对象钩子：它移除以 `$` 开头的键的前缀（若该键是唯一键，则解包其值），并将字符串 `nan`、`nat`、`null` 转为 `None`。它不会转换 snake_case 键。

!!! note
    `jcutil.drivers.mongo.to_json` 是 BSON JSON 工具，不等同于这里的 `to_json`。包含 `ObjectId` 的 Mongo 文档请使用 Mongo 模块的函数。

## 在线程池运行阻塞函数

在协程中调用阻塞 I/O 或 CPU 工作时使用 `async_run()`：

```python
import time

from jcutil.core import async_run


def blocking_lookup(value):
    time.sleep(0.01)
    return value * 2


async def main():
    assert await async_run(blocking_lookup, 21) == 42
```

`with_context=True` 会复制当前 `contextvars` 上下文到线程。函数会取得或创建事件循环；它不关闭事件循环。

## 同步批量并发

`map_async(func, data, limit=None)` 是**同步函数**。它内部调用 `run_until_complete()`，因此只能从没有正在运行事件循环的同步入口调用。

```python
from jcutil.core import map_async

assert sorted(map_async(lambda value: value * 2, [1, 2, 3])) == [2, 4, 6]
```

在 `async def`、Notebook 或 Web 框架请求处理器中不要调用它；改为自行创建 asyncio task，或将整体同步工作交给 `async_run()`。

## 对象序列化与导入

- `obj_dumps(obj)` 返回 base64 编码的 pickle bytes；`obj_loads(raw)` 反序列化它。两者只适用于可信数据。
- `load_fc('module:function')` 动态导入并取得属性；不存在的属性返回 `None`，缺少模块仍会抛出导入错误。
- `host_mac()` 返回主机 MAC 地址的无前缀大写十六进制文本；`utcnow()` 返回带 UTC tzinfo 的 `datetime`。

完整函数列表在[核心与终端 API](../reference/core-and-chalk.md)。
