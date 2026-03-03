# app/飞书/消息处理.py
# 飞书长连接：消息处理、回复、启动入口

import asyncio
import json
import logging
import time
import threading

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    ReplyMessageRequest, ReplyMessageRequestBody,
    CreateMessageRequest, CreateMessageRequestBody
)

from app.db.数据库 import 会话工厂
from app.常量 import FEISHU_MSG_EXPIRE, FEISHU_MSG_MAX_LEN
from app.飞书.配置与会话 import 读取飞书配置, 获取Agent配置, 获取或创建对话, 检查消息去重
from app.飞书.智能体调用 import 同步调用智能体

logger = logging.getLogger(__name__)


# ==================== 飞书消息发送（主动发送，非回复） ====================

def _飞书发送消息(飞书配置: dict, 用户open_id: str, 消息文本: str, 聊天类型: str = "p2p"):
    """主动发送消息给用户（不是回复消息）"""
    try:
        logger.info(f"[飞书-发送] 准备主动发送消息给用户: {用户open_id[:8]}..., 内容前50字: {消息文本[:50]}")
        app_id = 飞书配置.get("appId", "")
        app_secret = 飞书配置.get("appSecret", "")

        if not app_id or not app_secret:
            logger.warning("[飞书-发送] appId 或 appSecret 为空，无法发送")
            return

        客户端 = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

        if len(消息文本) > FEISHU_MSG_MAX_LEN:
            消息文本 = 消息文本[:FEISHU_MSG_MAX_LEN - 50] + "\n\n...（内容过长已截断）"

        请求体 = CreateMessageRequestBody.builder() \
            .receive_id(用户open_id) \
            .msg_type("text") \
            .content(json.dumps({"text": 消息文本})) \
            .build()

        请求 = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(请求体) \
            .build()

        响应 = 客户端.im.v1.message.create(请求)

        if 响应.success():
            logger.info(f"[飞书-发送] 发送成功，用户: {用户open_id[:8]}...")
        else:
            logger.warning(f"[飞书-发送] 发送失败，用户: {用户open_id[:8]}..., code={响应.code}, msg={响应.msg}")

    except Exception as e:
        logger.error(f"[飞书-发送] 发送异常: {e}")


# ==================== 后台异步处理Agent ====================

def _后台处理Agent(飞书配置: dict, agent配置: dict, 用户消息: str, 对话id: str, 用户open_id: str):
    """后台线程中处理Agent调用，完成后主动发送消息给用户

    ⭐ 修复：检测Agent是否调用了飞书工具发送消息，避免重复发送
    """
    try:
        logger.info(f"[后台处理] 开始处理Agent，对话ID: {对话id[:8]}..., 用户: {用户open_id[:8]}...")

        # 调用智能体（这里会耗时40-50秒）
        回复, 调用了飞书工具 = 同步调用智能体(agent配置, 用户消息, 对话id)
        logger.info(f"[后台处理] Agent调用完成，回复长度: {len(回复)}, 调用了飞书工具: {调用了飞书工具}")

        # ⭐ 修复：只有在Agent没有调用飞书工具发送消息时，才自动发送回复
        if not 调用了飞书工具:
            _飞书发送消息(飞书配置, 用户open_id, 回复)
            logger.info(f"[后台处理] 已发送回复，对话ID: {对话id[:8]}...")
        else:
            logger.info(f"[后台处理] Agent已通过飞书工具发送消息，跳过自动回复，对话ID: {对话id[:8]}...")

    except Exception as e:
        logger.error(f"[后台处理] 处理异常: {e}")
        import traceback
        traceback.print_exc()

        # 发送错误提示给用户
        错误消息 = f"抱歉，处理您的消息时出现错误：{str(e)[:100]}"
        try:
            _飞书发送消息(飞书配置, 用户open_id, 错误消息)
        except:
            pass


# ==================== 飞书消息处理 ====================

