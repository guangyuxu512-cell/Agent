# AGENTS.md

> 根目录版仅保留摘要与索引。  
> 详细规范已按主题拆分到 `docs/`，需要细节时优先查对应文档。

## 一、技术栈概要

- 前端：`Agent/`，React + TypeScript + Vite，路由入口在 `Agent/src/router/index.tsx`
- 后端：`backend/`，FastAPI + SQLAlchemy + Uvicorn
- 数据库：SQLite，默认文件为 `backend/data/app.db`
- 消息队列：Redis + Celery
- 调度：APScheduler + Celery
- 实时通信：HTTP + SSE
- 外部集成：飞书、OpenAI 兼容接口、RAGFlow、SMTP、影刀 / Shadowbot、外部 Worker

## 二、命名规范

### 2.1 后端

- 遵循 PEP 8 与 4 空格缩进
- 保留现有中文领域模块命名，不要随意英文化重命名
- 路由层放在 `backend/app/api/`
- 业务逻辑优先下沉到 `services/`、`tasks/`、`图引擎/`

### 2.2 前端

- 2 空格缩进、单引号、函数组件
- 页面放在 `Agent/src/views/`
- 通用组件放在 `Agent/src/components/`
- API 封装放在 `Agent/src/api/`
- 类型定义放在 `Agent/src/types/`

### 2.3 其他命名约定

- API 路由对外统一使用英文路径
- 数据库表名与字段名以英文 snake_case 为主
- `machines` 与 `workers` 不是同一概念，修改前先确认语义

## 三、架构核心原则

- 路由层保持薄，业务逻辑不要堆在 FastAPI 接口里
- 前端页面负责展示与交互，不复制后端业务规则
- 统一响应、统一鉴权、统一配置入口，避免各处私有协议
- 涉及实时能力时，优先遵守现有 HTTP + SSE + Celery 链路
- 涉及数据库结构、环境变量、Docker、回调协议时，同步更新文档

## 四、协作规范

- 当前仓库实际偏向单主干协作，默认围绕 `main`
- Commit 标题沿用中文动词短语风格，例如：
  - `修复...`
  - `优化...`
  - `修改...`
  - `升级...`
  - `feat: ...`
- PR / 交付说明至少包含：
  - 变更目的
  - 影响目录
  - 配置或数据变更
  - 验证结果
- 前端改动建议附截图
- 后端接口改动建议附请求 / 响应示例或关键日志
- 每次功能变更至少给出 1 条可复现的验证步骤

## 五、禁止事项（红线）

- 不要提交真实密钥、真实口令、真实生产地址
- 不要绕过 `app/加密.py` 长期明文存储敏感字段
- 不要删除或延后 `backend/app/启动器.py` 顶部的 `apply_all_patches()`
- 不要把新业务逻辑大量堆在 FastAPI 路由层
- 不要在未备份 `backend/data/` 的情况下直接改数据库结构或做破坏性数据处理
- 不要把 `Agent/README.md`、`Agent/.env.example` 里的模板内容当成当前业务事实
- 不要把日志 SSE 改成自定义 Header 鉴权；浏览器 `EventSource` 不支持

## 六、docs/ 目录索引

- `docs/architecture.md`
  - 分层设计、模块关系、目录结构、核心模块、性能敏感点
- `docs/api-spec.md`
  - 路由清单、统一响应、分页协议、错误码、鉴权方式
- `docs/database.md`
  - 数据库表结构、字段说明、表间关系、使用注意事项
- `docs/coding-style.md`
  - 代码风格、命名规范、落位原则、协作要求、常见坑点
- `docs/callback.md`
  - Worker / Agent / 飞书 / 影刀 / SSE / Celery 派发链路与回调格式
- `docs/testing.md`
  - pytest 现状、联调脚本、测试策略、手工验证建议
- `docs/frontend.md`
  - 前端页面设计、路由、页面职责、接口分层、前端环境变量
- `docs/deployment.md`
  - Docker、`.env`、本地启动、外部服务、部署注意事项

## 七、使用建议

- 改架构、模块边界、目录结构：先看 `docs/architecture.md`
- 改接口或联调外部系统：先看 `docs/api-spec.md` 和 `docs/callback.md`
- 改表结构、字段、状态流转：先看 `docs/database.md`
- 改代码风格、命名、代码落位：先看 `docs/coding-style.md`
- 改页面、路由、前端接口：先看 `docs/frontend.md`
- 改 `.env`、Docker、部署流程：先看 `docs/deployment.md`
- 补验证说明或梳理测试方式：先看 `docs/testing.md`

生成日期：2026-03-10  
本文件为摘要索引版，请结合 `docs/` 中的专题文档使用。
