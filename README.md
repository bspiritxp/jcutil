# JC Util

> Author: Jochen.He


module|desc
-|-
core|一些常用的工具方法
chalk|粉笔，控制台输出带颜色文本
drivers|常用数据库等连接工具
consul|Consul使用工具
crypto|简易AES加解密工具
data|函数结果缓存工具
netio|异步网络请求实用工具
schedjob|定时任务实用工具（默认使用mongodb store）

## 1. Chalk

『粉笔工具』

用于在`console`输出带有颜色和样式的文字

**Example:**

```python
RedChalk('a red string')
BrightBlueChalk('a bright blue string')
YellowChalk().bold('a bold yellow string')
```

## 2. Drivers

module|desc
-|-
db|关系型数据库驱动; 推荐安装`sqlalchemy`
mongodb|mongodb驱动
redis|redis驱动
mq|kafka驱动

### Example

```yaml
db:
  app: oracle://user:pwd@master.oradb.local/jstd?encoding=utf-8
  bsit: mysql+pymysql://app:pwd@master.mysql.local:3306/?charset=utf8mb
  jp: postgresql://app:pwd@master.psl.local:5432/linkedalliance
  ym: oracle://app:pwd@other.oradb.local:1521/orcl2?encoding=utf-8
mongo:
  app: mongodb://app:pwd@mongo1.local:27017/app
  pump: mongodb://pump:pwd@mongo1.local:27017,mongo2.local:27017,mongo3.local:27017/pump?replicaSet=zxjr
redis:
  app: cluster://redis1.local:6379,redis3.local:6379,redis5.local:6379
  cache: redis://10.116.132.74:6379
mq:
  app: 10.116.132.110:9092,10.116.132.112:9092,10.116.132.108:9092
```

```python
import yaml
from jcutil.drivers import smart_load, db, mongo, redis, mq

conf = yaml.load('config.yaml', Loader=yaml.SafeLoader)
# auto read config and register driver
smart_load(conf)

# use oracle is aliased "app" database
with db.connect('app') as conn:
  ...

# register a new database (sqlite3 with memory) and alias to 'memCache'
db.new_client('sqlite:///:memory', 'memCache')
with db.connect('memCache') as conn:
  ...

# ===== mongodb =======

# mongo: use aliased 'app' mongodb and find document from 'user' collection
user = mongo.get_collection('app', 'user')
docs = user.find({...})

# add a new mongodb client
mongo.new_client('mongodb://...', 'otherMongodb')

# ======= redis ========

client = redis.conn('app')
client.set('a', 111)

# ======= kafka ========

mq.send('app', 'some-topic', 'some message or json string')
```


## 3. Core实用函数API

函数名|函数签名|说明
-|-|-
`init_event_loop`|`() -> Loop`|获取或新建event loop
`host_mac`|`() -> str`|获取主机mac地址，16进制字符串
`hmac_sha256`|`(bytes, AnyStr) -> str`|base64格式的随机签名
`uri_encode`|`(str) -> str`|对字符串进行url安全编码
`uri_decode`|`(str) -> str`|对url编码的字符串进行解码
`async_run`|`(Callabe, *args, bool) -> Any`|异步执行同步函数，`with_context`用于控制是否复制线程上下文
`nl_print`|`(Any) -> None`|默认末尾输出2个换行的`print`函数
`c_write`|`(Any) -> None`|默认不输出换行的`print`函数
`clear`|-|控制台输出清屏
`load_fc`|`(str, Optional[str]) -> Callable`|动态导入(`import`)指定名称的方法
`obj_dumps`|`(Any) -> str`|序列化对象为一个base64字符串
`obj_loads`|`(str) -> Any`|反序列化base64字符串到对象
`map_async`|`(Callabe, Iterable, int) -> List`|异步非阻塞Map函数(Event Loop版)
`fix_document`|`(dict, dict) -> dict`|按照类型配置修复dict中的值（常用于kafka中接受json字符串后进行值修复）
`to_obj`|-|使用安全的类型转换字符串为Json
`from_json_file`|(Pathlike) -> Any|使用安全的类型读取Json文件
`to_json`|-|使用安全的类型转换对象为字符串
`to_json_file`|-|使用安全的类型转换对象为Json文件
`pp_json`|`(Any) -> None`|带色彩高亮输出对象为Json字符串
`df_dt`|-|转换输入值为pandas.datetime
`df_to_json`|-|转换pandas的DataFrame为Json
`ser_to_json`|-|转换pandas的Series为Json
`df_to_dict`|-|DataFrame或Series转标准dict