def _处理飞书消息(data):
    """收到飞书 im.message.receive_v1 事件后的处理函数"""
    try:
        import traceback
        调用栈 = ''.join(traceback.format_stack()[-5:-1])
        logger.info(f"[追踪-入口] 进入 _处理飞书消息 函数")
        logger.info(f"[追踪-入口] 调用栈:\n{调用栈}")

        # 1. 过滤非用户消息
        发送者类型 = data.event.sender.sender_type
        if 发送者类型 != "user":
            logger.debug("[飞书长连接] 非用户消息(sender_type=%s)，跳过", 发送者类型)
            return

        消息 = data.event.message
        消息ID = 消息.message_id
        logger.info(f"[追踪-入口] 收到消息ID: {消息ID}")

        # 2. 消息去重
        if 检查消息去重(消息ID):
            logger.debug("[飞书长连接] 消息已处理过 message_id=%s，跳过", 消息ID)
            return

        # 3. 过期消息过滤
        try:
            消息创建时间 = int(消息.create_time) / 1000
            消息年龄 = time.time() - 消息创建时间
            if 消息年龄 > FEISHU_MSG_EXPIRE:
                logger.debug("[飞书长连接] 消息已过期(%.0f秒前)，跳过", 消息年龄)
                return
        except (ValueError, TypeError, AttributeError):
            pass

        # 4. 只处理文本消息
        消息类型 = 消息.message_type
        聊天类型 = 消息.chat_type
        logger.info("[飞书长连接] 收到消息 id=%s, type=%s, chat=%s", 消息ID, 消息类型, 聊天类型)

        if 消息类型 != "text":
            logger.info("[飞书长连接] 暂不支持消息类型: %s", 消息类型)
            return

        内容 = json.loads(消息.content)
        文本 = 内容.get("text", "")

        # 群聊中去掉 @机器人 前缀
        if 聊天类型 == "group" and 消息.mentions:
            for mention in 消息.mentions:
                文本 = 文本.replace(mention.key, "").strip()

        if not 文本:
            logger.debug("[飞书长连接] 消息文本为空，跳过")
            return

        用户ID = data.event.sender.sender_id.open_id
        logger.info("[飞书长连接] 处理文本: %s", 文本[:50])

        # 5. 读取配置，确定智能体
        飞书配置 = 读取飞书配置()
        agent_id = 飞书配置.get("feishuEventAgentId", "")

        if not agent_id:
            logger.warning("[飞书长连接] 未配置 feishuEventAgentId，跳过")
            _飞书回复(飞书配置, 消息ID, "请先在系统配置中选择接收飞书事件的智能体。")
            return

        agent配置 = 获取Agent配置(agent_id)
        if not agent配置:
            logger.warning("[飞书长连接] Agent %s 不存在", agent_id)
            _飞书回复(飞书配置, 消息ID, "配置的智能体不存在，请在系统配置中重新选择。")
            return

        # 6. 获取/创建对话
        db = 会话工厂()
        try:
            对话id = 获取或创建对话(db, agent_id, 用户ID, 文本)
        finally:
            db.close()

        # 7. 启动后台线程处理Agent（不等待完成，立即返回）
        logger.info(f"[追踪-步骤7] 启动后台线程处理Agent，消息ID: {消息ID}, 对话ID: {对话id}")
        后台线程 = threading.Thread(
            target=_后台处理Agent,
            args=(飞书配置, agent配置, 文本, 对话id, 用户ID),
            daemon=True
        )
        后台线程.start()
        logger.info(f"[追踪-出口] 后台线程已启动，立即返回，消息ID: {消息ID}")

    except Exception as e:
        logger.error("[飞书长连接] 处理消息异常: %s", e)
        import traceback
        traceback.print_exc()


# ==================== 飞书回复 ====================

