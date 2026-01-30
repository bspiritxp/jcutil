# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

jcutil 是一个通用Python实用工具库,提供控制台彩色输出、数据库驱动、加密工具、网络IO等功能。作者: Jochen.He

## 构建和测试

### 代码检查和格式化

使用 Ruff 进行代码质量检查:

```bash
# 自动检查并修复代码风格问题
uvx ruff check . --fix

# 检查未修复的问题
uvx ruff check .

# 使用便捷脚本(推荐)
./scripts/lint.sh        # Linux/macOS
.\scripts\lint.ps1       # Windows
```

Ruff 配置要点:
- 行长度限制: 100字符
- 使用单引号
- 忽略 E501 (行过长警告)
- 目标Python版本: 3.8+

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_chalk.py

# 运行特定测试函数
pytest tests/test_core.py::test_function_name

# 显示详细输出
pytest -v

# 显示所有输出(包括通过的测试)
pytest -ra -v
```

pytest 配置:
- 测试目录: `tests/`
- 测试文件: `test_*.py`
- 异步模式: strict (使用 pytest-asyncio)

### 版本管理

版本号使用 hatch 动态管理,在 `src/jcutil/__init__.py` 中维护 `__version__` 变量。

## 代码架构

### 核心模块结构

```
src/jcutil/
├── chalk/              # 控制台彩色输出工具
├── core/               # 核心工具函数集合
│   ├── jsonfy.py      # JSON序列化工具(SafeJsonEncoder/Decoder)
│   └── pdtools.py     # Pandas数据处理工具
├── drivers/            # 数据库和消息队列驱动
│   ├── db.py          # 关系型数据库(SQLAlchemy)
│   ├── mongo.py       # MongoDB(pymongo + motor)
│   ├── redis.py       # Redis
│   └── mq.py          # Kafka消息队列
├── dba/                # 数据库管理工具
├── server/             # 服务器配置和环境变量
├── consul.py           # Consul服务发现与配置
├── crypto.py           # 加密解密工具
├── data.py             # 函数结果缓存工具
├── netio.py            # 异步网络请求工具
└── schedjob.py         # 定时任务工具
```

### 关键设计模式

#### 1. 驱动管理模式 (drivers)

所有驱动模块使用统一的客户端注册和获取模式:

- `smart_load(conf)`: 智能加载配置字典,自动导入并初始化对应的驱动模块
- 每个驱动模块提供:
  - `load(config)`: 从配置加载并注册客户端
  - `new_client(uri, tag)`: 注册新的客户端实例
  - `get_client(tag)` 或 `connect(tag)`: 获取已注册的客户端
  - `instances()`: 返回所有已注册的客户端实例

示例:
```python
from jcutil.drivers import smart_load, db, mongo, redis

# 统一加载所有驱动配置
smart_load({'db': {...}, 'mongo': {...}, 'redis': {...}})

# 使用标签访问
with db.connect('app') as conn:
    result = conn.execute("SELECT ...")
```

#### 2. 异步支持

- 数据库驱动支持同步和异步操作(SQLAlchemy AsyncEngine, Motor)
- `core.init_event_loop()`: 获取或创建 event loop
- `core.async_run()`: 在线程池中异步执行同步函数
- `core.map_async()`: 异步非阻塞 map 函数

#### 3. JSON序列化

使用自定义编码器处理特殊类型:
- `SafeJsonEncoder`: 支持 datetime, Decimal, ObjectId, UUID, Enum 等
- `SafeJsonDecoder`: 安全解析 JSON
- `pp_json()`: 彩色高亮输出 JSON
- `fix_document()`: 按类型配置修复 dict 值(用于 Kafka 等场景)

#### 4. 函数式编程

大量使用 `jcramda` 库提供的函数式工具:
- curry, compose, pipe
- when, if_else
- attr, getitem, has_attr
- 在 mongo.py 中广泛应用于数据转换

### 依赖关系

核心依赖:
- `jcramda>=1.0.6`: 函数式编程工具库
- `colorama`: 跨平台彩色终端输出
- `httpx>=0.24.0`: 异步 HTTP 客户端
- `pycryptodomex`: 加密算法实现
- `pymongo` + `motor`: MongoDB 同步/异步驱动
- `redis`: Redis 客户端
- `sqlalchemy`: 关系型数据库 ORM(可选)
- `apscheduler`: 定时任务调度
- `pandas`: 数据处理

### 配置系统

支持多种配置源:
- YAML 配置文件 (使用 `pyyaml`)
- HCL 配置文件 (使用 `pyhcl`)
- 环境变量 (使用 `python-dotenv`)
- Consul 配置中心

配置加载流程:
1. 读取配置文件或从 Consul 拉取
2. 使用 `smart_load()` 统一加载到各驱动模块
3. 各模块维护内部实例字典

## 编码规范

### 类型注解

- 最低支持 Python 3.8
- 使用 typing 模块的类型提示
- 可选依赖通过 try/except ImportError 处理
- 使用 `# pyright: ignore` 忽略类型检查警告(当依赖不可用时)

### 导出管理

每个模块都明确定义 `__all__` 列表,控制公开 API。

### 异步代码

- 使用 `asyncio` 协程
- 对可能是协程的返回值用 `asyncio.iscoroutine()` 检查
- 在事件循环中使用 `create_task()` 调度协程

### 错误处理

- 使用 `logging` 模块记录错误和调试信息
- 驱动加载失败时记录 debug 级别日志,不中断流程

## 测试编写

- 测试文件命名: `test_<module>.py`
- 异步测试使用 `pytest-asyncio` 的 `@pytest.mark.asyncio` 装饰器
- 测试需要外部服务(MongoDB, Redis等)的模块需要配置 docker-compose.yml 环境
- 使用 fixtures 管理测试依赖和清理
