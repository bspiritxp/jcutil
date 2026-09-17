# 缓存与持久化

`jcutil.data` 提供函数结果缓存和可观察的后台持久化，不是通用数据库或 ETL 框架。四个入口 `mem_cache()`、`clear_mem()`、`redis_cache()`、`persistence()` 保留；安全修复涉及的迁移见文末。

## 本地函数缓存

```python
from jcutil.data import clear_mem, mem_cache

@mem_cache('/tmp/jcutil-demo-cache')
def parse_report(source):
    return {'source': source}

assert parse_report('daily.csv') == parse_report('daily.csv')
clear_mem(cache_dir='/tmp/jcutil-demo-cache')
```

`mem_cache()` 返回原生 `joblib.Memory.cache` 装饰器，支持嵌套目录创建。默认位置改为当前用户的 `~/.cache/jcutil`，不再使用共享 `/tmp/joblib`。Joblib 磁盘数据包含 pickle；缓存目录必须可信、不可被不可信用户写入。

`clear_mem(path='', cache_dir=None)` 只删除指定目录下的 `joblib/<path>`。支持原有点分路径；拒绝绝对路径、`..` 及清理路径上的符号链接。不存在的目录无需处理，权限和其他 I/O 错误正常抛出。验证不能防御对缓存目录具有并发写入权限的恶意主体，仍应使用受控目录。

## Redis 函数缓存

同步函数使用同步 Redis 客户端，`async def` 使用 asyncio 客户端；不再用 `asyncio.run()` 桥接同步调用。`redis_connector` 必须同步返回相应模式的原生客户端，不能返回协程。未提供 connector 时，使用相应注册表的默认客户端；未注册时抛出 `RuntimeError`。装饰器不关闭共享 Redis 客户端。

```python
from jcutil.data import redis_cache
from jcutil.drivers import redis

client = redis.new_sync_client('redis://localhost:6379/0', 'catalog')

@redis_cache(prefix='catalog', redis_connector=lambda: client, codec='json')
def load_product(product_id):
    return {'id': product_id}

try:
    assert load_product('p-1') == {'id': 'p-1'}
    load_product.invalidate('p-1')
    load_product('p-1', update_cache=True)
finally:
    redis.close_sync_client('catalog')
```

异步入口的用法保持一致：

```python
client = await redis.new_client('redis://localhost:6379/0', 'catalog-async')

@redis_cache(prefix='catalog', redis_connector=lambda: client, codec='json')
async def load_product_async(product_id):
    return {'id': product_id}

try:
    await load_product_async('p-1')
    await load_product_async.invalidate('p-1')
finally:
    await redis.aclose_async_client('catalog-async')
```

即使在已有事件循环中，同步装饰器也不会创建新循环；但同步 Redis 和业务函数仍阻塞当前线程，应在适当的同步路径使用。

### 键、身份与失效

- 新键使用 `jcutil:fc:v2:` 前缀，摘要包含 `prefix`、`namespace`、函数模块及 `__qualname__`、`version`、codec 和参数。**不包含 PID，可跨进程共享。**
- 参数通过函数签名绑定并填入默认值，等价的位置/关键字调用共用缓存；tuple/list、bool/int 等保持类型区分。字典和 `**kwargs` 的插入顺序保留，因为函数可能依赖该顺序。
- 支持基本标量、bytes、list/tuple、dict、set/frozenset、datetime/date/timedelta、Decimal、UUID 和 Enum。自定义对象、实例参数、循环引用应提供 `key_fn(*args, **kwargs)`，返回受支持的键值；不会静默退化为 `str()` 或 `repr()`。
- 闭包必须显式提供 `namespace` 或 `key_fn`。namespace 必须区分不同业务含义的闭包；结果相关的闭包、实例、租户、授权、数据库版本等外部状态由调用方纳入键。装饰器不能自动判断这些语义。
- `version='1'` 默认值可随业务代码、数据格式或外部状态版本改变。装饰器不自动哈希函数源码。
- `wrapped.cache_key(...)` 返回准确的键；`wrapped.invalidate(...)` 仅删除该参数对应项。异步装饰器的 invalidate 需要 await。没有扫描或批量删除其他业务 key。
- `update_cache=True` 绕过读取，重算并刷新；这是包装器保留参数，不能同时作为业务函数参数使用。

实例或闭包示例：

```python
class Catalog:
    def __init__(self, tenant):
        self.tenant = tenant

    @redis_cache(key_fn=lambda self, product_id: (self.tenant, product_id), codec='json')
    def get(self, product_id):
        return {'tenant': self.tenant, 'id': product_id}
```

### TTL、codec 与错误边界

`expires` 默认 30 秒，接受正数秒、正数 `timedelta` 或 `None`（不自动过期）。使用 Redis 毫秒 TTL，向上取整，不会把正的亚秒 TTL 截断成零；零、负数和无穷值拒绝。

默认 `codec='pickle'` 保留 Python 结果类型，使用 Base64 编码以兼容 bytes/文本 Redis 响应。**Base64 不是安全措施，pickle 反序列化可执行代码：只允许可信主体写入这些缓存键。** `codec='json'` 不使用 pickle，仅允许 JSON 原生类型；tuple、非字符串字典键、自定义对象及非有限浮点数被拒绝，不会静默改变返回类型。

