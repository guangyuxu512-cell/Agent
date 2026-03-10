# 回调与通信机制

> 本文档承接原 `AGENTS.md` 中与 Worker、Agent、飞书、影刀、SSE、Celery 派发相关的详细说明，聚焦“谁与谁通信、走什么协议、请求体长什么样、结果落到哪里”。

## 1. 通信角色总览

### 1.1 参与方

- 前端 `Agent/`：管理页面、聊天页面、日志页面，主要通过 HTTP + SSE 与后端通信。
- 后端 `backend/app/`：统一接收 API 请求，负责鉴权、落库、调度、日志推送、Worker 管理。
- Redis / Celery：承担任务 Broker / Result Backend，负责把任务派发到指定队列。
- 外部 `worker_agent.py`：运行在局域网或外部机器上，先注册、再心跳、再消费 `worker.{machine_id}` 队列。
- 影刀 / Shadowbot：通过日志回推和状态回调与后端交互。
- 飞书开放平台：通过长连接事件推送触发消息处理链路。
- OpenAI / RAGFlow / SMTP 等外部服务：由后端在业务链路中主动调用。

### 1.2 主要链路

- Web 聊天：前端页面 → `POST /api/chat` → SSE 返回增量消息。
- Worker 注册：外部机器 → `POST /api/workers/register`。
- Worker 心跳：外部机器 → `POST /api/workers/heartbeat`。
- Celery 派发：后端 → Redis 队列 → 指定 Worker → 结果回写数据库。
- 影刀日志推流：外部系统 → `POST /api/logs/push`。
- 影刀状态回调：外部系统 → `PUT /api/machines/{machine_id}/status`。
- 日志订阅：前端先调用 `GET /api/logs/sse-token`，再用 `EventSource` 连接 `GET /api/logs/stream?token=...`。
- 飞书消息：飞书长连接事件 → 飞书消息处理 → 创建/复用会话 → 调用 Agent → 回复飞书用户。

## 2. Celery Worker 注册与心跳

### 2.1 注册接口

- 路径：`POST /api/workers/register`
- 鉴权：Header `X-RPA-KEY`
- 请求体模型：

```json
{
  "machine_id": "machine-a",
  "hostname": "DESKTOP-001",
  "ip": "192.168.0.23",
  "queue_name": "worker.machine-a",
  "status": "online",
  "tags": ["windows", "shadowbot"]
}
```

- 字段说明：
  - `machine_id`：机器唯一标识，必填。
  - `hostname`：主机名，必填。
  - `ip`：机器 IP，必填。
  - `queue_name`：可选；不传时后端回退为 `worker.{machine_id}`。
  - `status`：可选，允许值实际规范为 `online/offline/busy`，非法值会回退到 `online`。
  - `tags`：可选字符串数组。
- 返回：统一响应格式，成功时 `data` 为 Worker 当前快照，包含 `machine_id`、`hostname`、`ip`、`queue_name`、`status`、`last_heartbeat`、`tags`。

### 2.2 心跳接口

- 路径：`POST /api/workers/heartbeat`
- 鉴权：Header `X-RPA-KEY`
- 请求体模型：

```json
{
  "machine_id": "machine-a",
  "status": "online",
  "ip": "192.168.0.23",
  "tags": ["windows", "shadowbot"]
}
```

- 说明：
  - 心跳依赖“先注册后心跳”；未注册机器会返回错误。
  - `status` 同样规范为 `online/offline/busy`。
  - `ip`、`tags` 可选；传入时会同步更新数据库中的 Worker 信息。
- 成功返回示例：

```json
{
  "code": 0,
  "data": null,
  "msg": "心跳成功"
}
```

### 2.3 外部 Worker 推荐启动顺序

1. 设置环境变量：`SERVER_URL`、`MACHINE_ID`、`RPA_KEY`。
2. 调用 `POST /api/workers/register` 完成注册。
3. 定时调用 `POST /api/workers/heartbeat` 保活。
4. 启动 Celery Worker，监听 `worker.{machine_id}` 队列。

### 2.4 队列与状态约定

- 默认队列命名：`worker.{machine_id}`
- Worker 状态：`online`、`offline`、`busy`
- 注意区分：
  - `workers`：Celery Worker 维度，描述消费端状态。
  - `machines`：影刀机器维度，描述自动化设备状态，状态值是 `idle/running/offline/error`。

## 3. Celery 任务派发链路

### 3.1 Echo 测试派发

- 路径：`POST /api/task-dispatches/echo-test`
- 请求体模型：

```json
{
  "machine_id": "machine-a",
  "message": "hello celery"
}
```

- 作用：
  - 用于验证指定机器的 Celery 队列是否可达。
  - 后端会把任务派发到 `worker.{machine_id}` 队列。
  - 执行结果会写入 `task_dispatches`。
- 状态查询：
  - 路径：`GET /api/task-dispatches/{task_id}/status`
  - 返回任务当前 `status`，以及 `result`、`error`、`queue_name`、`submitted_at` 等派发信息。

### 3.2 定时任务派发链路

- 前端定时任务页调用 `/api/schedules` 管理任务定义。
- 应用启动时执行 `启动调度器()`。
- 到点后由 `backend/app/调度器.py` 调用 `派发定时任务()`。
- 任务进入 Celery 队列后，由 `schedule_executor.py` / `schedule_tasks.py` 执行。
- 执行结果回写：
  - `schedule_logs`
  - `task_dispatches`

