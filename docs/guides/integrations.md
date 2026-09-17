# Consul、服务端配置与调度

这些模块假定应用已具备基础设施：Consul agent、MongoDB 或二者。它们不是本地开发的默认依赖路径。

## 读取 Consul KV

```python
from jcutil.consul import ConfigFormat, ConsulClient, fetch_key

client = ConsulClient(host='127.0.0.1', port=8500)
settings = fetch_key('config/demo/prod', fmt=ConfigFormat.Yaml, client=client)
```

`fetch_key()` 要求键记录存在，否则触发 `AssertionError`；默认对 `Value` 进行文本解码，不替缺失值提供默认内容。支持 `Text`、`Number`、`Int`、`Float`、`Json`、`Yaml` 和 `Hcl` 格式；数值格式仍是 `ConfigFormat` 枚举成员，但会在解析时自动展开为对应转换函数。`kv_get()` 保持 py-consul 原生 `(index, data)` 元组。

`ConsulClient()` 无参数时保留 py-consul 的模块默认行为（包括 `CONSUL_HTTP_*` 环境变量）。只要传入任一构造参数，显式参数会被转发；例如 `ConsulClient(host=None, port=8501, token='...')` 使用默认 host，但保留显式端口和 token。同步客户端持有 requests session，生产代码应调用 `close()` 或使用 `with ConsulClient(...) as client:` 管理生命周期。原生同步客户端仍可通过 `client.client` 访问，`Consul` 仍是 py-consul 的原生类别名。

只传 `token` 时仍保留环境中的地址；显式指定 host 时保留旧版端口 8500、HTTP、TLS 验证开启的默认值。`KvProperty` 保留原远端路径规则；`bar = KvProperty('foo', cached=True)` 现在正确缓存到 `bar`，类属性访问返回描述符且不打印。

服务注册、健康检查、会话和锁也有模块级函数；这些函数默认使用模块导入时创建的客户端，也可通过关键字参数 `client=` 注入显式客户端。服务查询使用本地 agent 的 `agent.services()` 字典，不查询 catalog。锁的最小生命周期：

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

生产代码需要在 TTL 到期前调用 `renew_session()`，并确保异常路径释放锁和销毁 session。创建会话兼容原有 `'30s'` 秒数字符串及上游整数秒数；保持 `renew_session()` 异常返回 `False` 的契约，不自动续约。


## 异步 Consul 客户端

异步支持是可选安装项，避免同步导入路径强依赖 aiohttp：

```bash
pip install 'jcutil[consul-async]'
```

```python
from jcutil.consul import AsyncConsulClient

async with AsyncConsulClient(host='127.0.0.1', port=8500) as client:
    index, data = await client.kv_get('config/demo/prod')
    native = client.client  # consul.aio.Consul，用于本封装未重复暴露的 API
```

`AsyncConsulClient` 使用 py-consul 的 `consul.aio` transport；未安装可选依赖时会在实例化时抛出说明安装方式的 `ImportError`。在运行中的事件循环内创建和关闭，不跨事件循环共享。异步方法与同步封装保持同名语义，但不会把同步方法改成协程，也不会自动续约、后台 watch、重试或改变异常策略。使用 `await client.close()` 或 `async with` 关闭 aiohttp session。

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
