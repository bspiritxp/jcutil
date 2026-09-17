# 设计与边界

## 标签是进程内状态，不是连接池服务

驱动模块各自维护模块级字典：配置或 `new_client()` 将资源放入字典，后续业务代码通过标签取回资源。这降低了配置向业务代码传播的成本，但标签只在当前 Python 进程有效。

```text
YAML / 环境配置
       │
       ▼
smart_load({driver: {tag: connection}})
       │
       ▼
各驱动的模块级注册表
       │
       ▼
db.connect(tag) / mongo.get_client(tag) / redis.connect(tag)
```

因此启动、测试和关闭路径都必须明确：加载后检查可用性；测试间关闭或隔离注册项；进程退出时释放引擎、连接和调度器。库没有统一的“所有驱动都已连接”状态。

## 异步边界必须由调用方拥有

网络、Redis、Motor、SSE、WebSocket 和 `SchedulerManager.start()` 是异步 API。`async_run()` 是从协程移交到线程池的桥；`map_async()` 则是同步入口内部运行事件循环的工具。不要交叉使用：在正在运行的 loop 内调用 `map_async()` 或被 Redis 缓存包装的同步函数，都会进入嵌套事件循环风险。

## 自动 API 文档不执行模块

文档构建通过 mkdocstrings 的源码解析生成参考页，不在构建期 import jcutil 模块。这项约束防止文档构建触发 `server.envars` 的 `.env` 加载、日志配置和本机 IP 探测，也避免全局 Consul 客户端成为构建条件。

自动提取只负责签名和 docstring。选择模块、外部前提、资源生命周期、返回/异常差异和安全限制由手写指南维护；两者缺一不可。

## 安全边界

- `Where` 的 HTML escaping 不是 SQL escaping，更不是参数化查询。
- pickle 反序列化 (`obj_loads`、`redis_cache`) 可执行构造对象的代码；数据源必须可信。
- 密码需要慢哈希（默认 Argon2），不能使用 `crypto` 的 AES、MD5、SHA 或可逆密文替代。
- 密钥、Consul token、数据库 URI 与外部服务 endpoint 由部署环境注入；文档示例只使用占位值。Kafka 不再由 jcutil 提供驱动封装，应用必须直接拥有自己的 Kafka 客户端、配置和生命周期。

这些约束是公共使用契约。任何改变应同步更新使用指南、API docstring 和对应测试。
