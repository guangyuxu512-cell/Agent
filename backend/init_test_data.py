#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""初始化测试数据"""
import sys
import json
from datetime import datetime

# 设置输出编码
sys.stdout.reconfigure(encoding='utf-8')

from app.db.数据库 import 引擎, 会话工厂
from app.db.模型 import 基础模型, 机器模型, 机器应用模型, 系统配置模型

print("Step 1: Creating all tables...")
基础模型.metadata.create_all(引擎)
print("✓ Tables created")

db = 会话工厂()
try:
    print("\nStep 2: Inserting test machines...")

    # 检查是否已存在
    机器1 = db.query(机器模型).filter(机器模型.机器码 == "test_machine_1").first()
    if not 机器1:
        机器1 = 机器模型(
            机器码="test_machine_1",
            机器名称="测试机器1",
            状态="idle"  # idle = online (空闲)
        )
        db.add(机器1)
        print("  + Added test_machine_1 (status: idle)")
    else:
        print("  - test_machine_1 already exists")

    机器2 = db.query(机器模型).filter(机器模型.机器码 == "test_machine_2").first()
    if not 机器2:
        机器2 = 机器模型(
            机器码="test_machine_2",
            机器名称="测试机器2",
            状态="running"  # running = busy (忙碌)
        )
        db.add(机器2)
        print("  + Added test_machine_2 (status: running)")
    else:
        print("  - test_machine_2 already exists")

    db.commit()

    print("\nStep 3: Inserting test machine apps...")

    绑定1 = db.query(机器应用模型).filter(
        机器应用模型.机器码 == "test_machine_1",
        机器应用模型.应用名 == "测试应用A"
    ).first()
    if not 绑定1:
        绑定1 = 机器应用模型(
            机器码="test_machine_1",
            应用名="测试应用A",
            描述="测试用应用A",
            启用=True
        )
        db.add(绑定1)
        print("  + Added binding: test_machine_1 -> 测试应用A")
    else:
        print("  - Binding test_machine_1 -> 测试应用A already exists")

    绑定2 = db.query(机器应用模型).filter(
        机器应用模型.机器码 == "test_machine_2",
        机器应用模型.应用名 == "测试应用B"
    ).first()
    if not 绑定2:
        绑定2 = 机器应用模型(
            机器码="test_machine_2",
            应用名="测试应用B",
            描述="测试用应用B",
            启用=True
        )
        db.add(绑定2)
        print("  + Added binding: test_machine_2 -> 测试应用B")
    else:
        print("  - Binding test_machine_2 -> 测试应用B already exists")

    db.commit()

    print("\nStep 4: Inserting shadowbot config...")

    shadowbot_config = db.query(系统配置模型).filter(
        系统配置模型.分类 == "shadowbot",
        系统配置模型.键 == "__data__"
    ).first()

    shadowbot_data = {
        "targetEmail": "test@example.com",
        "subjectTemplate": "影刀触发-{app_name}",
        "contentTemplate": "请执行应用：{app_name}"
    }

    if not shadowbot_config:
        shadowbot_config = 系统配置模型(
            分类="shadowbot",
            键="__data__",
            值=json.dumps(shadowbot_data, ensure_ascii=False),
            说明="影刀触发配置"
        )
        db.add(shadowbot_config)
        print("  + Added shadowbot config")
    else:
        shadowbot_config.值 = json.dumps(shadowbot_data, ensure_ascii=False)
        print("  - Updated shadowbot config")

    db.commit()

    print("\nStep 5: Inserting email config...")

    email_config = db.query(系统配置模型).filter(
        系统配置模型.分类 == "email",
        系统配置模型.键 == "__data__"
    ).first()

    email_data = {
        "smtpServer": "smtp.example.com",
        "smtpPort": "587",
        "sender": "test@example.com",
        "smtpPassword": "test_password"
    }

    if not email_config:
        email_config = 系统配置模型(
            分类="email",
            键="__data__",
            值=json.dumps(email_data, ensure_ascii=False),
            说明="邮件配置"
        )
        db.add(email_config)
        print("  + Added email config")
    else:
        email_config.值 = json.dumps(email_data, ensure_ascii=False)
        print("  - Updated email config")

    db.commit()

    print("\n✓ Test data initialization completed!")

    # 验证数据
    print("\n=== Verification ===")
    print(f"Machines count: {db.query(机器模型).count()}")
    print(f"Machine apps count: {db.query(机器应用模型).count()}")
    print(f"System configs count: {db.query(系统配置模型).count()}")

except Exception as e:
    print(f"\n✗ Error: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
