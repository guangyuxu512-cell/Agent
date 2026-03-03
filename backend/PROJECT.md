# Agent 后端项目文档

## 项目概述

这是一个基于 LangGraph 的 AI Agent 平台后端，支持多智能体协作、工具调用、飞书集成等功能。

**核心特性**：
- 单/多 Agent 协作编排
- 工具系统（HTTP API / Python 代码 / 内置工具）
- 飞书长连接与表格操作
- SSE 流式对话
- 记忆管理与知识检索
- 定时任务调度
- 日志推流（影刀集成）

## 技术栈

- **Web 框架**：FastAPI 0.115+
- **AI 框架**：LangGraph + LangChain
- **数据库**：SQLite（SQLAlchemy ORM）
- **异步**：asyncio + httpx
- **安全**：JWT 鉴权 + RestrictedPython 沙箱
- **调度**：APScheduler
- **前端**：React（独立仓库）

## 目录结构

```
backend/
├── app/
│   ├── __init__.py
│   ├── 启动器.py                    # FastAPI 入口，注册路由和中间件
│   ├── 配置.py                      # 环境变量配置
│   ├── 常量.py                      # 全局常量
│   ├── 加密.py                      # AES 加密/解密工具
│   ├── 密码策略.py                  # 密码强度校验
│   ├── 调度器.py                    # APScheduler 定时任务
│   ├── schemas.py                   # 统一响应模型
│   │
│   ├── db/                          # 数据库层
│   │   ├── 数据库.py                # 会话工厂、初始化
│   │   └── 模型.py                  # ORM 模型定义
│   │
│   ├── middleware/                  # 中间件
│   │   └── 鉴权中间件.py            # JWT Token 验证
│   │
│   ├── api/                         # 路由层
│   │   ├── 鉴权.py                  # 登录、修改密码
│   │   ├── 智能体.py                # Agent CRUD
│   │   ├── 对话.py                  # 对话 CRUD + SSE 流式
│   │   ├── 工具.py                  # 工具 CRUD + 测试
│   │   ├── 系统配置.py              # 系统配置 CRUD
│   │   ├── 飞书表格.py              # 飞书表格配置
│   │   ├── 记忆.py                  # 记忆 CRUD
│   │   ├── 日志推流.py              # 影刀日志推流（X-RPA-KEY 鉴权）
│   │   ├── 编排.py                  # 多 Agent 编排配置
│   │   └── 定时任务.py              # 定时任务 CRUD
│   │
│   ├── 图引擎/                      # LangGraph 核心
│   │   ├── 构建器.py                # 单 Agent 图构建
│   │   ├── 多Agent构建器.py         # 多 Agent 协作图
│   │   ├── 上下文.py                # 上下文组装（历史+记忆+知识）
│   │   ├── 工具加载器.py            # 工具转 LangChain StructuredTool
│   │   ├── 记忆管理.py              # 记忆提取与查询
│   │   ├── 知识检索.py              # 向量检索（预留）
│   │   ├── _沙箱执行器.py           # Python 工具沙箱子进程
│   │   └── 内置工具/
│   │       ├── 邮件.py              # 发送邮件
│   │       ├── 飞书.py              # 飞书助手（发消息/读写表格）
│   │       └── _配置.py             # 内置工具注册表
│   │
│   └── 飞书/                        # 飞书集成
│       ├── 配置与会话.py            # 飞书 SDK 初始化
│       ├── 消息处理.py              # 飞书消息事件处理
│       └── 智能体调用.py            # 飞书调用 Agent 逻辑
│
├── data/                            # SQLite 数据库文件
├── tests/                           # 测试文件
├── Dockerfile                       # Docker 镜像
├── docker-compose.yml               # 容器编排
└── requirements.txt                 # Python 依赖
```

## 核心链路说明

### 1. Web 对话链路

**流程**：前端 → `/api/chat` → SSE 流式 → LangGraph 执行 → 工具调用 → 返回结果

**关键文件**：
- `app/api/对话.py:332` - `/api/chat` 接口
- `app/图引擎/构建器.py` - 单 Agent 图构建
- `app/图引擎/上下文.py` - 组装历史消息 + 记忆 + 知识
- `app/图引擎/工具加载器.py` - 加载工具列表

