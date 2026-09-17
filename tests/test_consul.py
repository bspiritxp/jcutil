import os

import pytest
from dotenv import load_dotenv

from jcutil.consul import (
    AsyncConsulClient,
    ConfigFormat,
    ConsulClient,
    KvProperty,
    fetch_key,
    list_keys,
)

# 从.env文件加载Consul配置
load_dotenv()


@pytest.fixture
def consul_client():
    """创建Consul客户端实例"""
    try:
        client = ConsulClient()
        # 测试连接是否有效
        client.kv_get("test")
        return client
    except Exception as e:
        pytest.skip(f"无法连接到Consul: {e}")


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



class MemoryConsulClient:
    def __init__(self, values=None):
        self.values = values or {}
        self.calls = []

    def kv_get(self, key, **kwargs):
        self.calls.append(("kv_get", key, kwargs))
        value = self.values[key]
        if isinstance(value, str):
            value = value.encode()
        return 1, {"Key": key, "Value": value}



def test_consul_client_no_args_preserves_upstream_env(monkeypatch):
    monkeypatch.setenv("CONSUL_HTTP_ADDR", "10.1.2.3:18500")
    monkeypatch.setenv("CONSUL_HTTP_TOKEN", "env-token")

    client = ConsulClient()

    assert client.client.http.host == "10.1.2.3"
    assert client.client.http.port == 18500
    assert client.client.token == "env-token"
    client.close()


def test_consul_client_explicit_options_with_host_none(monkeypatch):
    monkeypatch.setenv("CONSUL_HTTP_ADDR", "10.1.2.3:18500")
    monkeypatch.setenv("CONSUL_HTTP_TOKEN", "env-token")

    client = ConsulClient(
        host=None,
        port=19500,
        token="explicit-token",
        scheme="https",
        dc="dc-test",
        verify=False,
    )

    assert client.client.http.host == "127.0.0.1"
    assert client.client.http.port == 19500
    assert client.client.http.scheme == "https"
    assert client.client.http.verify is False
    assert client.client.dc == "dc-test"
    assert client.client.token == "explicit-token"
    client.close()



def test_fetch_key_numeric_config_formats():
    client = MemoryConsulClient(
        {
            "int": b"42",
            "float": b"3.5",
            "number": b"2.75",
        }
    )

    assert fetch_key("int", fmt=ConfigFormat.Int, client=client) == 42
    assert fetch_key("float", fmt=ConfigFormat.Float, client=client) == 3.5
    from decimal import Decimal

    assert fetch_key("number", fmt=ConfigFormat.Number, client=client) == Decimal("2.75")


def test_kv_property_descriptor_and_alias_cache(monkeypatch):
    values = {"properties/AliasExample/foo": "cached-value"}
    client = MemoryConsulClient(values)
    monkeypatch.setattr("jcutil.consul._default_client", client)

    class AliasExample:
        bar = KvProperty("foo", cached=True)

    assert isinstance(AliasExample.bar, KvProperty)
    obj = AliasExample()

    assert obj.bar == "cached-value"
    values["properties/AliasExample/foo"] = "new-value"
    assert obj.bar == "cached-value"
    assert AliasExample().bar == "new-value"


def test_token_only_preserves_environment_address(monkeypatch):
    monkeypatch.setenv("CONSUL_HTTP_ADDR", "10.1.2.3:18500")
    with ConsulClient(token="explicit-token") as client:
        assert client.client.http.host == "10.1.2.3"
        assert client.client.http.port == 18500
        assert client.client.token == "explicit-token"


@pytest.mark.asyncio
async def test_async_consul_kv_roundtrip(consul_client):
    pytest.importorskip("aiohttp")
    from uuid import uuid4

    key = f"test/jcutil/async/{uuid4().hex}"
    async with AsyncConsulClient() as client:
        try:
            assert await client.kv_put(key, "async-value") is True
            _, record = await client.kv_get(key)
            assert record["Value"] == b"async-value"
            _, records = await client.kv_list(key)
            assert [item["Key"] for item in records] == [key]
            assert await client.kv_delete(key) is True
            _, record = await client.kv_get(key)
            assert record is None
        finally:
            await client.kv_delete(key)


def test_session_default_ttl_preserves_legacy_api(consul_client):
    from jcutil.consul import create_session

    session_id = create_session("jcutil-ttl-test", client=consul_client, checks=[])
    try:
        _, sessions = consul_client.client.session.info(session_id)
        assert sessions["TTL"] == "30s"
        assert consul_client.session_renew(session_id) is True
    finally:
        consul_client.session_destroy(session_id)


@pytest.mark.asyncio
async def test_async_session_accepts_legacy_ttl(consul_client):
    pytest.importorskip("aiohttp")
    async with AsyncConsulClient() as client:
        session_id = await client.session_create("jcutil-async-ttl-test", ttl="30s", checks=[])
        try:
            _, sessions = await client.client.session.info(session_id)
            assert sessions["TTL"] == "30s"
            assert await client.session_renew(session_id) is True
        finally:
            await client.session_destroy(session_id)
