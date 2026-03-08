# app/api/对话.py
# Step 6 完整版（基于服务器实际代码 + agent_id 过滤修复）
# 功能：对话 CRUD + SSE 流式 + 工具事件 + 来源标记 + 记忆提取

import json
import asyncio
import logging
from uuid import uuid4
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import desc, func as sa_func
from sqlalchemy.orm import Session

from app.db.数据库 import 获取数据库, 会话工厂
from app.db.模型 import Agent模型, 对话模型, 消息模型, 工具模型, 编排模型
from app.加密 import 解密
from app.常量 import TOOL_RESULT_MAX_LEN, CONV_TITLE_MAX_LEN

logger = logging.getLogger(__name__)
from app.图引擎.构建器 import 构建Agent图
from app.图引擎.多Agent构建器 import 构建多Agent图
from app.图引擎.上下文 import 组装上下文


对话路由 = APIRouter(tags=["对话"])


# ==================== 请求模型 ====================

class 发送消息请求(BaseModel):
    agent_id: str
    conversation_id: Optional[str] = None
    message: str


# ==================== 辅助函数 ====================

def 获取Agent字典(db: Session, agent_id: str) -> Optional[dict]:
    """从数据库读取 Agent 配置，转成字典（字段名与构建器.py/上下文.py 一致）

    ⭐ Step 4 改动：
      - 新增 description 字段（构建器.py 用它做角色描述）
      - 新增 tools 字段（获取Agent工具记录 用它查工具 ID 列表）
    """
    agent = db.query(Agent模型).filter(Agent模型.id == agent_id).first()
    if not agent:
        return None
    return agent.to_config_dict(解密函数=解密)


def 获取历史消息(db: Session, 对话id: str) -> list:
    """获取某个对话的所有历史消息"""
    消息们 = (
        db.query(消息模型)
        .filter(消息模型.对话id == 对话id)
        .order_by(消息模型.创建时间)
        .all()
    )
    return [
        {"role": msg.角色, "content": msg.内容, "agent_name": msg.agent名称}
        for msg in 消息们
    ]


def 保存消息(db: Session, 对话id: str, 角色: str, 内容: str, agent名称: str = ""):
    """保存一条消息到数据库"""
    新消息 = 消息模型(
        id=str(uuid4()),
        对话id=对话id,
        角色=角色,
        内容=内容,
        agent名称=agent名称,
    )
    db.add(新消息)
    db.commit()
    return 新消息


def 更新对话时间(db: Session, 对话id: str):
    """更新对话的 updated_at"""
    对话 = db.query(对话模型).filter(对话模型.id == 对话id).first()
    if 对话:
        对话.更新时间 = sa_func.now()
        db.commit()


# ==================== ⭐ Step 4 新增：获取 Agent 绑定的工具记录 ====================

def 获取Agent工具记录(db: Session, agent配置: dict) -> list:
    """根据 Agent 的 tools 字段（JSON 数组），从 DB 查询激活状态的工具详情

    ⭐ 修复：支持按工具名称或工具ID查询（兼容历史数据）
    """
    工具标识原始 = agent配置.get("tools", [])
    logger.info(f"[对话] Agent工具标识原始: {工具标识原始}")

    if isinstance(工具标识原始, str):
        try:
            工具标识列表 = json.loads(工具标识原始)
        except (json.JSONDecodeError, TypeError):
            工具标识列表 = []
    else:
        工具标识列表 = 工具标识原始 or []

    logger.info(f"[对话] Agent工具标识列表: {工具标识列表}")

    if not 工具标识列表:
        logger.warning(f"[对话] Agent工具列表为空")
        return []

    # ⭐ 修复：同时支持按名称和按ID查询（兼容历史数据）
    工具记录 = db.query(工具模型).filter(
        (工具模型.名称.in_(工具标识列表)) | (工具模型.id.in_(工具标识列表)),
        工具模型.状态 == "active"
    ).all()

    logger.info(f"[对话] 查询到 {len(工具记录)} 个工具记录: {[t.名称 for t in 工具记录]}")

    return [
        {
            "name": t.名称,
            "description": t.描述,
            "tool_type": t.类型,
            "parameters": t.参数定义,
            "config": t.配置,
        }
        for t in 工具记录
    ]


# ==================== SSE 生成器 ====================

