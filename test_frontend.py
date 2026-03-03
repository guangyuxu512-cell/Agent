#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""模拟前端测试触发影刀功能"""

import requests
import json
import sys

BASE_URL = "http://localhost:8001"

def test_trigger_shadowbot():
    """测试触发影刀功能"""

    # 1. 登录获取token
    print("=== 步骤1: 登录 ===")
    login_resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "510519abc123.@"}
    )
    print(f"登录响应状态: {login_resp.status_code}")
    login_data = login_resp.json()

    if login_data.get("code") != 0:
        print(f"登录失败: {login_data.get('msg')}")
        return

    token = login_data["data"]["token"]
    print(f"登录成功，Token: {token[:50]}...")

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

    # 选择有触发影刀工具的智能体
    agent = None
    for a in agent_list:
        tools = a.get("tools", [])
        print(f"智能体: {a.get('name')}, 工具: {tools}")
        if "触发影刀" in str(tools):
            agent = a
            break

    if not agent:
        print("警告: 没有找到配置了触发影刀工具的智能体，使用第一个智能体")
        agent = agent_list[0] if agent_list else None

    if not agent:
        print("错误: 没有可用的智能体")
        return

    agent_id = agent["id"]
    agent_name = agent["name"]
    print(f"使用智能体: {agent_name} (ID: {agent_id})")

    # 3. 查看可用的机器和应用
    print("\n=== 步骤3: 查看可用的机器和应用 ===")
    machines_resp = requests.get(f"{BASE_URL}/api/machines", headers=headers)
    machines_data = machines_resp.json()

    if machines_data.get("code") == 0:
        machines = machines_data.get("data", [])
        print(f"机器数量: {len(machines)}")
        for m in machines:
            print(f"  - {m.get('machine_name')} (ID: {m.get('machine_id')}, 状态: {m.get('status')})")

            # 获取该机器的应用绑定
            apps_resp = requests.get(
                f"{BASE_URL}/api/machine-apps?machine_id={m.get('machine_id')}",
                headers=headers
            )
            apps_data = apps_resp.json()
            if apps_data.get("code") == 0:
                apps = apps_data.get("data", [])
                for app in apps:
                    if app.get("enabled"):
                        print(f"    * {app.get('app_name')}")

    # 4. 发送测试消息
    print("\n=== 步骤4: 发送测试消息 ===")

    test_messages = [
        "请触发邮件发送",
        "帮我启动数据文件",
        "触发测试应用A"
    ]

    for msg in test_messages:
        print(f"\n{'='*60}")
        print(f"测试消息: {msg}")
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
                stream=True
            )

            print(f"响应状态: {chat_resp.status_code}")

            if chat_resp.status_code != 200:
                print(f"请求失败: {chat_resp.text}")
                continue

            # 读取SSE流式响应
            print("\n--- Agent响应 ---")
            full_response = []
            tool_calls = []
            tool_results = []

            for line in chat_resp.iter_lines():
                if line:
                    line_str = line.decode('utf-8')
                    if line_str.startswith('data: '):
                        data_str = line_str[6:]
                        try:
                            data = json.loads(data_str)
                            event_type = data.get('type', 'unknown')
                            content = data.get('content', '')

                            if event_type == 'error':
                                print(f"[ERROR] {content}")
                            elif event_type == 'tool_call':
                                print(f"[TOOL_CALL] {content}")
                                tool_calls.append(content)
                            elif event_type == 'tool_result':
                                print(f"[TOOL_RESULT] {content}")
                                tool_results.append(content)
                            elif event_type == 'token':
                                full_response.append(content)
                            elif event_type == 'done':
                                print(f"[DONE]")
                        except json.JSONDecodeError:
                            pass

            print("\n完整回复:", "".join(full_response))
            print("--- 响应结束 ---\n")

            # 分析结果
            if tool_calls:
                print(f"工具调用次数: {len(tool_calls)}")
            if tool_results:
                print(f"工具结果: {tool_results[0] if tool_results else 'None'}")

        except Exception as e:
            print(f"发送消息失败: {e}")
            import traceback
            traceback.print_exc()

        # 等待一下
        import time
        time.sleep(2)

if __name__ == "__main__":
    try:
        test_trigger_shadowbot()
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
