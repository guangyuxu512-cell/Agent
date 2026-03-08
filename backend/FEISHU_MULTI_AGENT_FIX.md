# 飞书多 Agent 编排修复总结

## 问题
飞书入口（`飞书/智能体调用.py`）走的是单 Agent 路径，没有使用多 Agent 编排。

## 解决方案

### 1. 创建统一的智能调用函数
**文件：** `app/图引擎/智能调用.py`（新建）

**功能：**
- 自动判断是否启用多 Agent 编排
- 检查 running 状态的 Agent 数量
- 如果 ≥2 个，读取编排配置并使用多 Agent 图
- 否则使用单 Agent 图
- 返回统一的 `AgentResult` 对象

**关键逻辑：**
```python
async def 智能调用Agent(消息列表, agent配置, 工具记录列表, db):
    # 1. 检查编排配置
    编排 = 获取编排配置(db)

    if 编排:
        agents配置列表, 工具记录映射 = 获取所有running_Agent配置和工具(db)

        # 2. 至少 2 个 running Agent 才走多 Agent 模式
        if len(agents配置列表) >= 2:
            图 = 构建多Agent图(编排, agents配置列表, 工具记录映射)
            # 执行多 Agent 图...
            return AgentResult(...)

    # 3. 否则走单 Agent 模式
    图 = 构建Agent图(agent配置, 工具记录列表)
    # 执行单 Agent 图...
    return AgentResult(...)
```

### 2. 修改飞书智能体调用
**文件：** `app/飞书/智能体调用.py`

**修改点：**
- 导入 `智能调用Agent` 函数
- 移除直接构建单 Agent 图的代码
- 使用 `智能调用Agent` 替代原来的 `astream_events` 循环
- 保留重试逻辑和错误处理

**修改前：**
```python
图 = 构建Agent图(agent配置, 工具记录列表)
async for event in 图.astream_events(...):
    # 处理事件...
```

**修改后：**
```python
result = await 智能调用Agent(
    消息列表=消息列表,
    agent配置=agent配置,
    工具记录列表=工具记录列表,
    db=db
)
完整回复 = result.reply
调用了飞书发送消息 = result.used_feishu
```

## 优势

1. **代码复用**：飞书入口和 Web 入口共享同一套多 Agent 编排逻辑
2. **自动切换**：根据配置自动在单/多 Agent 模式间切换
3. **统一返回**：使用 `AgentResult` 统一返回格式
4. **易于维护**：多 Agent 逻辑集中在一个地方

## 测试步骤

1. **重启后端服务**
   ```bash
   cd backend && python 启动器.py
   ```

2. **从飞书发送消息**
   - 应该会自动使用多 Agent 编排（如果有 ≥2 个 running Agent）

3. **查看后端日志**
   ```
   [智能调用] 使用多Agent编排模式，Agent数量: 2
   [Supervisor] 可用智能体: ['阿维斯', '智能助手']
   [多Agent-Supervisor] tool_calls: ...
   ```

4. **验证功能**
   - 飞书消息应该能正确路由到子 Agent
   - 不再报 "too many values to unpack" 错误

## 下一步

如果 Supervisor 仍然不调用工具（只是文字描述），可能需要：
1. 更换模型为 OpenAI GPT-4 或 Claude（qwen3.5-plus 对 function calling 支持不够好）
2. 或者进一步强化 prompt
