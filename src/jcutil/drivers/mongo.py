from collections import namedtuple
from decimal import Decimal
from enum import Enum
from functools import partial
from typing import Any, Dict, List, Union
from uuid import uuid4

import motor.motor_asyncio
import pymongo
import pytz
from bson import CodecOptions, Decimal128, ObjectId
from bson.codec_options import TypeRegistry
from bson.json_util import dumps, loads
from gridfs import GridFS, GridFSBucket, GridOut
from jcramda import (
    _,
    attr,
    compose,
    curry,
    enum_name,
    first,
    getitem,
    has_attr,
    if_else,
    in_,
    is_a,
    locnow,
    not_,
    obj,
    popitem,
    when,
)
from pymongo.collection import Collection, ReturnDocument
from pymongo.database import Database
from pymongo.results import InsertOneResult, UpdateResult

from jcutil.core import get_running_loop


def fallback_encoder(value):
    return when(
        (is_a(Decimal), Decimal128),
        # (is_a(NDFrame), df_to_dict),
        (is_a(InsertOneResult), compose(obj("insertedId"), attr("inserted_id"))),
        (is_a(UpdateResult), compose(obj("upsertedId"), attr("upserted_id"))),
        (has_attr("get"), lambda o: o.get()),
        (has_attr("result"), lambda o: o.result()),
        else_=str,
    )(value)


# class NDFrameCodec(TypeCodec):
#     python_type = pd.Series
#     bson_type = dict
#
#     def transform_bson(self, value):
#         return pd.Series(value)
#
#     def transform_python(self, value):
#         return df_to_dict(value)


_type_registry = TypeRegistry(
    # type_codecs=[NDFrameCodec()],
    fallback_encoder=fallback_encoder
)


class UniqFileGridFSBucket(GridFSBucket):
    def _find_one(self, filename):
        return [*self.find({"filename": filename}).sort("uploadDate", -1).limit(1)]

    def _create_proxy(self, out: GridOut, opened=False):
        fid: ObjectId = getattr(out, "_id")
        self.delete(fid)
        create_method = (
            self.open_upload_stream_with_id
            if opened
            else self.upload_from_stream_with_id
        )
        return partial(create_method, fid)

    def open_save_file(self, filename, **kwargs):
        open_by_id = compose(
            lambda grid_out: self._create_proxy(grid_out, True)(filename, **kwargs),
            first,
        )
        return compose(
            if_else(
                not_, lambda _: self.open_upload_stream(filename, **kwargs), open_by_id
            ),
            self._find_one,
        )(filename)

    def save_file(self, filename, **kwargs):
        upload_by_id = compose(
            lambda grid_out: self._create_proxy(grid_out)(filename, **kwargs),
            first,
        )

        return compose(
            if_else(
                not_,
                lambda _: self.upload_from_stream(filename, **kwargs),
                upload_by_id,
            ),
            self._find_one,
        )(filename)


class AsyncUniqFileGridFSBucket:
    """异步版本的UniqFileGridFSBucket"""

    def __init__(self, db, bucket_name="fs"):
        self.bucket = motor.motor_asyncio.AsyncIOMotorGridFSBucket(
            db, bucket_name=bucket_name
        )

    async def _find_one(self, filename):
        cursor = (
            self.bucket.find({"filename": filename}).sort("uploadDate", -1).limit(1)
        )
        docs = []
        async for doc in cursor:
            docs.append(doc)
        return docs

    async def delete(self, file_id):
        await self.bucket.delete(file_id)

    async def open_upload_stream(self, filename, **kwargs):
        return await self.bucket.open_upload_stream(filename, **kwargs)

    async def open_upload_stream_with_id(self, file_id, filename, **kwargs):
        return await self.bucket.open_upload_stream_with_id(file_id, filename, **kwargs)

    async def upload_from_stream(self, filename, source, **kwargs):
        return await self.bucket.upload_from_stream(filename, source, **kwargs)

    async def upload_from_stream_with_id(self, file_id, filename, source, **kwargs):
        return await self.bucket.upload_from_stream_with_id(
            file_id, filename, source, **kwargs
        )

    async def _create_proxy(self, grid_out: Any, opened=False):
        fid: ObjectId = getattr(grid_out, "_id")
        await self.delete(fid)
        if opened:
            return partial(self.open_upload_stream_with_id, fid)
        else:
            return partial(self.upload_from_stream_with_id, fid)

    async def open_save_file(self, filename, **kwargs):
        docs = await self._find_one(filename)
        if not docs:
            return await self.open_upload_stream(filename, **kwargs)
        else:
            proxy = await self._create_proxy(docs[0], True)
            return proxy(filename, **kwargs)

    async def save_file(self, filename, **kwargs):
        """保存文件"""
        docs = await self._find_one(filename)
        if not docs:
            return self.upload_from_stream(filename, **kwargs)
        else:
            proxy = await self._create_proxy(docs[0])
            return proxy(filename, **kwargs)

    def __getattr__(self, name: str) -> Any:
        if name in self.bucket.__dict__:
            return getattr(self.bucket, name)
        raise AttributeError(f"AsyncUniqFileGridFSBucket has no attribute '{name}'")


