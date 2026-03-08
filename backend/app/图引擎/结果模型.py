# app/图引擎/结果模型.py
# 统一的 Agent 调用结果模型

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentResult:
    """Agent 调用结果的统一数据结构

    用于单 Agent 和多 Agent 模式的返回值统一
    """
    reply: str
    """Agent 的回复内容"""

    used_feishu: bool = False
    """是否调用了飞书工具发送消息（用于避免重复发送）"""

    agent_name: Optional[str] = None
    """执行任务的 Agent 名称（多 Agent 模式下有用）"""

    def to_tuple(self) -> tuple:
        """兼容旧代码：转换为 tuple 格式"""
        return (self.reply, self.used_feishu)

    def __iter__(self):
        """支持 tuple 解包：a, b = AgentResult(...)"""
        return iter((self.reply, self.used_feishu))

    def __getitem__(self, index):
        """支持索引访问：result[0], result[1]"""
        if index == 0:
            return self.reply
        elif index == 1:
            return self.used_feishu
        elif index == 2:
            return self.agent_name
        else:
            raise IndexError(f"AgentResult index out of range: {index}")