async def SSE生成器(agent配置: dict, 消息列表: list, 对话id: str):
    """
    LangGraph 流式执行，逐 token 通过 SSE 推送给前端。

    SSE 事件类型：
    - conversation_id: 返回对话 ID（前端绑定用）
    - agent: 当前回复的 Agent 名称
    - token: 单个 token
    - tool_call: 工具调用开始
    - tool_result: 工具调用结果
    - done: 完整回复内容
    - error: 错误信息
    """
    完整回复 = ""
    db = 会话工厂()

    try:
        # 返回 conversation_id
        yield f"data: {json.dumps({'type': 'conversation_id', 'content': 对话id}, ensure_ascii=False)}\n\n"

        # 返回 agent 名称
        yield f"data: {json.dumps({'type': 'agent', 'name': agent配置.get('name', '助手')}, ensure_ascii=False)}\n\n"
        # 加载工具记录，传给构建Agent图
        工具记录列表 = 获取Agent工具记录(db, agent配置)

        图 = 构建Agent图(agent配置, 工具记录列表=工具记录列表)

        # 流式执行 - 添加详细异常捕获
        try:
            logger.info(f"[SSE] 开始调用 astream_events，消息列表长度: {len(消息列表)}")

            async for event in 图.astream_events(
                {"messages": 消息列表},
                version="v2",
            ):
                事件类型 = event.get("event", "")

                # 捕获 LLM 逐 token 输出
                if 事件类型 == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token = chunk.content
                        完整回复 += token
                        yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

                # 工具调用开始事件
                elif 事件类型 == "on_tool_start":
                    工具名 = event.get("name", "")
                    工具参数 = event.get("data", {}).get("input", {})
                    yield f"data: {json.dumps({'type': 'tool_call', 'name': 工具名, 'args': 工具参数}, ensure_ascii=False)}\n\n"

                # 工具调用结果事件
                elif 事件类型 == "on_tool_end":
                    工具名 = event.get("name", "")
                    工具结果 = str(event.get("data", {}).get("output", ""))[:TOOL_RESULT_MAX_LEN]
                    yield f"data: {json.dumps({'type': 'tool_result', 'name': 工具名, 'result': 工具结果}, ensure_ascii=False)}\n\n"
        except TypeError as type_error:
            import traceback
            import sys
            错误堆栈 = traceback.format_exc()

            # 获取详细的调用栈信息
            tb = sys.exc_info()[2]
            stack_summary = traceback.extract_tb(tb)

            详细信息 = f"[SSE] TypeError 异常详情:\n"
            详细信息 += f"错误消息: {str(type_error)}\n"
            详细信息 += f"完整堆栈:\n{错误堆栈}\n"
            详细信息 += f"\n调用栈详情:\n"
            for frame in stack_summary:
                详细信息 += f"  文件: {frame.filename}:{frame.lineno}\n"
                详细信息 += f"  函数: {frame.name}\n"
                详细信息 += f"  代码: {frame.line}\n"

            logger.error(详细信息)
            # 强制刷新日志
            for handler in logger.handlers:
                handler.flush()
            # 同时输出到 stderr
            print(详细信息, file=sys.stderr, flush=True)

            yield f"data: {json.dumps({'type': 'error', 'content': f'类型错误 (by_alias): {str(type_error)}'}, ensure_ascii=False)}\n\n"
            raise
        except Exception as stream_error:
            import traceback
            错误堆栈 = traceback.format_exc()
            logger.error(f"[SSE] astream_events 异常:\n{错误堆栈}")
            yield f"data: {json.dumps({'type': 'error', 'content': f'流式执行错误: {str(stream_error)}'}, ensure_ascii=False)}\n\n"
            raise  # 重新抛出以便外层捕获

        # 流式完成
        yield f"data: {json.dumps({'type': 'done', 'content': 完整回复}, ensure_ascii=False)}\n\n"

        # 保存 assistant 消息到数据库
        if 完整回复.strip():
            保存消息(db, 对话id, "assistant", 完整回复, agent配置.get("name", ""))
            更新对话时间(db, 对话id)

            # ⭐ Step 6：异步触发记忆提取（不阻塞 SSE）
            try:
                from app.图引擎.记忆管理 import 异步提取记忆
                asyncio.create_task(异步提取记忆(agent配置, 对话id))
            except Exception as e:
                logger.warning("[记忆] 触发记忆提取失败（不影响对话）: %s", e)

    except Exception as e:
        import traceback
        错误堆栈 = traceback.format_exc()
        logger.error(f"[SSE] SSE生成器异常（完整堆栈）:\n{错误堆栈}")

        错误信息 = str(e)
        # 友好化常见错误
        if "API key" in 错误信息.lower() or "api_key" in 错误信息.lower():
            错误信息 = "LLM API Key 无效或未配置。请检查 Agent 设置或 .env 文件中的 OPENAI_API_KEY"
        elif "connection" in 错误信息.lower() or "timeout" in 错误信息.lower():
            错误信息 = f"LLM 服务连接失败，请检查网络或 API 地址配置。原始错误：{str(e)}"
        else:
            # 对于其他错误，包含完整堆栈信息
            错误信息 = f"{错误信息}\n\n完整堆栈已记录到后端日志"

        yield f"data: {json.dumps({'type': 'error', 'content': 错误信息}, ensure_ascii=False)}\n\n"

    finally:
        db.close()


