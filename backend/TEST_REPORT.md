# 影刀触发工具测试报告

## 测试环境

- Python 3.12.0
- FastAPI 后端
- SQLite 数据库
- pytest 7.4.3

## 第1步：数据库迁移 ✅

已成功创建 `task_queue` 表，包含以下字段：
- id (主键)
- app_name (应用名称)
- machine_id (机器ID)
- status (状态: waiting/triggered/failed)
- created_at (创建时间)
- triggered_at (触发时间)
- error (错误信息)

## 第2步：测试数据准备 ✅

已插入以下测试数据：

**机器表 (machines):**
- test_machine_1: 测试机器1 (status: idle)
- test_machine_2: 测试机器2 (status: running)

**应用绑定表 (machine_apps):**
- test_machine_1 → 测试应用A
- test_machine_2 → 测试应用B

**系统配置 (system_config):**
- shadowbot 配置: targetEmail, subjectTemplate, contentTemplate
- email 配置: SMTP 服务器配置

## 第3步：单元测试结果 ✅

**所有 7 个测试全部通过！**

### 测试用例详情

1. ✅ **test_app_not_found** - 应用不存在
   - 输入: 不存在的应用名
   - 预期: 返回错误信息 "未找到应用"
   - 结果: PASSED

2. ✅ **test_machine_offline** - 机器离线
   - 输入: 触发绑定到离线机器的应用
   - 预期: 返回错误信息 "机器离线"
   - 结果: PASSED

3. ✅ **test_machine_online_triggers_email** - 机器空闲时直接触发
   - 输入: 触发绑定到空闲机器的应用
   - 预期: 发送邮件，返回 "已触发执行"
   - 结果: PASSED (邮件 mock 被调用 1 次)

4. ✅ **test_machine_busy_queues_task** - 机器忙碌时加入队列
   - 输入: 触发绑定到忙碌机器的应用
   - 预期: 任务加入队列，返回 "已加入队列等待"
   - 结果: PASSED (队列任务数 0 → 1)

5. ✅ **test_callback_triggers_queued_task** - 回调触发队列任务
   - 输入: 机器状态从 running 变为 idle
   - 预期: 自动触发队列中的等待任务
   - 结果: PASSED (任务状态 waiting → triggered，邮件 mock 被调用 1 次)

6. ✅ **test_callback_no_queue** - 回调时队列为空
   - 输入: 机器状态变为 idle，但队列为空
   - 预期: 不报错，正常返回
   - 结果: PASSED

7. ✅ **test_callback_auth_required** - 回调接口需要鉴权
   - 输入: 不带 X-RPA-KEY 头调用状态更新接口
   - 预期: 返回 401 或 403
   - 结果: PASSED (返回 401)

### 测试命令

```bash
cd E:\Agent\backend
python -m pytest tests/test_trigger_shadowbot.py -v
```

### 测试输出摘要

```
============================= test session starts =============================
collected 7 items

tests/test_trigger_shadowbot.py::TestTriggerShadowbot::test_app_not_found PASSED
tests/test_trigger_shadowbot.py::TestTriggerShadowbot::test_machine_offline PASSED
tests/test_trigger_shadowbot.py::TestTriggerShadowbot::test_machine_online_triggers_email PASSED
tests/test_trigger_shadowbot.py::TestTriggerShadowbot::test_machine_busy_queues_task PASSED
tests/test_trigger_shadowbot.py::TestTriggerShadowbot::test_callback_triggers_queued_task PASSED
tests/test_trigger_shadowbot.py::TestTriggerShadowbot::test_callback_no_queue PASSED
tests/test_trigger_shadowbot.py::test_callback_auth_required PASSED

======================= 7 passed, 12 warnings in 7.08s =======================
```

## 第4步：代码修复

在测试过程中发现并修复了以下**配置键名兼容性**: 影刀配置支持 camelCase (targetEmail) 和 snake_case (target_email) 两种格式
2. **Mock 函数参数**: 修复了邮件发送 mock 函数的参数签名
3. **应用导入**: 修复了测试中的应用对象导入路径

## 第5步：集成测试准备 ✅

### DEBUG 模式

已在影刀触发工具中添加 DEBUG 模式。在 `.env` 文件中设置：

```bash
SHADOWBOT_DEBUG=true
```

启用后，邮件不会真实发送，只会打印日志：

