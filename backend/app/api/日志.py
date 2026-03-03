# app/api/日志.py
# 从 log_server 合并而来 — SSE 日志推流 + 历史查询
# 日志持久化到 SQLite，auto-increment ID 作为 seq（重启不重置）

import asyncio
import collections
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from jose import jwt, JWTError

from app.db.数据库 import 获取数据库, 会话工厂
from app.db.模型 import 推送日志模型
from app.常量 import LOG_RETENTION_DAYS, LOG_HISTORY_LIMIT, LOG_DEFAULT_PAGE_SIZE
from app.配置 import 密钥, 令牌算法

logger = logging.getLogger(__name__)

日志路由 = APIRouter()

clients: set[asyncio.Queue] = set()

# 日志保留天数
_LOG_RETENTION_DAYS = LOG_RETENTION_DAYS

# SSE 短期令牌有效期（分钟）
_SSE_TOKEN_MINUTES = 3

# ========== 推送审计统计（内存） ==========
_push_stats = {
    "total": 0,
    "last_push_at": None,      # ISO 时间字符串
    "last_ip": None,
    "last_ua": None,
    "last_task_id": None,
    "last_machine": None,
}
# 滑动窗口：记录最近 5 分钟每次 push 的时间戳
_push_timestamps: collections.deque = collections.deque()


class 日志推送请求(BaseModel):
    time: Optional[str] = None
    task_id: Optional[str] = "未知任务"
    machine: Optional[str] = "未知设备"
    level: Optional[str] = "进行中"
    msg: str


def _日志转字典(记录: 推送日志模型) -> dict:
    return {
        "seq": 记录.id,
        "time": 记录.时间 or "",
        "task_id": 记录.任务ID or "未知任务",
        "machine": 记录.设备 or "未知设备",
        "level": 记录.级别 or "进行中",
        "msg": 记录.消息 or "",
    }


@日志路由.post("/api/logs/push")
async def push_log(请求体: 日志推送请求, request: Request):
    # ── 审计日志（不落敏感信息） ──
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    logger.info(
        "LOG_PUSH from %s ua=%s task_id=%s machine=%s",
        client_ip, user_agent, 请求体.task_id, 请求体.machine,
    )

    # ── 更新内存统计 ──
    now = datetime.now(timezone.utc)
    _push_stats["total"] += 1
    _push_stats["last_push_at"] = now.isoformat()
    _push_stats["last_ip"] = client_ip
    _push_stats["last_ua"] = user_agent
    _push_stats["last_task_id"] = 请求体.task_id
    _push_stats["last_machine"] = 请求体.machine
    _push_timestamps.append(now.timestamp())

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

        log_entry = _日志转字典(新日志)
        for q in list(clients):
            try:
                q.put_nowait(log_entry)
            except asyncio.QueueFull:
                pass
        return {"code": 0, "msg": "ok"}
    finally:
        db.close()


@日志路由.get("/api/logs/sse-token")
async def get_sse_token(request: Request):
    """签发短期 SSE 令牌（3 分钟有效），仅限已登录用户调用。
    前端拿到后拼入 EventSource URL: /api/logs/stream?token=xxx
    """
    username = getattr(request.state, "username", None)
    if not username:
        return JSONResponse(
            status_code=401,
            content={"code": 401, "data": None, "msg": "未授权"},
        )
    过期时间 = datetime.now(timezone.utc) + timedelta(minutes=_SSE_TOKEN_MINUTES)
    载荷 = {"sub": username, "scope": "sse", "exp": 过期时间}
    token = jwt.encode(载荷, 密钥, algorithm=令牌算法)
    return {"code": 0, "data": {"token": token, "expires_in": _SSE_TOKEN_MINUTES * 60}}


