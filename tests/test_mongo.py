import pytest

from jcutil.drivers.mongo import MongoClient, get_client, new_client

# 测试MongoDB连接
# 运行测试前请确保有MongoDB服务器运行在本地27017端口
TEST_MONGO_URI = "mongodb://localhost:27017/test_db"
TEST_COLLECTION = "test_collection"


@pytest.fixture(scope="module")
def client():
    client = MongoClient(TEST_MONGO_URI, "test_client")
    yield client
    # 清理测试数据
    db = client.get_database()
    db[TEST_COLLECTION].drop()
    # 关闭连接以防内存泄漏
    client.sync_client.close()
    # Don't close async_client here as it will close the event loop
    # client.async_client.close()


def test_sync_api(client):
    # 测试同步API
    # 插入测试数据
    data = {"name": "test_item", "value": 100}
    result = client.save(TEST_COLLECTION, data)
    assert "_id" in result
    assert result["name"] == "test_item"

    # 查询数据
    found = client.find_by_id(TEST_COLLECTION, result["_id"])
    assert found["name"] == "test_item"

    # 更新数据
    data["value"] = 200
    updated = client.save(TEST_COLLECTION, data)
    assert updated["value"] == 200

    # 查询所有数据
    all_items = client.find(TEST_COLLECTION, {})
    assert len(all_items) > 0

    # 删除数据
    delete_result = client.delete(TEST_COLLECTION, result["_id"])
    assert delete_result == 1


@pytest.mark.asyncio
async def test_async_api(client):
    # 测试异步API
    # 插入测试数据
    data = {"name": "async_test_item", "value": 300}
    result = await client.async_save(TEST_COLLECTION, data)
    assert "_id" in result
    assert result["name"] == "async_test_item"

    # 查询数据
    found = await client.async_find_by_id(TEST_COLLECTION, result["_id"])
    assert found["name"] == "async_test_item"

    # 更新数据
    data["value"] = 400
    updated = await client.async_save(TEST_COLLECTION, data)
    assert updated["value"] == 400

    # 查询所有数据
    all_items = await client.async_find(TEST_COLLECTION, {})
    assert len(all_items) > 0

    # 删除数据
    delete_result = await client.async_delete(TEST_COLLECTION, result["_id"])
    assert delete_result == 1


@pytest.mark.asyncio
async def test_proxy(client):
    # 测试同步代理
    proxy = client.create_proxy(TEST_COLLECTION)
    data = {"name": "proxy_test", "value": 500}
    added = proxy.add(data)
    assert added["name"] == "proxy_test"

    # 存储添加的数据ID，用于后续清理
    added_id = added["_id"]

    try:
        # 测试异步代理
        async_proxy = await client.create_async_proxy(TEST_COLLECTION)
        async_data = {"name": "async_proxy_test", "value": 600}
        async_added = await async_proxy.add(async_data)
        assert async_added["name"] == "async_proxy_test"

        # 存储异步添加的数据ID，用于后续清理
        async_added_id = async_added["_id"]

        # 查询并验证
        items = proxy.all()
        assert len(items) >= 2

        async_items = await async_proxy.all()
        assert len(async_items) >= 2

        # 清理异步测试数据
        await async_proxy.delete(async_added_id)
    finally:
        # 无论测试成功与否，都要清理同步测试数据
        proxy.delete(added_id)


def test_global_client_management():
    # 测试全局客户端管理
    new_client(TEST_MONGO_URI, "global_test")
    client = get_client("global_test")

    # 测试基本操作
    data = {"name": "global_test_item", "value": 700}
    result = client.save(TEST_COLLECTION, data)
    assert result["name"] == "global_test_item"

    # 清理
    client.delete(TEST_COLLECTION, result["_id"])
