#!/bin/bash
# pre-push-check.sh - 插件推送前检查 + 自动修复脚本

set -e

echo "🔍 运行插件检查..."

# 1. 语法检查
echo "✅ 语法检查..."
python -m py_compile plugin.py
echo "   语法 OK"

# 2. ruff 检查 + 自动修复
if command -v ruff &> /dev/null; then
    echo "✅ Ruff 检查..."
    if ! ruff check plugin.py; then
        echo "   ⚠️ 发现问题，尝试自动修复..."
        ruff check --fix plugin.py
        echo "   🔧 已自动修复"

        # 如果有更改，重新检查
        if ruff check plugin.py; then
            echo "   ✅ 修复后检查通过"
        else
            echo "   ❌ 无法自动修复，请手动处理"
            exit 1
        fi
    else
        echo "   Ruff 检查通过"
    fi
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
