# Agent 平台 — 项目文档

## 1. 项目概览与模块图

Agent 平台是一个多智能体管理与编排系统，支持通过 Web 界面和飞书两种渠道与 AI Agent 进行对话交互。系统基于 LangGraph 实现单/多 Agent 流式对话，支持自定义工具（HTTP API / Python 沙箱代码）、定时任务调度、RAGFlow 知识检索、飞书消息长连接、长期记忆管理等功能。

**技术栈：** Python 3.11 + FastAPI / SQLAlchemy / LangGraph（后端），React + TypeScript + Vite（前端），SQLite（数据库），Nginx（反向代理）。

### 模块架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        前端 (React/Vite)                         │
│   Nginx :80  ──  SPA + /api/* 反向代理 → backend:8001           │
│   特殊路由: /api/chat, /api/logs/stream (SSE proxy_buffering off)│
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼───────────────────────────────────────┐
│                    FastAPI 后端 (:8001)                           │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐    │
│  │ 鉴权中间件   │  │ CORS 中间件  │  │ 异常处理器           │    │
│  │ (JWT Bearer) │  │              │  │ (RequestValidation)  │    │
│  └──────┬──────┘  └──────────────┘  └──────────────────────┘    │
│         │                                                        │
│  ┌──────▼──────────────────────────────────────────────────────┐ │
│  │                     API 路由层                               │ │
│  │  鉴权  智能体  对话  工具  日志  编排  定时任务              │ │
│  │  系统配置  飞书表格  记忆  健康检查                          │ │
│  └──────┬──────────────────────────────────────────────────────┘ │
│         │                                                        │
│  ┌──────▼──────────────────────────────────────────────────────┐ │
│  │                    核心引擎层                                │ │
│  │  图引擎/构建器.py — 单 Agent LangGraph 构建                  │ │
│  │  图引擎/多Agent构建器.py — Supervisor/Swarm 多 Agent 编排    │ │
│  │  图引擎/工具加载器.py — HTTP API / Python 沙箱执行           │ │
│  │  图引擎/_沙箱执行器.py — RestrictedPython 子进程隔离         │ │
│  │  图引擎/上下文.py — 消息组装 + RAGFlow 知识检索              │ │
│  │  图引擎/记忆管理.py — 对话后异步记忆提取                     │ │
│  │  调度器.py — APScheduler 定时任务引擎                        │ │
│  │  飞书/ — 飞书 WebSocket 长连接 + 消息处理 + 智能体调用       │ │
│  └──────┬──────────────────────────────────────────────────────┘ │
│         │                                                        │
│  ┌──────▼──────────────────────────────────────────────────────┐ │
│  │                    数据层                                    │ │
│  │  SQLAlchemy ORM — 13 张表                                    │ │
│  │  SQLite (data/app.db) — 自动建表                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 功能清单

每条功能均附代码证据（文件路径 + 函数/类名）。

| 模块 | 功能 | 代码证据 |
|------|------|----------|
| **鉴权** | 用户登录 / JWT 令牌（HS256，默认 24h） | `app/api/鉴权.py:34` `登录()` / `生成令牌()` |
| **鉴权** | 鉴权中间件（Bearer header + startswith 白名单） | `app/middleware/鉴权中间件.py:29` `鉴权中间件.dispatch()` |
| **鉴权** | 默认用户自动创建（admin / admin123） | `app/db/数据库.py:38` `初始化数据库()` |
| **智能体** | CRUD（分页、状态筛选、重名校验） | `app/api/智能体.py:87-195` 5 个路由函数 |
| **智能体** | API Key 加密存储（AES-256-CBC） | `app/加密.py:20` `加密()` / `解密()` |
| **对话** | 单 Agent SSE 流式对话（LangGraph astream_events） | `app/api/对话.py:126` `SSE生成器()` |
| **对话** | 多 Agent 协作对话（Supervisor / Swarm 模式） | `app/api/对话.py:211` `多Agent_SSE生成器()` + `app/图引擎/多Agent构建器.py:36` `构建多Agent图()` |
| **对话** | 对话历史 CRUD（列表/消息/删除） | `app/api/对话.py:394-501` 3 个路由函数 |
| **工具** | HTTP API 工具执行（GET/POST/PUT/DELETE，占位符 `{param}` 替换） | `app/图引擎/工具加载器.py:127` `执行HTTP工具()` |
| **工具** | Python 沙箱执行（RestrictedPython 7 层纵深防御，子进程隔离 + 平台资源限制） | `app/图引擎/工具加载器.py:163` `执行Python工具()` + `app/图引擎/_沙箱执行器.py` |
| **工具** | 平台资源限制（Windows: Job Object / Linux: rlimit / 容器: docker-compose） | `app/图引擎/工具加载器.py:33` `_创建受限Job()` / `_linux_preexec()` + `backend/docker-compose.yml` |
| **工具** | 工具 CRUD + 在线测试 | `app/api/工具.py:154-315` 6 个路由函数 |
| **日志** | SSE 实时推流（sse-token 鉴权，断线续传，心跳） | `app/api/日志.py:99` `log_stream()` |
| **日志** | 短期 SSE 令牌签发（scope=sse，3 分钟有效） | `app/api/日志.py:82` `get_sse_token()` |
| **日志** | 推送接口（外部设备上报日志） | `app/api/日志.py:56` `push_log()` |
| **日志** | 历史查询（按 task_id 过滤、增量 since_seq） | `app/api/日志.py:166` `log_history()` |
| **日志** | 过期日志自动清理（默认 30 天） | `app/api/日志.py:185` `清理过期日志()` |
| **定时任务** | Cron / Interval / Once 调度（APScheduler） | `app/调度器.py:29` `启动调度器()` / `app/调度器.py:150` `执行定时任务()` |
| **定时任务** | 定时任务 CRUD + 执行记录 | `app/api/定时任务.py:120-277` 4 个路由函数 |
| **编排** | 多 Agent 编排配置（全局单例，Supervisor 模式） | `app/api/编排.py:27-60` 2 个路由函数 |
| **飞书** | WebSocket 长连接消息处理（lark-oapi SDK，daemon 线程） | `app/飞书/消息处理.py:150` `启动飞书长连接()` / `_处理飞书消息()` |
| **飞书** | 飞书消息去重、过期过滤、自动回复 | `app/飞书/消息处理.py:36` `检查消息去重()` / `app/飞书/消息处理.py:112` `_飞书回复()` |
| **飞书表格** | 多维表格配置 CRUD | `app/api/飞书表格.py:56-141` 4 个路由函数 |
| **系统配置** | 全局配置管理（按分类存储 JSON blob，前端透传） | `app/api/系统配置.py:90-153` 5 个路由函数 |
| **记忆** | 长期记忆 CRUD（按 Agent / 类型过滤，重要性排序） | `app/api/记忆.py:28-85` 3 个路由函数 |
| **记忆** | 对话后异步记忆提取（LLM 调用提取偏好/事实/摘要） | `app/图引擎/记忆管理.py:43` `异步提取记忆()` |
| **记忆** | 对话前注入长期记忆到上下文 | `app/图引擎/上下文.py:24-31` + `app/图引擎/记忆管理.py:170` `获取Agent记忆()` |
| **知识检索** | RAGFlow 知识库检索（有配置则增强，无则跳过） | `app/图引擎/知识检索.py:13` `检索知识库()` |
| **N8N 工作流** | 仅 ORM 模型和前端配置存储，**无后端调用代码** | `app/db/模型.py:183` `N8N工作流模型`（仅表结构） |

---

## 3. API 接口总表

以下接口表从 FastAPI 路由装饰器逐一扫描得出。

### 统一响应格式

```json
{"code": 0, "data": ..., "msg": "ok"}
```

- `code=0` 成功，`code=1` 业务错误，`code=401` 未授权
- HTTP 状态码：200（业务正常/业务错误）、401（鉴权失败）

### 鉴权 — `app/api/鉴权.py`（prefix=`/api/auth`）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| POST | `/api/auth/login` | 无 | `登录()` | 34 |

**请求：**

```json
{"username": "admin", "password": "admin123"}
```

**响应：**

```json
{"code": 0, "data": {"token": "eyJ..."}, "msg": "ok"}
```

### 智能体 — `app/api/智能体.py`（prefix=`/api/agents`）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| GET | `/api/agents` | Bearer | `获取Agent列表()` | 87 |
| POST | `/api/agents` | Bearer | `创建Agent()` | 110 |
| GET | `/api/agents/{agent_id}` | Bearer | `获取Agent详情()` | 144 |
| PUT | `/api/agents/{agent_id}` | Bearer | `更新Agent()` | 153 |
| DELETE | `/api/agents/{agent_id}` | Bearer | `删除Agent()` | 188 |

**创建/更新请求（camelCase）：**

```json
{
  "name": "助手",
  "role": "通用助手",
  "prompt": "你是一个有帮助的助手",
  "llmProvider": "OpenAI",
  "llmModel": "GPT-4o",
  "llmApiUrl": "https://api.openai.com/v1",
  "llmApiKey": "sk-xxx",
  "temperature": 0.7,
  "tools": ["tool-uuid-1", "tool-uuid-2"],
  "maxIterations": 10,
  "timeout": 60,
  "requireApproval": false,
  "status": "running"
}
```

### 对话 — `app/api/对话.py`（无 prefix）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| POST | `/api/chat` | Bearer | `发送消息()` | 304 |
| GET | `/api/conversations` | Bearer | `获取对话列表()` | 394 |
| GET | `/api/conversations/{conversation_id}/messages` | Bearer | `获取消息列表()` | 462 |
| DELETE | `/api/conversations/{conversation_id}` | Bearer | `删除对话()` | 493 |

**POST /api/chat 请求：**

```json
{
  "agent_id": "uuid",
  "conversation_id": "uuid（可选，为空则新建）",
  "message": "你好"
}
```

**响应：** SSE 流，详见第 4 节。

### 工具 — `app/api/工具.py`（prefix=`/api/tools`）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| GET | `/api/tools` | Bearer | `获取工具列表()` | 154 |
| POST | `/api/tools` | Bearer | `创建工具()` | 179 |
| GET | `/api/tools/{tool_id}` | Bearer | `获取单个工具()` | 215 |
| PUT | `/api/tools/{tool_id}` | Bearer | `更新工具()` | 226 |
| DELETE | `/api/tools/{tool_id}` | Bearer | `删除工具()` | 271 |
| POST | `/api/tools/{tool_id}/test` | Bearer | `测试工具()` | 283 |

**创建请求：**

```json
{
  "name": "查天气",
  "tool_type": "http_api",
  "description": "查询天气",
  "config": {
    "url": "https://api.weather.com/v1?city={city}",
    "method": "GET",
    "headers": {}
  },
  "parameters": {
    "type": "object",
    "properties": {
      "city": {"type": "string", "description": "城市名"}
    },
    "required": ["city"]
  }
}
```

**工具类型：** `http_api`（HTTP 请求）、`python_code`（Python 沙箱执行）。

### 日志 — `app/api/日志.py`（无 prefix）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| POST | `/api/logs/push` | Bearer | `push_log()` | 56 |
| GET | `/api/logs/sse-token` | Bearer | `get_sse_token()` | 82 |
| GET | `/api/logs/stream` | Query Token（sse-token） | `log_stream()` | 99 |
| GET | `/api/logs/history` | Bearer | `log_history()` | 166 |

**POST /api/logs/push 请求：**

```json
{
  "task_id": "task_001",
  "machine": "worker-1",
  "level": "进行中",
  "msg": "正在执行步骤 3",
  "time": "2025-01-15 10:30:00（可选，为空则取服务器时间）"
}
```

**GET /api/logs/sse-token 响应：**

```json
{"code": 0, "data": {"token": "eyJ...", "expires_in": 180}}
```

**GET /api/logs/history 参数：** `task_id`（可选）、`since_seq`（增量，默认 0）、`page_size`（默认 200，最大 1000）。

### 定时任务 — `app/api/定时任务.py`（prefix=`/api/schedules`）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| GET | `/api/schedules` | Bearer | `获取定时任务列表()` | 120 |
| POST | `/api/schedules` | Bearer | `创建定时任务()` | 143 |
| PUT | `/api/schedules/{schedule_id}` | Bearer | `更新定时任务()` | 185 |
| DELETE | `/api/schedules/{schedule_id}` | Bearer | `删除定时任务()` | 263 |

**创建请求：**

```json
{
  "name": "每日报告",
  "agentId": "uuid",
  "triggerType": "cron",
  "cronExpression": "0 8 * * *",
  "inputMessage": "请生成今日报告",
  "enabled": true
}
```

**触发类型：** `cron`（Cron 表达式）、`interval`（定时间隔，需 `intervalValue` + `intervalUnit`）、`once`（一次性，需 `executeTime`）。

### 编排 — `app/api/编排.py`（prefix=`/api`）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| GET | `/api/orchestration` | Bearer | `获取编排配置()` | 27 |
| POST | `/api/orchestration` | Bearer | `保存编排配置()` | 45 |

**请求：**

```json
{
  "mode": "Supervisor",
  "entryAgent": "agent-uuid",
  "routingRules": "...",
  "parallelGroups": "...",
  "globalState": [{"key": "k", "desc": "描述"}]
}
```

### 系统配置 — `app/api/系统配置.py`（prefix=`/api/config`）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| GET | `/api/config` | Bearer | `获取全部配置()` | 90 |
| POST | `/api/config` | Bearer | `保存全部配置_POST()` | 115 |
| PUT | `/api/config` | Bearer | `保存全部配置_PUT()` | 121 |
| GET | `/api/config/{category}` | Bearer | `获取分类配置()` | 127 |
| DELETE | `/api/config/{category}` | Bearer | `删除分类配置()` | 146 |

**请求体示例：**

```json
{
  "email": {"smtpServer": "smtp.example.com", "smtpPort": 465},
  "feishu": {"appId": "cli_xxx", "appSecret": "xxx"},
  "n8n": {"apiUrl": "http://localhost:5678"}
}
```

> **注意：** 系统配置仅做 JSON blob 存储和透传，后端不对 email/n8n 等分类做功能性调用。飞书分类由 `app/飞书/配置与会话.py` 的 `读取飞书配置()` 读取使用。

### 飞书表格 — `app/api/飞书表格.py`（prefix=`/api/feishu/tables`）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| GET | `/api/feishu/tables` | Bearer | `获取全部表格()` | 56 |
| POST | `/api/feishu/tables` | Bearer | `新增表格()` | 70 |
| PUT | `/api/feishu/tables/{record_id}` | Bearer | `更新表格()` | 101 |
| DELETE | `/api/feishu/tables/{record_id}` | Bearer | `删除表格()` | 129 |

**请求：**

```json
{
  "name": "客户表",
  "appToken": "bascnXXX",
  "tableId": "tblXXX",
  "description": "客户信息表"
}
```

### 记忆 — `app/api/记忆.py`（无 prefix）

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| GET | `/api/memories` | Bearer | `获取记忆列表()` | 28 |
| DELETE | `/api/memories/{memory_id}` | Bearer | `删除记忆()` | 66 |
| DELETE | `/api/memories?agent_id=xxx` | Bearer | `清空记忆()` | 77 |

### 其他 — `app/启动器.py`

| Method | Path | 鉴权 | 函数 | 行号 |
|--------|------|------|------|------|
| GET | `/api/health` | 无 | `健康检查()` | 112 |

### 错误码

| code | HTTP Status | 说明 |
|------|-------------|------|
| 0 | 200 | 成功 |
| 1 | 200 | 业务错误（参数校验失败、资源不存在等） |
| 401 | 401 | 未授权（无 token / token 无效 / token 过期） |

---

## 4. SSE 协议

系统有两条 SSE 管线，协议细节差异较大。

### 4.1 对话流 — `POST /api/chat`

> 代码位置：`app/api/对话.py:126` `SSE生成器()`、`app/api/对话.py:211` `多Agent_SSE生成器()`

**鉴权方式：** 标准 Bearer 令牌（通过 `Authorization` 请求头，鉴权中间件统一处理）。

**前端调用方式：** `fetch()` + `ReadableStream` 解析（非 EventSource，因为是 POST 请求）。

**响应格式：** `text/event-stream`，每个事件仅包含 `data:` 行，**不包含 `id:` 行**。

**SSE 特性支持：**

| 特性 | 是否支持 | 代码证据 |
|------|----------|----------|
| `id:` 事件 ID | 不支持 | `yield f"data: {json.dumps(...)}\n\n"` — 无 id 行 |
| `Last-Event-ID` 断线续传 | 不支持 | 未读取 `Last-Event-ID` header |
| 心跳 | 不支持 | 生成器中无心跳逻辑 |
| 历史补发 | 不适用 | POST 请求，每次是新的 LLM 调用 |

**事件类型（`type` 字段）：**

| type | 时机 | payload |
|------|------|---------|
| `conversation_id` | 首个事件 | `{"type":"conversation_id","content":"uuid"}` |
| `agent` | Agent 开始响应 | `{"type":"agent","name":"助手"}` |
| `token` | 每个 LLM token | `{"type":"token","content":"你"}` |
| `tool_call` | 工具调用开始 | `{"type":"tool_call","name":"工具名","args":{...}}` |
| `tool_result` | 工具调用完成 | `{"type":"tool_result","name":"工具名","result":"..."}` |
| `done` | 流结束 | `{"type":"done","content":"完整回复文本"}` |
| `error` | 异常 | `{"type":"error","content":"错误描述"}` |

**tool_result 截断：** 结果文本截断为 `TOOL_RESULT_MAX_LEN`（默认 500）字符，见 `对话.py:177`。

**多 Agent 模式：** 当编排配置存在（`orchestration` 表 `id=default`）且有 >=2 个 `status=running` 的 Agent 时，自动切换为 `多Agent_SSE生成器`。`agent` 事件会在 Agent 切换时多次出现，`name` 取自 `event.metadata.langgraph_node`（`对话.py:235`）。

**响应头（代码: `对话.py:386-390`）：**

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### 4.2 日志流 — `GET /api/logs/stream`

> 代码位置：`app/api/日志.py:99` `log_stream()`

**鉴权方式：** Query Token（短期 SSE 令牌，非 Bearer header）。

EventSource API 无法发送自定义 header，因此日志流采用专用的短期令牌方案：

```
1. 前端用 Bearer token 调用 GET /api/logs/sse-token（日志.py:82）
   → 获得 3 分钟有效的 JWT（scope=sse）

2. 拼入 URL: new EventSource("/api/logs/stream?token=<sse-token>")

3. /api/logs/stream 端点自行验证 query token（日志.py:102-115）:
   - 缺少 token → 401
   - JWT 解码失败或过期 → 401
   - scope != "sse" → 401（登录 JWT 不被接受）
```

**SSE 特性支持：**

| 特性 | 是否支持 | 代码证据 |
|------|----------|----------|
| `id:` 事件 ID | **支持** | `yield f"id: {entry['seq']}\ndata: ...\n\n"` — 日志.py:138, 148 |
| `Last-Event-ID` 断线续传 | **支持** | `last_event_id = request.headers.get("last-event-id", "")` — 日志.py:117 |
| 心跳 | **支持** | `yield ": heartbeat\n\n"` 每 15 秒 — 日志.py:151 |
| 历史补发 | **支持** | 连接时查 DB 中 `id > last_seq` 的记录，最多 500 条 — 日志.py:128-139 |

**SSE 令牌 JWT 载荷（日志.py:94）：**

```json
{"sub": "admin", "scope": "sse", "exp": 1700000000}
```

**事件格式：**

```
id: 42
data: {"seq":42,"time":"2025-01-15 10:30:00","task_id":"task_001","machine":"worker-1","level":"进行中","msg":"步骤 3 完成"}

```

- `id` 字段为日志自增序号（`push_logs.id`），客户端通过 `Last-Event-ID` 实现断线续传
- 连接建立时先从 DB 补发 `> last_seq` 的历史日志（上限 `LOG_HISTORY_LIMIT`，默认 500 条）
- 实时日志通过 `asyncio.Queue` 广播：`push_log()` 写入 DB 后向所有 `clients` 集合中的 queue 推送（日志.py:72-76）
- 无新日志时每 15 秒发送 `: heartbeat\n\n` 保持连接（`asyncio.wait_for(queue.get(), timeout=15)` — 日志.py:145）

**响应头（代码: 日志.py:158-162）：**

```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

**Nginx 配置要点（`Agent/nginx.conf`）：**

`/api/logs/stream` 和 `/api/chat` 均需要以下配置以支持 SSE：

```nginx
proxy_http_version 1.1;
proxy_set_header Connection '';
chunked_transfer_encoding off;
proxy_buffering off;
proxy_cache off;
```

区别：`/api/logs/stream` 的 `proxy_read_timeout` 为 `86400s`（长连接），`/api/chat` 为 `300s`。

---

## 5. SQLite 数据模型

> 数据来源：`app/db/模型.py`，逐表提取。

数据库文件：`data/app.db`（通过 `DATABASE_URL` 环境变量可配置，默认 `sqlite:///./data/app.db`）。

ORM 使用中文属性名 + 英文列名映射，启动时调用 `Base.metadata.create_all()` 自动建表（`数据库.py:40`）。

### 表 1: `users` — 用户（模型.py:20）

| ORM 属性 | 列名 | 类型 | 约束 |
|----------|------|------|------|
| id | id | Integer | PK, autoincrement |
| 用户名 | username | String(50) | unique, not null |
| 密码哈希 | password_hash | String(255) | not null |
| 创建时间 | created_at | DateTime | default now |

### 表 2: `agents` — 智能体（模型.py:30）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| 名称 | name | String(100) | not null |
| 角色 | role | String(500) | "" |
| 提示词 | prompt | Text | "" |
| 提供商 | llm_provider | String(50) | "OpenAI" |
| 模型名称 | llm_model | String(50) | "GPT-4o" |
| 接口地址 | llm_api_url | String(500) | "" |
| 接口密钥 | llm_api_key | String(500) | ""（AES 加密存储） |
| 温度 | temperature | Float | 0.7 |
| 工具列表 | tools | Text | "[]"（JSON 数组，存工具 UUID） |
| 最大迭代 | max_iterations | Integer | 10 |
| 超时时间 | timeout_seconds | Integer | 60 |
| 需要审批 | require_approval | Boolean | false |
| 状态 | status | String(20) | "stopped" |
| 更新时间 | updated_at | DateTime | auto |
| 创建时间 | created_at | DateTime | auto |

### 表 3: `conversations` — 对话（模型.py:71）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| agent_id | agent_id | String(36) | not null |
| 标题 | title | String(200) | "新对话" |
| 来源 | source | String(20) | "web" |
| 更新时间 | updated_at | DateTime | auto |
| 创建时间 | created_at | DateTime | auto |

### 表 4: `messages` — 消息（模型.py:83）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| 对话id | conversation_id | String(36) | not null |
| 角色 | role | String(20) | not null |
| 内容 | content | Text | "" |
| agent名称 | agent_name | String(100) | "" |
| tool_calls | tool_calls | Text | None |
| tool_call_id | tool_call_id | String(36) | None |
| 创建时间 | created_at | DateTime | auto |

### 表 5: `tools` — 工具（模型.py:97）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| 名称 | name | String(100) | not null |
| 描述 | description | Text | "" |
| 类型 | tool_type | String(20) | "http_api" |
| 参数定义 | parameters | Text | "{}" |
| 配置 | config | Text | "{}" |
| 状态 | status | String(20) | "active" |
| 创建时间 | created_at | DateTime | auto |
| 更新时间 | updated_at | DateTime | auto |

### 表 6: `schedules` — 定时任务（模型.py:112）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| 名称 | name | String(100) | not null |
| 描述 | description | Text | "" |
| agent_id | agent_id | String(36) | not null |
| 触发类型 | trigger_type | String(20) | "cron" |
| 触发配置 | trigger_config | Text | "{}" |
| 提示词 | prompt | Text | "" |
| 启用 | enabled | Boolean | true |
| 上次运行 | last_run_at | DateTime | null |
| 下次运行 | next_run_at | DateTime | null |
| 创建时间 | created_at | DateTime | auto |
| 更新时间 | updated_at | DateTime | auto |

### 表 7: `schedule_logs` — 任务执行记录（模型.py:130）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| schedule_id | schedule_id | String(36) | not null |
| 状态 | status | String(20) | "running" |
| 结果 | result | Text | "" |
| 错误 | error | Text | None |
| 开始时间 | started_at | DateTime | auto |
| 结束时间 | finished_at | DateTime | None |

### 表 8: `orchestration` — 编排配置（模型.py:143）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | "default" |
| 模式 | mode | String(20) | "Supervisor" |
| 入口agent_id | entry_agent_id | String(36) | "" |
| 路由规则 | routing_rules | Text | "" |
| 并行分组 | parallel_groups | Text | "" |
| 全局状态 | global_state | Text | "[]" |
| 更新时间 | updated_at | DateTime | auto |

### 表 9: `system_config` — 系统配置（模型.py:156）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| 分类 | category | String(50) | not null |
| 键 | key | String(100) | not null |
| 值 | value | Text | "" |
| 说明 | description | String(200) | "" |
| 创建时间 | created_at | DateTime | auto |
| 更新时间 | updated_at | DateTime | auto |

### 表 10: `feishu_tables` — 飞书表格（模型.py:169）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| 名称 | name | String(100) | not null |
| app_token | app_token | String(200) | not null |
| table_id | table_id | String(200) | not null |
| 描述 | description | Text | "" |
| 字段映射 | field_mapping | Text | "{}"（ORM 中存在但 API 未暴露） |
| 创建时间 | created_at | DateTime | auto |
| 更新时间 | updated_at | DateTime | auto |

### 表 11: `n8n_workflows` — N8N 工作流（模型.py:183）

> **注意：** 仅 ORM 模型存在，无后端功能代码调用 N8N API。该表仅供前端配置存储。

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| 名称 | name | String(100) | not null |
| webhook_url | webhook_url | String(500) | not null |
| 描述 | description | Text | "" |
| 请求方法 | method | String(10) | "POST" |
| 请求头 | headers | Text | "{}" |
| 示例载荷 | sample_payload | Text | "{}" |
| 启用 | enabled | Boolean | true |
| 创建时间 | created_at | DateTime | auto |
| 更新时间 | updated_at | DateTime | auto |

### 表 12: `memories` — 长期记忆（模型.py:199）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | String(36) | PK |
| agent_id | agent_id | String(36) | not null |
| conversation_id | conversation_id | String(36) | null |
| 记忆类型 | memory_type | String(20) | "summary" |
| 内容 | content | Text | not null |
| 重要性 | importance | Float | 0.5 |
| 创建时间 | created_at | DateTime | auto |
| 过期时间 | expires_at | DateTime | null |

### 表 13: `push_logs` — 推送日志（模型.py:213）

| ORM 属性 | 列名 | 类型 | 默认值 |
|----------|------|------|--------|
| id | id | Integer | PK, autoincrement（即 seq） |
| 时间 | time | String(30) | "" |
| 任务ID | task_id | String(100) | "未知任务" |
| 设备 | machine | String(100) | "未知设备" |
| 级别 | level | String(20) | "进行中" |
| 消息 | msg | Text | "" |
| 创建时间 | created_at | DateTime | auto |

---

## 6. 本地启动与 Docker 部署

### 6.1 环境变量

在 `backend/.env` 中配置（或通过系统环境变量）：

| 变量名 | 默认值 | 说明 | 代码位置 |
|--------|--------|------|----------|
| `JWT_SECRET_KEY` | 随机生成 | JWT 签名密钥，未设置则每次重启生成新密钥 | `配置.py:16-21` |
| `JWT_EXPIRE_HOURS` | 24 | JWT 过期时间（小时） | `配置.py:22` |
| `DATABASE_URL` | `sqlite:///./data/app.db` | 数据库连接串 | `配置.py:26` |
| `CORS_ORIGINS` | `*` | CORS 允许源，多个用逗号分隔 | `配置.py:29-33` |
| `OPENAI_API_KEY` | "" | 默认 OpenAI API Key | `配置.py:41` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI 兼容 API 地址 | `配置.py:42` |
| `DEFAULT_MODEL` | `gpt-4o-mini` | 默认模型 | `配置.py:43` |
| `MAX_HISTORY_ROUNDS` | 10 | 对话历史保留轮数 | `配置.py:46` |
| `MAX_TOKENS` | 4000 | 最大 token 数 | `配置.py:47` |
| `RAGFLOW_BASE_URL` | `http://localhost:9380` | RAGFlow 地址 | `配置.py:50` |
| `RAGFLOW_API_KEY` | "" | RAGFlow API Key（为空则不检索） | `配置.py:51` |
| `RAGFLOW_DATASET_IDS` | "" | RAGFlow 数据集 ID（逗号分隔，为空则不检索） | `配置.py:52` |
| `DEFAULT_ADMIN_PASSWORD` | admin123 | 首次启动创建的 admin 用户密码 | `数据库.py:46` |
| `ENCRYPTION_KEY` | 取 `JWT_SECRET_KEY` | API Key AES 加密密钥 | `加密.py:14` |

### 6.2 本地启动

**后端：**

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/macOS

pip install -r requirements.txt
uvicorn app.启动器:app --host 0.0.0.0 --port 8001
```

**前端：**

```bash
cd Agent
npm install
npm run dev                  # 开发模式，默认端口 3000
# npm run build             # 生产构建
```

首次启动时自动创建默认用户 `admin`，密码取 `DEFAULT_ADMIN_PASSWORD` 环境变量（默认 `admin123`）。见 `数据库.py:38-57`。

### 6.3 Docker 部署

**后端（`backend/Dockerfile` + `backend/docker-compose.yml`）：**

```bash
cd backend
docker-compose up -d --build
```

- 基础镜像: `python:3.11-slim`
- 端口映射: `8001:8001`
- 数据卷: `./data` → `/app/data`（SQLite 持久化）
- 环境变量: `./.env` → `/app/.env`
- 启动命令: `uvicorn app.启动器:app --host 0.0.0.0 --port 8001`

**前端（`Agent/Dockerfile` + `Agent/docker-compose.yml`）：**

```bash
cd Agent
docker-compose up -d --build
```

- 构建阶段: `node:22-alpine` → `npm run build`
- 运行阶段: `nginx:alpine` → 静态文件 + `nginx.conf`
- 端口映射: `1254:80`

**前后端联合部署：** `Agent/docker-compose.yml` 中有后端服务的注释模板，取消注释即可。前端 Nginx 通过 `proxy_pass http://backend:8001` 反代后端 API。

### 6.4 可调常量

定义在 `backend/app/常量.py`，按用途分组：

| 常量 | 默认值 | 说明 |
|------|--------|------|
| `PYTHON_TOOL_EXEC_TIMEOUT` | 10s | Python 沙箱执行超时 |
| `LLM_HTTP_TIMEOUT` | 30s | 记忆提取 LLM 调用超时 |
| `RAGFLOW_TIMEOUT` | 15s | RAGFlow 知识检索超时 |
| `FEISHU_AGENT_TIMEOUT` | 120s | 飞书智能体调用最大等待 |
| `FEISHU_SESSION_TIMEOUT` | 1800s | 飞书会话超时（30 分钟） |
| `FEISHU_DEDUP_LIMIT` | 5000 | 飞书消息去重集合上限 |
| `FEISHU_MSG_EXPIRE` | 120s | 飞书消息过期阈值 |
| `FEISHU_MSG_MAX_LEN` | 4000 | 飞书回复消息长度限制 |
| `FEISHU_MAX_RETRY` | 3 | 飞书智能体调用最大重试 |
| `LOG_RETENTION_DAYS` | 30 | 日志保留天数 |
| `LOG_HISTORY_LIMIT` | 500 | SSE 连接时历史日志补发上限 |
| `LOG_DEFAULT_PAGE_SIZE` | 200 | 日志历史查询默认分页 |
| `TOOL_RESULT_MAX_LEN` | 500 | 工具结果截断字符数 |
| `HTTP_TOOL_RESULT_MAX_LEN` | 2000 | HTTP 工具响应截断字符数 |
| `SCHEDULER_MISFIRE_GRACE` | 60s | APScheduler 错过触发容忍 |
| `SCHEDULER_RESULT_MAX_LEN` | 5000 | 调度器任务结果截断 |
| `SCHEDULER_ERROR_MAX_LEN` | 2000 | 调度器错误信息截断 |
| `MEMORY_DEFAULT_LIMIT` | 10 | 记忆查询默认条数 |
| `MEMORY_SUMMARY_LIMIT` | 5 | 最近摘要查询条数 |
| `MEMORY_EXTRACTION_TEMPERATURE` | 0.3 | 记忆提取 LLM 温度 |
| `MEMORY_EXTRACTION_MAX_TOKENS` | 500 | 记忆提取最大 token |
| `RAGFLOW_DEFAULT_TOP_K` | 3 | 知识检索默认 top_k |
| `CONV_TITLE_MAX_LEN` | 20 | 对话标题截断长度 |
| `CONVERSATION_TEXT_MAX_LEN` | 6000 | 记忆提取对话文本截断 |

### 6.5 主要依赖

来自 `backend/requirements.txt`：

| 包 | 版本 | 用途 |
|----|------|------|
| fastapi | 0.115.* | Web 框架 |
| uvicorn[standard] | 0.34.* | ASGI 服务器 |
| sqlalchemy | 2.0.* | ORM |
| python-jose[cryptography] | 3.3.* | JWT 签发/验证 |
| passlib[bcrypt] + bcrypt | 1.7.* / 4.0.1 | 密码哈希 |
| pydantic | 2.10.* | 请求/响应模型 |
| langgraph | >=0.2.0 | Agent 图执行引擎 |
| langgraph-supervisor | >=0.0.31 | Supervisor 模式多 Agent |
| langgraph-swarm | >=0.1.0 | Swarm 模式多 Agent |
| langchain / langchain-openai / langchain-core | >=0.3.0 | LLM 抽象层 |
| httpx | >=0.27.0 | 异步 HTTP 客户端（工具调用、RAGFlow、记忆提取） |
| lark-oapi | >=1.3.0 | 飞书开放平台 SDK（WebSocket 长连接） |
| apscheduler | >=3.10.0 | 定时任务调度 |
| cryptography | >=42.0.0 | AES-256-CBC 加密（API Key 存储） |
| RestrictedPython | >=7.0 | Python 代码沙箱编译 |

---

## 7. 安全与回归测试

### 7.1 安全机制

#### JWT 鉴权（`app/middleware/鉴权中间件.py`）

免鉴权路径白名单（`鉴权中间件.py:10-17`，使用 `startswith` 匹配）：

| 路径 | 说明 |
|------|------|
| `/api/auth/login` | 登录接口 |
| `/api/health` | 健康检查 |
| `/api/logs/stream` | SSE 日志流（端点内部自行验证 query token） |
| `/docs` | FastAPI Swagger UI |
| `/openapi.json` | OpenAPI Schema |
| `/redoc` | ReDoc UI |

其他所有 `/api/*` 路径均需 `Authorization: Bearer <token>` 头。

**SSE 令牌隔离：** `/api/logs/stream` 仅接受 `scope=sse` 的短期令牌（3 分钟），登录 JWT（无 scope 字段）不被接受，防止登录令牌泄露到 URL（`日志.py:109-110`）。

#### Python 沙箱 — 7 层纵深防御（`app/图引擎/工具加载器.py` + `_沙箱执行器.py`）

| 层 | 措施 | 代码位置 |
|----|------|----------|
| L1 | RestrictedPython `compile_restricted` — 编译期阻断 `_` 前缀属性访问 | `_沙箱执行器.py` |
| L2 | 受限 builtins 白名单 — 无 `__import__`、`open`、`getattr`、`type` | `_沙箱执行器.py` |
| L3 | 子进程隔离（`subprocess.Popen`，独立 PID） | `工具加载器.py:213` |
| L4 | 禁网 — 环境变量剥离 + runner 内 import hook 阻断网络模块 | `工具加载器.py:192-210` |
| L5 | 文件系统限制 — cwd 设为空 `tempfile.mkdtemp()`，builtins 无 open | `工具加载器.py:187` |
| L6 | Windows Job Object（128MB 内存 + 禁止创建子进程） | `工具加载器.py:33-96` `_创建受限Job()` |
| L7 | `subprocess.communicate(timeout=N)` 超时终止 | `工具加载器.py:237` |

#### API Key 安全（`app/加密.py`）

- Agent 的 `llm_api_key` 使用 AES-256-CBC 加密存储，密文前缀 `enc:`（`加密.py:17`）
- 创建/更新 Agent 时调用 `加密()`（`智能体.py:128, 175`），读取时调用 `解密()`（`智能体.py:74`）
- 飞书渠道日志中仅记录"已配置"/"未配置"，不泄露 API Key 内容

### 7.2 回归测试套件

#### test_sandbox — Python 沙箱安全测试

**路径：** `tests/security/test_sandbox.py`

**运行：**

```bash
cd backend
python -m pytest ../tests/security/test_sandbox.py -v
```

| 用例 | 攻击方式 | 防御层 | 预期 |
|------|----------|--------|------|
| test_01 | `import os` 顶层 | L2（builtins 无 `__import__`） | NameError |
| test_02 | `open()` 读文件 | L2（builtins 无 `open`） | NameError |
| test_03 | `__import__('os')` 显式 | L1（编译期拒绝 `_` 前缀标识符） | 编译错误 |
| test_04 | `().__class__.__bases__` MRO 链 | L1（编译期拒绝 `_` 前缀属性） | 编译错误 |
| test_05 | `while True: pass` 死循环 | L7（subprocess timeout） | 超时终止 |
| test_06 | `chr()` 拼出 "socket" | 安全 — 可拼字符串但无法 import | 返回 "socket" |
| test_07 | 大量内存分配 (>128MB) | L6（Job Object） | 进程被终止 |
| test_08 | `import subprocess` 函数内 | L2（builtins 无 `__import__`） | NameError |
| test_09 | `import os` 运行期阻断 | L2（builtins 白名单） | NameError |
| test_10 | socket/connect 网络探测（4 项子测试） | L4（import hook + sys.modules） | 全部 BLOCKED |
| test_positive | `sum(range(100))` 合法代码 | — | 返回 "4950" |

#### test_sse_token_auth — SSE 鉴权回归测试

**路径：** `tests/regression/test_sse_token_auth.py`

**运行：**

```bash
cd backend
python -m pytest ../tests/regression/test_sse_token_auth.py -v
```

| 用例 | 说明 | 预期 |
|------|------|------|
| test_stream_no_token_returns_401 | 无 token 访问 `/api/logs/stream` | 401 |
| test_stream_invalid_token_returns_401 | 错误 token 访问 stream | 401 |
| test_stream_login_jwt_rejected | 登录 JWT 访问 stream（scope!=sse） | 401 |
| test_sse_token_requires_auth | 无 Bearer 访问 `/api/logs/sse-token` | 401 |
| test_sse_token_issued_with_correct_expiry | 已登录用户获取 sse-token | 200, expires_in=180 |
| test_sse_token_has_sse_scope | sse-token JWT 包含 scope=sse | scope=sse, 含 exp/sub |
| test_push_then_history_shows_log | push → history 端到端数据链路 | 数据一致 |

#### test_p02_tool_query — 工具查询字段回归测试

**路径：** `tests/regression/test_p02_tool_query.py`

**运行：**

```bash
cd backend
python -m pytest ../tests/regression/test_p02_tool_query.py -v
```

| 用例 | 说明 | 预期 |
|------|------|------|
| test_p02_query_by_id_returns_tool | 用工具 UUID 查询返回该工具 | 1 条结果 |
| test_p02_query_by_name_must_miss | 用名称冒充 ID 查询返回空 | 0 条结果 |

### 7.3 运行全部测试

```bash
cd backend
python -m pytest ../tests/ -v
```

---

## 8. 统一工具管理（规划 / Proposal）

> **本章为改造提案，尚未落地到代码。**
> 凡涉及 `builtin` 工具类型、`ToolResult` 返回结构、内置工具注册表、提取公共函数 `查询Agent工具记录()`、
> 删除三处重复工具加载代码等内容，均为**计划中的设计**，当前代码库中尚未实现。
> 已实现部分（`http_api` / `python_code` 两种工具类型、现有 CRUD API、Python 沙箱 7 层防御）
> 在本章中会明确标注"当前已实现"。

### 8.1 目标与范围

**当前存在的问题：**

1. **工具加载逻辑散布在 3 个文件中，结构完全重复** — `对话.py:92-121`（Web 对话）、`飞书/配置与会话.py:80-106`（飞书）、`调度器.py:190-214`（定时任务）各自独立实现"解析工具ID列表 → 查 DB → 组装字典"的相同逻辑。
2. **执行返回结构不统一** — `执行HTTP工具()` 返回 `"HTTP 200\n{body}"`（字符串拼接），`执行Python工具()` 返回 `"错误：..."` 或纯结果字符串，没有统一的 `success/error` 判断标准。调用方（`api/工具.py:306`）用 `startswith("错误")` 做成败判断，脆弱且不可靠。
3. **不支持内置工具** — 当前 `tool_type` 仅有 `http_api` 和 `python_code`。系统内置能力（如发邮件、获取时间戳、文件摘要）无标准接入方式。N8N 工作流已有 ORM 模型（`模型.py:183`）但无任何调用代码。
4. **工具测试端点（`POST /api/tools/{id}/test`）与对话中的工具调用走不同路径** — 测试端点直接调用 `执行HTTP工具/执行Python工具`（`api/工具.py:299-305`），而对话通过 `加载工具列表()` 转为 `StructuredTool` 后由 LangGraph 调用。两条路径的错误处理、超时逻辑、日志记录各不相同。

**计划统一后的覆盖范围：**

| 工具类型 | tool_type 值 | 执行方式 | 沙箱限制 | 状态 |
|----------|-------------|----------|----------|------|
| HTTP API 调用 | `http_api` | `httpx.AsyncClient`，支持 GET/POST/PUT/DELETE | 无代码执行；timeout 由 `config.timeout` 控制（默认 30s） | 当前已实现 |
| Python 沙箱代码 | `python_code` | 子进程 + RestrictedPython 7 层纵深防御 | L1-L7 全部启用（见 §7.1） | 当前已实现 |
| 内置工具 | `builtin` | 主进程内直接调用已注册的 Python 函数 | 由开发者编写的受信代码，无沙箱限制 | **计划新增** |

**明确不在范围内的：**

- N8N 工作流执行 — ORM 模型已存在，但等 N8N 对接方案确定后再接入
- MCP (Model Context Protocol) — 未来可作为第 4 种 `tool_type` 加入，当前不计划实现
- 工具版本管理 — 当前单实例部署，暂无版本控制需求

### 8.2 统一的工具模型（数据库 / Schema）

#### 8.2.1 tools 表现状（计划无需改表）

当前 `工具模型`（`模型.py:97-108`）字段已足够承载三种工具类型：

| ORM 属性 | 列名 | 类型 | 说明 |
|----------|------|------|------|
| `id` | `id` | `String(36)` PK | UUID |
| `名称` | `name` | `String(100)` NOT NULL | 工具名称（LangChain tool name），**必须唯一**（`api/工具.py:189` 重名校验） |
| `描述` | `description` | `Text` | 工具描述（注入 LLM 系统提示 + StructuredTool.description） |
| `类型` | `tool_type` | `String(20)` | 当前值：`http_api` / `python_code`；计划新增：`builtin` |
| `参数定义` | `parameters` | `Text` (JSON) | JSON Schema 格式，含 `properties`（每个属性需 `type` + `description`） |
| `配置` | `config` | `Text` (JSON) | 因 `tool_type` 不同而不同（见下表） |
| `状态` | `status` | `String(20)` | `active` / `inactive`，仅 `active` 的工具被加载 |
| `创建时间` | `created_at` | `DateTime` | 自动填充 |
| `更新时间` | `updated_at` | `DateTime` | 自动更新 |

**不需要加列的理由：**

- `timeout` → 各类型在 `config` JSON 内部定义（`http_api` 已有 `config.timeout`）
- `retry` → 重试策略仅 HTTP 类型需要，放在 `config.retry_count` 中
- `enabled` → 已有 `status` 字段控制，`active` = 启用

#### 8.2.2 各 tool_type 的 config JSON 结构

**http_api**（当前已实现，`工具加载器.py:127-160`）：

URL 和 headers 支持 `{param}` 占位符，运行时由工具引擎做字符串替换（`工具加载器.py:135-140`）。

```json
{
  "url": "https://api.example.com/users/{user_id}",
  "method": "GET",
  "headers": {
    "Authorization": "Bearer {token}"
  },
  "body_template": "",
  "timeout": 30
}
```

**python_code**（当前已实现，`工具加载器.py:163-277`）：

代码中必须定义 `execute(params) -> str` 函数，在 RestrictedPython 沙箱中运行（详见 §7.1）。

```json
{
  "code": "def execute(params):\n    return str(params.get('x', 0) * 2)"
}
```

**builtin**（**计划新增**类型，当前代码中尚未实现）：

`builtin_name` 指向计划中的内置工具注册表中的函数名，`settings` 为传给 builtin 函数的静态配置。

```json
{
  "builtin_name": "send_email",
  "settings": {
    "smtp_host": "smtp.example.com",
    "smtp_port": 465,
    "smtp_user": "bot@example.com",
    "smtp_pass_encrypted": "enc:..."
  }
}
```

#### 8.2.3 parameters JSON Schema 校验规则

已有的深度校验逻辑（`api/工具.py:123-149`，`深度校验参数定义()`）：

```
parameters = {
  "properties": {
    "字段名": {
      "type": "string|number|integer|boolean",    // 必填
      "description": "该参数的用途说明"             // 必填
    }
  },
  "required": ["字段名"]   // 可选，标记必填参数
}
```

`解析参数模型()`（`工具加载器.py:105-124`）将此 JSON Schema 转换为 Pydantic Model，供 LangChain `StructuredTool` 使用。类型映射：`string→str`, `number→float`, `integer→int`, `boolean→bool`。

### 8.3 计划中的统一执行协议（Execution Protocol）

> 以下 §8.3 全部内容为**计划设计**，当前代码中尚未实现。

#### 8.3.1 计划引入的统一返回结构 `ToolResult`

计划让所有工具类型的执行函数统一返回 `ToolResult` dataclass（当前各函数直接返回字符串）：

```python
# 定义位置：工具加载器.py 顶部
from dataclasses import dataclass

@dataclass
class ToolResult:
    success: bool          # 是否成功
    data: str              # 成功时为结果文本，失败时为错误描述
    duration_ms: int = 0   # 执行耗时（毫秒）
    tool_type: str = ""    # 工具类型（http_api / python_code / builtin）
```

#### 8.3.2 计划新增的统一执行入口

计划新增 `执行工具()` 函数，替代现有的分散调用：

```python
# 位置：工具加载器.py

async def 执行工具(工具类型: str, 配置: dict, 参数: dict) -> ToolResult:
    """统一工具执行入口 - 所有调用方（API 测试、对话、定时任务）使用此函数"""
    开始 = time.time()
    try:
        if 工具类型 == "http_api":
            结果文本 = await 执行HTTP工具(配置, 参数)
            成功 = not 结果文本.startswith("HTTP 请求失败") and not 结果文本.startswith("HTTP 请求超时")
        elif 工具类型 == "python_code":
            结果文本 = 执行Python工具(配置, 参数)
            成功 = not 结果文本.startswith("错误") and not 结果文本.startswith("Python")
        elif 工具类型 == "builtin":
            结果文本 = await 执行内置工具(配置, 参数)
            成功 = not 结果文本.startswith("错误")
        else:
            return ToolResult(success=False, data=f"不支持的工具类型: {工具类型}",
                              tool_type=工具类型)
    except Exception as e:
        return ToolResult(success=False, data=f"执行异常: {e}",
                          duration_ms=int((time.time() - 开始) * 1000),
                          tool_type=工具类型)

    return ToolResult(
        success=成功,
        data=结果文本,
        duration_ms=int((time.time() - 开始) * 1000),
        tool_type=工具类型,
    )
```

#### 8.3.3 计划提取的统一工具加载函数

计划将散布在 3 个文件中的重复逻辑提取为共用函数：

```python
# 位置：工具加载器.py（替代现有 对话.py / 飞书/配置与会话.py / 调度器.py 中的重复代码）

def 查询Agent工具记录(db: Session, agent配置: dict) -> list[dict]:
    """从 Agent 配置中解析工具 ID 列表，查询 DB 返回工具记录字典列表。

    所有渠道（Web 对话、飞书、定时任务）统一调用此函数。
    """
    工具ID原始 = agent配置.get("tools", [])
    if isinstance(工具ID原始, str):
        try:
            工具ID列表 = json.loads(工具ID原始)
        except (json.JSONDecodeError, TypeError):
            工具ID列表 = []
    else:
        工具ID列表 = 工具ID原始 or []

    if not 工具ID列表:
        return []

    工具记录 = db.query(工具模型).filter(
        工具模型.id.in_(工具ID列表),
        工具模型.状态 == "active"
    ).all()

    return [
        {
            "name": t.名称,
            "description": t.描述,
            "tool_type": t.类型,
            "parameters": t.参数定义,
            "config": t.配置,
        }
        for t in 工具记录
    ]
```

计划的调用方改造：

| 文件 | 现状 | 计划改造为 |
|------|------|-----------|
| `对话.py:92-121` | `获取Agent工具记录()` 自行实现 | 计划改为 `from app.图引擎.工具加载器 import 查询Agent工具记录` |
| `飞书/配置与会话.py:80-106` | 内联 20 行重复代码 | 计划改为 `from app.图引擎.工具加载器 import 查询Agent工具记录` |
| `调度器.py:190-214` | 内联 24 行重复代码 | 计划改为 `from app.图引擎.工具加载器 import 查询Agent工具记录` |

#### 8.3.4 执行日志关联（远期规划）

当前工具执行不记录日志。统一执行入口落地后，可在将来添加执行日志，关联结构如下：

```
Agent (agents.id) → 工具列表 (JSON 数组) → 工具 (tools.id)
                                               ↓
对话 (conversations.id)                    执行工具() → ToolResult
   ↓                                          ↓
消息 (messages.tool_calls / tool_call_id)  [将来] 工具执行日志表
```

当前阶段不新建日志表。计划中 `ToolResult.duration_ms` 将供 `/api/tools/{id}/test` 返回给前端显示，对话中的工具执行结果继续通过 SSE `tool_result` 事件推送。

### 8.4 API 设计

现有 API 路径和方法不需要改动。计划仅调整 `测试工具()` 的内部实现（改用 `ToolResult` + 支持 `builtin` 类型）。以下是完整的工具 API 列表及示例。

#### 8.4.1 接口总表（当前已实现）

| 方法 | 路径 | 功能 | 鉴权 | 代码位置 |
|------|------|------|------|----------|
| GET | `/api/tools` | 工具列表（分页） | Bearer | `api/工具.py:154` `获取工具列表()` |
| POST | `/api/tools` | 创建工具 | Bearer | `api/工具.py:179` `创建工具()` |
| GET | `/api/tools/{tool_id}` | 获取单个工具 | Bearer | `api/工具.py:215` `获取单个工具()` |
| PUT | `/api/tools/{tool_id}` | 更新工具 | Bearer | `api/工具.py:226` `更新工具()` |
| DELETE | `/api/tools/{tool_id}` | 删除工具 | Bearer | `api/工具.py:271` `删除工具()` |
| POST | `/api/tools/{tool_id}/test` | 测试执行工具 | Bearer | `api/工具.py:283` `测试工具()` |

#### 8.4.2 创建 HTTP API 工具（当前已支持）

```bash
curl -X POST http://localhost:8001/api/tools \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "查询天气",
    "description": "根据城市名查询当前天气信息",
    "tool_type": "http_api",
    "parameters": {
      "properties": {
        "city": {"type": "string", "description": "城市名称，如 北京"}
      },
      "required": ["city"]
    },
    "config": {
      "url": "https://api.weather.com/v1/current?city={city}",
      "method": "GET",
      "headers": {"X-Api-Key": "weather-key-123"},
      "timeout": 10
    }
  }'
```

响应：

```json
{
  "code": 0,
  "data": {
    "id": "a1b2c3d4-...",
    "name": "查询天气",
    "description": "根据城市名查询当前天气信息",
    "tool_type": "http_api",
    "parameters": {
      "properties": {"city": {"type": "string", "description": "城市名称，如 北京"}},
      "required": ["city"]
    },
    "config": {
      "url": "https://api.weather.com/v1/current?city={city}",
      "method": "GET",
      "headers": {"X-Api-Key": "weather-key-123"},
      "timeout": 10
    },
    "status": "active",
    "created_at": "2026-02-28 10:00:00",
    "updated_at": "2026-02-28 10:00:00"
  },
  "msg": "ok"
}
```

#### 8.4.3 创建 Python 沙箱工具（当前已支持）

```bash
curl -X POST http://localhost:8001/api/tools \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "计算器",
    "description": "执行数学计算，支持加减乘除和幂运算",
    "tool_type": "python_code",
    "parameters": {
      "properties": {
        "expression": {"type": "string", "description": "数学表达式，如 2+3*4"}
      },
      "required": ["expression"]
    },
    "config": {
      "code": "def execute(params):\n    expr = params.get(\"expression\", \"0\")\n    allowed = set(\"0123456789+-*/.() \")\n    if not all(c in allowed for c in expr):\n        return \"仅支持数字和+-*/运算符\"\n    return str(eval(expr))"
    }
  }'
