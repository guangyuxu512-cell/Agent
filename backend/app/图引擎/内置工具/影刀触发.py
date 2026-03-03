# app/图引擎/内置工具/影刀触发.py
# 内置工具：触发影刀应用执行

import logging
import smtplib
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from app.db.数据库 import 会话工厂
from app.db.模型 import 机器模型, 机器应用模型, 任务队列模型
from ._配置 import _获取系统配置

logger = logging.getLogger(__name__)


async def 触发影刀(app_name: str) -> str:
    """触发影刀应用执行

    配置项（从系统配置表读取）：
        category=shadowbot:
            target_email: 影刀监听的目标邮箱
            subject_template: 邮件主题模板（默认: "影刀触发-{app_name}"）
            content_template: 邮件内容模板（默认: "请执行应用：{app_name}"）
        category=email:
            smtp_host / smtpServer: SMTP 服务器地址
            smtp_port / smtpPort: SMTP 端口
            smtp_user / sender: SMTP 用户名
            smtp_password / smtpPassword: SMTP 密码

    Args:
        app_name: 要触发的影刀应用名称

    Returns:
        执行结果消息
    """
    # 输入校验
    if not app_name or not app_name.strip():
        logger.warning("[触发影刀] app_name 参数为空")
        return "错误：应用名称不能为空"

    # 调试日志：记录接收到的参数
    logger.debug(f"[触发影刀] 被调用，app_name={repr(app_name)}, type={type(app_name)}, 长度={len(app_name)}")

    db = 会话工厂()
    try:
        # 1. 读取影刀配置（兼容 camelCase 和 snake_case）
        影刀配置 = _获取系统配置("shadowbot")
        target_email = 影刀配置.get("target_email") or 影刀配置.get("targetEmail")
        subject_template = 影刀配置.get("subject_template") or 影刀配置.get("subjectTemplate") or "影刀触发-{app_name}"
        content_template = 影刀配置.get("content_template") or 影刀配置.get("contentTemplate") or "请执行应用：{app_name}"

        if not target_email:
            return "错误：未配置影刀目标邮箱，请在系统配置中设置 shadowbot 分类的 target_email"

        # 2. 查询应用绑定，找到对应的机器
        # 先查询所有启用的应用，用于调试
        所有绑定 = db.query(机器应用模型).filter(机器应用模型.启用 == True).all()
        logger.debug(f"[触发影刀] 数据库中所有启用的应用: {[(b.应用名, repr(b.应用名), len(b.应用名)) for b in 所有绑定]}")

        # 标准化应用名称（去除首尾空格）
        app_name_normalized = app_name.strip()
        logger.debug(f"[触发影刀] 标准化后的 app_name={repr(app_name_normalized)}")

        # 先精确匹配
        绑定 = db.query(机器应用模型).filter(
            机器应用模型.应用名 == app_name_normalized,
            机器应用模型.启用 == True
        ).first()

        # 精确匹配失败，尝试模糊匹配
        if not 绑定:
            logger.debug(f"[触发影刀] 精确匹配失败，尝试模糊匹配")
            for b in 所有绑定:
                db_name = b.应用名.strip()
                logger.debug(f"[触发影刀] 比较: '{app_name_normalized}' vs '{db_name}'")
                if db_name in app_name_normalized or app_name_normalized in db_name:
                    logger.debug(f"[触发影刀] 模糊匹配成功: {db_name}")
                    绑定 = b
                    break

        # 还是找不到，列出所有可用应用
        if not 绑定:
            可用应用 = [b.应用名 for b in 所有绑定]
            logger.warning(f"[触发影刀] 未找到应用 '{app_name_normalized}'，可用应用: {可用应用}")
            return f"错误：未找到应用 '{app_name_normalized}'。当前可用应用：{', '.join(可用应用)}"

        logger.info(f"[触发影刀] 匹配成功，应用: {绑定.应用名}, 机器: {绑定.机器码}")

        machine_id = 绑定.机器码

        # 3. 查询机器状态
        机器 = db.query(机器模型).filter(机器模型.机器码 == machine_id).first()

        if not 机器:
            return f"错误：机器 '{machine_id}' 不存在"

        # 状态映射：idle -> online, running -> busy
        状态映射 = {
            "idle": "online",
            "running": "busy",
            "offline": "offline",
            "error": "offline"
        }
        实际状态 = 状态映射.get(机器.状态, "offline")

        # 4. 根据机器状态处理
        if 实际状态 == "online":       # 机器空闲，直接发送邮件触发
            结果 = await _发送触发邮件(
                target_email,
                subject_template.format(app_name=app_name),
                content_template.format(app_name=app_name)
            )

            if 结果.startswith("错误"):
                return 结果

            # 机器状态由影刀应用通过 HTTP 回调自行更新
            return f"已触发执行：应用 '{app_name}' 已发送到机器 '{机器.机器名称}'"

        elif 实际状态 == "busy":
            # 机器忙碌，加入任务队列
            try:
                新任务 = 任务队列模型(
                    应用名=app_name,
                    机器码=machine_id,
                    状态="waiting"
                )
                db.add(新任务)
                db.commit()

                # 查询队列位置
                队列位置 = db.query(任务队列模型).filter(
                    任务队列模型.机器码 == machine_id,
                    任务队列模型.状态 == "waiting"
                ).count()

                logger.info(f"[触发影刀] 任务已加入队列: {app_name}, 机器: {machine_id}, 位置: {队列位置}")
                return f"机器 '{机器.机器名称}' 正在忙碌，任务已加入队列等待（队列位置：第{队列位置}个）"
            except Exception as e:
                db.rollback()
                logger.error(f"[触发影刀] 加入任务队列失败: {e}", exc_info=True)
                return f"错误：加入任务队列失败 - {str(e)}"

        else:  # offline
            return f"错误：机器 '{机器.机器名称}' 当前离线，无法执行"

    except Exception as e:
        logger.error(f"触发影刀失败: {e}", exc_info=True)
        return f"错误：触发失败 - {str(e)}"
    finally:
        db.close()