**SSE 事件类型**：
- `conversation_id` - 对话 ID
- `agent` - 当前 Agent 名称
- `token` - 逐 token 输出
- `tool_call` - 工具调用开始
- `tool_result` - 工具调用结果
- `done` - 完整回复
- `error` - 错误信息

### 2. 飞书对话链路

**流程**：飞书消息 → Webhook → 长连接推送 → Agent 处理 → 回复飞书

**关键文件**：
- `app/飞书/消息处理.py` - 飞书消息事件处理
- `app/飞书/智能体调用.py` - 调用 Agent 并回复
- `app/飞书/配置与会话.py` - 飞书 SDK 初始化

**配置要求**：
- 系统配置表 `system_config` 中配置 `feishu` 分类（appId/appSecret）
- 飞书开放平台配置事件订阅和机器人权限

### 3. 工具执行链路

**工具类型**：
1. **HTTP API** - 调用外部 HTTP 接口
2. **Python 代码** - 沙箱执行 Python 代码（7 层安全防护）
3. **内置工具** - 发送邮件、飞书助手

**安全机制（Python 工具）**：
- L1: RestrictedPython 编译期阻断
- L2: 受限 builtins（无 open/import）
- L3: 子进程隔离
- L4: 禁网（环境剥离）
- L5: 文件系统限制（空临时目录）
- L6: Windows Job Object / Linux rlimit（内存 128MB）
- L7: subprocess timeout + 递归限制

**关键文件**：
- `app/图引擎/工具加载器.py:165` - `执行HTTP工具`
- `app/图引擎/工具加载器.py:201` - `执行Python工具`
- `app/图引擎/_沙箱执行器.py` - 沙箱子进程

## API 接口文档

### 鉴权接口 (`/api/auth`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/login` | 用户登录，返回 JWT Token |
| POST | `/api/auth/change-password` | 修改密码（需登录） |

### 智能体接口 (`/api/agents`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/agents` | 获取 Agent 列表（分页） |
| POST | `/api/agents` | 创建 Agent |
| GET | `/api/agents/{agent_id}` | 获取 Agent 详情 |
| PUT | `/api/agents/{agent_id}` | 更新 Agent |
| DELETE | `/api/agents/{agent_id}` | 删除 Agent |

**Agent 字段**：
- `name` - 名称
- `role` - 角色描述
- `prompt` - 系统提示词
- `llmProvider` - LLM 提供商（OpenAI/Gemini/DashScope）
- `llmModel` - 模型名称
- `llmApiUrl` - API 地址
- `llmApiKey` - API 密钥（加密存储）
- `temperature` - 温度参数
- `tools` - 工具 ID 列表
- `status` - 状态（running/stopped）

### 对话接口 (`/api`)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/chat` | 发送消息（SSE 流式） |
| GET | `/api/conversations` | 获取对话列表 |
| GET | `/api/conversations/{id}/messages` | 获取消息列表 |
| DELETE | `/api/conversations/{id}` | 删除对话 |

### 工具接口 (`/api/tools`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tools` | 获取工具列表（分页） |
| POST | `/api/tools` | 创建工具 |
| GET | `/api/tools/{tool_id}` | 获取工具详情 |
| PUT | `/api/tools/{tool_id}` | 更新工具 |
| DELETE | `/api/tools/{tool_id}` | 删除工具 |
| POST | `/api/tools/{tool_id}/test` | 测试工具 |

**工具字段**：
- `name` - 工具名称（唯一）
- `description` - 工具描述
- `tool_type` - 类型（http_api/python_code/builtin）
- `parameters` - 参数定义（JSON Schema）
- `config` - 配置（HTTP URL/Python 代码/builtin_name）
- `status` - 状态（active/inactive）

### 系统配置接口 (`/api/config`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/config` | 获取全部配置 |
| POST | `/api/config` | 保存全部配置 |
| GET | `/api/config/{category}` | 获取分类配置 |
| DELETE | `/api/config/{category}` | 删除分类配置 |

**配置分类**：
- `email` - 邮件配置（SMTP）
- `feishu` - 飞书配置（appId/appSecret）
- `n8n` - n8n 工作流配置

### 飞书表格接口 (`/api/feishu/tables`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/feishu/tables` | 获取表格列表 |
| POST | `/api/feishu/tables` | 新增表格 |
| PUT | `/api/feishu/tables/{id}` | 更新表格 |
| DELETE | `/api/feishu/tables/{id}` | 删除表格 |

