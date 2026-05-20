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


def enqueue_extraction(intake_id: int) -> None:
    """Publish extraction job for intake_id."""
    logger.info("Enqueue extraction intake_id=%s backend=%s", intake_id, get_settings().queue_backend)
    get_queue_backend().enqueue_extraction(intake_id)
