"""
环境变量配置
兼容 Step 1/2 的扁平变量 + Step 3 LLM + Step 5 RAGFlow
"""

import os
import secrets
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ===== JWT 鉴权（Step 1） =====
_jwt_secret_from_env = os.getenv("JWT_SECRET_KEY", "").strip()
if not _jwt_secret_from_env or _jwt_secret_from_env == "dev-secret-key-change-in-production":
    密钥 = secrets.token_urlsafe(64)
    logger.warning("[配置] JWT_SECRET_KEY 未设置或使用默认值，已自动生成随机密钥（重启后旧 token 将失效）")
else:
    密钥 = _jwt_secret_from_env
令牌过期小时数 = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
令牌算法 = "HS256"

# ===== 数据库（Step 1） =====
数据库地址 = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

# ===== 生产环境配置 =====
APP_ENV = os.getenv("APP_ENV", "dev").lower()  # dev / prod
DISABLE_DOCS_IN_PROD = os.getenv("DISABLE_DOCS_IN_PROD", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if APP_ENV == "prod" else "DEBUG")

# ===== CORS =====
_cors_origins_raw = os.getenv("CORS_ORIGINS", "").strip()
if not _cors_origins_raw:
    if APP_ENV == "prod":
        raise ValueError("生产环境必须明确设置 CORS_ORIGINS（逗号分隔）")
    CORS_ORIGINS = ["http://localhost:3000"]  # 开发环境默认
elif _cors_origins_raw == "*":
    if APP_ENV == "prod":
        raise ValueError("生产环境 CORS_ORIGINS 不能为 '*'")
    CORS_ORIGINS = ["*"]
else:
    CORS_ORIGINS = [origin.strip() for origin in _cors_origins_raw.split(",") if origin.strip()]

# ===== 影刀推流鉴权 =====
RPA密钥 = os.getenv("RPA_PUSH_KEY", "changeme-rpa-key-2026")


# ===== Step 3+ 配置 =====
class 环境变量:
    """构建器.py / 上下文.py / 知识检索.py 用这个类"""

    # LLM（Step 3）
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")

    # 对话参数（Step 3）
    MAX_HISTORY_ROUNDS: int = int(os.getenv("MAX_HISTORY_ROUNDS", "10"))
    MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4000"))

    # ⭐ RAGFlow 知识库（Step 5 新增）
    RAGFLOW_BASE_URL: str = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
    RAGFLOW_API_KEY: str = os.getenv("RAGFLOW_API_KEY", "")
    RAGFLOW_DATASET_IDS: str = os.getenv("RAGFLOW_DATASET_IDS", "")  # 多个用逗号分隔