class MongoClient:
    """MongoDB客户端，同时提供同步和异步接口"""

    def __init__(self, uri: str, alias: str = None):
        self.uri = uri
        self.alias = alias if alias is not None else uuid4().hex
        self.sync_client = pymongo.MongoClient(uri)

        # Use the same event loop for all async operations
        loop = get_running_loop()
        self.async_client = motor.motor_asyncio.AsyncIOMotorClient(uri, io_loop=loop)

        self.default_db_name = (
            self.sync_client.get_default_database().name
            if self.sync_client.get_default_database() is not None
            else None
        )

        # 配置编解码选项
        self.codec_options = CodecOptions(
            tz_aware=True,
            type_registry=_type_registry,
            tzinfo=pytz.timezone("Asia/Shanghai"),
        )

    def get_database(self, db_name=None) -> Database:
        """获取同步数据库对象"""
        if db_name is None:
            return self.sync_client.get_default_database()
        return self.sync_client.get_database(db_name)

    def get_async_database(self, db_name=None):
        """获取异步数据库对象"""
        # Ensure we have a valid async client
        self._ensure_valid_async_client()

        if db_name is None:
            if self.default_db_name:
                return self.async_client[self.default_db_name]
            return self.async_client.get_default_database()
        return self.async_client.get_database(db_name)

    def get_collection(
        self, collection_name: Union[str, Enum], db_name=None
    ) -> Collection:
        """获取同步集合对象"""
        db = self.get_database(db_name)
        collection_name = enum_name(collection_name)
        return db.get_collection(collection_name, codec_options=self.codec_options)

    def get_async_collection(self, collection_name: Union[str, Enum], db_name=None):
        """获取异步集合对象"""
        # Ensure we have a valid async client
        self._ensure_valid_async_client()

        db = self.get_async_database(db_name)
        collection_name = enum_name(collection_name)
        return db.get_collection(collection_name, codec_options=self.codec_options)

    def _ensure_valid_async_client(self):
        """确保异步客户端使用有效的事件循环"""
        try:
            # Try to get the loop used by the async client
            loop = self.async_client.get_io_loop()
            # Check if the loop is closed
            if loop.is_closed():
                # Create a new async client with a valid loop
                loop = get_running_loop()
                self.async_client = motor.motor_asyncio.AsyncIOMotorClient(
                    self.uri, io_loop=loop
                )
        except (RuntimeError, AttributeError):
            # If we can't get the loop or there's another issue,
            # create a new async client with a valid loop
            loop = get_running_loop()
            self.async_client = motor.motor_asyncio.AsyncIOMotorClient(
                self.uri, io_loop=loop
            )

    def get_fs(self, db_name=None) -> GridFS:
        """获取同步GridFS对象"""
        db = self.get_database(db_name)
        return GridFS(db)

    def get_fs_bucket(self, db_name=None, bucket_name="fs") -> UniqFileGridFSBucket:
        """获取同步GridFSBucket对象"""
        db = self.get_database(db_name)
        return UniqFileGridFSBucket(db, bucket_name)

    def get_async_fs_bucket(
        self, db_name=None, bucket_name="fs"
    ) -> AsyncUniqFileGridFSBucket:
        """获取异步GridFSBucket对象"""
        db = self.get_async_database(db_name)
        return AsyncUniqFileGridFSBucket(db, bucket_name)

    # 同步操作方法
    def find(
        self,
        collection: Union[Collection, str, Enum],
        query: dict,
        db_name=None,
        **kwargs,
    ):
        """同步查询多条记录"""
        if isinstance(collection, (str, Enum)):
            collection = self.get_collection(collection, db_name)
        return list(collection.find(query, **kwargs))

    def find_one(
        self,
        collection: Union[Collection, str, Enum],
        query: dict,
        db_name=None,
        **kwargs,
    ):
        """同步查询单条记录"""
        if isinstance(collection, (str, Enum)):
            collection = self.get_collection(collection, db_name)
        return collection.find_one(query, **kwargs)

    def find_by_id(
        self,
        collection: Union[Collection, str, Enum],
        _id: Union[str, ObjectId],
        db_name=None,
        **kwargs,
    ):
        """同步按ID查询"""
        if isinstance(collection, (str, Enum)):
            collection = self.get_collection(collection, db_name)
        query_id = _id if isinstance(_id, ObjectId) else ObjectId(_id)
        return collection.find_one({"_id": query_id}, **kwargs)

    def find_in_ids(
        self,
        collection: Union[Collection, str, Enum],
        ids: List[str],
        db_name=None,
        **kwargs,
    ):
        """同步按多个ID查询"""
        if isinstance(collection, (str, Enum)):
            collection = self.get_collection(collection, db_name)
        query = {"_id": {"$in": [ObjectId(n) for n in ids if n is not None]}}
        return list(collection.find(query, **kwargs))

    def find_page(
        self,
        collection: Union[Collection, str, Enum],
        query: dict,
        page_size=10,
        page_no=1,
        sort=None,
        db_name=None,
        **kwargs,
    ):
        """同步分页查询"""
        if isinstance(collection, (str, Enum)):
            collection = self.get_collection(collection, db_name)
        skip = page_size * (page_no - 1)
        if sort is None:
            sort = [("createdTime", pymongo.DESCENDING)]
        query.setdefault("logicDeleted", False)
        cursor = collection.find(query, **kwargs).sort(sort).skip(skip).limit(page_size)
        total = collection.count_documents(query)
        return {
            "content": list(cursor),
            "pageNo": page_no,
            "pageSize": page_size,
            "totalCount": total,
        }

    def save(self, collection: Union[Collection, str, Enum], data: dict, db_name=None):
        """同步保存数据（插入或更新）

        Args:
            collection: 集合名称或枚举
            data: 要保存的数据
            db_name: 数据库名称，默认使用默认数据库

        Returns:
            Dict: 包含保存后数据的字典，如果是新插入会包含_id
        """
        if isinstance(collection, (str, Enum)):
            collection = self.get_collection(collection, db_name)

        data_copy = data.copy()  # 创建副本以避免修改原始数据

        if "_id" in data_copy:
            # 从更新数据中提取_id
            doc_id = data_copy["_id"]

            # 从$set中移除_id字段，避免MongoDB报错
            set_data = data_copy.copy()
            if "_id" in set_data:
                set_data.pop("_id")

            # 构建更新操作
            update_ops = {
                "$set": set_data,
                "$currentDate": {"updateTime": True},
                "$inc": {"__v": 1},
            }

            # 更新现有文档
            result = collection.update_one({"_id": doc_id}, update_ops, upsert=True)

            if result.upserted_id:
                data_copy["_id"] = result.upserted_id

            # 获取更新后的完整文档以包含updateTime和__v
            return self.find_by_id(collection, data_copy["_id"])
        else:
            # 插入新文档
            data_copy.setdefault("createTime", locnow())
            data_copy.setdefault("__v", 0)
            data_copy.setdefault("updateTime", locnow())

            result = collection.insert_one(data_copy)
            if result.inserted_id:
                data_copy["_id"] = result.inserted_id

        return data_copy

    def replace(
        self,
        collection: Union[Collection, str, Enum],
        _id: Union[str, ObjectId],
        data: dict,
        db_name=None,
    ):
        """同步替换数据"""
        if isinstance(collection, (str, Enum)):
            collection = self.get_collection(collection, db_name)

        query_id = _id if isinstance(_id, ObjectId) else ObjectId(_id)
        old = collection.find_one({"_id": query_id})

        if "_id" in data:
            data.pop("_id")

        data.setdefault("__v", 0)
        data["__v"] += 1
        data["updateTime"] = locnow()

        result = collection.replace_one({"_id": query_id}, data, upsert=True)
        if result.modified_count or result.upserted_id:
            return self.find_by_id(collection, query_id), old

        return None, old

    def delete(
        self,
        collection: Union[Collection, str, Enum],
        _id: Union[str, ObjectId],
        db_name=None,
    ):
        """同步删除数据"""
        if isinstance(collection, (str, Enum)):
            collection = self.get_collection(collection, db_name)

        query_id = _id if isinstance(_id, ObjectId) else ObjectId(_id)
        result = collection.delete_one({"_id": query_id})
        return result.deleted_count

    # 异步操作方法
    async def async_find(
        self, collection: Union[str, Enum], query: dict, db_name=None, **kwargs
    ):
        """异步查询多条记录"""
        async_collection = self.get_async_collection(collection, db_name)
        cursor = async_collection.find(query, **kwargs)
        result = []
        async for doc in cursor:
            result.append(doc)
        return result

    async def async_find_one(
        self, collection: Union[str, Enum], query: dict, db_name=None, **kwargs
    ):
        """异步查询单条记录"""
        async_collection = self.get_async_collection(collection, db_name)
        return await async_collection.find_one(query, **kwargs)

    async def async_find_by_id(
        self,
        collection: Union[str, Enum],
        _id: Union[str, ObjectId],
        db_name=None,
        **kwargs,
    ):
        """异步按ID查询"""
        query_id = _id if isinstance(_id, ObjectId) else ObjectId(_id)
        return await self.async_find_one(
            collection, {"_id": query_id}, db_name, **kwargs
        )

    async def async_find_in_ids(
        self, collection: Union[str, Enum], ids: List[str], db_name=None, **kwargs
    ):
        """异步按多个ID查询"""
        query = {"_id": {"$in": [ObjectId(n) for n in ids if n is not None]}}
        return await self.async_find(collection, query, db_name, **kwargs)

    async def async_find_page(
        self,
        collection: Union[str, Enum],
        query: dict,
        page_size=10,
        page_no=1,
        sort=None,
        db_name=None,
        **kwargs,
    ):
        """异步分页查询"""
        async_collection = self.get_async_collection(collection, db_name)
        skip = page_size * (page_no - 1)
        if sort is None:
            sort = [("createdTime", pymongo.DESCENDING)]
        query.setdefault("logicDeleted", False)

        cursor = (
            async_collection.find(query, **kwargs)
            .sort(sort)
            .skip(skip)
            .limit(page_size)
        )
        docs = []
        async for doc in cursor:
            docs.append(doc)

        total = await async_collection.count_documents(query)
        return {
            "content": docs,
            "pageNo": page_no,
            "pageSize": page_size,
            "totalCount": total,
        }

    async def async_save(self, collection: Union[str, Enum], data: dict, db_name=None):
        """异步保存数据（插入或更新）

        Args:
            collection: 集合名称或枚举
            data: 要保存的数据
            db_name: 数据库名称，默认使用默认数据库

        Returns:
            Dict: 包含保存后数据的字典，如果是新插入会包含_id
        """
        async_collection = self.get_async_collection(collection, db_name)
        data_copy = data.copy()  # 创建副本以避免修改原始数据

        if "_id" in data_copy:
            # 从更新数据中提取_id
            doc_id = data_copy["_id"]

            # 从$set中移除_id字段，避免MongoDB报错
            set_data = data_copy.copy()
            if "_id" in set_data:
                set_data.pop("_id")

            # 构建更新操作
            update_ops = {
                "$set": set_data,
                "$currentDate": {"updateTime": True},
                "$inc": {"__v": 1},
            }

            # 更新现有文档
            result = await async_collection.update_one(
                {"_id": doc_id}, update_ops, upsert=True
            )

            # motor的UpdateResult直接提供upserted_id属性
            if result.upserted_id:
                data_copy["_id"] = result.upserted_id

            # 获取更新后的完整文档以包含updateTime和__v
            return await self.async_find_by_id(collection, data_copy["_id"], db_name)
        else:
            # 插入新文档
            data_copy.setdefault("createTime", locnow())
            data_copy.setdefault("__v", 0)
            data_copy.setdefault("updateTime", locnow())

            # motor的InsertOneResult直接提供inserted_id属性
            result = await async_collection.insert_one(data_copy)
            if result.inserted_id:
                data_copy["_id"] = result.inserted_id

        return data_copy

    async def async_replace(
        self,
        collection: Union[str, Enum],
        _id: Union[str, ObjectId],
        data: dict,
        db_name=None,
    ):
        """异步替换数据

        Args:
            collection: 集合名称或枚举
            _id: 文档ID
            data: 替换的新数据
            db_name: 数据库名称，默认使用默认数据库

        Returns:
            Tuple[Dict, Dict]: 包含新文档和旧文档的元组，如果操作失败返回(None, old)
        """
        async_collection = self.get_async_collection(collection, db_name)
        data_copy = data.copy()  # 创建副本以避免修改原始数据

        query_id = _id if isinstance(_id, ObjectId) else ObjectId(_id)
        old = await async_collection.find_one({"_id": query_id})

        if "_id" in data_copy:
            data_copy.pop("_id")

        data_copy.setdefault("__v", 0)
        data_copy["__v"] += 1
        data_copy["updateTime"] = locnow()

        try:
            result = await async_collection.replace_one(
                {"_id": query_id}, data_copy, upsert=True
            )

            if result.modified_count > 0 or result.upserted_id:
                # 获取更新后的完整文档
                new_doc = await self.async_find_by_id(collection, query_id, db_name)
                return new_doc, old

            # 如果没有修改文档（可能数据相同），但文档存在
            if old:
                return old, old

            return None, old
        except Exception as e:
            # 记录异常，但不抛出，保持与同步API一致的行为
            print(f"Error in async_replace: {e}")
            return None, old

    async def async_delete(
        self, collection: Union[str, Enum], _id: Union[str, ObjectId], db_name=None
    ):
        """异步删除数据

        Args:
            collection: 集合名称或枚举
            _id: 要删除的文档ID
            db_name: 数据库名称，默认使用默认数据库

        Returns:
            int: 被删除的文档数量
        """
        async_collection = self.get_async_collection(collection, db_name)

        query_id = _id if isinstance(_id, ObjectId) else ObjectId(_id)
        try:
            result = await async_collection.delete_one({"_id": query_id})
            return result.deleted_count
        except Exception as e:
            print(f"Error in async_delete: {e}")
            return 0

    def create_proxy(self, collection_name: str, db_name=None):
        """创建集合代理对象，提供简化的操作方法"""
        proxy_obj = namedtuple(
            f"{self.alias}_{collection_name}", "all,find,add,update,replace,delete"
        )

        def all(**kwargs):
            return self.find(collection_name, {}, db_name, **kwargs)

        def find(query: dict, **kwargs):
            return self.find(collection_name, query, db_name, **kwargs)

        def add(data):
            data.setdefault("createTime", locnow())
            return self.save(collection_name, data, db_name)

        def update(_id, data, **kwargs):
            current = self.find_by_id(collection_name, _id, db_name)
            if current:
                data_to_update = current.copy()
                data_to_update.update(data)
                data_to_update["_id"] = current["_id"]
                result = self.save(collection_name, data_to_update, db_name)
                return result
            return None

        def replace(_id, data, **kwargs):
            new_doc, old = self.replace(collection_name, _id, data, db_name)
            return new_doc

        def delete(_id):
            return self.delete(collection_name, _id, db_name)

        return proxy_obj(all, find, add, update, replace, delete)

    def create_async_proxy(self, collection_name: str, db_name=None):
        """创建异步集合代理对象，提供简化的异步操作方法"""
        proxy_obj = namedtuple(
            f"{self.alias}_{collection_name}_async",
            "all,find,add,update,replace,delete",
        )

        async def all(**kwargs):
            return await self.async_find(collection_name, {}, db_name, **kwargs)

        async def find(query: dict, **kwargs):
            return await self.async_find(collection_name, query, db_name, **kwargs)

        async def add(data):
            data.setdefault("createTime", locnow())
            return await self.async_save(collection_name, data, db_name)

        async def update(_id, data, **kwargs):
            """更新文档，保留原始数据的其他字段

            Args:
                _id: 文档ID
                data: 要更新的数据字段

            Returns:
                Dict: 更新后的完整文档
            """
            current = await self.async_find_by_id(collection_name, _id, db_name)
            if current:
                data_to_update = current.copy()
                data_to_update.update(data)
                data_to_update["_id"] = current["_id"]
                return await self.async_save(collection_name, data_to_update, db_name)
            return None

        async def replace(_id, data, **kwargs):
            """完全替换文档的内容

            Args:
                _id: 文档ID
                data: 新的完整文档内容

            Returns:
                Dict: 替换后的新文档
            """
            new_doc, old = await self.async_replace(collection_name, _id, data, db_name)
            return new_doc

        async def delete(_id):
            """删除文档

            Args:
                _id: 要删除的文档ID

            Returns:
                int: 删除的文档数量
            """
            return await self.async_delete(collection_name, _id, db_name)

        return proxy_obj(all, find, add, update, replace, delete)

    def drop_collection(self, collection_name: str, db_name=None):
        """删除集合"""
        collection = self.get_collection(collection_name, db_name)
        collection.drop()

    async def async_drop_collection(self, collection_name: str, db_name=None):
        """异步删除集合"""
        async_collection = self.get_async_collection(collection_name, db_name)
        await async_collection.drop()

    async def async_drop_database(self, db_name=None):
        """异步删除数据库"""
        async_db = self.get_async_database(db_name)
        await async_db.drop()

    def drop_database(self, db_name=None):
        """删除数据库"""
        db = self.get_database(db_name)
        db.drop()

    def close(self):
        """关闭客户端"""
        self.sync_client.close()
        self.async_client.close()

    def __str__(self):
        return f"MongoClient(uri='{self.uri}', alias='{self.alias}')"

    def __repr__(self):
        return self.__str__()


