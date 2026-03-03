# app/api/记忆.py
# Step 6：记忆 CRUD 路由

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.数据库 import 获取数据库
from app.db.模型 import 记忆模型


记忆路由 = APIRouter(tags=["记忆"])


def _记忆转字典(记忆):
    return {
        "id": 记忆.id,
        "agent_id": 记忆.agent_id,
        "conversation_id": 记忆.conversation_id,
        "memory_type": 记忆.记忆类型,
        "content": 记忆.内容,
        "importance": 记忆.重要性,
        "created_at": 记忆.创建时间.strftime("%Y-%m-%d %H:%M:%S") if 记忆.创建时间 else "",
        "expires_at": 记忆.过期时间.strftime("%Y-%m-%d %H:%M:%S") if 记忆.过期时间 else None,
    }


@记忆路由.get("/api/memories")
async def 获取记忆列表(
    agent_id: str = None,
    memory_type: str = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(获取数据库),
):
    """获取记忆列表，支持按 agent_id 和 memory_type 过滤"""
    查询 = db.query(记忆模型)

    if agent_id:
        查询 = 查询.filter(记忆模型.agent_id == agent_id)
    if memory_type:
        查询 = 查询.filter(记忆模型.记忆类型 == memory_type)

    总数 = 查询.count()

    记忆们 = (
        查询
        .order_by(desc(记忆模型.重要性), desc(记忆模型.创建时间))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "code": 0,
        "data": {
            "list": [_记忆转字典(m) for m in 记忆们],
            "total": 总数,
            "page": page,
            "page_size": page_size,
        },
        "msg": "ok",
    }


@记忆路由.delete("/api/memories/{memory_id}")
async def 删除记忆(
    memory_id: str,
    db: Session = Depends(获取数据库),
):
    """删除一条记忆"""
    db.query(记忆模型).filter(记忆模型.id == memory_id).delete()
    db.commit()
    return {"code": 0, "data": None, "msg": "ok"}


@记忆路由.delete("/api/memories")
async def 清空记忆(
    agent_id: str,
    db: Session = Depends(获取数据库),
):
    """清空某个 Agent 的所有记忆"""
    删除数 = db.query(记忆模型).filter(记忆模型.agent_id == agent_id).delete()
    db.commit()
    return {"code": 0, "data": {"deleted": 删除数}, "msg": "ok"}