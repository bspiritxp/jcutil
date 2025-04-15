#!/usr/bin/env python3
"""
密码哈希和加密工具模块
提供基于 passlib 的密码安全处理工具
"""

import base64
import os
import random
import string
from enum import Enum
from typing import Optional, Tuple, Union

# Import the secure_compare function from our existing crypto module

try:
    from passlib.context import CryptContext
    from passlib.exc import PasswordValueError
    from passlib.hash import argon2, bcrypt, pbkdf2_sha256, sha512_crypt

    PASSLIB_AVAILABLE = True
except ImportError:
    PASSLIB_AVAILABLE = False

# 默认密码哈希上下文，包含多种算法以支持历史密码和升级
DEFAULT_CONTEXT = (
    CryptContext(
        schemes=["argon2", "bcrypt", "pbkdf2_sha256", "sha512_crypt"],
        default="argon2",
        # 当验证旧模式的密码时自动升级到新模式
        deprecated=["sha512_crypt"],
        # argon2 配置
        argon2__rounds=4,
        argon2__memory_cost=65536,
        # bcrypt 配置
        bcrypt__rounds=12,
        # pbkdf2_sha256 配置
        pbkdf2_sha256__rounds=150000,
    )
    if PASSLIB_AVAILABLE
    else None
)


class HashScheme(Enum):
    """支持的哈希算法"""

    ARGON2 = "argon2"
    BCRYPT = "bcrypt"
    PBKDF2 = "pbkdf2_sha256"
    SHA512 = "sha512_crypt"


def _require_passlib():
    """Verify that passlib is installed"""
    if not PASSLIB_AVAILABLE:
        raise ImportError(
            "Password hashing features require the 'passlib' library. "
            "Please install it with 'pip install passlib bcrypt argon2-cffi'"
        )


def password_hash(
    password: str, scheme: Union[str, HashScheme] = None, **kwargs
) -> str:
    """使用选定的哈希算法创建密码哈希

    Args:
        password: 原始密码
        scheme: 使用的哈希算法，默认为 argon2
        **kwargs: 额外的参数，用于特定哈希算法的配置

    Returns:
        格式化的密码哈希字符串

    Raises:
        ImportError: 如果找不到 passlib 库
    """
    _require_passlib()

    # 处理空值
    if password is None:
        raise ValueError("密码不能为空")

    # 处理枚举值
    if isinstance(scheme, HashScheme):
        scheme = scheme.value

    # 如果指定了特定算法和轮数
    if scheme and kwargs:
        if scheme == HashScheme.ARGON2.value:
            # Default settings for Argon2 (if not provided in kwargs)
            time_cost = kwargs.get("time_cost", 3)
            memory_cost = kwargs.get("memory_cost", 65536)
            parallelism = kwargs.get("parallelism", 4)
            return argon2.using(
                time_cost=time_cost, memory_cost=memory_cost, parallelism=parallelism
            ).hash(password)
        elif scheme == HashScheme.BCRYPT.value:
            rounds = kwargs.get("rounds", 12)
            return bcrypt.using(rounds=rounds).hash(password)
        elif scheme == HashScheme.PBKDF2.value:
            rounds = kwargs.get("rounds", 150000)
            return pbkdf2_sha256.using(rounds=rounds).hash(password)
        elif scheme == HashScheme.SHA512.value:
            rounds = kwargs.get("rounds", 100000)
            return sha512_crypt.using(rounds=rounds).hash(password)
        else:
            raise ValueError(f"不支持的哈希算法: {scheme}")

    # 使用默认上下文
    if scheme:
        return DEFAULT_CONTEXT.handler(scheme).hash(password)
    else:
        return DEFAULT_CONTEXT.hash(password)