```
[DEBUG] 影刀触发邮件（未实际发送）:
  收件人: test@example.com
  主题: 影刀触发-测试应用A
  正文: 请执行应用：测试应用A
```

### 集成测试脚本

已创建 `integration_test.py` 脚本，包含 4 个集成测试：

1. **测试1**: 直接触发（机器空闲）
2. **测试2**: 排队等待（机器忙碌）
3. **测试3**: 回调触发队列
4. **测试4**: 鉴权测试

### 运行集成测试

```bash
# 1. 确保后端已启动
cd E:\Agent\backend
python app/启动器.py

# 2. 在另一个终端运行集成测试
cd E:\Agent\backend
python integration_test.py
```

### 手动测试步骤

#### 测试1：直接触发（机器空闲）

```bash
# 设置机器为空闲
curl -X PUT http://localhost:8001/api/machines/test_machine_1/status \
  -H "X-RPA-KEY: changeme-rpa-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"status": "idle"}'

# 通过 Agent 触发（需要先获取 token）
# 或直接在 Python 中调用：
python -c "from app.图引擎.内置工具.影刀触发 import 触发影刀; import asyncio; print(asyncio.run(触发影刀('测试应用A')))"
```

#### 测试2：排队等待（机器忙碌）

```bash
# 设置机器为忙碌
curl -X PUT http://localhost:8001/api/machines/test_machine_2/status \
  -H "X-RPA-KEY: changeme-rpa-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"status": "running"}'

# 触发应用（应该加入队列）
python -c "from app.图引擎.内置工具.影刀触发 import 触发影刀; import asyncio; print(asyncio.run(触发影刀('测试应用B')))"
```

#### 测试3：回调触发队列

```bash
# 机器变为空闲（模拟影刀执行完成）
curl -X PUT http://localhost:8001/api/machines/test_machine_2/status \
  -H "X-RPA-KEY: changeme-rpa-key-2026" \
  -H "Content-Type: application/json" \
  -d '{"status": "idle"}'

# 观察后端日志，应该看到：
# [任务队列] 自动触发等待任务: 测试应用B (机器: test_machine_2)
```

## 测试结论

✅ **所有测试通过！影刀触发工具已完成开发和验证。**

### 功能验证

- ✅ 应用不存在时返回错误
- ✅ 机器离线时返回错误
- ✅ 机器空闲时直接触发邮件
- ✅ 机器忙碌时任务加入队列
- ✅ 机器空闲后自动触发队列任务
- ✅ 队列为空时不报错
- ✅ 回调接口需要 X-RPA-KEY 鉴权

### 安全性验证

- ✅ 状态更新接口需要 X-RPA-KEY 鉴权
- ✅ 未鉴权请求返回 401 Unauthorized

### 配置兼容性

- ✅ 支持 camelCase 和 snake_case 配置键名
- ✅ 支持 DEBUG 模式（不真实发送邮件）

## 使用说明

### 1. 配置系统

在前端"影刀触发"配置区设置：
- 影刀目标邮箱
- 邮件主题模板（默认: "影刀触发-{app_name}"）
- 邮件内容模板（默认: "请执行应用：{app_name}"）

### 2. 添加机器和应用绑定

通过机器管理接口添加机器和应用绑定。

### 3. Agent 调用

在 Agent 的工具列表中添加"触发影刀"工具，然后通过对话触发：

```
用户: 请触发测试应用A
Agent: [调用 trigger_shadowbot 工具]
```

### 4. 影刀回调

影刀执行完成后，通过 HTTP 回调更新机器状态：

```bash
PUT /api/machines/{machine_id}/status
Headers: X-RPA-KEY: changeme-rpa-key-2026
Body: {"status": "idle"}
```

系统会自动检查任务队列并触发下一个等待任务。

## 文件清单

- ✅ `backend/app/db/模型.py` - 新增 task_queue 表
- ✅ `backend/app/图引擎/内置工具/影刀触发.py` - 影刀触发工具
- ✅ `backend/app/图引擎/内置工具/__init__.py` - 注册工具
- ✅ `backend/app/api/机器管理.py` - 状态回调接口和队列处理
- ✅ `Agent/src/types/config.ts` - 前端类型定义
- ✅ `Agent/src/views/BasicConfig.tsx` - 前端配置页面
- ✅ `backend/tests/test_trigger_shadowbot.py` - 单元测试
- ✅ `backend/integration_test.py` - 集成测试脚本
- ✅ `backend/init_test_data.py` - 测试数据初始化脚本