async def _发送触发邮件(收件人: str, 主题: str, 正文: str) -> str:
    """发送触发邮件（内部函数）"""
    import os

    # DEBUG 模式：只打印日志不真发邮件
    if os.getenv("SHADOWBOT_DEBUG", "false").lower() == "true":
        logger.info(f"[DEBUG] 影刀触发邮件（未实际发送）:")
        logger.info(f"  收件人: {收件人}")
        logger.info(f"  主题: {主题}")
        logger.info(f"  正文: {正文}")
        return "邮件发送成功（DEBUG模式）"

    try:
        # 读取 SMTP 配置
        配置 = _获取系统配置("email")

        smtp_host = 配置.get("smtp_host") or 配置.get("smtpServer")
        smtp_port = 配置.get("smtp_port") or 配置.get("smtpPort", 587)
        smtp_user = 配置.get("smtp_user") or 配置.get("sender")
        smtp_password = 配置.get("smtp_password") or 配置.get("smtpPassword")
        from_email = 配置.get("from_email", smtp_user)
        from_name = 配置.get("from_name", "")
        use_tls = 配置.get("use_tls", True)

        if isinstance(smtp_port, str):
            smtp_port = int(smtp_port)

        if not all([smtp_host, smtp_user, smtp_password]):
            return "错误：邮件配置不完整，请在系统配置中设置 email 分类的 SMTP 配置"

        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = 主题
        msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        msg["To"] = 收件人

        part = MIMEText(正文, "plain", "utf-8")
        msg.attach(part)

        # 发送邮件
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                if use_tls:
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

        logger.info(f"影刀触发邮件发送成功: {收件人} - {主题}")
        return "邮件发送成功"

    except smtplib.SMTPAuthenticationError:
        error_msg = "SMTP 认证失败，请检查用户名和密码"
        logger.error(error_msg)
        return f"错误：{error_msg}"
    except smtplib.SMTPException as e:
        error_msg = f"SMTP 错误: {str(e)}"
        logger.error(error_msg)
        return f"错误：{error_msg}"
    except (socket.timeout, TimeoutError):
        error_msg = "SMTP 连接超时，请检查网络或服务器地址"
        logger.error(error_msg)
        return f"错误：{error_msg}"
    except Exception as e:
        error_msg = f"发送触发邮件失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"错误：{error_msg}"
