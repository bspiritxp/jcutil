# 入门：注册并使用一个驱动

这一页演示本库最常见的服务端使用方式：使用标签注册资源，再通过标签取得它。示例使用 SQLite 内存库，因此不需要部署数据库服务。

## 前提

```bash
pip install jcutil sqlalchemy
```

## 1. 注册连接

`drivers.db` 维护进程内的引擎注册表。标签是调用方定义的稳定名称；不要在业务代码中散落连接 URL。

```python
from sqlalchemy import create_engine

from jcutil.drivers import db

engine = db.new_client('demo', create_engine=create_engine, url='sqlite:///:memory:')
assert db.instances() == ['demo']
```

`new_client()` 的第一个参数始终是标签。直接传入 `create_engine` 时，剩余参数会交给该函数；此写法避免依赖 `db.init_engine()` 的 Oracle 风格默认参数。

## 2. 取得并使用资源

```python
from sqlalchemy import text

with db.connect('demo') as connection:
    connection.execute(text('CREATE TABLE greeting (message TEXT)'))
    connection.execute(text("INSERT INTO greeting VALUES ('hello jcutil')"))
    row = connection.execute(text('SELECT message FROM greeting')).one()

assert row.message == 'hello jcutil'
```

`db.connect(tag)` 返回引擎的 `connect()` 结果。它没有隐式提交事务；实际应用应遵循所使用 SQLAlchemy 引擎与事务 API 的规则。

## 3. 关闭注册表资源

```python
db.close_engine('demo')
assert db.instances() == []
```

长生命周期进程通常在应用退出时关闭引擎。测试或一次性脚本必须主动清理，避免同一解释器中的后续调用使用旧注册项。

## 下一步

- 用 YAML 一次注册多类资源：[标签化驱动](guides/drivers.md)。
- 处理 MongoDB 的同步与异步集合：[标签化驱动](guides/drivers.md#mongodb)。
- 查询完整签名：[驱动 API 参考](reference/drivers.md)。
