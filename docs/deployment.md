# 部署与环境配置

> 本文档承接原 `AGENTS.md` 中关于部署环境、环境变量、外部服务、Docker、本地启动和调试入口的详细说明，重点回答“这个项目依赖什么、怎么配 `.env`、怎么启动、怎么部署”。

## 1. 部署环境概览

### 1.1 后端

- 框架：FastAPI
- 运行方式：`uvicorn`
- Python 版本：仓库当前使用 Python 3 体系
- 典型部署方式：
  - 本地直接运行
  - `backend/docker-compose.yml`

### 1.2 前端

- 框架：React + TypeScript + Vite
- 典型部署方式：
  - 本地 `npm run dev`
  - Docker + Nginx 托管静态文件

### 1.3 数据库与消息队列

- 数据库：SQLite，默认文件位于 `backend/data/app.db`
- 消息队列 / 结果后端：Redis
- Celery：依赖 Redis 作为 Broker / Backend

### 1.4 外部服务

- OpenAI 兼容大模型接口
- 飞书开放平台
- RAGFlow
- SMTP 邮件服务
- 影刀 / Shadowbot
- 外部 `worker_agent.py` + Celery Worker
- 预留项：N8N / WeCom

## 2. 环境变量

### 2.1 后端应用环境变量

| 变量名 | 用途 | 是否必填 | 默认值 / 回退 |
|---|---|---:|---|
| `JWT_SECRET_KEY` | JWT 签名密钥 | 生产必填 | 未设置时自动生成随机密钥 |
| `JWT_EXPIRE_HOURS` | JWT 过期小时数 | 否 | `24` |
| `DATABASE_URL` | 数据库连接串 | 否 | `sqlite:///./data/app.db` |
| `DEFAULT_ADMIN_PASSWORD` | 首次初始化默认管理员密码 | 初始化时必填强口令 | 当前代码无安全默认值 |
| `APP_ENV` | 环境标识 | 否 | `dev` |
| `DISABLE_DOCS_IN_PROD` | 生产是否禁用文档 | 否 | `true` |
| `LOG_LEVEL` | 日志等级 | 否 | `INFO` 或 `DEBUG`（按环境回退） |
| `CORS_ORIGINS` | CORS 白名单 | 生产必填 | 开发为空时回退 `http://localhost:3000`；设为 `*` 仅开发可用 |
| `REDIS_URL` | Redis / Celery 地址 | 否 | `redis://192.168.0.43:6380/0` |
| `CELERY_BROKER_URL` | Celery Broker 地址 | 否 | 回退 `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | Celery Result Backend | 否 | 回退 `REDIS_URL` |
| `CELERY_DEFAULT_QUEUE` | Celery 默认队列名 | 否 | `worker.default` |
| `RPA_PUSH_KEY` | 影刀日志/回调鉴权密钥 | 生产建议必填 | `changeme-rpa-key-2026` |
| `OPENAI_API_KEY` | 默认 OpenAI 兼容 API Key | 按是否启用相关能力决定 | 空字符串 |
| `OPENAI_BASE_URL` | 默认 OpenAI 兼容接口地址 | 否 | `https://api.openai.com/v1` |
| `DEFAULT_MODEL` | 默认模型名 | 否 | `gpt-4o-mini` |
| `MAX_HISTORY_ROUNDS` | 对话上下文轮数上限 | 否 | `10` |
| `MAX_TOKENS` | 对话最大 token 配置 | 否 | `4000` |
| `RAGFLOW_BASE_URL` | RAGFlow 地址 | 否 | `http://localhost:9380` |
| `RAGFLOW_API_KEY` | RAGFlow API Key | 否 | 空字符串 |
| `RAGFLOW_DATASET_IDS` | RAGFlow 数据集列表 | 否 | 空字符串 |
| `ENCRYPTION_KEY` | 敏感字段加密密钥 | 否 | 回退 `JWT_SECRET_KEY` |

### 2.2 外部 `worker_agent.py` 环境变量

| 变量名 | 用途 | 是否必填 | 默认值 / 回退 |
|---|---|---:|---|
| `SERVER_URL` | 后端服务地址 | 是 | 无 |
| `MACHINE_ID` | 当前机器唯一标识 | 是 | 无 |
| `RPA_KEY` | `X-RPA-KEY` 的值 | 是 | 无 |

### 2.3 前端环境变量

| 变量名 | 用途 | 是否必填 | 默认值 / 回退 |
|---|---|---:|---|
| `VITE_API_BASE_URL` | 前端 API 基地址 | 否 | `/api` |
| `VITE_SKIP_AUTH` | 出现在 `Agent/.env` 中 | 当前源码未见直接使用 | 空 |
| `GEMINI_API_KEY` | 出现在 `Agent/.env.example` 与 `vite.config.ts` | 当前前端业务源码未见直接使用 | 模板占位 |
| `APP_URL` | 出现在 `Agent/.env.example` | 当前前端业务源码未见直接使用 | 模板占位 |
| `DISABLE_HMR` | Vite 开发 HMR 开关 | 否 | 非 `true` 时启用 HMR |

### 2.4 当前项目暂无此内容

- 当前仓库未见额外的集中式密钥管理系统文档或 K8s Secret 编排说明。

## 3. 外部服务配置说明

### 3.1 OpenAI 兼容大模型接口

