"""Celery application (demo/MVP — Redis broker)."""

from __future__ import annotations

from celery import Celery
from celery.signals import worker_ready

from sms_demo.config import get_settings

settings = get_settings()

celery_app = Celery(
    "nightwing_sms_demo",
    broker=settings.resolved_celery_broker_url,
    backend=settings.resolved_celery_result_backend,
    include=["sms_demo.tasks.extraction"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # One LLM extraction at a time per worker process (Ollama/local GPU).
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue=settings.celery_queue_name,
    task_routes={
        "sms_demo.tasks.extraction.extract_intake": {"queue": settings.celery_queue_name},
    },
)


@worker_ready.connect
def _recover_on_worker_ready(sender, **kwargs) -> None:
    """Re-enqueue pending intakes once when Celery worker starts (not on API reload)."""
    from sms_demo.services.pipeline import recover_queued_intakes

    recover_queued_intakes()