```

#### 8.4.4 创建内置工具 builtin（计划支持，当前会存入 DB 但执行时返回"不支持的工具类型"）

```bash
curl -X POST http://localhost:8001/api/tools \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "发送邮件",
    "description": "通过 SMTP 发送邮件通知",
    "tool_type": "builtin",
    "parameters": {
      "properties": {
        "to": {"type": "string", "description": "收件人邮箱"},
        "subject": {"type": "string", "description": "邮件主题"},
        "body": {"type": "string", "description": "邮件正文"}
      },
      "required": ["to", "subject", "body"]
    },
    "config": {
      "builtin_name": "send_email",
      "settings": {
        "smtp_host": "smtp.example.com",
        "smtp_port": 465,
        "smtp_user": "bot@example.com",
        "smtp_pass_encrypted": "enc:..."
      }
    }
  }'
```

#### 8.4.5 测试执行工具（当前已支持 http_api / python_code）

```bash
curl -X POST http://localhost:8001/api/tools/a1b2c3d4-.../test \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"test_params": {"city": "北京"}}'
```

响应：

```json
{
  "code": 0,
  "data": {
    "success": true,
    "result": "HTTP 200\n{\"temp\":22,\"weather\":\"晴\"}",
    "duration_ms": 342
  },
  "msg": "ok"
}
```

**计划改造要点：** 将 `api/工具.py:298-312` 的 `if/elif` 分支替换为统一调用 `执行工具(工具类型, 配置, 参数)`，由 `ToolResult` 统一提供 `success`、`data`、`duration_ms`。当前代码中 `测试工具()` 仍使用 `startswith("错误")` 判断成败。

### 8.5 工具注册与加载（计划中的代码落点）

> 以下 §8.5 全部内容为**计划设计**，当前代码中尚未实现。

#### 8.5.1 计划修改的文件清单

| # | 文件 | 修改内容 |
|---|------|----------|
| 1 | `backend/app/图引擎/工具加载器.py` | 计划新增 `ToolResult` dataclass、`执行工具()` 统一入口、`查询Agent工具记录()` 共用函数、`执行内置工具()` 函数；`加载工具列表()` 增加 `builtin` 分支 |
| 2 | **计划新增** `backend/app/图引擎/内置工具/__init__.py` | 内置工具注册表：`_BUILTIN_REGISTRY`、`注册内置工具()` 装饰器、`获取内置工具()` 查找函数 |
| 3 | **计划新增** `backend/app/图引擎/内置工具/邮件.py` | `send_email(settings, params)` — SMTP 发邮件实现 |
| 4 | `backend/app/api/工具.py` | 计划将 `测试工具()` 改为调用 `执行工具()`；创建/更新校验增加 `builtin` 类型的 `config.builtin_name` 检查 |
| 5 | `backend/app/api/对话.py` | 计划删除 `获取Agent工具记录()` 函数（92-121 行），改为 `from app.图引擎.工具加载器 import 查询Agent工具记录` |
| 6 | `backend/app/飞书/配置与会话.py` | 计划删除 80-106 行内联工具加载代码，改为 `from app.图引擎.工具加载器 import 查询Agent工具记录` |
| 7 | `backend/app/调度器.py` | 计划删除 190-214 行内联工具加载代码，改为 `from app.图引擎.工具加载器 import 查询Agent工具记录` |

#### 8.5.2 计划中的内置工具注册表设计

```python
# backend/app/图引擎/内置工具/__init__.py

