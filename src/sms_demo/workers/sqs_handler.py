"""
AWS SQS consumer entrypoint for production (Lambda or ECS).

Wire your queue's event source to call ``handle_sqs_records`` or ``handle_sqs_record``.
Each message body must be JSON: ``{"intake_id": <int>, "job": "extract_intake"}``
(same shape as ``SqsExtractionQueue.enqueue_extraction``).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sms_demo.logging_config import configure_logging
from sms_demo.services.pipeline import complete_intake

configure_logging()
logger = logging.getLogger(__name__)


def _parse_intake_id(body: str) -> int:
    payload = json.loads(body)
    intake_id = payload.get("intake_id")
    if intake_id is None:
        raise ValueError(f"SQS message missing intake_id: {body!r}")
    return int(intake_id)


def handle_sqs_record(record: dict[str, Any]) -> None:
    """Process one SQS record (Lambda event record or polled message dict)."""
    body = record.get("body") or record.get("Body") or ""
    intake_id = _parse_intake_id(body)
    logger.info("SQS worker processing intake_id=%s", intake_id)
    complete_intake(intake_id)


def handle_sqs_records(records: list[dict[str, Any]]) -> None:
    for record in records:
        handle_sqs_record(record)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, str]:
    """AWS Lambda handler for SQS event source mapping."""
    handle_sqs_records(event.get("Records", []))
    return {"statusCode": "200"}