# 全局客户端实例管理
__clients: Dict[str, MongoClient] = dict()


def exists(name: str):
    """检查指定名称的客户端是否存在"""
    return name in __clients


def new_client(uri: str, alias: str = None) -> MongoClient:
    """创建新的MongoDB客户端实例"""
    db_name = alias if alias is not None else uuid4().hex
    client = MongoClient(uri, db_name)
    __clients[db_name] = client
    return client


def get_client(alias: str = None) -> MongoClient:
    """获取指定别名的客户端实例"""
    if alias is None:
        alias = first(list(__clients.keys()))
    return __clients[alias]


def load(conf: dict):
    """从配置加载多个MongoDB连接"""
    if conf and len(conf) > 0:
        for key in conf:
            new_client(conf[key], key)
            # print(f'mongodb: [{key}] connected')


def instances():
    """获取所有客户端实例名称"""
    return list(__clients.keys())


# 兼容旧API的辅助函数
def conn(key=None) -> MongoClient:
    """获取客户端连接（兼容旧API）"""
    return get_client(key)


def get_collection(tag, collection: Union[str, Enum], db_name=None):
    """获取集合对象（兼容旧API）"""
    client = get_client(tag)
    return client.get_collection(collection, db_name)


def fs_client(key=None) -> GridFS:
    """获取GridFS对象（兼容旧API）"""
    client = get_client(key)
    return client.get_fs()