### 记忆接口 (`/api/memories`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/memories` | 获取记忆列表 |
| DELETE | `/api/memories/{id}` | 删除记忆 |

### 日志推流接口 (`/api/logs`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/logs/stream` | SSE 日志推流（X-RPA-KEY 鉴权） |

### 编排接口 (`/api/orchestration`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/orchestration` | 获取编排配置 |
| POST | `/api/orchestration` | 保存编排配置 |

### 定时任务接口 (`/api/scheduled-tasks`)

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/scheduled-tasks` | 获取任务列表 |
| POST | `/api/scheduled-tasks` | 创建任务 |
| PUT | `/api/scheduled-tasks/{id}` | 更新任务 |
| DELETE | `/api/scheduled-tasks/{id}` | 删除任务 |

## 工具系统

### 工具类型

系统支持三种工具类型：

| 工具类型 | 说明 | 配置方式 |
|---------|------|---------|
| `builtin` | 内置工具（邮件、飞书） | `config.builtin_name` 指定工具标识 |
| `http_api` | HTTP API 调用 | `config` 包含 url/method/headers 等 |
| `python_code` | Python 代码沙箱执行 | `config.code` 包含 Python 代码 |

### 内置工具 (builtin)

当前已实现的内置工具：

**1. 发送邮件** (`send_email`)
- **参数**：收件人、主题、正文
- **配置来源**：系统配置表 `email` 分类（smtpServer/smtpPort/sender/smtpPassword）
- **config 格式**：`{"builtin_name": "send_email"}`

**2. 飞书助手** (`feishu_assistant`)
- **参数**：操作类型（发消息/读表格/写表格）、参数（JSON 字符串）
- **配置来源**：系统配置表 `feishu` 分类（appId/appSecret）+ 飞书表格配置表
- **config 格式**：`{"builtin_name": "feishu_assistant"}`
- **支持操作**：
  - 发消息：`{"操作类型": "发消息", "参数": "{\"open_id\": \"xxx\", \"内容\": \"xxx\"}"}`
  - 读表格：`{"操作类型": "读表格", "参数": "{\"表格名称\": \"xxx\"}"}`
  - 写表格：`{"操作类型": "写表格", "参数": "{\"表格名称\": \"xxx\", \"数据\": {\"字段名\": \"值\"}}"}`

### HTTP API 工具

**config 字段**：
- `url` - 接口地址（支持 `{参数名}` 占位符）
- `method` - 请求方法（GET/POST/PUT/DELETE）
- `headers` - 请求头（可选）
- `body_template` - 请求体模板（可选）
- `timeout` - 超时时间（秒，默认 30）

**示例**：
```json
{
  "url": "https://api.example.com/users/{user_id}",
  "method": "GET",
  "headers": {"Authorization": "Bearer {token}"},
  "timeout": 30
}
```

### Python 代码工具

**config 字段**：
- `code` - Python 代码（使用 RestrictedPython）

**参数传递**：
- 参数通过 `params` 字典传入代码
- 返回值通过 `print()` 输出

**安全限制**（7 层防护）：
- L1: RestrictedPython 编译期阻断 `import`、`_` 前缀属性
- L2: 受限 builtins（无 `open`/`getattr`/`type`/`__import__`）
- L3: 子进程隔离（独立 PID）
- L4: 禁网（环境变量剥离）
- L5: 文件系统限制（空临时目录，无 `open`）
- L6: Windows Job Object / Linux rlimit（内存 128MB）
- L7: subprocess timeout（10 秒）+ 递归限制（100 层）

**示例**：
```python
# config.code
result = params.get('a', 0) + params.get('b', 0)
print(f"计算结果: {result}")
```

## 内置工具开发规范

### 文件结构

在 `app/图引擎/内置工具/` 目录下新建 `.py` 文件：

```
app/图引擎/内置工具/
├── __init__.py          # 工具注册表
├── _配置.py             # 配置读取工具函数
├── 邮件.py              # 发送邮件工具
├── 飞书.py              # 飞书助手工具
└── 你的工具.py          # 新增工具
```

### 函数规范

**1. 函数签名**
- 必须是 `async def` 异步函数
- 参数使用类型注解（`str`、`int` 等）
- 返回值类型为 `str`

**2. 配置读取**
- 从系统配置表读取配置：`_获取系统配置(category)`
- 配置存储在 `system_config` 表，按 `category` 分类

**3. 错误处理**
- 使用 `try-except` 捕获异常
- 返回格式：成功返回描述性文本，失败返回 `"错误：{错误信息}"`

**示例代码**：
```python
# app/图引擎/内置工具/示例.py
import logging
from ._配置 import _获取系统配置

