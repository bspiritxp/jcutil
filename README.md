# JC Util

> Author: Jochen.He

通用Python实用工具库，包含控制台彩色输出、数据库驱动、缓存工具等多种功能。

> jcutil 3.0 requires Python 3.12 or newer.

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
│   │   └── redis.py      # Redis驱动
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
`drivers`|数据库连接与缓存客户端工具
`consul`|Consul服务发现与配置工具
`crypto`|加密解密工具，支持AES/RSA/哈希等多种算法
`data`|函数结果缓存工具
`netio`|异步网络请求工具
`schedjob`|定时任务工具（默认使用MongoDB存储）

## 使用手册

面向使用者的完整手册、按任务组织的指南和自动同步的 API 参考位于 [`docs/`](docs/index.md)。

本地浏览：

```bash
uv run --group docs mkdocs serve
```

提交前构建并检查链接：

```bash
uv run --group docs mkdocs build --strict
```

## 详细文档

### 1. Chalk - 控制台彩色输出工具

`jcutil.chalk` 同时提供直接渲染函数和增量式 `Chalk`。`render()` 适合单段文本；`Chalk` 则表示一支正在使用的粉笔：选颜色或样式、写入一段文本、再换一支粉笔继续写。每次 `write()` 都会快照当前属性，后续变更不会影响已写入的文字。

#### Chalk 链式写作

```python
from jcutil.chalk import Chalk, ColorMode

message = (
    Chalk(mode=ColorMode.ALWAYS)
    .green('服务')
    .bold()
    .write(' 已启动')
    .red()
    .style()
    .write('；等待请求')
)
print(f'状态: {message}')
```

`Chalk` 是可变的链式 builder，所有选色、选背景、选样式和 `write()` 方法都返回同一个实例。使用 `color()`、`background()` 和 `style()` 设置后续文本；`style()` 不带参数会清除当前样式，`reset()` 会清除颜色、背景和样式。`red()`、`green()` 等颜色方法以及 `bold()`、`italic()`、`underline()` 等样式方法可以直接接收要写入的文本。

兼容旧调用：`RedChalk`、`GreenChalk`、`BlueChalk`、其余基础色与全部 `Bright*Chalk` 工厂，以及 `BoldChalk` 都仍可用。例如 `RedChalk('错误')` 等价于 `Chalk('错误', Color.RED)`，并返回同样可继续链式调用的 `Chalk` 实例。

#### 直接渲染

```python
from jcutil.chalk import Color, TextStyle, render

message = render('服务已启动', fg=Color.GREEN, styles=(TextStyle.BOLD,))
print(f'状态: {message}')
```

#### 颜色、背景和样式

`Color` 提供标准和明亮的 16 个 ANSI 前景色；将同一个颜色用于 `bg` 时会生成相应背景色。`TextStyle` 提供 `BOLD`、`DIM`、`ITALIC`、`UNDERLINE`、`REVERSE` 和 `STRIKETHROUGH`。

```python
from jcutil.chalk import Color, TextStyle, render

warning = render(
    '磁盘空间不足',
    fg=Color.BLACK,
    bg=Color.YELLOW,
    styles=(TextStyle.BOLD, TextStyle.UNDERLINE),
)
print(f'警告: {warning}')
```

除粗体等基础效果外，样式的可视支持由终端决定。该模块不声明 256 色或真彩色兼容性。

#### 输出策略

`ColorMode.AUTO` 是默认策略：仅在目标 stream 是 TTY 且 `TERM` 不为 `dumb` 时输出 ANSI。`stream` 未指定时检查 `sys.stdout`，因此重定向输出默认保持纯文本。非空的 `NO_COLOR` 仅在 `AUTO` 下禁用前景和背景色，保留请求的文本样式。

```python
from jcutil.chalk import Color, ColorMode, render

# 即使输出被重定向，也明确要求颜色。
payload = render('已完成', fg=Color.GREEN, mode=ColorMode.ALWAYS)
print(f'任务: {payload}')

# 明确禁用全部 ANSI 属性。
print(f'任务: {render("已完成", fg=Color.GREEN, mode=ColorMode.NEVER)}')
```

`ALWAYS` 和 `NEVER` 都会覆盖 TTY、`TERM` 与 `NO_COLOR` 自动策略。Windows 上仅在实际选择输出 ANSI 时，`enable_windows_ansi()` 才会通过已声明的 `colorama` 依赖启用虚拟终端支持；模块导入本身不会初始化终端。

### 2. Drivers - 数据库驱动工具

模块|描述
-|-
`db`|关系型数据库驱动; 推荐安装`sqlalchemy`
`mongodb`|MongoDB驱动（同时支持同步和异步操作）
`redis`|Redis驱动（支持同步和异步操作）

#### v3 数据库配置

`db` 标签现在显式声明同步或异步模式；不要从 URL 文本推断模式：

```yaml
db:
  app:
    url: postgresql+psycopg://user:password@db.example/app
    mode: sync
    pool_pre_ping: true
  analytics:
    url: postgresql+asyncpg://user:password@db.example/analytics
    mode: async
```

#### v3 使用示例

```python
from sqlalchemy import text

from jcutil.drivers import db

db.register_sync('app', 'sqlite:///:memory:')
try:
    with db.connect('app') as connection:
        connection.execute(text('SELECT 1'))
finally:
    db.dispose_sync('app')
```

异步引擎使用 `db.register_async()` 和 `async with db.async_connect(tag)`。完整的驱动、HTTP、SSE 和 WebSocket 使用手册见 [`docs/`](docs/index.md)。

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
`fix_document`|`(dict, dict) -> dict`|按照类型配置修复dict中的值（常用于JSON文档清洗）
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