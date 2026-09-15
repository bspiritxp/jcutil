# Consul、服务端配置与调度

这些模块假定应用已具备基础设施：Consul agent、MongoDB 或二者。它们不是本地开发的默认依赖路径。

## 读取 Consul KV

```python
from jcutil.consul import ConfigFormat, ConsulClient, fetch_key

client = ConsulClient(host='127.0.0.1', port=8500)
settings = fetch_key('config/demo/prod', fmt=ConfigFormat.Yaml, client=client)
```

`fetch_key()` 要求该键存在且值非空，否则触发 `AssertionError`。支持 `Text`、`Number`、`Int`、`Float`、`Json`、`Yaml` 和 `Hcl` 格式。全局快捷函数默认使用模块导入时创建的客户端；需要控制 host、ACL token 或 TLS 时，应显式传入 `ConsulClient`。

服务注册、健康检查、会话和锁也有模块级函数。锁的最小生命周期：

```python
from jcutil.consul import acquire_lock, create_session, destroy_session, release_lock

session = create_session('worker-1', ttl='30s')
try:
    if acquire_lock('locks/demo', session, 'worker-1'):
        # 受锁保护的工作
        release_lock('locks/demo', session)
finally:
    destroy_session(session)
```

生产代码需要在 TTL 到期前调用 `renew_session()`，并确保异常路径释放锁和销毁 session。

## 服务端环境和配置加载

`jcutil.server.envars` 在导入时读取 `.env`、计算本机 IP，并调用 `logging.basicConfig()`。仅在应用入口、且接受这些全局副作用时导入。

`Envars.CONFIG_PATH` 的默认形式是 `config/<app_name>/<app_env>`，其构成来自 `CONSUL_KV_PATH`、`APP_NAME` 和 `APP_ENV`。`server.config.load_config(*keys)` 从该路径读取 YAML，并将匹配的驱动段交给 `smart_load()`；传入任意 `keys` 时配置必须含 `server` 键。

只读 KV 时请直接调用 `consul.fetch_key()`，不要使用 `load_config()`，后者会加载驱动并更新 `server.config.context['conf']`。

## MongoDB 持久化调度

```python
from jcutil.schedjob import SchedulerType, create_by_mongo

scheduler = create_by_mongo(
    SchedulerType.BACKGROUND,
    database='app',
    collection='jobs.worker-1',
    host='localhost',
    port=27017,
)
scheduler.add_job(print, {'id': 'heartbeat', 'trigger': 'interval', 'seconds': 60, 'args': ('ok',)})
await scheduler.start()
```

`create_by_mongo()` 只能在每个进程调用一次；再次调用会断言失败。`start()` 是协程，且会一直运行到 `stop()` 释放内部锁。后台调度器、异步调度器和阻塞调度器分别由 `SchedulerType` 选择。`default_store_opts()` 从已注册的 Mongo 客户端构造 jobstore 参数。

`dba.Where` 仅将字典拼成 `AND` SQL 文本。它不是 SQL 参数化机制，严禁用于任何不可信输入。

完整签名见[Consul、服务端与调度 API](../reference/integrations.md)。
