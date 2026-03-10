# 代码风格与命名规范

> 本文件承接原根目录 `AGENTS.md` 中的「代码风格与命名规范」「协作规范」「注意事项与红线」内容，重点回答：代码怎么命名、如何落位、如何协作、哪些事情不能做。

## 1. 命名与风格事实

### 1.1 后端 Python 命名事实

- 文件命名：
  - 基础/通用文件常见英文：`schemas.py`、`celery_app.py`
  - 业务域模块大量使用中文文件名：`启动器.py`、`配置.py`、`对话.py`、`机器管理.py`
- 类命名：
  - ORM 模型：中文或中英混合，如 `用户模型`、`Agent模型`、`Worker模型`
  - 请求体模型：中文类名，如 `创建Agent请求`、`Worker心跳请求`
- 函数命名：
  - 业务函数大量中文，如 `获取对话列表`、`启动飞书长连接`、`派发Echo测试`
  - 少量英文标识用于兼容外部协议或库要求，如 `dispatch_id`、`agent_id`
- 常量/环境变量：
  - 环境变量与协议字段统一用大写英文，如 `JWT_SECRET_KEY`、`REDIS_URL`
  - 常量文件中使用英文常量名，如 `DEFAULT_MODEL`、`RAGFLOW_TIMEOUT`

### 1.2 前端 TypeScript / React 命名事实

- 组件、页面文件：`PascalCase`，如 `AgentChat.tsx`、`ShadowbotLogs.tsx`
- API、类型、store 文件：小写英文语义名，如 `agents.ts`、`chatStore.ts`
- 变量、函数：`camelCase`
- 路由 path：英文小写路径，如 `/agent`、`/workers`、`/logs`
- 类型字段：
  - 前端自有表单与显示数据多为 `camelCase`
  - 与后端直接对接的部分类型保留后端字段风格，如 `Worker.machine_id`、`Conversation.created_at`

### 1.3 API 路由命名风格

- 整体采用 `/api/...` 前缀
- 资源名使用英文：
  - `/api/agents`
  - `/api/tools`
  - `/api/schedules`
  - `/api/feishu/tables`
  - `/api/task-dispatches`
- 特定动作路径使用英文短语或连字符：
  - `/api/chat`
  - `/api/logs/sse-token`
  - `/api/task-dispatches/echo-test`
- 路径参数统一英文命名，如 `tool_id`、`schedule_id`、`conversation_id`

### 1.4 数据库表名和字段命名风格

- 表名：英文 `snake_case`，多数为复数名词，如 `users`、`agents`、`messages`、`task_dispatches`
- 列名：英文 `snake_case`
- ORM 属性：中文为主，通过 `Column("english_name", ...)` 进行映射

## 2. 代码落位原则

### 2.1 前端

- 页面写在 `Agent/src/views/`
- 通用组件写在 `Agent/src/components/`
- API 请求集中在 `Agent/src/api/`
- 类型集中在 `Agent/src/types/`
- 聊天模块级状态集中在 `Agent/src/stores/chatStore.ts`

### 2.2 后端

- 路由层写在 `backend/app/api/`
- 核心业务尽量下沉到 `services/`、`tasks/`、`图引擎/`
- 中文领域模块命名应保持现有风格，不要随意英文化重命名
- 新业务不要在 FastAPI 路由里堆积大量流程控制和数据拼装逻辑

## 3. 协作规范

### 3.1 Git 分支策略（基于实际仓库现状）

- 当前仓库可见分支只有：
  - 本地 `main`
  - 远端 `origin/main`
- 当前未见：
  - `develop`
  - `release/*`
  - `hotfix/*`
- 可据此判断：
  - 当前仓库实际偏向单主干（`main`）协作模式
  - 更细的分支策略当前项目暂无明确文档约束

### 3.2 Commit 消息格式

- 从 `git log --oneline` 可见，提交标题以中文动词短语为主：
  - `增加celery和机器码管理页面，未测试`
  - `优化飞书长连接和多Agent编排问题`
  - `升级OPEN AI SDK`
  - `修复影刀触发状态改回调触发，机器码名字重复优化`
  - `feat: 影刀运行日志前端推流无显示优化`
