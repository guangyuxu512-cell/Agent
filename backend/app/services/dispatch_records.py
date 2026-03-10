import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.数据库 import 会话工厂
from app.db.模型 import 任务派发模型

logger = logging.getLogger(__name__)


Celery状态映射 = {
    "PENDING": "pending",
    "RECEIVED": "running",
    "STARTED": "running",
    "RETRY": "running",
    "SUCCESS": "success",
    "FAILURE": "failed",
    "REVOKED": "failed",
}


def 获取任务派发记录(db: Session, dispatch_id: str | None):
    if not dispatch_id:
        return None
    return db.query(任务派发模型).filter(任务派发模型.dispatch_id == dispatch_id).first()


def _解析载荷(payload: Any) -> Any:
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            return payload
    return payload


def _序列化结果(result: Any) -> str | None:
    if result is None:
        return None
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False)
    except TypeError:
        return str(result)


def _规范Celery状态(celery_state: str | None, 当前状态: str | None) -> str:
    if 当前状态 in {"success", "failed"}:
        return 当前状态
    if not celery_state:
        return 当前状态 or "pending"
    return Celery状态映射.get(celery_state.strip().upper(), 当前状态 or "pending")


def 更新任务派发状态(
    db,
    dispatch_id: str | None,
    状态: str,
    重试次数: int = 0,
    错误信息: str | None = None,
    载荷引用: str | None = None,
):
    if not dispatch_id:
        return None

    派发记录 = 获取任务派发记录(db, dispatch_id)
    if not 派发记录:
        return None

    派发记录.状态 = 状态
    派发记录.重试次数 = 重试次数
    if 状态 in {"success", "failed"}:
        派发记录.完成时间 = datetime.now()
    if 错误信息 is not None:
        派发记录.错误信息 = 错误信息
    if 载荷引用 is not None:
        派发记录.载荷引用 = 载荷引用
    return 派发记录


def 标记任务派发状态(
    dispatch_id: str | None,
    状态: str,
    重试次数: int = 0,
    错误信息: str | None = None,
    载荷引用: str | None = None,
):
    if not dispatch_id:
        return

    db = 会话工厂()
    try:
        更新任务派发状态(db, dispatch_id, 状态, 重试次数, 错误信息, 载荷引用)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def 任务派发转字典(记录: 任务派发模型) -> dict:
    payload = _解析载荷(记录.载荷引用)

    return {
        "task_id": 记录.dispatch_id,
        "dispatch_id": 记录.dispatch_id,
        "task_name": 记录.任务名,
        "machine_id": 记录.机器码,
        "queue_name": 记录.队列名,
        "schedule_id": 记录.schedule_id,
        "status": 记录.状态,
        "payload_ref": payload,
        "requested_by": 记录.请求来源,
        "retry_count": 记录.重试次数,
        "submitted_at": 记录.提交时间.isoformat() if 记录.提交时间 else None,
        "finished_at": 记录.完成时间.isoformat() if 记录.完成时间 else None,
        "error_message": 记录.错误信息,
    }


def 查询任务执行状态(db: Session, task_id: str) -> dict | None:
    记录 = 获取任务派发记录(db, task_id)
    if not 记录:
        return None

    celery_state = None
    try:
        from app.celery_app import celery_app

        异步结果 = celery_app.AsyncResult(task_id)
        celery_state = getattr(异步结果, "state", None)
        最新状态 = _规范Celery状态(celery_state, 记录.状态)
        错误信息 = None
        载荷引用 = None

        if 最新状态 == "success":
            载荷引用 = _序列化结果(getattr(异步结果, "result", None))
        elif 最新状态 == "failed":
            异常信息 = getattr(异步结果, "result", None) or getattr(异步结果, "info", None)
            错误信息 = str(异常信息) if 异常信息 else 记录.错误信息

        if 最新状态 != 记录.状态 or (载荷引用 and not 记录.载荷引用):
            更新任务派发状态(
                db,
                dispatch_id=task_id,
                状态=最新状态,
                重试次数=记录.重试次数,
                错误信息=错误信息,
                载荷引用=载荷引用 if 载荷引用 else None,
            )
            db.commit()
            db.refresh(记录)
    except Exception as exc:
        logger.warning("[任务派发] 查询 Celery 状态失败 task_id=%s: %s", task_id, exc)

    数据 = 任务派发转字典(记录)
    数据["celery_state"] = celery_state
    数据["result"] = 数据.get("payload_ref")
    数据["error"] = 数据.get("error_message")
    return 数据
