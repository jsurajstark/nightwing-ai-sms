from __future__ import annotations

from functools import lru_cache

from sms_demo.config import Settings, get_settings
from sms_demo.services.queue.base import ExtractionQueue
from sms_demo.services.queue.celery_backend import CeleryExtractionQueue
from sms_demo.services.queue.inline_backend import InlineExtractionQueue
from sms_demo.services.queue.sqs_backend import SqsExtractionQueue

_BACKENDS: dict[str, type] = {
    "celery": CeleryExtractionQueue,
    "sqs": SqsExtractionQueue,
    "inline": InlineExtractionQueue,
}


@lru_cache
def get_extraction_queue(settings: Settings | None = None) -> ExtractionQueue:
    settings = settings or get_settings()
    backend = (settings.queue_backend or "celery").lower()
    cls = _BACKENDS.get(backend)
    if cls is None:
        raise ValueError(
            f"Unknown QUEUE_BACKEND={backend!r}; use one of: {', '.join(sorted(_BACKENDS))}"
        )
    if backend == "sqs":
        return SqsExtractionQueue(settings)
    return cls()
