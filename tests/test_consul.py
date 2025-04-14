import os

import pytest
from dotenv import load_dotenv

from jcutil.consul import ConfigFormat, ConsulClient, KvProperty, fetch_key, list_keys

# 从.env文件加载Consul配置
load_dotenv()


@pytest.fixture
def consul_client():
    """创建Consul客户端实例"""
    return ConsulClient()


class TestA:
    name = KvProperty("name")
    bar = KvProperty("foo", format=ConfigFormat.Yaml, cached=True)

    def desc(self):
        print("my name is:", self.name)


@pytest.fixture
def setup_test_data(consul_client):
    """设置测试数据"""
    # 准备测试数据
    consul_client.kv_put("properties/TestA/name", "FooBar")
    consul_client.kv_put(
        "properties/TestA/foo", "key: value\nlist:\n  - item1\n  - item2"
    )

    yield

    # 清理测试数据
    consul_client.kv_delete("properties/TestA/name")
    consul_client.kv_delete("properties/TestA/foo")


# 如果没有配置Consul，则跳过测试
skip_reason = "需要配置Consul服务才能运行此测试"
skip_test = os.getenv("CONSUL_HTTP_ADDR") == "127.0.0.1:8500" and not os.path.exists(
    "/usr/bin/consul"
)


@pytest.mark.skipif(skip_test, reason=skip_reason)
def test_kvp(setup_test_data):
    """测试KvProperty功能"""
    ta = TestA()
    ta.desc()
    assert ta.name == "FooBar"

    # 测试YAML格式和缓存功能
    assert isinstance(ta.bar, dict)
    assert ta.bar.get("key") == "value"
    assert isinstance(ta.bar.get("list"), list)
    assert len(ta.bar.get("list")) == 2


@pytest.mark.skipif(skip_test, reason=skip_reason)
def test_consul_client(consul_client):
    """测试ConsulClient基本功能"""
    # 测试键值操作
    test_key = "test/consul_client/key1"
    test_value = "test_value"

    try:
        # 设置键值
        result = consul_client.kv_put(test_key, test_value)
        assert result is True

        # 获取键值
        index, data = consul_client.kv_get(test_key)
        assert data["Value"].decode() == test_value

        # 列出键
        keys = list_keys("test/consul_client", client=consul_client)
        assert len(keys) > 0
        assert any(k["Key"] == test_key for k in keys)

        # 使用fetch_key获取值
        value = fetch_key(test_key, client=consul_client)
        assert value == test_value

        # 使用不同格式获取值
        json_key = "test/consul_client/json"
        json_value = '{"name": "test", "value": 123}'
        consul_client.kv_put(json_key, json_value)

        json_data = fetch_key(json_key, fmt=ConfigFormat.Json, client=consul_client)
        assert isinstance(json_data, dict)
        assert json_data["name"] == "test"
        assert json_data["value"] == 123

    finally:
        # 清理测试数据
        consul_client.kv_delete(test_key)
        consul_client.kv_delete("test/consul_client/json")
