import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.加密 import 加密, 解密
from app.配置 import RPA密钥
from app.db.模型 import 任务派发模型, 机器模型
from app.services.dispatch_records import 更新任务派发状态, 任务派发转字典

logger = logging.getLogger(__name__)


机器状态映射 = {
    "online": "idle",
    "idle": "idle",
    "busy": "running",
    "running": "running",
    "offline": "offline",
    "error": "error",
    "failed": "error",
}

任务状态映射 = {
    "pending": "pending",
    "queued": "pending",
    "submitted": "pending",
    "running": "running",
    "started": "running",
    "processing": "running",
    "success": "success",
    "succeeded": "success",
    "completed": "success",
    "done": "success",
    "ok": "success",
    "failed": "failed",
    "failure": "failed",
    "error": "failed",
}


def 规范机器状态(状态: str | None) -> str:
    if not 状态:
        return "idle"
    return 机器状态映射.get(状态.strip().lower(), "idle")


def 规范任务状态(状态: str | None) -> str:
    if not 状态:
        return "pending"
    return 任务状态映射.get(状态.strip().lower(), "pending")


def 获取机器鉴权密钥(机器: 机器模型 | None) -> str:
    if not 机器 or not 机器.RPA密钥:
        return ""
    return 解密(机器.RPA密钥 or "")


def 校验机器密钥(机器: 机器模型 | None, rpa_key: str | None = None) -> bool:
    if not 机器:
        return False

    已保存密钥 = 获取机器鉴权密钥(机器).strip()
    提供密钥 = (rpa_key or "").strip()

    if 提供密钥:
        if 已保存密钥 and 提供密钥 == 已保存密钥:
            return True
        return 提供密钥 == RPA密钥

    if not 已保存密钥:
        return True

    return 已保存密钥 == RPA密钥


def 注册机器(
    db: Session,
    machine_id: str,
    rpa_key: str | None = None,
    machine_name: str | None = None,
    status: str | None = None,
) -> tuple[机器模型, str]:
    当前时间 = datetime.now()
    机器码 = (machine_id or "").strip()
    if not 机器码:
        raise ValueError("machine_id 不能为空")

    密钥明文 = (rpa_key or RPA密钥).strip()
    机器名称 = (machine_name or 机器码).strip() or 机器码
    机器状态 = 规范机器状态(status)

    机器 = db.query(机器模型).filter(机器模型.机器码 == 机器码).first()
    if 机器:
        机器.机器名称 = 机器名称
        if 密钥明文:
            机器.RPA密钥 = 加密(密钥明文)
        机器.状态 = 机器状态
        机器.最后心跳 = 当前时间
        机器.更新时间 = 当前时间
        消息 = "注册信息已更新"
    else:
        机器 = 机器模型(
            机器码=机器码,
            机器名称=机器名称,
            RPA密钥=加密(密钥明文) if 密钥明文 else "",
            状态=机器状态,
            最后心跳=当前时间,
        )
        db.add(机器)
        消息 = "注册成功"

    db.commit()
    db.refresh(机器)
    return 机器, 消息


def 更新机器心跳(
    db: Session,
    machine_id: str,
    status: str | None = None,
    rpa_key: str | None = None,
) -> 机器模型 | None:
    机器码 = (machine_id or "").strip()
    机器 = db.query(机器模型).filter(机器模型.机器码 == 机器码).first()
    if not 机器:
        return None

    if not 校验机器密钥(机器, rpa_key):
        raise PermissionError("rpa_key 校验失败")

    当前时间 = datetime.now()
    机器.状态 = 规范机器状态(status)
    机器.最后心跳 = 当前时间
    机器.更新时间 = 当前时间
    db.commit()
    db.refresh(机器)
    return 机器


def 机器转接入字典(机器: 机器模型) -> dict[str, Any]:
    return {
        "machine_id": 机器.机器码,
        "machine_name": 机器.机器名称,
        "status": 机器.状态,
        "last_heartbeat": 机器.最后心跳.isoformat() if 机器.最后心跳 else None,
    }


def 处理任务回调(
    db: Session,
    task_id: str,
    status: str,
    machine_id: str | None = None,
    result: Any = None,
    error: str | None = None,
    retry_count: int = 0,
) -> dict | None:
    任务状态 = 规范任务状态(status)
    结果载荷 = None
    if result is not None:
        结果载荷 = json.dumps(result, ensure_ascii=False) if not isinstance(result, str) else result

    记录 = 更新任务派发状态(
        db,
        dispatch_id=task_id,
        状态=任务状态,
        重试次数=retry_count,
        错误信息=error,
        载荷引用=结果载荷,
    )
    if not 记录:
        return None

    if machine_id:
        机器 = db.query(机器模型).filter(机器模型.机器码 == machine_id.strip()).first()
        if 机器:
            机器.最后心跳 = datetime.now()
            if 任务状态 == "running":
                机器.状态 = "running"
            elif 任务状态 == "success":
                机器.状态 = "idle"
            elif 任务状态 == "failed":
                机器.状态 = "error"
            机器.更新时间 = datetime.now()

    db.commit()
    db.refresh(记录)
    return 任务派发转字典(记录)


def 获取任务状态详情(db: Session, task_id: str) -> dict | None:
    记录 = db.query(任务派发模型).filter(任务派发模型.dispatch_id == task_id).first()
    if not 记录:
        return None

    数据 = 任务派发转字典(记录)
    数据["result"] = 数据.get("payload_ref")
    数据["error"] = 数据.get("error_message")
    return 数据
