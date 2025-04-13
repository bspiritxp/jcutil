# JC Util

> Author: Jochen.He

通用Python实用工具库，包含控制台彩色输出、数据库驱动、缓存工具等多种功能。

## 目录结构

```
jcutil/
│
├── src/jcutil/           # 主源代码目录
│   ├── chalk/            # 控制台彩色输出工具
│   ├── core/             # 核心工具函数
│   ├── drivers/          # 数据库驱动工具
│   │   ├── db.py         # 关系型数据库驱动
│   │   ├── mongo.py      # MongoDB驱动
│   │   ├── redis.py      # Redis驱动
│   │   └── mq.py         # 消息队列驱动(Kafka)
│   ├── consul.py         # Consul配置工具
│   ├── crypto.py         # 加密解密工具
│   ├── data.py           # 缓存工具
│   ├── defines.py        # 常量定义
│   ├── netio.py          # 网络IO工具
│   └── schedjob.py       # 定时任务工具
│
├── tests/                # 测试目录
│   ├── test_chalk.py     # Chalk模块测试
│   ├── test_core.py      # 核心功能测试
│   └── ...               # 其他测试文件
│
└── ...                   # 其他配置文件
```

## 模块说明

模块|描述
-|-
`chalk`|粉笔工具，用于控制台输出带颜色文本
`core`|常用工具函数集合(JSON处理、异步执行等)
`drivers`|数据库及消息队列连接工具
`consul`|Consul服务发现与配置工具
`crypto`|加密解密工具，支持AES/RSA/哈希等多种算法
`data`|函数结果缓存工具
`netio`|异步网络请求工具
`schedjob`|定时任务工具（默认使用MongoDB存储）

## 详细文档

### 1. Chalk - 控制台彩色输出工具

在终端中输出带有颜色和格式的文本，支持链式调用、样式组合和嵌套使用。

#### 安装依赖

Chalk模块依赖`colorama`库以支持跨平台彩色输出：

```bash
pip install colorama
```

#### 基本用法

```python
from jcutil.chalk import RedChalk, GreenChalk, YellowChalk, FontFormat

# 基本颜色输出
print(RedChalk("这是红色文本"))
print(GreenChalk("这是绿色文本"))

# 链式调用
print(YellowChalk().bold("粗体黄色文本").text(" 普通黄色文本"))

# 嵌套使用
print(GreenChalk(f"绿色文本中嵌入{RedChalk('红色文本')}继续绿色"))

# 文本连接
result = RedChalk("红色") + " 普通文本 " + GreenChalk("绿色")
print(result)
```

#### 可用颜色

Chalk提供了以下预定义颜色：

- `BlackChalk` - 黑色
- `RedChalk` - 红色
- `GreenChalk` - 绿色
- `YellowChalk` - 黄色
- `BlueChalk` - 蓝色
- `MagentaChalk` - 洋红色
- `CyanChalk` - 青色
- `WhiteChalk` - 白色

此外，还提供了明亮色系列：

- `BrightBlackChalk` - 亮黑色(灰色)
- `BrightRedChalk` - 亮红色
- `BrightGreenChalk` - 亮绿色
- `BrightYellowChalk` - 亮黄色
- `BrightBlueChalk` - 亮蓝色
- `BrightMagentaChalk` - 亮洋红色
- `BrightCyanChalk` - 亮青色
- `BrightWhiteChalk` - 亮白色

#### 文本样式

可以通过以下方式为文本添加样式：

```python
from jcutil.chalk import RedChalk, FontFormat

# 使用样式方法
print(RedChalk().bold("粗体文本"))
print(RedChalk().italic("斜体文本"))
print(RedChalk().underline("下划线文本"))

# 链式组合样式
print(RedChalk().bold("粗体").text(" 普通 ").italic("斜体").text(" 组合样式"))

# 使用use方法设置样式
print(RedChalk().use(FontFormat.BOLD, FontFormat.UNDER_LINE).text("粗体下划线"))
```

