"""
Celery异步任务配置 - 增强版本
包含任务重试机制、可靠性配置和监控支持
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue
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

# 增强配置 - 添加重试机制和可靠性设置
celery_app.conf.update(
    # 序列化配置
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # 队列配置
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("high_priority", routing_key="high_priority"),
        Queue("literature_processing", routing_key="literature"),
    ),
    task_default_exchange="tasks",
    task_default_routing_key="default",

    # 重试和可靠性配置
    task_default_retry_delay=30,           # 默认重试延迟30秒
    task_acks_late=True,                   # 延迟确认，确保任务不丢失
    task_reject_on_worker_lost=True,       # worker崩溃时拒绝任务
    task_acks_on_failure_or_timeout=False, # 失败时不确认，重新排队

    # Worker配置
    worker_prefetch_multiplier=1,          # 与acks_late配合，避免任务抢占
    worker_max_tasks_per_child=100,        # 降低内存泄漏风险

    # 任务跟踪和监控
    task_track_started=True,
    task_send_sent_event=True,             # 发送任务发出事件
    worker_send_task_events=True,          # 启用worker事件，支持Flower监控

    # 超时配置
    task_time_limit=30 * 60,              # 30分钟硬超时
    task_soft_time_limit=25 * 60,         # 25分钟软超时

    # 调度器配置
    beat_scheduler="celery.beat:PersistentScheduler",
)

# 通用重试策略配置，供任务复用
default_retry_kwargs = {
    "autoretry_for": (ConnectionError, TimeoutError, OSError),
    "retry_backoff": True,                 # 指数退避策略
    "retry_backoff_max": 300,             # 最大退避时间5分钟
    "retry_jitter": True,                 # 添加随机抖动避免雪崩
    "retry_kwargs": {"max_retries": 5},   # 最大重试5次
}

# 高优先级任务重试策略
high_priority_retry_kwargs = {
    "autoretry_for": (ConnectionError, TimeoutError),
    "retry_backoff": True,
    "retry_backoff_max": 120,             # 高优先级任务更短退避时间
    "retry_jitter": True,
    "retry_kwargs": {"max_retries": 3},   # 更少重试次数
}
