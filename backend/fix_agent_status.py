#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复 Agent 状态：将前 2 个 Agent 设置为 running 状态
"""

from app.db.数据库 import 会话工厂
from app.db.模型 import Agent模型

db = 会话工厂()
try:
    # 获取所有 Agent
    all_agents = db.query(Agent模型).all()

    print(f"=== 当前所有 Agent ===")
    for agent in all_agents:
        print(f"  - {agent.名称} (id={agent.id[:8]}..., 状态={agent.状态})")

    if len(all_agents) < 2:
        print(f"\n错误：只有 {len(all_agents)} 个 Agent，至少需要 2 个才能启用多 Agent 编排")
        print("请先在前端创建至少 2 个 Agent")
    else:
        print(f"\n=== 将前 2 个 Agent 设置为 running 状态 ===")
        for i, agent in enumerate(all_agents[:2]):
            agent.状态 = "running"
            print(f"  [OK] {agent.名称} -> running")

        db.commit()
        print("\n✅ 修改成功！")

        # 验证
        print("\n=== 验证修改结果 ===")
        running_agents = db.query(Agent模型).filter(Agent模型.状态 == "running").all()
        print(f"running 状态的 Agent 数量: {len(running_agents)}")
        for agent in running_agents:
            print(f"  - {agent.名称} (id={agent.id[:8]}...)")

        if len(running_agents) >= 2:
            print("\n[SUCCESS] 多 Agent 编排已启用！")
            print("现在通过 POST /api/chat 发送消息时，会自动使用多 Agent 协作模式")

finally:
    db.close()
