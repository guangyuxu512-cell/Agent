# app/api/机器管理.py
# 影刀机器管理 + 应用绑定 API
# 包含：machines CRUD、machine_apps CRUD、心跳接口、状态回调接口

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from app.db.数据库 import 获取数据库, 会话工厂
from app.db.模型 import 机器模型, 机器应用模型, 任务队列模型
from app.schemas import 统一响应
from app.配置 import RPA密钥

logger = logging.getLogger(__name__)


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


class 状态更新请求(BaseModel):
    status: str  # idle / running / offline


# ==================== 辅助函数 ====================

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
    """获取所有机器列表（状态完全由影刀客户端通过 HTTP 回调控制）"""
    机器列表 = 数据库.query(机器模型).order_by(机器模型.创建时间.desc()).all()
    return 统一响应(data=[机器转字典(m) for m in 机器列表])


@机器管理路由.post("/machines", response_model=统一响应)
async def 添加机器(
    请求体: 添加机器请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    """添加新机器"""
    鉴权失败 = _校验X密钥(x_rpa_key, "机器注册")
    if 鉴权失败:
        return 鉴权失败

    # 检查 machine_id 是否已存在
    已存在 = 数据库.query(机器模型).filter(机器模型.机器码 == 请求体.machine_id).first()
    if 已存在:
        return 统一响应(code=1, msg=f"机器码 '{请求体.machine_id}' 已存在")

    新机器 = 机器模型(
        机器码=请求体.machine_id,
        机器名称=请求体.machine_name,
        状态="idle"  # 默认为空闲状态，可立即触发
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
async def 机器心跳(
    请求体: 心跳请求,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY"),
):
    """机器心跳接口（仅更新心跳时间，不更新状态）"""
    鉴权失败 = _校验X密钥(x_rpa_key, "机器心跳")
    if 鉴权失败:
        return 鉴权失败

    机器 = 数据库.query(机器模型).filter(机器模型.机器码 == 请求体.machine_id).first()
    if not 机器:
        return 统一响应(code=1, msg=f"机器码 '{请求体.machine_id}' 不存在")

    # 只更新心跳时间，状态由 HTTP 回调接口控制
    机器.最后心跳 = datetime.now()
    机器.更新时间 = datetime.now()
    数据库.commit()

    return 统一响应(msg="心跳更新成功")


@机器管理路由.put("/machines/{machine_id}/status", response_model=统一响应)
async def 更新机器状态(
    machine_id: str,
    请求体: 状态更新请求,
    request: Request,
    数据库: Session = Depends(获取数据库),
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY")
):
    """更新机器状态（影刀回调接口，X-RPA-KEY 鉴权）

    请求头：
        X-RPA-KEY: 影刀推流密钥

    请求体：
        {"status": "idle"}  或  {"status": "running"}  或  {"status": "offline"}

    返回：
        {"code": 0, "data": null, "msg": "状态更新成功"}
    """
    # 详细日志：记录调用来源
    logger.info(f"[状态更新请求] machine_id={machine_id}, status={请求体.status}, client_ip={request.client.host if request.client else 'unknown'}")

    # X-RPA-KEY 鉴权
    鉴权失败 = _校验X密钥(x_rpa_key, "更新机器状态")
    if 鉴权失败:
        return 鉴权失败

    # 查询机器
    机器 = 数据库.query(机器模型).filter(机器模型.机器码 == machine_id).first()
    if not 机器:
        return 统一响应(code=1, msg=f"机器码 '{machine_id}' 不存在")

    # 验证状态值
    允许的状态 = ["idle", "running", "offline", "error"]
    if 请求体.status not in 允许的状态:
        return 统一响应(code=1, msg=f"无效的状态值，允许的值: {', '.join(允许的状态)}")

    旧状态 = 机器.状态
    新状态 = 请求体.status

    # 更新状态
    机器.状态 = 新状态
    机器.更新时间 = datetime.now()
    数据库.commit()

    logger.info(f"机器状态已更新: {machine_id} ({旧状态} -> {新状态})")

    # 如果状态从 running 变为 idle，检查任务队列
    if 旧状态 == "running" and 新状态 == "idle":
        await _处理任务队列(machine_id, 数据库)

    return 统一响应(msg="状态更新成功")


async def _处理任务队列(machine_id: str, 数据库: Session):
    """检查并处理任务队列（内部函数）"""
    try:
        # 查询该机器的等待任务（按创建时间排序）
        等待任务 = 数据库.query(任务队列模型).filter(
            任务队列模型.机器码 == machine_id,
            任务队列模型.状态 == "waiting"
        ).order_by(任务队列模型.创建时间).first()

        if not 等待任务:
            logger.debug(f"机器 {machine_id} 无等待任务")
            return

        # 读取影刀配置（兼容 camelCase 和 snake_case）
        from app.图引擎.内置工具._配置 import _获取系统配置
        影刀配置 = _获取系统配置("shadowbot")
        target_email = 影刀配置.get("target_email") or 影刀配置.get("targetEmail")
        subject_template = 影刀配置.get("subject_template") or 影刀配置.get("subjectTemplate") or "影刀触发-{app_name}"
        content_template = 影刀配置.get("content_template") or 影刀配置.get("contentTemplate") or "请执行应用：{app_name}"

        if not target_email:
            logger.error("未配置影刀目标邮箱，无法自动触发队列任务")
            等待任务.状态 = "failed"
            等待任务.错误 = "未配置影刀目标邮箱"
            数据库.commit()
            return

        # 发送触发邮件
        from app.图引擎.内置工具.影刀触发 import _发送触发邮件
        结果 = await _发送触发邮件(
            target_email,
            subject_template.format(app_name=等待任务.应用名),
            content_template.format(app_name=等待任务.应用名)
        )

        if 结果.startswith("错误"):
            # 发送失败
            logger.error(f"自动触发队列任务失败: {结果}")
            等待任务.状态 = "failed"
            等待任务.错误 = 结果
            数据库.commit()
            return

        # 发送成功，更新任务状态（机器状态由影刀回调更新）
        等待任务.状态 = "triggered"
        等待任务.触发时间 = datetime.now()
        数据库.commit()
        logger.info(f"[任务队列] 自动触发等待任务: {等待任务.应用名} (机器: {machine_id})")

    except Exception as e:
        logger.error(f"处理任务队列失败: {e}", exc_info=True)
