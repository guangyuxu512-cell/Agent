# 架构设计

> 本文件承接原根目录 `AGENTS.md` 中的「项目概述」「技术栈」「项目结构」「核心模块说明」以及部分性能说明，重点回答：项目如何分层、模块如何协作、目录如何组织。

## 1. 项目概述

### 1.1 项目名称与一句话介绍

- 项目名称：`Agent 平台`
- 一句话介绍：一个集「多智能体管理与编排、流式对话、工具调用、定时任务、飞书接入、影刀联动、Celery Worker 管理」于一体的内部自动化平台。

### 1.2 核心业务场景和目标用户

- 核心业务场景：
  - 通过 Web 控制台管理 Agent、工具、编排配置和定时任务
  - 通过 Web SSE 对话或飞书消息与 Agent 交互
  - 通过 HTTP 工具、Python 沙箱工具、内置邮件/飞书/影刀工具完成自动化操作
  - 通过 APScheduler + Celery 将任务派发给指定机器执行
  - 通过影刀日志推流、机器状态回调、机器应用绑定管理自动化执行现场
- 目标用户：
  - 内部管理员/配置人员
  - 自动化运营人员、RPA 运维人员
  - 负责 Agent/工具/飞书接入的开发与联调人员

### 1.3 整体架构简图（文字版）

- 前端 `Agent/`：React + TypeScript + Vite 单页应用，经 Nginx 托管，并把 `/api/*` 代理到后端。
- 后端 `backend/app/`：FastAPI 提供鉴权、智能体、对话、工具、配置、飞书、影刀、Celery Worker、任务派发等 API。
- 数据库：默认使用 SQLite（`backend/data/app.db`），由 SQLAlchemy 自动建表，并启用 WAL。
- 消息队列：Redis 作为 Celery Broker / Backend。
- 外部服务：
  - OpenAI 兼容大模型接口
  - 飞书开放平台（消息、长连接、多维表格）
  - RAGFlow 检索 API
  - SMTP 邮箱
  - 影刀/Shadowbot 外部机器与日志回调
  - 局域网/外部机器上的 `worker_agent.py` + Celery Worker

## 2. 技术栈

### 2.1 后端

- 语言：Python
- 运行时版本：
  - Docker 镜像使用 `python:3.11-slim`，见 `backend/Dockerfile`
  - `requirements.txt` 约束：
    - `fastapi==0.115.*`
    - `uvicorn[standard]==0.34.*`
    - `sqlalchemy==2.0.*`
    - `pydantic==2.10.*`
    - `celery>=5.4,<6`
    - `redis>=5.0,<6`
    - `python-jose[cryptography]==3.3.*`
    - `passlib[bcrypt]==1.7.*`
    - `bcrypt==4.0.1`
    - `python-dotenv==1.0.*`
    - `apscheduler>=3.10.0`
    - `httpx>=0.27.0`
    - `cryptography>=42.0.0`
    - `RestrictedPython>=7.0`
    - `langgraph` / `langchain-openai` / `langgraph-supervisor` / `langgraph-swarm`
    - `lark-oapi>=1.3.0`

### 2.2 前端

- 语言：TypeScript
- 框架与构建：
  - `react ^19.0.0`
  - `react-dom ^19.0.0`
  - `react-router-dom ^7.13.0`
  - `vite ^6.2.0`
  - `typescript ~5.8.2`
  - `@vitejs/plugin-react ^5.0.4`
  - `@tailwindcss/vite ^4.1.14`
- 常用库：
  - `axios`
  - `lucide-react`
  - `react-markdown`
- 现状说明：
  - `Agent/package.json` 中还保留 `@google/genai`、`better-sqlite3`、`dotenv`、`express`、`motion` 等依赖，但当前 `Agent/src/` 未见直接 import，属于模板/预留依赖的可能性较高。

### 2.3 数据库

- 类型：SQLite
- 默认地址：`sqlite:///./data/app.db`
- 用途：
  - 用户、Agent、对话消息、工具、系统配置、飞书表格、记忆、影刀日志、机器/应用绑定、Celery Worker、任务派发等持久化
- ORM：SQLAlchemy 2.x
- 初始化方式：
  - 启动时 `Base.metadata.create_all()`
  - SQLite 连接阶段和会话阶段均启用 `WAL` 模式

### 2.4 消息队列 / 缓存