logger = logging.getLogger(__name__)

async def 示例工具(参数1: str, 参数2: int) -> str:
    """工具描述

    Args:
        参数1: 参数1说明
        参数2: 参数2说明

    Returns:
        成功返回结果描述，失败返回错误信息
    """
    try:
        # 1. 读取配置
        配置 = _获取系统配置("your_category")
        api_key = 配置.get("api_key")

        if not api_key:
            return "错误：配置不完整，请在系统配置中设置 your_category 分类"

        # 2. 执行业务逻辑
        # ...

        logger.info(f"示例工具执行成功: {参数1}")
        return f"执行成功：{参数1}"

    except Exception as e:
        error_msg = f"示例工具执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"错误：{error_msg}"
```

### 注册规范

在 `app/图引擎/内置工具/__init__.py` 中注册工具：

```python
from .邮件 import 发送邮件
from .飞书 import 飞书助手
from .示例 import 示例工具  # 导入新工具

# 内置工具映射表
BUILTIN_TOOLS = {
    "send_email": 发送邮件,
    "feishu_assistant": 飞书助手,
    "example_tool": 示例工具,  # 添加映射（英文标识）
}
```

**重要**：
- `builtin_name` 必须使用英文标识符（如 `send_email`）
- 英文标识符必须与 `BUILTIN_TOOLS` 的 key 一致
- 英文标识符用于 LLM API 调用（兼容 Gemini 等要求英文工具名的 API）

### 前端注册

在前端工具管理页面创建工具时：

| 字段 | 值 | 说明 |
|------|-----|------|
| `name` | 中文名称（如"示例工具"） | 前端显示名称 |
| `tool_type` | `builtin` | 工具类型 |
| `description` | 工具描述 | LLM 理解工具用途 |
| `parameters` | JSON Schema | 定义工具参数 |
| `config` | `{"builtin_name": "example_tool"}` | 指定英文标识符 |

**parameters 示例**：
```json
{
  "type": "object",
  "properties": {
    "参数1": {
      "type": "string",
      "description": "参数1说明"
    },
    "参数2": {
      "type": "integer",
      "description": "参数2说明"
    }
  },
  "required": ["参数1"]
}
```

### 参考现有工具

- **邮件工具**：`app/图引擎/内置工具/邮件.py` - 简单的 SMTP 调用
- **飞书工具**：`app/图引擎/内置工具/飞书.py` - 复杂的多操作工具，包含 HTTP API 调用和数据库查询

## 配置说明

### 环境变量 (`.env`)

```bash
# 数据库
DATABASE_URL=sqlite:///./data/agent.db

# JWT
SECRET_KEY=your-secret-key-here
TOKEN_EXPIRE_HOURS=24

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# 环境
APP_ENV=dev  # dev/prod
DISABLE_DOCS_IN_PROD=true

