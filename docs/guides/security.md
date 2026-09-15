# 密码与密码学

`jcutil.crypto_utils` 处理**密码哈希**、验证与令牌；`jcutil.crypto` 处理可逆加密、摘要、HMAC、RSA 与安全比较。两者用途不同，密码绝不能用 AES 或普通哈希保存。

## 密码哈希与迁移

默认方案为 Argon2。确保对应后端可用：

```bash
pip install argon2-cffi
```

```python
from jcutil.crypto_utils import password_hash, password_verify

stored = password_hash('correct horse battery staple')
valid, replacement = password_verify('correct horse battery staple', stored)
assert valid

if replacement is not None:
    # 将 replacement 写回用户记录；原 hash 已落后于当前默认策略。
    stored = replacement
```

`password_verify()` 对格式不合法或验证失败的 hash 返回 `(False, None)`。`replacement` 非空表示 Passlib 判定原 hash 需要升级。可以通过 `HashScheme.BCRYPT`、`HashScheme.PBKDF2` 或 `HashScheme.SHA512` 显式选择历史兼容方案；新增密码优先保留默认 Argon2。

## 随机令牌和密码

```python
from jcutil.crypto_utils import generate_password, generate_token

reset_token = generate_token(length=32, url_safe=True)
temporary_password = generate_password(length=16, complexity=4)
```

`length` 是随机字节数（令牌）或字符数（密码）。`url_safe=True` 使用 URL-safe Base64。随机密码 `complexity` 可选 1–4 类字符；值超出这个范围会抛出 `ValueError`。

## AES

```python
from jcutil.crypto import Mode, aes_decrypt, aes_encrypt, generate_aes_key

key = generate_aes_key(32)
ciphertext, nonce_or_iv = aes_encrypt(key, 'secret payload', mode=Mode.EAX)
plaintext = aes_decrypt(key, ciphertext, mode=Mode.EAX, nonce_or_iv=nonce_or_iv)
assert plaintext == 'secret payload'
```

加密结果和 nonce/IV 都是大写十六进制文本。解密必须使用**相同模式、相同密钥和返回的 nonce/IV**。不要将密钥与密文一起保存，也不要自行从密码截断密钥；如确需从密码派生密钥，使用 `pbkdf2_key()` 并持久化盐。

!!! warning "模式选择"
    库公开 ECB 便捷函数仅用于既有协议兼容；新数据不要选 ECB。`aes_encrypt()` 的默认模式是 EAX。调用方仍需设计密钥轮换、密文存储和访问控制。

## 摘要、HMAC 与 RSA

- `hash_sha256()`、`sha3sum()` 等返回大写十六进制摘要。MD5/SHA-1 仅用于兼容或非安全校验。
- `hmac_sha256(key, message)` 为消息完整性生成大写十六进制 HMAC；它不加密消息。
- `generate_rsa_key_pair(bits=2048)` 返回 PEM bytes 字典；`rsa_encrypt()` 返回 Base64 文本；`rsa_decrypt()` 返回 bytes。`rsa_sign()`/`rsa_verify()` 用于签名验证。
- `secure_compare(a, b)` 用 `hmac.compare_digest()` 比较同类型文本或 bytes，适合比较令牌。

完整签名见[安全、缓存与网络 API](../reference/security-cache-network.md)。
