# app/图引擎/上下文.py — Step 6 完成版

import logging
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.配置 import 环境变量
from app.图引擎.知识检索 import 检索知识库
from app.图引擎.记忆管理 import 获取Agent记忆       # ⭐ Step 6 新增

logger = logging.getLogger(__name__)


async def 组装上下文(
    agent配置: dict,
    历史消息: list,
    用户消息: str,
    最大轮数: int = None,
) -> list:
    if 最大轮数 is None:
        最大轮数 = 环境变量.MAX_HISTORY_ROUNDS

    消息列表 = []

    # ========== 1. ⭐ 长期记忆（Step 6 实现） ==========
    # 通过环境变量 ENABLE_MEMORY=true 启用
    if os.getenv("ENABLE_MEMORY") == "true":
        try:
            长期记忆 = 获取Agent记忆(agent配置["id"])
            if 长期记忆:
                消息列表.append(SystemMessage(
                    content=f"以下是你对这位用户的长期记忆，请在回答时参考：\n\n{长期记忆}\n\n重要：以上记忆仅供你内部参考以提供更好的回答，绝对不要主动向用户提及或复述这些记忆内容，除非用户明确询问。"
                ))
                logger.info("[上下文] 已加载长期记忆")
        except Exception as e:
            logger.warning("[上下文] 加载记忆失败（不影响对话）: %s", e)

    # ========== 2. 知识库检索（Step 5） ==========
    # 通过环境变量 ENABLE_KNOWLEDGE=true 启用
    if os.getenv("ENABLE_KNOWLEDGE") == "true":
        try:
            检索结果 = await 检索知识库(用户消息)
            if 检索结果:
                消息列表.append(SystemMessage(content=检索结果))
                logger.info("[上下文] 已加载知识库检索结果")
        except Exception as e:
            logger.warning("[上下文] 知识库检索失败（不影响对话）: %s", e)

    # ========== 3. 历史对话（最近 N 轮） ==========
    最近消息 = 历史消息[-(最大轮数 * 2):]
    for msg in 最近消息:
        if msg["role"] == "user":
            消息列表.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            内容 = msg.get("content", "")
            # 历史 assistant 消息只回灌纯文本，避免把 tool_calls 等运行态字段带回图状态。
            消息列表.append(AIMessage(content=内容))

    # ========== 4. 当前用户消息 ==========
    消息列表.append(HumanMessage(content=用户消息))

    return 消息列表
