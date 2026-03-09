# Celery 表结构草案

> 本文档仅保留 `PLAN.md` 中确认需要的表，不包含事件表、历史心跳表等扩展设计。

## 1. `workers`

用途：

- 记录局域网内 Worker 机器注册信息
- 支撑心跳、在线状态和前端展示

字段如下：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 自增主键 |
| `machine_id` | varchar(100) | 机器唯一标识，唯一 |
| `hostname` | varchar(200) | 主机名 |
| `ip` | varchar(64) | IP 地址 |
| `queue_name` | varchar(200) | 队列名，格式 `worker.{machine_id}` |
| `status` | varchar(20) | `online / offline / busy` |
| `last_heartbeat` | datetime | 最近一次心跳时间 |
| `tags` | text | JSON 数组字符串 |
| `created_at` | datetime | 创建时间 |
| `updated_at` | datetime | 更新时间 |

建议索引：

- `unique(machine_id)`
- `index(status)`
- `index(last_heartbeat)`

## 2. `task_dispatches`

用途：

- 记录 APScheduler 或接口投递到 Celery 的派发信息
- 不依赖 Celery 自身结果做长期业务追踪

字段如下：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `dispatch_id` | varchar(36) | 主键 |
| `task_name` | varchar(200) | Celery 任务名 |
| `machine_id` | varchar(100) | 目标机器 |
| `queue_name` | varchar(200) | 投递队列 |
| `schedule_id` | varchar(36) | 来源定时任务 ID，可为空 |
| `status` | varchar(20) | `pending / running / success / failed` |
| `payload_ref` | text | 任务参数摘要 |
| `requested_by` | varchar(100) | 来源，如 `scheduler` |
| `retry_count` | integer | 重试次数 |
| `submitted_at` | datetime | 投递时间 |
| `finished_at` | datetime | 完成时间 |
| `error_message` | text | 错误信息 |

建议索引：

- `index(machine_id, status)`
- `index(queue_name)`
- `index(schedule_id)`

## 3. 现有表处理建议

### 3.1 `machines`

- 继续保留，服务现有影刀机器管理逻辑
- 不直接替代新的 `workers`

### 3.2 `task_queue`

- 继续保留现有业务用途
- 不作为 Celery 主执行队列

### 3.3 `schedules`

- 继续保留
- APScheduler 仍从该表读取任务
- 执行方式改为“到点后投递 Celery”

## 4. 本轮不新增的表

以下表本轮不创建：

- `task_dispatch_events`
- `worker_heartbeats`