from typing import Callable, Awaitable

# 注册表：builtin_name -> 执行函数
_BUILTIN_REGISTRY: dict[str, Callable[..., Awaitable[str] | str]] = {}


def 注册内置工具(name: str):
    """装饰器：将函数注册为内置工具"""
    def decorator(func):
        _BUILTIN_REGISTRY[name] = func
        return func
    return decorator


def 获取内置工具(name: str) -> Callable | None:
    return _BUILTIN_REGISTRY.get(name)


# 导入所有内置工具模块（触发注册）
from . import 邮件  # noqa: F401
```

```python
# backend/app/图引擎/内置工具/邮件.py

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.加密 import 解密
from . import 注册内置工具


@注册内置工具("send_email")
async def send_email(settings: dict, params: dict) -> str:
    """通过 SMTP 发送邮件"""
    host = settings.get("smtp_host", "")
    port = int(settings.get("smtp_port", 465))
    user = settings.get("smtp_user", "")
    password = 解密(settings.get("smtp_pass_encrypted", ""))

    to = params.get("to", "")
    subject = params.get("subject", "")
    body = params.get("body", "")

    if not all([host, user, password, to, subject]):
        return "错误：缺少必要的邮件配置或参数"

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP_SSL(host, port, timeout=10) as server:
            server.login(user, password)
            server.send_message(msg)
        return f"邮件已发送至 {to}"
    except Exception as e:
        return f"错误：邮件发送失败 - {e}"
