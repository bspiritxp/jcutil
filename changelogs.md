# Change Logs

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
