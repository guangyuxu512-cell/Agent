# app/api/日志推流.py
# 影刀日志推流 — X-RPA-KEY 鉴权方案
# POST /api/logs/push — 校验 X-RPA-KEY 请求头
# GET /api/logs/stream — SSE 推流（JWT 鉴权）
# GET /api/logs/history — 历史日志（JWT 鉴权）

import asyncio
import collections
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, Header
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.数据库 import 获取数据库, 会话工厂
from app.db.模型 import 推送日志模型, 机器模型
from app.常量 import LOG_RETENTION_DAYS, LOG_HISTORY_LIMIT, LOG_DEFAULT_PAGE_SIZE
from app.配置 import RPA密钥
from app.schemas import 统一响应

logger = logging.getLogger(__name__)

日志推流路由 = APIRouter(prefix="/api/logs", tags=["日志推流"])

# ========== 广播模式：asyncio.Queue + deque 缓冲区 ==========

# 所有 SSE 客户端的队列集合
_sse_clients: set[asyncio.Queue] = set()

# 历史日志缓冲区（最近 500 条）
_log_buffer: collections.deque = collections.deque(maxlen=500)

# 推送审计统计
_push_stats = {
    "total": 0,
    "last_push_at": None,
    "last_ip": None,
    "last_ua": None,
    "last_task_id": None,
    "last_machine": None,
}


# ========== 请求模型 ==========

class 日志推送请求(BaseModel):
    time: Optional[str] = None
    task_id: Optional[str] = "未知任务"
    machine: Optional[str] = "未知设备"
    level: Optional[str] = "进行中"
    msg: str


# ========== 工具函数 ==========

def _日志转字典(记录: 推送日志模型) -> dict:
    """将数据库记录转为字典"""
    return {
        "seq": 记录.id,
        "time": 记录.时间 or "",
        "task_id": 记录.任务ID or "未知任务",
        "machine": 记录.设备 or "未知设备",
        "level": 记录.级别 or "进行中",
        "msg": 记录.消息 or "",
    }


async def _广播日志(日志字典: dict):
    """广播日志到所有 SSE 客户端"""
    if not _sse_clients:
        return

    # 将日志放入所有客户端队列
    死亡队列 = []
    for client_queue in _sse_clients:
        try:
            client_queue.put_nowait(日志字典)
        except asyncio.QueueFull:
            # 队列满了，标记为死亡
            死亡队列.append(client_queue)
        except Exception as e:
            logger.warning("广播日志失败: %s", e)
            死亡队列.append(client_queue)

    # 清理死亡队列
    for dead in 死亡队列:
        _sse_clients.discard(dead)


# ========== 接口 ==========

@日志推流路由.post("/push")
async def push_log(
    请求体: 日志推送请求,
    request: Request,
    x_rpa_key: Optional[str] = Header(None, alias="X-RPA-KEY")
):
    """推送日志（X-RPA-KEY 鉴权）

    请求头：
        X-RPA-KEY: 影刀推流密钥（环境变量 RPA_PUSH_KEY）

    请求体：
        {
            "time": "2026-03-01 12:00:00",  // 可选
            "task_id": "task_123",          // 可选
            "machine": "PC-001",            // 可选
            "level": "进行中",               // 可选
            "msg": "日志内容"                // 必填
        }

    返回：
        {"code": 0, "data": {"seq": 123}, "msg": "ok"}
    """
    # ========== X-RPA-KEY 鉴权 ==========
    if not x_rpa_key:
        logger.warning("推送日志失败：缺少 X-RPA-KEY 请求头")
        return JSONResponse(
            status_code=403,
            content={"code": 403, "data": None, "msg": "缺少 X-RPA-KEY 请求头"}
        )

    if x_rpa_key != RPA密钥:
        logger.warning("推送日志失败：X-RPA-KEY 错误 (收到: %s...)", x_rpa_key[:10])
        return JSONResponse(
            status_code=403,
            content={"code": 403, "data": None, "msg": "X-RPA-KEY 错误"}
        )

    # ========== 审计日志 ==========
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    logger.info(
        "LOG_PUSH from %s ua=%s task_id=%s machine=%s",
        client_ip, user_agent, 请求体.task_id, 请求体.machine,
    )

    # ========== 更新统计 ==========
    now = datetime.now(timezone.utc)
    _push_stats["total"] += 1
    _push_stats["last_push_at"] = now.isoformat()
    _push_stats["last_ip"] = client_ip
    _push_stats["last_ua"] = user_agent
    _push_stats["last_task_id"] = 请求体.task_id
    _push_stats["last_machine"] = 请求体.machine

    # ========== 持久化到数据库 ==========
    db = 会话工厂()
    try:
        新日志 = 推送日志模型(
            时间=请求体.time or time.strftime("%Y-%m-%d %H:%M:%S"),
            任务ID=请求体.task_id or "未知任务",
            设备=请求体.machine or "未知设备",
            级别=请求体.level or "进行中",
            消息=请求体.msg,
        )
        db.add(新日志)
        db.commit()
        db.refresh(新日志)

        日志字典 = _日志转字典(新日志)

        # 添加到缓冲区
        _log_buffer.append(日志字典)

        # 广播到所有 SSE 客户端
        await _广播日志(日志字典)

        # ========== 更新机器状态 ==========
        machine_id = 请求体.machine
        level = 请求体.level or "进行中"

        if machine_id and machine_id != "未知设备":
            try:
                # 查询机器是否存在
                机器 = db.query(机器模型).filter(机器模型.机器码 == machine_id).first()

                if 机器:
                    # 根据日志级别更新机器状态
                    if "进行中" in level or "执行中" in level:
                        机器.状态 = "running"
                    elif "完成" in level or "成功" in level:
                        机器.状态 = "idle"
                    elif "失败" in level or "异常" in level:
                        机器.状态 = "error"

                    # 更新最后心跳时间
                    机器.最后心跳 = datetime.now()
                    机器.更新时间 = datetime.now()
                    db.commit()

                    logger.debug(f"更新机器状态: {machine_id} -> {机器.状态}")
            except Exception as e:
                logger.warning(f"更新机器状态失败: {e}")
                # 不影响日志推送，继续执行

        return 统一响应(data={"seq": 新日志.id})

    except Exception as e:
        db.rollback()
        logger.error("推送日志失败: %s", e, exc_info=True)
        return 统一响应(code=1, msg=f"推送日志失败: {str(e)}")
    finally:
        db.close()


