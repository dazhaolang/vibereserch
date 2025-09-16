"""
Celery异步任务配置
"""

from celery import Celery
from app.core.config import settings

# 创建Celery实例
celery_app = Celery(
    "research_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.literature_tasks",
        "app.tasks.celery_tasks"
    ]
)

# 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30分钟超时
    task_soft_time_limit=25 * 60,  # 25分钟软超时
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)