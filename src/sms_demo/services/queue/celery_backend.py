from __future__ import annotations

import logging

from sms_demo.celery_app import complete_intake_task

logger = logging.getLogger(__name__)


class CeleryExtractionQueue:
    """Demo/MVP: publish extraction jobs to Redis via Celery."""

    def enqueue(self, intake_id: int) -> None:
        complete_intake_task.delay(intake_id)
        logger.info("Celery extraction enqueued intake_id=%s", intake_id)
