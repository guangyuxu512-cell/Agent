# app/图引擎/智能调用.py
# 统一的 Agent 调用入口，支持单 Agent 和多 Agent 编排

import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.db.数据库 import 会话工厂
from app.db.模型 import Agent模型, 编排模型
from app.加密 import 解密
from app.图引擎.构建器 import 构建Agent图
from app.图引擎.多Agent构建器 import 构建多Agent图
from app.图引擎.结果模型 import AgentResult

logger = logging.getLogger(__name__)


def 获取编排配置(db: Session) -> Optional[dict]:
    """读取编排配置，如果没有或只有单 Agent 模式则返回 None"""
    try:
        记录 = db.query(编排模型).filter(编排模型.id == "default").first()
        if not 记录 or not 记录.模式:
            return None
        return {
            "mode": 记录.模式,
            "entryAgent": 记录.入口agent_id or "",
            "routingRules": 记录.路由规则 or "",
            "parallelGroups": 记录.并行分组 or "",
        }
    except Exception as e:
        logger.error(f"[智能调用] 读取编排配置失败: {e}")
        return None


def 获取所有running_Agent配置和工具(db: Session) -> tuple[list[dict], dict[str, list]]:
    """获取所有 running 状态的 Agent 配置及其工具记录"""
    agents = db.query(Agent模型).filter(Agent模型.状态 == "running").all()
    agents配置列表 = []
    工具记录映射 = {}

    for agent in agents:
        配置 = agent.to_config_dict(解密函数=解密)
        agents配置列表.append(配置)

        # 获取工具记录
        from app.api.对话 import 获取Agent工具记录
        工具记录映射[agent.id] = 获取Agent工具记录(db, 配置)

    return agents配置列表, 工具记录映射


async def 智能调用Agent(
    消息列表: list,
    agent配置: dict,
    工具记录列表: list = None,
    db: Session = None
) -> AgentResult:
    """
    智能调用 Agent：自动判断使用单 Agent 还是多 Agent 编排。

    Args:
        消息列表: 消息历史列表
        agent配置: 当前 Agent 的配置字典
        工具记录列表: 当前 Agent 的工具记录列表
        db: 数据库会话（如果为 None，会自动创建）

    Returns:
        AgentResult: 包含回复、是否调用飞书工具等信息
    """
    需要关闭db = False
    if db is None:
        db = 会话工厂()
        需要关闭db = True

    try:
        # 1. 检查是否启用多 Agent 编排
        编排 = 获取编排配置(db)

        if 编排:
            agents配置列表, 工具记录映射 = 获取所有running_Agent配置和工具(db)

            # 至少 2 个 running 的 Agent 才走多 Agent 模式
            if len(agents配置列表) >= 2:
                logger.info(f"[智能调用] 使用多Agent编排模式，Agent数量: {len(agents配置列表)}")

                # 构建多 Agent 图
                图 = 构建多Agent图(编排, agents配置列表, 工具记录映射)

                # 执行多 Agent 图
                完整回复 = ""
                调用了飞书工具 = False
                当前agent名称 = ""

                async for event in 图.astream_events(
                    {"messages": 消息列表},
                    version="v2",
                ):
                    事件类型 = event.get("event", "")

                    # 收集 LLM 输出
                    if 事件类型 == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            完整回复 += chunk.content

                            # 记录当前 Agent
                            agent名 = event.get("metadata", {}).get("langgraph_node", "")
                            if agent名:
                                当前agent名称 = agent名

                    # 检测飞书工具调用
                    elif 事件类型 == "on_tool_start":
                        工具名 = event.get("name", "")
                        if 工具名 == "飞书助手":
                            工具参数 = event.get("data", {}).get("input", {})
                            操作类型 = 工具参数.get("操作类型", "")
                            if 操作类型 == "发消息":
                                调用了飞书工具 = True
                                logger.info(f"[智能调用] 检测到飞书工具调用")

                return AgentResult(
                    reply=完整回复 or "（智能体未返回内容）",
                    used_feishu=调用了飞书工具,
                    agent_name=当前agent名称 or "多Agent"
                )

        # 2. 单 Agent 模式
        logger.info(f"[智能调用] 使用单Agent模式: {agent配置.get('name', 'Unknown')}")

        # 构建单 Agent 图
        图 = 构建Agent图(agent配置, 工具记录列表=工具记录列表)

        # 执行单 Agent 图
        完整回复 = ""
        调用了飞书工具 = False

        async for event in 图.astream_events(
            {"messages": 消息列表},
            version="v2",
        ):
            事件类型 = event.get("event", "")

            # 收集 LLM 输出
            if 事件类型 == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    完整回复 += chunk.content

            # 检测飞书工具调用
            elif 事件类型 == "on_tool_start":
                工具名 = event.get("name", "")
                if 工具名 == "飞书助手":
                    工具参数 = event.get("data", {}).get("input", {})
                    操作类型 = 工具参数.get("操作类型", "")
                    if 操作类型 == "发消息":
                        调用了飞书工具 = True
                        logger.info(f"[智能调用] 检测到飞书工具调用")

        return AgentResult(
            reply=完整回复 or "（智能体未返回内容）",
            used_feishu=调用了飞书工具,
            agent_name=agent配置.get("name", "")
        )

    finally:
        if 需要关闭db:
            db.close()
