from __future__ import annotations

import json
import logging

from sms_demo.config import Settings

logger = logging.getLogger(__name__)

MESSAGE_TYPE_EXTRACTION = "sms_extraction"


class SqsExtractionQueue:
    """Production: enqueue extraction jobs to AWS SQS (Lambda/ECS consumer)."""

    def __init__(self, settings: Settings) -> None:
        if not settings.sqs_queue_url:
            raise RuntimeError("SQS_QUEUE_URL is required when QUEUE_BACKEND=sqs")
        if not settings.aws_region:
            raise RuntimeError("AWS_REGION is required when QUEUE_BACKEND=sqs")
        self._queue_url = settings.sqs_queue_url
        self._region = settings.aws_region
        self._client = None

    def _sqs_client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as e:
                raise RuntimeError(
                    "boto3 is required for QUEUE_BACKEND=sqs; install with: pip install 'nightwing-ai-sms-demo[sqs]'"
                ) from e
            self._client = boto3.client("sqs", region_name=self._region)
        return self._client

    def enqueue(self, intake_id: int) -> None:
        body = json.dumps({"type": MESSAGE_TYPE_EXTRACTION, "intake_id": intake_id})
        self._sqs_client().send_message(QueueUrl=self._queue_url, MessageBody=body)
        logger.info("SQS extraction enqueued intake_id=%s queue=%s", intake_id, self._queue_url)
