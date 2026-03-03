# app/schemas.py
# 全局共享的响应模型

from typing import Any
from pydantic import BaseModel


class 统一响应(BaseModel):
    code: int = 0
    data: Any = None
    msg: str = "ok"