def fs_bucket(db_name, bucket_name="fs") -> UniqFileGridFSBucket:
    """获取GridFSBucket对象（兼容旧API）"""
    client = get_client(db_name)
    return client.get_fs_bucket(bucket_name=bucket_name)


# 兼容旧API的数据操作函数
@curry
def find(collection, query):
    """查询函数（兼容旧API）"""
    assert is_a(Collection, collection)
    return tuple(collection.find(query))


@curry
def find_one(collection, query):
    """查询单条记录（兼容旧API）"""
    assert is_a(Collection, collection)
    return collection.find_one(query)


@curry
def find_by(collection, key, value):
    """按字段查询（兼容旧API）"""
    return collection.find(filter={key: value})


@curry
def save(collection, data):
    """保存数据（兼容旧API）"""
    data_copy = data.copy()  # 创建副本以避免修改原始数据

    if "_id" in data_copy:
        doc_id = data_copy["_id"]

        # 从$set中移除_id字段，避免MongoDB报错
        set_data = data_copy.copy()
        if "_id" in set_data:
            set_data.pop("_id")

        # 构建更新操作，包含currentDate和inc
        update_ops = {
            "$set": set_data,
            "$currentDate": {"updateTime": True},
            "$inc": {"__v": 1},
        }

        r = collection.update_one({"_id": doc_id}, update_ops, upsert=True)

        if hasattr(r, "upserted_id") and r.upserted_id:
            data_copy["_id"] = r.upserted_id

        # 获取完整更新后的文档
        updated = collection.find_one({"_id": doc_id if doc_id else data_copy["_id"]})
        if updated:
            return updated
    else:
        # 添加createTime、updateTime和初始版本字段
        data_copy.setdefault("createTime", locnow())
        data_copy.setdefault("updateTime", locnow())
        data_copy.setdefault("__v", 0)

        r = collection.insert_one(data_copy)
        if hasattr(r, "inserted_id"):
            data_copy["_id"] = r.inserted_id

    return data_copy


