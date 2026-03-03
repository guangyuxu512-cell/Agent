# app/飞书/智能体调用.py
# 飞书长连接：智能体调用（含重试逻辑）

import asyncio
import logging

from app.db.数据库 import 会话工厂
from app.图引擎.构建器 import 构建Agent图
from app.图引擎.上下文 import 组装上下文
from app.常量 import FEISHU_MAX_RETRY, FEISHU_AGENT_TIMEOUT
from app.飞书.配置与会话 import (
    获取飞书loop, 获取Agent工具记录, 保存消息, 获取历史消息,
)

logger = logging.getLogger(__name__)


async def 调用智能体(agent配置: dict, 用户消息: str, 对话id: str) -> tuple[str, bool]:
    """
    调用 LangGraph 智能体处理消息，返回完整回复文本和是否调用了飞书工具。

    修复要点：
    1. 用户消息只保存一次（在重试循环外）
    2. 403/500/429 指数退避重试
    3. 诊断日志：失败时打印 base_url + api_key 长度
    4. DashScope 特定错误识别
    5. ⭐ 新增：检测是否调用了飞书助手工具发送消息，避免重复发送

    Returns:
        tuple[str, bool]: (回复文本, 是否调用了飞书发送消息工具)
    """
    最大重试 = FEISHU_MAX_RETRY
    db = 会话工厂()
    try:
        logger.info(f"[飞书调试] 收到消息，准备调用Agent，消息内容: {用户消息}")
        # 1. 保存用户消息（仅一次）
        保存消息(db, 对话id, "user", 用户消息)

        # 2. 获取历史（排除刚保存的当前消息）
        历史 = 获取历史消息(db, 对话id)
        历史 = 历史[:-1] if 历史 else []

        # 3. 组装上下文
        消息列表 = await 组装上下文(
            agent配置=agent配置,
            历史消息=历史,
            用户消息=用户消息,
        )

        # 4. 构建 Agent 图（含工具）
        工具记录列表 = 获取Agent工具记录(db, agent配置)
        图 = 构建Agent图(agent配置, 工具记录列表=工具记录列表)
        logger.info(f"[飞书调试] 工具列表: {[工具.get('name', str(工具)) for 工具 in 工具记录列表]}, 数量: {len(工具记录列表)}")

        # 5. 重试循环
        最后异常 = None
        完整回复 = ""
        调用了飞书发送消息 = False  # ⭐ 新增：标记是否调用了飞书发送消息工具

        for 第几次 in range(最大重试 + 1):
            try:
                完整回复 = ""
                async for event in 图.astream_events(
                    {"messages": 消息列表},
                    version="v2",
                ):
                    事件类型 = event.get("event", "")
                    logger.info(f"[飞书调试] 事件类型: {事件类型}")

                    # 处理 LLM 文本输出
                    if 事件类型 == "on_chat_model_stream":
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            完整回复 += chunk.content

                    # ⭐ 新增：处理工具调用开始事件
                    elif 事件类型 == "on_tool_start":
                        工具名 = event.get("name", "")
                        工具参数 = event.get("data", {}).get("input", {})
                        logger.info(f"[飞书] Agent调用工具: {工具名}, 参数: {工具参数}")

                        # ⭐ 检测是否调用了飞书助手的发消息功能
                        if 工具名 == "飞书助手":
                            操作类型 = 工具参数.get("操作类型", "")
                            if 操作类型 == "发消息":
                                调用了飞书发送消息 = True
                                logger.info(f"[飞书] 检测到Agent调用飞书助手发送消息，将跳过自动回复")

                    # ⭐ 新增：处理工具调用结果事件
                    elif 事件类型 == "on_tool_end":
                        工具名 = event.get("name", "")
                        工具结果 = str(event.get("data", {}).get("output", ""))[:500]
                        logger.info(f"[飞书] 工具执行完成: {工具名}, 结果: {工具结果}")

                break

            except Exception as e:
                最后异常 = e
                错误信息 = str(e)
                可重试 = any(code in 错误信息 for code in ["403", "500", "429"])

                base_url = (agent配置.get("llm_api_url") or "").strip()
                api_key = (agent配置.get("llm_api_key") or "").strip()
                logger.warning(
                    "[飞书长连接] 智能体调用异常 (第%d次): %s\n"
                    "  base_url=%s\n"
                    "  api_key已配置=%s",
                    第几次+1, 错误信息, base_url, "是" if api_key else "否"
                )

                if 可重试 and 第几次 < 最大重试:
                    等待秒 = 2 ** (第几次 + 1)
                    logger.info("[飞书长连接] 将在 %ds 后重试 (%d/%d)...", 等待秒, 第几次+1, 最大重试)
                    await asyncio.sleep(等待秒)
                    图 = 构建Agent图(agent配置, 工具记录列表=工具记录列表)
                    continue
                else:
                    raise

        # 6. 保存 assistant 消息
        if 完整回复.strip():
            保存消息(db, 对话id, "assistant", 完整回复, agent配置.get("name", ""))

            try:
                from app.图引擎.记忆管理 import 异步提取记忆
                loop = 获取飞书loop()
                asyncio.run_coroutine_threadsafe(异步提取记忆(agent配置, 对话id), loop)
            except Exception as e:
                logger.warning("[飞书长连接] 触发记忆提取失败（不影响回复）: %s", e)

        return (完整回复 or "（智能体未返回内容）", 调用了飞书发送消息)

    except Exception as e:
        错误信息 = str(e).lower()
        logger.error("[飞书长连接] 智能体最终失败: %s", 错误信息)

        if "verify your account" in 错误信息 or "verify_your_account" in 错误信息:
            return (
                "阿里云 DashScope 要求验证账号。\n"
                "请登录 dashscope.console.aliyun.com 完成实名认证后再试。"
            )
        if "llm 未配置" in 错误信息 or ("llm" in 错误信息 and "未配置" in 错误信息):
            return "当前飞书绑定的智能体未配置 LLM（接口地址/接口密钥）。请到『智能体管理』里补全后再试。"
        if any(kw in 错误信息 for kw in ["api key", "api_key", "no auth", "auth_unavailable", "unauthorized", "invalid_api_key"]):
            return "当前飞书绑定的智能体鉴权缺失或无效。请检查该智能体的接口密钥是否正确保存。"
        if "429" in 错误信息 or "rate" in 错误信息 or "too many" in 错误信息:
            return "AI 服务请求过于频繁，请稍后再试。"
        if "connection" in 错误信息 or "timeout" in 错误信息:
            return "抱歉，AI 服务暂时无法连接，请稍后再试。"
        if "403" in 错误信息 or "500" in 错误信息:
            return (
                f"AI 服务持续返回错误（已重试{最大重试}次）。\n"
                f"请检查 DashScope 账号状态和余额，或稍后再试。\n"
                f"错误详情: {str(e)[:150]}"
            )
        return f"执行失败: {str(e)[:200]}"
    finally:
        db.close()


def 同步调用智能体(agent配置: dict, 用户消息: str, 对话id: str) -> tuple[str, bool]:
    """用共享 event loop 执行异步智能体调用。

    Returns:
        tuple[str, bool]: (回复文本, 是否调用了飞书发送消息工具)
    """
    logger.info(f"[飞书调试-同步] 进入同步调用智能体，消息: {用户消息[:50]}")
    loop = 获取飞书loop()
    future = asyncio.run_coroutine_threadsafe(
        调用智能体(agent配置, 用户消息, 对话id),
        loop
    )
    回复, 调用了飞书工具 = future.result(timeout=FEISHU_AGENT_TIMEOUT)
    logger.info(f"[飞书调试-同步] 同步调用完成，回复长度: {len(回复)}, 调用了飞书工具: {调用了飞书工具}")
    return 回复, 调用了飞书工具
