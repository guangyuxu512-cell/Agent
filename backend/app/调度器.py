# app/调度器.py
# APScheduler 封装 — 定时任务调度 + 执行逻辑

import json
import logging
import time
from uuid import uuid4
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.db.数据库 import 会话工厂
from app.db.模型 import 定时任务模型, 任务记录模型, Agent模型, 工具模型
from app.加密 import 解密
from app.常量 import SCHEDULER_MISFIRE_GRACE, SCHEDULER_RESULT_MAX_LEN, SCHEDULER_ERROR_MAX_LEN

logger = logging.getLogger(__name__)

# ========== 全局单例 ==========

调度器实例: AsyncIOScheduler | None = None


# ========== 生命周期 ==========

async def 启动调度器():
    global 调度器实例
    调度器实例 = AsyncIOScheduler(timezone="Asia/Shanghai")
    调度器实例.start()
    logger.info("[调度器] APScheduler 已启动")

    # 从数据库加载所有 enabled 的任务
    db = 会话工厂()
    try:
        任务列表 = db.query(定时任务模型).filter(定时任务模型.启用 == True).all()
        for 任务 in 任务列表:
            try:
                注册任务(任务)
                logger.info("[调度器] 已加载任务: %s (%s)", 任务.名称, 任务.id)
            except Exception as e:
                logger.error("[调度器] 加载任务失败 %s: %s", 任务.id, e)
        logger.info("[调度器] 已加载 %d 个定时任务", len(任务列表))
    finally:
        db.close()


async def 关闭调度器():
    global 调度器实例
    if 调度器实例:
        调度器实例.shutdown(wait=False)
        调度器实例 = None
        logger.info("[调度器] APScheduler 已关闭")


# ========== 任务注册 / 移除 ==========

def _解析触发器(任务: 定时任务模型):
    """根据 trigger_type + trigger_config 构建 APScheduler 触发器"""
    配置原始 = 任务.触发配置
    if isinstance(配置原始, str):
        try:
            配置 = json.loads(配置原始)
        except (json.JSONDecodeError, TypeError):
            配置 = {}
    else:
        配置 = 配置原始 or {}

    触发类型 = 任务.触发类型

    if 触发类型 == "cron":
        cron表达式 = 配置.get("cronExpression", "0 8 * * *")
        parts = cron表达式.strip().split()
        if len(parts) == 5:
            return CronTrigger(
                minute=parts[0], hour=parts[1],
                day=parts[2], month=parts[3], day_of_week=parts[4]
            )
        elif len(parts) == 6:
            return CronTrigger(
                second=parts[0], minute=parts[1], hour=parts[2],
                day=parts[3], month=parts[4], day_of_week=parts[5]
            )
        else:
            return CronTrigger(minute=parts[0], hour=parts[1],
                               day=parts[2], month=parts[3], day_of_week=parts[4])

    elif 触发类型 == "interval":
        值 = int(配置.get("intervalValue", 1))
        单位 = 配置.get("intervalUnit", "hours")
        if 单位 == "minutes":
            return IntervalTrigger(minutes=值)
        elif 单位 == "hours":
            return IntervalTrigger(hours=值)
        elif 单位 == "days":
            return IntervalTrigger(days=值)
        else:
            return IntervalTrigger(hours=值)

    elif 触发类型 == "once":
        执行时间 = 配置.get("executeTime", "")
        if 执行时间:
            return DateTrigger(run_date=datetime.strptime(执行时间, "%Y-%m-%d %H:%M:%S"))
        raise ValueError("once 模式缺少 executeTime")

    else:
        raise ValueError(f"不支持的触发类型: {触发类型}")


def 注册任务(任务: 定时任务模型):
    """向调度器注册一个定时任务"""
    if not 调度器实例:
        return

    job_id = f"schedule_{任务.id}"

    # 先移除旧的（幂等）
    existing = 调度器实例.get_job(job_id)
    if existing:
        调度器实例.remove_job(job_id)

    触发器 = _解析触发器(任务)
    调度器实例.add_job(
        执行定时任务,
        trigger=触发器,
        id=job_id,
        args=[任务.id],
        replace_existing=True,
        misfire_grace_time=SCHEDULER_MISFIRE_GRACE,
    )
    logger.info("[调度器] 注册任务: %s (type=%s)", 任务.名称, 任务.触发类型)


def 移除任务(schedule_id: str):
    """从调度器移除任务"""
    if not 调度器实例:
        return
    job_id = f"schedule_{schedule_id}"
    existing = 调度器实例.get_job(job_id)
    if existing:
        调度器实例.remove_job(job_id)
        logger.info("[调度器] 已移除任务: %s", schedule_id)


# ========== 任务执行 ==========

async def 执行定时任务(schedule_id: str):
    """
    实际执行逻辑：
    1. 从 DB 读取 schedule → 获取 agent_id + inputMessage
    2. 获取 Agent 配置 + 工具
    3. 构建 Agent 图，invoke（非流式）
    4. 写入 schedule_logs 记录
    5. 更新 schedule 的 last_run_at
    """
    db = 会话工厂()
    开始时间 = time.time()
    日志记录 = None

    try:
        # 1. 读取定时任务
        任务 = db.query(定时任务模型).filter(定时任务模型.id == schedule_id).first()
        if not 任务:
            logger.error("[调度器] 任务不存在: %s", schedule_id)
            return

        logger.info("[调度器] 开始执行任务: %s (%s)", 任务.名称, schedule_id)

        # 创建执行日志
        日志记录 = 任务记录模型(
            id=str(uuid4()),
            schedule_id=schedule_id,
            状态="running",
            开始时间=datetime.now(),
        )
        db.add(日志记录)
        db.commit()

        # 2. 获取 Agent 配置
        agent = db.query(Agent模型).filter(Agent模型.id == 任务.agent_id).first()
        if not agent:
            raise ValueError(f"Agent 不存在: {任务.agent_id}")

        agent配置 = agent.to_config_dict(解密函数=解密)

        # 3. 获取工具记录
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

        # 4. 构建 Agent 图并执行（非流式）
        from app.图引擎.构建器 import 构建Agent图

        图 = 构建Agent图(agent配置, 工具记录列表=工具记录列表)

        输入消息 = 任务.提示词 or "请执行任务"
        结果 = await 图.ainvoke({"messages": [{"role": "user", "content": 输入消息}]})

        # 提取最终回复
        最终回复 = ""
        if "messages" in 结果:
            for msg in reversed(结果["messages"]):
                if hasattr(msg, "content") and msg.content:
                    最终回复 = msg.content if isinstance(msg.content, str) else str(msg.content)
                    break

        # 5. 更新日志记录
        耗时 = time.time() - 开始时间
        日志记录.状态 = "success"
        日志记录.结果 = 最终回复[:SCHEDULER_RESULT_MAX_LEN]  # 截断过长结果
        日志记录.结束时间 = datetime.now()

        # 6. 更新任务的 last_run_at
        任务.上次运行 = datetime.now()
        db.commit()

        logger.info("[调度器] 任务执行成功: %s (耗时 %.1fs)", 任务.名称, 耗时)

    except Exception as e:
        logger.error("[调度器] 任务执行失败 %s: %s", schedule_id, e)
        if 日志记录:
            日志记录.状态 = "failed"
            日志记录.错误 = str(e)[:SCHEDULER_ERROR_MAX_LEN]
            日志记录.结束时间 = datetime.now()
            try:
                db.commit()
            except Exception:
                db.rollback()
    finally:
        db.close()