- Redis：
  - 用作 Celery Broker / Result Backend
  - 默认值：`redis://192.168.0.43:6380/0`
- Celery：
  - 执行定时任务与 `echo_test`
  - 按 `worker.{machine_id}` 队列定向派发

### 2.5 外部服务 / 第三方集成

- OpenAI 兼容大模型接口：用于单 Agent、多 Agent、记忆提取
- 飞书开放平台：
  - WebSocket 长连接接收消息
  - IM 主动回复/发送消息
  - Bitable 读写
- RAGFlow：知识检索增强
- SMTP：普通邮件发送、影刀触发邮件发送
- 影刀 / Shadowbot：
  - 外部日志推流
  - 机器状态回调
  - 邮件触发影刀应用执行
- 当前仅有配置占位、尚未形成明确业务链路的集成：
  - N8N（前端配置项 + 表结构存在，但未见直接业务调用代码）
  - 企业微信 WeCom（前端配置项存在，后端未见对接实现）

### 2.6 部署环境

- 已明确支持：
  - Docker / Docker Compose
  - Nginx 反向代理前端静态资源与后端 API/SSE
  - 局域网多机器 Worker（见 Celery 相关文档与 `backend/worker_agent.py`）
- 当前项目暂无明确代码或专门脚本支持：
  - 群晖专用部署方案
  - 公有云专用 IaC 模板

## 3. 项目结构

### 3.1 一级与二级目录树

```text
.
├─ .claude/                      # Claude/Codex 辅助命令与本地设置
│  └─ commands/                 # 自定义审查命令
├─ .vscode/                     # VS Code 启动与任务配置
├─ Agent/                       # React + TypeScript 前端
│  ├─ dist/                     # 前端构建产物（生成目录）
│  ├─ node_modules/             # 前端依赖（生成目录）
│  └─ src/                      # 前端源码
├─ backend/                     # FastAPI + Celery 后端
│  ├─ .pytest_cache/            # pytest 缓存（生成目录）
│  ├─ app/                      # 后端核心源码
│  ├─ data/                     # SQLite 数据目录
│  └─ __pycache__/              # Python 缓存（生成目录）
├─ docs/                        # 项目、部署、Celery 等专题文档
└─ EAgentdocs/                 # 当前为空的异常命名目录，未见代码引用
```

### 3.2 关键目录与文件说明

#### 根目录

- `AGENTS.md`：项目协作入口与摘要
- `test_doudian.py`：根目录联调脚本，直接登录本地后端并触发聊天，不是正式测试
- `.claude/commands/audit.md`：代码审查指令模板
- `.vscode/launch.json`：后端调试与 pytest 调试配置
- `.vscode/tasks.json`：前后端安装与启动任务

#### `Agent/`

- `Agent/package.json`：前端依赖与脚本入口
- `Agent/vite.config.ts`：Vite 配置，开发时代理 `/api` 到 `http://localhost:8001`
- `Agent/tsconfig.json`：TS 编译配置
- `Agent/Dockerfile`：前端两阶段构建镜像
- `Agent/docker-compose.yml`：前端容器编排
- `Agent/nginx.conf`：Nginx 代理 `/api/chat`、`/api/logs/stream` 等 SSE 路由
- `Agent/.env` / `Agent/.env.development` / `Agent/.env.example`：前端环境变量和模板
- `Agent/src/main.tsx`：前端入口
- `Agent/src/router/index.tsx`：路由定义与登录守卫入口
- `Agent/src/components/`：布局、边栏、错误边界、改密弹窗等通用组件
- `Agent/src/api/`：Axios 封装与业务 API 模块
- `Agent/src/types/`：前端类型定义
- `Agent/src/stores/chatStore.ts`：聊天模块级状态存储，管理 SSE 对话流和 localStorage
- `Agent/src/views/`：页面组件

#### `backend/`

- `backend/requirements.txt`：后端依赖清单
- `backend/Dockerfile`：后端镜像构建
- `backend/docker-compose.yml`：Redis + Backend 组合部署
- `backend/.env`：后端本地环境变量
- `backend/worker_agent.py`：外部机器运行的注册/心跳/Celery Worker 启动器
- `backend/check_db.py`、`backend/fix_agent_status.py`：一次性维护脚本
- `backend/test_real_request.py`、`backend/test_full_context.py`、`backend/test_by_alias_error.py`：本地联调/问题排查脚本
- `backend/app/启动器.py`：FastAPI 入口文件
- `backend/app/配置.py`：环境变量读取
- `backend/app/常量.py`：集中常量
- `backend/app/schemas.py`：统一响应模型
- `backend/app/加密.py`：敏感字段加解密
- `backend/app/密码策略.py`：密码强度策略
- `backend/app/monkey_patches.py`：Pydantic / OpenAI SDK 兼容补丁
- `backend/app/celery_app.py`：Celery 应用入口
- `backend/app/调度器.py`：APScheduler 封装

