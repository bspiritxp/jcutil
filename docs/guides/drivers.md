# 标签化驱动

`jcutil.drivers` 以进程内注册表保存命名客户端。配置键必须匹配驱动模块名：`db`、`mongo`、`redis`、`mq`。`smart_load(conf)` 逐键导入 `jcutil.drivers.<key>` 并调用该模块的 `load()`。

```python
from jcutil.drivers import smart_load

smart_load({
    'mongo': {'app': 'mongodb://localhost:27017/app'},
    'redis': {'cache': 'redis://localhost:6379/0'},
})
```

标签只在当前 Python 进程有效。应用启动时加载并检查资源；应用关闭时由相应模块释放需要关闭的资源。

## 返回/缺失语义

| 驱动 | 取得客户端 | 未找到标签 |
| --- | --- | --- |
| `db` | `db.get_sync_engine()` / `db.get_async_engine()` | `KeyError` |
| `mongo` | `mongo.get_client()` / `mongo.get_collection()` | `KeyError` |
| `redis` | `redis.connect()` | `None` |
| `mq` | `mq.send()` | `AssertionError` |

不要写一个假定这些行为相同的通用访问层。

## SQLAlchemy 2.x

从 jcutil 3.0 开始，DB 配置显式区分同步与异步引擎，且不再从 URL 文本猜测模式：

```yaml
db:
  app:
    url: postgresql+psycopg://user:password@db.example/app
    mode: sync
    pool_pre_ping: true
  analytics:
    url: postgresql+asyncpg://user:password@db.example/analytics
    mode: async
    pool_pre_ping: true
```

`db.load()` 会把每个标签的 `url` 和 `mode` 取出，并将其他选项原样交给 SQLAlchemy。无效配置、重复标签和创建失败都会立即抛出异常；不会记录 warning 后继续运行。同步使用 `db.connect(tag)`，异步使用 `async with db.async_connect(tag)`。既有同步调用方可暂时使用[数据库入门](../getting-started.md)中的旧函数兼容层，但新代码应直接调用 v3 API。

## MongoDB

一个 `mongo.MongoClient` 同时持有 PyMongo 同步客户端和 Motor 异步客户端。URI 需要含默认数据库名，才能让无 `db_name` 的调用可靠工作。

```python
from jcutil.drivers import mongo

mongo.new_client('mongodb://localhost:27017/app', 'app')
users = mongo.get_collection('app', 'users')
saved = mongo.save(users, {'name': 'Ada'})
assert saved['_id']
```

`save()` 插入时添加 `createTime`、`updateTime` 和 `__v`；带 `_id` 的数据会以 `$set` 更新并增加版本。`find_page()` 默认按 `createdTime` 倒序，并向传入的查询字典加入 `logicDeleted: False`；如果调用方还要使用原查询，请先复制。

异步集合来自 `mongo.get_client('app').get_async_collection('users')`，随后使用 Motor 的 `await collection.find_one(...)` 等 API。

## Redis

`redis.new_client(uri, tag)` 是协程；`redis.load(conf)` 会在当前运行循环中创建 task。`redis.connect(tag)` 仅返回已注册客户端，不会等待连接就绪。

```python
from jcutil.drivers import redis

await redis.new_client('redis://localhost:6379/0', 'cache')
client = redis.connect('cache')
assert client is not None
await client.set('answer', '42')
assert await client.get('answer') == b'42'
```

以 `cluster://` 开头的 URI 使用 `RedisCluster`；其他 URI 使用 `Redis.from_url`。`Lock`、`SpinLock` 和 `interval_lock()` 建立在异步 Redis 客户端上，参见 API 参考。

## Kafka

`mq` 使用 `kafka-python`。先注册 bootstrap server 字符串，再发送或订阅：

```python
from jcutil.drivers import mq

mq.new_client('events', 'broker-1.example:9092', 'broker-2.example:9092')
future = mq.send('events', 'user-created', {'id': 1})
future.get(timeout=10)
```

`send()` 将字符串原样 UTF-8 编码，其他可 JSON 序列化对象用 JSON 编码。`subscribe()` 是协程并包装同步消费者；其回调可为同步或协程函数。Kafka 服务不可达时异常由 kafka-python 或返回的 future 报告。

完整函数和类签名见[驱动 API 参考](../reference/drivers.md)。
