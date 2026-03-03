"""Agent CRUD 接口（适配前端版）
文件：app/api/智能体.py
路径前缀：/api/agents

JSON key 使用前端 camelCase 命名：
  name, role, prompt, llmProvider, llmModel, llmApiUrl, llmApiKey,
  temperature, tools, maxIterations, timeout, requireApproval, status, updateTime
"""

import json
from uuid import uuid4
from typing import Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.数据库 import 获取数据库
from app.db.模型 import Base,Agent模型
from app.加密 import 加密, 解密
from app.schemas import 统一响应


智能体路由 = APIRouter(prefix="/api/agents", tags=["智能体管理"])


# ========== 请求模型（camelCase，匹配前端 formData） ==========

class 创建Agent请求(BaseModel):
    name: str
    role: Optional[str] = ""
    prompt: Optional[str] = ""
    llmProvider: Optional[str] = "OpenAI"
    llmModel: Optional[str] = "GPT-4o"
    llmApiUrl: Optional[str] = ""
    llmApiKey: Optional[str] = ""
    temperature: Optional[float] = 0.7
    tools: Optional[List[str]] = []
    maxIterations: Optional[int] = 10
    timeout: Optional[int] = 60
    requireApproval: Optional[bool] = False
    status: Optional[str] = "stopped"


class 更新Agent请求(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    prompt: Optional[str] = None
    llmProvider: Optional[str] = None
    llmModel: Optional[str] = None
    llmApiUrl: Optional[str] = None
    llmApiKey: Optional[str] = None
    temperature: Optional[float] = None
    tools: Optional[List[str]] = None
    maxIterations: Optional[int] = None
    timeout: Optional[int] = None
    requireApproval: Optional[bool] = None
    status: Optional[str] = None


# ========== 序列化（ORM → 前端 JSON） ==========

def _序列化(agent: Agent模型) -> dict:
    """把 ORM 对象转成前端需要的 camelCase 字典"""
    return {
        "id": agent.id,
        "name": agent.名称,
        "role": agent.角色 or "",
        "prompt": agent.提示词 or "",
        "llmProvider": agent.提供商 or "OpenAI",
        "llmModel": agent.模型名称 or "GPT-4o",
        "llmApiUrl": agent.接口地址 or "",
        "llmApiKey": 解密(agent.接口密钥 or ""),
        "temperature": agent.温度 if agent.温度 is not None else 0.7,
        "tools": json.loads(agent.工具列表 or "[]"),
        "maxIterations": agent.最大迭代 or 10,
        "timeout": agent.超时时间 or 60,
        "requireApproval": bool(agent.需要审批),
        "status": agent.状态 or "stopped",
        "updateTime": agent.更新时间.strftime("%Y-%m-%d %H:%M:%S") if agent.更新时间 else "",
    }


# ========== 路由 ==========

@智能体路由.get("")
async def 获取Agent列表(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    数据库: Session = Depends(获取数据库),
):
    """获取 Agent 列表（分页 + 状态筛选）"""
    查询 = 数据库.query(Agent模型)
    if status:
        查询 = 查询.filter(Agent模型.状态 == status)
    总数 = 查询.count()
    列表 = 查询.order_by(Agent模型.创建时间.desc()) \
               .offset((page - 1) * page_size) \
               .limit(page_size).all()
    return 统一响应(data={
        "list": [_序列化(a) for a in 列表],
        "total": 总数,
        "page": page,
        "page_size": page_size,
    })


@智能体路由.post("")
async def 创建Agent(请求体: 创建Agent请求, 数据库: Session = Depends(获取数据库)):
    """创建新 Agent"""
    if not 请求体.name or not 请求体.name.strip():
        return 统一响应(code=1, msg="Agent 名称不能为空")
    # 重名校验
    已存在 = 数据库.query(Agent模型).filter(Agent模型.名称 == 请求体.name.strip()).first()
    if 已存在:
        return 统一响应(code=1, msg=f"已存在同名智能体「{请求体.name.strip()}」，请换个名称")

    新Agent = Agent模型(
        id=str(uuid4()),
        名称=请求体.name.strip(),
        角色=请求体.role or "",
        提示词=请求体.prompt or "",
        提供商=请求体.llmProvider or "OpenAI",
        模型名称=请求体.llmModel or "GPT-4o",
        接口地址=请求体.llmApiUrl or "",
        接口密钥=加密(请求体.llmApiKey or ""),
        温度=请求体.temperature if 请求体.temperature is not None else 0.7,
        工具列表=json.dumps(请求体.tools or [], ensure_ascii=False),
        最大迭代=请求体.maxIterations or 10,
        超时时间=请求体.timeout or 60,
        需要审批=请求体.requireApproval or False,
        状态=请求体.status or "stopped",
        创建时间=datetime.now(),
        更新时间=datetime.now(),
    )
    数据库.add(新Agent)
    数据库.commit()
    数据库.refresh(新Agent)
    return 统一响应(data=_序列化(新Agent))


@智能体路由.get("/{agent_id}")
async def 获取Agent详情(agent_id: str, 数据库: Session = Depends(获取数据库)):
    """获取单个 Agent"""
    agent = 数据库.query(Agent模型).filter(Agent模型.id == agent_id).first()
    if not agent:
        return 统一响应(code=1, msg="Agent不存在")
    return 统一响应(data=_序列化(agent))


@智能体路由.put("/{agent_id}")
async def 更新Agent(agent_id: str, 请求体: 更新Agent请求, 数据库: Session = Depends(获取数据库)):
    """更新 Agent（只更新传入的字段）"""
    agent = 数据库.query(Agent模型).filter(Agent模型.id == agent_id).first()
    if not agent:
        return 统一响应(code=1, msg="Agent不存在")

    # 字段映射：JSON camelCase → ORM 中文属性
    映射 = {
        "name": "名称", "role": "角色", "prompt": "提示词",
        "llmProvider": "提供商", "llmModel": "模型名称",
        "llmApiUrl": "接口地址", "llmApiKey": "接口密钥",
        "temperature": "温度", "maxIterations": "最大迭代",
        "timeout": "超时时间", "requireApproval": "需要审批",
        "status": "状态",
    }

    更新数据 = 请求体.model_dump(exclude_unset=True)
    for 英文键, 中文属性 in 映射.items():
        if 英文键 in 更新数据 and 更新数据[英文键] is not None:
            值 = 更新数据[英文键]
            if 英文键 == "llmApiKey":
                值 = 加密(值)
            setattr(agent, 中文属性, 值)

    # tools 单独处理（需要 JSON 序列化）
    if "tools" in 更新数据 and 更新数据["tools"] is not None:
        agent.工具列表 = json.dumps(更新数据["tools"], ensure_ascii=False)

    agent.更新时间 = datetime.now()
    数据库.commit()
    数据库.refresh(agent)
    return 统一响应(data=_序列化(agent))


@智能体路由.delete("/{agent_id}")
async def 删除Agent(agent_id: str, 数据库: Session = Depends(获取数据库)):
    """删除 Agent（幂等）"""
    agent = 数据库.query(Agent模型).filter(Agent模型.id == agent_id).first()
    if agent:
        数据库.delete(agent)
        数据库.commit()
    return 统一响应()