# 文档维护

`docs/` 是使用者文档的唯一源。生成的站点目录 `site/` 不提交。

## 内容职责

- `guides/`：任务导向的手写说明。每页必须明确前提、可复制示例、验证方式和失败/安全边界。
- `reference/`：mkdocstrings 从源码解析的签名和 docstring。不要手抄签名或默认值。
- `explanation.md`：跨模块设计、生命周期与不变量。

## 修改代码时

1. 改变公开函数、类、参数、默认值或异常语义：同步更新 docstring 和对应使用指南。
2. 改变外部服务、可选依赖或配置：同步更新 `docs/index.md` 的前提与对应指南。
3. 添加示例：必须可复制运行；不得包含真实凭据、内网 URL 或令牌。
4. 运行 `uv run --group docs mkdocs build --strict`，然后提交文档源码而不是 `site/`。

Mkdocstrings 在构建期从源码解析 API，避免 import `jcutil.server.envars` 等有副作用的模块。