@curry
def replace_one(collection, data):
    """替换数据（兼容旧API）"""
    assert "_id" in data, "must include _id field in data."
    query = {"_id": data["_id"]}
    old = collection.find_one(query)
    collection.replace_one(query, data, upsert=True)
    return data, old


def find_page(collection, query, page_size=10, page_no=1, sort=None):
    """分页查询（兼容旧API）"""
    assert is_a(Collection, collection)
    skip = page_size * (page_no - 1)
    if sort is None:
        sort = [("createdTime", pymongo.DESCENDING)]
    query["logicDeleted"] = False
    cursor = collection.find(query).sort(sort).skip(skip).limit(page_size)
    total = collection.count_documents(query)
    return {
        "content": list(cursor),
        "pageNo": page_no,
        "pageSize": page_size,
        "totalCount": total,
    }


def mdb_proxy(tag, collection_name):
    """创建集合代理（兼容旧API）"""
    client = get_client(tag)
    return client.create_proxy(collection_name)


# 工具函数
to_json = dumps
from_json = loads


class BaseModel:
    """基础模型类"""

    def __init__(self, db_or_client, collection_name):
        if isinstance(db_or_client, MongoClient):
            self.client = db_or_client
            self.collection = db_or_client.get_collection(collection_name)
        else:
            self.client = None
            self.collection = db_or_client.get_collection(collection_name)

    def find_by_id(self, _id: Union[str, ObjectId]):
        query_id = _id if isinstance(_id, ObjectId) else ObjectId(_id)
        return self.collection.find_one(filter={"_id": query_id})

    def find_in_ids(self, ids: List[str], *args):
        query = {"_id": {"$in": [ObjectId(n) for n in ids if n is not None]}}
        return list(self.collection.find(query, *args))

    def _save(self, sepc_field: str = None, **kwargs):
        assert (
            "_id" in kwargs or not not_(sepc_field) and sepc_field in kwargs
        ), f"must had [_id] field or [{sepc_field}] field"
        query = if_else(
            in_(_, "_id"),
            compose(obj("_id"), popitem("_id")),
            compose(obj(sepc_field), getitem(sepc_field)),
        )
        return self.collection.find_one_and_update(
            filter=query(kwargs),
            update={"$set": kwargs},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
