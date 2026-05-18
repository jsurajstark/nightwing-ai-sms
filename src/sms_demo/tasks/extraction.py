"""Celery task: run LLM extraction for one intake."""

from __future__ import annotations

import logging

from sms_demo.celery_app import celery_app
from sms_demo.logging_config import configure_logging

configure_logging()
logger = logging.getLogger(__name__)


@celery_app.task(name="sms_demo.tasks.extraction.extract_intake", bind=True, max_retries=3)
def extract_intake_task(self, intake_id: int) -> None:
    from sms_demo.services.pipeline import complete_intake

    logger.info("Celery worker starting extraction intake_id=%s", intake_id)
    try:
        complete_intake(intake_id)
    except Exception as exc:
        logger.exception("Extraction task failed intake_id=%s", intake_id)
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries)) from exc
