from typing import Any, Optional

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.数据库 import 获取数据库
from app.db.模型 import 机器模型
from app.schemas import 统一响应
from app.services.机器接入 import 校验机器密钥, 处理任务回调


回调路由 = APIRouter(prefix="/api", tags=["回调"])


class 任务回调请求(BaseModel):
    task_id: Optional[str] = None
    dispatch_id: Optional[str] = None
    machine_id: Optional[str] = None
    status: str
    result: Any = None
    error: Optional[str] = None
    retry_count: int = Field(default=0, ge=0)
    rpa_key: Optional[str] = None


@回调路由.post("/callback", response_model=统一响应)
async def 接收任务回调(
    请求体: 任务回调请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    task_id = (请求体.task_id or 请求体.dispatch_id or "").strip()
    if not task_id:
        return 统一响应(code=1, msg="task_id 不能为空")

    if 请求体.machine_id:
        机器 = 数据库.query(机器模型).filter(机器模型.机器码 == 请求体.machine_id.strip()).first()
        if 机器 and not 校验机器密钥(机器, 请求体.rpa_key or x_rpa_key):
            return 统一响应(code=403, msg="rpa_key 校验失败")

    结果 = 处理任务回调(
        数据库,
        task_id=task_id,
        status=请求体.status,
        machine_id=请求体.machine_id,
        result=请求体.result,
        error=请求体.error,
        retry_count=请求体.retry_count,
    )
    if not 结果:
        return 统一响应(code=1, msg="任务派发记录不存在")

    return 统一响应(data=结果, msg="回调处理成功")