### 3.3 调度输入与结果

- 输入：定时任务定义、`machine_id`、`dispatch_id`
- 输出：
  - `schedule_logs` 中的执行历史
  - `task_dispatches` 中的派发记录
  - `echo_test` 任务的执行结果

## 4. 影刀 / Shadowbot 回调

### 4.1 日志推流

- 路径：`POST /api/logs/push`
- 鉴权：Header `X-RPA-KEY`
- 请求体模型：

```json
{
  "time": "2026-03-10T10:30:00+08:00",
  "task_id": "task_123",
  "machine": "PC-001",
  "level": "进行中",
  "msg": "日志内容"
}
```

- 字段说明：
  - `msg` 必填。
  - `time`、`task_id`、`machine`、`level` 不传时后端有默认值。
- 成功返回示例：

```json
{
  "code": 0,
  "data": {
    "seq": 123
  },
  "msg": "ok"
}
```

- 处理逻辑：
  - 校验 `X-RPA-KEY`
  - 记录审计信息（来源 IP、UA、task_id、machine）
  - 持久化到 `push_logs`
  - 广播给当前所有 SSE 日志订阅端

### 4.2 机器状态回调

- 路径：`PUT /api/machines/{machine_id}/status`
- 鉴权：Header `X-RPA-KEY`
- 请求体模型：

```json
{
  "status": "idle"
}
```

- 允许状态值：`idle`、`running`、`offline`、`error`
- 典型用途：
  - 影刀任务开始时回调 `running`
  - 执行结束回调 `idle`
  - 机器断线或异常时回调 `offline/error`
- 业务效果：
  - 更新 `machines` 表状态与心跳时间
  - 当机器从 `running` 回到 `idle` 时，后端会尝试继续消费 `task_queue`

### 4.3 机器心跳

- 路径：`POST /api/machine/heartbeat`
- 请求体模型：

```json
{
  "machine_id": "machine-a",
  "shadowbot_running": true
}
```

- 说明：
  - 该接口只更新影刀机器心跳时间，不直接修改机器状态。
  - 机器状态由 `PUT /api/machines/{machine_id}/status` 控制。

## 5. SSE 通信

### 5.1 聊天 SSE

- 路径：`POST /api/chat`
- 用途：Web 端 Agent 对话、编排对话、流式返回消息。
- 前端特点：
  - 长连接返回增量内容。
  - Nginx 代理必须关闭 buffering。

### 5.2 日志 SSE

- 申请令牌：`GET /api/logs/sse-token`
- 建立连接：`GET /api/logs/stream?token=...`
- 可选查询参数：
  - `task_id`
  - `since_seq`
- SSE 消息格式：

```text
data: {"seq":123,"time":"...","task_id":"...","machine":"...","level":"...","msg":"..."}
```

- 心跳消息格式：

```text
data: {"type":"heartbeat","time":"2026-03-10T10:30:00+08:00"}
```

- 协议注意点：
  - `EventSource` 不能自定义 Header。
  - 因此前端先取短期 token，再通过 query 参数建立 SSE。
  - 日志 SSE token 有效期为 5 分钟。
  - 后端在响应头中显式关闭缓冲：`X-Accel-Buffering: no`。

## 6. 飞书回调链路

### 6.1 长连接事件

- 飞书侧通过 `lark-oapi` WebSocket 长连接推送 `p2_im_message_receive_v1` 事件。
- 启动器生命周期内会触发 `启动飞书长连接()`。

### 6.2 消息处理流程

- 飞书事件进入 `backend/app/飞书/消息处理.py`
- 根据 `open_id` 创建或复用对话
- 调用 Agent / 图引擎
- 将回复消息发回飞书用户

### 6.3 关键配置

- `system_config.feishu.appId`
- `system_config.feishu.appSecret`
- `system_config.feishu.feishuEventAgentId`

## 7. 鉴权与安全约束

- Worker 注册 / 心跳、影刀日志推流、影刀状态回调都依赖 Header `X-RPA-KEY`。
- 普通 Web API 主要使用 JWT Bearer。
- 日志 SSE 不走 Header 鉴权，而是走短期 token 查询参数。
- 不要把真实 `RPA_PUSH_KEY`、`RPA_KEY`、生产地址写进示例文档或提交到仓库。

## 8. 外部脚本最小接入规范

### 8.1 只做心跳的脚本

- 若脚本只负责“上报在线状态”，也应先完成一次注册，再按固定间隔发送心跳。
- 最小请求头：

```http
X-RPA-KEY: <RPA_PUSH_KEY>
Content-Type: application/json
```

- 最小心跳请求体：

```json
{
  "machine_id": "machine-a",
  "status": "online"
}
```

### 8.2 具备完整执行能力的脚本 / Agent

- 除了心跳外，还应：
  - 维护稳定的 `machine_id`
  - 监听 `worker.{machine_id}` 队列
  - 在任务执行阶段按需回推日志
  - 在自动化程序开始/结束时更新机器状态

## 9. 当前项目暂无此内容

- 当前文档未单列 WebSocket 双向业务协议；核心实时链路以 HTTP + SSE + Celery 为主。
