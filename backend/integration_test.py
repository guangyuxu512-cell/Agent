#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""影刀触发工具集成测试脚本"""
import sys
import os
import requests
import json

# 设置输出编码
sys.stdout.reconfigure(encoding='utf-8')

# 配置
BASE_URL = "http://localhost:8001"
RPA_KEY = os.getenv("RPA_PUSH_KEY", "changeme-rpa-key-2026")

# 需要先登录获取 token
def get_token():
    """登录获取 JWT token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": os.getenv("DEFAULT_ADMIN_PASSWORD", "")}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("data", {}).get("token")
    else:
        print(f"登录失败: {response.text}")
        return None


def test_1_direct_trigger():
    """测试1：直接触发（机器空闲）"""
    print("\n" + "="*60)
    print("测试1：直接触发（机器空闲）")
    print("="*60)

    # 确保机器1是空闲状态
    print("\n[步骤1] 设置机器1为空闲状态...")
    response = requests.put(
        f"{BASE_URL}/api/machines/test_machine_1/status",
        headers={"X-RPA-KEY": RPA_KEY},
        json={"status": "idle"}
    )
    print(f"状态更新结果: {response.json()}")

    # 通过 Agent 触发应用
    print("\n[步骤2] 通过内置工具触发应用...")
    token = get_token()
    if not token:
        print("❌ 无法获取 token，跳过此测试")
        return

    # 直接调用内置工具（模拟 Agent 调用）
    from app.图引擎.内置工具.影刀触发 import 触发影刀
    import asyncio

    result = asyncio.run(触发影刀(app_name="测试应用A"))
    print(f"触发结果: {result}")

    if "已触发" in result:
        print("✅ 测试1通过：机器空闲时直接触发成功")
    else:
        print(f"❌ 测试1失败：{result}")


def test_2_queue_when_busy():
    """测试2：排队等待（机器忙碌）"""
    print("\n" + "="*60)
    print("测试2：排队等待（机器忙碌）")
    print("="*60)

    # 设置机器2为忙碌状态
    print("\n[步骤1] 设置机器2为忙碌状态...")
    response = requests.put(
        f"{BASE_URL}/api/machines/test_machine_2/status",
        headers={"X-RPA-KEY": RPA_KEY},
        json={"status": "running"}
    )
    print(f"状态更新结果: {response.json()}")

    # 触发应用
    print("\n[步骤2] 触发应用（应该加入队列）...")
    from app.图引擎.内置工具.影刀触发 import 触发影刀
    import asyncio

    result = asyncio.run(触发影刀(app_name="测试应用B"))
    print(f"触发结果: {result}")

    if "队列" in result or "等待" in result:
        print("✅ 测试2通过：机器忙碌时任务加入队列")
    else:
        print(f"❌ 测试2失败：{result}")


def test_3_callback_trigger_queue():
    """测试3：回调触发队列"""
    print("\n" + "="*60)
    print("测试3：回调触发队列")
    print("="*60)

    # 机器2变为空闲，应该自动触发队列中的任务
    print("\n[步骤1] 设置机器2为空闲状态（模拟影刀执行完成）...")
    response = requests.put(
        f"{BASE_URL}/api/machines/test_machine_2/status",
        headers={"X-RPA-KEY": RPA_KEY},
        json={"status": "idle"}
    )
    print(f"状态更新结果: {response.json()}")

    print("\n[步骤2] 检查后端日志，应该看到 '[任务队列] 自动触发等待任务' 的日志")
    print("✅ 如果日志中有自动触发的记录，则测试3通过")


def test_4_auth_required():
    """测试4：鉴权测试"""
    print("\n" + "="*60)
    print("测试4：回调接口需要鉴权")
    print("="*60)

    # 不带 X-RPA-KEY 头
    print("\n[步骤1] 不带 X-RPA-KEY 头调用状态更新接口...")
    response = requests.put(
        f"{BASE_URL}/api/machines/test_machine_1/status",
        json={"status": "idle"}
    )
    print(f"响应状态码: {response.status_code}")
    print(f"响应内容: {response.json()}")

    if response.status_code in [401, 403]:
        print("✅ 测试4通过：未鉴权请求被拒绝")
    else:
        print(f"❌ 测试4失败：应该返回401或403，实际返回{response.status_code}")


if __name__ == "__main__":
    print("影刀触发工具集成测试")
    print("="*60)
    print("注意：请确保后端已启动，并且 .env 中设置了 SHADOWBOT_DEBUG=true")
    print("="*60)

    try:
        test_1_direct_trigger()
        test_2_queue_when_busy()
        test_3_callback_trigger_queue()
        test_4_auth_required()

        print("\n" + "="*60)
        print("集成测试完成")
        print("="*60)
    except Exception as e:
        print(f"\n❌ 测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