#### `backend/app` 二级目录

- `backend/app/api/`：FastAPI 路由层
- `backend/app/db/`：数据库引擎、会话工厂、ORM 模型
- `backend/app/middleware/`：鉴权中间件
- `backend/app/services/`：任务派发与执行服务
- `backend/app/tasks/`：Celery 任务定义
- `backend/app/图引擎/`：LangGraph、工具加载、RAGFlow、记忆等核心引擎
- `backend/app/飞书/`：飞书长连接、消息处理、会话管理、智能体调用

### 3.3 入口文件

- 前端入口：`Agent/src/main.tsx`
- 前端路由入口：`Agent/src/router/index.tsx`
- 后端入口：`backend/app/启动器.py`
- Celery 入口：`backend/app/celery_app.py`
- 外部机器入口：`backend/worker_agent.py`

## 4. 核心分层与模块关系

### 4.1 鉴权与安全模块

- 职责：
  - 处理 JWT 登录、密码修改、全局鉴权、敏感字段加密
- 关键文件：
  - `backend/app/api/鉴权.py`
  - `backend/app/middleware/鉴权中间件.py`
  - `backend/app/密码策略.py`
  - `backend/app/加密.py`
- 输入输出：
  - 输入：用户名密码、Bearer Token、密码变更请求
  - 输出：JWT、改密结果、401/403 统一响应
- 依赖关系：
  - 依赖 `用户模型`、`配置.py`、`数据库.py` 中的密码工具
- 调用链：
  - 前端 `Login.tsx` → `src/api/auth.ts` → `/api/auth/login` → 返回 JWT → `localStorage`

### 4.2 智能体管理与编排模块

- 职责：
  - 管理 Agent 列表、LLM 配置、工具绑定、编排模式、多 Agent 入口配置
- 关键文件：
  - `backend/app/api/智能体.py`
  - `backend/app/api/编排.py`
  - `Agent/src/views/Agent.tsx`
  - `Agent/src/api/agents.ts`
- 输入输出：
  - 输入：前端 camelCase Agent 表单、编排配置
  - 输出：Agent 列表、单个 Agent、编排配置 JSON
- 依赖关系：
  - 依赖 `Agent模型`、`编排模型`、`工具模型`
  - 与图引擎、对话模块、定时任务模块耦合

### 4.3 对话与图引擎模块

- 职责：
  - 处理单 Agent / 多 Agent 对话
  - 通过 SSE 向前端逐 token 推送
  - 注入工具、记忆和知识检索
- 关键文件：
  - `backend/app/api/对话.py`
  - `backend/app/图引擎/构建器.py`
  - `backend/app/图引擎/多Agent构建器.py`
  - `backend/app/图引擎/上下文.py`
  - `backend/app/图引擎/知识检索.py`
  - `backend/app/图引擎/记忆管理.py`
  - `Agent/src/views/AgentChat.tsx`
  - `Agent/src/stores/chatStore.ts`
- 输入输出：
  - 输入：`agent_id`、`message`、可选 `conversation_id`
  - 输出：SSE 事件流：`conversation_id` / `agent` / `token` / `tool_call` / `tool_result` / `done` / `error`
- 调用链：
  - `AgentChat.tsx` → `chatStore.send()` → `sendMessageSSE()` → `POST /api/chat`
  - 后端 `对话.py` 根据编排决定走单 Agent 图或多 Agent 图
  - 图引擎执行时调用工具、RAGFlow、记忆模块
  - 完成后保存消息并异步提取记忆

### 4.4 工具系统与沙箱执行模块

- 职责：
  - 管理工具 CRUD
  - 加载 HTTP / Python / builtin 工具
  - 对 Python 工具做 RestrictedPython + 子进程沙箱
