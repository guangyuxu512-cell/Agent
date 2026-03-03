# app/启动器.py
# FastAPI 入口 — 挂载中间件、注册路由、健康检查
# ⭐ 问题7修复：新增 RequestValidationError 异常处理器
# ⭐ Windows asyncio 修复：使用 WindowsSelectorEventLoopPolicy 避免 [Errno 22]

import sys
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import logging

# ⭐ 日志配置：同时输出到控制台和文件
# 强制刷新日志，避免缓冲导致日志丢失
file_handler = logging.FileHandler('backend.log', encoding='utf-8', mode='a')
file_handler.setLevel(logging.INFO)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
    handlers=[stream_handler, file_handler],
    force=True
)

# 强制刷新所有日志输出
for handler in logging.root.handlers:
    handler.flush = lambda: handler.stream.flush() if hasattr(handler, 'stream') else None

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.db.数据库 import 初始化数据库
from app.api.鉴权 import 路由 as 鉴权路由
from app.api.智能体 import 智能体路由
from app.api.对话 import 对话路由                    # Step 3 新增
from app.api.工具 import 工具路由                    # Step 4 新增
from app.api.系统配置 import 配置路由                  # 系统配置
from app.middleware.鉴权中间件 import 鉴权中间件
from app.schemas import 统一响应
from app.配置 import CORS_ORIGINS, APP_ENV, DISABLE_DOCS_IN_PROD
from app.api.飞书表格 import 飞书表格路由
from app.飞书 import 启动飞书长连接
from app.api.记忆 import 记忆路由
from app.api.日志推流 import 日志推流路由              # 影刀推流（X-RPA-KEY 鉴权）
from app.api.编排 import 编排路由
from app.api.定时任务 import 定时任务路由
from app.api.机器管理 import 机器管理路由              # 影刀机器管理
from app.调度器 import 启动调度器, 关闭调度器

logger = logging.getLogger(__name__)


# ========== 内置工具自动注册 ==========

def 清理Agent工具引用():
    """启动时清理所有 Agent 的 tools 字段，移除不存在的工具引用"""
    from app.db.数据库 import 会话工厂
    from app.db.模型 import Agent模型, 工具模型
    import json

    db = 会话工厂()
    try:
        # 获取所有存在的工具名称和ID
        所有工具 = db.query(工具模型).all()
        有效工具名称 = {t.名称 for t in 所有工具}
        有效工具ID = {t.id for t in 所有工具}

        # 扫描所有 Agent
        所有agents = db.query(Agent模型).all()
        清理计数 = 0

        for agent in 所有agents:
            try:
                工具列表 = json.loads(agent.工具列表) if isinstance(agent.工具列表, str) else (agent.工具列表 or [])
                if not isinstance(工具列表, list):
                    continue

                # 过滤出存在的工具（按名称或ID）
                原始长度 = len(工具列表)
                工具列表 = [t for t in 工具列表 if t in 有效工具名称 or t in 有效工具ID]

                # 如果有变化则更新
                if len(工具列表) != 原始长度:
                    agent.工具列表 = json.dumps(工具列表, ensure_ascii=False)
                    清理计数 += 1
                    logger.info(f"[启动] 清理 Agent '{agent.名称}' 的无效工具引用")
            except Exception as e:
                logger.warning(f"[启动] 清理 Agent '{agent.名称}' 工具引用失败: {e}")
                continue

        if 清理计数 > 0:
            db.commit()
            logger.info(f"[启动] 工具引用清理完成，共清理 {清理计数} 个 Agent")
    except Exception as e:
        db.rollback()
        logger.error(f"[启动] 清理工具引用失败: {e}", exc_info=True)
    finally:
        db.close()


