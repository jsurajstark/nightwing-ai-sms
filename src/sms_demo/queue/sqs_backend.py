from __future__ import annotations

import json
import logging

from sms_demo.config import get_settings
from sms_demo.queue.base import ExtractionQueueBackend

logger = logging.getLogger(__name__)


class SqsExtractionQueue(ExtractionQueueBackend):
    """
    Production: AWS SQS → Lambda or ECS worker.

    The worker should call ``complete_intake(intake_id)`` (same entrypoint as Celery).
    """

    def enqueue_extraction(self, intake_id: int) -> None:
        settings = get_settings()
        if not settings.sqs_queue_url:
            raise RuntimeError("SQS_QUEUE_URL is required when QUEUE_BACKEND=sqs")

        try:
            import boto3
        except ImportError as e:
            raise RuntimeError(
                "boto3 is required for QUEUE_BACKEND=sqs; pip install 'nightwing-ai-sms-demo[sqs]'"
            ) from e

        client = boto3.client("sqs", region_name=settings.aws_region)
        body = json.dumps({"intake_id": intake_id, "job": "extract_intake"})
        client.send_message(QueueUrl=settings.sqs_queue_url, MessageBody=body)
        logger.info("SQS message sent intake_id=%s queue=%s", intake_id, settings.sqs_queue_url)