```

#### 8.5.3 计划新增的执行内置工具函数

```python
# 位置：工具加载器.py

async def 执行内置工具(配置: dict, 参数: dict) -> str:
    """执行内置工具"""
    from app.图引擎.内置工具 import 获取内置工具

    builtin_name = 配置.get("builtin_name", "")
    if not builtin_name:
        return "错误：builtin 工具缺少 builtin_name 配置"

    func = 获取内置工具(builtin_name)
    if func is None:
        return f"错误：未知的内置工具 '{builtin_name}'"

    settings = 配置.get("settings", {})

    import asyncio
    if asyncio.iscoroutinefunction(func):
        return await func(settings, 参数)
    else:
        return func(settings, 参数)
```

#### 8.5.4 计划为加载工具列表增加 builtin 分支

计划在现有 `加载工具列表()`（`工具加载器.py:280-318`）中 `if 工具类型 == "http_api"` / `elif 工具类型 == "python_code"` / `else: continue` 的 `else` 分支改为：

```python
elif 工具类型 == "builtin":
    async def _执行builtin(当前配置=配置, **kwargs):
        return await 执行内置工具(当前配置, kwargs)
    工具 = StructuredTool.from_function(
        coroutine=_执行builtin,
        name=工具名称,
        description=工具描述,
        args_schema=参数模型,
    )
