#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试触发影刀功能"""

import requests
import json

BASE_URL = "http://localhost:8000"

def test_trigger_shadowbot():
    """测试触发影刀功能"""

    # 1. 登录获取token
    print("=== 步骤1: 登录 ===")
    login_resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "510519abc123.@"}
    )
    print(f"登录响应: {login_resp.status_code}")
    login_data = login_resp.json()
    print(f"登录结果: {json.dumps(login_data, ensure_ascii=False, indent=2)}")

    if login_data.get("code") != 0:
        print("登录失败！")
        return

    token = login_data["data"]["token"]
    print(f"Token: {token[:50]}...")

    headers = {"Authorization": f"Bearer {token}"}

    # 2. 获取智能体列表
    print("\n=== 步骤2: 获取智能体列表 ===")
    agents_resp = requests.get(f"{BASE_URL}/api/agents", headers=headers)
    agents_data = agents_resp.json()

    if agents_data.get("code") != 0:
        print(f"获取智能体失败: {agents_data.get('msg')}")
        return

    agent_list = agents_data["data"]["list"]
    print(f"智能体数量: {len(agent_list)}")

    if not agent_list:
        print("没有可用的智能体！")
        return

    # 选择有触发影刀工具的智能体
    agent = None
    for a in agent_list:
        if "触发影刀" in str(a.get("tools", [])):
            agent = a
            break

    if not agent:
        agent = agent_list[0]  # 如果没有找到，使用第一个
    agent_id = agent["id"]
    agent_name = agent["name"]
    print(f"使用智能体: {agent_name} (ID: {agent_id})")

    # 3. 发送消息测试触发影刀
    print("\n=== 步骤3: 发送消息测试触发影刀 ===")
    test_messages = [
        "请触发邮件发送应用",
        "帮我启动测试应用A",
        "触发影刀应用：数据文件"
    ]

    for msg in test_messages:
        print(f"\n{'='*60}")
        print(f"发送消息: {msg}")
        print(f"{'='*60}")

        try:
            # 使用 /api/chat 接口发送消息（SSE流式响应）
            chat_resp = requests.post(
                f"{BASE_URL}/api/chat",
                headers=headers,
                json={
                    "agent_id": agent_id,
                    "message": msg
                },
                stream=True  # 启用流式响应
            )

            print(f"响应状态: {chat_resp.status_code}")

            if chat_resp.status_code != 200:
                print(f"✗ 请求失败: {chat_resp.text}")
                continue

            # 读取SSE流式响应
            print("\n--- Agent响应 ---")
            for line in chat_resp.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # 去掉 "data: " 前缀
                        try:
                            data = json.loads(data_str)
                            event_type = data.get('type', 'unknown')
                            content = data.get('content', '')

                            if event_type == 'error':
                                print(f"[ERROR] {content}")
                            elif event_type == 'tool_call':
                                print(f"[TOOL_CALL] {content}")
                            elif event_type == 'tool_result':
                                print(f"[TOOL_RESULT] {content}")
                            elif event_type == 'text':
                                print(f"[TEXT] {content}")
                            elif event_type == 'done':
                                print(f"[DONE]")
                            else:
                                print(f"[{event_type}] {content}")
                        except json.JSONDecodeError:
                            print(f"[RAW] {data_str}")

            print("--- 响应结束 ---\n")

        except Exception as e:
            print(f"✗ 发送消息失败: {e}")
            import traceback
            traceback.print_exc()

        # 等待一下，避免请求过快
        import time
        time.sleep(3)

if __name__ == "__main__":
    try:
        test_trigger_shadowbot()
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
