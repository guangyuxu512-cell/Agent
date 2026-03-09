import asyncio
import json
import logging
import time
from datetime import datetime
from uuid import uuid4

from app.db.数据库 import 会话工厂
from app.db.模型 import 定时任务模型, 任务记录模型, Agent模型, 工具模型, 任务派发模型
from app.加密 import 解密
from app.常量 import SCHEDULER_RESULT_MAX_LEN, SCHEDULER_ERROR_MAX_LEN
from app.services.dispatch_records import 更新任务派发状态

logger = logging.getLogger(__name__)


async def _执行定时任务异步(schedule_id: str, dispatch_id: str | None = None, retry_count: int = 0):
    db = 会话工厂()
    开始时间 = time.time()
    日志记录 = None

    try:
        任务 = db.query(定时任务模型).filter(定时任务模型.id == schedule_id).first()
        if not 任务:
            更新任务派发状态(db, dispatch_id, "failed", retry_count, f"定时任务不存在: {schedule_id}")
            db.commit()
            logger.error("[Celery] 定时任务不存在: %s", schedule_id)
            return {"ok": False, "error": "schedule_not_found"}

        logger.info("[Celery] 开始执行定时任务: %s (%s)", 任务.名称, schedule_id)
        更新任务派发状态(db, dispatch_id, "running", retry_count)

        日志记录 = 任务记录模型(
            id=str(uuid4()),
            schedule_id=schedule_id,
            状态="running",
            开始时间=datetime.now(),
        )
        db.add(日志记录)
        db.commit()

        agent = db.query(Agent模型).filter(Agent模型.id == 任务.agent_id).first()
        if not agent:
            raise ValueError(f"Agent 不存在: {任务.agent_id}")

        agent配置 = agent.to_config_dict(解密函数=解密)

        工具ID原始 = agent配置.get("tools", [])
        if isinstance(工具ID原始, str):
            try:
                工具ID列表 = json.loads(工具ID原始)
            except (json.JSONDecodeError, TypeError):
                工具ID列表 = []
        else:
            工具ID列表 = 工具ID原始 or []

        工具记录列表 = []
        if 工具ID列表:
            工具记录 = db.query(工具模型).filter(
                工具模型.id.in_(工具ID列表),
                工具模型.状态 == "active"
            ).all()
            工具记录列表 = [
                {
                    "name": t.名称,
                    "description": t.描述,
                    "tool_type": t.类型,
                    "parameters": t.参数定义,
                    "config": t.配置,
                }
                for t in 工具记录
            ]

        from app.图引擎.构建器 import 构建Agent图

        图 = 构建Agent图(agent配置, 工具记录列表=工具记录列表)

        输入消息 = 任务.提示词 or "请执行任务"
        结果 = await 图.ainvoke({"messages": [{"role": "user", "content": 输入消息}]})

        最终回复 = ""
        if "messages" in 结果:
            for msg in reversed(结果["messages"]):
                if hasattr(msg, "content") and msg.content:
                    最终回复 = msg.content if isinstance(msg.content, str) else str(msg.content)
                    break

        耗时 = time.time() - 开始时间
        日志记录.状态 = "success"
        日志记录.结果 = 最终回复[:SCHEDULER_RESULT_MAX_LEN]
        日志记录.结束时间 = datetime.now()
        任务.上次运行 = datetime.now()
        更新任务派发状态(db, dispatch_id, "success", retry_count)
        db.commit()

        logger.info("[Celery] 定时任务执行成功: %s (耗时 %.1fs)", 任务.名称, 耗时)
        return {"ok": True, "result": 最终回复}

    except Exception as e:
        logger.error("[Celery] 定时任务执行失败 %s: %s", schedule_id, e, exc_info=True)
        if 日志记录:
            日志记录.状态 = "failed"
            日志记录.错误 = str(e)[:SCHEDULER_ERROR_MAX_LEN]
            日志记录.结束时间 = datetime.now()
        更新任务派发状态(db, dispatch_id, "failed", retry_count, str(e)[:SCHEDULER_ERROR_MAX_LEN])
        try:
            db.commit()
        except Exception:
            db.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


def 同步执行定时任务(schedule_id: str, dispatch_id: str | None = None, retry_count: int = 0):
    return asyncio.run(_执行定时任务异步(schedule_id, dispatch_id, retry_count))
