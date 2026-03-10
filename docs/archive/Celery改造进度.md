# Celery 改造进度

> 更新时间：2026-03-10

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
- 已统一通过 `REDIS_URL` 读取 Celery Broker / Backend，默认值为 `redis://192.168.0.43:6380/0`

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

## 5. 外部脚本接入格式

### 5.1 注册接口

- 地址：`POST /api/workers/register`
- 请求头：`X-RPA-KEY: <RPA_KEY>`
- 请求体：

```json
{
  "machine_id": "machine-a",
  "hostname": "DESKTOP-001",
  "ip": "192.168.0.55",
  "queue_name": "worker.machine-a",
  "status": "online",
  "tags": ["celery", "worker-agent"]
}
```

- 说明：
  - `machine_id` 必填，且需要全局唯一
  - `queue_name` 可不传；后端会默认生成 `worker.{machine_id}`
  - `status` 支持 `online / offline / busy`，其他值会被规范成 `online`
  - `tags` 为字符串数组，可为空列表

### 5.2 心跳接口

- 地址：`POST /api/workers/heartbeat`
- 请求头：`X-RPA-KEY: <RPA_KEY>`
- 请求体：

```json
{
  "machine_id": "machine-a",
  "status": "online",
  "ip": "192.168.0.55",
  "tags": ["celery", "worker-agent"]
}
```

- 说明：
  - 心跳前必须先完成注册，否则会返回“机器未注册”
  - 当前 `worker_agent.py` 默认每 30 秒发送一次心跳
  - 成功响应示例：`{"code": 0, "data": null, "msg": "心跳成功"}`

### 5.3 外部脚本调用示例

```powershell
$headers = @{
  'X-RPA-KEY' = 'changeme-rpa-key-2026'
  'Content-Type' = 'application/json'
}

$registerBody = @{
  machine_id = 'machine-a'
  hostname = 'DESKTOP-001'
  ip = '192.168.0.55'
  status = 'online'
  tags = @('celery', 'worker-agent')
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri 'http://127.0.0.1:8001/api/workers/register' `
  -Headers $headers `
  -Body $registerBody
```

```powershell
$heartbeatBody = @{
  machine_id = 'machine-a'
  status = 'online'
  ip = '192.168.0.55'
  tags = @('celery', 'worker-agent')
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri 'http://127.0.0.1:8001/api/workers/heartbeat' `
  -Headers $headers `
  -Body $heartbeatBody
```

```python
import httpx

server_url = 'http://127.0.0.1:8001'
rpa_key = 'changeme-rpa-key-2026'
machine_id = 'machine-a'

headers = {'X-RPA-KEY': rpa_key}

register_payload = {
    'machine_id': machine_id,
    'hostname': 'DESKTOP-001',
    'ip': '192.168.0.55',
    'status': 'online',
    'tags': ['celery', 'worker-agent'],
}

heartbeat_payload = {
    'machine_id': machine_id,
    'status': 'online',
    'ip': '192.168.0.55',
    'tags': ['celery', 'worker-agent'],
}

with httpx.Client(timeout=10.0) as client:
    print(client.post(f'{server_url}/api/workers/register', json=register_payload, headers=headers).json())
    print(client.post(f'{server_url}/api/workers/heartbeat', json=heartbeat_payload, headers=headers).json())
```

### 5.4 本地 Celery/Redis 自测方法

- 下面脚本用于本地验证 `backend/.env` 中 `REDIS_URL` 是否可被 Redis 与 Celery Broker / Backend 正常使用
- 该脚本只验证连接链路，不会真正消费任务

```powershell
cd backend
@'
from pathlib import Path
from celery import Celery
import redis

root = Path('.')
redis_url = None
for line in (root / '.env').read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    if key.strip() == 'REDIS_URL':
        redis_url = value.strip()
        break

print(f'REDIS_URL={redis_url}')
client = redis.Redis.from_url(redis_url, socket_connect_timeout=5, socket_timeout=5, decode_responses=True)
print('redis_ping=', client.ping())

app = Celery('agent_backend_test', broker=redis_url, backend=redis_url)
with app.connection_for_write() as conn:
    conn.ensure_connection(max_retries=1)
    print('celery_broker_connection=ok')

backend_client = getattr(app.backend, 'client', None)
if backend_client is not None:
    print('celery_backend_ping=', backend_client.ping())
else:
    print('celery_backend_client=unavailable')
'@ | python -
```

### 5.5 本次本地自测结果（2026-03-10）

- `REDIS_URL=redis://192.168.0.43:6380/0`
- `redis_ping=True`
- `celery_broker_connection=ok`
- `celery_backend_ping=True`

### 5.6 端到端验证方法

- 确保后端已启动：`python -m uvicorn app.启动器:app --reload --port 8001`
- 确保目标机器已注册并持续发送心跳，且对应 Celery Worker 正在监听 `worker.{machine_id}`
- 调用 `POST /api/task-dispatches/echo-test`

```json
{
  "machine_id": "machine-a",
  "message": "hello celery"
}
```

- 成功后从返回值里的 `data.dispatch_id` 获取派发单号
- 再调用 `GET /api/task-dispatches/{dispatch_id}` 查询执行状态与结果

## 6. 当前结论 / 回复

### 6.1 关于 Redis / Celery

- 本地开发环境已具备 `REDIS_URL`，当前值为 `redis://192.168.0.43:6380/0`
- 已完成本地连通性校验：`redis_ping=True`、`celery_broker_connection=ok`、`celery_backend_ping=True`
- 结论：当前本地 Redis 与 Celery Broker / Backend 链路可用

### 6.2 关于外部机器脚本

- 外部机器至少需要准备 `SERVER_URL`、`MACHINE_ID`、`RPA_KEY`
- 推荐同时保证外部机器访问的是同一套 Redis，并使用相同的 `REDIS_URL`
- 接入顺序为：先 `register`，后周期性 `heartbeat`，最后由服务端通过 `echo-test` 或调度任务向 `worker.{machine_id}` 投递任务
- `machine_id` 必须唯一；如果外部脚本不传 `queue_name`，后端默认使用 `worker.{machine_id}`

### 6.3 关于“外部 5 台机器是否已分配”

- 从当前仓库文档与配置只能确认“所需变量和接口格式已经明确”
- 是否已经给 5 台外部机器分配好 `SERVER_URL / MACHINE_ID / RPA_KEY`，仍需要你在部署侧最终确认
- 建议为每台机器固定一组值，并把 `MACHINE_ID` 与实际机器一一对应，避免派发串队列

### 6.4 关于是否需要前端按钮

- 当前不是必需项
- 现阶段已有 `POST /api/task-dispatches/echo-test`，足以完成联调与验收
- 如果后续要给非开发同事做日常巡检或验收，再补前端按钮会更合适

### 6.5 关于是否需要分页

- 当前不是必须项
- 在联调和初期上线阶段，任务派发记录量通常可直接全量查看
- 当 `task_dispatches` 记录明显增长，或前端查询开始变慢时，再补分页会更合适
