from __future__ import annotations

import logging

from sms_demo.queue.base import ExtractionQueueBackend

logger = logging.getLogger(__name__)


class CeleryExtractionQueue(ExtractionQueueBackend):
    """Demo/MVP: Redis broker via Celery."""

    def enqueue_extraction(self, intake_id: int) -> None:
        from sms_demo.services.pipeline import intake_is_finished
        from sms_demo.tasks.extraction import extract_intake_task

        if intake_is_finished(intake_id):
            logger.info("Celery skip enqueue intake_id=%s — already extracted", intake_id)
            return

        logger.info("Celery enqueue intake_id=%s", intake_id)
        extract_intake_task.apply_async(args=[intake_id])
