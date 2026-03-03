#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通过前端 API 注册触发影刀工具"""

import requests
import json

BASE_URL = "http://localhost:8001"

def register_trigger_tool():
    """注册触发影刀工具"""

    # 1. 登录
    print("=== 登录 ===")
    login_resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "510519abc123.@"}
    )
    login_data = login_resp.json()

    if login_data.get("code") != 0:
        print(f"登录失败: {login_data.get('msg')}")
        return

    token = login_data["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("登录成功")

    # 2. 检查工具是否已存在
    print("\n=== 检查现有工具 ===")
    tools_resp = requests.get(f"{BASE_URL}/api/tools", headers=headers)
    tools_data = tools_resp.json()

    if tools_data.get("code") == 0:
        existing_tools = tools_data.get("data", [])
        print(f"现有工具数量: {len(existing_tools)}")

        # 检查是否已有触发影刀工具
        for tool in existing_tools:
            if tool.get("name") == "触发影刀":
                print("触发影刀工具已存在")
                print(f"  工具ID: {tool.get('id')}")
                print(f"  状态: {tool.get('status')}")
                return

    # 3. 注册触发影刀工具
    print("\n=== 注册触发影刀工具 ===")
    tool_data = {
        "name": "触发影刀",
        "tool_type": "builtin",
        "description": "触发影刀RPA应用执行。根据机器状态：空闲时直接触发，忙碌时加入队列等待，离线时返回错误",
        "parameters": json.dumps({
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "要触发的影刀应用名称（需要在机器管理中预先绑定）"
                }
            },
            "required": ["app_name"]
        }, ensure_ascii=False),
        "config": json.dumps({
            "builtin_name": "trigger_shadowbot"
        }, ensure_ascii=False),
        "status": "active"
    }

    create_resp = requests.post(
        f"{BASE_URL}/api/tools",
        headers=headers,
        json=tool_data
    )
    create_data = create_resp.json()

    if create_data.get("code") == 0:
        print("工具注册成功")
        print(f"  工具ID: {create_data['data'].get('id')}")
    else:
        print(f"工具注册失败: {create_data.get('msg')}")
        print(f"  响应: {json.dumps(create_data, ensure_ascii=False, indent=2)}")

if __name__ == "__main__":
    try:
        register_trigger_tool()
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
