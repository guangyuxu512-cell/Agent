# app/图引擎/内置工具/_配置.py
# 公共配置函数：系统配置读取

import json
import logging
from typing import Dict, Any

from app.db.数据库 import 会话工厂
from app.db.模型 import 系统配置模型

logger = logging.getLogger(__name__)


def _获取系统配置(category: str) -> Dict[str, Any]:
    """从系统配置表读取配置

    Args:
        category: 配置分类（email / feishu）

    Returns:
        配置字典，如果不存在返回空字典
    """
    db = 会话工厂()
    try:
        配置记录 = db.query(系统配置模型).filter(
            系统配置模型.分类 == category,
            系统配置模型.键 == "__data__"
        ).first()

        if 配置记录 and 配置记录.值:
            return json.loads(配置记录.值) if isinstance(配置记录.值, str) else 配置记录.值
        return {}
    except Exception as e:
        logger.error(f"读取系统配置失败 (category={category}): {e}")
        return {}
    finally:
        db.close()
