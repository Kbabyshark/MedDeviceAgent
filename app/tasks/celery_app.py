"""
Celery 异步任务配置。

Queue 设计：
- embedding_tasks:  文档 Embedding 入库
- notification_tasks: 短信/邮件通知
- ticket_sync_tasks: 工单同步到外部系统
- cleanup_tasks:    定时清理过期数据
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "med_device_agent",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 单任务最大 10 分钟
    task_soft_time_limit=540,  # 软超时 9 分钟
    task_default_queue="default",
    task_queues={
        "embedding": {"exchange": "embedding", "routing_key": "embedding"},
        "notification": {"exchange": "notification", "routing_key": "notification"},
        "ticket_sync": {"exchange": "ticket_sync", "routing_key": "ticket_sync"},
        "cleanup": {"exchange": "cleanup", "routing_key": "cleanup"},
    },
    task_routes={
        "app.tasks.embedding_tasks.*": {"queue": "embedding"},
        "app.tasks.notification_tasks.*": {"queue": "notification"},
        "app.tasks.ticket_sync_tasks.*": {"queue": "ticket_sync"},
        "app.tasks.cleanup_tasks.*": {"queue": "cleanup"},
    },
    # 定时任务
    beat_schedule={
        "cleanup-expired-traces": {
            "task": "app.tasks.cleanup_tasks.cleanup_expired_traces",
            "schedule": crontab(hour=3, minute=0),  # 每天凌晨 3:00
        },
        "cleanup-expired-sessions": {
            "task": "app.tasks.cleanup_tasks.cleanup_expired_redis_keys",
            "schedule": crontab(minute="*/30"),  # 每 30 分钟
        },
    },
)
