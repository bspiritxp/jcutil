#!/bin/bash
# 运行代码检查和自动修复

# 显示当前步骤的辅助函数
function step() {
    echo -e "\033[0;34m\n===> $1\033[0m"
}

# 确保脚本从项目根目录运行
if [ ! -f "pyproject.toml" ]; then
    echo "错误: 请从项目根目录运行此脚本"
    exit 1
fi

# 检查是否安装了uv和ruff
if ! command -v uv &> /dev/null; then
    step "安装uv"
    pip install uv
fi

if ! command -v ruff &> /dev/null; then
    step "安装ruff"
    uv pip install --system ruff
fi

# 运行Ruff检查
step "运行Ruff检查和自动修复"
uvx ruff check . --fix

# 显示最终检查结果
step "显示最终检查结果"
uvx ruff check .

# 提供提交命令的提示
step "完成"
echo "如果您对自动修复的更改满意，可以运行以下命令提交:"
echo "git add ."
echo "git commit -m \"style: 修复代码风格问题\"" 