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

def enqueue_task(task, *args, **kwargs):
    """
    智能任务排队分发器。
    如果 task_always_eager 为 True（本地同步调试开发模式），则通过线程池异步执行任务（task.apply），
    从而防止阻塞 FastAPI 的 ASGI 主事件循环（Event Loop），解决上传教材和提炼摘要时前端卡死的问题。
    否则，使用标准的 Celery 消息队列后台异步分发（task.delay）。
    """
    if celery_app.conf.task_always_eager:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        if not hasattr(enqueue_task, "_executor"):
            enqueue_task._executor = ThreadPoolExecutor(max_workers=4)
            
        try:
            loop = asyncio.get_running_loop()
            loop.run_in_executor(
                enqueue_task._executor, 
                lambda: task.apply(args=args, kwargs=kwargs)
            )
        except RuntimeError:
            # 处在非 asyncio 事件循环环境中（如独立测试或命令行），回退为同步串行执行
            task.apply(args=args, kwargs=kwargs)
    else:
        task.delay(*args, **kwargs)
