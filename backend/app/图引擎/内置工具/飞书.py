# app/图引擎/内置工具/飞书.py
# 内置工具：飞书助手（发送消息、读取表格、写入表格）

import json
import logging
import httpx

from ._配置 import _获取系统配置

logger = logging.getLogger(__name__)


async def 飞书助手(操作类型: str, 参数: str) -> str:
    """飞书助手 - 统一的飞书操作工具

    Args:
        操作类型: 操作类型，可选值：发消息、读表格、写表格
        参数: JSON 字符串，不同操作对应不同参数结构

    Returns:
        操作结果字符串
    """
    try:
        # 解析参数
        try:
            参数字典 = json.loads(参数) if isinstance(参数, str) else 参数
        except json.JSONDecodeError:
            return f"错误：参数格式不正确，应为 JSON 格式"

        # 根据操作类型分发
        if 操作类型 == "发消息":
            # 参数: {"open_id": "xxx", "内容": "xxx"}
            open_id = 参数字典.get("open_id") or 参数字典.get("接收者open_id")
            内容 = 参数字典.get("内容") or 参数字典.get("消息内容")

            if not all([open_id, 内容]):
                return "错误：发消息需要提供 open_id 和 内容 参数"

            return await _发送飞书消息(open_id, 内容)

        elif 操作类型 == "读表格":
            # 参数: {"表格名称": "xxx", "筛选条件": ""}
            表格名称 = 参数字典.get("表格名称")
            筛选条件 = 参数字典.get("筛选条件", "")

            if not 表格名称:
                return "错误：读表格需要提供 表格名称 参数"

            return await _读取飞书表格(表格名称, 筛选条件)

        elif 操作类型 == "写表格":
            # 参数: {"表格名称": "xxx", "数据": {"字段名": "值"}}
            表格名称 = 参数字典.get("表格名称")
            数据 = 参数字典.get("数据")

            if not all([表格名称, 数据]):
                return "错误：写表格需要提供 表格名称 和 数据 参数"

            # 将数据转换为 JSON 字符串
            数据字符串 = json.dumps(数据, ensure_ascii=False) if isinstance(数据, dict) else 数据
            return await _写入飞书表格(表格名称, 数据字符串)

        else:
            return f"错误：不支持的操作类型 '{操作类型}'，支持的操作：发消息、读表格、写表格"

    except Exception as e:
        error_msg = f"飞书助手执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"错误：{error_msg}"


async def _发送飞书消息(接收者open_id: str, 消息内容: str) -> str:
    """发送飞书消息（飞书 API）

    配置项（从系统配置表 category=feishu 读取）：
        app_id: 飞书应用 App ID
        app_secret: 飞书应用 App Secret

    Args:
        接收者open_id: 接收者的 Open ID
        消息内容: 消息内容（文本）

    Returns:
        成功返回 "飞书消息发送成功"，失败返回错误信息
    """
    try:
        # 读取配置
        配置 = _获取系统配置("feishu")

        app_id = 配置.get("app_id") or 配置.get("appId")
        app_secret = 配置.get("app_secret") or 配置.get("appSecret")

        # 验证必填配置
        if not all([app_id, app_secret]):
            return "错误：飞书配置不完整，请在系统配置中设置 feishu 分类的 app_id 和 app_secret"

        # 1. 获取 tenant_access_token
        async with httpx.AsyncClient(timeout=30) as client:
            token_resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret}
            )
            token_data = token_resp.json()

            if token_data.get("code") != 0:
                error_msg = f"获取飞书 token 失败: {token_data.get('msg')}"
                logger.error(error_msg)
                return f"错误：{error_msg}"

            access_token = token_data["tenant_access_token"]

            # 2. 发送消息
            msg_resp = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                params={"receive_id_type": "open_id"},
                json={
                    "receive_id": 接收者open_id,
                    "msg_type": "text",
                    "content": f'{{"text": "{消息内容}"}}'
                }
            )
            msg_data = msg_resp.json()

            if msg_data.get("code") != 0:
                error_msg = f"发送飞书消息失败: {msg_data.get('msg')}"
                logger.error(error_msg)
                return f"错误：{error_msg}"

            logger.info(f"飞书消息发送成功: {接收者open_id}")
            return f"飞书消息发送成功：{接收者open_id}"

    except httpx.TimeoutException:
        error_msg = "飞书 API 请求超时"
        logger.error(error_msg)
        return f"错误：{error_msg}"
    except Exception as e:
        error_msg = f"发送飞书消息失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"错误：{error_msg}"


