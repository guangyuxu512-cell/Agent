import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.配置 import RPA密钥
from app.db.worker模型 import Worker模型
from app.db.数据库 import 获取数据库
from app.schemas import 统一响应
from app.services.task_dispatcher import 生成Worker队列名

logger = logging.getLogger(__name__)


Worker管理路由 = APIRouter(prefix="/api/workers", tags=["Worker管理"])


class Worker注册请求(BaseModel):
    machine_id: str
    machine_name: str


class Worker心跳请求(BaseModel):
    machine_id: str
    shadowbot_running: bool


class Worker状态更新请求(BaseModel):
    status: str


def _校验X密钥(x_rpa_key: Optional[str], 操作: str):
    if not x_rpa_key:
        logger.warning("%s失败：缺少 X-RPA-KEY 请求头", 操作)
        return JSONResponse(
            status_code=403,
            content={"code": 403, "data": None, "msg": "缺少 X-RPA-KEY 请求头"},
        )

    if x_rpa_key != RPA密钥:
        logger.warning("%s失败：X-RPA-KEY 错误", 操作)
        return JSONResponse(
            status_code=403,
            content={"code": 403, "data": None, "msg": "X-RPA-KEY 错误"},
        )

    return None


def _规范状态(状态: str | None, 默认值: str = "idle") -> str:
    if not 状态:
        return 默认值
    允许状态 = {"idle", "running", "offline", "error"}
    return 状态.strip().lower() if 状态.strip().lower() in 允许状态 else 默认值


def Worker转字典(worker: Worker模型) -> dict:
    主机名 = worker.主机名 or "-"
    IP地址 = worker.IP地址 or "-"
    return {
        "id": worker.id,
        "machine_id": worker.机器码,
        "machine_name": worker.机器名称 or 主机名,
        "hostname": 主机名,
        "ip": IP地址,
        "status": worker.状态,
        "queue_name": worker.队列名,
        "last_heartbeat": worker.最后心跳.isoformat() if worker.最后心跳 else None,
        "created_at": worker.创建时间.isoformat() if worker.创建时间 else None,
        "updated_at": worker.更新时间.isoformat() if worker.更新时间 else None,
    }


@Worker管理路由.post("/register", response_model=统一响应)
async def 注册Worker(
    请求体: Worker注册请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    鉴权失败 = _校验X密钥(x_rpa_key, "Worker注册")
    if 鉴权失败:
        return 鉴权失败

    machine_id = 请求体.machine_id.strip()
    machine_name = 请求体.machine_name.strip()
    if not machine_id:
        return 统一响应(code=1, msg="machine_id 不能为空")
    if not machine_name:
        return 统一响应(code=1, msg="machine_name 不能为空")

    当前时间 = datetime.now()
    队列名 = 生成Worker队列名(machine_id)

    worker = 数据库.query(Worker模型).filter(Worker模型.机器码 == machine_id).first()
    if worker:
        worker.机器名称 = machine_name
        worker.主机名 = worker.主机名 or "-"
        worker.IP地址 = worker.IP地址 or "-"
        worker.队列名 = 队列名
        worker.状态 = "idle"
        worker.最后心跳 = 当前时间
        worker.更新时间 = 当前时间
        消息 = "注册信息已更新"
    else:
        worker = Worker模型(
            机器码=machine_id,
            机器名称=machine_name,
            主机名="-",
            IP地址="-",
            队列名=队列名,
            状态="idle",
            最后心跳=当前时间,
        )
        数据库.add(worker)
        消息 = "注册成功"

    数据库.commit()
    数据库.refresh(worker)
    logger.info("[Worker] 注册成功 machine_id=%s queue=%s", machine_id, 队列名)
    return 统一响应(data=Worker转字典(worker), msg=消息)


@Worker管理路由.post("/heartbeat", response_model=统一响应)
async def Worker心跳(
    请求体: Worker心跳请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    鉴权失败 = _校验X密钥(x_rpa_key, "Worker心跳")
    if 鉴权失败:
        return 鉴权失败

    machine_id = 请求体.machine_id.strip()
    worker = 数据库.query(Worker模型).filter(Worker模型.机器码 == machine_id).first()
    if not worker:
        return 统一响应(code=1, msg=f"Worker '{machine_id}' 未注册")

    worker.最后心跳 = datetime.now()
    worker.更新时间 = datetime.now()
    if worker.状态 == "offline" and 请求体.shadowbot_running:
        worker.状态 = "idle"
    数据库.commit()

    logger.info("[Worker] 心跳成功 machine_id=%s", machine_id)
    return 统一响应(msg="心跳成功")


@Worker管理路由.put("/{machine_id}/status", response_model=统一响应)
async def 更新Worker状态(
    machine_id: str,
    请求体: Worker状态更新请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    鉴权失败 = _校验X密钥(x_rpa_key, "更新Worker状态")
    if 鉴权失败:
        return 鉴权失败

    worker = 数据库.query(Worker模型).filter(Worker模型.机器码 == machine_id.strip()).first()
    if not worker:
        return 统一响应(code=1, msg=f"Worker '{machine_id}' 未注册")

    worker.状态 = _规范状态(请求体.status, 默认值=worker.状态 or "idle")
    worker.最后心跳 = datetime.now()
    worker.更新时间 = datetime.now()
    数据库.commit()
    数据库.refresh(worker)

    logger.info("[Worker] 状态更新 machine_id=%s status=%s", machine_id, worker.状态)
    return 统一响应(data=Worker转字典(worker), msg="状态更新成功")


@Worker管理路由.get("", response_model=统一响应)
async def 获取Workers(
    status: Optional[str] = Query(None),
    数据库: Session = Depends(获取数据库),
):
    查询 = 数据库.query(Worker模型)
    if status:
        查询 = 查询.filter(Worker模型.状态 == _规范状态(status, 默认值=status))

    列表 = 查询.order_by(desc(Worker模型.最后心跳), desc(Worker模型.id)).all()
    return 统一响应(data={"list": [Worker转字典(item) for item in 列表], "total": len(列表)})
