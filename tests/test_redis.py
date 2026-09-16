import asyncio
import logging
import os

import pytest
import pytest_asyncio
import yaml

from jcutil.drivers.redis import Lock, SpinLock, get_client, new_client


@pytest_asyncio.fixture
async def setup_redis():
    """Yield an async Redis client or skip when the configured service is unavailable."""
    redis_uri = "redis://127.0.0.1:6379"
    if os.path.exists("tests/config.yaml"):
        with open("tests/config.yaml", "r") as file:
            conf = yaml.safe_load(file)
            redis_uri = conf.get("redis", {}).get("test", redis_uri)

    try:
        await new_client(redis_uri, "test")
        client = get_client("test")
        assert client is not None
        await client.ping()
    except Exception as error:
        logging.error("Failed to connect to Redis: %s", error)
        pytest.skip("Redis connection failed")

    try:
        yield client
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_redis_basic_operations(setup_redis):
    """测试Redis基本操作"""
    # 获取连接
    client = setup_redis

    # 测试设置和获取值
    test_key = "test_key"
    test_value = "test_value"

    # 确保键不存在
    await client.delete(test_key)

    # 测试设置值
    assert await client.set(test_key, test_value) is True

    # 测试获取值
    result = await client.get(test_key)
    assert result.decode("utf-8") == test_value

    # 测试键存在
    assert await client.exists(test_key) == 1

    # 测试删除键
    assert await client.delete(test_key) == 1

    # 确认键已删除
    assert await client.exists(test_key) == 0


@pytest.mark.asyncio
async def test_redis_expire(setup_redis):
    """测试Redis过期时间设置"""
    client = setup_redis
    test_key = "expire_key"

    # 设置带过期时间的键
    await client.set(test_key, "temporary", ex=2)

    # 键应该存在
    assert await client.exists(test_key) == 1

    # 等待过期
    await asyncio.sleep(3)

    # 键应该已过期
    assert await client.exists(test_key) == 0


@pytest.mark.asyncio
async def test_spin_lock(setup_redis):
    """测试SpinLock功能"""
    lock_key = "test_lock"

    # 测试自动获取和释放锁
    async with SpinLock("test", lock_key):
        # 在锁内执行操作
        await asyncio.sleep(1)
        logging.info("holding lock for 1 second")

    # 测试手动锁操作
    lock = Lock("test", lock_key)
    acquired = await lock.acquire()
    assert acquired is True
    assert lock.locked is True

    # 尝试获取已被锁定的锁
    lock2 = Lock("test", lock_key)
    acquired2 = await lock2.acquire(blocking=False)
    assert acquired2 is False

    # 释放锁
    await lock.release()
    assert lock.locked is False

    # 现在应该能获取锁了
    acquired2 = await lock2.acquire(blocking=False)
    assert acquired2 is True

    # 释放第二个锁
    await lock2.release()
