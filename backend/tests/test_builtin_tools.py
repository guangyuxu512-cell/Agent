"""
测试内置工具功能
- 测试1：发送邮件
- 测试2：读取飞书多维表格
"""

import pytest
import json
import httpx
from app.db.数据库 import 会话工厂
from app.db.模型 import 系统配置模型, 飞书表格模型


@pytest.mark.asyncio
async def test_发送邮件():
    """测试1：发送邮件功能"""
    print("\n" + "="*60)
    print("测试1：发送邮件")
    print("="*60)

    db = 会话工厂()
    try:
        # 从数据库读取email配置
        email_config_record = db.query(系统配置模型).filter(
            系统配置模型.分类 == "email",
            系统配置模型.键 == "__data__"
        ).first()

        assert email_config_record is not None, "未找到email配置"

        config_data = json.loads(email_config_record.值) if isinstance(email_config_record.值, str) else email_config_record.值
        print(f"\n读取到的配置: {json.dumps(config_data, indent=2, ensure_ascii=False)}")

        # 适配配置字段名（数据库用的是 smtpServer/sender，内置工具期望 smtp_host/smtp_user）
        smtp_host = config_data.get("smtpServer")
        smtp_port = int(config_data.get("smtpPort", 587))
        smtp_user = config_data.get("sender")
        smtp_password = config_data.get("smtpPassword")
        from_email = smtp_user

        assert all([smtp_host, smtp_user, smtp_password]), "邮件配置不完整"

        # 发送测试邮件
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        收件人 = "eexzs3457@163.com"
        主题 = "builtin工具测试"
        正文 = "这是自动化测试邮件"

        print(f"\n发送邮件:")
        print(f"  SMTP服务器: {smtp_host}:{smtp_port}")
        print(f"  发件人: {from_email}")
        print(f"  收件人: {收件人}")
        print(f"  主题: {主题}")

        # 构建邮件
        msg = MIMEMultipart("alternative")
        msg["Subject"] = 主题
        msg["From"] = from_email
        msg["To"] = 收件人
        msg.attach(MIMEText(正文, "plain", "utf-8"))

        # 发送邮件（465端口使用SSL）
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=30) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)

        print(f"\n[成功] 邮件发送成功: {收件人}")

    except smtplib.SMTPAuthenticationError as e:
        print(f"\n[失败] SMTP认证失败: {e}")
        pytest.fail(f"SMTP认证失败: {e}")
    except Exception as e:
        print(f"\n[失败] 发送邮件失败: {e}")
        pytest.fail(f"发送邮件失败: {e}")
    finally:
        db.close()


@pytest.mark.asyncio
async def test_读取飞书多维表格():
    """测试2：读取飞书多维表格"""
    print("\n" + "="*60)
    print("测试2：读取飞书多维表格")
    print("="*60)

    db = 会话工厂()
    try:
        # 1. 从数据库读取飞书配置
        feishu_config_record = db.query(系统配置模型).filter(
            系统配置模型.分类 == "feishu",
            系统配置模型.键 == "__data__"
        ).first()

        assert feishu_config_record is not None, "未找到feishu配置"

        config_data = json.loads(feishu_config_record.值) if isinstance(feishu_config_record.值, str) else feishu_config_record.值
        app_id = config_data.get("appId")
        app_secret = config_data.get("appSecret")

        assert all([app_id, app_secret]), "飞书配置不完整"
        print(f"\n飞书配置:")
        print(f"  App ID: {app_id}")
        print(f"  App Secret: {app_secret[:10]}...")

        # 2. 从数据库读取飞书表格配置
        table_record = db.query(飞书表格模型).first()
        assert table_record is not None, "未找到飞书表格配置"

        app_token = table_record.app_token
        table_id = table_record.table_id

        print(f"\n飞书表格:")
        print(f"  名称: {table_record.名称}")
        print(f"  app_token: {app_token}")
        print(f"  table_id: {table_id}")

        # 3. 获取 tenant_access_token
        async with httpx.AsyncClient(timeout=30) as client:
            print(f"\n获取 tenant_access_token...")
            token_resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret}
            )
            token_data = token_resp.json()

            assert token_data.get("code") == 0, f"获取token失败: {token_data.get('msg')}"
            access_token = token_data["tenant_access_token"]
            print(f"  [成功] 获取成功: {access_token[:20]}...")

            # 4. 获取字段元数据（字段名映射）
            print(f"\n获取字段元数据...")
            fields_resp = await client.get(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                headers={
                    "Authorization": f"Bearer {access_token}"
                }
            )
            fields_data = fields_resp.json()

            assert fields_data.get("code") == 0, f"获取字段元数据失败: {fields_data.get('msg')}"

            # 构建字段ID到中文名的映射
            field_mapping = {}
            for field in fields_data.get("data", {}).get("items", []):
                field_id = field.get("field_id")
                field_name = field.get("field_name")
                if field_id and field_name:
                    field_mapping[field_id] = field_name

            print(f"  [成功] 获取到 {len(field_mapping)} 个字段映射")

            # 5. 读取多维表格数据
            print(f"\n读取多维表格数据...")
            list_resp = await client.post(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={
                    "page_size": 5
                }
            )
            list_data = list_resp.json()

            assert list_data.get("code") == 0, f"读取表格失败: {list_data.get('msg')}"

            records = list_data.get("data", {}).get("items", [])
            print(f"  [成功] 读取成功，共 {len(records)} 条记录\n")

            # 6. 打印前5条记录的"店铺名称"和"状态"字段
            print("前5条记录:")
            print("-" * 60)
            for i, record in enumerate(records[:5], 1):
                fields = record.get("fields", {})

                # 直接使用中文字段名（飞书API已返回中文）
                店铺名称_raw = fields.get("店铺名称", "N/A")
                状态_raw = fields.get("状态", "N/A")

                # 处理字段值（可能是列表格式）
                if isinstance(店铺名称_raw, list) and 店铺名称_raw:
                    店铺名称 = 店铺名称_raw[0].get("text", "N/A")
                else:
                    店铺名称 = 店铺名称_raw

                if isinstance(状态_raw, list) and 状态_raw:
                    状态 = 状态_raw[0].get("text", "N/A")
                else:
                    状态 = 状态_raw

                print(f"{i}. 店铺名称: {店铺名称}, 状态: {状态}")

            print("-" * 60)
            print(f"\n[成功] 测试完成，成功读取 {len(records)} 条记录")

    except httpx.TimeoutException as e:
        print(f"\n[失败] 飞书API请求超时: {e}")
        pytest.fail(f"飞书API请求超时: {e}")
    except Exception as e:
        print(f"\n[失败] 读取飞书表格失败: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"读取飞书表格失败: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import asyncio

    print("开始运行内置工具测试...")

    # 运行测试1
    asyncio.run(test_发送邮件())

    # 运行测试2
    asyncio.run(test_读取飞书多维表格())

    print("\n所有测试完成！")
