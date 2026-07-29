"""
Celery Configuration for SigmaFlow
===================================
Async task queue for running DMAIC pipelines in the background.
"""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from sigmaflow.core.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "sigmaflow",
    broker=settings.celery_broker_url or settings.redis_url,
    backend=settings.celery_result_backend or settings.redis_url,
    include=[
        "sigmaflow.worker.tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer=settings.celery_task_serializer,
    result_serializer=settings.celery_result_serializer,
    accept_content=settings.celery_accept_content,

    # Timezone
    timezone=settings.celery_timezone,
    enable_utc=settings.celery_enable_utc,

    # Task execution
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,

    # Worker
    worker_prefetch_multiplier=settings.celery_worker_prefetch_multiplier,
    worker_max_tasks_per_child=settings.celery_worker_max_tasks_per_child,

    # Results
    result_expires=3600,  # 1 hour
    result_extended=True,

    # Beat schedule (periodic tasks)
    beat_schedule={
        # The actual scheduled runs are stored in the database
        # and loaded dynamically by the beat scheduler
    },

    # Task routing
    task_routes={
        "sigmaflow.worker.tasks.run_pipeline": {"queue": "pipeline"},
        "sigmaflow.worker.tasks.run_scheduled_pipelines": {"queue": "scheduler"},
    },

    # Task default queue
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["sigmaflow.worker"])


@celery_app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to verify Celery is working."""
    print(f"Request: {self.request!r}")


if __name__ == "__main__":
    celery_app.start()