- 关键文件：
  - `backend/app/api/工具.py`
  - `backend/app/图引擎/工具加载器.py`
  - `backend/app/图引擎/_沙箱执行器.py`
  - `backend/app/图引擎/内置工具/邮件.py`
  - `backend/app/图引擎/内置工具/飞书.py`
  - `backend/app/图引擎/内置工具/影刀触发.py`
- 输入输出：
  - 输入：工具定义（`tool_type`、`parameters`、`config`）
  - 输出：LangGraph Tool 列表、工具测试结果、执行日志

### 4.5 定时任务、APScheduler 与 Celery 模块

- 职责：
  - 管理定时任务 CRUD
  - APScheduler 到点触发
  - Celery 投递与执行
  - 记录执行日志与派发记录
- 关键文件：
  - `backend/app/api/定时任务.py`
  - `backend/app/调度器.py`
  - `backend/app/celery_app.py`
  - `backend/app/services/task_dispatcher.py`
  - `backend/app/services/schedule_executor.py`
  - `backend/app/services/dispatch_records.py`
  - `backend/app/tasks/schedule_tasks.py`
  - `backend/app/tasks/test_tasks.py`
- 调用链：
  - 前端定时任务页 → `/api/schedules`
  - 启动时 `启动调度器()`
  - 到点后 `调度器.py` → `派发定时任务()`
  - 任务进入 Celery 队列 → `schedule_executor.py`
  - 执行结果写入 `schedule_logs` 与 `task_dispatches`

### 4.6 系统配置与飞书表格配置模块

- 职责：
  - 存储整站 JSON Blob 配置
  - 管理飞书表格元数据
- 关键文件：
  - `backend/app/api/系统配置.py`
  - `backend/app/api/飞书表格.py`
  - `Agent/src/views/BasicConfig.tsx`
  - `Agent/src/views/FeishuTables.tsx`
- 输入输出：
  - 输入：email/shadowbot/feishu/n8n/ragflow/wecom 等分类配置
  - 输出：原样 JSON 回显
- 依赖关系：
  - 内置邮件、飞书、影刀触发工具都会读取系统配置

### 4.7 记忆模块

- 职责：
  - 对话结束后调用 LLM 提取长期记忆
  - 新对话开始前查询记忆并注入上下文
- 关键文件：
  - `backend/app/api/记忆.py`
  - `backend/app/图引擎/记忆管理.py`
- 输入输出：
  - 输入：Agent 配置、对话 ID、消息历史
  - 输出：`memories` 记录、上下文注入文本

### 4.8 需要到其他文档查看的专项模块

- Worker 注册、心跳、派发、影刀日志推流、机器状态回调：见 `docs/callback.md`
- API 请求/响应格式、路由清单、错误码：见 `docs/api-spec.md`
- 数据表和字段说明：见 `docs/database.md`
- 前端页面设计与状态流：见 `docs/frontend.md`
- 部署、Docker、环境变量：见 `docs/deployment.md`

## 5. 架构核心原则

- 路由层只负责协议转换、鉴权和基本校验，核心业务优先放在 `services/`、`tasks/`、`图引擎/`
- 前端通过 `src/api/` 统一访问后端，不在页面里散落大量裸请求逻辑
- 系统配置采用“按分类整块 JSON 存储”的策略，前后端尽量保持字段原样透传
- 单 Agent / 多 Agent / 工具执行 / 记忆 / 知识检索保持可插拔，某一项不可用时尽量降级而不是整体失败
- Worker 执行体系采用“APScheduler 负责到点，Celery 负责派发，外部机器负责执行”的分层模式
- 安全相关补丁、沙箱限制、JWT 鉴权和 `X-RPA-KEY` 鉴权属于架构前提，不能随意绕过

## 6. 性能敏感点

- `/api/chat` 为 SSE 长连接，Nginx 代理必须关闭 buffering
- `/api/logs/stream` 也是 SSE 长连接，同时前端还有 3 秒兜底轮询
- SQLite 已启用 WAL，但本质仍是单文件数据库；日志写入、调度、Worker 状态更新并发升高时要谨慎
- Python 工具通过子进程 + RestrictedPython + 资源限制运行，避免随意放宽超时/内存/子进程限制
- 飞书长连接依赖内存中的会话缓存和消息去重集合，进程重启会失去这部分缓存
- 大页面文件如 `Agent/src/views/ShadowbotLogs.tsx`、`Agent/src/views/Agent.tsx`、`Agent/src/views/Tools.tsx` 修改时要注意回归影响

