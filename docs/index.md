# jcutil 使用手册

`jcutil` 是一个面向 Python 服务端程序的实用工具库。包根只提供版本和作者信息；请从所需**子模块**导入功能，例如 `jcutil.core` 或 `jcutil.drivers.mongo`。

本手册以库当前的源码行为为准，覆盖控制台输出、JSON、并发、标签化驱动、缓存、密码学、网络 I/O、Consul 与任务调度。

## 选择功能

| 需求 | 模块 | 从这里开始 |
| --- | --- | --- |
| 彩色终端文本或交互菜单 | `jcutil.chalk` | [核心与终端 API](reference/core-and-chalk.md) |
| JSON、对象序列化、线程池辅助函数 | `jcutil.core` | [核心、JSON 与并发](guides/core.md) |
| SQLAlchemy、MongoDB、Redis、Kafka 的命名连接 | `jcutil.drivers` | [标签化驱动](guides/drivers.md) |
| 密码哈希、令牌、AES、RSA、摘要 | `jcutil.crypto_utils`、`jcutil.crypto` | [密码与密码学](guides/security.md) |
| 异步 HTTP、文件传输、SSE、WebSocket | `jcutil.netio` | [HTTP、SSE 与 WebSocket](guides/network.md) |
| 本地/Redis 缓存或异步写入文件 | `jcutil.data` | [缓存与持久化](guides/cache.md) |
| Consul KV、服务注册、分布式锁 | `jcutil.consul` | [Consul、服务端配置与调度](guides/integrations.md) |
| Mongo 持久化 APScheduler 任务 | `jcutil.schedjob` | [Consul、服务端配置与调度](guides/integrations.md) |
| 将字典拼为 SQL `WHERE` 片段 | `jcutil.dba.Where` | [设计与边界](explanation.md) |

## 安装

```bash
pip install jcutil
```

项目声明的基础依赖会随安装一并解析。下面两类环境仍有额外前置条件：

- `drivers.db` 只有检测到 SQLAlchemy 后才创建数据库引擎：`pip install sqlalchemy`。
- 默认的密码哈希方案是 Argon2；运行密码哈希前安装后端：`pip install argon2-cffi`。如选择 BCrypt，还需要 `bcrypt`。

MongoDB、Redis、Kafka、Consul 与 APScheduler 都是客户端封装；相应的服务端必须由应用自行提供。

## 最小可运行示例

下面的代码不依赖外部服务，验证安装、JSON 编解码和终端输出：

```python
from datetime import datetime, timezone

from jcutil.chalk import GreenChalk
from jcutil.core import to_json, to_obj

encoded = to_json({'created_at': datetime(2026, 9, 15, tzinfo=timezone.utc)})
print(GreenChalk(encoded))
assert to_obj(encoded)['created_at'] == '2026-09-15 00:00:00'
```

`SafeJsonEncoder` 将 `datetime` 格式化为 `%Y-%m-%d %H:%M:%S`；时区信息不会保留。映射键会按原样保留。更多限制见[核心、JSON 与并发](guides/core.md)。

!!! warning "先读边界"
    `obj_loads()`、`redis_cache()` 会反序列化 pickle 数据；只可处理可信来源。`dba.Where` 生成 SQL 字符串而不是参数化查询；绝不能将不可信输入传入。

## 文档约定

- **使用指南**回答“如何完成一项任务”，提供可复制的前提、代码与验证方式。
- **API 参考**由构建时从源码解析签名和 docstring，避免函数签名漂移；不在构建时 import 业务模块。
- **设计与边界**记录跨模块生命周期、异步边界与安全限制。

开发本手册：安装文档依赖后运行 `uv run --group docs mkdocs serve`。提交前运行 `uv run --group docs mkdocs build --strict`。
