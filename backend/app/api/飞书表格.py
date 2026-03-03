# app/api/飞书表格.py
# 飞书多维表格配置 CRUD
#
# 前端 FeishuTables.tsx 对应接口：
#   GET    /api/feishu/tables          → 获取全部表格
#   POST   /api/feishu/tables          → 新增表格
#   PUT    /api/feishu/tables/{id}     → 更新表格
#   DELETE /api/feishu/tables/{id}     → 删除表格
#
# 字段映射：前端 camelCase → DB snake_case
#   appToken → app_token
#   tableId  → table_id

from uuid import uuid4
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.数据库 import 获取数据库
from app.db.模型 import 飞书表格模型
from app.schemas import 统一响应


飞书表格路由 = APIRouter(prefix="/api/feishu/tables", tags=["飞书表格"])


# ==================== 请求模型 ====================

class 表格请求体(BaseModel):
    name: str
    appToken: str
    tableId: str
    description: str = ""


# ==================== 辅助：ORM → dict ====================

def 表格转字典(record) -> dict:
    """把 ORM 对象转为前端需要的 camelCase 字典"""
    return {
        "id": record.id,
        "name": record.名称,
        "appToken": record.app_token,
        "tableId": record.table_id,
        "description": record.描述,
        "createdAt": record.创建时间.isoformat() if record.创建时间 else None,
        "updatedAt": record.更新时间.isoformat() if record.更新时间 else None,
    }


# ==================== 接口 ====================

@飞书表格路由.get("", response_model=统一响应)
async def 获取全部表格(数据库: Session = Depends(获取数据库)):
    """
    GET /api/feishu-tables
    返回所有飞书表格配置（按创建时间倒序）
    """
    所有表格 = (
        数据库.query(飞书表格模型)
        .order_by(飞书表格模型.创建时间.desc())
        .all()
    )
    return 统一响应(data=[表格转字典(t) for t in 所有表格])


@飞书表格路由.post("", response_model=统一响应)
async def 新增表格(请求体: 表格请求体, 数据库: Session = Depends(获取数据库)):
    """
    POST /api/feishu-tables
    新增飞书表格配置
    """
    if not 请求体.name.strip():
        return 统一响应(code=1, msg="表格名称不能为空")

    if not 请求体.appToken.strip():
        return 统一响应(code=1, msg="App Token 不能为空")

    if not 请求体.tableId.strip():
        return 统一响应(code=1, msg="Table ID 不能为空")
    已有表格 = 数据库.query(飞书表格模型).filter(飞书表格模型.名称 == 请求体.name.strip()).first()
    if 已有表格:
        return 统一响应(code=1, msg="表格名称已存在")

    新表格 = 飞书表格模型(
        id=str(uuid4()),
        名称=请求体.name.strip(),
        app_token=请求体.appToken.strip(),
        table_id=请求体.tableId.strip(),
        描述=请求体.description,
    )
    数据库.add(新表格)
    数据库.commit()
    数据库.refresh(新表格)
    return 统一响应(data=表格转字典(新表格), msg="表格已添加")


@飞书表格路由.put("/{record_id}", response_model=统一响应)
async def 更新表格(record_id: str, 请求体: 表格请求体, 数据库: Session = Depends(获取数据库)):
    """
    PUT /api/feishu-tables/{id}
    更新飞书表格配置
    """
    表格 = 数据库.query(飞书表格模型).filter(飞书表格模型.id == record_id).first()
    if not 表格:
        return 统一响应(code=1, msg="表格不存在")

    if not 请求体.name.strip():
        return 统一响应(code=1, msg="表格名称不能为空")
        
    已有表格 = 数据库.query(飞书表格模型).filter(飞书表格模型.名称 == 请求体.name.strip(),飞书表格模型.id != record_id).first()
    if 已有表格:
        return 统一响应(code=1, msg="表格名称已存在")

    表格.名称 = 请求体.name.strip()
    表格.app_token = 请求体.appToken.strip()
    表格.table_id = 请求体.tableId.strip()
    表格.描述 = 请求体.description
    表格.更新时间 = datetime.now()

    数据库.commit()
    数据库.refresh(表格)
    return 统一响应(data=表格转字典(表格), msg="表格已更新")


@飞书表格路由.delete("/{record_id}", response_model=统一响应)
async def 删除表格(record_id: str, 数据库: Session = Depends(获取数据库)):
    """
    DELETE /api/feishu-tables/{id}
    删除飞书表格配置
    """
    表格 = 数据库.query(飞书表格模型).filter(飞书表格模型.id == record_id).first()
    if not 表格:
        return 统一响应(code=1, msg="表格不存在")

    数据库.delete(表格)
    数据库.commit()
    return 统一响应(msg="表格已删除")