else:
    logger.warning("跳过不支持的工具类型: %s (%s)", 工具类型, 工具名称)
    continue
```

#### 8.5.5 LangGraph 集成路径（改造后的目标状态）

改造完成后，工具从 DB 到 LLM 调用的完整链路：

```
Agent 配置 (agents.tools JSON 数组)
    ↓
查询Agent工具记录(db, agent配置)              ← 工具加载器.py（计划提取的统一入口）
    ↓ list[dict]
加载工具列表(工具记录列表)                     ← 工具加载器.py:280
    ↓ list[StructuredTool]
    ├─ http_api    → StructuredTool(coroutine=_执行http)
    ├─ python_code → StructuredTool(func=_执行py)
    └─ builtin     → StructuredTool(coroutine=_执行builtin)
    ↓
构建Agent图(agent配置, 工具记录列表)           ← 构建器.py:100
    ↓
create_react_agent(model=LLM, tools=工具列表)  ← langgraph
    ↓
图.astream_events() / 图.ainvoke()             ← 对话.py / 调度器.py
    ↓
on_tool_start → on_tool_end (SSE 推送)
```

### 8.6 验收标准（改造完成后需通过的测试）

> 以下测试用例为改造完成后的验收标准，当前尚未编写到代码库中。

#### 测试用例 1：HTTP API 工具端到端（基于现有能力，改造后 result 结构变化）

```python
def test_http_tool_e2e(client, auth_token):
    """创建 HTTP 工具 -> 测试执行 -> 验证 ToolResult 结构"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 1. 创建工具
    resp = client.post("/api/tools", json={
        "name": "httpbin_get",
        "tool_type": "http_api",
        "parameters": {
            "properties": {
                "name": {"type": "string", "description": "名称参数"}
            }
        },
        "config": {
            "url": "https://httpbin.org/get?name={name}",
            "method": "GET",
            "timeout": 10
        }
    }, headers=headers)
    assert resp.status_code == 200
    tool_id = resp.json()["data"]["id"]

    # 2. 测试执行
    test_resp = client.post(f"/api/tools/{tool_id}/test", json={
        "test_params": {"name": "test_value"}
    }, headers=headers)
    assert test_resp.status_code == 200
    result = test_resp.json()["data"]
    assert result["success"] is True
    assert "HTTP 200" in result["result"]
    assert result["duration_ms"] > 0

    # 3. 清理
    client.delete(f"/api/tools/{tool_id}", headers=headers)
```

#### 测试用例 2：Python 沙箱工具安全边界（基于现有能力，改造后 result 结构变化）

```python
def test_python_sandbox_boundary(client, auth_token):
    """合法代码成功 + 恶意代码被阻断"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 创建合法工具
    resp = client.post("/api/tools", json={
        "name": "safe_calc",
        "tool_type": "python_code",
        "parameters": {},
        "config": {"code": "def execute(params):\n    return str(sum(range(100)))"}
    }, headers=headers)
    tool_id = resp.json()["data"]["id"]

    # 合法执行 — 应返回 "4950"
    test_resp = client.post(f"/api/tools/{tool_id}/test", json={
        "test_params": {}
    }, headers=headers)
    result = test_resp.json()["data"]
    assert result["success"] is True
    assert result["result"] == "4950"

    # 更新为恶意代码（import os）
    client.put(f"/api/tools/{tool_id}", json={
        "config": {"code": "import os\ndef execute(params):\n    return os.popen('whoami').read()"}
    }, headers=headers)

    # 恶意执行 — 应被沙箱阻断
    test_resp = client.post(f"/api/tools/{tool_id}/test", json={
        "test_params": {}
    }, headers=headers)
    result = test_resp.json()["data"]
    assert result["success"] is False

    # 清理
    client.delete(f"/api/tools/{tool_id}", headers=headers)
