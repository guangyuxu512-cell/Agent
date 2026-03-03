# app/api/定时任务.py
# 定时任务 CRUD 接口
# 对齐前端 Schedule 类型（camelCase）

import json
import logging
from uuid import uuid4
from typing import Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.数据库 import 获取数据库
from app.db.模型 import 定时任务模型, 任务记录模型
from app.调度器 import 注册任务, 移除任务
from app.schemas import 统一响应

logger = logging.getLogger(__name__)


定时任务路由 = APIRouter(prefix="/api/schedules", tags=["定时任务"])


# ==================== 请求模型 ====================

class 创建定时任务请求(BaseModel):
    name: str
    agentId: str
    triggerType: str = "cron"
    cronExpression: Optional[str] = None
    intervalValue: Optional[int] = None
    intervalUnit: Optional[str] = None
    executeTime: Optional[str] = None
    inputMessage: str = ""
    enabled: bool = True


class 更新定时任务请求(BaseModel):
    name: Optional[str] = None
    agentId: Optional[str] = None
    triggerType: Optional[str] = None
    cronExpression: Optional[str] = None
    intervalValue: Optional[int] = None
    intervalUnit: Optional[str] = None
    executeTime: Optional[str] = None
    inputMessage: Optional[str] = None
    enabled: Optional[bool] = None


# ==================== 辅助函数 ====================

def _构建触发配置(triggerType: str, cronExpression=None, intervalValue=None,
                intervalUnit=None, executeTime=None) -> dict:
    """根据触发类型构建 trigger_config JSON"""
    if triggerType == "cron":
        return {"cronExpression": cronExpression or "0 8 * * *"}
    elif triggerType == "interval":
        return {
            "intervalValue": intervalValue or 1,
            "intervalUnit": intervalUnit or "hours",
        }
    elif triggerType == "once":
        return {"executeTime": executeTime or ""}
    return {}


def 任务转字典(任务: 定时任务模型) -> dict:
    """ORM → 前端 camelCase 字典，拆开 trigger_config 为扁平字段"""
    配置原始 = 任务.触发配置
    if isinstance(配置原始, str):
        try:
            配置 = json.loads(配置原始)
        except (json.JSONDecodeError, TypeError):
            配置 = {}
    else:
        配置 = 配置原始 or {}

    # 查最近一条执行日志获取 lastRunStatus / lastRunDuration
    结果 = {
        "id": 任务.id,
        "name": 任务.名称,
        "agentId": 任务.agent_id,
        "triggerType": 任务.触发类型 or "cron",
        "cronExpression": 配置.get("cronExpression"),
        "intervalValue": 配置.get("intervalValue"),
        "intervalUnit": 配置.get("intervalUnit"),
        "executeTime": 配置.get("executeTime"),
        "inputMessage": 任务.提示词 or "",
        "enabled": 任务.启用 if 任务.启用 is not None else True,
        "lastRunTime": 任务.上次运行.strftime("%Y-%m-%d %H:%M:%S") if 任务.上次运行 else None,
        "lastRunStatus": None,
        "lastRunDuration": None,
    }
    return 结果


def _补充运行状态(db: Session, 任务字典: dict):
    """从 schedule_logs 补充 lastRunStatus 和 lastRunDuration"""
    最近日志 = (
        db.query(任务记录模型)
        .filter(任务记录模型.schedule_id == 任务字典["id"])
        .order_by(desc(任务记录模型.开始时间))
        .first()
    )
    if 最近日志:
        任务字典["lastRunStatus"] = 最近日志.状态
        if 最近日志.开始时间 and 最近日志.结束时间:
            耗时秒 = (最近日志.结束时间 - 最近日志.开始时间).total_seconds()
            if 耗时秒 < 60:
                任务字典["lastRunDuration"] = f"{耗时秒:.1f}s"
            else:
                任务字典["lastRunDuration"] = f"{耗时秒/60:.1f}min"


# ==================== 接口 ====================