def password_verify(password: str, hash_str: str) -> Tuple[bool, Optional[str]]:
    """验证密码与哈希是否匹配，并在需要时返回升级后的哈希

    Args:
        password: 原始密码
        hash_str: 存储的密码哈希

    Returns:
        (是否匹配, 升级后的哈希或 None)

    Raises:
        ImportError: 如果找不到 passlib 库
    """
    _require_passlib()

    try:
        # Identify which hash scheme was used
        if hash_str.startswith("$argon2"):
            hasher = argon2
        elif hash_str.startswith("$2"):  # BCrypt
            hasher = bcrypt
        elif hash_str.startswith("$pbkdf2-sha256"):
            hasher = pbkdf2_sha256
        elif hash_str.startswith("$6$"):  # SHA512
            hasher = sha512_crypt
        else:
            raise ValueError(f"Unrecognized password hash format: {hash_str[:10]}...")

        # Verify the password
        is_valid = hasher.verify(password, hash_str)

        # Check if hash needs upgrading (returns new hash or None)
        new_hash = (
            hasher.hash(password)
            if is_valid and hasher.needs_update(hash_str)
            else None
        )

        # If still using an older scheme and password is valid, upgrade to Argon2
        if is_valid and not hash_str.startswith("$argon2") and not new_hash:
            new_hash = password_hash(password, HashScheme.ARGON2)

        return is_valid, new_hash

    except (ValueError, PasswordValueError) as e:
        # Handle any errors during verification
        print(f"Password verification error: {e}")
        return False, None


def generate_token(length: int = 32, url_safe: bool = True) -> str:
    """生成高熵随机令牌

    Args:
        length: 令牌字节长度
        url_safe: 是否生成 URL 安全的 base64 令牌

    Returns:
        随机令牌字符串
    """
    if length < 16:
        raise ValueError("Token length should be at least 16 bytes for security")

    token_bytes = os.urandom(length)

    if url_safe:
        return base64.urlsafe_b64encode(token_bytes).decode("utf-8").rstrip("=")
    else:
        return base64.b64encode(token_bytes).decode("utf-8")


def generate_password(length: int = 12, complexity: int = 4) -> str:
    """生成随机安全密码

    Args:
        length: 密码长度
        complexity: 复杂度级别 (1-4)，决定使用的字符集

    Returns:
        随机密码字符串
    """
    if length < 8:
        raise ValueError("Password length should be at least 8 characters")

    if complexity < 1 or complexity > 4:
        raise ValueError("Complexity must be between 1 and 4")

    char_sets = [
        string.ascii_lowercase,  # Level 1: lowercase
        string.digits,  # Level 2: add digits
        string.ascii_uppercase,  # Level 3: add uppercase
        "!@#$%^&*()-_=+[]{}|;:,.<>?/~",  # Level 4: add special
    ]

    # Add character sets based on complexity
    available_chars = ""
    for i in range(complexity):
        available_chars += char_sets[i]

    # Ensure at least one character from each set is included
    password = []
    for i in range(complexity):
        password.append(random.choice(char_sets[i]))

    # Fill the rest of the password with random characters
    for _ in range(length - complexity):
        password.append(random.choice(available_chars))

    # Shuffle the password to avoid predictable pattern
    random.shuffle(password)

    return "".join(password)


# 代码测试部分
if __name__ == "__main__":
    pwd = "my_secure_password"

    # 测试默认哈希
    hash1 = password_hash(pwd)
    print(f"默认哈希: {hash1}")

    # 测试 bcrypt
    hash2 = password_hash(pwd, HashScheme.BCRYPT)
    print(f"BCrypt哈希: {hash2}")

    # 测试验证
    is_valid, new_hash = password_verify(pwd, hash1)
    print(f"验证结果: {is_valid}, 升级后的哈希: {new_hash or '无需升级'}")

    # 测试令牌生成
    token = generate_token()
    print(f"随机令牌: {token}")

    # 测试密码生成
    random_pwd = generate_password(length=12, complexity=4)
    print(f"随机密码: {random_pwd}")
