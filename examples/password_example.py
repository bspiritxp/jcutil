#!/usr/bin/env python3
"""
密码哈希功能演示
展示如何使用 jcutil 的密码哈希、验证和安全功能
"""

from jcutil.crypto_utils import (
    HashScheme,
    generate_password,
    generate_token,
    password_hash,
    password_verify,
    secure_compare,
)


def main():
    """演示密码哈希和验证功能"""
    print("= 密码哈希功能演示 =\n")

    # 1. 创建测试密码
    print("生成随机安全密码:")
    auto_password = generate_password(length=12, complexity=4)
    print(f"  自动生成的密码: {auto_password}\n")

    # 也可以使用用户输入的密码
    user_password = "MySecurePassword123!"
    print(f"  用户输入的密码: {user_password}\n")

    # 2. 使用不同算法创建密码哈希
    print("创建密码哈希:")
    # 默认哈希 (Argon2)
    default_hash = password_hash(user_password)
    print(f"  默认哈希 (Argon2): {default_hash}")

    # BCrypt 哈希
    bcrypt_hash = password_hash(user_password, HashScheme.BCRYPT)
    print(f"  BCrypt 哈希: {bcrypt_hash}")

    # PBKDF2 哈希
    pbkdf2_hash = password_hash(user_password, HashScheme.PBKDF2, rounds=160000)
    print(f"  PBKDF2 哈希 (160k轮): {pbkdf2_hash}")

    # SHA512 哈希 (已废弃但仍支持验证)
    sha512_hash = password_hash(user_password, HashScheme.SHA512)
    print(f"  SHA512 哈希 (已废弃): {sha512_hash}\n")

    # 3. 验证密码
    print("验证密码:")
    # 正确密码验证
    is_valid, upgraded_hash = password_verify(user_password, default_hash)
    print(f"  原始密码验证: {is_valid}")
    if upgraded_hash:
        print(f"  升级后的哈希: {upgraded_hash}")

    # 错误密码验证
    wrong_password = "WrongPassword123"
    is_valid, _ = password_verify(wrong_password, default_hash)
    print(f"  错误密码验证: {is_valid}\n")

    # 4. 安全令牌生成
    print("安全令牌生成:")
    # URL 安全的令牌
    url_safe_token = generate_token(length=24, url_safe=True)
    print(f"  URL安全令牌: {url_safe_token}")

    # 标准 Base64 令牌
    std_token = generate_token(length=24, url_safe=False)
    print(f"  标准Base64令牌: {std_token}\n")

    # 5. 安全字符串比较
    print("安全字符串比较 (防止时序攻击):")
    token_a = "a1b2c3d4e5f6"
    token_b = "a1b2c3d4e5f6"
    token_c = "x1y2z3d4e5f6"

    print(f"  Token A: {token_a}")
    print(f"  Token B: {token_b}")
    print(f"  Token C: {token_c}")

    print(f"  A == B: {secure_compare(token_a, token_b)}")
    print(f"  A == C: {secure_compare(token_a, token_c)}")


if __name__ == "__main__":
    try:
        main()
    except ImportError as e:
        print(f"错误: {e}")
        print("\n请安装所需的库: pip install passlib")
