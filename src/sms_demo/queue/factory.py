from __future__ import annotations

import logging
from functools import lru_cache

from sms_demo.config import Settings, get_settings
from sms_demo.queue.base import ExtractionQueueBackend
from sms_demo.queue.celery_backend import CeleryExtractionQueue
from sms_demo.queue.inline_backend import InlineExtractionQueue
from sms_demo.queue.sqs_backend import SqsExtractionQueue

logger = logging.getLogger(__name__)


@lru_cache
def get_queue_backend() -> ExtractionQueueBackend:
    settings = get_settings()
    backend = (settings.queue_backend or "celery").lower()
    if backend == "celery":
        return CeleryExtractionQueue()
    if backend == "sqs":
        return SqsExtractionQueue()
    if backend == "inline":
        return InlineExtractionQueue()
    raise ValueError(
        f"Unknown QUEUE_BACKEND={settings.queue_backend!r}; "
        "use 'celery' (demo), 'sqs' (production), or 'inline' (dev, no Redis)"
    )


def reset_queue_backend_cache() -> None:
    """Clear cached backend after QUEUE_BACKEND changes in .env."""
    get_queue_backend.cache_clear()


def enqueue_extraction(intake_id: int) -> None:
    """Publish extraction job for intake_id."""
    logger.info("Enqueue extraction intake_id=%s backend=%s", intake_id, get_settings().queue_backend)
    get_queue_backend().enqueue_extraction(intake_id)


def purge_extraction_queue() -> None:
    """Drop pending Celery tasks (no-op for inline/sqs)."""
    settings = get_settings()
    if (settings.queue_backend or "").lower() != "celery":
        return
    try:
        from sms_demo.celery_app import celery_app

        queue = settings.celery_queue_name or "sms_extraction"
        purged = celery_app.control.purge()
        logger.info("Purged Celery queue=%s (approx %s message(s))", queue, purged)
    except Exception as exc:
        logger.warning("Could not purge Celery queue: %s", exc)
