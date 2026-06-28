from celery import Celery
from core.config import settings

celery_app = Celery(
    "edu_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# 可选配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=True, # 启用本地同步执行，无需依赖 Redis
)

# 自动发现 worker 模块中的任务
celery_app.autodiscover_tasks(["worker.tasks"])
