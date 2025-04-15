import os

import pytest
import yaml
from dotenv import load_dotenv

from jcutil.drivers.mongo import MongoClient

load_dotenv()

# 测试MongoDB连接
# 首先尝试从配置文件加载
config_mongo_uri = None
if os.path.exists("tests/config.yaml"):
    try:
        with open("tests/config.yaml", "r") as f:
            config = yaml.safe_load(f)
            if "mongo" in config and "test" in config["mongo"]:
                config_mongo_uri = config["mongo"]["test"]
    except Exception as e:
        print(f"读取配置文件失败: {e}")

# 如果配置文件中没有，则从环境变量读取，如果环境变量中也没有，则使用默认连接
TEST_MONGO_URI = (
    os.getenv("MONGO_URI") or config_mongo_uri or "mongodb://localhost:27017/test"
)
TEST_COLLECTION = "test_collection"  # 使用特定的测试集合名称，避免冲突


@pytest.fixture(scope="module")
def client():
    """准备测试客户端"""
    try:
        client = MongoClient(TEST_MONGO_URI, "test_client")
        # 测试连接是否有效
        db = client.get_database()
        db.list_collection_names()  # 这会触发连接验证
        print(f"成功连接到MongoDB: {TEST_MONGO_URI}")
    except Exception as e:
        print(f"连接MongoDB失败: {e}")
        pytest.skip(f"无法连接到MongoDB: {e}")
        return None

    yield client

    try:
        # 清理测试数据
        db = client.get_database()
        if TEST_COLLECTION in db.list_collection_names():
            db[TEST_COLLECTION].drop()
        # 关闭连接以防内存泄漏
        client.sync_client.close()
    except Exception as e:
        print(f"清理测试数据失败：{e}")


def test_sync_api(client):
    """测试同步API"""
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
    """测试异步API"""
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
    """测试代理功能"""
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
