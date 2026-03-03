# app/图引擎/构建器.py
# Step 4 版：支持动态工具加载 + 系统提示词注入
# ⭐ 问题7修复：用 prompt 强制注入系统提示词
# ⭐ 问题8修复：role→description + 工具描述注入系统提示
# ⭐ 问题9修复：state_modifier → prompt（langgraph ≥1.0 不再支持 state_modifier）
# ⭐ 并发修复：移除 os.environ 全局赋值，避免多 Agent 竞态覆盖

import logging
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from app.配置 import 环境变量
from app.图引擎.工具加载器 import 加载工具列表
from app.常量 import DEFAULT_TEMPERATURE

logger = logging.getLogger(__name__)


def 获取LLM模型(agent配置: dict) -> ChatOpenAI:
    """
    根据 Agent 配置创建 LLM 实例（仅使用 Agent 显式参数，不依赖环境变量）
    """
    api_key = (agent配置.get("llm_api_key") or "").strip()
    base_url = (agent配置.get("llm_api_url") or "").strip()

    if not base_url or not api_key:
        agent_name = agent配置.get("name", "")
        agent_id = agent配置.get("id", "")
        raise ValueError(
            "LLM 未配置：请在智能体管理中为当前智能体填写 llmApiUrl 和 llmApiKey。"
            f"（agent={agent_name or '未命名'} {agent_id[:8]}...）"
        )

    logger.info("创建LLM: base_url=%s, model=%s", base_url, agent配置.get("model"))

    模型 = ChatOpenAI(
        model=agent配置.get("model", 环境变量.DEFAULT_MODEL),
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=agent配置.get("temperature", DEFAULT_TEMPERATURE),
        streaming=True,
    )

    return 模型


def 构建系统提示(agent配置: dict, 工具记录列表: list = None) -> str:
    """
    从 Agent 配置构建系统提示词。
    拼接顺序：名称 → 描述(角色) → 自定义提示词 → 可用工具 → 约束声明
    ⭐ 问题8修复：
      1. role → description（数据库字段名修正）
      2. 新增工具描述注入，让 AI 知道自己有什么技能
    """
    系统部分 = []

    名称 = agent配置.get("name", "").strip()
    # ⭐ 问题8修复：数据库里是 description 字段，不是 role
    角色 = agent配置.get("description", "").strip()
    提示词 = agent配置.get("system_prompt", "").strip()

    if 名称:
        系统部分.append(f"你的名字是：{名称}")
    if 角色:
        系统部分.append(f"你的角色定位：{角色}")
    if 提示词:
        系统部分.append(f"行为准则：\n{提示词}")

    # ⭐ 问题8修复：把工具信息注入系统提示，让 AI 知道自己能做什么
    if 工具记录列表:
        import json as _json
        工具描述列表 = []
        for t in 工具记录列表:
            # ⭐ 修复：对于 builtin 类型的工具，使用英文名称（builtin_name）
            # 这样 system prompt 中的工具名称与实际绑定的工具名称一致
            工具名称 = t.get("name", "未知")
            if t.get("tool_type") == "builtin":
                try:
                    配置原始 = t.get("config", "{}")
                    if isinstance(配置原始, str):
                        配置 = _json.loads(配置原始)
                    else:
                        配置 = 配置原始
                    builtin_name = 配置.get("builtin_name", "")
                    if builtin_name:
                        工具名称 = builtin_name  # 使用英文名称
                except:
                    pass  # 解析失败则使用原名称

            描 = t.get("description", "")
            参数原始 = t.get("parameters", "{}")
            if isinstance(参数原始, str):
                try:
                    参数 = _json.loads(参数原始)
                except:
                    参数 = {}
            else:
                参数 = 参数原始
            参数说明 = ""
            props = 参数.get("properties", {})
            if props:
                参数说明 = "，参数：" + "、".join(
                    f"{k}({v.get('description', v.get('type', ''))})" for k, v in props.items()
                )
            工具描述列表.append(f"- {工具名称}：{描}{参数说明}")
        工具文本 = "\n".join(工具描述列表)

        # 工具技能说明 + 权限声明
        工具说明 = f"你拥有以下工具技能，当用户提出相关需求时，你必须直接调用对应的工具来完成任务，而不是解释如何操作或告诉用户你无法访问：\n{工具文本}"
        权限声明 = "重要权限声明：用户已经配置好所有必要的API密钥、权限和凭证，你可以直接使用工具访问数据，不要以'没有权限'、'无法访问'等理由拒绝。当用户询问飞书表格数据时，你必须使用「feishu_assistant」工具进行查询或写入。"

        系统部分.append(f"{工具说明}\n\n{权限声明}")

    # 约束声明
    if 系统部分:
        系统部分.append("请严格按照以上角色定位和行为准则回答用户问题，不要偏离设定。")

    return "\n\n".join(系统部分)


