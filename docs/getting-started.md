# 入门：注册同步和异步数据库

`jcutil.drivers.db` 是 SQLAlchemy 2.x 的标签化引擎注册表。它只管理引擎的注册与释放；连接、事务和 SQL 仍由调用方显式拥有。

## 前提

jcutil 3.0 要求 Python 3.12+。安装 SQLAlchemy 的 asyncio extra；异步 SQLite 示例还需要 `aiosqlite`：

```bash
pip install 'sqlalchemy[asyncio]' aiosqlite
```

## 同步引擎

```python
from sqlalchemy import text

from jcutil.drivers import db

# 应用启动时注册。
db.register_sync('app', 'sqlite:///:memory:')

# 每个调用点显式管理连接与事务。
with db.connect('app') as connection:
    connection.execute(text('CREATE TABLE greeting (message TEXT)'))
    connection.execute(text("INSERT INTO greeting VALUES ('hello jcutil')"))
    assert connection.scalar(text('SELECT message FROM greeting')) == 'hello jcutil'

# 应用停止时释放连接池。
db.dispose_sync('app')
```

## 异步引擎

异步 URL 必须选择 SQLAlchemy 支持的异步 driver，例如 `sqlite+aiosqlite` 或 `postgresql+asyncpg`。

```python
from sqlalchemy import text

from jcutil.drivers import db


db.register_async('analytics', 'sqlite+aiosqlite:///:memory:')

async with db.async_connect('analytics') as connection:
    await connection.execute(text('SELECT 1'))

await db.dispose_async('analytics')
```

同步标签调用 `async_connect()`（或异步标签调用 `connect()`）会抛出 `TypeError`。标签不存在会抛出 `KeyError`；不再接受按注册顺序取第一个引擎的隐式行为。

## 旧同步函数的兼容层

为帮助既有调用方迁移，旧同步函数继续存在，但全部委托给 v3 注册表：

| 旧函数 | v3 等价调用 |
| --- | --- |
| `init_engine(tag, url, **options)` | `register_sync(tag, url, **options)` |
| `new_client(tag, url, **options)` | `register_sync(tag, url, **options)` |
| `get_client(tag)` | `get_sync_engine(tag)` |
| `conn(tag)` | `connect(tag)` |
| `close_engine(tag)` | `dispose_sync(tag)` |
| `close_all_engines()` | 对每个同步标签调用 `dispose_sync()` |

兼容函数仍接受旧的整数注册表索引（例如 `get_client(0)`），但新代码必须使用明确的字符串标签。它们只处理**同步**引擎；异步调用统一使用 `register_async()`、`async_connect()` 与 `dispose_async()`。

## 配置加载

`smart_load()` 仍会调用 `db.load()`，但 db 配置现在要求每个标签显式指定 `url` 和 `mode`：

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

除 `url` 与 `mode` 外的字段会直接传给 SQLAlchemy 的对应引擎构造函数。完整签名见[驱动 API 参考](reference/drivers.md)。
