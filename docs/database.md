# 数据库模型

> 本文件承接原根目录 `AGENTS.md` 中的「数据库命名风格」「数据模型」内容，重点回答：有哪些表、字段是什么意思、模型之间如何关联。

## 1. 数据库与命名事实

### 1.1 数据库类型与初始化

- 类型：SQLite
- 默认地址：`sqlite:///./data/app.db`
- ORM：SQLAlchemy 2.x
- 初始化方式：
  - 启动时 `Base.metadata.create_all()`
  - SQLite 连接阶段和会话阶段均启用 `WAL` 模式

### 1.2 表名和字段命名风格

- 表名：英文 `snake_case`，多数为复数名词，如 `users`、`agents`、`messages`、`task_dispatches`
- 列名：英文 `snake_case`
- ORM 属性：中文为主，通过 `Column("english_name", ...)` 进行映射
- 关系处理：
  - 主要通过 `id` / `agent_id` / `conversation_id` / `machine_id` 等手工关联
  - 当前模型文件未见显式 `ForeignKey` 约束定义

## 2. 表结构总览

当前 ORM 模型文件 `backend/app/db/模型.py` 中定义了 18 张业务表：

1. `users`
2. `agents`
3. `conversations`
4. `messages`
5. `tools`
6. `schedules`
7. `schedule_logs`
8. `orchestration`
9. `system_config`
10. `feishu_tables`
11. `n8n_workflows`
12. `memories`
13. `push_logs`
14. `machines`
15. `machine_apps`
16. `task_queue`
17. `workers`
18. `task_dispatches`

## 3. 各表关键字段与用途

### 3.1 `users`

- `username`：登录用户名
- `password_hash`：密码哈希
- `created_at`：创建时间
- 用途：后台管理登录

### 3.2 `agents`

- `id`：主键
- `name`：Agent 名称
- `role`：角色描述
- `prompt`：系统提示词
- `llm_provider` / `llm_model`：模型提供商与模型名
- `llm_api_url` / `llm_api_key`：模型接口地址与密钥
- `temperature`
- `tools`：绑定工具列表（JSON 字符串）
- `max_iterations`
- `timeout_seconds`
- `require_approval`
- `status`
- `updated_at` / `created_at`
- 用途：定义单个 Agent 的行为与模型配置

### 3.3 `conversations`

- `id`
- `agent_id`
- `title`
- `source`：来源，代码中用于区分 `web` / `feishu`
- `updated_at` / `created_at`
- 用途：对话会话头信息

### 3.4 `messages`

- `id`
- `conversation_id`
- `role`
- `content`
- `agent_name`
- `tool_calls`
- `tool_call_id`
- `created_at`
- 用途：对话消息明细

### 3.5 `tools`

- `id`
- `name`
- `description`
- `tool_type`
- `parameters`
- `config`
- `status`
- `created_at` / `updated_at`
- 用途：HTTP / Python / builtin 工具定义

### 3.6 `schedules`

- `id`
- `name`
- `description`
- `agent_id`
- `trigger_type`
- `trigger_config`
- `prompt`
- `enabled`
- `last_run_at`
- `next_run_at`
- `created_at` / `updated_at`
- 用途：定时任务配置

### 3.7 `schedule_logs`

- `id`
- `schedule_id`
- `status`
- `result`
- `error`
- `started_at`
- `finished_at`
- 用途：定时任务执行历史

### 3.8 `orchestration`

- `id`
- `mode`
- `entry_agent_id`
- `routing_rules`
- `parallel_groups`
- `global_state`
- `updated_at`
- 用途：多 Agent 编排配置

### 3.9 `system_config`

- `id`
- `category`
- `key`
- `value`
- `description`
- `created_at` / `updated_at`
- 用途：系统配置存储
- 现状：按 `category + __data__` 存整块 JSON，而不是逐字段拆行

### 3.10 `feishu_tables`

- `id`
- `name`
- `app_token`
- `table_id`
- `description`
- `field_mapping`
- `created_at` / `updated_at`
- 用途：飞书多维表格元数据

### 3.11 `n8n_workflows`

- `id`
- `name`
- `webhook_url`
- `description`
- `method`
- `headers`
- `sample_payload`
- `enabled`
- `created_at` / `updated_at`
- 用途：预留/存量工作流数据表；当前未见明确业务路由使用

### 3.12 `memories`

- `id`
- `agent_id`
- `conversation_id`
- `memory_type`
- `content`
- `importance`
- `created_at`
- `expires_at`
- 用途：长期记忆

### 3.13 `push_logs`

- `id`：自增序号，前端也把它当 `seq`
- `time`
- `task_id`
- `machine`
- `level`
- `msg`
- `created_at`
- 用途：影刀日志流与历史查询

### 3.14 `machines`

- `id`
- `machine_id`
- `machine_name`
- `status`：`idle / running / error / offline`
- `last_heartbeat`
- `created_at` / `updated_at`
- 用途：影刀机器管理

### 3.15 `machine_apps`

- `id`
- `machine_id`
- `app_name`
- `description`
- `enabled`
- `created_at`
- 用途：机器与影刀应用绑定

### 3.16 `task_queue`

- `id`
- `app_name`
- `machine_id`
- `status`：`waiting / triggered / failed`
- `created_at`
- `triggered_at`
- `error`
- 用途：影刀应用等待触发队列

### 3.17 `workers`

- `id`
- `machine_id`
- `hostname`
- `ip`
- `queue_name`
- `status`：`online / offline / busy`
- `last_heartbeat`
- `tags`
- `created_at` / `updated_at`
- 用途：Celery Worker 元数据

### 3.18 `task_dispatches`

- `dispatch_id`
- `task_name`
- `machine_id`
- `queue_name`
- `schedule_id`
- `status`：`pending / running / success / failed`
- `payload_ref`
- `requested_by`
- `retry_count`
- `submitted_at`
- `finished_at`
- `error_message`
- 用途：Celery 任务派发跟踪

## 4. 关键关联关系

- `conversations.agent_id` → `agents.id`
- `messages.conversation_id` → `conversations.id`
- `schedules.agent_id` → `agents.id`
- `schedule_logs.schedule_id` → `schedules.id`
- `memories.agent_id` → `agents.id`
- `memories.conversation_id` → `conversations.id`
- `machine_apps.machine_id` / `task_queue.machine_id` / `workers.machine_id` 通过机器码与机器或外部 Worker 关联
- 注意：这些关联目前主要通过业务代码维护，没有显式数据库外键约束

## 5. 使用注意事项

- `machines` 和 `workers` 是两套不同的数据域：
  - `machines`：影刀机器，状态偏向业务运行态
  - `workers`：Celery Worker，状态偏向消息队列消费态
- `system_config` 目前是“分类 + 整块 JSON”，不要把它误认为传统键值表
- `n8n_workflows` 虽然有表结构，但当前代码中尚未看到明确路由或服务层消费逻辑
- 数据库变更当前没有 Alembic 迁移体系，调整模型前要优先备份 `backend/data/`

## 6. 当前项目暂无此内容

- 当前项目暂无显式数据库外键约束
- 当前项目暂无独立的迁移脚本目录
- 当前项目暂无数据库分库分表、多租户或读写分离设计

