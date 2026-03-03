# 项目前端状态审查报告 & 契约文档

## 1. 技术栈
- **框架**: React 18
- **构建工具**: Vite
- **路由**: React Router v6 (`react-router-dom`)
- **UI 样式**: Tailwind CSS
- **图标库**: Lucide React
- **HTTP 客户端**: Axios
- **Markdown 渲染**: `react-markdown`

## 2. 环境变量清单
目前项目尚未配置 `.env` 文件，所有配置依赖于 `src/mock/index.ts` 中的硬编码或应用内的基础配置页面。
建议添加以下环境变量：
- `VITE_API_BASE_URL`: 后端 API 基础地址（默认 `/api`）
- `VITE_USE_MOCK`: 是否开启前端 Mock（默认 `true`）

## 3. 启动方式
```bash
# 安装依赖
npm install

# 开发环境启动 (默认端口 3000)
npm run dev

# 生产环境构建
npm run build
```

## 4. 目录结构说明
```text
src/
├── api/            ← 所有 API 请求函数集中管理
│   ├── index.ts    ← Axios 实例 + 拦截器（401跳转等）
│   ├── agents.ts   ← 智能体及编排层 API
│   ├── config.ts   ← 系统基础配置 API
│   ├── feishu.ts   ← 飞书表管理 API
│   ├── logs.ts     ← 运行日志 API
│   └── tools.ts    ← 工具管理 API
├── components/     ← 公共组件（如 Layout.tsx）
├── mock/           ← Mock 数据及开关
│   └── index.ts    ← USE_MOCK 开关及所有模拟数据
├── router/         ← 路由配置
│   └── index.tsx   ← 路由表及鉴权守卫
├── types/          ← TypeScript 类型定义
│   └── tool.ts     ← 工具类型定义（其他类型待完善）
├── views/          ← 页面组件
│   ├── Agent.tsx         ← 智能体管理 & 编排层
│   ├── AgentChat.tsx     ← 智能体聊天界面
│   ├── BasicConfig.tsx   ← 系统基础配置
│   ├── FeishuTables.tsx  ← 飞书表管理
│   ├── Login.tsx         ← 登录页
│   ├── ShadowbotLogs.tsx ← 影刀运行日志
│   └── Tools.tsx         ← 工具管理
├── App.tsx         ← 根组件
├── index.css       ← 全局样式 (Tailwind 引入)
└── main.tsx        ← 入口文件
```

## 5. Mock 数据说明
- **开关位置**: `src/mock/index.ts` 中的 `export const USE_MOCK = true;`
- **切换方式**: 将 `USE_MOCK` 改为 `false` 即可让 `src/api/` 下的所有请求走真实的 Axios 请求。

## 6. API 契约文档 (基于当前前端实现)

### 智能体模块 (Agents)
- `GET /agents`
  - 响应: `{ code: 200, data: Agent[], msg: 'success' }`
- `POST /agents`
  - 请求体: `Omit<Agent, 'id' | 'status' | 'updateTime'>`
  - 响应: `{ code: 200, data: Agent, msg: 'success' }`
- `PUT /agents/:id`
  - 请求体: `Partial<Agent>`
  - 响应: `{ code: 200, data: Agent, msg: 'success' }`
- `DELETE /agents/:id`
  - 响应: `{ code: 200, data: null, msg: 'success' }`
- `GET /orchestration`
  - 响应: `{ code: 200, data: OrchestrationConfig, msg: 'success' }`
- `POST /orchestration`
  - 请求体: `OrchestrationConfig`
  - 响应: `{ code: 200, msg: 'success' }`

### 工具模块 (Tools)
- `GET /tools`
  - 响应: `{ code: 200, data: Tool[], msg: 'success' }`
- `POST /tools`
  - 请求体: `Omit<Tool, 'id'>`
  - 响应: `{ code: 200, data: Tool, msg: 'success' }`
- `PUT /tools/:id`
  - 请求体: `Partial<Tool>`
  - 响应: `{ code: 200, data: Tool, msg: 'success' }`
- `DELETE /tools/:id`
  - 响应: `{ code: 200, data: null, msg: 'success' }`

### 系统配置 (Config)
- `GET /config`
  - 响应: `{ code: 200, data: ConfigData, msg: 'success' }`
- `POST /config`
  - 请求体: `ConfigData`
  - 响应: `{ code: 200, msg: 'success' }`

### 飞书表 (Feishu)
- `GET /feishu/tables`
  - 响应: `{ code: 200, data: FeishuTable[], msg: 'success' }`
- `POST /feishu/tables`
  - 请求体: `Omit<FeishuTable, 'id'>`
  - 响应: `{ code: 200, data: FeishuTable, msg: 'success' }`
- `PUT /feishu/tables/:id`
  - 请求体: `Partial<FeishuTable>`
  - 响应: `{ code: 200, data: FeishuTable, msg: 'success' }`