- 推荐沿用当前仓库风格：
  - `修复...`
  - `优化...`
  - `修改...`
  - `升级...`
  - `feat: ...`

### 3.3 PR / 代码审查流程

- 当前仓库未见独立 PR 流程文档
- 现有仓库规则要求：
  - PR 需说明变更目的、影响目录、配置/数据变更、验证结果
  - 前端改动附截图
  - 后端接口改动附请求/响应示例或日志片段
  - 若修改 `docs/`、`docker-compose.yml`、环境变量约定或数据库模型，要同步更新文档与部署说明

### 3.4 验证与交付要求

- 功能改动至少给出 1 条可复现验证步骤
- 涉及 UI 建议附截图
- 涉及 SSE/飞书/Worker 建议附关键日志或请求示例
- 前端当前没有正式自动化测试框架，不应假设已有 UI 自动回归体系

## 4. 禁止事项（红线）

### 4.1 安全与数据

- 不要提交真实密钥、真实口令、真实生产地址
  - 后端敏感配置位于 `backend/.env`
  - 前端环境变量位于 `Agent/.env*`
- 不要绕过 `app/加密.py` 直接以明文长期存储 LLM API Key 等敏感字段
- 不要在未备份 `backend/data/` 的情况下直接改动数据库结构或做破坏性数据处理

### 4.2 启动与兼容性

- 不要删除或延后 `backend/app/启动器.py` 顶部的 `apply_all_patches()`；它用于修复 Pydantic v2 / OpenAI SDK 兼容问题
- 不要轻易改动 `worker_agent.py` 的注册 → 心跳 → 启动 Worker 顺序
- 不要忽略 `DEFAULT_ADMIN_PASSWORD` 的强口令约束；初始化阶段会拒绝弱口令

### 4.3 架构边界

- 不要把新业务逻辑大量堆在 FastAPI 路由里
- 不要在前端页面组件中散落与多处复制裸请求逻辑，优先复用 `src/api/`
- 不要混淆 `machines`（影刀机器）与 `workers`（Celery Worker）两套数据域

## 5. 容易踩坑的地方

- `machines` 和 `workers` 不是一套概念：
  - `machines`：影刀机器，状态值 `idle/running/offline/error`
  - `workers`：Celery Worker，状态值 `online/offline/busy`
- `系统配置` 是按分类整块 JSON Blob 存储，不是逐字段拆行；前端发什么，后端基本原样存什么
- `Agent/README.md` 和 `Agent/.env.example` 仍带有 AI Studio / Gemini 模板内容，不应视为当前业务真相
- `Agent/package.json` 中存在未直接使用的模板/预留依赖，不要仅凭依赖列表判断功能已落地
- `EventSource` 不能带自定义 Header，因此日志 SSE 用的是短期 token 查询参数，不要误改成 Bearer Header 模式
- `pytest.ini` 指向 `tests/`，但当前仓库主要是联调脚本，不是完整 pytest 套件
- 根目录和后端调试脚本里存在本地示例 URL/账号口令，只能用于本地调试，不能直接复制到生产环境

## 6. 性能与实现敏感点

- `/api/chat` 和 `/api/logs/stream` 都是 SSE 长连接
- SQLite 已启用 WAL，但高并发写入仍需谨慎
- Python 工具通过子进程 + RestrictedPython + 资源限制运行，不能随意放宽超时和资源限制
- 飞书长连接依赖进程内缓存，重启后缓存会消失
- 大文件如 `Agent/src/views/ShadowbotLogs.tsx`、`Agent/src/views/Agent.tsx`、`Agent/src/views/Tools.tsx` 修改时要额外注意回归范围

## 7. 现有规则整合

- 前端默认风格：2 空格缩进、单引号、函数组件
- 后端默认风格：PEP 8、4 空格缩进、中文业务命名保留
- 若修改 `docs/`、环境变量、Docker、数据库模型，应同步更新配套文档
- 代码审查命令 `.claude/commands/audit.md` 重点关注：
  - 超过 50 行的函数
  - 嵌套超过 3 层的逻辑
  - 重复代码块
  - 命名不清晰
  - 魔法数字
  - 类型不安全
  - 内存泄漏与安全漏洞

