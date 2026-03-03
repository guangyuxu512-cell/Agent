"""
模型.py — 全部 12 张表（合并版）
基类：基础模型(DeclarativeBase) — 和 数据库.py 对齐
属性：中文 ORM 属性 + 英文列名映射 — 和所有路由文件对齐
"""

import uuid
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Float, func
from sqlalchemy.orm import DeclarativeBase
from app.常量 import DEFAULT_MODEL, DEFAULT_TEMPERATURE


class 基础模型(DeclarativeBase):
    pass
# ⭐ 兼容别名：服务器上有些文件 import Base，有些 import 基础模型，都能用
Base = 基础模型


# ==================== 表 1：用户 ====================
class 用户模型(基础模型):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    用户名 = Column("username", String(50), unique=True, nullable=False)
    密码哈希 = Column("password_hash", String(255), nullable=False)
    创建时间 = Column("created_at", DateTime, default=func.now())


# ==================== 表 2：智能体 ====================
class Agent模型(基础模型):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True)
    名称 = Column("name", String(100), nullable=False)
    角色 = Column("role", String(500), default="")
    提示词 = Column("prompt", Text, default="")
    提供商 = Column("llm_provider", String(50), default="OpenAI")
    模型名称 = Column("llm_model", String(50), default="GPT-4o")
    接口地址 = Column("llm_api_url", String(500), default="")
    接口密钥 = Column("llm_api_key", String(500), default="")
    温度 = Column("temperature", Float, default=0.7)
    工具列表 = Column("tools", Text, default="[]")
    最大迭代 = Column("max_iterations", Integer, default=10)
    超时时间 = Column("timeout_seconds", Integer, default=60)
    需要审批 = Column("require_approval", Boolean, default=False)
    状态 = Column("status", String(20), default="stopped")
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())
    创建时间 = Column("created_at", DateTime, default=func.now())

    def to_config_dict(self, 解密函数=None) -> dict:
        """转为内部 LLM 配置字典（对话/飞书/调度器共用）"""
        api_key = self.接口密钥 or ""
        if 解密函数:
            api_key = 解密函数(api_key)
        return {
            "id": self.id,
            "name": self.名称,
            "role": self.角色 or "",
            "description": self.角色 or "",
            "system_prompt": self.提示词 or "",
            "model": self.模型名称 or DEFAULT_MODEL,
            "llm_api_url": self.接口地址 or "",
            "llm_api_key": api_key,
            "temperature": self.温度 if self.温度 is not None else DEFAULT_TEMPERATURE,
            "tools": self.工具列表 or "[]",
            "status": self.状态 or "stopped",
        }


# ==================== 表 3：对话 ====================
class 对话模型(基础模型):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)
    agent_id = Column(String(36), nullable=False)
    标题 = Column("title", String(200), default="新对话")
    来源 = Column("source", String(20), default="web")
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())
    创建时间 = Column("created_at", DateTime, default=func.now())


# ==================== 表 4：消息 ====================
class 消息模型(基础模型):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True)
    对话id = Column("conversation_id", String(36), nullable=False)
    角色 = Column("role", String(20), nullable=False)
    内容 = Column("content", Text, default="")
    agent名称 = Column("agent_name", String(100), default="")
    tool_calls = Column(Text, default=None)
    tool_call_id = Column(String(36), default=None)
    创建时间 = Column("created_at", DateTime, default=func.now())


# ==================== 表 5：工具 ====================
class 工具模型(基础模型):
    __tablename__ = "tools"

    id = Column(String(36), primary_key=True)
    名称 = Column("name", String(100), nullable=False)
    描述 = Column("description", Text, default="")
    类型 = Column("tool_type", String(20), default="http_api")
    参数定义 = Column("parameters", Text, default="{}")
    配置 = Column("config", Text, default="{}")
    状态 = Column("status", String(20), default="active")
    创建时间 = Column("created_at", DateTime, default=func.now())
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())


# ==================== 表 6：定时任务 ====================
class 定时任务模型(基础模型):
    __tablename__ = "schedules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    名称 = Column("name", String(100), nullable=False)
    描述 = Column("description", Text, default="")
    agent_id = Column(String(36), nullable=False)
    触发类型 = Column("trigger_type", String(20), default="cron")
    触发配置 = Column("trigger_config", Text, default="{}")
    提示词 = Column("prompt", Text, default="")
    启用 = Column("enabled", Boolean, default=True)
    上次运行 = Column("last_run_at", DateTime, default=None)
    下次运行 = Column("next_run_at", DateTime, default=None)
    创建时间 = Column("created_at", DateTime, default=func.now())
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())


