# app/图引擎/多Agent构建器.py
# Step 3：根据编排配置构建多 Agent 协作图

import json
import logging
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from langgraph_swarm import create_swarm
from app.图引擎.构建器 import 获取LLM模型, 构建系统提示

logger = logging.getLogger(__name__)


def 构建子Agent(agent配置: dict, 工具记录列表: list = None) -> object:
    """构建单个子 Agent（用于多 Agent 编排中的节点）"""
    模型 = 获取LLM模型(agent配置)

    工具列表 = []
    if 工具记录列表:
        from app.图引擎.工具加载器 import 加载工具列表
        工具列表 = 加载工具列表(工具记录列表)

    系统提示 = 构建系统提示(agent配置, 工具记录列表=工具记录列表)

    构建参数 = {
        "model": 模型,
        "tools": 工具列表,
        "name": agent配置.get("name", "agent"),
    }
    if 系统提示:
        构建参数["prompt"] = 系统提示

    return create_react_agent(**构建参数)


def 构建多Agent图(
    编排配置: dict,
    agents配置列表: list[dict],
    工具记录映射: dict[str, list] = None,
) -> object:
    """
    根据编排配置构建多 Agent 协作图。

    参数:
        编排配置: {"mode": "Supervisor"|"Network"|"Hierarchical", "entryAgent": "...", ...}
        agents配置列表: [agent配置字典, ...]
        工具记录映射: {agent_id: [工具记录, ...], ...}

    返回:
        编译好的 LangGraph 图
    """
    if not 工具记录映射:
        工具记录映射 = {}

    模式 = 编排配置.get("mode", "Supervisor")
    入口agent_id = 编排配置.get("entryAgent", "")

    # 构建所有子 Agent
    子agents = []
    入口agent名称 = None
    for agent配置 in agents配置列表:
        agent_id = agent配置.get("id", "")
        工具记录 = 工具记录映射.get(agent_id, [])
        子agent = 构建子Agent(agent配置, 工具记录)
        子agents.append(子agent)
        if agent_id == 入口agent_id:
            入口agent名称 = agent配置.get("name", "agent")

    if not 子agents:
        raise ValueError("没有可用的子 Agent")

    logger.info("构建多Agent图: mode=%s, agents=%d", 模式, len(子agents))

    if 模式 == "Network":
        # Network 模式：平等协作，Agent 之间可以互相 handoff
        图 = create_swarm(
            agents=子agents,
            default_active_agent=入口agent名称 or 子agents[0].name,
        )
        return 图.compile()

    else:
        # Supervisor / Hierarchical 模式：主管调度
        # 用入口 Agent 的 LLM 作为 supervisor 的模型
        入口配置 = None
        for a in agents配置列表:
            if a.get("id") == 入口agent_id:
                入口配置 = a
                break
        if not 入口配置:
            入口配置 = agents配置列表[0]

        supervisor模型 = 获取LLM模型(入口配置)

        prompt = "你是一个任务调度主管。根据用户的请求，将任务分配给最合适的智能体处理。"
        路由规则 = 编排配置.get("routingRules", "").strip()
        if 路由规则:
            prompt += f"\n\n路由规则：\n{路由规则}"

        图 = create_supervisor(
            agents=子agents,
            model=supervisor模型,
            prompt=prompt,
        )
        return 图.compile()