- `DELETE /feishu/tables/:id`
  - 响应: `{ code: 200, data: null, msg: 'success' }`

### 日志模块 (Logs)
- `GET /logs`
  - 响应: `{ code: 200, data: Log[], msg: 'success' }`

### 聊天模块 (Chat)
- `POST /chat`
  - 请求体: `{ agent_id: string, message: string }`
  - 响应: `{ code: 200, data: ChatResponse, msg: 'success' }` (注：实际可能为 SSE 流式响应)

### 认证模块 (Auth)
- `POST /auth/login`
  - 请求体: `{ username: string, password: string }`
  - 响应: `{ code: 200, data: LoginResponse, msg: 'success' }`

---

## 7. 后端对接注意事项
- **统一响应格式**: `{ code: number, data: any, msg: string }`
- **鉴权方式**: Bearer Token，请求头 `Authorization: Bearer xxx`
- **SSE 消息格式**: 待后端定义（目前前端通过定时器模拟推流）
- **CORS**: 开发环境需允许 `localhost:3000` 跨域请求

---

## 8. 前端状态审查报告

### 1. 项目结构总览
项目结构清晰，符合标准 React SPA 架构。页面组件、路由、API 请求、Mock 数据均已分离。

### 2. API 接口现状
- **完整度**: API 请求已全部集中在 `src/api/` 目录下，没有散落在组件中的直接请求。
- **缺失**: 智能体 (Agent) 的新增、修改、删除接口目前在前端是直接操作 Mock 数组，`src/api/agents.ts` 中尚未定义 `addAgent`, `updateAgent`, `deleteAgent` 方法（目前在 `Agent.tsx` 中硬编码了 Mock 逻辑，这是一个 **TODO**）。

### 3. Mock 数据覆盖度
- **覆盖度 100%**: 所有核心业务（智能体、编排、工具、飞书表、配置、日志）均有 Mock 数据支持。

### 4. TypeScript 类型完整性
- **已完善**: 新增了 `types/` 目录下的所有核心类型：
  - `agent.ts` (Agent, OrchestrationConfig)
  - `auth.ts` (LoginRequest, LoginResponse)
  - `chat.ts` (ChatRequest, ChatResponse)
  - `config.ts` (ConfigData)
  - `feishu.ts` (FeishuTable)
  - `log.ts` (Log)
  - `tool.ts` (Tool)
- **改进**: 替换了大部分组件中的 `any` 类型。

### 5. 路由清单
- `/` : 智能体聊天 (`AgentChat.tsx`)
- `/agent` : 智能体管理 & 编排 (`Agent.tsx`)
- `/tools` : 工具管理 (`Tools.tsx`)
- `/logs` : 影刀运行日志 (`ShadowbotLogs.tsx`)
- `/feishu` : 飞书表管理 (`FeishuTables.tsx`)
- `/config` : 基础配置 (`BasicConfig.tsx`)
- `/login` : 登录页 (`Login.tsx`)

### 6. Agent 状态实现
- **硬编码**: 目前 Agent 的运行状态（`status: 'running' | 'stopped'`）是在 Mock 数据中写死的。实际业务中需要通过轮询或 WebSocket/SSE 动态获取。

### 7. TODO / FIXME / 硬编码
- `AgentChat.tsx`: 聊天回复目前是 `setTimeout` 模拟的硬编码回复。
- `ShadowbotLogs.tsx`: SSE 推流是前端通过 `setInterval` 模拟的，需要替换为真实的 `EventSource`。
- `Agent.tsx`: 保存 Agent 的逻辑直接修改了 `mockAgents.data`，没有走 `api/agents.ts` 的封装接口。

### 代码规范
1. **API 集中**: 是的，全部集中在 `api/` 目录。
2. **TS 严格度**: 不严格，存在较多 `any`。
3. **错误处理**: `api/index.ts` 中统一处理了 401 跳转，但缺乏全局的 500 错误提示（如全局 Toast）。
4. **Loading 状态**: 按钮级别的 Loading（如保存中、提交中）已实现，但页面初次加载的骨架屏或全局 Loading 较少。
5. **命名规范**: 统一规范（组件 PascalCase，变量 camelCase）。

### 安全边界
6. **Token 存储**: 存在 `localStorage` 中。对于纯前端 SPA 属于常规做法，但存在 XSS 风险。
7. **防重复提交**: 已实现。所有保存按钮在提交时均会 `disabled` 并显示“保存中...”。
8. **表单验证**: 依赖 HTML5 的 `required` 属性，缺乏更严格的正则校验（如邮箱格式、URL格式）。
9. **删除二次确认**: 已实现。使用了 `window.confirm` 或自定义的二次确认弹窗。
10. **XSS 防护**: React 默认转义所有文本输出，未使用 `dangerouslySetInnerHTML`，基本安全。

### 修复记录
- 已为“编排层配置”、“工具管理”、“飞书表管理”、“智能体管理”的保存/修改操作补充了绿色的成功提示（Toast/Text）。