```

#### 测试用例 3：Builtin 工具注册与执行（改造完成后才可运行）

```python
def test_builtin_tool_registration(client, auth_token):
    """内置工具通过 builtin_name 查找注册表，未注册的返回错误"""
    headers = {"Authorization": f"Bearer {auth_token}"}

    # 1. 创建 builtin 工具（使用不存在的 builtin_name）
    resp = client.post("/api/tools", json={
        "name": "ghost_builtin",
        "tool_type": "builtin",
        "parameters": {},
        "config": {"builtin_name": "nonexistent_tool", "settings": {}}
    }, headers=headers)
    tool_id = resp.json()["data"]["id"]

    # 2. 测试执行 — 应返回 "未知的内置工具"
    test_resp = client.post(f"/api/tools/{tool_id}/test", json={
        "test_params": {}
    }, headers=headers)
    result = test_resp.json()["data"]
    assert result["success"] is False
    assert "未知的内置工具" in result["result"]

    # 3. 创建 send_email 工具（已注册但配置不完整）
    resp2 = client.post("/api/tools", json={
        "name": "email_test",
        "tool_type": "builtin",
        "parameters": {
            "properties": {
                "to": {"type": "string", "description": "收件人"},
                "subject": {"type": "string", "description": "主题"},
                "body": {"type": "string", "description": "正文"}
            },
            "required": ["to", "subject", "body"]
        },
        "config": {"builtin_name": "send_email", "settings": {}}
    }, headers=headers)
    tool_id2 = resp2.json()["data"]["id"]

    # 4. 执行 — 配置不完整应返回 "缺少必要的邮件配置"
    test_resp2 = client.post(f"/api/tools/{tool_id2}/test", json={
        "test_params": {"to": "x@x.com", "subject": "test", "body": "hi"}
    }, headers=headers)
    result2 = test_resp2.json()["data"]
    assert result2["success"] is False
    assert "缺少" in result2["result"] or "错误" in result2["result"]

    # 清理
    client.delete(f"/api/tools/{tool_id}", headers=headers)
    client.delete(f"/api/tools/{tool_id2}", headers=headers)
