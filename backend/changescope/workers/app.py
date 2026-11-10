"""ChangeScope Celery Worker Application Configuration."""

from celery import Celery
from changescope.config import settings

celery_app = Celery(
    "changescope",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["changescope.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        "changescope.workers.tasks.process_scan_task": {"queue": "scans"},
        "changescope.workers.tasks.process_outbox_task": {"queue": "outbox"},
        "changescope.workers.tasks.aggregate_otel_traces_task": {"queue": "otel"},
    },
    beat_schedule={
        "poll-outbox-every-5-seconds": {
            "task": "changescope.workers.tasks.process_outbox_task",
            "schedule": 5.0,
        },
        "aggregate-traces-every-60-seconds": {
            "task": "changescope.workers.tasks.aggregate_otel_traces_task",
            "schedule": 60.0,
        },
    },
)