def _飞书回复(飞书配置: dict, 消息ID: str, 回复文本: str):
    """通过飞书 API 回复消息"""
    try:
        import traceback
        调用栈 = ''.join(traceback.format_stack()[-5:])  # 获取完整调用栈
        logger.info(f"[追踪-回复] ========== 进入 _飞书回复 函数 ==========")
        logger.info(f"[追踪-回复] 消息ID: {消息ID}")
        logger.info(f"[追踪-回复] 回复内容前50字: {回复文本[:50]}")
        logger.info(f"[追踪-回复] 完整调用栈:\n{调用栈}")
        app_id = 飞书配置.get("appId", "")
        app_secret = 飞书配置.get("appSecret", "")

        if not app_id or not app_secret:
            logger.warning("[飞书长连接] appId 或 appSecret 为空，无法回复")
            return

        客户端 = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

        if len(回复文本) > FEISHU_MSG_MAX_LEN:
            回复文本 = 回复文本[:FEISHU_MSG_MAX_LEN - 50] + "\n\n...（内容过长已截断）"

        请求体 = ReplyMessageRequestBody.builder() \
            .msg_type("text") \
            .content(json.dumps({"text": 回复文本})) \
            .build()

        请求 = ReplyMessageRequest.builder() \
            .message_id(消息ID) \
            .request_body(请求体) \
            .build()

        logger.info(f"[追踪-回复] 即将调用飞书API发送回复，消息ID: {消息ID}")
        响应 = 客户端.im.v1.message.reply(请求)
        logger.info(f"[追踪-回复] 飞书API调用完成，消息ID: {消息ID}")

        if 响应.success():
            logger.info(f"[追踪-回复] 回复成功，消息ID: {消息ID}")
        else:
            logger.warning(f"[追踪-回复] 回复失败，消息ID: {消息ID}, code={响应.code}, msg={响应.msg}")

    except Exception as e:
        logger.error("[飞书长连接] 回复异常: %s", e)


# ==================== 启动入口 ====================

def 启动飞书长连接():
    """
    启动飞书 WebSocket 长连接（非阻塞，daemon 线程）。
    在 启动器.py 的生命周期中调用。
    """
    飞书配置 = 读取飞书配置()
    应用ID = 飞书配置.get("appId", "")
    应用密钥 = 飞书配置.get("appSecret", "")

    if not 应用ID or not 应用密钥:
        logger.warning("[飞书长连接] 未配置飞书 appId 或 appSecret，长连接未启动")
        logger.warning("[飞书长连接] 请在前端「系统配置 → 飞书」中填写应用 ID 和密钥")
        return

    agent_id = 飞书配置.get("feishuEventAgentId", "")
    if agent_id:
        agent配置 = 获取Agent配置(agent_id)
        if agent配置:
            logger.info("[飞书长连接] 绑定智能体: %s (id=%s...)", agent配置['name'], agent_id[:8])
        else:
            logger.warning("[飞书长连接] 配置的 Agent ID %s 不存在，消息将无法处理", agent_id)
    else:
        logger.warning("[飞书长连接] 未配置 feishuEventAgentId，消息将无法处理")
        logger.warning("[飞书长连接] 请在前端「系统配置 → 飞书 → 事件订阅绑定智能体」中选择")

    事件处理器 = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(_处理飞书消息) \
        .build()

    WS客户端 = lark.ws.Client(
        app_id=应用ID,
        app_secret=应用密钥,
        event_handler=事件处理器,
        log_level=lark.LogLevel.INFO,
        auto_reconnect=True,
    )

    def _运行():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            import lark_oapi.ws.client as _ws_mod
            _ws_mod.loop = new_loop
        except (ImportError, AttributeError):
            pass
        logger.info("[飞书长连接] WebSocket 连接线程启动")
        WS客户端.start()

    线程 = threading.Thread(target=_运行, daemon=True)
    线程.start()
    logger.info("[飞书长连接] WebSocket 已在后台线程启动")
