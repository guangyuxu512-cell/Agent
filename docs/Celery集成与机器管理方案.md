# Celery 集成与机器管理方案

> 本文档以 `docs/PLAN.md` 为准，已去除当前明确不需要的功能，避免后续误读。

## 1. 总体方案

本次改造目标是：在保留现有 `APScheduler` 的前提下，引入 `Celery + Redis` 支持多机器并发执行。

当前确定方案：

- **Broker**：Redis
- **APScheduler**：保留，只负责到点后投递 Celery
- **Celery Beat**：本轮不使用
- **Worker 启动方式**：各机器通过 `worker_agent.py` 启动
- **鉴权**：沿用现有 `X-RPA-KEY`
- **部署范围**：局域网 5 台机器
- **前端刷新方式**：10 秒轮询

## 2. 调度与执行

### 2.1 Celery 结构

建议结构：

- `app/celery_app.py`：Celery 应用入口
- `app/tasks/`：Celery 任务定义
- `app/services/`：任务执行逻辑

### 2.2 队列策略

每台机器独占一个队列：

- `worker.{machine_id}`

例如：

- `worker.machine-01`
- `worker.machine-02`

### 2.3 `worker_agent.py`

每台机器运行独立的 `worker_agent.py`：

1. 启动时调用 `/api/workers/register`
2. 后台线程每 30 秒调用 `/api/workers/heartbeat`
3. 拉起本机 Celery Worker，监听 `worker.{machine_id}`

脚本环境变量：

- `SERVER_URL`
- `MACHINE_ID`
- `RPA_KEY`

### 2.4 调度链路

新的执行链路为：

1. APScheduler 到点触发
2. 创建 `task_dispatches` 记录
3. 调用 `task.apply_async()` 投递到指定队列
4. Celery Worker 执行任务
5. 回写执行状态

### 2.5 链路验证任务

新增 `echo_test` 任务用于端到端验证：

- API 投递测试任务
- Celery Worker 消费并执行
- `task_dispatches` 更新为 `success/failed`

## 3. Worker 注册与心跳

本轮只保留最小能力：

- `POST /api/workers/register`
- `POST /api/workers/heartbeat`
- `GET /api/workers`
- `GET /api/task-dispatches`
- `GET /api/task-dispatches/{dispatch_id}`
- `POST /api/task-dispatches/echo-test`

说明：

- 注册和心跳沿用 `X-RPA-KEY`
- 心跳每 30 秒上报一次
- `last_heartbeat` 超过 60 秒标记为 `offline`
- 离线检测继续使用 APScheduler 每分钟扫描一次

## 4. 数据存储

新增两张表：

- `workers`
- `task_dispatches`

SQLite 继续作为控制面数据库，并启用 `WAL` 模式提升并发写入能力。

## 5. 前端页面

新增独立机器管理页面，展示：

- 机器列表
- 在线状态
- 最后心跳时间

页面采用：

- 10 秒轮询
- 状态筛选

## 6. 明确不做的功能

以下内容本轮**不纳入方案**：

- HMAC / 签名认证
- Celery Beat
- `task_dispatch_events` 事件表
- `worker_heartbeats` 历史表
- WebSocket
- 幂等键机制

## 7. 实施顺序

1. 引入 Celery 与 Redis
2. 新增 `workers` 与 `task_dispatches`
3. 改造 APScheduler 为“只投递不执行”
4. 增加 Worker 注册、心跳、列表接口
5. 增加任务派发查询接口与 `echo_test`
6. 增加 `worker_agent.py`
7. 增加前端机器管理页面
