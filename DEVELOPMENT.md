# 插件开发工作流程

## 推送前检查清单

在推送到市场之前，必须执行以下检查：

### 1. 本地语法检查
```bash
python -m py_compile plugin.py
```

### 2. 运行 ruff
```bash
ruff check plugin.py
```

### 3. 导入测试
```bash
python -c "from plugin import plugin; print('OK')"
```

### 4. 检查 __init__.py
确保包含：
```python
from .plugin import plugin
```

### 5. 使用检查脚本
```bash
chmod +x pre-push-check.sh
./pre-push-check.sh
```

## GitHub Actions

项目已配置 CI 检查：
- **语法检查**: Python 编译检查
- **Ruff 检查**: 代码风格和错误
- **导入测试**: 验证插件可以正确导入

## 常见问题

### Q: `= = None` 语法错误？
A: 这是复制粘贴错误，应该是 `= None`

### Q: `AttributeError: module 'nekro_agent.api.schemas' has no attribute 'ChatMessage'`？
A: 正确导入是：
```python
from nekro_agent.api.message import ChatMessage
from nekro_agent.api.signal import MsgSignal
```

### Q: `No package metadata was found`？
A: `__init__.py` 必须包含 `from .plugin import plugin`

## 最佳实践

1. **先测试后推送**: 每次推送前运行完整检查
2. **参考内置插件**: 查看 `nekro-agent/plugins/builtin/` 中的示例
3. **使用 ruff**: 自动化代码检查
4. **类型注解**: 使用类型注解帮助静态检查
