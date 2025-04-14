"""
测试jcutil core模块的功能

此测试文件验证jcutil.core模块中的核心功能，包括JSON处理、对象序列化和异步操作等。
"""

import tempfile
from pathlib import Path

import pytest

from jcutil.core import (
    async_run,
    from_json_file,
    map_async,
    obj_dumps,
    obj_loads,
    to_json,
    to_json_file,
    to_obj,
)


def test_json_serialization():
    """测试JSON序列化功能"""
    # 测试基本数据类型
    data = {
        "string": "hello",
        "number": 42,
        "boolean": True,
        "null": None,
        "array": [1, 2, 3],
        "object": {"a": 1, "b": 2},
    }

    # 测试to_json
    json_str = to_json(data)
    assert isinstance(json_str, str)

    # 测试反序列化
    obj = to_obj(json_str)
    assert obj["string"] == "hello"
    assert obj["number"] == 42

    # 测试特殊处理器
    complex_data = {
        "date": "2023-01-01",
        "camelCaseKey": "value",
    }
    json_str = to_json(complex_data)
    assert "camelCaseKey" in json_str


def test_json_file_operations():
    """测试JSON文件操作功能"""
    data = {"test": "file_operation", "value": 123}

    # 创建临时文件
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as temp_file:
        temp_path = temp_file.name

    try:
        # 测试to_json_file
        to_json_file(data, temp_path)

        # 测试from_json_file
        loaded_data = from_json_file(temp_path)
        assert loaded_data["test"] == "file_operation"
        assert loaded_data["value"] == 123
    finally:
        # 清理临时文件
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_async_functions():
    """测试异步功能"""

    def sync_func(x):
        return x * 2

    # 测试async_run
    result = await async_run(sync_func, 21)
    assert result == 42

    # 测试带上下文的async_run
    result_with_context = await async_run(sync_func, 21, with_context=True)
    assert result_with_context == 42


def test_map_async():
    """测试并行映射功能"""
    data = [1, 2, 3, 4, 5]

    def multiply_by_2(x):
        return x * 2

    # 测试map_async
    results = map_async(multiply_by_2, data)
    assert sorted(results) == [2, 4, 6, 8, 10]


def test_obj_serialization():
    """测试对象序列化功能"""
    # 创建一个复杂对象
    obj = {"complex": [1, 2, 3], "nested": {"a": 1, "b": 2}}

    # 测试序列化和反序列化
    serialized = obj_dumps(obj)
    assert isinstance(serialized, bytes)

    deserialized = obj_loads(serialized)
    assert deserialized["complex"] == [1, 2, 3]
    assert deserialized["nested"]["a"] == 1
