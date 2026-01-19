# Change Logs

## 2.1.0

> 2026-01-19

- 为数据库驱动模块添加类型标注
  - 为 db.py 文件中的所有函数添加完整的类型注解
  - 引入 Engine、AsyncEngine 等 SQLAlchemy 类型支持
  - 添加适当的 Union 和 Optional 类型以提高代码可读性

- 代码质量改进
  - 为 jsonfy.py 模块添加类型标注和优化
  - 更新 chalk 模块以符合类型检查标准
  - 改进核心模块的类型安全性

- 依赖和配置更新
  - 更新 pyproject.toml 以反映新的依赖关系
  - 更新 requirements.lock 和 uv.lock 以同步依赖版本

- 数据访问层改进
  - 重构 DBA 模块中的 SQL 相关功能
  - 移除不再使用的 async_ 和 helper 模块
  - 优化数据访问接口的一致性

## 2.0.1

> 2025-04-13

- 修改server环境变量的读取方式，减少副作用
- 添加加解密的工具方法
- 增强 `jcutil.netio` 模块
  - 添加 EventSource (SSE) 支持
  - 添加 WebSocket 客户端支持
  - 添加文件上传功能
  - 添加文件下载到磁盘功能
  - 添加 PUT 和 DELETE 方法支持

- 完善 Redis 测试用例
  - 添加基础操作测试
  - 添加过期时间测试
  - 增强锁机制测试

- 改进类型提示和静态检查支持
  - 修复 consul.pyi 中的星号导入问题
  - 完善 ConsulClient 类型定义
  - 更新类型注解以符合现代 Python 标准

- 代码质量和工程化改进
  - 添加 GitHub Actions CI/CD 工作流
  - 配置自动测试和发布流程
  - 增加 Ruff 代码静态检查支持
  - 修复命名规范问题

## 1.0.4

> 2021-1-20

- use `redis-py-cluster` handle redis cluster mode

- add `jcutil.server` module

- add `KvProperty` proxy class to consul

- add `mdb_proxy` method on `drivers.mongo`
