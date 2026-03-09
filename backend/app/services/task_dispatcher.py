import json
import logging
from datetime import datetime
from uuid import uuid4

from app.db.数据库 import 会话工厂
from app.db.模型 import 定时任务模型, 任务派发模型
from app.配置 import CELERY_DEFAULT_QUEUE
from app.services.dispatch_records import 任务派发转字典, 标记任务派发状态

logger = logging.getLogger(__name__)


def 生成Worker队列名(machine_id: str | None = None) -> str:
    if machine_id and machine_id.strip():
        return f"worker.{machine_id.strip()}"
    return CELERY_DEFAULT_QUEUE


def 创建任务派发记录(
    task_name: str,
    queue_name: str,
    payload_ref: dict,
    machine_id: str | None = None,
    requested_by: str = "system",
    schedule_id: str | None = None,
):
    db = 会话工厂()
    try:
        派发记录 = 任务派发模型(
            dispatch_id=str(uuid4()),
            任务名=task_name,
            机器码=machine_id or "",
            队列名=queue_name,
            schedule_id=schedule_id,
            状态="pending",
            载荷引用=json.dumps(payload_ref, ensure_ascii=False),
            请求来源=requested_by,
            重试次数=0,
            提交时间=datetime.now(),
        )
        db.add(派发记录)
        db.commit()
        db.refresh(派发记录)
        return 任务派发转字典(派发记录)
    finally:
        db.close()


def 派发定时任务(schedule_id: str, machine_id: str | None = None, requested_by: str = "scheduler") -> str | None:
    派发记录 = None
    try:
        db = 会话工厂()
        任务 = db.query(定时任务模型).filter(定时任务模型.id == schedule_id).first()
        if not 任务:
            logger.error("[派发] 定时任务不存在: %s", schedule_id)
            return None

        队列名 = 生成Worker队列名(machine_id)
        派发记录 = 创建任务派发记录(
            task_name="app.tasks.execute_schedule",
            queue_name=队列名,
            payload_ref={"schedule_id": schedule_id},
            machine_id=machine_id,
            requested_by=requested_by,
            schedule_id=schedule_id,
        )

        from app.tasks.schedule_tasks import 执行定时任务Celery

        执行定时任务Celery.apply_async(
            args=[schedule_id, 派发记录["dispatch_id"]],
            task_id=派发记录["dispatch_id"],
            queue=队列名,
        )
        logger.info("[派发] 定时任务已投递: schedule=%s dispatch=%s queue=%s", schedule_id, 派发记录["dispatch_id"], 队列名)
        return 派发记录["dispatch_id"]
    except Exception as e:
        logger.error("[派发] 投递定时任务失败 %s: %s", schedule_id, e, exc_info=True)
        if 派发记录:
            标记任务派发状态(派发记录["dispatch_id"], "failed", 错误信息=str(e))
        return None
    finally:
        if 'db' in locals():
            db.close()


def 派发Echo测试(machine_id: str, message: str, requested_by: str = "api") -> dict | None:
    队列名 = 生成Worker队列名(machine_id)
    派发记录 = None
    try:
        派发记录 = 创建任务派发记录(
            task_name="app.tasks.echo_test",
            queue_name=队列名,
            payload_ref={"message": message},
            machine_id=machine_id,
            requested_by=requested_by,
        )

        from app.tasks.test_tasks import echo_test

        echo_test.apply_async(
            args=[message, 派发记录["dispatch_id"], machine_id],
            task_id=派发记录["dispatch_id"],
            queue=队列名,
        )
        logger.info("[派发] echo_test 已投递: dispatch=%s queue=%s", 派发记录["dispatch_id"], 队列名)
        return 派发记录
    except Exception as e:
        logger.error("[派发] echo_test 投递失败 machine=%s: %s", machine_id, e, exc_info=True)
        if 派发记录:
            标记任务派发状态(派发记录["dispatch_id"], "failed", 错误信息=str(e))
        return None
