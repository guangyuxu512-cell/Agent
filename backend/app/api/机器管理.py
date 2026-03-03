# app/api/机器管理.py
# 影刀机器管理 + 应用绑定 API
# 包含：machines CRUD、machine_apps CRUD、心跳接口

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.db.数据库 import 获取数据库
from app.db.模型 import 机器模型, 机器应用模型
from app.schemas import 统一响应


机器管理路由 = APIRouter(prefix="/api", tags=["机器管理"])


# ==================== 请求模型 ====================

class 添加机器请求(BaseModel):
    machine_id: str
    machine_name: str


class 编辑机器请求(BaseModel):
    machine_name: str


class 添加应用绑定请求(BaseModel):
    machine_id: str
    app_name: str
    description: Optional[str] = ""


class 编辑应用绑定请求(BaseModel):
    description: Optional[str] = None
    enabled: Optional[bool] = None


class 心跳请求(BaseModel):
    machine_id: str
    shadowbot_running: bool


# ==================== 辅助函数 ====================

def 机器转字典(机器: 机器模型) -> dict:
    """将机器 ORM 对象转为字典"""
    return {
        "id": 机器.id,
        "machine_id": 机器.机器码,
        "machine_name": 机器.机器名称,
        "status": 机器.状态,
        "last_heartbeat": 机器.最后心跳.isoformat() if 机器.最后心跳 else None,
        "created_at": 机器.创建时间.isoformat() if 机器.创建时间 else None,
        "updated_at": 机器.更新时间.isoformat() if 机器.更新时间 else None,
    }


def 应用绑定转字典(绑定: 机器应用模型) -> dict:
    """将应用绑定 ORM 对象转为字典"""
    return {
        "id": 绑定.id,
        "machine_id": 绑定.机器码,
        "app_name": 绑定.应用名,
        "description": 绑定.描述,
        "enabled": 绑定.启用,
        "created_at": 绑定.创建时间.isoformat() if 绑定.创建时间 else None,
    }


# ==================== Machines CRUD ====================

@机器管理路由.get("/machines", response_model=统一响应)
async def 获取机器列表(数据库: Session = Depends(获取数据库)):
    """获取所有机器列表"""
    机器列表 = 数据库.query(机器模型).order_by(机器模型.创建时间.desc()).all()

    # 检查并更新超时的机器状态
    现在 = datetime.now()
    超时阈值 = timedelta(minutes=10)

    for 机器 in 机器列表:
        # 如果机器状态为 running 且最后心跳超过 10 分钟，更新为 offline
        if 机器.状态 == "running" and 机器.最后心跳:
            if 现在 - 机器.最后心跳 > 超时阈值:
                机器.状态 = "offline"
                机器.更新时间 = 现在

    # 提交状态更新
    数据库.commit()

    return 统一响应(data=[机器转字典(m) for m in 机器列表])


@机器管理路由.post("/machines", response_model=统一响应)
async def 添加机器(请求体: 添加机器请求, 数据库: Session = Depends(获取数据库)):
    """添加新机器"""
    # 检查 machine_id 是否已存在
    已存在 = 数据库.query(机器模型).filter(机器模型.机器码 == 请求体.machine_id).first()
    if 已存在:
        return 统一响应(code=1, msg=f"机器码 '{请求体.machine_id}' 已存在")

    新机器 = 机器模型(
        机器码=请求体.machine_id,
        机器名称=请求体.machine_name,
        状态="offline"
    )
    数据库.add(新机器)
    数据库.commit()
    数据库.refresh(新机器)
    return 统一响应(data=机器转字典(新机器), msg="机器添加成功")


@机器管理路由.put("/machines/{machine_id}", response_model=统一响应)
async def 编辑机器(
    machine_id: str,
    请求体: 编辑机器请求,
    数据库: Session = Depends(获取数据库)
):
    """编辑机器名称"""
    机器 = 数据库.query(机器模型).filter(机器模型.机器码 == machine_id).first()
    if not 机器:
        return 统一响应(code=1, msg="机器不存在")

    机器.机器名称 = 请求体.machine_name
    机器.更新时间 = datetime.now()
    数据库.commit()
    数据库.refresh(机器)
    return 统一响应(data=机器转字典(机器), msg="机器信息已更新")