```

#### 通过标准（改造完成后）

| 条件 | 判定 |
|------|------|
| 测试 1（`http_api` 端到端）通过 | `success=True`，响应含 `HTTP 200`，`duration_ms > 0` |
| 测试 2 合法代码返回 `"4950"` | `success=True`，`result == "4950"` |
| 测试 2 恶意代码被阻断 | `success=False` |
| 测试 3 未注册 builtin 返回错误 | `success=False`，消息含"未知的内置工具" |
| 测试 3 配置不完整返回错误 | `success=False`，消息含"缺少" |
| 对话.py / 飞书/配置与会话.py / 调度器.py 中无重复工具加载代码 | 三处均改为调用 `查询Agent工具记录()` |

---

## 12. Docker 部署与资源限制

### 12.1 双层资源限制架构

本项目采用**语言层 + OS 层**双重资源限制，确保工具执行安全：

#### 语言层限制（Python 沙箱）

针对每个工具执行子进程，由 `app/图引擎/工具加载器.py` 实现：

| 平台 | 实现方式 | 限制项 | 代码位置 |
|------|---------|--------|----------|
| **Windows** | Job Object | 128MB 内存 / 禁止子进程 / 自动终止 | `工具加载器.py:33` `_创建受限Job()` |
| **Linux** | resource.setrlimit | 128MB 虚拟内存 / 禁止子进程 / 10秒 CPU | `工具加载器.py:103` `_linux_preexec()` |

**关键代码**：
```python
# Linux 下通过 preexec_fn 设置 rlimit
proc = subprocess.Popen(
    [sys.executable, _沙箱执行器路径],
    preexec_fn=_linux_preexec if _IS_LINUX else None,
    ...
)

