"""
A simple aes encrypt and decrypt module with cryptodome
Support multiple encryption algorithms including AES, RSA, hash functions and more
"""

# depend on pycryptodomex module
import base64
import binascii
import hashlib
import hmac
from enum import IntEnum
from typing import Dict, Optional, Tuple, Union

from Cryptodome.Cipher import AES, PKCS1_OAEP
from Cryptodome.Hash import HMAC, SHA1, SHA256
from Cryptodome.PublicKey import RSA
from Cryptodome.Random import get_random_bytes
from Cryptodome.Signature import pkcs1_15
from Cryptodome.Util.Padding import pad, unpad
from jcramda import co, curry, enum_value, first
from jcramda.base.text import b64_urlsafe_encode

BS = AES.block_size
DEFAULT_ITERATIONS = 10000  # 默认PBKDF2迭代次数


class Mode(IntEnum):
    """AES加密模式"""

    EAX = AES.MODE_EAX
    ECB = AES.MODE_ECB
    CBC = AES.MODE_CBC
    OCB = AES.MODE_OCB
    CFB = AES.MODE_CFB
    OFB = AES.MODE_OFB
    CTR = AES.MODE_CTR
    CCM = AES.MODE_CCM
    GCM = AES.MODE_GCM
    SIV = AES.MODE_SIV


class HashAlgorithm(IntEnum):
    """哈希算法类型"""

    MD5 = 0
    SHA1 = 1
    SHA256 = 2
    SHA512 = 3


# AES加密解密相关函数
@curry
def aes_encrypt(key, plain: str, /, mode=None) -> Tuple[str, str]:
    """AES加密函数

    Args:
        key: 密钥，可以是十六进制字符串或字节
        plain: 待加密的明文
        mode: 加密模式，默认为AES.MODE_EAX

    Returns:
        (密文的十六进制表示, nonce/iv的十六进制表示)
    """
    key = bytes.fromhex(key) if isinstance(key, str) else key
    cipher = AES.new(key, enum_value(mode) or AES.MODE_EAX)
    # add padding to plaintext
    raw = pad(plain.encode(), BS)
    if hasattr(cipher, "encrypt_and_digest"):
        ciphertext, tag = cipher.encrypt_and_digest(raw)
        nonce_or_iv = getattr(
            cipher, "nonce", tag if enum_value(mode) == AES.MODE_SIV else b""
        )
    else:
        ciphertext = cipher.encrypt(raw)
        nonce_or_iv = getattr(cipher, "iv", getattr(cipher, "nonce", b""))
    return tuple(it.hex().upper() for it in (ciphertext, nonce_or_iv))


@curry
def aes_decrypt(key, value: str, /, mode=None, nonce_or_iv: str = None) -> str:
    """AES解密函数

    Args:
        key: 密钥，可以是十六进制字符串或字节
        value: 待解密的密文（十六进制字符串）
        mode: 解密模式，默认为AES.MODE_EAX
        nonce_or_iv: nonce或iv值（十六进制字符串）

    Returns:
        解密后的明文
    """
    key = bytes.fromhex(key) if isinstance(key, str) else key
    args = [key, enum_value(mode) or AES.MODE_EAX]
    kws = {}
    if nonce_or_iv:
        if enum_value(mode) == AES.MODE_CTR:
            kws["nonce"] = bytes.fromhex(nonce_or_iv)
        elif enum_value(mode) != AES.MODE_SIV:
            args.append(bytes.fromhex(nonce_or_iv))
    cryptor = AES.new(*args, **kws)
    if enum_value(mode) == AES.MODE_SIV:
        ciphertext = cryptor.decrypt_and_verify(
            bytes.fromhex(value), bytes.fromhex(nonce_or_iv)
        )
    else:
        ciphertext = cryptor.decrypt(bytes.fromhex(value))
    return unpad(ciphertext, BS).decode()


def get_sha1prng_key(key: str) -> str:
    """SHA1PRNG密钥生成

    使用SHA1PRNG算法生成与Java AES加密兼容的密钥

    Args:
        key: 原始密钥字符串

    Returns:
        生成的密钥（十六进制字符串）
    """
    return hashlib.sha1(hashlib.sha1(key.encode()).digest()).hexdigest().upper()[:32]


