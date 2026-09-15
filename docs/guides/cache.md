# 缓存与持久化

`jcutil.data` 提供本地 joblib 缓存、Redis 结果缓存和“返回后异步写出”的持久化包装。它们缓存的是函数结果，而不是通用键值存储 API。

## 本地函数缓存

```python
from jcutil.data import clear_mem, mem_cache


@mem_cache('/tmp/jcutil-demo-cache')
def parse_report(source):
    print('runs once per argument set')
    return {'source': source}

assert parse_report('daily.csv') == parse_report('daily.csv')
clear_mem(cache_dir='/tmp/jcutil-demo-cache')
```

`mem_cache(cache_dir)` 返回 `joblib.Memory.cache` 装饰器。缓存目录不存在时会创建；`clear_mem()` 递归删除 `cache_dir/joblib/<path>`。请为应用配置专用的可写目录，不要清理共享路径。

## Redis 函数缓存

```python
from datetime import timedelta

from jcutil.data import redis_cache
from jcutil.drivers import redis


@redis_cache(expires=timedelta(minutes=5), prefix='catalog')
async def load_product(product_id):
    return {'id': product_id}

await redis.new_client('redis://localhost:6379/0', 'cache')
assert await load_product('p-1') == {'id': 'p-1'}
```

缓存 key 来自函数模块名、进程 ID 以及参数的 MD5，因此**不跨进程共享**。装饰器内部将结果 pickle 后写入 Redis，且不是线程安全的。只缓存可信对象；不要让不可信主体拥有同一 Redis keyspace 的写权限。

对同步函数的包装器使用 `asyncio.run()`。因此不要在已有事件循环的线程中调用被 `redis_cache` 装饰的同步函数；改用异步函数或直接使用 Redis 客户端。

传入 `update_cache=True` 可绕过读取并刷新结果。`result_assert(result)` 返回假值时会视缓存失效。

## 异步持久化返回值

`persistence(fs, f)` 返回 `f` 的包装函数：`f` 返回非 `None` 后，库将结果先写到临时 joblib 文件，再在线程池中传给 `fs.write(file_object)`，最后关闭文件对象。

```python
from jcutil.data import persistence


def compute():
    return {'status': 'done'}

# make_destination 必须每次返回一个已打开、可写入的二进制目标。
persisted_compute = persistence(make_destination, compute)
result = persisted_compute()
assert result == {'status': 'done'}
```

调用方不应读取或关闭传给 `fs.write()` 的临时文件；该函数拥有其生命周期。同步调用返回时后台写入可能尚未完成。

完整签名见[安全、缓存与网络 API](../reference/security-cache-network.md)。