支持的样式类型（`FontFormat`枚举）：

- `BOLD` - 粗体
- `LIGHT` - 轻体
- `ITALIC` - 斜体
- `UNDER_LINE` - 下划线
- `BLINK` - 闪烁
- `RESERVE` - 反相
- `DELETE` - 删除线

#### 高级用法

##### 背景色设置

```python
from jcutil.chalk import Chalk, Color

# 设置前景色和背景色
print(Chalk("彩色文本", fgc=Color.WHITE, bgc=Color.RED))

# 使用use方法设置背景色
print(Chalk().use(fg_color=Color.BLACK, bg_color=Color.YELLOW).text("黑字黄底"))
```

##### 字符串格式化

```python
from jcutil.chalk import RedChalk

# 使用%操作符
print(RedChalk("值: %d") % 42)

# 嵌入f-string
name = "世界"
print(RedChalk(f"你好，{name}！"))
```

##### 菜单生成

Chalk模块提供了生成交互式菜单的功能：

```python
from jcutil.chalk import show_menu

def option1():
    print("选择了选项1")
    return "选项1结果"

def option2():
    print("选择了选项2")
    return "选项2结果"

# 定义菜单项列表 [(显示文本, 执行函数), ...]
menu_items = [
    ("选项1", option1),
    ("选项2", option2),
]

# 显示菜单并获取用户选择结果
result = show_menu(menu_items, title="测试菜单")
print(f"返回结果: {result}")
```

#### 自定义Chalk

可以通过基础`Chalk`类创建自定义样式：

```python
from jcutil.chalk import Chalk, Color, FontFormat

# 创建自定义彩色文本函数
WarningChalk = lambda text=None: Chalk(text, fgc=Color.BLACK, bgc=Color.YELLOW)
ErrorChalk = lambda text=None: Chalk(text, fgc=Color.WHITE, bgc=Color.RED, styles=(FontFormat.BOLD,))

print(WarningChalk("警告信息"))
print(ErrorChalk("错误信息"))
```

### 2. Drivers - 数据库驱动工具

模块|描述
-|-
`db`|关系型数据库驱动; 推荐安装`sqlalchemy`
`mongodb`|MongoDB驱动（同时支持同步和异步操作）
`redis`|Redis驱动（支持异步操作）
`mq`|Kafka驱动

#### 配置示例

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

#### 使用示例

```python
import yaml
from jcutil.drivers import smart_load, db, mongo, redis, mq

# 读取配置文件
with open('config.yaml', 'r') as f:
    conf = yaml.safe_load(f)
    
# 自动加载配置并注册驱动
smart_load(conf)

# 使用别名为"app"的Oracle数据库
with db.connect('app') as conn:
    result = conn.execute("SELECT * FROM users")
    for row in result:
        print(row)

# 注册新的内存SQLite数据库并使用
db.new_client('sqlite:///:memory:', 'memCache')
with db.connect('memCache') as conn:
    conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test VALUES (1, 'test')")

# MongoDB操作示例
user_coll = mongo.get_collection('app', 'users')
users = user_coll.find({'active': True})
for user in users:
    print(user['name'])

# Redis操作示例
redis_client = redis.connect('app')
redis_client.set('key', 'value')
print(redis_client.get('key'))

# Kafka消息发送示例
mq.send('app', 'user-events', '{"event": "user_login", "user_id": 123}')
```

## 3. Core实用函数API

