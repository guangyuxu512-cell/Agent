# app/图引擎/内置工具/__init__.py
# 内置工具包：自动收集所有工具并导出 BUILTIN_TOOLS 映射表

from .邮件 import 发送邮件
from .飞书 import 飞书助手
from .影刀触发 import 触发影刀

# 内置工具映射表
BUILTIN_TOOLS = {
    "send_email": 发送邮件,
    "feishu_assistant": 飞书助手,
    "trigger_shadowbot": 触发影刀,
}

__all__ = ["BUILTIN_TOOLS", "发送邮件", "飞书助手", "触发影刀"]
