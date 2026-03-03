# app/api/编排.py
# 编排配置 GET/POST — 全局单例（id="default"）

import json
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.db.数据库 import 获取数据库
from app.db.模型 import 编排模型

编排路由 = APIRouter(prefix="/api", tags=["编排"])


class 全局状态项(BaseModel):
    key: str
    desc: str


class 编排请求(BaseModel):
    mode: str = "Supervisor"
    entryAgent: str = ""
    routingRules: str = ""
    parallelGroups: str = ""
    globalState: list[全局状态项] = []


@编排路由.get("/orchestration")
async def 获取编排配置(db: Session = Depends(获取数据库)):
    记录 = db.query(编排模型).filter(编排模型.id == "default").first()
    if not 记录:
        return {"code": 0, "data": None, "msg": "ok"}
    return {
        "code": 0,
        "data": {
            "mode": 记录.模式,
            "entryAgent": 记录.入口agent_id or "",
            "routingRules": 记录.路由规则 or "",
            "parallelGroups": 记录.并行分组 or "",
            "globalState": json.loads(记录.全局状态 or "[]"),
        },
        "msg": "ok",
    }


@编排路由.post("/orchestration")
async def 保存编排配置(data: 编排请求, db: Session = Depends(获取数据库)):
    记录 = db.query(编排模型).filter(编排模型.id == "default").first()
    if not 记录:
        记录 = 编排模型(id="default")
        db.add(记录)
    记录.模式 = data.mode
    记录.入口agent_id = data.entryAgent
    记录.路由规则 = data.routingRules
    记录.并行分组 = data.parallelGroups
    记录.全局状态 = json.dumps(
        [item.model_dump() for item in data.globalState],
        ensure_ascii=False,
    )
    db.commit()
    return {"code": 0, "msg": "ok"}
