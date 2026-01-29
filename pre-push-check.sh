#!/bin/bash
# pre-push-check.sh - 插件推送前检查脚本

set -e

echo "🔍 运行插件检查..."

# 1. 语法检查
echo "✅ 语法检查..."
python -m py_compile plugin.py
echo "   语法 OK"

# 2. ruff 检查
if command -v ruff &> /dev/null; then
    echo "✅ Ruff 检查..."
    ruff check plugin.py
else
    echo "⚠️  ruff 未安装，跳过"
fi

# 3. 导入测试
echo "✅ 导入测试..."
python -c "from plugin import plugin; print('   导入 OK')"

# 4. 检查 __init__.py
echo "✅ __init__.py 检查..."
if grep -q "from .plugin import plugin" __init__.py; then
    echo "   __init__.py 包含正确的导入"
else
    echo "   ⚠️  __init__.py 可能缺少导入"
fi

# 5. 检查 pyproject.toml
echo "✅ pyproject.toml 检查..."
if grep -q 'name = "nekro-plugin-social-memory"' pyproject.toml; then
    echo "   pyproject.toml 配置正确"
fi

echo ""
echo "✨ 所有检查通过！可以推送了。"
