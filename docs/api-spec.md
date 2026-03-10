# API 接口规范

> 本文件承接原根目录 `AGENTS.md` 中的「API 规范」与接口路由事实清单，重点回答：有哪些路由、统一请求/响应长什么样、错误码和鉴权怎么约定。

## 1. 路由清单

### 1.1 鉴权

- `POST /api/auth/login`
- `POST /api/auth/change-password`

### 1.2 智能体与编排

- `GET /api/agents`
- `POST /api/agents`
- `GET /api/agents/{agent_id}`
- `PUT /api/agents/{agent_id}`
- `DELETE /api/agents/{agent_id}`
- `GET /api/orchestration`
- `POST /api/orchestration`

### 1.3 对话与记忆

- `POST /api/chat`
- `GET /api/conversations`
- `GET /api/conversations/{conversation_id}/messages`
- `DELETE /api/conversations/{conversation_id}`
- `GET /api/memories`
- `DELETE /api/memories/{memory_id}`
- `DELETE /api/memories`

### 1.4 工具与系统配置

- `GET /api/tools`
- `POST /api/tools`
- `GET /api/tools/{tool_id}`
- `PUT /api/tools/{tool_id}`
- `DELETE /api/tools/{tool_id}`
- `POST /api/tools/{tool_id}/test`
- `GET /api/config`
- `POST /api/config`
- `PUT /api/config`
- `GET /api/config/{category}`
- `DELETE /api/config/{category}`
- `GET /api/feishu/tables`
- `POST /api/feishu/tables`
- `PUT /api/feishu/tables/{record_id}`
- `DELETE /api/feishu/tables/{record_id}`

### 1.5 定时任务与派发

- `GET /api/schedules`
- `POST /api/schedules`
- `PUT /api/schedules/{schedule_id}`
- `DELETE /api/schedules/{schedule_id}`
- `GET /api/task-dispatches`
- `GET /api/task-dispatches/{dispatch_id}`
- `GET /api/task-dispatches/{task_id}/status`
- `POST /api/task-dispatches/echo-test`

### 1.6 Worker 与机器管理

- `POST /api/workers/register`
- `POST /api/workers/heartbeat`
- `PUT /api/workers/{machine_id}/status`
- `GET /api/workers`
- `GET /api/machines`
- `POST /api/machines`
- `PUT /api/machines/{machine_id}`
- `DELETE /api/machines/{machine_id}`
- `GET /api/machine-apps`
- `POST /api/machine-apps`
- `PUT /api/machine-apps/{binding_id}`
- `DELETE /api/machine-apps/{binding_id}`
- `POST /api/machine/heartbeat`
- `PUT /api/machines/{machine_id}/status`

### 1.7 日志与健康检查

- `GET /api/logs/sse-token`
- `POST /api/logs/push`
- `GET /api/logs/stream`
- `GET /api/logs/history`
- `GET /api/logs/stats`
- `GET /api/health`

## 2. 路由命名风格

- 整体采用 `/api/...` 前缀
- 资源名使用英文：
  - `/api/agents`
  - `/api/tools`
  - `/api/schedules`
  - `/api/feishu/tables`
  - `/api/task-dispatches`
- 特定动作路径使用英文短语或连字符：
  - `/api/chat`
  - `/api/logs/sse-token`
  - `/api/task-dispatches/echo-test`
  - `/api/task-dispatches/{task_id}/status`
- 路径参数统一英文命名，如 `tool_id`、`schedule_id`、`conversation_id`

## 3. 统一响应格式

- 全局响应模型定义在 `backend/app/schemas.py`
- 标准格式：

```json
{
  "code": 0,
  "data": null,
  "msg": "ok"
}
```

- 说明：
  - `code=0` 表示成功
  - `code=1` 常用于业务失败或参数错误
  - `code=401` 用于未授权
  - `code=403` 常用于 `X-RPA-KEY` 校验失败
  - `code=500` 用于全局未处理异常

## 4. 分页协议

### 4.1 标准分页接口

- `GET /api/agents`
- `GET /api/tools`
- `GET /api/schedules`
- `GET /api/conversations`

### 4.2 常用参数

- `page`
- `page_size`

### 4.3 常见返回

```json
{
  "code": 0,
  "data": {
    "list": [],
    "total": 0,
    "page": 1,
    "page_size": 20
  },
  "msg": "ok"
}
```

