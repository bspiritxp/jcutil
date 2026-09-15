# 标签化驱动

`jcutil.drivers` 以进程内注册表保存命名客户端。配置键与驱动模块名必须一致：`db`、`mongo`、`redis`、`mq`。`smart_load(conf)` 逐键加载 `jcutil.drivers.<key>` 并调用其 `load()`。

```python
from jcutil.drivers import smart_load

smart_load({
    'mongo': {'app': 'mongodb://localhost:27017/app'},
    'redis': {'cache': 'redis://localhost:6379/0'},
})
```

未知键或加载模块失败会被记录为 debug；数据库单个引擎连接失败会记录 warning。调用 `smart_load()` 成功并不代表所有资源均可用，应用启动检查必须查询各自注册表或做健康检查。

## 返回/缺失语义

| 驱动 | 取得客户端 | 未找到标签 |
| --- | --- | --- |
| `db` | `db.get_client()` / `db.connect()` | `RuntimeError` |
| `mongo` | `mongo.get_client()` / `mongo.get_collection()` | `KeyError` |
| `redis` | `redis.connect()` | `None` |
| `mq` | `mq.send()` | `AssertionError` |

不要写一个假定这些行为相同的通用访问层。

## SQLAlchemy

`drivers.db` 在未安装 SQLAlchemy 时可以导入，但创建引擎会失败。`load()` 接受 `{tag: url}`；`new_client()` 可用 `url=` 或自定义的 `create_engine=` 注册。

```python
from sqlalchemy import text

from jcutil.drivers import db

# URL 必须由部署环境提供；示例不包含凭据。
db.load({'app': 'postgresql://user:password@db.example/app'})
with db.connect('app') as connection:
    result = connection.execute(text('SELECT 1'))

db.close_all_engines()
```

`connect()` 只适用于同步引擎。异步 SQLAlchemy 引擎应通过 `get_client()` 取得后，使用 SQLAlchemy 的异步连接 API。

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

异步集合来自 `mongo.get_client('app').get_async_collection('users')`，随后使用 Motor 的 `await collection.find_one(...)` 等 API。不要在一个已运行的事件循环中使用 Redis `load()` 的同步启动路径。

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