def 注册内置工具():
    """启动时自动注册内置工具到工具表"""
    from app.db.数据库 import 会话工厂
    from app.db.模型 import 工具模型
    import json
    import uuid

    # 内置工具定义
    内置工具列表 = [
        {
            "name": "发送邮件",
            "tool_type": "builtin",
            "description": "通过 SMTP 发送邮件，支持 HTML 格式正文",
            "parameters": {
                "type": "object",
                "properties": {
                    "收件人": {
                        "type": "string",
                        "description": "收件人邮箱地址"
                    },
                    "主题": {
                        "type": "string",
                        "description": "邮件主题"
                    },
                    "正文": {
                        "type": "string",
                        "description": "邮件正文内容，支持 HTML 格式"
                    }
                },
                "required": ["收件人", "主题", "正文"]
            },
            "config": {
                "builtin_name": "send_email"
            },
            "status": "active"
        },
        {
            "name": "飞书助手",
            "tool_type": "builtin",
            "description": "飞书操作助手，支持发送消息、读取表格、写入表格等操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "操作类型": {
                        "type": "string",
                        "description": "操作类型，可选值：发消息、读表格、写表格",
                        "enum": ["发消息", "读表格", "写表格"]
                    },
                    "参数": {
                        "type": "string",
                        "description": "操作参数，JSON格式字符串。发消息: {\"open_id\": \"xxx\", \"内容\": \"xxx\"}；读表格: {\"表格名称\": \"拼多多店铺\"}；写表格: {\"表格名称\": \"拼多多店铺\", \"数据\": {\"店铺名称\": \"测试\", \"状态\": \"正常\"}}"
                    }
                },
                "required": ["操作类型", "参数"]
            },
            "config": {
                "builtin_name": "feishu_assistant"
            },
            "status": "active"
        }
    ]

    db = 会话工厂()
    try:
        for 工具定义 in 内置工具列表:
            # 检查工具是否已存在（使用中文列名）
            existing = db.query(工具模型).filter(
                工具模型.名称 == 工具定义["name"],
                工具模型.类型 == "builtin"
            ).first()

            if not existing:
                # 创建新的内置工具
                新工具 = 工具模型(
                    id=str(uuid.uuid4()),
                    名称=工具定义["name"],
                    类型=工具定义["tool_type"],
                    描述=工具定义["description"],
                    参数定义=json.dumps(工具定义["parameters"], ensure_ascii=False),
                    配置=json.dumps(工具定义["config"], ensure_ascii=False),
                    状态=工具定义["status"]
                )
                db.add(新工具)
                logger.info(f"[启动] 注册内置工具: {工具定义['name']}")

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[启动] 注册内置工具失败: {e}", exc_info=True)
    finally:
        db.close()


# ========== 生命周期（启动时初始化数据库） ==========

@asynccontextmanager
async def 生命周期(app: FastAPI):
    初始化数据库()
    注册内置工具()  # 自动注册内置工具
    清理Agent工具引用()  # 清理无效的工具引用
    启动飞书长连接()
    await 启动调度器()
    logger.info("[启动] FastAPI 后端已启动，端口 8001")
    yield
    await 关闭调度器()
    logger.info("[关闭] FastAPI 后端已关闭")


# ========== 创建 FastAPI 实例 ==========

# ⭐ P0 安全：生产环境禁用 API 文档
_docs_url = None if (APP_ENV == "prod" and DISABLE_DOCS_IN_PROD) else "/docs"
_redoc_url = None if (APP_ENV == "prod" and DISABLE_DOCS_IN_PROD) else "/redoc"
_openapi_url = None if (APP_ENV == "prod" and DISABLE_DOCS_IN_PROD) else "/openapi.json"

app = FastAPI(
    title="Agent 后端",
    version="0.5.0",
    lifespan=生命周期,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url
)


# ========== ⭐ 异常处理（问题7核心修复） ==========

@app.exception_handler(RequestValidationError)
async def 参数校验异常处理(request, exc):
    errors = exc.errors()
    if errors:
        第一个错误 = errors[0]
        字段路径 = " → ".join(
            str(loc) for loc in 第一个错误.get("loc", [])
            if loc != "body"
        )
        错误消息 = 第一个错误.get("msg", "参数格式错误")
        if 字段路径:
            msg = f"字段 {字段路径} 校验失败：{错误消息}"
        else:
            msg = 错误消息
    else:
        msg = "请求参数格式错误"

    return JSONResponse(
        status_code=200,
        content={"code": 1, "data": None, "msg": msg}
    )


# ========== 中间件 ==========

# 1. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=("*" not in CORS_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. JWT 鉴权
app.add_middleware(鉴权中间件)


# ========== 注册路由 ==========

app.include_router(鉴权路由)
app.include_router(智能体路由)
app.include_router(对话路由)                                # Step 3 新增
app.include_router(工具路由)                                # Step 4 新增
app.include_router(配置路由)                                # 系统配置
app.include_router(飞书表格路由)
app.include_router(记忆路由)
app.include_router(日志推流路由)                            # 影刀推流（X-RPA-KEY 鉴权）
app.include_router(编排路由)
app.include_router(定时任务路由)                            # Step 4 新增
app.include_router(机器管理路由)                            # 影刀机器管理

# ========== 健康检查 ==========

@app.get("/api/health")
async def 健康检查():
    return 统一响应()