# 运行代码检查和自动修复

# 显示当前步骤的辅助函数
function Step {
    param([string]$Message)
    Write-Host "`n===> $Message" -ForegroundColor Blue
}

# 确保脚本从项目根目录运行
if (-not (Test-Path "pyproject.toml")) {
    Write-Host "错误: 请从项目根目录运行此脚本" -ForegroundColor Red
    exit 1
}

# 检查是否安装了uv和ruff
try {
    uv --version | Out-Null
} catch {
    Step "安装uv"
    pip install uv
}

try {
    ruff --version | Out-Null
} catch {
    Step "安装ruff"
    uv pip install --system ruff
}

# 运行Ruff检查
Step "运行Ruff检查和自动修复"
uvx ruff check . --fix --unsafe-fixes

# 显示最终检查结果
Step "显示最终检查结果"
uvx ruff check .

# 提供提交命令的提示
Step "完成"
Write-Host "如果您对自动修复的更改满意，可以运行以下命令提交:"
Write-Host "git add ." -ForegroundColor Green
Write-Host "git commit -m ""style: 修复代码风格问题""" -ForegroundColor Green 