import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.数据库 import 获取数据库
from app.db.模型 import Worker模型
from app.schemas import 统一响应
from app.配置 import RPA密钥
from app.services.task_dispatcher import 生成Worker队列名

logger = logging.getLogger(__name__)


Workers路由 = APIRouter(prefix="/api/workers", tags=["Workers"])


class Worker注册请求(BaseModel):
    machine_id: str
    hostname: str
    ip: str
    queue_name: Optional[str] = None
    status: str = "online"
    tags: list[str] = Field(default_factory=list)


class Worker心跳请求(BaseModel):
    machine_id: str
    status: str = "online"
    ip: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


def _校验X密钥(x_rpa_key: Optional[str]) -> Optional[统一响应]:
    if not x_rpa_key:
        return 统一响应(code=403, msg="缺少 X-RPA-KEY 请求头")
    if x_rpa_key != RPA密钥:
        return 统一响应(code=403, msg="X-RPA-KEY 错误")
    return None


def _规范状态(状态: str) -> str:
    return 状态 if 状态 in {"online", "offline", "busy"} else "online"


def Worker转字典(worker: Worker模型) -> dict:
    try:
        标签 = json.loads(worker.标签 or "[]")
    except (json.JSONDecodeError, TypeError):
        标签 = []

    return {
        "id": worker.id,
        "machine_id": worker.机器码,
        "hostname": worker.主机名,
        "ip": worker.IP地址,
        "queue_name": worker.队列名,
        "status": worker.状态,
        "last_heartbeat": worker.最后心跳.isoformat() if worker.最后心跳 else None,
        "tags": 标签,
    }


@Workers路由.post("/register", response_model=统一响应)
async def 注册Worker(
    请求体: Worker注册请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    鉴权失败 = _校验X密钥(x_rpa_key)
    if 鉴权失败:
        return 鉴权失败

    if not 请求体.machine_id.strip():
        return 统一响应(code=1, msg="machine_id 不能为空")

    队列名 = 请求体.queue_name or 生成Worker队列名(请求体.machine_id)
    当前时间 = datetime.now()

    worker = 数据库.query(Worker模型).filter(Worker模型.机器码 == 请求体.machine_id).first()
    if worker:
        worker.主机名 = 请求体.hostname.strip()
        worker.IP地址 = 请求体.ip.strip()
        worker.队列名 = 队列名
        worker.状态 = _规范状态(请求体.status)
        worker.标签 = json.dumps(请求体.tags, ensure_ascii=False)
        worker.最后心跳 = 当前时间
        worker.更新时间 = 当前时间
        msg = "注册信息已更新"
    else:
        worker = Worker模型(
            机器码=请求体.machine_id.strip(),
            主机名=请求体.hostname.strip(),
            IP地址=请求体.ip.strip(),
            队列名=队列名,
            状态=_规范状态(请求体.status),
            最后心跳=当前时间,
            标签=json.dumps(请求体.tags, ensure_ascii=False),
        )
        数据库.add(worker)
        msg = "注册成功"

    数据库.commit()
    数据库.refresh(worker)
    return 统一响应(data=Worker转字典(worker), msg=msg)


@Workers路由.post("/heartbeat", response_model=统一响应)
async def Worker心跳(
    请求体: Worker心跳请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    鉴权失败 = _校验X密钥(x_rpa_key)
    if 鉴权失败:
        return 鉴权失败

    worker = 数据库.query(Worker模型).filter(Worker模型.机器码 == 请求体.machine_id).first()
    if not worker:
        return 统一响应(code=1, msg=f"机器 '{请求体.machine_id}' 未注册")

    worker.状态 = _规范状态(请求体.status)
    worker.最后心跳 = datetime.now()
    worker.更新时间 = datetime.now()
    if 请求体.ip:
        worker.IP地址 = 请求体.ip.strip()
    if 请求体.tags:
        worker.标签 = json.dumps(请求体.tags, ensure_ascii=False)
    数据库.commit()
    return 统一响应(msg="心跳成功")


@Workers路由.get("", response_model=统一响应)
async def 获取Workers(
    status: Optional[str] = Query(None),
    数据库: Session = Depends(获取数据库),
):
    查询 = 数据库.query(Worker模型)
    if status:
        查询 = 查询.filter(Worker模型.状态 == status)

    列表 = 查询.order_by(desc(Worker模型.最后心跳), desc(Worker模型.id)).all()
    return 统一响应(data={"list": [Worker转字典(item) for item in 列表], "total": len(列表)})
