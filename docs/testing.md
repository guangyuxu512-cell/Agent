# 测试策略

> 本文档承接原 `AGENTS.md` 中关于测试框架、现状、联调方式和交付要求的说明，重点描述“当前项目怎么测、哪些是真实测试、哪些只是联调脚本、交付时至少要补什么验证信息”。

## 1. 当前测试现状

- 后端已配置 `pytest`，配置文件位于 `backend/pytest.ini`。
- 仓库里存在若干联调 / 排查脚本，但当前“正式 pytest 套件”并不完整。
- 前端当前未落地自动化测试框架。
- 涉及 SSE、飞书、Worker、影刀等链路时，更依赖手工联调与关键日志验证。

## 2. 后端测试框架与运行命令

### 2.1 `pytest` 约定

- 配置文件：`backend/pytest.ini`
- 约定内容：
  - `testpaths = tests`
  - `python_files = test_*.py`
  - `python_classes = Test*`
  - `python_functions = test_*`

### 2.2 常用命令

- 后端依赖安装：

```bash
cd backend
pip install -r requirements.txt
```

- 运行 pytest：

```bash
cd backend
pytest
```

- 启动本地 FastAPI 服务做手工联调：

```bash
cd backend
python -m uvicorn app.启动器:app --reload --port 8001
```

## 3. 当前仓库里的实际测试 / 联调文件

### 3.1 后端排查脚本

- `backend/test_real_request.py`
- `backend/test_full_context.py`
- `backend/test_by_alias_error.py`

### 3.2 根目录联调脚本

- `test_doudian.py`

### 3.3 需要特别说明的“非 pytest 测试文件”

- `backend/app/tasks/test_tasks.py`
- 该文件是 Celery 业务任务，不是 pytest 测试用例。

## 4. 当前覆盖范围说明

### 4.1 当前已有

- 登录 / 聊天 / Agent 图构建的本地脚本级联调
- 手工接口联调脚本
- 部分 Celery、Worker、日志推流链路的业务级验证

### 4.2 当前暂无

- 实际存在的 `backend/tests/` 完整测试目录
- 前端自动化测试框架（Vitest / Jest / Cypress / Playwright）
- 明确的覆盖率阈值

## 5. 当前测试现状的注意点

- `pytest.ini` 指向 `backend/tests/`，但当前仓库未见该目录。
- `.vscode/launch.json` 中引用的部分测试路径（如 `../tests/security/test_sandbox.py`）当前仓库也未见实际文件。
- 因此当前测试体系更接近“配置已预留 + 联调脚本为主”，不能简单视为一个完备的自动化测试仓库。

## 6. 前后端手工验证建议

### 6.1 后端接口改动

- 至少提供 1 条可复现的接口验证步骤。
- 建议附：
  - 请求示例
  - 响应示例
  - 关键日志片段

### 6.2 前端页面改动

- 至少提供 1 条可复现的手工验证路径。
- 建议附页面截图，尤其是列表、表单、流式消息、日志页面等可视化变化。

### 6.3 SSE / 飞书 / Worker / 影刀链路

- 建议附：
  - SSE 连接建立与心跳日志
  - 飞书消息收发日志
  - Worker 注册 / 心跳请求示例
  - 影刀日志推流与状态回调示例

## 7. 建议的最小回归清单

- 登录成功并拿到 JWT。
- `Agent聊天` 页面可以正常建立 SSE 会话。
- `Agent智能体` 页面能读取 Agent、工具、编排、定时任务数据。
- `工具管理` 页面能完成工具列表读取与基础 CRUD。
- `机器管理` 页面能看到 Worker 列表，心跳时间正常刷新。
- `自动化日志` 页面能获取 SSE token，建立日志流，并读取历史日志。
- `飞书表管理`、`基础配置` 页面能正常加载配置数据。

## 8. 特殊链路测试提示

### 8.1 Celery / Worker

- 先验证 Redis 可达，再验证 Worker 注册与心跳，再验证 `echo-test` 派发。
- 不要只看任务是否提交成功，还要看：
  - `task_dispatches` 是否落库
  - Worker 状态是否在线
  - 指定队列是否正确

### 8.2 Shadowbot / 日志推流

- 需要区分：
  - `POST /api/logs/push`：外部日志写入
  - `GET /api/logs/stream`：前端 SSE 订阅
  - `GET /api/logs/history`：历史日志补偿读取
- 日志实时流失败时，还要检查前端 3 秒兜底轮询是否补回数据。

### 8.3 飞书长连接

- 飞书链路不仅要看回包，还要看：
  - 长连接是否成功建立
  - `open_id` 是否正确映射到会话
  - 重复消息是否被去重

## 9. 现阶段限制与风险

- 根目录和后端联调脚本中存在本地硬编码 URL / 账号 / 口令示例，只能用于本地调试，不能直接复制到生产环境。
- `Agent/README.md`、`Agent/.env.example`、部分依赖和调试配置仍带模板痕迹，不应把模板文件误当成测试真相。
- 仓库当前更适合“局部改动后跑定向验证”，不适合宣称已具备高覆盖率自动化回归。

## 10. 当前项目暂无此内容

- 当前仓库未见独立性能测试框架、压测脚本或 E2E 自动化测试平台配置。
