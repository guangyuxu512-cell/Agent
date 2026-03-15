# app/图引擎/多Agent构建器.py
# Step 3：根据编排配置构建多 Agent 协作图

import logging
import re
from langgraph_supervisor import create_supervisor
from langgraph_swarm import create_swarm
from app.配置 import SUPERVISOR_API_KEY, SUPERVISOR_API_URL, SUPERVISOR_MODEL
from app.图引擎.构建器 import 获取LLM模型, 构建Agent图

logger = logging.getLogger(__name__)


def 安全Agent名称(原始名称: str, 索引: int) -> str:
    """将 Agent 名称转换为适合 transfer_to 工具名的英文标识符。"""
    清洗后名称 = re.sub(r"[^a-zA-Z0-9_]", "", 原始名称 or "")
    if not 清洗后名称:
        return f"agent_{索引}"
    if 清洗后名称[0].isdigit():
        清洗后名称 = f"agent_{清洗后名称}"
    return 清洗后名称


def 构建子Agent(agent配置: dict, 工具记录列表: list = None, 安全名称: str = None) -> object:
    """构建单个子 Agent（用于多 Agent 编排中的节点）"""
    子图 = 构建Agent图(agent配置, 工具记录列表=工具记录列表)
    子图.name = 安全名称 or agent配置.get("name", "agent")
    return 子图


def 获取Supervisor模型(入口配置: dict) -> object:
    """获取 Supervisor 使用的 LLM 模型。"""
    if SUPERVISOR_API_KEY and SUPERVISOR_API_URL and SUPERVISOR_MODEL:
        logger.info("[Supervisor] 使用独立配置的 Supervisor 模型: %s", SUPERVISOR_MODEL)
        supervisor配置 = {
            "llm_api_key": SUPERVISOR_API_KEY,
            "llm_api_url": SUPERVISOR_API_URL,
            "llm_model": SUPERVISOR_MODEL,
            "model": SUPERVISOR_MODEL,
            "temperature": 入口配置.get("temperature", 0.7),
        }
        return 获取LLM模型(supervisor配置)

    logger.info(
        "[Supervisor] 未配置独立模型，使用入口 Agent 的模型: %s",
        入口配置.get("llm_model") or 入口配置.get("model", "unknown"),
    )
    return 获取LLM模型(入口配置)


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
    有效agents信息列表 = []
    名称映射 = {}
    入口agent名称 = None
    for 索引, agent配置 in enumerate(agents配置列表):
        agent_id = agent配置.get("id", "")
        原始名称 = agent配置.get("name", "") or f"agent_{索引}"
        try:
            api_key = (agent配置.get("llm_api_key") or "").strip()
            base_url = (agent配置.get("llm_api_url") or "").strip()
            if not api_key or not base_url:
                logger.warning("跳过未配置LLM的Agent: 原始名称=%s", 原始名称)
                continue

            安全名称 = 安全Agent名称(原始名称, 索引)
            if 安全名称 in 名称映射:
                安全名称 = f"{安全名称}_{索引}"

            工具记录 = 工具记录映射.get(agent_id, [])
            try:
                子agent = 构建子Agent(agent配置, 工具记录, 安全名称=安全名称)
            except TypeError as e:
                if "安全名称" not in str(e):
                    raise
                子agent = 构建子Agent(agent配置, 工具记录)

            实际名称 = getattr(子agent, "name", 安全名称) or 安全名称
            子agents.append(子agent)
            有效agents信息列表.append({
                "配置": agent配置,
                "安全名称": 安全名称,
                "实际名称": 实际名称,
                "原始名称": 原始名称,
            })
            名称映射[实际名称] = 原始名称

            logger.info(
                "构建子Agent成功: 安全名称=%s, 实际名称=%s, 原始名称=%s, agent_id=%s",
                安全名称,
                实际名称,
                原始名称,
                agent_id,
            )

            if agent_id == 入口agent_id:
                入口agent名称 = 实际名称
        except Exception as e:
            logger.error(
                "构建子Agent失败，跳过: 安全名称=%s, 原始名称=%s, error=%s",
                安全Agent名称(原始名称, 索引),
                原始名称,
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
        for agent信息 in 有效agents信息列表:
            if agent信息["配置"].get("id") == 入口agent_id:
                入口配置 = agent信息["配置"]
                break
        if not 入口配置:
            入口配置 = 有效agents信息列表[0]["配置"]

        supervisor模型 = 获取Supervisor模型(入口配置)

        # 构建 Supervisor 的 prompt，明确指示使用 tool calling 进行路由
        agent_names = [agent.name for agent in 子agents]
        agent_descriptions = []
        for agent信息 in 有效agents信息列表:
            agent配置 = agent信息["配置"]
            安全名称 = agent信息["实际名称"]
            原始名称 = agent信息["原始名称"]
            role = agent配置.get("role", "")
            desc = agent配置.get("description", "")
            if role or desc:
                agent_descriptions.append(f"- {安全名称}（{原始名称}）: {role or desc}")
            else:
                agent_descriptions.append(f"- {安全名称}（{原始名称}）")

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

        名称映射说明 = "\n".join(
            f"- 当你需要委派给「{原始名称}」时，调用 transfer_to_{安全名称}"
            for 安全名称, 原始名称 in 名称映射.items()
        )

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
        prompt += f"\n\n智能体名称映射：\n{名称映射说明}"

        logger.info(f"[Supervisor] 可用智能体: {agent_names}")
        logger.info(f"[Supervisor] 名称映射: {名称映射}")
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
