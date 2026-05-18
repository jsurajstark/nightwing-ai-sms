"""Celery application for demo/MVP extraction workers (broker: Redis)."""

from __future__ import annotations

from celery import Celery

from sms_demo.config import get_settings


def _celery_config() -> dict:
    settings = get_settings()
    return {
        "broker_url": settings.celery_broker_url,
        "result_backend": settings.celery_result_backend,
        "task_default_queue": settings.celery_task_queue,
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        "timezone": "UTC",
        "enable_utc": True,
        # One LLM extraction at a time per worker process (matches in-process lock intent).
        "worker_prefetch_multiplier": 1,
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
    }


celery_app = Celery("sms_demo")
celery_app.conf.update(_celery_config())


@celery_app.task(name="sms_demo.complete_intake", bind=True, max_retries=3)
def complete_intake_task(self, intake_id: int) -> None:
    from sms_demo.services.pipeline import complete_intake

    complete_intake(intake_id)
