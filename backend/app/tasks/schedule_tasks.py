from app.celery_app import celery_app
from app.services.schedule_executor import 同步执行定时任务


@celery_app.task(bind=True, name="app.tasks.execute_schedule")
def 执行定时任务Celery(self, schedule_id: str, dispatch_id: str | None = None):
    return 同步执行定时任务(schedule_id, dispatch_id, self.request.retries or 0)
