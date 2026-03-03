# app/图引擎/内置工具/邮件.py
# 内置工具：发送邮件（SMTP）

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from ._配置 import _获取系统配置

logger = logging.getLogger(__name__)


async def 发送邮件(收件人: str, 主题: str, 正文: str) -> str:
    """发送邮件（SMTP）

    配置项（从系统配置表 category=email 读取）：
        smtp_host / smtpServer: SMTP 服务器地址
        smtp_port / smtpPort: SMTP 端口（默认 587）
        smtp_user / sender: SMTP 用户名
        smtp_password / smtpPassword: SMTP 密码
        from_email: 发件人邮箱（可选，默认使用 smtp_user）
        from_name: 发件人名称（可选）
        use_tls: 是否使用 TLS（默认 true）

    Args:
        收件人: 收件人邮箱地址
        主题: 邮件主题
        正文: 邮件正文（支持 HTML）

    Returns:
        成功返回 "邮件发送成功"，失败返回错误信息
    """
    try:
        # 读取配置
        配置 = _获取系统配置("email")

        # 兼容两种字段名格式
        smtp_host = 配置.get("smtp_host") or 配置.get("smtpServer")
        smtp_port = 配置.get("smtp_port") or 配置.get("smtpPort", 587)
        smtp_user = 配置.get("smtp_user") or 配置.get("sender")
        smtp_password = 配置.get("smtp_password") or 配置.get("smtpPassword")
        from_email = 配置.get("from_email", smtp_user)
        from_name = 配置.get("from_name", "")
        use_tls = 配置.get("use_tls", True)

        # 处理端口号（可能是字符串）
        if isinstance(smtp_port, str):
            smtp_port = int(smtp_port)

        # 验证必填配置
        if not all([smtp_host, smtp_user, smtp_password]):
            return "错误：邮件配置不完整，请在系统配置中设置 email 分类的 SMTP 配置"

        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = 主题
        msg["From"] = f"{from_name} <{from_email}>" if from_name else from_email
        msg["To"] = 收件人

        # 添加正文（支持 HTML）
        if "<html>" in 正文.lower() or "<body>" in 正文.lower():
            part = MIMEText(正文, "html", "utf-8")
        else:
            part = MIMEText(正文, "plain", "utf-8")
        msg.attach(part)

        # 发送邮件（根据端口选择SSL或TLS）
        if smtp_port == 465:
            # 465端口使用SSL
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            # 其他端口使用STARTTLS
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                if use_tls:
                    server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

        logger.info(f"邮件发送成功: {收件人} - {主题}")
        return f"邮件发送成功：{收件人}"

    except smtplib.SMTPAuthenticationError:
        error_msg = "SMTP 认证失败，请检查用户名和密码"
        logger.error(error_msg)
        return f"错误：{error_msg}"
    except smtplib.SMTPException as e:
        error_msg = f"SMTP 错误: {str(e)}"
        logger.error(error_msg)
        return f"错误：{error_msg}"
    except Exception as e:
        error_msg = f"发送邮件失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"错误：{error_msg}"
