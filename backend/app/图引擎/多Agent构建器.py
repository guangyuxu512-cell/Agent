# app/图引擎/多Agent构建器.py
# Step 3：根据编排配置构建多 Agent 协作图

import logging
from langgraph_supervisor import create_supervisor
from langgraph_swarm import create_swarm
from app.图引擎.构建器 import 获取LLM模型, 构建Agent图

logger = logging.getLogger(__name__)


def 构建子Agent(agent配置: dict, 工具记录列表: list = None) -> object:
    """构建单个子 Agent（用于多 Agent 编排中的节点）"""
    子图 = 构建Agent图(agent配置, 工具记录列表=工具记录列表)
    子图.name = agent配置.get("name", "agent")
    return 子图


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
    有效agents配置列表 = []
    入口agent名称 = None
    for agent配置 in agents配置列表:
        agent_id = agent配置.get("id", "")
        try:
            api_key = (agent配置.get("llm_api_key") or "").strip()
            base_url = (agent配置.get("llm_api_url") or "").strip()
            if not api_key or not base_url:
                logger.warning("跳过未配置LLM的Agent: %s", agent配置.get("name"))
                continue

            工具记录 = 工具记录映射.get(agent_id, [])
            子agent = 构建子Agent(agent配置, 工具记录)
            子agents.append(子agent)
            有效agents配置列表.append(agent配置)

            if agent_id == 入口agent_id:
                入口agent名称 = agent配置.get("name", "agent")
        except Exception as e:
            logger.error(
                "构建子Agent失败，跳过: %s, error=%s",
                agent配置.get("name"),
                e,
            )
            continue

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
        for a in 有效agents配置列表:
            if a.get("id") == 入口agent_id:
                入口配置 = a
                break
        if not 入口配置:
            入口配置 = 有效agents配置列表[0]

        supervisor模型 = 获取LLM模型(入口配置)

        # 构建 Supervisor 的 prompt，明确指示使用 tool calling 进行路由
        agent_names = [agent.name for agent in 子agents]
        agent_descriptions = []
        for i, agent配置 in enumerate(有效agents配置列表):
            name = agent配置.get("name", f"agent_{i}")
            role = agent配置.get("role", "")
            desc = agent配置.get("description", "")
            if role or desc:
                agent_descriptions.append(f"- {name}: {role or desc}")
            else:
                agent_descriptions.append(f"- {name}")

        if len(子agents) >= 2:
            示例文本 = (
                "示例：\n"
                f"- 调用 transfer_to_{子agents[0].name} 工具\n"
                f"- 调用 transfer_to_{子agents[1].name} 工具"
            )
        elif len(子agents) == 1:
            示例文本 = f"示例：\n- 调用 transfer_to_{子agents[0].name} 工具"
        else:
            示例文本 = ""

        prompt = f"""你是一个任务调度主管。你的职责是分析用户请求，并将任务委派给最合适的智能体处理。

可用的智能体：
{chr(10).join(agent_descriptions)}

【重要】你必须遵守以下规则：
1. 仔细分析用户的请求内容
2. 选择最合适的智能体来处理该任务
3. 【必须】使用 transfer_to_<agent_name> 工具将任务委派给选定的智能体
4. 【禁止】自己回答问题或只用文字描述，你必须调用工具
5. 【禁止】说"我将分配给xxx"这样的话，直接调用工具即可
6. 每次只能委派给一个智能体

{示例文本}"""

        路由规则 = 编排配置.get("routingRules", "").strip()
        if 路由规则:
            prompt += f"\n\n路由规则：\n{路由规则}"

        logger.info(f"[Supervisor] 可用智能体: {agent_names}")
        logger.info(f"[Supervisor] Prompt 前100字: {prompt[:100]}...")

        # 创建 Supervisor 图
        图 = create_supervisor(
            agents=子agents,
            model=supervisor模型,
            prompt=prompt,
            parallel_tool_calls=False,  # 禁用并行调用，确保一次只委派一个任务
        )

        # 编译图并添加调试
        compiled_graph = 图.compile()

        # 打印图的节点信息
        logger.info(f"[Supervisor] 图节点: {list(compiled_graph.nodes.keys()) if hasattr(compiled_graph, 'nodes') else 'N/A'}")

        return compiled_graph
