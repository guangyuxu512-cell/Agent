from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import jwt

from app.配置 import 密钥, 令牌过期小时数, 令牌算法
from app.db.数据库 import 获取数据库, 密码工具
from app.db.模型 import 用户模型
from app.schemas import 统一响应
from app.密码策略 import 检查密码强度, 是否为弱口令

路由 = APIRouter(prefix="/api/auth", tags=["鉴权"])


# ========== 请求模型 ==========

class 登录请求(BaseModel):
    username: str
    password: str


class 修改密码请求(BaseModel):
    old_password: str
    new_password: str


# ========== 工具函数 ==========

def 生成令牌(数据: dict) -> str:
    """生成 JWT Token"""
    过期时间 = datetime.now(timezone.utc) + timedelta(hours=令牌过期小时数)
    载荷 = {**数据, "exp": 过期时间}
    return jwt.encode(载荷, 密钥, algorithm=令牌算法)


# ========== 接口 ==========

@路由.post("/login", response_model=统一响应)
async def 登录(请求体: 登录请求, 数据库: Session = Depends(获取数据库)):
    """用户登录，返回 JWT Token + force_change_password 标志"""
    用户 = 数据库.query(用户模型).filter(用户模型.用户名 == 请求体.username).first()

    if not 用户 or not 密码工具.verify(请求体.password, 用户.密码哈希):
        return 统一响应(code=1, msg="用户名或密码错误")

    # 检查是否为弱口令
    force_change = 是否为弱口令(请求体.password)

    令牌 = 生成令牌({"sub": 用户.用户名})
    return 统一响应(data={
        "token": 令牌,
        "force_change_password": force_change
    })


@路由.post("/change-password", response_model=统一响应)
async def 修改密码(请求体: 修改密码请求, request: Request, 数据库: Session = Depends(获取数据库)):
    """修改密码（需要登录）"""
    # 从 request.state 获取当前用户名（由鉴权中间件设置）
    username = getattr(request.state, "username", None)
    if not username:
        return 统一响应(code=1, msg="未授权")

    用户 = 数据库.query(用户模型).filter(用户模型.用户名 == username).first()
    if not 用户:
        return 统一响应(code=1, msg="用户不存在")

    # 验证旧密码
    if not 密码工具.verify(请求体.old_password, 用户.密码哈希):
        return 统一响应(code=1, msg="旧密码错误")

    # 检查新密码强度
    is_strong, error_msg = 检查密码强度(请求体.new_password)
    if not is_strong:
        return 统一响应(code=1, msg=f"新密码不符合安全要求：{error_msg}")

    # 更新密码
    用户.密码哈希 = 密码工具.hash(请求体.new_password)
    数据库.commit()

    return 统一响应(msg="密码修改成功")