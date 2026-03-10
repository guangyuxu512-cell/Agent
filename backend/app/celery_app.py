from celery import Celery

from app.配置 import REDIS_URL, CELERY_DEFAULT_QUEUE


celery_app = Celery(
    "agent_backend",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_default_queue=CELERY_DEFAULT_QUEUE,
    task_create_missing_queues=True,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
    imports=(
        "app.tasks.schedule_tasks",
        "app.tasks.test_tasks",
    ),
)

# 显式导入任务模块，确保 Celery 在普通导入和 Worker 启动时都能注册任务
from app.tasks import schedule_tasks as _schedule_tasks  # noqa: F401,E402
from app.tasks import test_tasks as _test_tasks  # noqa: F401,E402