@日志推流路由.get("/stream")
async def log_stream(
    request: Request,
    task_id: Optional[str] = Query(None, description="任务ID过滤"),
    since_seq: int = Query(0, description="从哪个 seq 开始（不含）"),
):
    """SSE 日志推流（JWT 鉴权）

    查询参数：
        task_id: 可选，过滤指定任务的日志
        since_seq: 从哪个 seq 开始推送（不含该 seq）

    返回：
        SSE 流，每条消息格式：
        data: {"seq": 123, "time": "...", "task_id": "...", "machine": "...", "level": "...", "msg": "..."}

    注意：
        - 此接口走 JWT 鉴权中间件，需要 Authorization: Bearer <token>
        - 客户端断开连接后自动清理
    """
    # 创建客户端队列
    client_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_clients.add(client_queue)

    async def event_generator():
        try:
            # 1. 发送历史日志（从缓冲区）
            for log in _log_buffer:
                if log["seq"] <= since_seq:
                    continue
                if task_id and log.get("task_id") != task_id:
                    continue
                yield f"data: {json.dumps(log, ensure_ascii=False)}\n\n"

            # 2. 发送心跳
            yield f"data: {json.dumps({'type': 'heartbeat', 'time': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)}\n\n"

            # 3. 实时推送新日志
            while True:
                try:
                    # 等待新日志（30秒超时，用于发送心跳）
                    log = await asyncio.wait_for(client_queue.get(), timeout=30.0)

                    # 过滤
                    if log["seq"] <= since_seq:
                        continue
                    if task_id and log.get("task_id") != task_id:
                        continue

                    yield f"data: {json.dumps(log, ensure_ascii=False)}\n\n"

                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f"data: {json.dumps({'type': 'heartbeat', 'time': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)}\n\n"

        except asyncio.CancelledError:
            logger.info("SSE 客户端断开连接")
        except Exception as e:
            logger.error("SSE 推流错误: %s", e, exc_info=True)
        finally:
            # 清理客户端队列
            _sse_clients.discard(client_queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 禁用缓冲
        }
    )


@日志推流路由.get("/history", response_model=统一响应)
async def log_history(
    task_id: Optional[str] = Query(None, description="任务ID过滤"),
    since_seq: int = Query(0, description="从哪个 seq 开始（不含）"),
    limit: int = Query(LOG_DEFAULT_PAGE_SIZE, description="返回条数", le=LOG_HISTORY_LIMIT),
    数据库: Session = Depends(获取数据库),
):
    """查询历史日志（JWT 鉴权）

    查询参数：
        task_id: 可选，过滤指定任务的日志
        since_seq: 从哪个 seq 开始（不含该 seq）
        limit: 返回条数（默认 50，最大 1000）

    返回：
        {
            "code": 0,
            "data": {
                "logs": [
                    {"seq": 123, "time": "...", "task_id": "...", "machine": "...", "level": "...", "msg": "..."},
                    ...
                ],
                "total": 100,
                "has_more": true
            },
            "msg": "ok"
        }

    注意：
        - 此接口走 JWT 鉴权中间件，需要 Authorization: Bearer <token>
    """
    try:
        # 构建查询
        query = 数据库.query(推送日志模型).filter(推送日志模型.id > since_seq)

        if task_id:
            query = query.filter(推送日志模型.任务ID == task_id)

        # 总数
        total = query.count()

        # 分页查询（按 seq 倒序）
        记录列表 = query.order_by(desc(推送日志模型.id)).limit(limit).all()

        # 转换为字典
        logs = [_日志转字典(记录) for 记录 in 记录列表]

        return 统一响应(data={
            "logs": logs,
            "total": total,
            "has_more": total > limit,
        })

    except Exception as e:
        logger.error("查询历史日志失败: %s", e, exc_info=True)
        return 统一响应(code=1, msg=f"查询失败: {str(e)}")


@日志推流路由.get("/stats", response_model=统一响应)
async def push_stats():
    """推送统计（调试用）

    返回：
        {
            "code": 0,
            "data": {
                "total": 100,
                "last_push_at": "2026-03-01T12:00:00Z",
                "last_ip": "192.168.1.100",
                "last_ua": "Mozilla/5.0...",
                "last_task_id": "task_123",
                "last_machine": "PC-001",
                "buffer_size": 500,
                "sse_clients": 3
            },
            "msg": "ok"
        }
    """
    return 统一响应(data={
        **_push_stats,
        "buffer_size": len(_log_buffer),
        "sse_clients": len(_sse_clients),
    })
