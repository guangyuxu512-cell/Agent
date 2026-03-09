# app/调度器.py
# APScheduler 封装 — 定时任务调度 + Celery 投递

import json
import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from app.db.数据库 import 会话工厂
from app.db.模型 import 定时任务模型, Worker模型
from app.常量 import SCHEDULER_MISFIRE_GRACE
from app.services.task_dispatcher import 派发定时任务

logger = logging.getLogger(__name__)

# ========== 全局单例 ==========

调度器实例: AsyncIOScheduler | None = None


# ========== 生命周期 ==========

async def 启动调度器():
    global 调度器实例
    调度器实例 = AsyncIOScheduler(timezone="Asia/Shanghai")
    调度器实例.start()
    logger.info("[调度器] APScheduler 已启动")

    # 注册日志清理任务（每天凌晨 3 点执行）
    from app.api.日志推流 import 清理过期日志
    调度器实例.add_job(
        清理过期日志,
        trigger="cron",
        hour=3,
        minute=0,
        id="log_cleanup",
        name="清理过期日志",
        replace_existing=True,
        misfire_grace_time=3600
    )
    logger.info("[调度器] 已注册日志清理任务（每天 03:00）")

    调度器实例.add_job(
        检查离线Workers,
        trigger="interval",
        minutes=1,
        id="worker_offline_check",
        name="巡检离线Workers",
        replace_existing=True,
        misfire_grace_time=120,
    )
    logger.info("[调度器] 已注册 Worker 离线巡检任务（每 1 分钟）")

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


# ========== 任务投递 ==========

async def 执行定时任务(schedule_id: str):
    """
    APScheduler 到点后只负责把任务投递到 Celery。
    """
    try:
        dispatch_id = 派发定时任务(schedule_id, requested_by="scheduler")
        if not dispatch_id:
            logger.error("[调度器] 投递到 Celery 失败: %s", schedule_id)
            return
        logger.info("[调度器] 已投递到 Celery: schedule=%s dispatch=%s", schedule_id, dispatch_id)
    except Exception as e:
        logger.error("[调度器] 投递任务失败 %s: %s", schedule_id, e, exc_info=True)


def 检查离线Workers():
    """每分钟扫描 workers 表，60 秒无心跳标记为 offline。"""
    db = 会话工厂()
    try:
        截止时间 = datetime.now() - timedelta(seconds=60)
        待离线列表 = db.query(Worker模型).filter(
            Worker模型.最后心跳.is_not(None),
            Worker模型.最后心跳 < 截止时间,
            Worker模型.状态 != "offline"
        ).all()

        if not 待离线列表:
            return

        for worker in 待离线列表:
            worker.状态 = "offline"
            worker.更新时间 = datetime.now()

        db.commit()
        logger.info("[调度器] Worker 离线巡检完成，标记 %d 台机器离线", len(待离线列表))
    except Exception as e:
        db.rollback()
        logger.error("[调度器] Worker 离线巡检失败: %s", e, exc_info=True)
    finally:
        db.close()