函数名|函数签名|说明
-|-|-
`init_event_loop`|`() -> Loop`|获取或新建event loop
`host_mac`|`() -> str`|获取主机mac地址，16进制字符串
`hmac_sha256`|`(bytes, AnyStr) -> str`|base64格式的随机签名
`uri_encode`|`(str) -> str`|对字符串进行url安全编码
`uri_decode`|`(str) -> str`|对url编码的字符串进行解码
`async_run`|`(Callable, *args, bool) -> Any`|异步执行同步函数，`with_context`用于控制是否复制线程上下文
`nl_print`|`(Any) -> None`|默认末尾输出2个换行的`print`函数
`c_write`|`(Any) -> None`|默认不输出换行的`print`函数
`clear`|-|控制台输出清屏
`load_fc`|`(str, Optional[str]) -> Callable`|动态导入(`import`)指定名称的方法
`obj_dumps`|`(Any) -> str`|序列化对象为一个base64字符串
`obj_loads`|`(str) -> Any`|反序列化base64字符串到对象
`map_async`|`(Callable, Iterable, int) -> List`|异步非阻塞Map函数(Event Loop版)
`fix_document`|`(dict, dict) -> dict`|按照类型配置修复dict中的值（常用于kafka中接受json字符串后进行值修复）
`to_obj`|-|使用安全的类型转换字符串为Json
`from_json_file`|`(Pathlike) -> Any`|使用安全的类型读取Json文件
`to_json`|-|使用安全的类型转换对象为字符串
`to_json_file`|-|使用安全的类型转换对象为Json文件
`pp_json`|`(Any) -> None`|带色彩高亮输出对象为Json字符串
`df_dt`|-|转换输入值为pandas.datetime
`df_to_json`|-|转换pandas的DataFrame为Json
`ser_to_json`|-|转换pandas的Series为Json
`df_to_dict`|-|DataFrame或Series转标准dict

## 4. Crypto加密工具

加密解密工具模块，支持多种加密算法，包括AES、RSA、各种哈希函数等。

#### 安装依赖

```bash
pip install pycryptodomex
```

#### AES加密解密

AES是一种对称加密算法，使用相同的密钥进行加密和解密。

```python
from jcutil.crypto import (
    aes_encrypt, aes_decrypt, aes_ecb_encrypt, aes_ecb_decrypt,
    aes_cbc_encrypt, aes_cbc_decrypt, aes_cfb_encrypt, aes_cfb_decrypt,
    get_sha1prng_key, generate_aes_key, Mode
)

# 生成随机密钥
key = generate_aes_key(32)  # 生成32字节的随机密钥
print(f"随机生成的密钥: {key}")

# 基本AES加密解密
plain_text = "Hello, World!"
cipher_text, nonce = aes_encrypt(key, plain_text)  # 默认使用EAX模式
decrypted_text = aes_decrypt(key, cipher_text, nonce_or_iv=nonce)
print(f"解密结果: {decrypted_text}")

# 使用不同模式
cipher_text, iv = aes_encrypt(key, plain_text, mode=Mode.CBC)
decrypted_text = aes_decrypt(key, cipher_text, mode=Mode.CBC, nonce_or_iv=iv)

# 使用预定义函数简化调用
cipher_text = aes_ecb_encrypt(key, plain_text)  # ECB模式不需要IV
decrypted_text = aes_ecb_decrypt(key, cipher_text)

# 与Java AES兼容的密钥生成
java_compatible_key = get_sha1prng_key("my_password")
```

#### 哈希函数

提供各种常用哈希算法实现：

```python
from jcutil.crypto import (
    hash_md5, hash_sha1, hash_sha256, hash_sha512, sha3sum,
    hmac_sha1, hmac_sha256
)

# 计算字符串哈希值
text = "Hello, World!"
print(f"MD5: {hash_md5(text)}")
print(f"SHA1: {hash_sha1(text)}")
print(f"SHA256: {hash_sha256(text)}")
print(f"SHA512: {hash_sha512(text)}")
print(f"SHA3-256: {sha3sum(text)}")

# 计算HMAC值
key = "secret_key"
print(f"HMAC-SHA1: {hmac_sha1(key, text)}")
print(f"HMAC-SHA256: {hmac_sha256(key, text)}")
```

#### RSA加密与签名

RSA是一种非对称加密算法，使用公钥加密、私钥解密：

