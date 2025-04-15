# JCUtil 密码哈希与安全工具

这个模块提供了安全的密码哈希、验证和加密功能，使用行业标准的算法和最佳实践。

## 功能特点

- **多算法支持**: 支持 Argon2、BCrypt、PBKDF2_SHA256 和 SHA512 多种哈希算法
- **自动升级**: 可以自动将旧的哈希算法升级到更安全的新算法
- **安全令牌生成**: 生成高熵随机令牌，适用于会话标识符、CSRF令牌等
- **密码生成器**: 生成符合安全要求的随机密码
- **防时序攻击比较**: 安全地比较哈希值，避免时序攻击

## 安装

确保已安装所需依赖：

```bash
pip install passlib bcrypt argon2-cffi
```

## 使用示例

### 密码哈希和验证

```python
from jcutil.crypto_utils import password_hash, password_verify, HashScheme

# 使用默认算法(Argon2)哈希密码
password_hash = password_hash("my_secure_password")

# 使用特定算法哈希密码
bcrypt_hash = password_hash("my_secure_password", HashScheme.BCRYPT)
pbkdf2_hash = password_hash("my_secure_password", HashScheme.PBKDF2, rounds=150000)

# 验证密码
is_valid, new_hash = password_verify("my_secure_password", password_hash)
if is_valid:
    print("密码验证成功!")
    if new_hash:
        # 如果返回了新哈希值，表示原哈希已升级到更安全的算法
        print("哈希已升级，建议存储新哈希值")
else:
    print("密码验证失败!")
```

### 生成安全令牌

```python
from jcutil.crypto_utils import generate_token

# 生成URL安全的随机令牌 (适用于重置密码链接等)
reset_token = generate_token(length=32, url_safe=True)

# 生成标准Base64编码的令牌
session_token = generate_token(length=24, url_safe=False)
```

### 生成随机密码

```python
from jcutil.crypto_utils import generate_password

# 生成12字符长度、包含所有字符类型的密码
password = generate_password(length=12, complexity=4)

# 生成只包含字母和数字的密码
simple_password = generate_password(length=10, complexity=2)
```

### 安全字符串比较

```python
from jcutil.crypto_utils import secure_compare

# 安全比较两个字符串，防止时序攻击
is_same = secure_compare(token_a, token_b)
```

## 完整示例

查看 `examples/password_example.py` 获取完整功能演示。

## 安全建议

1. **永远不要存储明文密码** - 始终使用哈希值
2. **避免自定义加密算法** - 使用经过验证的库和标准
3. **定期升级哈希算法** - 当有新的安全标准时进行更新
4. **使用足够的熵** - 生成令牌和密码时使用适当的长度

## 支持的哈希算法

| 算法 | 枚举值 | 安全性 | 推荐用途 |
|------|---------|----------|-------------|
| Argon2 | `HashScheme.ARGON2` | 极高 | 默认首选算法 |
| BCrypt | `HashScheme.BCRYPT` | 高 | 广泛兼容的选择 |
| PBKDF2 | `HashScheme.PBKDF2` | 中高 | 兼容性好 |
| SHA512 | `HashScheme.SHA512` | 中 | 仅用于兼容旧系统 |

## 参考资料

- [OWASP密码存储指南](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)
- [Passlib文档](https://passlib.readthedocs.io/) 