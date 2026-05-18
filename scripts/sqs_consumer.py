#!/usr/bin/env python3
"""Poll SQS and run extraction (production ECS/Fargate worker; local testing).

Set QUEUE_BACKEND=sqs, SQS_QUEUE_URL, AWS_REGION, and AWS credentials, then:

  python scripts/sqs_consumer.py

Lambda: use the same message body and call ``complete_intake(intake_id)`` from the handler.
"""

from __future__ import annotations

import json
import logging
import signal
import sys
import time

from sms_demo.config import get_settings
from sms_demo.logging_config import configure_logging
from sms_demo.services.pipeline import complete_intake
from sms_demo.services.queue.sqs_backend import MESSAGE_TYPE_EXTRACTION

configure_logging()
logger = logging.getLogger(__name__)

_stop = False


def _handle_stop(*_args) -> None:
    global _stop
    _stop = True


def main() -> int:
    settings = get_settings()
    if (settings.queue_backend or "").lower() != "sqs":
        logger.error("QUEUE_BACKEND must be sqs (got %r)", settings.queue_backend)
        return 1
    if not settings.sqs_queue_url or not settings.aws_region:
        logger.error("SQS_QUEUE_URL and AWS_REGION are required")
        return 1

    try:
        import boto3
    except ImportError:
        logger.error("Install boto3: pip install 'nightwing-ai-sms-demo[sqs]'")
        return 1

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    client = boto3.client("sqs", region_name=settings.aws_region)
    queue_url = settings.sqs_queue_url
    logger.info("SQS consumer started queue=%s", queue_url)

    while not _stop:
        resp = client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            MessageAttributeNames=["All"],
        )
        messages = resp.get("Messages") or []
        for msg in messages:
            receipt = msg["ReceiptHandle"]
            try:
                body = json.loads(msg["Body"])
            except json.JSONDecodeError:
                logger.warning("Invalid JSON message_id=%s", msg.get("MessageId"))
                client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                continue
            if body.get("type") != MESSAGE_TYPE_EXTRACTION:
                logger.warning("Unknown message type=%r", body.get("type"))
                client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                continue
            intake_id = int(body["intake_id"])
            logger.info("Processing SQS message intake_id=%s", intake_id)
            complete_intake(intake_id)
            client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
        if not messages:
            time.sleep(0.1)

    logger.info("SQS consumer stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