```python
from jcutil.crypto import (
    generate_rsa_key_pair, rsa_encrypt, rsa_decrypt,
    rsa_sign, rsa_verify
)

# 生成RSA密钥对
key_pair = generate_rsa_key_pair(2048)
private_key = key_pair['private_key']
public_key = key_pair['public_key']

# 使用公钥加密
plain_text = "这是RSA加密测试"
encrypted = rsa_encrypt(public_key, plain_text)

# 使用私钥解密
decrypted = rsa_decrypt(private_key, encrypted)
print(f"解密结果: {decrypted.decode()}")

# 数字签名
message = "待签名的数据"
signature = rsa_sign(private_key, message)

# 验证签名
is_valid = rsa_verify(public_key, message, signature)
print(f"签名验证结果: {is_valid}")
```

#### Base64编码

提供标准和URL安全的Base64编码实现：

```python
from jcutil.crypto import to_base64, from_base64, to_base64_url_safe

# 标准Base64编码
data = "Hello, World!"
encoded = to_base64(data)
print(f"Base64编码: {encoded}")

# Base64解码
decoded = from_base64(encoded)
print(f"解码结果: {decoded.decode()}")

# URL安全的Base64编码
url_safe = to_base64_url_safe(data)
print(f"URL安全编码: {url_safe}")
```

#### PBKDF2密钥派生

基于密码的安全密钥生成：

```python
from jcutil.crypto import pbkdf2_key

# 从密码生成密钥
password = "my_secure_password"
key, salt = pbkdf2_key(password)
print(f"生成的密钥: {key.hex()}")
print(f"盐值: {salt.hex()}")

# 使用已知盐值重新生成相同的密钥
same_key, _ = pbkdf2_key(password, salt)
print(f"相同的密钥: {same_key.hex()}")
```

#### 实用工具函数

```python
from jcutil.crypto import secure_compare, generate_random_string

# 安全字符串比较(抵抗时序攻击)
is_equal = secure_compare("string1", "string2")

# 生成随机字符串
random_str = generate_random_string(32)
print(f"随机字符串: {random_str}")
```

#### 可用的加密模式

AES支持多种加密模式：

```python
from jcutil.crypto import Mode

# 可用的AES加密模式
print(f"ECB模式: {Mode.ECB}")  # 电子密码本模式
print(f"CBC模式: {Mode.CBC}")  # 密码块链接模式
print(f"CFB模式: {Mode.CFB}")  # 密码反馈模式
print(f"OFB模式: {Mode.OFB}")  # 输出反馈模式
print(f"CTR模式: {Mode.CTR}")  # 计数器模式
print(f"EAX模式: {Mode.EAX}")  # EAX模式
print(f"GCM模式: {Mode.GCM}")  # 伽罗瓦计数器模式
print(f"CCM模式: {Mode.CCM}")  # 计数器CBC-MAC模式
print(f"OCB模式: {Mode.OCB}")  # 偏移密码块模式
print(f"SIV模式: {Mode.SIV}")  # 合成初始化向量模式
```

## 开发指南

### 代码质量检查

本项目使用 [Ruff](https://github.com/charliermarsh/ruff) 进行代码静态检查，确保代码风格一致性和代码质量。

#### 本地运行代码检查

##### 使用脚本（推荐）

项目提供了便捷脚本用于检查和自动修复代码风格问题：

- Linux/macOS:
  ```bash
  # 确保脚本有执行权限
  chmod +x scripts/lint.sh
  # 运行脚本
  ./scripts/lint.sh
  ```

- Windows:
  ```powershell
  # 运行PowerShell脚本
  .\scripts\lint.ps1
  ```

##### 手动运行

如果你已经安装了 uv 和 ruff，可以直接运行：

```bash
# 检查代码风格问题并自动修复
uvx ruff check . --fix

# 检查是否还有未修复的问题
uvx ruff check .
```


## 许可证

本项目采用 [MIT许可证](LICENSE) 授权。

```
MIT License

Copyright (c) 2020 Jochen.He

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.