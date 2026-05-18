from __future__ import annotations

import logging

from sms_demo.queue.base import ExtractionQueueBackend

logger = logging.getLogger(__name__)


class CeleryExtractionQueue(ExtractionQueueBackend):
    """Demo/MVP: Redis broker via Celery."""

    def enqueue_extraction(self, intake_id: int) -> None:
        from sms_demo.tasks.extraction import extract_intake_task

        extract_intake_task.delay(intake_id)
        logger.debug("Celery task queued intake_id=%s", intake_id)
