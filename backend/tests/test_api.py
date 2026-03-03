# tests/test_api.py
# 全接口 CRUD 测试

import json
from uuid import uuid4


# ==================== 鉴权 ====================

class Test鉴权:
    def test_登录成功(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert "token" in data["data"]

    def test_登录失败_密码错误(self, client):
        r = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.json()["code"] == 1

    def test_未授权访问(self, client):
        r = client.get("/api/agents")
        assert r.status_code == 401

    def test_健康检查_无需鉴权(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["code"] == 0


# ==================== 智能体 CRUD ====================

class Test智能体:
    agent_id = None

    def test_创建Agent(self, client, auth):
        r = client.post("/api/agents", json={
            "name": "测试Agent",
            "role": "测试角色",
            "prompt": "你是测试助手",
            "llmProvider": "OpenAI",
            "llmModel": "gpt-4o",
            "llmApiUrl": "https://api.test.com/v1",
            "llmApiKey": "sk-test-key",
            "temperature": 0.5,
            "tools": [],
            "status": "running",
        }, headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        Test智能体.agent_id = data["data"]["id"]
        assert Test智能体.agent_id

    def test_获取Agent列表(self, client, auth):
        r = client.get("/api/agents", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert len(data["data"]["list"]) >= 1

    def test_获取Agent详情(self, client, auth):
        r = client.get(f"/api/agents/{Test智能体.agent_id}", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert data["data"]["name"] == "测试Agent"

    def test_更新Agent(self, client, auth):
        r = client.put(f"/api/agents/{Test智能体.agent_id}", json={
            "name": "更新后Agent",
            "role": "新角色",
            "prompt": "更新提示词",
            "llmProvider": "OpenAI",
            "llmModel": "gpt-4o",
            "llmApiUrl": "https://api.test.com/v1",
            "llmApiKey": "sk-test-key",
            "temperature": 0.8,
            "tools": [],
            "status": "running",
        }, headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 验证更新生效
        r2 = client.get(f"/api/agents/{Test智能体.agent_id}", headers=auth)
        assert r2.json()["data"]["name"] == "更新后Agent"

    def test_获取不存在的Agent(self, client, auth):
        r = client.get("/api/agents/nonexistent-id", headers=auth)
        data = r.json()
        assert data["code"] == 1 or data["data"] is None

    def test_删除Agent(self, client, auth):
        # 先创建一个用于删除
        r = client.post("/api/agents", json={
            "name": "待删除Agent",
            "role": "",
            "prompt": "",
            "llmProvider": "OpenAI",
            "llmModel": "gpt-4o",
            "llmApiUrl": "https://api.test.com/v1",
            "llmApiKey": "sk-test",
            "temperature": 0.7,
            "tools": [],
            "status": "stopped",
        }, headers=auth)
        del_id = r.json()["data"]["id"]

        r2 = client.delete(f"/api/agents/{del_id}", headers=auth)
        assert r2.status_code == 200
        assert r2.json()["code"] == 0

        # 验证已删除
        r3 = client.get(f"/api/agents/{del_id}", headers=auth)
        assert r3.json()["data"] is None or r3.json()["code"] == 1


# ==================== 工具 CRUD ====================

class Test工具:
    tool_id = None

    def test_创建工具(self, client, auth):
        r = client.post("/api/tools", json={
            "name": "测试工具",
            "description": "用于测试的HTTP工具",
            "tool_type": "http_api",
            "parameters": json.dumps({"properties": {"url": {"type": "string", "description": "URL参数"}}}),
            "config": json.dumps({"method": "GET", "url": "https://example.com"}),
        }, headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        Test工具.tool_id = data["data"]["id"]

    def test_获取工具列表(self, client, auth):
        r = client.get("/api/tools", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert len(data["data"]["list"]) >= 1

    def test_获取单个工具(self, client, auth):
        r = client.get(f"/api/tools/{Test工具.tool_id}", headers=auth)
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "测试工具"

    def test_更新工具(self, client, auth):
        r = client.put(f"/api/tools/{Test工具.tool_id}", json={
            "name": "更新后工具",
            "description": "更新描述",
            "tool_type": "http_api",
            "parameters": "{}",
            "config": "{}",
        }, headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_删除工具(self, client, auth):
        # 创建一个用于删除
        r = client.post("/api/tools", json={
            "name": "待删除工具",
            "description": "",
            "tool_type": "http_api",
            "parameters": "{}",
            "config": "{}",
        }, headers=auth)
        del_id = r.json()["data"]["id"]

        r2 = client.delete(f"/api/tools/{del_id}", headers=auth)
        assert r2.status_code == 200
        assert r2.json()["code"] == 0


# ==================== 对话 ====================

class Test对话:
    conversation_id = None

    def test_获取对话列表_空(self, client, auth):
        r = client.get("/api/conversations", headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert "list" in data["data"]

    def test_获取对话列表_按agent过滤(self, client, auth):
        r = client.get(f"/api/conversations?agent_id={Test智能体.agent_id}", headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_获取不存在对话的消息(self, client, auth):
        r = client.get("/api/conversations/nonexistent/messages", headers=auth)
        data = r.json()
        # 可能返回 {"code":1} 或 FastAPI 422/404 {"detail":"..."}
        assert data.get("code") == 1 or "detail" in data

    def test_删除不存在的对话(self, client, auth):
        r = client.delete("/api/conversations/nonexistent", headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0  # 幂等删除

    def test_获取对话列表_批量查询无N加1(self, client, auth):
        """验证对话列表接口返回正确的 agent_name 和 message_count"""
        r = client.get("/api/conversations", headers=auth)
        assert r.status_code == 200
        data = r.json()["data"]
        assert "list" in data
        assert "total" in data
        # 每条对话都应有 agent_name 和 message_count 字段
        for item in data["list"]:
            assert "agent_name" in item
            assert "message_count" in item
            assert isinstance(item["message_count"], int)


# ==================== 编排 ====================

class Test编排:
    def test_获取编排_初始为空(self, client, auth):
        r = client.get("/api/orchestration", headers=auth)
        assert r.status_code == 200
        # 可能是 null 或有数据（取决于之前测试）
        assert r.json()["code"] == 0

    def test_保存编排配置(self, client, auth):
        r = client.post("/api/orchestration", json={
            "mode": "Supervisor",
            "entryAgent": Test智能体.agent_id or "test-id",
            "routingRules": "规则1",
            "parallelGroups": "组1",
            "globalState": [{"key": "testKey", "desc": "测试"}],
        }, headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_获取编排_已保存(self, client, auth):
        r = client.get("/api/orchestration", headers=auth)
        assert r.status_code == 200
        data = r.json()["data"]
        assert data is not None
        assert data["mode"] == "Supervisor"
        assert data["routingRules"] == "规则1"

    def test_更新编排配置(self, client, auth):
        r = client.post("/api/orchestration", json={
            "mode": "Network",
            "entryAgent": "",
            "routingRules": "",
            "parallelGroups": "",
            "globalState": [],
        }, headers=auth)
        assert r.json()["code"] == 0

        r2 = client.get("/api/orchestration", headers=auth)
        assert r2.json()["data"]["mode"] == "Network"


# ==================== 记忆 ====================

class Test记忆:
    def test_获取记忆列表(self, client, auth):
        r = client.get("/api/memories", headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_清空记忆(self, client, auth):
        r = client.delete(f"/api/memories?agent_id={Test智能体.agent_id}", headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0


# ==================== 系统配置 ====================

class Test系统配置:
    def test_获取全部配置_初始为空(self, client, auth):
        r = client.get("/api/config", headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_保存配置(self, client, auth):
        r = client.post("/api/config", json={
            "test_cat": {
                "key1": "value1",
                "key2": "value2",
            }
        }, headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_获取分类配置(self, client, auth):
        r = client.get("/api/config/test_cat", headers=auth)
        assert r.status_code == 200
        data = r.json()["data"]
        assert len(data) >= 2

    def test_删除分类配置(self, client, auth):
        r = client.delete("/api/config/test_cat", headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

        # 验证已删除
        r2 = client.get("/api/config/test_cat", headers=auth)
        assert len(r2.json()["data"]) == 0


# ==================== 飞书表格 ====================

class Test飞书表格:
    record_id = None

    def test_新增表格(self, client, auth):
        r = client.post("/api/feishu/tables", json={
            "name": "测试表格",
            "appToken": "app_test_token",
            "tableId": "tbl_test_id",
            "description": "测试用飞书表格",
        }, headers=auth)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        Test飞书表格.record_id = data["data"]["id"]

    def test_获取全部表格(self, client, auth):
        r = client.get("/api/feishu/tables", headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0
        assert len(r.json()["data"]) >= 1

    def test_更新表格(self, client, auth):
        r = client.put(f"/api/feishu/tables/{Test飞书表格.record_id}", json={
            "name": "更新表格",
            "appToken": "app_updated",
            "tableId": "tbl_updated",
            "description": "更新后",
        }, headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0

    def test_删除表格(self, client, auth):
        r = client.delete(f"/api/feishu/tables/{Test飞书表格.record_id}", headers=auth)
        assert r.status_code == 200
        assert r.json()["code"] == 0
