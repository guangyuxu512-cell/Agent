import os
import sys
import time
import socket
import signal
import logging
import threading
import subprocess
from urllib.parse import urlparse

import httpx


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("worker_agent")


SERVER_URL = os.getenv("SERVER_URL", "").rstrip("/")
MACHINE_ID = os.getenv("MACHINE_ID", "").strip()
RPA_KEY = os.getenv("RPA_KEY", "").strip()
QUEUE_NAME = f"worker.{MACHINE_ID}" if MACHINE_ID else ""
停止事件 = threading.Event()


def 校验环境变量():
    缺失项 = [name for name, value in {
        "SERVER_URL": SERVER_URL,
        "MACHINE_ID": MACHINE_ID,
        "RPA_KEY": RPA_KEY,
    }.items() if not value]
    if 缺失项:
        raise ValueError(f"缺少环境变量: {', '.join(缺失项)}")


def 获取本机主机名() -> str:
    return socket.gethostname()


def 获取本机IP() -> str:
    try:
        目标主机 = urlparse(SERVER_URL).hostname or "8.8.8.8"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((目标主机, 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


def 请求头() -> dict:
    return {"X-RPA-KEY": RPA_KEY}


def 注册机器(client: httpx.Client):
    payload = {
        "machine_id": MACHINE_ID,
        "machine_name": 获取本机主机名(),
    }
    resp = client.post(f"{SERVER_URL}/api/workers/register", json=payload, headers=请求头())
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(data.get("msg") or "注册失败")
    logger.info("Worker 注册成功: machine_id=%s queue=%s", MACHINE_ID, QUEUE_NAME)


def 心跳循环():
    with httpx.Client(timeout=10.0) as client:
        while not 停止事件.is_set():
            try:
                payload = {
                    "machine_id": MACHINE_ID,
                    "shadowbot_running": True,
                }
                resp = client.post(f"{SERVER_URL}/api/workers/heartbeat", json=payload, headers=请求头())
                resp.raise_for_status()
                data = resp.json()
                if data.get("code") != 0:
                    logger.warning("心跳返回异常: %s", data.get("msg"))
                else:
                    logger.info("心跳成功: machine_id=%s", MACHINE_ID)
            except Exception as e:
                logger.warning("心跳失败: %s", e)

            停止事件.wait(30)


def 启动CeleryWorker() -> subprocess.Popen:
    命令 = [
        sys.executable,
        "-m",
        "celery",
        "-A",
        "app.celery_app:celery_app",
        "worker",
        "-l",
        "info",
        "-Q",
        QUEUE_NAME,
        "-n",
        f"{MACHINE_ID}@%h",
    ]
    logger.info("启动 Celery Worker: %s", " ".join(命令))
    return subprocess.Popen(命令, cwd=os.path.dirname(os.path.abspath(__file__)))


def 处理退出信号(signum, frame):
    logger.info("收到退出信号，准备停止 worker_agent")
    停止事件.set()


def main():
    校验环境变量()

    signal.signal(signal.SIGINT, 处理退出信号)
    signal.signal(signal.SIGTERM, 处理退出信号)

    with httpx.Client(timeout=10.0) as client:
        注册机器(client)

    心跳线程 = threading.Thread(target=心跳循环, daemon=True, name="worker-heartbeat")
    心跳线程.start()

    worker进程 = 启动CeleryWorker()

    try:
        while worker进程.poll() is None and not 停止事件.is_set():
            time.sleep(1)
    finally:
        停止事件.set()
        if worker进程.poll() is None:
            logger.info("停止 Celery Worker 进程")
            worker进程.terminate()
            try:
                worker进程.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker进程.kill()


if __name__ == "__main__":
    main()
