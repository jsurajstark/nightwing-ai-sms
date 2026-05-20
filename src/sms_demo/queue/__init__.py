"""Extraction job queue — Celery+Redis (demo) or AWS SQS (production)."""

from sms_demo.queue.factory import enqueue_extraction, get_queue_backend

__all__ = ["enqueue_extraction", "get_queue_backend"]