async def _读取飞书表格(表格名称: str, 筛选条件: str = "") -> str:
    """读取飞书多维表格数据

    Args:
        表格名称: 飞书表格名称（从 feishu_tables 表查询）
        筛选条件: 可选的筛选条件（暂未实现，预留参数）

    Returns:
        格式化的表格数据文本，失败返回错误信息
    """
    from app.db.数据库 import 会话工厂
    from app.db.模型 import 飞书表格模型

    db = 会话工厂()
    try:
        # 1. 从数据库查询表格配置
        表格记录 = db.query(飞书表格模型).filter(飞书表格模型.名称 == 表格名称).first()
        if not 表格记录:
            return f"错误：未找到名为 '{表格名称}' 的飞书表格配置"

        app_token = 表格记录.app_token
        table_id = 表格记录.table_id

        # 2. 读取飞书配置
        配置 = _获取系统配置("feishu")
        app_id = 配置.get("app_id") or 配置.get("appId")
        app_secret = 配置.get("app_secret") or 配置.get("appSecret")

        if not all([app_id, app_secret]):
            return "错误：飞书配置不完整，请在系统配置中设置 feishu 分类的 app_id 和 app_secret"

        # 3. 获取 tenant_access_token
        async with httpx.AsyncClient(timeout=30) as client:
            token_resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret}
            )
            token_data = token_resp.json()

            if token_data.get("code") != 0:
                return f"错误：获取飞书 token 失败: {token_data.get('msg')}"

            access_token = token_data["tenant_access_token"]

            # 4. 获取字段元数据（字段名映射）
            fields_resp = await client.get(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            fields_data = fields_resp.json()

            if fields_data.get("code") != 0:
                return f"错误：获取字段元数据失败: {fields_data.get('msg')}"

            # 构建字段ID到中文名的映射
            field_mapping = {}
            for field in fields_data.get("data", {}).get("items", []):
                field_id = field.get("field_id")
                field_name = field.get("field_name")
                if field_id and field_name:
                    field_mapping[field_id] = field_name

            # 5. 读取表格数据
            list_resp = await client.post(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={"page_size": 100}  # 最多返回100条
            )
            list_data = list_resp.json()

            if list_data.get("code") != 0:
                return f"错误：读取表格数据失败: {list_data.get('msg')}"

            records = list_data.get("data", {}).get("items", [])

            # 6. 格式化输出
            if not records:
                return f"表格 '{表格名称}' 中没有数据"

            # 使用中文字段名格式化数据
            结果行 = []
            结果行.append(f"表格 '{表格名称}' 共有 {len(records)} 条记录：\n")

            for i, record in enumerate(records, 1):
                fields = record.get("fields", {})
                行数据 = []

                # 直接使用中文字段名（飞书API已返回中文）
                for field_name, field_value in fields.items():
                    # 处理字段值（可能是列表格式）
                    if isinstance(field_value, list) and field_value:
                        值 = field_value[0].get("text", str(field_value[0])) if isinstance(field_value[0], dict) else str(field_value[0])
                    else:
                        值 = str(field_value) if field_value is not None else ""

                    if 值:  # 只显示非空字段
                        行数据.append(f"{field_name}: {值}")

                if 行数据:
                    结果行.append(f"{i}. {', '.join(行数据)}")

            logger.info(f"读取飞书表格成功: {表格名称}, {len(records)}条记录")
            return "\n".join(结果行)

    except httpx.TimeoutException:
        return "错误：飞书 API 请求超时"
    except Exception as e:
        error_msg = f"读取飞书表格失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"错误：{error_msg}"
    finally:
        db.close()


async def _写入飞书表格(表格名称: str, 数据: str) -> str:
    """写入飞书多维表格数据（支持新增和更新）

    Args:
        表格名称: 飞书表格名称（从 feishu_tables 表查询）
        数据: JSON 字符串，如 {"店铺名称": "测试店铺", "状态": "正常"}
              使用 upsert 模式：根据第一个字段查询，存在则更新，不存在则新增

    Returns:
        成功返回操作结果，失败返回错误信息
    """
    from app.db.数据库 import 会话工厂
    from app.db.模型 import 飞书表格模型

    db = 会话工厂()
    try:
        # 1. 解析数据
        try:
            数据字典 = json.loads(数据) if isinstance(数据, str) else 数据
        except json.JSONDecodeError:
            return f"错误：数据格式不正确，应为 JSON 格式，如 {{\"店铺名称\": \"测试店铺\"}}"

        if not isinstance(数据字典, dict) or not 数据字典:
            return "错误：数据应为非空 JSON 对象格式"

        # 2. 从数据库查询表格配置
        表格记录 = db.query(飞书表格模型).filter(飞书表格模型.名称 == 表格名称).first()
        if not 表格记录:
            return f"错误：未找到名为 '{表格名称}' 的飞书表格配置"

        app_token = 表格记录.app_token
        table_id = 表格记录.table_id

        # 3. 读取飞书配置
        配置 = _获取系统配置("feishu")
        app_id = 配置.get("app_id") or 配置.get("appId")
        app_secret = 配置.get("app_secret") or 配置.get("appSecret")

        if not all([app_id, app_secret]):
            return "错误：飞书配置不完整，请在系统配置中设置 feishu 分类的 app_id 和 app_secret"

        # 4. 获取 tenant_access_token
        async with httpx.AsyncClient(timeout=30) as client:
            token_resp = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={"app_id": app_id, "app_secret": app_secret}
            )
            token_data = token_resp.json()

            if token_data.get("code") != 0:
                return f"错误：获取飞书 token 失败: {token_data.get('msg')}"

            access_token = token_data["tenant_access_token"]

            # 5. 查询是否存在记录（根据第一个字段作为查询条件）
            查询字段名 = list(数据字典.keys())[0]
            查询字段值 = 数据字典[查询字段名]

            existing_record_id = None
            try:
                # 使用 POST /records/search 接口查询所有记录
                list_resp = await client.post(
                    f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"page_size": 500}  # 查询最多500条
                )
                list_data = list_resp.json()

                if list_data.get("code") == 0:
                    records = list_data.get("data", {}).get("items", [])
                    # 查找匹配的记录
                    for record in records:
                        fields = record.get("fields", {})
                        if 查询字段名 in fields:
                            字段值 = fields[查询字段名]

                            # 兼容字段值可能是列表格式：[{"text":"xxx"}]
                            if isinstance(字段值, list) and len(字段值) > 0:
                                if isinstance(字段值[0], dict) and "text" in 字段值[0]:
                                    字段值 = 字段值[0]["text"]

                            # 比较值
                            if 字段值 == 查询字段值:
                                existing_record_id = record.get("record_id")
                                break
            except Exception as e:
                logger.warning(f"查询记录失败: {e}")

            # 6. 根据是否存在记录，决定新增或更新
            if existing_record_id:
                # 更新模式：PUT /records/{record_id}
                update_resp = await client.put(
                    f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{existing_record_id}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"fields": 数据字典}
                )
                update_data = update_resp.json()

                if update_data.get("code") != 0:
                    return f"错误：更新数据失败: {update_data.get('msg')}"

                logger.info(f"更新飞书表格成功: {表格名称}, record_id={existing_record_id}")
                return f"成功更新表格 '{表格名称}' 中的记录（{查询字段名}={查询字段值}）"
            else:
                # 新增模式：POST /records
                create_resp = await client.post(
                    f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json"
                    },
                    json={"fields": 数据字典}
                )
                create_data = create_resp.json()

                if create_data.get("code") != 0:
                    return f"错误：新增数据失败: {create_data.get('msg')}"

                record_id = create_data.get("data", {}).get("record", {}).get("record_id", "")
                logger.info(f"新增飞书表格成功: {表格名称}, record_id={record_id}")
                return f"成功新增记录到表格 '{表格名称}'，记录ID: {record_id}"

    except httpx.TimeoutException:
        return "错误：飞书 API 请求超时"
    except Exception as e:
        error_msg = f"写入飞书表格失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return f"错误：{error_msg}"
    finally:
        db.close()
