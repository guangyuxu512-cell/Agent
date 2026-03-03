#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试影刀触发工具"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from app.db.数据库 import 会话工厂
from app.db.模型 import 机器模型, 机器应用模型, 任务队列模型
from app.图引擎.内置工具.影刀触发 import 触发影刀


class TestTriggerShadowbot:
    """影刀触发工具测试套件"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """每个测试前的设置"""
        self.db = 会话工厂()
        yield
        # 清理测试数据
        self.db.query(任务队列模型).delete()
        self.db.commit()
        self.db.close()

    def test_app_not_found(self):
        """测试1：应用不存在"""
        print("\n[TEST 1] Testing app not found...")

        result = asyncio.run(触发影刀(app_name="不存在的应用"))

        assert "错误" in result or "未找到" in result
        print(f"[PASS] Result: {result}")

    def test_machine_offline(self):
        """测试2：机器离线"""
        print("\n[TEST 2] Testing machine offline...")

        # 设置机器为离线状态
        机器 = self.db.query(机器模型).filter(机器模型.机器码 == "test_machine_1").first()
        if 机器:
            机器.状态 = "offline"
            self.db.commit()

        result = asyncio.run(触发影刀(app_name="测试应用A"))

        assert "离线" in result or "offline" in result.lower()
        print(f"[PASS] Result: {result}")

    @patch('app.图引擎.内置工具.影刀触发._发送触发邮件')
    def test_machine_online_triggers_email(self, mock_send_email):
        """测试3：机器空闲时直接触发"""
        print("\n[TEST 3] Testing machine online triggers email...")

        # Mock 邮件发送 - 接受3个参数（收件人、主题、正文）
        async def mock_send(recipient, subject, content):
            return "邮件发送成功"

        mock_send_email.side_effect = mock_send

        # 设置机器为空闲状态
        机器 = self.db.query(机器模型).filter(机器模型.机器码 == "test_machine_1").first()
        if 机器:
            机器.状态 = "idle"
            self.db.commit()

        result = asyncio.run(触发影刀(app_name="测试应用A"))

        assert "已触发" in result or "触发执行" in result
        assert mock_send_email.called
        print(f"[PASS] Result: {result}")
        print(f"[PASS] Email mock called: {mock_send_email.call_count} times")

    def test_machine_busy_queues_task(self):
        """测试4：机器忙碌时加入队列"""
        print("\n[TEST 4] Testing machine busy queues task...")

        # 设置机器为忙碌状态
        机器 = self.db.query(机器模型).filter(机器模型.机器码 == "test_machine_2").first()
        if 机器:
            机器.状态 = "running"
            self.db.commit()

        # 记录队列初始数量
        初始数量 = self.db.query(任务队列模型).filter(
            任务队列模型.机器码 == "test_machine_2"
        ).count()

        result = asyncio.run(触发影刀(app_name="测试应用B"))

        assert "队列" in result or "等待" in result

        # 验证队列中新增了任务
        新数量 = self.db.query(任务队列模型).filter(
            任务队列模型.机器码 == "test_machine_2",
            任务队列模型.状态 == "waiting"
        ).count()

        assert 新数量 == 初始数量 + 1
        print(f"[PASS] Result: {result}")
        print(f"[PASS] Queue task added: {初始数量} -> {新数量}")

    @patch('app.图引擎.内置工具.影刀触发._发送触发邮件')
    def test_callback_triggers_queued_task(self, mock_send_email):
        """测试5：回调触发队列任务"""
        print("\n[TEST 5] Testing callback triggers queued task...")

        # Mock 邮件发送 - 接受3个参数
        async def mock_send(recipient, subject, content):
            return "邮件发送成功"

        mock_send_email.side_effect = mock_send

        # 插入一个等待任务
        等待任务 = 任务队列模型(
            应用名="测试应用B",
            机器码="test_machine_2",
            状态="waiting"
        )
        self.db.add(等待任务)
        self.db.commit()
        任务id = 等待任务.id

        # 模拟回调：机器状态从 running 变为 idle
        from app.api.机器管理 import _处理任务队列

        机器 = self.db.query(机器模型).filter(机器模型.机器码 == "test_machine_2").first()
        if 机器:
            机器.状态 = "running"
            self.db.commit()

        # 调用处理队列函数
        asyncio.run(_处理任务队列("test_machine_2", self.db))

        # 验证任务状态变为 triggered
        任务 = self.db.query(任务队列模型).filter(任务队列模型.id == 任务id).first()

        assert 任务 is not None
        assert 任务.状态 == "triggered"
        assert mock_send_email.called
        print(f"[PASS] Task status changed to: {任务.状态}")
        print(f"[PASS] Email mock called: {mock_send_email.call_count} times")

    def test_callback_no_queue(self):
        """测试6：回调时队列为空"""
        print("\n[TEST 6] Testing callback with empty queue...")

        # 清空队列
        self.db.query(任务队列模型).filter(
            任务队列模型.机器码 == "test_machine_1"
        ).delete()
        self.db.commit()

        # 调用处理队列函数
        from app.api.机器管理 import _处理任务队列

        try:
            asyncio.run(_处理任务队列("test_machine_1", self.db))
            print("[PASS] No error when queue is empty")
        except Exception as e:
            pytest.fail(f"Should not raise error when queue is empty: {e}")


def test_callback_auth_required():
    """测试7：回调接口需要鉴权"""
    print("\n[TEST 7] Testing callback auth required...")

    from fastapi.testclient import TestClient
    from app.启动器 import app

    client = TestClient(app)

    # 不带 X-RPA-KEY 头
    response = client.put(
        "/api/machines/test_machine_1/status",
        json={"status": "idle"}
    )

    assert response.status_code in [401, 403]
    print(f"[PASS] Auth required: status code {response.status_code}")


if __name__ == "__main__":
    print("Running trigger_shadowbot tests...")
    pytest.main([__file__, "-v", "-s"])
