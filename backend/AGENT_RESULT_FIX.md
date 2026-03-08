# 修复总结：统一 Agent 返回值格式

## 问题
飞书发消息报错 "too many values to unpack (expected 2)"，原因是返回值格式不统一。

## 解决方案

### 1. 创建统一的返回值模型
文件：`backend/app/图引擎/结果模型.py`

```python
@dataclass
class AgentResult:
    reply: str                    # Agent 的回复内容
    used_feishu: bool = False     # 是否调用了飞书工具
    agent_name: Optional[str] = None  # Agent 名称（多 Agent 模式）
```

### 2. 修改飞书智能体调用
文件：`backend/app/飞书/智能体调用.py`

**修改点：**
- 导入 `AgentResult`
- `调用智能体()` 返回类型改为 `AgentResult`
- `同步调用智能体()` 返回类型改为 `AgentResult`
- 所有错误处理返回 `AgentResult` 对象
- 添加兼容处理：支持旧格式 tuple

### 3. 修改飞书消息处理
文件：`backend/app/飞书/消息处理.py`

**修改点：**
- 使用 `AgentResult` 对象接收返回值
- 添加类型检查和兼容处理
- 支持 `AgentResult`、`tuple`、`str` 三种格式

## 兼容性
- 新代码返回 `AgentResult` 对象
- 自动兼容旧代码的 `tuple` 格式
- 自动兼容字符串格式

## 测试验证
```bash
cd backend && python -c "
from app.图引擎.结果模型 import AgentResult
result = AgentResult(reply='测试', used_feishu=True)
print(result.reply, result.used_feishu)
"
```

## 下一步
如果需要在其他地方使用 Agent 调用，统一使用 `AgentResult` 格式：

```python
from app.图引擎.结果模型 import AgentResult

# 返回结果
return AgentResult(
    reply="回复内容",
    used_feishu=False,
    agent_name="Agent名称"
)
```
