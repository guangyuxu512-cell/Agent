# Celery 改造进度

> 更新时间：2026-03-09

## 1. 已完成

### 后端

- 已新增 `backend/app/celery_app.py`
- 已新增 Celery 任务目录 `backend/app/tasks/`
- 已新增执行服务目录 `backend/app/services/`
- 已新增 `backend/worker_agent.py`
- 已新增 `workers` 表模型
- 已新增 `task_dispatches` 表模型
- 已在 SQLite 连接与初始化阶段启用 `WAL` 模式
- 已新增：
  - `POST /api/workers/register`
  - `POST /api/workers/heartbeat`
  - `GET /api/workers`
  - `GET /api/task-dispatches`
  - `GET /api/task-dispatches/{dispatch_id}`
  - `POST /api/task-dispatches/echo-test`
- 已把 APScheduler 改为“到点后投递 Celery”
- 已新增每分钟 Worker 离线巡检
- 已新增 `echo_test` 任务用于端到端验证

### 前端

- 已新增机器管理页面
- 已新增机器管理路由
- 已在左侧导航加入“机器管理”
- 已实现 10 秒轮询与状态筛选

### 文档

- 已按 `docs/PLAN.md` 收敛历史方案文档
- 已删除不需要功能的描述，避免后续误读
- 已同步新版 `worker_agent.py`、派发查询接口和 `echo_test`

## 2. 当前保留方案

- 保留 APScheduler
- 使用 Redis 作为 Celery Broker
- 不使用 Celery Beat
- 各机器通过 `worker_agent.py` 启动本机 Celery Worker
- 注册与心跳继续沿用 `X-RPA-KEY`
- 不做 HMAC、事件表、心跳历史表、WebSocket、幂等键

## 3. 已完成校验

- `python -m compileall backend/app`
- `python -m compileall backend/worker_agent.py`
- `cd Agent && npm run lint`

## 4. 待你后续确认 / 可能继续补充

- Redis 环境变量与部署环境是否已准备好
- 外部 5 台机器的 `SERVER_URL / MACHINE_ID / RPA_KEY` 是否已分配
- 是否需要把 `echo_test` 做成前端按钮
- 是否需要增加任务派发记录的分页能力
