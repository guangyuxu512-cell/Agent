# app/飞书/配置与会话.py
# 飞书长连接：配置读取、会话管理、共享 Event Loop

import asyncio
import json
import logging
import time
import threading
from uuid import uuid4

from app.db.数据库 import 会话工厂
from app.db.模型 import 系统配置模型, Agent模型, 对话模型, 消息模型, 工具模型
from app.加密 import 解密
from app.常量 import FEISHU_SESSION_TIMEOUT, FEISHU_DEDUP_LIMIT

logger = logging.getLogger(__name__)


# ==================== 状态管理 ====================

_已处理消息 = set()
_消息锁 = threading.Lock()
_用户会话 = {}
_会话锁 = threading.Lock()  # ⭐ 新增：会话管理锁
_会话超时秒 = FEISHU_SESSION_TIMEOUT
_已处理消息上限 = FEISHU_DEDUP_LIMIT


# ==================== 共享 Event Loop ====================

_飞书loop = None
_飞书loop锁 = threading.Lock()


def 获取飞书loop():
    """获取共享的 event loop（线程安全），首次调用时创建并启动"""
    global _飞书loop
    with _飞书loop锁:
        if _飞书loop is None or _飞书loop.is_closed():
            _飞书loop = asyncio.new_event_loop()
            t = threading.Thread(target=_飞书loop.run_forever, daemon=True)
            t.start()
    return _飞书loop


# ==================== 配置读取 ====================

def 读取飞书配置() -> dict:
    """从 system_config 表读取 feishu 分类配置"""
    db = 会话工厂()
    try:
        record = (
            db.query(系统配置模型)
            .filter(系统配置模型.分类 == "feishu", 系统配置模型.键 == "__data__")
            .first()
        )
        if record and record.值:
            return json.loads(record.值)
        return {}
    except Exception as e:
        logger.error("[飞书长连接] 读取配置异常: %s", e)
        return {}
    finally:
        db.close()


def 获取Agent配置(agent_id: str) -> dict | None:
    """从数据库读取 Agent 配置，转成字典"""
    db = 会话工厂()
    try:
        agent = db.query(Agent模型).filter(Agent模型.id == agent_id).first()
        if not agent:
            return None
        return agent.to_config_dict(解密函数=解密)
    finally:
        db.close()


def 获取Agent工具记录(db, agent配置: dict) -> list:
    """获取 Agent 绑定的工具

    ⭐ 修复：支持按工具名称或工具ID查询（兼容历史数据，与Web端对齐）
    """
    工具标识原始 = agent配置.get("tools", [])

    logger.info(f"[飞书] Agent工具标识原始: {工具标识原始}")

    if isinstance(工具标识原始, str):
        try:
            工具标识列表 = json.loads(工具标识原始)
        except (json.JSONDecodeError, TypeError):
            工具标识列表 = []
    else:
        工具标识列表 = 工具标识原始 or []

    logger.info(f"[飞书] Agent工具标识列表: {工具标识列表}")

    if not 工具标识列表:
        logger.warning(f"[飞书] Agent工具列表为空")
        return []

    # ⭐ 修复：同时支持按名称和按ID查询（与Web端对齐）
    工具记录 = db.query(工具模型).filter(
        (工具模型.名称.in_(工具标识列表)) | (工具模型.id.in_(工具标识列表)),
        工具模型.状态 == "active"
    ).all()

    logger.info(f"[飞书] 查询到 {len(工具记录)} 个工具记录: {[t.名称 for t in 工具记录]}")

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


# ==================== 对话管理 ====================

def 获取或创建对话(db, agent_id: str, open_id: str, 首条消息: str) -> str:
    """
    根据 open_id 获取或创建对话。
    超过 30 分钟没活跃 → 创建新对话。
    ⭐ 修复：添加线程锁，防止并发创建多个对话
    """
    当前时间 = time.time()

    # ⭐ 使用锁保护整个查找和创建过程
    with _会话锁:
        logger.info(f"[飞书会话] 查找会话: open_id={open_id[:8]}..., 当前缓存数量={len(_用户会话)}")

        if open_id in _用户会话:
            会话 = _用户会话[open_id]
            会话年龄 = 当前时间 - 会话["最后活跃"]
            logger.info(f"[飞书会话] 找到缓存会话: 对话id={会话['对话id'][:8]}..., 年龄={会话年龄:.1f}秒")

            if 会话年龄 < _会话超时秒:
                会话["最后活跃"] = 当前时间
                logger.info(f"[飞书会话] 复用会话: open_id={open_id[:8]}..., 对话id={会话['对话id'][:8]}...")
                return 会话["对话id"]
            else:
                logger.info(f"[飞书会话] 会话已超时({会话年龄:.1f}秒 > {_会话超时秒}秒)，将创建新会话")

        # 创建新对话
        对话id = str(uuid4())
        标题 = f"飞书: {首条消息[:15]}" if 首条消息 else "飞书对话"
        logger.info(f"[飞书会话] 创建新会话: open_id={open_id[:8]}..., 对话id={对话id[:8]}..., 标题={标题}")

        新对话 = 对话模型(
            id=对话id,
            agent_id=agent_id,
            标题=标题,
            来源="feishu",
        )
        db.add(新对话)
        db.commit()

        _用户会话[open_id] = {"对话id": 对话id, "最后活跃": 当前时间}
        logger.info("[飞书长连接] 为用户 %s... 创建新对话 %s...", open_id[:8], 对话id[:8])
        return 对话id


def 保存消息(db, 对话id: str, 角色: str, 内容: str, agent名称: str = ""):
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


def 获取历史消息(db, 对话id: str) -> list:
    """获取对话历史"""
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


# ==================== 去重辅助 ====================

def 检查消息去重(消息ID: str) -> bool:
    """检查消息是否已处理过。返回 True 表示重复，应跳过。"""
    with _消息锁:
        是否重复 = 消息ID in _已处理消息
        logger.info(f"[飞书] 消息去重检查: message_id={消息ID}, 是否重复={是否重复}, 已处理数量={len(_已处理消息)}")
        if 是否重复:
            return True
        _已处理消息.add(消息ID)
        if len(_已处理消息) > _已处理消息上限:
            logger.warning(f"[飞书] 去重缓存已满({len(_已处理消息)})，清空缓存")
            _已处理消息.clear()
    return False
