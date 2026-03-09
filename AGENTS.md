# Repository Guidelines

## 项目结构与模块组织

- `Agent/` 是 React + TypeScript + Vite 前端；页面在 `src/views/`，通用组件在 `src/components/`，接口封装在 `src/api/`，类型定义在 `src/types/`，路由配置在 `src/router/`。
- `backend/` 是 FastAPI 服务；路由在 `app/api/`，核心编排与工具执行在 `app/图引擎/`，飞书集成在 `app/飞书/`，数据库层在 `app/db/`。
- `docs/` 保存架构、部署与专题说明；根目录的 `test_doudian.py` 是本地联调脚本，不替代正式测试。

## 构建、测试与开发命令

- `cd Agent && npm install && npm run dev`：启动前端开发环境，默认监听 `3000` 端口。
- `cd Agent && npm run build`：构建前端产物；`cd Agent && npm run lint` 运行 TypeScript 类型检查。
- `cd backend && pip install -r requirements.txt`：安装后端依赖。
- `cd backend && python -m uvicorn app.启动器:app --reload --port 8001`：启动本地 FastAPI 服务。
- `cd backend && pytest`：运行后端测试；需要接口联调时，可在仓库根目录执行 `python test_doudian.py`。
- `cd backend && docker-compose up -d` 与 `cd Agent && docker-compose up -d`：分别启动后端或前端容器。

## 编码风格与命名约定

- 前端使用 2 空格缩进、单引号、函数组件；组件和视图文件使用 `PascalCase`，API、store、类型模块使用语义化英文名，如 `chatStore.ts`、`agents.ts`。
- 后端遵循 PEP 8 与 4 空格缩进；按现有约定保留中文领域模块名，如 `app/api/对话.py`、`app/图引擎/工具加载器.py`。
- 新逻辑优先放入对应分层，避免在路由层堆积业务代码。仓库未配置独立格式化工具，提交前至少运行 `npm run lint`，并保持与周边文件一致的导入顺序、空行和注释风格。

## 测试指南

- Pytest 已在 `backend/pytest.ini` 中配置，测试文件命名为 `test_*.py`，测试类为 `Test*`，测试函数为 `test_*`。
- 新增后端测试统一放在 `backend/tests/`，优先为改动模块补充最小回归用例，例如 `backend/tests/test_对话.py`。
- 仓库当前没有前端自动化测试框架，也没有强制覆盖率阈值；每次功能变更至少提供 1 条可复现的手动验证步骤，涉及 UI 时附截图，涉及 SSE 或飞书时附关键日志或请求示例。

## 提交与 Pull Request 规范

- 提交标题以简短中文动词短语为主，历史中常见写法有 `修复`、`优化`、`修改`、`升级` 和 `feat:`，例如：`修复前端：编排页面空白问题`。
- Pull Request 需说明变更目的、影响目录、配置或数据变更以及验证结果；前端改动附截图，后端接口改动附示例请求、响应或日志片段。
- 若修改 `docs/`、`docker-compose.yml`、环境变量约定或数据库模型，请在同一 PR 中同步更新文档和部署说明。

## 安全与配置提示

- 不要提交真实密钥；前端配置位于 `Agent/.env*`，后端配置位于 `backend/.env`。
- 生产环境至少显式设置 `JWT_SECRET_KEY`、`CORS_ORIGINS`、`OPENAI_API_KEY` 与 `RPA_PUSH_KEY`。
- SQLite 数据默认写入 `backend/data/`；修改数据库相关代码前先备份本地数据。