# LLM（可选，Agent 配置优先）
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://api.openai.com/v1
```

### 数据库表

**核心表**：
- `users` - 用户表
- `agents` - Agent 配置
- `conversations` - 对话记录
- `messages` - 消息记录
- `tools` - 工具配置
- `system_config` - 系统配置（JSON blob）
- `feishu_tables` - 飞书表格配置
- `memories` - 记忆存储
- `orchestration` - 编排配置
- `scheduled_tasks` - 定时任务

### 系统配置表 (`system_config`)

存储格式：每个分类存一行 JSON blob
- `category` - 分类名（email/feishu/n8n）
- `key` - 固定为 `__data__`
- `value` - JSON 字符串

### 飞书表格配置 (`feishu_tables`)

字段：
- `name` - 表格名称（唯一）
- `app_token` - 飞书 App Token
- `table_id` - 飞书 Table ID
- `description` - 描述

## 已知问题与注意事项

### 1. Windows 部署问题

**asyncio 事件循环错误**
- **问题**：Windows 下 asyncio 默认使用 `ProactorEventLoopPolicy`，可能导致 `[Errno 22]` 错误
- **解决**：在 `app/启动器.py:7` 设置 `WindowsSelectorEventLoopPolicy()`
- **代码**：
  ```python
  import sys
  if sys.platform == "win32":
      import asyncio
      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
  ```

**Python 工具沙箱资源限制**
- Windows 使用 Job Object 限制资源（内存 128MB、禁止子进程）
- Linux 使用 rlimit（RLIMIT_AS、RLIMIT_NPROC、RLIMIT_CPU）
- 容器部署时由 `docker-compose.yml` 提供 OS 级限制

### 2. 工具名称规范

**System Prompt 工具名必须用英文**
- **问题**：部分 LLM API（如 Gemini）要求工具名称必须是英文标识符
- **解决**：内置工具使用英文 `builtin_name`（`send_email`、`feishu_assistant`）
- **前端显示**：前端 `name` 字段可以用中文（如"发送邮件"），但 `config.builtin_name` 必须是英文
- **位置**：`app/图引擎/工具加载器.py:389` - 使用 `builtin_name` 作为工具名称

**自定义工具命名建议**
- HTTP API 工具和 Python 工具支持- 但建议使用英文或拼音以提高兼容性

### 3. 飞书表格写入机制

**Upsert 实现方式**
- **问题**：飞书 API 没有原生 upsert 接口
- **解决**：使用 `POST /records/search` + filter 精确匹配
- **逻辑**：
  1. 根据第一个字段作为查询条件（如 `{"店铺名称": "测试店铺"}`）
  2. 使用 `POST /records/search` 查询所有记录（最多 500 条）
  3. 遍历记录，精确匹配第一个字段的值
  4. 存在则 `PUT /records/{record_id}` 更新，不存在则 `POST /records` 新增
- **位置**：`app/图引擎/内置工具/飞书.py:317-353`

**字段值格式兼容**
- 飞书字段值可能是列表格式：`[{"text": "xxx"}]`
- 查询时需要提取 `text` 字段进行比较

### 4. 中转 API 要求

**OpenAI Function Calling 格式**
- **问题**：使用中转 API（如 one-api）时，必须支持 OpenAI 的 `tools` 参数格式
- **要求**n  - 支持 `tools` 参数（JSON Schema 格式）
  - 支持 `tool_choice` 参数
  - 返回 `tool_calls` 字段
- **不兼容的 API**：部分中转 API 只支持旧版 `functions` 参数，会导致工具调用失败

### 5. 对话链路工具查询

**P0-2 修复**
- **问题**：历史版本使用工具名称查询，导致重名工具冲突
- **解决**：改用 `工具模型.id` 匹配（兼容按名称查询）
- **位置**：`app/api/对话.py:119`

### 6. 日志接口鉴权

**P0-3 修复**
- **问题**：旧版日志接口免鉴权，存在安全风险
- **解决**：日志接口需 Bearer token 访问
- **影刀推流**：使用独立接口 `/api/logs/stream`，通过 `X-RPA-KEY` 鉴权

**P1-1 修复**
- **问题**：飞书智能体调用日志输出 API Key 前缀
- **解决**：日志中不再输出敏感信息
- **位置**：`app/飞书/智能体调用.py`

## 待办事项

### 功能增强

- [ ] 向量检索功能完善（`app/图引擎/知识检索.py`）
- [ ] 多 Agent 编排模式测试（路由/并行）
- [ ] 工具执行日志持久化
- [ ] Agent 执行审批流程
- [ ] 前端国际化支持

### 工具系统优化（未实现）

以下功能在早期规划中，但当前版本未实现：

- [ ] **统一 ToolResult 模型**：标准化工具返回格式（success/data/error）
- [ ] **统一执行入口**：抽象 `execute_tool(tool_record, params)` 函数
- [ ] **工具执行中间件**：日志记录、性能监控、错误重试
- [ ] **工具版本管理**：支持工具多版本并存
- [ ] **工具市场**：内置工具模板库

## 开发指南

### 启动开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 启动后端
cd backend
python -m uvicorn app.启动器:app --reload --port 8001

# 访问 API 文档
http://localhost:8001/docs
```

### Docker 部署

```bash
cd backend
docker-compose up -d
```

### 运行测试

```bash
# 回归测试
pytest tests/regression/

# 安全测试
pytest tests/security/
```

## 联系方式

如有问题，请查看项目 README 或提交 Issue。