- 用途：
  - 单 Agent 对话
  - 多 Agent 编排
  - 记忆提取
- 对接方式：
  - `langchain_openai.ChatOpenAI`
  - 或 `httpx` 直接请求兼容 OpenAI 的接口
- 关键配置项：
  - Agent 级：`llmApiUrl`、`llmApiKey`、`llmModel`
  - 环境级：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`DEFAULT_MODEL`

### 3.2 飞书开放平台

- 用途：
  - 飞书 IM 消息接收与回复
  - 飞书多维表格读写
- 对接方式：
  - `lark-oapi` WebSocket 长连接
  - HTTP 调用飞书开放平台 API
- 关键配置项：
  - `system_config.feishu.appId`
  - `system_config.feishu.appSecret`
  - `system_config.feishu.feishuEventAgentId`

### 3.3 RAGFlow

- 用途：知识检索增强
- 对接方式：`POST {RAGFLOW_BASE_URL}/api/v1/retrieval`
- 关键配置项：
  - `RAGFLOW_BASE_URL`
  - `RAGFLOW_API_KEY`
  - `RAGFLOW_DATASET_IDS`
- 当前特性：
  - 未配置时静默跳过，不阻塞对话

### 3.4 SMTP 邮件

- 用途：
  - 内置邮件工具
  - 影刀触发邮件
- 对接方式：
  - `smtplib.SMTP`
  - `SMTP_SSL`
- 关键配置项：
  - `system_config.email.smtpServer`
  - `system_config.email.smtpPort`
  - `system_config.email.sender`
  - `system_config.email.smtpPassword`

### 3.5 影刀 / Shadowbot

- 用途：
  - 通过邮件触发应用执行
  - 外部日志回推
  - 机器状态回调
- 对接方式：
  - 邮件触发
  - `POST /api/logs/push`
  - `PUT /api/machines/{machine_id}/status`
- 关键配置项：
  - `RPA_PUSH_KEY`
  - `system_config.shadowbot.targetEmail`
  - `system_config.shadowbot.subjectTemplate`
  - `system_config.shadowbot.contentTemplate`

### 3.6 Redis / Celery / 外部 Worker

- 用途：
  - 后端调度派发
  - 外部机器执行 Celery 任务
- 对接方式：
  - Redis 作为 Broker / Backend
  - `worker_agent.py` 先注册、再心跳、再启动 Celery Worker
- 关键配置项：
  - `REDIS_URL`
  - `SERVER_URL`
  - `MACHINE_ID`
  - `RPA_KEY`

### 3.7 N8N / WeCom

- N8N：
  - 前端配置项存在，数据库也有 `n8n_workflows` 表
  - 当前项目暂无明确 API 路由或服务层业务调用
- WeCom：
  - 仅在前端基础配置页与配置类型中出现
  - 当前项目暂无后端实际对接逻辑

## 4. 本地开发启动

### 4.1 前端

```bash
cd Agent
npm install
npm run dev
```

- 默认监听：`0.0.0.0:3000`
- 开发代理：`/api -> http://localhost:8001`

### 4.2 后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.启动器:app --reload --port 8001
```

- 启动时会执行：
  - 应用 Pydantic / OpenAI monkey patch
  - 初始化数据库
  - 注册内置工具
  - 清理无效 Agent 工具引用
  - 启动飞书长连接
  - 启动 APScheduler

### 4.3 外部 Worker（按需）

```bash
cd backend
set SERVER_URL=http://<backend-host>:8001
set MACHINE_ID=machine-a
set RPA_KEY=<same-as-RPA_PUSH_KEY>
python worker_agent.py
```

## 5. 依赖安装命令

- 前端：`cd Agent && npm install`
- 后端：`cd backend && pip install -r requirements.txt`

## 6. Docker 部署步骤

### 6.1 后端

```bash
cd backend
docker-compose up -d --build
```

- 包含服务：
  - `redis`
  - `backend`
- 数据卷：
  - `./data:/app/data`
  - `./.env:/app/.env`

### 6.2 前端

```bash
cd Agent
docker-compose up -d --build
```

- 端口：`1254:80`
- Nginx 会把 `/api/*` 代理到容器内的 `backend:8001`

## 7. 数据库迁移策略

- 当前项目暂无 Alembic 或其他显式迁移工具。
- 当前策略：
  - 启动时自动建表
  - 变更表结构时人工修改模型
  - 兼顾已有 SQLite 数据
- 因此在改动数据库结构前，应先备份 `backend/data/`。

## 8. VS Code 调试入口

- `.vscode/launch.json` 提供：
  - 后端开发启动
  - 后端“生产模拟”启动
  - pytest 调试入口
- `.vscode/tasks.json` 提供：
  - 前端 dev
  - 前端 build + preview
  - 后端 pip install
  - 前端 npm install

## 9. 部署注意事项

- 生产环境不要提交真实密钥、真实口令、真实生产地址。
- `DEFAULT_ADMIN_PASSWORD` 必须设置强口令，否则启动初始化会拒绝创建默认用户。
- 涉及 SSE 的代理链路必须关闭 buffering，尤其是：
  - `/api/chat`
  - `/api/logs/stream`
- SQLite 已启用 WAL，但仍是单文件数据库；并发日志写入、调度与 Worker 状态更新增高时要谨慎。
- 修改 `docs/`、Docker、环境变量约定或数据库模型时，要同步更新部署说明。