def 构建Agent图(agent配置: dict, 工具记录列表: list = None) -> object:
    """从数据库的 Agent 配置动态构建 LangGraph

    ⭐ 修复：不使用 create_react_agent，改用自定义 agent + bind_tools
    原因：create_react_agent 的内部逻辑导致 LLM 拒绝调用工具
    """
    import logging
    from typing import Annotated
    from typing_extensions import TypedDict
    from langgraph.graph import StateGraph, START, END
    from langgraph.graph.message import add_messages
    from langchain_core.messages import SystemMessage, AIMessage, ToolMessage
    from langgraph.prebuilt import ToolNode

    logger = logging.getLogger(__name__)

    logger.info(f"[构建器] 开始构建Agent图，工具记录列表长度: {len(工具记录列表) if 工具记录列表 else 0}")

    模型 = 获取LLM模型(agent配置)

    工具列表 = []
    if 工具记录列表:
        logger.info(f"[构建器] 调用加载工具列表，记录数: {len(工具记录列表)}")
        工具列表 = 加载工具列表(工具记录列表)
        logger.info(f"[构建器] 加载完成，工具列表长度: {len(工具列表)}, 工具名称: {[t.name for t in 工具列表]}")
    else:
        logger.warning(f"[构建器] 工具记录列表为空，不加载工具")

    # 构建系统提示
    系统提示 = 构建系统提示(agent配置, 工具记录列表=工具记录列表)

    # ⭐ 关键修复：直接使用 bind_tools（已验证有效）
    if 工具列表:
        模型_with_tools = 模型.bind_tools(工具列表)
        logger.info(f"[构建器] 使用 bind_tools 绑定 {len(工具列表)} 个工具")
    else:
        模型_with_tools = 模型
        logger.info(f"[构建器] 无工具，使用原始模型")

    # 定义状态
    class AgentState(TypedDict):
        messages: Annotated[list, add_messages]

    # 定义 agent 节点
    def call_model(state: AgentState):
        messages = state["messages"]

        # 在最前面添加系统提示（包含工具描述和权限声明）
        if 系统提示:
            messages = [SystemMessage(content=系统提示)] + messages
            logger.debug(f"[构建器] 已添加系统提示，消息数={len(messages)}")

        logger.debug(f"[构建器] 发送给LLM的消息数: {len(messages)}")

        for i, msg in enumerate(messages):
            msg_type = type(msg).__name__
            content_preview = ""
            if hasattr(msg, 'content'):
                content = str(msg.content) if msg.content else ""
                content_preview = content[:200] if len(content) > 200 else content
            logger.info(f"[构建器-调试] 消息{i+1} - {msg_type}: {content_preview}")

        response = 模型_with_tools.invoke(messages)
        return {"messages": [response]}

    # 定义路由函数
    def should_continue(state: AgentState):
        messages = state["messages"]
        last_message = messages[-1]

        # 如果有工具调用，继续执行工具
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        # 否则结束
        return END

    # 创建图
    workflow = StateGraph(AgentState)

    # 添加节点
    workflow.add_node("agent", call_model)
    if 工具列表:
        workflow.add_node("tools", ToolNode(工具列表))

    # 添加边
    workflow.add_edge(START, "agent")
    if 工具列表:
        workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
        workflow.add_edge("tools", "agent")
    else:
        workflow.add_edge("agent", END)

    # 编译图
    图 = workflow.compile()
    logger.info(f"[构建器] Agent图构建完成（自定义agent + bind_tools）")

    return 图