def _linux_preexec():
    import resource
    mem_limit = 128 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (mem_limit, mem_limit))
    resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
```

#### OS 层限制（容器）

作用于整个容器（主进程 + 所有子进程），由 `backend/docker-compose.yml` 配置：

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'        # 最多 2 核 CPU
      memory: 1G         # 最多 1GB 内存
pids_limit: 100          # 最多 100 个进程
```

### 12.2 部署步骤

```bash
# 1. 构建镜像
cd backend
docker-compose build

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f backend
```

### 12.3 验收测试

#### 测试 1: 资源限制生效

```bash
# 查看内存限制（应显示 1GB = 1073741824 字节）
docker exec agent-backend cat /sys/fs/cgroup/memory/memory.limit_in_bytes

# 查看进程数限制（应显示 100）
docker exec agent-backend cat /sys/fs/cgroup/pids/pids.max

# 实时监控资源使用
docker stats agent-backend
```

**预期输出**：
```
CONTAINER        CPU %    MEM USAGE / LIMIT    MEM %
agent-backend    5.2%     256MiB / 1GiB        25%
```

#### 测试 2: pytest 沙箱测试全绿

```bash
# 进入容器
docker exec -it agent-backend bash

# 运行沙箱安全测试
cd /app
python -m pytest tests/security/test_sandbox.py -v

# 预期结果：
# - 测试 1-6, 8-10, 正向: PASSED
# - 测试 7 (内存耗尽): PASSED（Linux rlimit 生效）
```

#### 测试 3: 工具执行内存限制

```bash
docker exec -it agent-backend python -c "
from app.图引擎.工具加载器 import 执行Python工具

code = '''
def execute(params):
    x = []
    for i in range(10**9):
        x.append('A' * 10**6)
    return 'done'
'''

result = 执行Python工具({'code': code}, {})
print('结果:', result)
# 预期: '错误：Python 执行进程被终止（可能超出内存限制）'
"
```

### 12.4 安全检查清单

- [ ] 容器内存限制已配置（1GB）
- [ ] 容器进程数限制已配置（100）
- [ ] 容器 CPU 限制已配置（2.0 核）
- [ ] pytest 沙箱测试全部通过
- [ ] 工具执行内存耗尽测试通过
- [ ] 资源监控已部署（docker stats）
- [ ] 日志轮转已配置
- [ ] .env 文件权限正确（600）
- [ ] 生产环境已禁用 API 文档（APP_ENV=prod）

### 12.5 详细文档

完整的 Docker 部署指南、故障排查、生产环境建议，请参阅：

**[docs/DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md)**

---
| `POST /api/tools/{id}/test` 不再使用 `startswith("错误")` 判断 | 改为使用 `ToolResult.success` |