默认不缓存 `None`；`cache_none=True` 可缓存负结果。显式刷新得到 `None` 且未开启负缓存时，旧项被删除。`result_assert(result)` 为同步校验函数，返回假值则回源；其异常不会被当作缓存损坏吞掉。

一次读取只执行 `GET`，没有 `EXISTS`/`GET` 竞态窗口。格式损坏（包括空 pickle）视作未命中并重算；网络错误、业务异常、编码错误正常传播。该工具不提供跨进程锁、single-flight、事务一致性或自动重试：并发未命中仍可能重复执行业务函数，失效与其他并发写入也没有顺序保证。

## 可观察的后台持久化

`persistence(fs, f, *, write_mode='bytes')` 返回可调用的 `Persistence` 对象，保留函数名称、文档及 `__wrapped__`。同步调用仍返回计算结果；包装 `async def` 时 await 调用后得到结果。非 `None` 结果先序列化为独立 joblib 快照，再交给单工作线程写出，调用方后续修改结果不会改变待写数据。

快照序列化在调用线程完成，不保证整个调用非阻塞；大快照会溢出到系统临时文件。目标 I/O 才在后台执行。每个包装器内部串行写入，不保证不同包装器或进程之间的写入顺序。

### 目标与资源所有权

- **路径（str/PathLike）**：目标父目录必须存在。写到同目录临时文件，flush/fsync 后通过 `os.replace()` 原子替换；失败不覆盖旧文件。新文件权限来自安全临时文件，不继承旧文件元数据。不承诺所有平台上的断电持久性或跨进程事务。
- **已打开的二进制流**：借用而非拥有，包装器不会关闭它；从当前流位置写入，不会自动 seek/truncate。不要与其他写入者并发使用。
- **工厂函数**：每次返回新的目标，由包装器写完后关闭；错误路径也尝试关闭，不以关闭错误替换原始写入错误。
- **旧文件对象上传接口**：显式使用 `write_mode='file'`，调用 `target.write(snapshot_file)`；该方法必须在返回前完成读取，不能保存临时文件供之后使用。默认 bytes 模式调用标准 `write(buffer) -> byte_count`，支持短写。

### 等待、错误与关闭

```python
from pathlib import Path
from jcutil.data import persistence

def compute():
    return {'status': 'done'}

with persistence(Path('/tmp/result.joblib'), compute) as save:
    result = save()       # 返回业务结果；写入可能仍在进行
    save.flush()          # 等待此前提交的写入，抛出保存失败
    done = save.submit() # 返回 concurrent.futures.Future
    assert done.result() == {'status': 'done'}  # 写入成功后才完成
```

`flush()` 等待并清理本批完成句柄，全部完成后抛出第一项失败。单次 `submit()` 返回的 Future 可分别检查各次结果；在 Future 上观察过错误不等于已从 flush 批次消费。长生命周期包装器应定期 flush，避免积累句柄与结果引用。调用 `close()` 或退出 with 时停止接收新调用、等待队列并传播错误。

异步调用使用 `aflush()`、`aclose()` 和 `async with`，避免在事件循环中等待工作线程：

```python
import asyncio

async def compute_async():
    return {'status': 'done'}

async with persistence('/tmp/async-result.joblib', compute_async) as save:
    result = await save()
    await save.aflush()
    completion = await save.submit()
    await asyncio.wrap_future(completion)
```

调用方必须管理关闭，不应依赖解释器退出或垃圾回收证明保存成功。目标创建、编码、写入、替换和关闭失败均可被调用方观察；没有后台失败静默成功的承诺。读取持久化 joblib 文件同样要求来源可信。

## 旧版迁移

1. 默认本地目录从共享 `/tmp` 改为 `~/.cache/jcutil`。不会读取、迁移或清理旧共享缓存；需要保留自定义位置时显式传 `cache_dir`。
2. Redis v2 键与旧键隔离，首次调用会重算。旧键按原 TTL 自然过期；无 TTL 的旧项由应用按其已知命名空间处理，不做全库扫描删除。不会尝试读取旧键，避免继承旧类型碰撞。
3. 同步函数改用 `new_sync_client()` / `get_sync_client()`，不能继续传 asyncio 客户端。异步函数保留原异步 Redis 使用方式。
4. pickle 默认值保留。改用 JSON 是显式、独立的缓存命名空间变化，需保证结果类型符合 JSON 契约。
5. 闭包补充业务 namespace/key_fn；外部状态或版本改变时显式失效。
6. 持久化常规二进制流默认传 bytes；依赖 `write(file_object)` 的上传接口增加 `write_mode='file'`。直接传入的流由调用方关闭；工厂创建的流由包装器关闭。新增 with/close 或 async with/aclose，确保错误可见。
7. `data.pyi` 同步更新，`clear_mem()` 正确返回 `None`，缓存装饰器暴露 key/失效方法，持久化对象暴露完成句柄与生命周期方法。

完整签名见[安全、缓存与网络 API](../reference/security-cache-network.md)。