# 预定义的AES加密解密函数
aes_ecb_encrypt = co(first, aes_encrypt(mode=AES.MODE_ECB))
aes_ecb_decrypt = aes_decrypt(mode=AES.MODE_ECB)
aes_cfb_encrypt = aes_encrypt(mode=AES.MODE_CFB)
aes_cfb_decrypt = aes_decrypt(mode=AES.MODE_CFB)
aes_cbc_encrypt = aes_encrypt(mode=AES.MODE_CBC)
aes_cbc_decrypt = aes_decrypt(mode=AES.MODE_CBC)
aes_eax_encrypt = aes_encrypt(mode=AES.MODE_EAX)
aes_eax_decrypt = aes_decrypt(mode=AES.MODE_EAX)


# PBKDF2密钥生成
def pbkdf2_key(
    password: str,
    salt: Optional[bytes] = None,
    iterations: int = DEFAULT_ITERATIONS,
    key_length: int = 32,
) -> Tuple[bytes, bytes]:
    """使用PBKDF2算法生成密钥

    Args:
        password: 密码明文
        salt: 盐值，如果为None则随机生成
        iterations: 迭代次数，默认10000
        key_length: 密钥长度，默认32字节

    Returns:
        (密钥, 盐值)
    """
    if salt is None:
        salt = get_random_bytes(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, iterations, key_length
    )
    return derived_key, salt


def generate_aes_key(length: int = 32) -> str:
    """生成随机AES密钥

    Args:
        length: 密钥长度（字节），默认32

    Returns:
        随机密钥（十六进制字符串）
    """
    return get_random_bytes(length).hex().upper()


# Base64编码解码函数
def to_base64(data: Union[str, bytes]) -> str:
    """转换为Base64编码

    Args:
        data: 待编码的数据，可以是字符串或字节

    Returns:
        Base64编码后的字符串
    """
    if isinstance(data, str):
        if all(c in "0123456789ABCDEFabcdef" for c in data) and len(data) % 2 == 0:
            # 如果是十六进制字符串，先转换为字节
            data = bytes.fromhex(data)
        else:
            data = data.encode()
    return base64.b64encode(data).decode()


def from_base64(data: str) -> bytes:
    """从Base64解码

    Args:
        data: Base64编码的字符串

    Returns:
        解码后的字节
    """
    return base64.b64decode(data)


def to_base64_url_safe(data: Union[str, bytes]) -> str:
    """转换为URL安全的Base64编码

    Args:
        data: 待编码的数据，可以是字符串或字节

    Returns:
        URL安全的Base64编码字符串
    """
    if isinstance(data, str):
        if all(c in "0123456789ABCDEFabcdef" for c in data) and len(data) % 2 == 0:
            data = bytes.fromhex(data)
        else:
            data = data.encode()
    return b64_urlsafe_encode(data)


# 哈希函数
def hash_sha1(data: Union[str, bytes]) -> str:
    """计算SHA1哈希值

    Args:
        data: 待哈希的数据，可以是字符串或字节

    Returns:
        十六进制哈希值（大写）
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha1(data).hexdigest().upper()


def hash_sha256(data: Union[str, bytes]) -> str:
    """计算SHA256哈希值

    Args:
        data: 待哈希的数据，可以是字符串或字节

    Returns:
        十六进制哈希值（大写）
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest().upper()


