from sqlalchemy import Column, DateTime, Integer, String, func

from app.db.模型 import 基础模型


class Worker模型(基础模型):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    机器码 = Column("machine_id", String(100), unique=True, nullable=False)
    机器名称 = Column("machine_name", String(200), nullable=False, default="")
    主机名 = Column("hostname", String(200), nullable=True, default="-")
    IP地址 = Column("ip", String(64), nullable=True, default="-")
    状态 = Column("status", String(20), default="offline")  # idle / running / offline / error
    队列名 = Column("queue_name", String(200), nullable=False)
    最后心跳 = Column("last_heartbeat", DateTime, default=None)
    创建时间 = Column("created_at", DateTime, default=func.now())
    更新时间 = Column("updated_at", DateTime, default=func.now(), onupdate=func.now())
