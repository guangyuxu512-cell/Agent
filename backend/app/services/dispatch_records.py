import json
from datetime import datetime

from app.db.数据库 import 会话工厂
from app.db.模型 import 任务派发模型


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

    派发记录 = db.query(任务派发模型).filter(任务派发模型.dispatch_id == dispatch_id).first()
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
    payload = 记录.载荷引用
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
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