# ==================== 表 7：任务执行记录 ====================
class 任务记录模型(基础模型):
    __tablename__ = "schedule_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    schedule_id = Column(String(36), nullable=False)
    状态 = Column("status", String(20), default="running")
    结果 = Column("result", Text, default="")
    错误 = Column("error", Text, default=None)
    开始时间 = Column("started_at", DateTime, default=func.now())
    结束时间 = Column("finished_at", DateTime, default=None)


# ==================== 表 8：编排配置 ====================
class 编排模型(基础模型):
    __tablename__ = "orchestration"

    id = Column(String(36), primary_key=True, default="default")
    模式 = Column("mode", String(20), default="Supervisor")
    入口agent_id = Column("entry_agent_id", String(36), default="")
    路由规则 = Column("routing_rules", Text, default="")
    并行分组 = Column("parallel_groups", Text, default="")
    全局状态 = Column("global_state", Text, default="[]")
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())


# ==================== 表 9：系统配置 ====================
class 系统配置模型(基础模型):
    __tablename__ = "system_config"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    分类 = Column("category", String(50), nullable=False)
    键 = Column("key", String(100), nullable=False)
    值 = Column("value", Text, default="")
    说明 = Column("description", String(200), default="")
    创建时间 = Column("created_at", DateTime, default=func.now())
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())


# ==================== 表 10：飞书表格 ====================
class 飞书表格模型(基础模型):
    __tablename__ = "feishu_tables"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    名称 = Column("name", String(100), nullable=False)
    app_token = Column(String(200), nullable=False)
    table_id = Column(String(200), nullable=False)
    描述 = Column("description", Text, default="")
    字段映射 = Column("field_mapping", Text, default="{}")
    创建时间 = Column("created_at", DateTime, default=func.now())
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())


# ==================== 表 11：N8N 工作流 ====================
class N8N工作流模型(基础模型):
    __tablename__ = "n8n_workflows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    名称 = Column("name", String(100), nullable=False)
    webhook_url = Column(String(500), nullable=False)
    描述 = Column("description", Text, default="")
    请求方法 = Column("method", String(10), default="POST")
    请求头 = Column("headers", Text, default="{}")
    示例载荷 = Column("sample_payload", Text, default="{}")
    启用 = Column("enabled", Boolean, default=True)
    创建时间 = Column("created_at", DateTime, default=func.now())
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())


# ==================== 表 12：长期记忆 ====================
class 记忆模型(基础模型):
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String(36), nullable=False)
    conversation_id = Column(String(36), default=None)
    记忆类型 = Column("memory_type", String(20), default="summary")
    内容 = Column("content", Text, nullable=False)
    重要性 = Column("importance", Float, default=0.5)
    创建时间 = Column("created_at", DateTime, default=func.now())
    过期时间 = Column("expires_at", DateTime, default=None)


# ==================== 表 13：推送日志 ====================
class 推送日志模型(基础模型):
    __tablename__ = "push_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)  # 自增 ID 即 seq
    时间 = Column("time", String(30), default="")
    任务ID = Column("task_id", String(100), default="未知任务")
    设备 = Column("machine", String(100), default="未知设备")
    级别 = Column("level", String(20), default="进行中")
    消息 = Column("msg", Text, default="")
    创建时间 = Column("created_at", DateTime, default=func.now())


# ==================== 表 14：机器管理 ====================
class 机器模型(基础模型):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    机器码 = Column("machine_id", String(100), unique=True, nullable=False)
    机器名称 = Column("machine_name", String(200), nullable=False)
    状态 = Column("status", String(20), default="offline")  # idle / running / error / offline
    最后心跳 = Column("last_heartbeat", DateTime, default=None)
    创建时间 = Column("created_at", DateTime, default=func.now())
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())


# ==================== 表 15：机器应用绑定 ====================
class 机器应用模型(基础模型):
    __tablename__ = "machine_apps"
    __table_args__ = (
        # 联合唯一约束：同一机器不能重复绑定同一应用
        {'sqlite_autoincrement': True}
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    机器码 = Column("machine_id", String(100), nullable=False)
    应用名 = Column("app_name", String(200), nullable=False)
    描述 = Column("description", Text, default="")
    启用 = Column("enabled", Boolean, default=True)
    创建时间 = Column("created_at", DateTime, default=func.now())


# ==================== 表 16：任务队列 ====================
class 任务队列模型(基础模型):
    __tablename__ = "task_queue"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    应用名 = Column("app_name", String(100), nullable=False)
    机器码 = Column("machine_id", String(100), nullable=False)
    状态 = Column("status", String(20), default="waiting")  # waiting / triggered / failed
    创建时间 = Column("created_at", DateTime, default=func.now())
    触发时间 = Column("triggered_at", DateTime, default=None)
    错误 = Column("error", Text, default=None)