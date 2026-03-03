# app/api/工具.py
# 工具 CRUD + 测试接口
# ⚠️ 数据库会话统一用 Depends(获取数据库)
# ⚠️ 路径参数必须用英文名（FastAPI 不支持中文路径参数名）
# ⭐ 包含：重名校验 + 参数 properties 深度校验（type/description 必填）

import json
import time
from uuid import uuid4
from typing import Any, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.数据库 import 获取数据库
from app.db.模型 import 工具模型
from app.schemas import 统一响应


工具路由 = APIRouter(prefix="/api/tools", tags=["工具"])


# ==================== 请求模型 ====================

class 创建工具请求(BaseModel):
    name: str
    description: Optional[str] = ""
    tool_type: Optional[str] = "http_api"
    parameters: Optional[dict] = {}
    config: Optional[dict] = {}
    status: Optional[str] = "active"

    @field_validator("parameters", mode="before")
    @classmethod
    def 校验参数格式(cls, v):
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("parameters 必须是合法的 JSON 对象")
        if not isinstance(v, dict):
            raise ValueError("parameters 必须是 JSON 对象（dict），不能是数组或其他类型")
        return v

    @field_validator("config", mode="before")
    @classmethod
    def 校验配置格式(cls, v):
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("config 必须是合法的 JSON 对象")
        if not isinstance(v, dict):
            raise ValueError("config 必须是 JSON 对象（dict），不能是数组或其他类型")
        return v


