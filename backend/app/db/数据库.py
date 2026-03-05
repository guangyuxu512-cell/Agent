import os
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext

from app.配置 import 数据库地址, APP_ENV
from app.db.模型 import Base, 用户模型

logger = logging.getLogger(__name__)

# ========== 引擎和会话 ==========

引擎 = create_engine(
    数据库地址,
    connect_args={"check_same_thread": False},  # SQLite 需要
    echo=(APP_ENV != "prod")  # 生产环境关闭 SQL 日志
)

会话工厂 = sessionmaker(autocommit=False, autoflush=False, bind=引擎)

密码工具 = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ========== 获取数据库会话 ==========

def 获取数据库() -> Session:
    数据库 = 会话工厂()
    try:
        yield 数据库
    finally:
        数据库.close()


# ========== 初始化：建表 + 默认用户 ==========

def 初始化数据库():
    """启动时调用：自动建表，插入默认 admin 用户（如果不存在）"""
    Base.metadata.create_all(bind=引擎)

    数据库 = 会话工厂()
    try:
        已有用户 = 数据库.query(用户模型).filter(用户模型.用户名 == "admin").first()
        if not 已有用户:
            默认密码 = os.getenv("DEFAULT_ADMIN_PASSWORD", "").strip()

            # ⭐ P0 安全：禁止弱口令
            if not 默认密码 or 默认密码 == "admin123" or len(默认密码) < 12:
                logger.error(
                    "[初始化] DEFAULT_ADMIN_PASSWORD 未设置或为弱口令，拒绝创建默认用户。"
                    "请设置强密码（长度>=12，包含大小写/数字/符号至少两类）"
                )
                logger.error("[初始化] 系统无法启动，请在 .env 中设置 DEFAULT_ADMIN_PASSWORD")
                raise ValueError("DEFAULT_ADMIN_PASSWORD 必须设置为强密码")

            默认用户 = 用户模型(
                用户名="admin",
                密码哈希=密码工具.hash(默认密码)
            )
            数据库.add(默认用户)
            数据库.commit()
            logger.info("[初始化] 已创建默认用户 admin（使用强密码）")
        else:
            logger.info("[初始化] admin 用户已存在，跳过")

        # ⭐ 自动迁移：检查并添加缺失列
        _自动迁移(数据库)
    finally:
        数据库.close()


def _自动迁移(db):
    """检查并添加缺失的列（安全幂等）"""
    迁移列表 = [
        ("conversations", "source", "VARCHAR(20) DEFAULT 'web'"),
    ]
    for 表名, 列名, 列定义 in 迁移列表:
        try:
            db.execute(text(f"SELECT {列名} FROM {表名} LIMIT 1"))
        except Exception:
            try:
                db.execute(text(f"ALTER TABLE {表名} ADD COLUMN {列名} {列定义}"))
                db.commit()
                logger.info("[迁移] 已添加列 %s.%s", 表名, 列名)
            except Exception as e:
                logger.error("[迁移] 添加列 %s.%s 失败: %s", 表名, 列名, e)


# ========== SQLAlchemy 事件监听器：追踪机器状态变更 ==========

from sqlalchemy import event
import traceback

@event.listens_for(Session, "before_flush")
def 追踪机器状态变更(session, flush_context, instances):
    """在提交前追踪所有机器状态的变更"""
    from app.db.模型 import 机器模型

    for obj in session.dirty:
        if isinstance(obj, 机器模型):
            # 检查状态是否被修改
            状态历史 = session.get_history(obj, '状态')
            if 状态历史.has_changes():
                旧状态 = 状态历史.deleted[0] if 状态历史.deleted else None
                新状态 = obj.状态

                if APP_ENV != "prod":
                    # 开发环境：记录详细的调用栈
                    调用栈 = ''.join(traceback.format_stack())
                    logger.warning(
                        f"[SQLAlchemy 事件] 检测到机器状态变更！\n"
                        f"  机器码: {obj.机器码}\n"
                        f"  机器名称: {obj.机器名称}\n"
                        f"  旧状态: {旧状态}\n"
                        f"  新状态: {新状态}\n"
                        f"  调用栈:\n{调用栈}"
                    )
                else:
                    # 生产环境：只记录简短信息
                    logger.info(f"[状态变更] 机器 {obj.机器码} ({obj.机器名称}): {旧状态} -> {新状态}")