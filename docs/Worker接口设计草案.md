# Worker 接口设计草案

> 本文档以当前 `PLAN.md` 为准，只保留已确认的三个接口与现有 `X-RPA-KEY` 鉴权方式。

## 1. 统一约定

- 路由前缀：`/api/workers`
- 注册与心跳：使用 `X-RPA-KEY`
- 列表查询：沿用现有后台登录鉴权
- 响应格式：沿用现有 `统一响应`

响应示例：

```json
{
  "code": 0,
  "data": {},
  "msg": "ok"
}
```

## 2. 注册接口

## `POST /api/workers/register`

用途：

- 外部机器启动时注册或更新自身信息

请求头：

- `X-RPA-KEY: <key>`

请求体：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `machine_id` | 是 | string | 机器唯一标识 |
| `hostname` | 是 | string | 主机名 |
| `ip` | 是 | string | IP 地址 |
| `queue_name` | 否 | string | 队列名，不传则后端自动生成 |
| `status` | 否 | string | 默认 `online` |
| `tags` | 否 | string[] | 标签数组 |

说明：

- 若 `queue_name` 为空，后端默认生成 `worker.{machine_id}`
- 已注册机器再次调用时按更新处理

## 3. 心跳接口

## `POST /api/workers/heartbeat`

用途：

- 每 30 秒刷新一次 Worker 心跳

请求头：

- `X-RPA-KEY: <key>`

请求体：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `machine_id` | 是 | string | 机器唯一标识 |
| `status` | 否 | string | `online / busy / offline` |
| `ip` | 否 | string | 当前 IP |
| `tags` | 否 | string[] | 标签 |

说明：

- 心跳接口只做轻量更新
- 机器超过 60 秒无心跳，由后端定时任务标记 `offline`

## 4. 列表接口

## `GET /api/workers`

用途：

- 前端机器管理页面展示
- 支持按状态过滤

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `online / busy / offline` |

返回字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 主键 |
| `machine_id` | string | 机器标识 |
| `hostname` | string | 主机名 |
| `ip` | string | IP |
| `queue_name` | string | 队列名 |
| `status` | string | 当前状态 |
| `last_heartbeat` | string/null | 最近心跳 |
| `tags` | string[] | 标签 |

## 5. 任务派发查询接口

## `GET /api/task-dispatches`

用途：

- 查询任务派发列表
- 支持按机器和状态过滤

查询参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `machine_id` | string | 按机器过滤 |
| `status` | string | 按状态过滤 |

返回字段：

- `dispatch_id`
- `task_name`
- `machine_id`
- `queue_name`
- `schedule_id`
- `status`
- `payload_ref`
- `requested_by`
- `retry_count`
- `submitted_at`
- `finished_at`
- `error_message`

## `GET /api/task-dispatches/{dispatch_id}`

用途：

- 查询单条任务派发详情

## `POST /api/task-dispatches/echo-test`

用途：

- 投递一个 `echo_test` 到指定机器
- 用于端到端验证整条链路

请求体：

| 字段 | 必填 | 类型 | 说明 |
| --- | --- | --- | --- |
| `machine_id` | 是 | string | 目标机器 |
| `message` | 否 | string | 测试消息 |

## 6. 本轮不做的接口能力

以下能力本轮明确不做：

- HMAC / 签名校验
- 每机器独立 token
- JWT 心跳认证
- WebSocket 推送
- 心跳历史查询