@机器管理路由.delete("/machines/{machine_id}", response_model=统一响应)
async def 删除机器(machine_id: str, 数据库: Session = Depends(获取数据库)):
    """删除机器（级联删除该机器的所有应用绑定）"""
    机器 = 数据库.query(机器模型).filter(机器模型.机器码 == machine_id).first()
    if not 机器:
        return 统一响应(code=1, msg="机器不存在")

    # 级联删除该机器的所有应用绑定
    数据库.query(机器应用模型).filter(机器应用模型.机器码 == machine_id).delete()
    数据库.delete(机器)
    数据库.commit()
    return 统一响应(msg="机器及其应用绑定已删除")


# ==================== Machine Apps CRUD ====================

@机器管理路由.get("/machine-apps", response_model=统一响应)
async def 获取应用绑定列表(
    machine_id: Optional[str] = None,
    数据库: Session = Depends(获取数据库)
):
    """获取所有应用绑定（支持按 machine_id 筛选）"""
    查询 = 数据库.query(机器应用模型)
    if machine_id:
        查询 = 查询.filter(机器应用模型.机器码 == machine_id)

    绑定列表 = 查询.order_by(机器应用模型.创建时间.desc()).all()
    return 统一响应(data=[应用绑定转字典(b) for b in 绑定列表])


@机器管理路由.post("/machine-apps", response_model=统一响应)
async def 添加应用绑定(请求体: 添加应用绑定请求, 数据库: Session = Depends(获取数据库)):
    """添加应用绑定"""
    # 检查机器是否存在
    机器 = 数据库.query(机器模型).filter(机器模型.机器码 == 请求体.machine_id).first()
    if not 机器:
        return 统一响应(code=1, msg=f"机器码 '{请求体.machine_id}' 不存在")

    # 检查是否已存在相同绑定
    已存在 = 数据库.query(机器应用模型).filter(
        and_(
            机器应用模型.机器码 == 请求体.machine_id,
            机器应用模型.应用名 == 请求体.app_name
        )
    ).first()
    if 已存在:
        return 统一响应(code=1, msg=f"该机器已绑定应用 '{请求体.app_name}'")

    新绑定 = 机器应用模型(
        机器码=请求体.machine_id,
        应用名=请求体.app_name,
        描述=请求体.description or "",
        启用=True
    )
    数据库.add(新绑定)
    数据库.commit()
    数据库.refresh(新绑定)
    return 统一响应(data=应用绑定转字典(新绑定), msg="应用绑定添加成功")


@机器管理路由.put("/machine-apps/{binding_id}", response_model=统一响应)
async def 编辑应用绑定(
    binding_id: int,
    请求体: 编辑应用绑定请求,
    数据库: Session = Depends(获取数据库)
):
    """编辑应用绑定（修改 description、enabled）"""
    绑定 = 数据库.query(机器应用模型).filter(机器应用模型.id == binding_id).first()
    if not 绑定:
        return 统一响应(code=1, msg="应用绑定不存在")

    if 请求体.description is not None:
        绑定.描述 = 请求体.description
    if 请求体.enabled is not None:
        绑定.启用 = 请求体.enabled

    数据库.commit()
    数据库.refresh(绑定)
    return 统一响应(data=应用绑定转字典(绑定), msg="应用绑定已更新")


@机器管理路由.delete("/machine-apps/{binding_id}", response_model=统一响应)
async def 删除应用绑定(binding_id: int, 数据库: Session = Depends(获取数据库)):
    """删除应用绑定"""
    绑定 = 数据库.query(机器应用模型).filter(机器应用模型.id == binding_id).first()
    if not 绑定:
        return 统一响应(code=1, msg="应用绑定不存在")

    数据库.delete(绑定)
    数据库.commit()
    return 统一响应(msg="应用绑定已删除")


# ==================== 心跳接口 ====================

@机器管理路由.post("/machine/heartbeat", response_model=统一响应)
async def 机器心跳(请求体: 心跳请求, 数据库: Session = Depends(获取数据库)):
    """机器心跳接口（给电脑上的脚本调用）"""
    机器 = 数据库.query(机器模型).filter(机器模型.机器码 == 请求体.machine_id).first()
    if not 机器:
        return 统一响应(code=1, msg=f"机器码 '{请求体.machine_id}' 不存在")

    # 更新心跳时间和状态
    机器.最后心跳 = datetime.now()
    机器.状态 = "running" if 请求体.shadowbot_running else "idle"
    机器.更新时间 = datetime.now()
    数据库.commit()

    return 统一响应(msg="心跳更新成功")
