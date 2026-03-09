import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from jose import jwt, JWTError

from app.配置 import 密钥, 令牌算法

# 不需要鉴权的路径
免鉴权路径 = [
    "/api/auth/login",
    # "/api/auth/change-password",  # ⭐ 修复：修改密码需要鉴权，移除免鉴权
    "/api/health",
    "/api/logs/push",  # 影刀推流（自行验证 X-RPA-KEY）
    "/api/logs/stream",  # SSE 端点自行验证 query token（EventSource 无法发 header）
    "/api/workers/register",
    "/api/workers/heartbeat",
    "/docs",
    "/openapi.json",
    "/redoc",
]


def _构造401响应() -> Response:
    """返回统一格式的 401 响应"""
    return Response(
        content=json.dumps({"code": 401, "data": None, "msg": "未授权"}, ensure_ascii=False),
        status_code=401,
        media_type="application/json"
    )


class 鉴权中间件(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        路径 = request.url.path

        # 跳过免鉴权路径
        for 免鉴权 in 免鉴权路径:
            if 路径.startswith(免鉴权):
                return await call_next(request)

        # 跳过 OPTIONS 预检请求（CORS）
        if request.method == "OPTIONS":
            return await call_next(request)

        # 提取 Token
        授权头 = request.headers.get("Authorization", "")
        if not 授权头.startswith("Bearer "):
            return _构造401响应()

        令牌 = 授权头[7:]  # 去掉 "Bearer " 前缀

        # 验证 Token
        try:
            载荷 = jwt.decode(令牌, 密钥, algorithms=[令牌算法])
            # 把用户信息存到 request.state，后续接口可以用
            request.state.username = 载荷.get("sub", "")
        except JWTError:
            return _构造401响应()

        return await call_next(request)