### 4.4 特殊分页 / 增量协议

- `GET /api/logs/history` 使用 `since_seq` + `limit`
- 返回 `logs`、`total`、`has_more`

### 4.5 当前未统一分页的接口

- `GET /api/workers`
- `GET /api/task-dispatches`
- `GET /api/machines`
- `GET /api/machine-apps`

## 5. 错误处理与状态码规范

- 业务错误：
  - 大多数接口返回 HTTP `200`，并在 JSON 内使用 `code=1`
- 参数校验错误：
  - `RequestValidationError` 被全局异常处理器改写为 HTTP `200` + `{"code":1,...}`
- 未授权：
  - 鉴权中间件直接返回 HTTP `401`，JSON 为 `{"code":401,"data":null,"msg":"未授权"}`
- 全局异常：
  - 返回 HTTP `500`，JSON 为 `{"code":500,"data":null,"msg":"服务器内部错误"}`
- 特殊鉴权接口：
  - 日志推流和机器/Worker 接口中的 `X-RPA-KEY` 错误可能返回 HTTP `403`
- 现状说明：
  - 对话接口 `backend/app/api/对话.py` 部分返回原生 dict，但键结构仍保持 `code/data/msg`

## 6. 认证 / 鉴权方式

### 6.1 JWT Bearer

- 登录入口：`POST /api/auth/login`
- 登录成功后返回 JWT，前端存入 `localStorage.token`
- 之后通过 `Authorization: Bearer <token>` 访问绝大多数接口
- 中间件：`backend/app/middleware/鉴权中间件.py`

### 6.2 免鉴权路径

- `/api/auth/login`
- `/api/health`
- `/api/logs/push`
- `/api/machines/{machine_id}/status`
- `/api/task-dispatches/echo-test`
- `/api/task-dispatches/{task_id}/status`
- `/api/logs/stream`
- `/api/workers/register`
- `/api/workers/heartbeat`
- `/api/workers/{machine_id}/status`
- `/docs`
- `/openapi.json`
- `/redoc`

### 6.3 X-RPA-KEY

- 用于外部影刀/Worker 侧回调
- 典型接口：
  - `POST /api/logs/push`
  - `PUT /api/machines/{machine_id}/status`
  - `POST /api/task-dispatches/echo-test`
  - `GET /api/task-dispatches/{task_id}/status`
  - `POST /api/workers/register`
  - `POST /api/workers/heartbeat`
  - `PUT /api/workers/{machine_id}/status`

### 6.4 SSE Token

- 日志流 `GET /api/logs/stream` 不直接使用 Header 鉴权
- 前端先调用 `GET /api/logs/sse-token` 获取短期 token
- 然后通过 `EventSource('/api/logs/stream?token=...')` 建立 SSE

## 7. 请求与响应风格补充

### 7.1 前后端字段风格

- 智能体、定时任务、系统配置、飞书表格接口大量使用前端友好的 `camelCase`
- Worker、日志、数据库直出字段中仍存在 `snake_case` 风格，如：
  - `machine_id`
  - `queue_name`
  - `last_heartbeat`
  - `created_at`

### 7.2 典型接口示例

#### 登录

请求：

```json
{
  "username": "admin",
  "password": "your-password"
}
```

成功响应：

```json
{
  "code": 0,
  "data": {
    "token": "jwt-token",
    "force_change_password": false
  },
  "msg": "ok"
}
```

#### Worker 心跳

请求头：

```text
X-RPA-KEY: <RPA_KEY>
```

请求体：

```json
{
  "machine_id": "machine-a",
  "shadowbot_running": true
}
```

成功响应：

```json
{
  "code": 0,
  "data": null,
  "msg": "心跳成功"
}
```

#### 聊天 SSE

- 请求：`POST /api/chat`
- 输出为 `text/event-stream`
- 常见事件类型：
  - `conversation_id`
  - `agent`
  - `token`
  - `tool_call`
  - `tool_result`
  - `done`
  - `error`

## 8. 当前项目暂无此内容

- 当前项目暂无统一的 OpenAPI 书面规范文件
- 当前项目暂无独立的 API 版本号管理策略（如 `/api/v1`、`/api/v2`）
- 当前项目暂无统一错误码枚举表，主要通过 `code` 字段和消息文案表达错误语义