class 更新工具请求(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tool_type: Optional[str] = None
    parameters: Optional[dict] = None
    config: Optional[dict] = None
    status: Optional[str] = None

    @field_validator("parameters", mode="before")
    @classmethod
    def 校验参数格式(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("parameters 必须是合法的 JSON 对象")
        if not isinstance(v, dict):
            raise ValueError("parameters 必须是 JSON 对象（dict），不能是数组或其他类型")
        return v

    @field_validator("config", mode="before")
    @classmethod
    def 校验配置格式(cls, v):
        if v is None:
            return None
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("config 必须是合法的 JSON 对象")
        if not isinstance(v, dict):
            raise ValueError("config 必须是 JSON 对象（dict），不能是数组或其他类型")
        return v


class 测试工具请求(BaseModel):
    test_params: Optional[dict] = {}


# ==================== 辅助函数 ====================

def 工具转字典(工具) -> dict:
    """将 ORM 对象转为前端需要的字典格式"""
    return {
        "id": 工具.id,
        "name": 工具.名称,
        "description": 工具.描述,
        "tool_type": 工具.类型,
        "parameters": json.loads(工具.参数定义) if isinstance(工具.参数定义, str) else 工具.参数定义,
        "config": json.loads(工具.配置) if isinstance(工具.配置, str) else 工具.配置,
        "status": 工具.状态,
        "created_at": 工具.创建时间.strftime("%Y-%m-%d %H:%M:%S") if 工具.创建时间 else "",
        "updated_at": 工具.更新时间.strftime("%Y-%m-%d %H:%M:%S") if 工具.更新时间 else "",
    }


def 深度校验参数定义(参数: dict) -> Optional[str]:
    """
    深度校验 parameters 字段：
    1. 必须包含 properties 键
    2. properties 内每个字段必须有 type 和 description
    返回 None 表示通过，否则返回错误信息
    """
    if not 参数:
        # 空字典允许通过（没有参数的工具）
        return None

    if "properties" not in 参数:
        return "参数定义格式错误，必须包含 properties 字段"

    属性 = 参数["properties"]
    if not isinstance(属性, dict):
        return "properties 必须是 JSON 对象"

    for 字段名, 字段信息 in 属性.items():
        if not isinstance(字段信息, dict):
            return f"参数 '{字段名}' 的定义必须是 JSON 对象"
        if "type" not in 字段信息:
            return f"参数 '{字段名}' 缺少 type 字段"
        if "description" not in 字段信息:
            return f"参数 '{字段名}' 缺少 description 字段"

    return None


# ==================== 接口（路径参数统一用英文 tool_id） ====================

@工具路由.get("", response_model=统一响应)
async def 获取工具列表(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    数据库: Session = Depends(获取数据库),
):
    查询 = 数据库.query(工具模型)
    if status:
        查询 = 查询.filter(工具模型.状态 == status)
    总数 = 查询.count()
    工具列表 = (
        查询.order_by(desc(工具模型.创建时间))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return 统一响应(data={
        "list": [工具转字典(t) for t in 工具列表],
        "total": 总数,
        "page": page,
        "page_size": page_size,
    })


@工具路由.post("", response_model=统一响应)
async def 创建工具(
    请求体: 创建工具请求,
    数据库: Session = Depends(获取数据库),
):
    # 1. 名称不能为空
    if not 请求体.name or not 请求体.name.strip():
        return 统一响应(code=1, msg="工具名称不能为空")

    # 2. ★ 重名校验
    已存在 = 数据库.query(工具模型).filter(工具模型.名称 == 请求体.name.strip()).first()
    if 已存在:
        return 统一响应(code=1, msg=f"工具名称 '{请求体.name.strip()}' 已存在，请换一个名称")

    # 3. ★ 参数深度校验（properties + type/description）
    if 请求体.parameters:
        校验结果 = 深度校验参数定义(请求体.parameters)
        if 校验结果:
            return 统一响应(code=1, msg=校验结果)

    # 4. 写入数据库
    新工具 = 工具模型(
        id=str(uuid4()),
        名称=请求体.name.strip(),
        描述=请求体.description or "",
        类型=请求体.tool_type or "http_api",
        参数定义=json.dumps(请求体.parameters or {}, ensure_ascii=False),
        配置=json.dumps(请求体.config or {}, ensure_ascii=False),
        状态=请求体.status or "active",
    )
    数据库.add(新工具)
    数据库.commit()
    数据库.refresh(新工具)
    return 统一响应(data=工具转字典(新工具))


@工具路由.get("/{tool_id}", response_model=统一响应)
async def 获取单个工具(
    tool_id: str,
    数据库: Session = Depends(获取数据库),
):
    工具 = 数据库.query(工具模型).filter(工具模型.id == tool_id).first()
    if not 工具:
        return 统一响应(code=1, msg="工具不存在")
    return 统一响应(data=工具转字典(工具))


@工具路由.put("/{tool_id}", response_model=统一响应)
async def 更新工具(
    tool_id: str,
    请求体: 更新工具请求,
    数据库: Session = Depends(获取数据库),
):
    工具 = 数据库.query(工具模型).filter(工具模型.id == tool_id).first()
    if not 工具:
        return 统一响应(code=1, msg="工具不存在")

    # 1. ★ 改名时重名校验（排除自己）
    if 请求体.name is not None and 请求体.name.strip() != 工具.名称:
        已存在 = 数据库.query(工具模型).filter(
            工具模型.名称 == 请求体.name.strip(),
            工具模型.id != tool_id
        ).first()
        if 已存在:
            return 统一响应(code=1, msg=f"工具名称 '{请求体.name.strip()}' 已存在，请换一个名称")

    # 2. ★ 参数深度校验（properties + type/description）
    if 请求体.parameters is not None and 请求体.parameters:
        校验结果 = 深度校验参数定义(请求体.parameters)
        if 校验结果:
            return 统一响应(code=1, msg=校验结果)

    # 3. 更新字段
    if 请求体.name is not None:
        工具.名称 = 请求体.name.strip()
    if 请求体.description is not None:
        工具.描述 = 请求体.description
    if 请求体.tool_type is not None:
        工具.类型 = 请求体.tool_type
    if 请求体.parameters is not None:
        工具.参数定义 = json.dumps(请求体.parameters, ensure_ascii=False)
    if 请求体.config is not None:
        工具.配置 = json.dumps(请求体.config, ensure_ascii=False)
    if 请求体.status is not None:
        工具.状态 = 请求体.status

    工具.更新时间 = datetime.now()
    数据库.commit()
    数据库.refresh(工具)
    return 统一响应(data=工具转字典(工具))


@工具路由.delete("/{tool_id}", response_model=统一响应)
async def 删除工具(
    tool_id: str,
    数据库: Session = Depends(获取数据库),
):
    工具 = 数据库.query(工具模型).filter(工具模型.id == tool_id).first()
    if 工具:
        工具名称 = 工具.名称

        # 删除工具
        数据库.delete(工具)
        数据库.commit()

        # ⭐ 清理所有 Agent 的 tools 字段中对该工具的引用
        from app.db.模型 import Agent模型
        所有agents = 数据库.query(Agent模型).all()

        for agent in 所有agents:
            try:
                工具列表 = json.loads(agent.工具列表) if isinstance(agent.工具列表, str) else (agent.工具列表 or [])
                if not isinstance(工具列表, list):
                    continue

                # 移除已删除工具的名称和ID
                原始长度 = len(工具列表)
                工具列表 = [t for t in 工具列表 if t != tool_id and t != 工具名称]

                # 如果有变化则更新
                if len(工具列表) != 原始长度:
                    agent.工具列表 = json.dumps(工具列表, ensure_ascii=False)
                    agent.更新时间 = datetime.now()
            except Exception as e:
                # 单个 Agent 清理失败不影响整体
                continue

        数据库.commit()

    return 统一响应()


@工具路由.post("/{tool_id}/test", response_model=统一响应)
async def 测试工具(
    tool_id: str,
    请求体: 测试工具请求,
    数据库: Session = Depends(获取数据库),
):
    工具 = 数据库.query(工具模型).filter(工具模型.id == tool_id).first()
    if not 工具:
        return 统一响应(code=1, msg="工具不存在")

    配置 = json.loads(工具.配置) if isinstance(工具.配置, str) else 工具.配置
    工具类型 = 工具.类型
    测试参数 = 请求体.test_params or {}
    开始时间 = time.time()

    try:
        if 工具类型 == "http_api":
            from app.图引擎.工具加载器 import 执行HTTP工具
            结果 = await 执行HTTP工具(配置, 测试参数)
            成功 = True
        elif 工具类型 == "python_code":
            from app.图引擎.工具加载器 import 执行Python工具
            结果 = 执行Python工具(配置, 测试参数)
            成功 = not 结果.startswith("错误") and not 结果.startswith("Python 执行错误")
        else:
            结果 = f"不支持的工具类型: {工具类型}"
            成功 = False
    except Exception as e:
        结果 = f"执行异常: {str(e)}"
        成功 = False

    耗时 = int((time.time() - 开始时间) * 1000)
    return 统一响应(data={"success": 成功, "result": 结果, "duration_ms": 耗时})