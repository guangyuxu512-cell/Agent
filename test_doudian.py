#!/usr/bin/env python
# -*- coding: utf-8 -*-
import requests
import json

BASE_URL = "http://localhost:8001"

# 1. 登录
login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "510519abc123.@"})
token = login_resp.json()["data"]["token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. 获取智能体
agents_resp = requests.get(f"{BASE_URL}/api/agents", headers=headers)
agent_id = agents_resp.json()["data"]["list"][0]["id"]

# 3. 测试触发抖店发货
print("测试: 请触发抖店发货")
chat_resp = requests.post(
    f"{BASE_URL}/api/chat",
    headers=headers,
    json={"agent_id": agent_id, "message": "请触发抖店发货"},
    stream=True
)

for line in chat_resp.iter_lines():
    if line:
        line_str = line.decode('utf-8')
        if line_str.startswith('data: '):
            try:
                data = json.loads(line_str[6:])
                if data.get('type') == 'tool_result':
                    print(f"[工具结果] {data.get('content')}")
                elif data.get('type') == 'token':
                    print(data.get('content'), end='')
            except:
                pass
print("\n")
