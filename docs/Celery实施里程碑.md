# Celery 实施里程碑

> 本文档已按 `docs/PLAN.md` 收敛，不包含 Celery Beat、签名认证、事件表等本轮不需要的内容。

## P0：准备阶段

目标：

- 明确 Celery + Redis 为本轮执行方案
- 明确 APScheduler 保留，不引入 Beat
- 明确局域网 5 台机器沿用 `X-RPA-KEY`

输出：

- `PLAN.md`
- 代码改造范围确认

## P1：后端基础接入

目标：

- 新增 `celery_app.py`
- 增加 Redis / Celery 配置
- 增加 `workers` 与 `task_dispatches`
- SQLite 启用 WAL

验收：

- 项目可正常启动
- 新表可自动建表

## P2：调度链路改造

目标：

- APScheduler 不再直接执行业务
- 到点后创建派发记录并 `apply_async()`
- Celery Worker 执行实际任务

验收：

- 定时任务可成功投递
- 派发表可看到状态变化

## P3：Worker 管理接口

目标：

- 完成 `/api/workers/register`
- 完成 `/api/workers/heartbeat`
- 完成 `/api/workers`
- 增加每分钟离线巡检

验收：

- 30 秒心跳可更新状态
- 60 秒超时可标记离线

## P4：前端页面

目标：

- 新增机器管理页面
- 展示机器列表、状态、最后心跳
- 10 秒轮询刷新

验收：

- 页面可筛选状态
- 机器状态变化可在轮询周期内看到

## 本轮明确不做

- Celery Beat
- HMAC / 签名认证
- `task_dispatch_events`
- `worker_heartbeats`
- WebSocket
- 幂等键

