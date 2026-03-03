# app/api/系统配置.py  (V2)
# 系统配置 CRUD — 适配前端 BasicConfig.tsx
#
# 存储方式：每个分类存一行 JSON blob
#   category="email", key="__data__", value='{"smtpServer":"...","smtpPort":"..."}'
#
# 前端格式完全透传：camelCase key / 嵌套对象 / 数组（如 n8n.workflows）
# 前端发什么 JSON，后端原样存、原样返回，零转换。

import json
from typing import Any
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.数据库 import 获取数据库
from app.db.模型 import 系统配置模型
from app.schemas import 统一响应


配置路由 = APIRouter(prefix="/api/config", tags=["系统配置"])

DATA_KEY = "__data__"  # 每个分类只存一行，key 固定为 __data__


# ==================== 辅助函数 ====================

def 读取全部配置(数据库: Session) -> dict:
    """
    从数据库读取所有配置，返回前端需要的嵌套结构：
    {
        "email": {"smtpServer": "...", "smtpPort": "...", ...},
        "feishu": {"appId": "...", "appSecret": "...", ...},
        "n8n": {"apiUrl": "...", "workflows": [...], ...},
        ...
    }
    """
    所有配置 = (
        数据库.query(系统配置模型)
        .filter(系统配置模型.键 == DATA_KEY)
        .all()
    )
    结果 = {}
    for item in 所有配置:
        try:
            结果[item.分类] = json.loads(item.值) if item.值 else {}
        except json.JSONDecodeError:
            结果[item.分类] = {}
    return 结果


def 写入分类(数据库: Session, 分类: str, 数据: Any):
    """写入单个分类的配置（整个 JSON blob）"""
    json_值 = json.dumps(数据, ensure_ascii=False)

    已存在 = (
        数据库.query(系统配置模型)
        .filter(系统配置模型.分类 == 分类, 系统配置模型.键 == DATA_KEY)
        .first()
    )

    if 已存在:
        # 合并：已有的字段保留，新传入的字段覆盖
        try:
            旧数据 = json.loads(已存在.值) if 已存在.值 else {}
        except json.JSONDecodeError:
            旧数据 = {}

        if isinstance(旧数据, dict) and isinstance(数据, dict):
            旧数据.update(数据)
            已存在.值 = json.dumps(旧数据, ensure_ascii=False)
        else:
            已存在.值 = json_值

        已存在.更新时间 = datetime.now()
    else:
        新配置 = 系统配置模型(
            id=str(uuid4()),
            分类=分类,
            键=DATA_KEY,
            值=json_值,
        )
        数据库.add(新配置)


# ==================== 接口 ====================

@配置路由.get("", response_model=统一响应)
async def 获取全部配置(数据库: Session = Depends(获取数据库)):
    """
    GET /api/config
    返回前端 ConfigData 结构（camelCase，嵌套对象，数组）
    """
    return 统一响应(data=读取全部配置(数据库))


async def _保存配置(request: Request, 数据库: Session) -> 统一响应:
    """POST/PUT 共用的保存逻辑"""
    body = await request.json()

    # 兼容：如果有人用 V1 的 {configs: {...}} 格式调用
    if "configs" in body and isinstance(body["configs"], dict):
        body = body["configs"]

    for 分类, 数据 in body.items():
        if isinstance(数据, (dict, list)):
            写入分类(数据库, 分类, 数据)

    数据库.commit()
    return 统一响应(data=读取全部配置(数据库), msg="配置已保存")


@配置路由.post("", response_model=统一响应)
async def 保存全部配置_POST(request: Request, 数据库: Session = Depends(获取数据库)):
    """POST /api/config"""
    return await _保存配置(request, 数据库)


@配置路由.put("", response_model=统一响应)
async def 保存全部配置_PUT(request: Request, 数据库: Session = Depends(获取数据库)):
    """PUT /api/config — 和 POST 完全一样，兼容不同前端调用方式"""
    return await _保存配置(request, 数据库)


@配置路由.get("/{category}", response_model=统一响应)
async def 获取分类配置(
    category: str,
    数据库: Session = Depends(获取数据库),
):
    """GET /api/config/{category}"""
    配置 = (
        数据库.query(系统配置模型)
        .filter(系统配置模型.分类 == category, 系统配置模型.键 == DATA_KEY)
        .first()
    )
    if 配置 and 配置.值:
        try:
            return 统一响应(data=json.loads(配置.值))
        except json.JSONDecodeError:
            return 统一响应(data={})
    return 统一响应(data={})


@配置路由.delete("/{category}", response_model=统一响应)
async def 删除分类配置(
    category: str,
    数据库: Session = Depends(获取数据库),
):
    """DELETE /api/config/{category}"""
    数据库.query(系统配置模型).filter(系统配置模型.分类 == category).delete()
    数据库.commit()
    return 统一响应(msg=f"{category} 配置已删除")