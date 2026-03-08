# Supervisor 不调用子 Agent 排查指南

## 已添加的调试日志

### 1. 多Agent构建器.py
- ✅ 打印可用智能体列表
- ✅ 打印 Supervisor prompt 前100字
- ✅ 打印图的节点信息
- ✅ 强化了 prompt，明确要求必须调用工具

### 2. 对话.py - 多Agent_SSE生成器
- ✅ 捕获 `on_chat_model_end` 事件（Supervisor 节点）
- ✅ 检查 `output.tool_calls` 字段
- ✅ 检查 `output.additional_kwargs.tool_calls` 字段
- ✅ 打印 Supervisor 的输出内容
- ✅ 记录所有工具调用（on_tool_start/on_tool_end）

## 测试步骤

1. **重启后端**
   ```bash
   cd backend && python 启动器.py
   ```

2. **发送测试消息**
   通过前端或 API 发送消息，触发多 Agent 编排

3. **查看后端日志**，关注以下关键信息：

   ```
   [Supervisor] 可用智能体: ['阿维斯', '智能助手']
   [Supervisor] Prompt 前100字: ...
   [Supervisor] 图节点: ...
   [多Agent] 开始执行多Agent图
   [多Agent-Supervisor] 事件类型: on_chat_model_end
   [多Agent-Supervisor] LLM输出类型: ...
   [多Agent-Supervisor] tool_calls: ...
   ```

## 可能的问题和解决方案

### 问题1：tool_calls 为空
**症状：**
```
[多Agent-Supervisor] ⚠️ tool_calls 为空！Supervisor 没有调用任何工具
[多Agent-Supervisor] 内容: 我将把这个任务分配给抖店助手...
```

**原因：**
- qwen3.5-plus 对 function calling 支持不够好
- LLM 只是用文字描述，没有实际调用工具

**解决方案：**
1. 更换模型为 OpenAI GPT-4 或 Claude
2. 或者在 prompt 中更强硬地要求：
   ```python
   prompt = """【强制要求】你必须调用 transfer_to_xxx 工具，不允许用文字描述。
   如果你只是说"我将分配给xxx"而不调用工具，这是错误的行为。"""
   ```

### 问题2：工具未注册
**症状：**
```
[Supervisor] 图节点: ['supervisor', '__start__', '__end__']
```
没有看到子 Agent 节点

**原因：**
- `create_supervisor` 没有正确注册子 Agent
- 子 Agent 构建失败

**解决方案：**
检查子 Agent 构建日志，确保每个子 Agent 都成功创建

### 问题3：模型不支持 tool calling
**症状：**
```
[多Agent-Supervisor] 输出中没有 tool_calls 字段
```

**原因：**
- 使用的模型不支持 function calling
- 模型配置错误

**解决方案：**
1. 确认模型支持 function calling（OpenAI、Claude、部分 Qwen 模型）
2. 检查模型配置是否正确

## 下一步

根据日志输出，我们可以确定：
1. Supervisor 是否收到了 transfer_to_xxx 工具
2. Supervisor LLM 是否调用了这些工具
3. 如果没调用，是模型问题还是 prompt 问题

请重启后端，发送测试消息，然后分享后端日志中的关键信息。