# ==================== 多 Agent SSE 生成器 ====================

async def 多Agent_SSE生成器(编排配置: dict, agents配置列表: list, 工具记录映射: dict, 消息列表: list, 对话id: str):
    """
    多 Agent 协作的 SSE 流式执行。
    """
    yield f"data: {json.dumps({'type': 'conversation_id', 'content': 对话id}, ensure_ascii=False)}\n\n"
    yield f"data: {json.dumps({'type': 'agent', 'name': '多Agent协作'}, ensure_ascii=False)}\n\n"

    完整回复 = ""
    当前agent = ""
    db = 会话工厂()

    try:
        图 = 构建多Agent图(编排配置, agents配置列表, 工具记录映射)

        logger.info(f"[多Agent] 开始执行多Agent图，消息列表长度: {len(消息列表)}")

        async for event in 图.astream_events(
            {"messages": 消息列表},
            version="v2",
        ):
            事件类型 = event.get("event", "")
            节点名 = event.get("metadata", {}).get("langgraph_node", "")

            # 调试：打印所有事件
            if 节点名 == "supervisor":
                logger.info(f"[多Agent-Supervisor] 事件类型: {事件类型}")

            if 事件类型 == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    # 检测 agent 切换
                    agent名 = event.get("metadata", {}).get("langgraph_node", "")
                    if agent名 and agent名 != 当前agent:
                        当前agent = agent名
                        logger.info(f"[多Agent] Agent切换: {当前agent}")
                        yield f"data: {json.dumps({'type': 'agent', 'name': 当前agent}, ensure_ascii=False)}\n\n"

                    token = chunk.content
                    完整回复 += token
                    yield f"data: {json.dumps({'type': 'token', 'content': token}, ensure_ascii=False)}\n\n"

            # 捕获 Supervisor 的完整输出
            elif 事件类型 == "on_chat_model_end":
                if 节点名 == "supervisor":
                    output = event.get("data", {}).get("output", {})
                    logger.info(f"[多Agent-Supervisor] LLM输出类型: {type(output)}")
                    logger.info(f"[多Agent-Supervisor] LLM输出内容: {output}")

                    # 检查是否有 tool_calls
                    if hasattr(output, "tool_calls"):
                        logger.info(f"[多Agent-Supervisor] tool_calls: {output.tool_calls}")
                        if not output.tool_calls:
                            logger.warning(f"[多Agent-Supervisor] ⚠️ tool_calls 为空！Supervisor 没有调用任何工具")
                    elif hasattr(output, "additional_kwargs"):
                        tool_calls = output.additional_kwargs.get("tool_calls", [])
                        logger.info(f"[多Agent-Supervisor] additional_kwargs.tool_calls: {tool_calls}")
                        if not tool_calls:
                            logger.warning(f"[多Agent-Supervisor] ⚠️ tool_calls 为空！Supervisor 没有调用任何工具")
                    else:
                        logger.warning(f"[多Agent-Supervisor] ⚠️ 输出中没有 tool_calls 字段")

                    # 打印内容
                    if hasattr(output, "content"):
                        logger.info(f"[多Agent-Supervisor] 内容: {output.content[:200]}")

            elif 事件类型 == "on_tool_start":
                工具名 = event.get("name", "")
                工具参数 = event.get("data", {}).get("input", {})
                logger.info(f"[多Agent] 工具调用开始: {工具名}, 参数: {工具参数}")
                yield f"data: {json.dumps({'type': 'tool_call', 'name': 工具名, 'args': 工具参数}, ensure_ascii=False)}\n\n"

            elif 事件类型 == "on_tool_end":
                工具名 = event.get("name", "")
                工具结果 = str(event.get("data", {}).get("output", ""))[:TOOL_RESULT_MAX_LEN]
                logger.info(f"[多Agent] 工具调用结束: {工具名}, 结果长度: {len(工具结果)}")
                yield f"data: {json.dumps({'type': 'tool_result', 'name': 工具名, 'result': 工具结果}, ensure_ascii=False)}\n\n"

        logger.info(f"[多Agent] 执行完成，完整回复长度: {len(完整回复)}")
        yield f"data: {json.dumps({'type': 'done', 'content': 完整回复}, ensure_ascii=False)}\n\n"

        if 完整回复.strip():
            保存消息(db, 对话id, "assistant", 完整回复, 当前agent or "多Agent")
            更新对话时间(db, 对话id)

    except Exception as e:
        错误信息 = str(e)
        if "API key" in 错误信息.lower() or "api_key" in 错误信息.lower():
            错误信息 = "LLM API Key 无效或未配置。请检查 Agent 设置"
        elif "connection" in 错误信息.lower() or "timeout" in 错误信息.lower():
            错误信息 = f"LLM 服务连接失败: {str(e)}"
        yield f"data: {json.dumps({'type': 'error', 'content': 错误信息}, ensure_ascii=False)}\n\n"

    finally:
        db.close()


