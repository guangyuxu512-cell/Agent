# app/图引擎/记忆管理.py
# Step 6：记忆提取 + 查询
#
# 功能：
# 1. 对话结束后，用 LLM 提取关键记忆
# 2. 新对话开始时，查询相关记忆注入上下文

import json
import logging
from uuid import uuid4
from datetime import datetime

logger = logging.getLogger(__name__)

from app.db.数据库 import 会话工厂
from app.db.模型 import 记忆模型, 消息模型
from app.配置 import 环境变量
from app.常量 import (
    CONVERSATION_TEXT_MAX_LEN, LLM_HTTP_TIMEOUT,
    MEMORY_EXTRACTION_TEMPERATURE, MEMORY_EXTRACTION_MAX_TOKENS,
    MEMORY_DEFAULT_LIMIT, MEMORY_SUMMARY_LIMIT,
)


# ==================== 记忆提取（对话结束后调用） ====================

记忆提取提示词 = """你是一个记忆提取助手。请分析以下对话，提取需要长期记住的信息。

要求：
1. 提取用户的偏好、习惯、重要信息
2. 生成一句话总结本次对话的主题
3. 忽略闲聊和无意义的内容
4. 用 JSON 格式返回

返回格式（严格 JSON，不要 markdown 代码块）：
{"summary": "对话摘要（一句话）", "memories": [{"type": "preference|fact", "content": "记忆内容", "importance": 0.1到1.0}]}

如果没有值得记忆的内容，返回：
{"summary": "对话摘要", "memories": []}
"""


async def 异步提取记忆(agent配置: dict, 对话id: str):
    """
    对话结束后异步调用。
    从对话历史中提取记忆，存入 memories 表。
    失败不影响任何功能。
    """
    db = 会话工厂()
    try:
        # 1. 获取对话消息
        消息们 = (
            db.query(消息模型)
            .filter(消息模型.对话id == 对话id)
            .order_by(消息模型.创建时间)
            .all()
        )

        # 少于 3 轮对话不提取
        用户消息数 = sum(1 for m in 消息们 if m.角色 == "user")
        if 用户消息数 < 3:
            return

        # 2. 拼接对话文本
        对话文本 = ""
        for msg in 消息们:
            角色标签 = "用户" if msg.角色 == "user" else "助手"
            对话文本 += f"{角色标签}: {msg.内容}\n"

        # 截断过长的对话（防止 token 超限）
        if len(对话文本) > CONVERSATION_TEXT_MAX_LEN:
            对话文本 = 对话文本[:CONVERSATION_TEXT_MAX_LEN] + "\n...（对话过长已截断）"

        # 3. 调用 LLM 提取记忆
        import httpx

        接口地址 = (agent配置.get("llm_api_url") or "").strip()
        接口密钥 = (agent配置.get("llm_api_key") or "").strip()
        模型名称 = agent配置.get("model", "gpt-4o-mini")

        if not 接口地址 or not 接口密钥:
            logger.info("[记忆] 当前智能体未配置 llm_api_url/llm_api_key，跳过记忆提取")
            return

        async with httpx.AsyncClient(timeout=LLM_HTTP_TIMEOUT) as client:
            响应 = await client.post(
                f"{接口地址.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {接口密钥}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": 模型名称,
                    "messages": [
                        {"role": "system", "content": 记忆提取提示词},
                        {"role": "user", "content": f"以下是对话内容：\n\n{对话文本}"},
                    ],
                    "temperature": MEMORY_EXTRACTION_TEMPERATURE,
                    "max_tokens": MEMORY_EXTRACTION_MAX_TOKENS,
                },
            )

        if 响应.status_code != 200:
            logger.warning("[记忆] LLM 调用失败: HTTP %d", 响应.status_code)
            return

        结果文本 = 响应.json()["choices"][0]["message"]["content"].strip()

        # 兼容 LLM 返回 ```json ... ``` 格式
        if 结果文本.startswith("```"):
            结果文本 = 结果文本.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        结果 = json.loads(结果文本)

        # 4. 保存对话摘要
        摘要 = 结果.get("summary", "")
        if 摘要:
            摘要记忆 = 记忆模型(
                id=str(uuid4()),
                agent_id=agent配置["id"],
                conversation_id=对话id,
                记忆类型="summary",
                内容=摘要,
                重要性=0.5,
            )
            db.add(摘要记忆)

        # 5. 保存提取的记忆
        for 记忆 in 结果.get("memories", []):
            内容 = 记忆.get("content", "").strip()
            if not 内容:
                continue

            # 去重：如果已有相同内容的记忆，跳过
            已存在 = (
                db.query(记忆模型)
                .filter(
                    记忆模型.agent_id == agent配置["id"],
                    记忆模型.内容 == 内容,
                )
                .first()
            )
            if 已存在:
                continue

            新记忆 = 记忆模型(
                id=str(uuid4()),
                agent_id=agent配置["id"],
                conversation_id=对话id,
                记忆类型=记忆.get("type", "fact"),
                内容=内容,
                重要性=min(max(float(记忆.get("importance", 0.5)), 0.1), 1.0),
            )
            db.add(新记忆)

        db.commit()
        记忆数量 = len(结果.get("memories", []))
        logger.info("[记忆] 提取完成: 摘要=%s, 记忆 %d 条", '有' if 摘要 else '无', 记忆数量)

    except json.JSONDecodeError as e:
        logger.warning("[记忆] LLM 返回格式解析失败: %s", e)
    except Exception as e:
        logger.warning("[记忆] 提取异常（不影响对话）: %s", e)
    finally:
        db.close()


# ==================== 记忆查询（新对话开始时调用） ====================

def 获取Agent记忆(agent_id: str, 最大条数: int = MEMORY_DEFAULT_LIMIT) -> str:
    """
    查询 Agent 的长期记忆，返回格式化的文本。
    按重要性降序，返回最近且最重要的记忆。
    未找到则返回空字符串。
    """
    db = 会话工厂()
    try:
        记忆们 = (
            db.query(记忆模型)
            .filter(
                记忆模型.agent_id == agent_id,
                # 排除已过期的记忆
                (记忆模型.过期时间.is_(None)) | (记忆模型.过期时间 > datetime.now()),
            )
            .order_by(记忆模型.重要性.desc(), 记忆模型.创建时间.desc())
            .limit(最大条数)
            .all()
        )

        if not 记忆们:
            return ""

        偏好和事实 = []
        摘要列表 = []

        for 记忆 in 记忆们:
            if 记忆.记忆类型 == "summary":
                摘要列表.append(f"- {记忆.内容}")
            else:
                标签 = "偏好" if 记忆.记忆类型 == "preference" else "事实"
                偏好和事实.append(f"- [{标签}] {记忆.内容}")

        结果 = ""
        if 偏好和事实:
            结果 += "用户相关信息：\n" + "\n".join(偏好和事实)
        if 摘要列表:
            if 结果:
                结果 += "\n\n"
            # 只保留最近 5 条摘要
            结果 += "近期对话摘要：\n" + "\n".join(摘要列表[:5])

        return 结果

    except Exception as e:
        logger.warning("[记忆] 查询异常: %s", e)
        return ""
    finally:
        db.close()