# 前端页面设计

> 本文档承接原 `AGENTS.md` 中与前端技术栈、目录结构、页面职责、接口封装和环境变量相关的详细说明，重点回答“前端有哪些页面、各自负责什么、数据从哪里来、修改时应注意什么”。

## 1. 前端技术栈与运行方式

- 技术栈：React + TypeScript + Vite
- UI 组织方式：单页应用（SPA）
- 运行入口：`Agent/src/router/index.tsx`
- 容器代理：生产环境通常由 Nginx 托管，并将 `/api/*` 代理到后端
- 本地开发默认：
  - 前端：`0.0.0.0:3000`
  - 代理：`/api -> http://localhost:8001`

## 2. 前端目录与分层

### 2.1 关键目录

- `Agent/src/views/`：页面级组件
- `Agent/src/components/`：通用布局和复用组件
- `Agent/src/api/`：接口封装
- `Agent/src/types/`：类型定义
- `Agent/src/router/`：路由配置
- `Agent/src/stores/`：状态与交互辅助逻辑

### 2.2 落位原则

- 页面逻辑优先放在 `views/`
- 可复用 UI 放在 `components/`
- 网络请求集中放在 `api/`
- 类型声明集中放在 `types/`
- 不要把后端业务判断复制到前端页面里“硬写一份”

## 3. 路由结构

### 3.1 鉴权与布局

- `/login`：登录页
- `/`：受保护布局页，进入前会检查 `localStorage` 中是否存在 `token`
- 若未登录，则由路由守卫重定向到 `/login`
- 登录后，所有主页面都挂在 `Layout` 下

### 3.2 菜单与页面总览

| 路径 | 页面组件 | 菜单名称 | 主要职责 |
|---|---|---|---|
| `/login` | `Login.tsx` | 登录 | 用户鉴权、保存 JWT |
| `/` | `AgentChat.tsx` | Agent聊天 | 对话、历史会话、SSE 流式回复 |
| `/agent` | `Agent.tsx` | Agent智能体 | Agent 管理、编排管理、定时任务管理 |
| `/tools` | `Tools.tsx` | 工具管理 | 工具市场、工具注册、工具 CRUD |
| `/workers` | `Workers.tsx` | 机器管理 | Worker 列表与状态查看 |
| `/logs` | `ShadowbotLogs.tsx` | 自动化日志 | 影刀机器、应用绑定、日志 SSE、历史日志 |
| `/feishu` | `FeishuTables.tsx` | 飞书表管理 | 飞书多维表格配置管理 |
| `/config` | `BasicConfig.tsx` | 基础配置 | 系统配置、第三方配置、事件 Agent 选择 |

## 4. 各页面职责

### 4.1 `Login.tsx`

- 调用 `Agent/src/api/auth.ts` 中的登录接口。
- 成功后把 JWT 保存到 `localStorage`。
- 失败时展示错误信息，不负责后续权限续期逻辑。

### 4.2 `AgentChat.tsx`

- 是默认首页，也是核心对话页面。
- 主要职责：
  - 拉取会话列表
  - 拉取会话消息
  - 建立 `/api/chat` SSE 对话
  - 联动 Agent 列表与编排配置
- 相关接口：
  - `Agent/src/api/chat.ts`
  - `Agent/src/api/conversations.ts`
  - `/api/orchestration`
  - `/api/agents`
- 页面特点：
  - 对滚动定位、流式消息增量展示比较敏感
  - 改动时需要重点关注 SSE 回归

### 4.3 `Agent.tsx`

- 负责 Agent、编排和定时任务的统一管理。
- 相关接口：
  - `Agent/src/api/agents.ts`
  - `Agent/src/api/tools.ts`
  - `Agent/src/api/schedule.ts`
- 页面职责：
  - Agent CRUD
  - 关联工具
  - 管理多 Agent 编排
  - 管理定时任务
- 注意：
  - 这是仓库中的大页面之一，改动时要注意拆分风险和回归影响。

### 4.4 `Tools.tsx`

- 负责工具市场与注册管理。
- 相关接口：
  - `Agent/src/api/tools.ts`
  - `Agent/src/api/index.ts`
- 页面职责：
  - 展示工具列表
  - 添加 / 编辑 / 删除工具
  - 进行工具测试
- 注意：
  - 存在“市场 / 注册”标签页切换，涉及动态表单与工具参数结构。

### 4.5 `Workers.tsx`

- 负责展示 Celery Worker 列表及心跳状态。
- 相关接口：
  - `Agent/src/api/workers.ts`
- 页面职责：
  - 读取 Worker 列表
  - 展示 `machine_id`、`hostname`、`ip`、`queue_name`、`status`、`last_heartbeat`、`tags`