def hash_sha512(data: Union[str, bytes]) -> str:
    """计算SHA512哈希值

    Args:
        data: 待哈希的数据，可以是字符串或字节

    Returns:
        十六进制哈希值（大写）
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha512(data).hexdigest().upper()


def hash_md5(data: Union[str, bytes]) -> str:
    """计算MD5哈希值

    Args:
        data: 待哈希的数据，可以是字符串或字节

    Returns:
        十六进制哈希值（大写）
    """
    if isinstance(data, str):
        data = data.encode()
    return hashlib.md5(data).hexdigest().upper()


def sha3sum(plaintext: Union[str, bytes]) -> str:
    """计算SHA3-256哈希值

    Args:
        plaintext: 待哈希的数据，可以是字符串或字节

    Returns:
        十六进制哈希值（大写）
    """
    if isinstance(plaintext, str):
        plaintext = plaintext.encode()
    return hashlib.sha3_256(plaintext).hexdigest().upper()


# HMAC函数
def hmac_sha256(key: Union[str, bytes], message: Union[str, bytes]) -> str:
    """计算HMAC-SHA256值

    Args:
        key: 密钥，可以是字符串或字节
        message: 消息，可以是字符串或字节

    Returns:
        十六进制HMAC值（大写）
    """
    if isinstance(key, str):
        key = key.encode()
    if isinstance(message, str):
        message = message.encode()
    h = HMAC.new(key, message, SHA256)
    return h.hexdigest().upper()


def hmac_sha1(key: Union[str, bytes], message: Union[str, bytes]) -> str:
    """计算HMAC-SHA1值

    Args:
        key: 密钥，可以是字符串或字节
        message: 消息，可以是字符串或字节

    Returns:
        十六进制HMAC值（大写）
    """
    if isinstance(key, str):
        key = key.encode()
    if isinstance(message, str):
        message = message.encode()
    h = HMAC.new(key, message, SHA1)
    return h.hexdigest().upper()


# RSA加解密相关函数
def generate_rsa_key_pair(bits: int = 2048) -> Dict[str, bytes]:
    """生成RSA密钥对

    Args:
        bits: 密钥位数，默认2048

    Returns:
        包含私钥和公钥的字典
    """
    key = RSA.generate(bits)
    private_key = key.export_key()
    public_key = key.publickey().export_key()
    return {"private_key": private_key, "public_key": public_key}


def rsa_encrypt(public_key: Union[str, bytes], plain_data: Union[str, bytes]) -> str:
    """RSA加密

    Args:
        public_key: RSA公钥，可以是PEM格式的字符串或字节
        plain_data: 待加密的数据，可以是字符串或字节

    Returns:
        加密后的数据（Base64编码）
    """
    if isinstance(public_key, str):
        public_key = public_key.encode()
    if isinstance(plain_data, str):
        plain_data = plain_data.encode()

    key = RSA.import_key(public_key)
    cipher = PKCS1_OAEP.new(key)
    ciphertext = cipher.encrypt(plain_data)
    return base64.b64encode(ciphertext).decode()


def rsa_decrypt(private_key: Union[str, bytes], cipher_data: str) -> bytes:
    """RSA解密

    Args:
        private_key: RSA私钥，可以是PEM格式的字符串或字节
        cipher_data: 待解密的数据（Base64编码）

    Returns:
        解密后的原始数据
    """
    if isinstance(private_key, str):
        private_key = private_key.encode()

    key = RSA.import_key(private_key)
    cipher = PKCS1_OAEP.new(key)
    ciphertext = base64.b64decode(cipher_data)
    return cipher.decrypt(ciphertext)


def rsa_sign(private_key: Union[str, bytes], data: Union[str, bytes]) -> str:
    """RSA签名

    Args:
        private_key: RSA私钥，可以是PEM格式的字符串或字节
        data: 待签名的数据，可以是字符串或字节

    Returns:
        签名值（Base64编码）
    """
    if isinstance(private_key, str):
        private_key = private_key.encode()
    if isinstance(data, str):
        data = data.encode()

    key = RSA.import_key(private_key)
    h = SHA256.new(data)
    signature = pkcs1_15.new(key).sign(h)
    return base64.b64encode(signature).decode()


def rsa_verify(
    public_key: Union[str, bytes], data: Union[str, bytes], signature: str
) -> bool:
    """验证RSA签名

    Args:
        public_key: RSA公钥，可以是PEM格式的字符串或字节
        data: 原始数据，可以是字符串或字节
        signature: 签名值（Base64编码）

    Returns:
        签名是否有效
    """
    if isinstance(public_key, str):
        public_key = public_key.encode()
    if isinstance(data, str):
        data = data.encode()

    key = RSA.import_key(public_key)
    h = SHA256.new(data)
    try:
        pkcs1_15.new(key).verify(h, base64.b64decode(signature))
        return True
    except (ValueError, TypeError):
        return False


# 实用工具函数
def secure_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    """安全比较两个字符串或字节，防止时序攻击

    Args:
        a: 第一个字符串或字节
        b: 第二个字符串或字节

    Returns:
        两个值是否相等
    """
    if isinstance(a, str):
        a = a.encode()
    if isinstance(b, str):
        b = b.encode()

    return hmac.compare_digest(a, b)


def generate_random_string(length: int = 16) -> str:
    """生成随机字符串

    Args:
        length: 字符串长度，默认16

    Returns:
        随机字符串（十六进制）
    """
    return binascii.hexlify(get_random_bytes(length)).decode()
