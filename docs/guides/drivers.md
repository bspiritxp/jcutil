# 标签化驱动

`jcutil.drivers` 以进程内注册表保存命名客户端。配置键必须匹配现有驱动模块名：`db`、`mongo`、`redis`。`smart_load(conf)` 逐键导入 `jcutil.drivers.<key>` 并调用该模块的 `load()`。

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

`mongo.MongoClient` 同时公开 PyMongo 4.18 的同步 `MongoClient` 和原生 asyncio `AsyncMongoClient`；不再依赖已弃用的 Motor。同步客户端可跨线程使用；异步客户端按事件循环隔离，不能跨事件循环或线程共享。

```python
from jcutil.drivers import mongo

client = mongo.new_client('mongodb://localhost:27017/app', 'app')
users = mongo.get_collection('app', 'users')
saved = mongo.save(users, {'name': 'Ada'})
assert saved['_id']

client.create_index('users', [('name', 1)], unique=True)
assert 'name_1' in client.index_information('users')
```

`save()` 插入时添加 `createTime`、`updateTime` 和 `__v`；带 `_id` 的数据会以 `$set` 更新并增加版本。`find_page()` 默认按 `createdTime` 倒序，并向传入的查询字典加入 `logicDeleted: False`；如果调用方还要使用原查询，请先复制。

异步集合来自 `client.get_async_collection('users')`，并直接暴露 PyMongo 的最新异步集合 API，包括 `bulk_write()`、`create_search_index()`、`list_search_indexes()` 和 Atlas Vector Search 管理。包装器还提供同名 `async_create_index()`、`async_list_indexes()`、`async_drop_index()` 以及 Search/Vector Search 的 `async_*_search_index()` 方法。Search/Vector Search 管理由 Atlas 异步执行；用 `list_search_indexes()` 轮询状态。

异步资源应通过 `await client.async_close()` 关闭；`client.close()` 仅关闭同步 PyMongo 客户端。

`get_fs_bucket()` 和 `get_async_fs_bucket()` 返回同步/异步 GridFS bucket，均保留 `open_save_file()`、`save_file()` 的同名文件替换语义，同时公开 PyMongo 的下载、重命名和 `rename_by_name()` API。文件超过 BSON 的 16MB 限制时应使用 GridFS。

## Redis

`redis` 采用 redis-py 8.1+，同步与 asyncio 注册表相互独立。既有 `new_client()`、`get_client()`、`connect()` / `conn()` 保持为异步 API 的别名；显式 API 为 `new_async_client()` / `get_async_client()` 和 `new_sync_client()` / `get_sync_client()`。

```python
from jcutil.drivers import redis

# Existing asyncio API
client = await redis.new_client('redis://localhost:6379/0', 'cache')
await client.set('answer', '42')
assert await client.get('answer') == b'42'
await redis.aclose_async_client('cache')

# Synchronous API
client = redis.new_sync_client('redis://localhost:6379/0', 'cache')
assert client.set('answer', '42') is True
assert client.get('answer') == b'42'
redis.close_sync_client('cache')
```

返回的是原生 redis-py 客户端，直接支持 pipeline / transaction、Pub/Sub、Streams、Lua Functions 及其他当前 Redis 命令。异步 pipeline 使用 `async with`，仅 `execute()` 和命令读取需要 `await`；同步与异步客户端都应在应用关闭时调用相应 close API。

普通 URI 支持 redis-py 的 `redis://`、`rediss://` 与 `unix://`。原有 `cluster://` 前缀仍受支持，会转换为 redis-py 的 Cluster URI；集群 pipeline 支持 key 命令，事务中的所有 key 必须位于同一 hash slot。`redis.load(conf)` 仍加载异步客户端，`redis.load_sync(conf)` 用于同步客户端。`Lock`、`SpinLock` 和 `interval_lock()` 继续使用异步注册表。

## 迁移旧 `mq` 配置

`jcutil.drivers.mq` 已移除。仍然使用 Kafka 的应用必须直接拥有 Kafka 客户端、生产者/消费者配置、消息序列化协议、错误处理和生命周期管理；jcutil 不再提供替代 MQ 抽象。

不要把 Redis Streams 当作 `mq` 的语义等价替换。Redis Streams 与 Kafka 在持久化模型、消费组语义、保留策略、重放能力和运维边界上都不同；如果业务选择迁移，必须作为独立的消息系统设计与验证。

删除配置中的旧 `mq` 段。`smart_load(conf)` 对不存在的驱动模块只记录 debug 日志并继续运行，因此遗留 `mq` 配置可能被静默忽略，不能作为 Kafka 客户端已经初始化的信号。

完整函数和类签名见[驱动 API 参考](../reference/drivers.md)。