- 页面定位：
  - 这是 Celery Worker 视角，不是影刀机器视角。

### 4.6 `ShadowbotLogs.tsx`

- 负责影刀自动化相关的综合页面。
- 相关接口：
  - `/api/logs/sse-token`
  - `/api/logs/stream`
  - `/api/logs/history`
  - `/api/machines`
  - `/api/machine-apps`
- 页面职责：
  - 机器列表管理
  - 机器应用绑定管理
  - 实时日志订阅
  - 历史日志回放
  - 失败时的轮询兜底
- 页面特点：
  - 前端先获取短期 token，再通过 `EventSource` 连接 SSE
  - 收到 `type=heartbeat` 的消息时只做保活，不作为业务日志展示
  - 这是仓库中另一个大页面，改动时需重点看日志流回归

### 4.7 `FeishuTables.tsx`

- 调用 `Agent/src/api/feishu.ts`
- 页面职责：
  - 飞书多维表格记录增删改查
  - 管理表格元数据和字段映射

### 4.8 `BasicConfig.tsx`

- 调用 `Agent/src/api/config.ts`
- 同时会读取 Agent 列表辅助配置事件 Agent
- 页面职责：
  - 管理 `email`、`shadowbot`、`feishu`、`n8n`、`ragflow`、`wecom` 等分类配置
- 数据特点：
  - 后端按分类整块 JSON Blob 存储，前端提交什么，后端基本原样存什么

## 5. 接口封装与数据流

### 5.1 API 模块

- 当前 `Agent/src/api/` 下可见模块：
  - `agents.ts`
  - `auth.ts`
  - `chat.ts`
  - `config.ts`
  - `conversations.ts`
  - `feishu.ts`
  - `index.ts`
  - `logs.ts`
  - `schedule.ts`
  - `tools.ts`
  - `workers.ts`

### 5.2 通用请求特点

- 绝大多数业务接口走 `/api/*`
- 普通接口依赖 JWT Bearer
- 日志 SSE 例外：
  - 先请求 `/api/logs/sse-token`
  - 再拼接到 `/api/logs/stream?token=...`

### 5.3 状态与存储

- 当前前端主要通过 React 本地状态 + 少量 store 辅助管理页面数据。
- 登录态保存在 `localStorage` 的 `token` 中。
- 路由守卫基于 `token` 是否存在进行跳转控制。

## 6. 前端环境变量

| 变量名 | 用途 | 是否必填 | 默认值 / 说明 |
|---|---|---:|---|
| `VITE_API_BASE_URL` | 前端 API 基地址 | 否 | `/api` |
| `VITE_SKIP_AUTH` | 出现在 `Agent/.env` 中 | 当前源码未见直接使用 | 空 |
| `GEMINI_API_KEY` | 出现在 `Agent/.env.example` 与 `vite.config.ts` | 当前前端业务源码未见直接使用 | 模板占位 |
| `APP_URL` | 出现在 `Agent/.env.example` | 当前前端业务源码未见直接使用 | 模板占位 |
| `DISABLE_HMR` | Vite 开发 HMR 开关 | 否 | 非 `true` 时启用 HMR |

## 7. 设计与实现注意事项

### 7.1 现有风格

- 2 空格缩进
- 单引号
- 函数组件

### 7.2 已知注意点

- `Agent/README.md` 和 `Agent/.env.example` 仍带有 AI Studio / Gemini 模板内容，不应直接视为当前业务真相。
- `Agent/package.json` 中存在模板 / 预留依赖，不能仅凭依赖列表判断功能已经上线。
- 日志 SSE 不能改成自定义 Header 鉴权，因为浏览器 `EventSource` 不支持。
- 大页面修改时要特别注意：
  - `Agent/src/views/ShadowbotLogs.tsx`
  - `Agent/src/views/Agent.tsx`
  - `Agent/src/views/Tools.tsx`

### 7.3 当前代码中的页面入口现状

- 实际路由使用的是 `Agent/src/views/*.tsx` 这一组页面文件。
- `Agent/src/views/Agent/`、`Agent/src/views/Logs/`、`Agent/src/views/Feishu/`、`Agent/src/views/Config/` 下还存在占位或模板式入口文件，但当前主路由并未使用它们。

## 8. 手工验证建议

- 登录后应能跳转到 `/` 并正常拉取首页数据。
- `Agent聊天` 页面应能发起对话并收到流式回复。
- `Agent智能体` 页面应能同时读取 Agent、工具、编排、定时任务数据。
- `机器管理` 页面应能看到 Worker 心跳时间变化。
- `自动化日志` 页面应能建立 `EventSource` 连接并收到心跳或日志消息。

## 9. 当前项目暂无此内容

- 当前前端未见独立的设计系统文档、页面原型图仓库或自动生成的组件 Storybook。