# ==================== 编排辅助 ====================

def 获取编排配置(db: Session) -> dict | None:
    """读取编排配置，如果没有或只有单 Agent 模式则返回 None"""
    记录 = db.query(编排模型).filter(编排模型.id == "default").first()
    if not 记录 or not 记录.模式:
        return None
    return {
        "mode": 记录.模式,
        "entryAgent": 记录.入口agent_id or "",
        "routingRules": 记录.路由规则 or "",
        "parallelGroups": 记录.并行分组 or "",
        "globalState": json.loads(记录.全局状态 or "[]"),
    }


def 获取所有Agent配置和工具(db: Session) -> tuple[list[dict], dict[str, list]]:
    """获取所有 running 状态的 Agent 配置及其工具记录"""
    agents = db.query(Agent模型).filter(Agent模型.状态 == "running").all()
    agents配置列表 = []
    工具记录映射 = {}

    for agent in agents:
        配置 = agent.to_config_dict(解密函数=解密)
        agents配置列表.append(配置)
        工具记录映射[agent.id] = 获取Agent工具记录(db, 配置)

    return agents配置列表, 工具记录映射


# ==================== 接口定义 ====================

@对话路由.post("/api/chat")
async def 发送消息(请求体: 发送消息请求, db: Session = Depends(获取数据库)):
    """
    发送消息并获取 SSE 流式回复。

    - 没传 conversation_id → 自动新建对话
    - 没有 Agent → 返回 error 类型 SSE
    """
    # 1. 检查 Agent 是否存在
    agent配置 = 获取Agent字典(db, 请求体.agent_id)

    if not agent配置:
        agent数量 = db.query(Agent模型).count()
        if agent数量 == 0:
            async def 无Agent错误():
                yield f"data: {json.dumps({'type': 'error', 'content': '没有可用的 Agent，请先到智能体管理页创建一个智能体'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(无Agent错误(), media_type="text/event-stream")
        else:
            async def Agent不存在错误():
                yield f"data: {json.dumps({'type': 'error', 'content': f'Agent {请求体.agent_id} 不存在'}, ensure_ascii=False)}\n\n"
            return StreamingResponse(Agent不存在错误(), media_type="text/event-stream")

    # 2. 获取或创建对话
    对话id = 请求体.conversation_id
    if not 对话id:
        对话id = str(uuid4())
        标题 = 请求体.message[:CONV_TITLE_MAX_LEN].strip() or "新对话"
        新对话 = 对话模型(
            id=对话id,
            agent_id=请求体.agent_id,
            标题=标题,
            来源="web",
        )
        db.add(新对话)
        db.commit()
    else:
        已有对话 = db.query(对话模型).filter(对话模型.id == 对话id).first()
        if not 已有对话:
            标题 = 请求体.message[:CONV_TITLE_MAX_LEN].strip() or "新对话"
            新对话 = 对话模型(
                id=对话id,
                agent_id=请求体.agent_id,
                标题=标题,
                来源="web",
            )
            db.add(新对话)
            db.commit()

    # 3. 保存用户消息
    保存消息(db, 对话id, "user", 请求体.message)

    # 4. 获取历史消息
    历史 = 获取历史消息(db, 对话id)
    历史 = 历史[:-1] if 历史 else []   # 排除刚保存的当前消息

    # 5. 组装上下文（Step 5 改为 async）
    消息列表 = await 组装上下文(
        agent配置=agent配置,
        历史消息=历史,
        用户消息=请求体.message,
    )

    # 6. 检查编排配置，决定单 Agent 还是多 Agent
    编排 = 获取编排配置(db)
    if 编排:
        agents配置列表, 工具记录映射 = 获取所有Agent配置和工具(db)
        # 至少 2 个 running 的 Agent 才走多 Agent 模式
        if len(agents配置列表) >= 2:
            return StreamingResponse(
                多Agent_SSE生成器(编排, agents配置列表, 工具记录映射, 消息列表, 对话id),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

    # 7. 单 Agent 模式 — 返回 SSE 流
    return StreamingResponse(
        SSE生成器(agent配置, 消息列表, 对话id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@对话路由.get("/api/conversations")
async def 获取对话列表(
    page: int = 1,
    page_size: int = 20,
    agent_id: str = None,
    db: Session = Depends(获取数据库),
):
    """获取对话列表，按 updated_at 倒序。支持按 agent_id 过滤。"""
    # ⭐ 修复：加 agent_id 过滤（你服务器上漏了这一步）
    查询 = db.query(对话模型)

    if agent_id:
        查询 = 查询.filter(对话模型.agent_id == agent_id)

    总数 = 查询.count()

    对话们 = (
        查询
        .order_by(desc(对话模型.更新时间))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 批量查询 Agent 名称（避免 N+1）
    agent_ids = list({对话.agent_id for 对话 in 对话们 if 对话.agent_id})
    agent名称映射 = {}
    if agent_ids:
        agents = db.query(Agent模型.id, Agent模型.名称).filter(Agent模型.id.in_(agent_ids)).all()
        agent名称映射 = {a.id: a.名称 for a in agents}

    # 批量查询消息数（避免 N+1）
    对话ids = [对话.id for 对话 in 对话们]
    消息数映射 = {}
    if 对话ids:
        消息统计 = (
            db.query(消息模型.对话id, sa_func.count(消息模型.id))
            .filter(消息模型.对话id.in_(对话ids))
            .group_by(消息模型.对话id)
            .all()
        )
        消息数映射 = {行[0]: 行[1] for 行 in 消息统计}

    列表数据 = []
    for 对话 in 对话们:
        列表数据.append({
            "id": 对话.id,
            "agent_id": 对话.agent_id,
            "agent_name": agent名称映射.get(对话.agent_id, "未知Agent"),
            "title": 对话.标题,
            "source": getattr(对话, '来源', 'web') or 'web',
            "message_count": 消息数映射.get(对话.id, 0),
            "created_at": 对话.创建时间.strftime("%Y-%m-%d %H:%M:%S") if 对话.创建时间 else "",
            "updated_at": 对话.更新时间.strftime("%Y-%m-%d %H:%M:%S") if 对话.更新时间 else "",
        })

    return {
        "code": 0,
        "data": {
            "list": 列表数据,
            "total": 总数,
            "page": page,
            "page_size": page_size,
        },
        "msg": "ok",
    }


@对话路由.get("/api/conversations/{conversation_id}/messages")
async def 获取消息列表(
    conversation_id: str,
    db: Session = Depends(获取数据库),
):
    """获取某个对话的所有消息，按 created_at 正序。"""
    对话 = db.query(对话模型).filter(对话模型.id == conversation_id).first()
    if not 对话:
        return {"code": 1, "data": None, "msg": "对话不存在"}

    消息们 = (
        db.query(消息模型)
        .filter(消息模型.对话id == conversation_id)
        .order_by(消息模型.创建时间)
        .all()
    )

    消息数据 = [
        {
            "id": msg.id,
            "role": msg.角色,
            "content": msg.内容,
            "agent_name": msg.agent名称 or "",
            "created_at": msg.创建时间.strftime("%Y-%m-%d %H:%M:%S") if msg.创建时间 else "",
        }
        for msg in 消息们
    ]

    return {"code": 0, "data": 消息数据, "msg": "ok"}


@对话路由.delete("/api/conversations/{conversation_id}")
async def 删除对话(
    conversation_id: str,
    db: Session = Depends(获取数据库),
):
    """删除对话及其所有消息"""
    db.query(消息模型).filter(消息模型.对话id == conversation_id).delete()
    db.query(对话模型).filter(对话模型.id == conversation_id).delete()
    db.commit()
    return {"code": 0, "data": None, "msg": "ok"}