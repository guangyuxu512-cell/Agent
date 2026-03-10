import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.配置 import RPA密钥
from app.db.数据库 import 获取数据库
from app.db.模型 import 任务派发模型
from app.db.worker模型 import Worker模型
from app.schemas import 统一响应
from app.services.dispatch_records import 任务派发转字典, 查询任务执行状态
from app.services.task_dispatcher import 派发Echo测试

logger = logging.getLogger(__name__)


任务派发路由 = APIRouter(prefix="/api/task-dispatches", tags=["任务派发"])


class Echo测试请求(BaseModel):
    machine_id: str
    message: str = "hello celery"


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


@任务派发路由.get("", response_model=统一响应)
async def 获取任务派发列表(
    machine_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    数据库: Session = Depends(获取数据库),
):
    查询 = 数据库.query(任务派发模型)
    if machine_id:
        查询 = 查询.filter(任务派发模型.机器码 == machine_id)
    if status:
        查询 = 查询.filter(任务派发模型.状态 == status)

    列表 = 查询.order_by(desc(任务派发模型.提交时间)).all()
    return 统一响应(data={"list": [任务派发转字典(item) for item in 列表], "total": len(列表)})


@任务派发路由.get("/{dispatch_id}", response_model=统一响应)
async def 获取任务派发详情(
    dispatch_id: str,
    数据库: Session = Depends(获取数据库),
):
    记录 = 数据库.query(任务派发模型).filter(任务派发模型.dispatch_id == dispatch_id).first()
    if not 记录:
        return 统一响应(code=1, msg="任务派发记录不存在")

    return 统一响应(data=任务派发转字典(记录))


@任务派发路由.get("/{task_id}/status", response_model=统一响应)
async def 获取任务执行状态详情(
    task_id: str,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    鉴权失败 = _校验X密钥(x_rpa_key, "查询任务状态")
    if 鉴权失败:
        return 鉴权失败

    状态详情 = 查询任务执行状态(数据库, task_id)
    if not 状态详情:
        return 统一响应(code=1, msg="任务派发记录不存在")

    logger.info("[任务派发] 查询任务状态 task_id=%s status=%s", task_id, 状态详情["status"])
    return 统一响应(data=状态详情)


@任务派发路由.post("/echo-test", response_model=统一响应)
async def 创建Echo测试任务(
    请求体: Echo测试请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    鉴权失败 = _校验X密钥(x_rpa_key, "任务派发")
    if 鉴权失败:
        return 鉴权失败

    machine_id = 请求体.machine_id.strip()
    if not machine_id:
        return 统一响应(code=1, msg="machine_id 不能为空")

    worker = 数据库.query(Worker模型).filter(Worker模型.机器码 == machine_id).first()
    if not worker:
        return 统一响应(code=1, msg=f"Worker '{machine_id}' 未注册")

    logger.info("[任务派发] 收到 echo_test 请求 machine_id=%s", machine_id)
    派发记录 = 派发Echo测试(machine_id, 请求体.message, requested_by="api")
    if not 派发记录:
        return 统一响应(code=1, msg="echo_test 投递失败")
    return 统一响应(data=派发记录, msg="echo_test 已投递")