@日志路由.get("/api/logs/stream")
async def log_stream(request: Request, token: Optional[str] = None):
    # 仅此端点接受 query token（短期 SSE 令牌，scope=sse）
    if not token:
        return JSONResponse(
            status_code=401,
            content={"code": 401, "data": None, "msg": "缺少 token 参数"},
        )
    try:
        载荷 = jwt.decode(token, 密钥, algorithms=[令牌算法])
        if 载荷.get("scope") != "sse":
            raise JWTError("scope mismatch")
    except JWTError:
        return JSONResponse(
            status_code=401,
            content={"code": 401, "data": None, "msg": "token 无效或已过期"},
        )

    last_event_id = request.headers.get("last-event-id", "")
    last_seq = int(last_event_id) if last_event_id.isdigit() else 0

    queue: asyncio.Queue = asyncio.Queue(maxsize=2000)
    clients.add(queue)

    async def generate():
        try:
            # 从 DB 补发历史
            db = 会话工厂()
            try:
                历史 = (
                    db.query(推送日志模型)
                    .filter(推送日志模型.id > last_seq)
                    .order_by(推送日志模型.id)
                    .limit(LOG_HISTORY_LIMIT)
                    .all()
                )
                sent_seq = last_seq
                for 记录 in 历史:
                    entry = _日志转字典(记录)
                    yield f"id: {entry['seq']}\ndata: {json.dumps(entry, ensure_ascii=False)}\n\n"
                    sent_seq = max(sent_seq, entry["seq"])
            finally:
                db.close()

            while True:
                try:
                    entry = await asyncio.wait_for(queue.get(), timeout=15)
                    entry_seq = entry.get("seq", 0)
                    if entry_seq > sent_seq:
                        yield f"id: {entry_seq}\ndata: {json.dumps(entry, ensure_ascii=False)}\n\n"
                        sent_seq = entry_seq
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            clients.discard(queue)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@日志路由.get("/api/logs/history")
async def log_history(
    task_id: Optional[str] = None,
    since_seq: int = 0,
    page_size: int = Query(LOG_DEFAULT_PAGE_SIZE, ge=1, le=1000),
):
    db = 会话工厂()
    try:
        查询 = db.query(推送日志模型)
        if since_seq:
            查询 = 查询.filter(推送日志模型.id > since_seq)
        if task_id:
            查询 = 查询.filter(推送日志模型.任务ID == task_id)
        结果 = 查询.order_by(推送日志模型.id).limit(page_size).all()
        return {"code": 0, "data": [_日志转字典(r) for r in 结果]}
    finally:
        db.close()


@日志路由.get("/api/logs/debug/stats")
async def push_debug_stats(request: Request):
    """管理接口：返回推送统计，仅 admin 可用。"""
    username = getattr(request.state, "username", None)
    if username != "admin":
        return JSONResponse(
            status_code=403,
            content={"code": 403, "data": None, "msg": "仅 admin 可访问"},
        )

    # 清理滑动窗口中超过 5 分钟的时间戳
    cutoff = datetime.now(timezone.utc).timestamp() - 300
    while _push_timestamps and _push_timestamps[0] < cutoff:
        _push_timestamps.popleft()

    return {
        "code": 0,
        "data": {
            "push_count_5min": len(_push_timestamps),
            "total_since_restart": _push_stats["total"],
            "last_push_at": _push_stats["last_push_at"],
            "last_ip": _push_stats["last_ip"],
            "last_ua": _push_stats["last_ua"],
            "last_task_id": _push_stats["last_task_id"],
            "last_machine": _push_stats["last_machine"],
        },
    }


def 清理过期日志():
    """删除超过保留天数的日志"""
    db = 会话工厂()
    try:
        截止时间 = datetime.now() - timedelta(days=_LOG_RETENTION_DAYS)
        删除数 = db.query(推送日志模型).filter(推送日志模型.创建时间 < 截止时间).delete()
        db.commit()
        if 删除数:
            logger.info("[日志清理] 已删除 %d 条过期日志", 删除数)
    except Exception as e:
        logger.error("[日志清理] 失败: %s", e)
    finally:
        db.close()
