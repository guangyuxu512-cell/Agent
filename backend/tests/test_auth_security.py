"""
测试密码策略和修改密码功能
pytest backend/tests/test_auth_security.py -v
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.启动器 import app
from app.db.数据库 import 获取数据库, 密码工具
from app.db.模型 import Base, 用户模型


# 测试数据库
TEST_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[获取数据库] = override_get_db
client = TestClient(app)


@pytest.fixture(scope="function", autouse=True)
def setup_database():
    """每个测试前重建数据库"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # 创建测试用户（强密码）
    test_user = 用户模型(
        用户名="testuser",
        密码哈希=密码工具.hash("StrongPass123!@#")
    )
    db.add(test_user)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)


def test_login_with_weak_password_returns_force_change_flag():
    """测试：弱密码登录返回 force_change_password=true"""
    db = TestingSessionLocal()
    # 创建弱密码用户
    weak_user = 用户模型(
        用户名="weakuser",
        密码哈希=密码工具.hash("admin123")
    )
    db.add(weak_user)
    db.commit()
    db.close()

    response = client.post("/api/auth/login", json={
        "username": "weakuser",
        "password": "admin123"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["force_change_password"] is True


def test_login_with_strong_password_no_force_change():
    """测试：强密码登录返回 force_change_password=false"""
    response = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "StrongPass123!@#"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["force_change_password"] is False


def test_change_password_with_wrong_old_password():
    """测试：旧密码错误"""
    # 先登录获取 token
    login_resp = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "StrongPass123!@#"
    })
    token = login_resp.json()["data"]["token"]

    # 尝试修改密码（旧密码错误）
    response = client.post("/api/auth/change-password", json={
        "old_password": "WrongPassword",
        "new_password": "NewStrongPass456!@#"
    }, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1
    assert "旧密码错误" in data["msg"]


def test_change_password_with_weak_new_password():
    """测试：新密码不符合强度要求"""
    login_resp = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "StrongPass123!@#"
    })
    token = login_resp.json()["data"]["token"]

    # 尝试修改为弱密码
    response = client.post("/api/auth/change-password", json={
        "old_password": "StrongPass123!@#",
        "new_password": "weak"  # 太短
    }, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 1
    assert "密码长度必须至少 12 位" in data["msg"]


def test_change_password_success():
    """测试：修改密码成功"""
    # 登录
    login_resp = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "StrongPass123!@#"
    })
    token = login_resp.json()["data"]["token"]

    # 修改密码
    response = client.post("/api/auth/change-password", json={
        "old_password": "StrongPass123!@#",
        "new_password": "NewStrongPass456!@#"
    }, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "密码修改成功" in data["msg"]


def test_old_password_fails_after_change():
    """测试：改密后旧密码无法登录"""
    # 登录
    login_resp = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "StrongPass123!@#"
    })
    token = login_resp.json()["data"]["token"]

    # 修改密码
    client.post("/api/auth/change-password", json={
        "old_password": "StrongPass123!@#",
        "new_password": "NewStrongPass456!@#"
    }, headers={"Authorization": f"Bearer {token}"})

    # 尝试用旧密码登录
    old_login = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "StrongPass123!@#"
    })
    assert old_login.json()["code"] == 1
    assert "用户名或密码错误" in old_login.json()["msg"]


def test_new_password_works_after_change():
    """测试：改密后新密码可以登录"""
    # 登录
    login_resp = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "StrongPass123!@#"
    })
    token = login_resp.json()["data"]["token"]

    # 修改密码
    client.post("/api/auth/change-password", json={
        "old_password": "StrongPass123!@#",
        "new_password": "NewStrongPass456!@#"
    }, headers={"Authorization": f"Bearer {token}"})

    # 用新密码登录
    new_login = client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "NewStrongPass456!@#"
    })
    assert new_login.json()["code"] == 0
    assert "token" in new_login.json()["data"]
