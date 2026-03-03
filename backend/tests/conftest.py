# tests/conftest.py
# 测试夹具：内存 SQLite + 依赖覆盖 + JWT token

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from passlib.context import CryptContext

from app.db.模型 import 基础模型, 用户模型
from app.db.数据库 import 获取数据库

# 内存数据库 — StaticPool 确保所有连接共享同一个内存 DB
测试引擎 = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
测试会话工厂 = sessionmaker(autocommit=False, autoflush=False, bind=测试引擎)
密码工具 = CryptContext(schemes=["bcrypt"], deprecated="auto")


def 覆盖获取数据库():
    db = 测试会话工厂()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def 创建表():
    """建表 + 默认 admin 用户（整个测试会话只执行一次）"""
    基础模型.metadata.create_all(bind=测试引擎)
    db = 测试会话工厂()
    db.add(用户模型(用户名="admin", 密码哈希=密码工具.hash("admin123")))
    db.commit()
    db.close()
    yield
    基础模型.metadata.drop_all(bind=测试引擎)


@pytest.fixture(scope="session")
def client(创建表):
    """TestClient，依赖覆盖为内存数据库"""
    from app.启动器 import app
    app.dependency_overrides[获取数据库] = 覆盖获取数据库
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def token(client):
    """登录拿 JWT token"""
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    return r.json()["data"]["token"]


@pytest.fixture(scope="session")
def auth(token):
    """Authorization header"""
    return {"Authorization": f"Bearer {token}"}
