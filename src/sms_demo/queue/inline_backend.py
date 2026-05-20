from __future__ import annotations

import logging
import threading

from sms_demo.queue.base import ExtractionQueueBackend

logger = logging.getLogger(__name__)


class InlineExtractionQueue(ExtractionQueueBackend):
    """
    Dev-only: run extraction in a daemon thread (no Redis/Celery).

    Prefer ``celery`` for the real queue demo; use this only when Redis is unavailable.
    """

    def enqueue_extraction(self, intake_id: int) -> None:
        from sms_demo.services.pipeline import complete_intake, intake_is_finished

        if intake_is_finished(intake_id):
            logger.info("Inline skip enqueue intake_id=%s — already extracted", intake_id)
            return

        logger.info("Inline thread enqueue intake_id=%s", intake_id)
        threading.Thread(target=complete_intake, args=(intake_id,), daemon=True).start()
