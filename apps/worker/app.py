"""ChangeScope Celery Worker Application Configuration."""

from celery import Celery

from packages.shared.config import settings

celery_app = Celery(
    "changescope_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["apps.worker.tasks"],
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
        "apps.worker.tasks.process_scan_task": {"queue": "scans"},
        "apps.worker.tasks.process_outbox_task": {"queue": "outbox"},
        "apps.worker.tasks.aggregate_otel_traces_task": {"queue": "otel"},
    },
    beat_schedule={
        "poll-outbox-every-5-seconds": {
            "task": "apps.worker.tasks.process_outbox_task",
            "schedule": 5.0,
        },
        "aggregate-traces-every-60-seconds": {
            "task": "apps.worker.tasks.aggregate_otel_traces_task",
            "schedule": 60.0,
        },
    },
)