@定时任务路由.get("", response_model=统一响应)
async def 获取定时任务列表(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    数据库: Session = Depends(获取数据库),
):
    查询 = 数据库.query(定时任务模型)
    总数 = 查询.count()
    任务列表 = (
        查询.order_by(desc(定时任务模型.创建时间))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    结果列表 = []
    for 任务 in 任务列表:
        d = 任务转字典(任务)
        _补充运行状态(数据库, d)
        结果列表.append(d)

    return 统一响应(data={"list": 结果列表, "total": 总数})


@定时任务路由.post("", response_model=统一响应)
async def 创建定时任务(
    请求体: 创建定时任务请求,
    数据库: Session = Depends(获取数据库),
):
    if not 请求体.name or not 请求体.name.strip():
        return 统一响应(code=1, msg="任务名称不能为空")
    if not 请求体.agentId:
        return 统一响应(code=1, msg="必须指定 agentId")

    触发配置 = _构建触发配置(
        请求体.triggerType,
        请求体.cronExpression,
        请求体.intervalValue,
        请求体.intervalUnit,
        请求体.executeTime,
    )

    新任务 = 定时任务模型(
        id=str(uuid4()),
        名称=请求体.name.strip(),
        agent_id=请求体.agentId,
        触发类型=请求体.triggerType,
        触发配置=json.dumps(触发配置, ensure_ascii=False),
        提示词=请求体.inputMessage or "",
        启用=请求体.enabled,
    )
    数据库.add(新任务)
    数据库.commit()
    数据库.refresh(新任务)

    # 如果启用，注册到调度器
    if 新任务.启用:
        try:
            注册任务(新任务)
        except Exception as e:
            logger.error("[定时任务] 注册调度失败: %s", e)

    d = 任务转字典(新任务)
    return 统一响应(data=d)


@定时任务路由.put("/{schedule_id}", response_model=统一响应)
async def 更新定时任务(
    schedule_id: str,
    请求体: 更新定时任务请求,
    数据库: Session = Depends(获取数据库),
):
    任务 = 数据库.query(定时任务模型).filter(定时任务模型.id == schedule_id).first()
    if not 任务:
        return 统一响应(code=1, msg="定时任务不存在")

    # 更新基础字段
    if 请求体.name is not None:
        任务.名称 = 请求体.name.strip()
    if 请求体.agentId is not None:
        任务.agent_id = 请求体.agentId
    if 请求体.inputMessage is not None:
        任务.提示词 = 请求体.inputMessage

    # 更新触发配置
    触发类型变更 = 请求体.triggerType is not None
    当前触发类型 = 请求体.triggerType or 任务.触发类型

    if 触发类型变更:
        任务.触发类型 = 请求体.triggerType

    # 重建 trigger_config（合并现有配置和新值）
    现有配置原始 = 任务.触发配置
    if isinstance(现有配置原始, str):
        try:
            现有配置 = json.loads(现有配置原始)
        except (json.JSONDecodeError, TypeError):
            现有配置 = {}
    else:
        现有配置 = 现有配置原始 or {}

    if 请求体.cronExpression is not None:
        现有配置["cronExpression"] = 请求体.cronExpression
    if 请求体.intervalValue is not None:
        现有配置["intervalValue"] = 请求体.intervalValue
    if 请求体.intervalUnit is not None:
        现有配置["intervalUnit"] = 请求体.intervalUnit
    if 请求体.executeTime is not None:
        现有配置["executeTime"] = 请求体.executeTime

    # 如果触发类型变更，重建干净的配置
    if 触发类型变更:
        现有配置 = _构建触发配置(
            当前触发类型,
            现有配置.get("cronExpression"),
            现有配置.get("intervalValue"),
            现有配置.get("intervalUnit"),
            现有配置.get("executeTime"),
        )

    任务.触发配置 = json.dumps(现有配置, ensure_ascii=False)

    # 更新启用状态
    if 请求体.enabled is not None:
        任务.启用 = 请求体.enabled

    任务.更新时间 = datetime.now()
    数据库.commit()
    数据库.refresh(任务)

    # 更新调度器
    if 任务.启用:
        try:
            注册任务(任务)
        except Exception as e:
            logger.error("[定时任务] 更新调度失败: %s", e)
    else:
        移除任务(schedule_id)

    d = 任务转字典(任务)
    _补充运行状态(数据库, d)
    return 统一响应(data=d)


@定时任务路由.delete("/{schedule_id}", response_model=统一响应)
async def 删除定时任务(
    schedule_id: str,
    数据库: Session = Depends(获取数据库),
):
    任务 = 数据库.query(定时任务模型).filter(定时任务模型.id == schedule_id).first()
    if 任务:
        # 先从调度器移除
        移除任务(schedule_id)
        # 删除执行日志
        数据库.query(任务记录模型).filter(任务记录模型.schedule_id == schedule_id).delete()
        # 删除任务
        数据库.delete(任务)
        数据库.commit()
    return 统一响应()
