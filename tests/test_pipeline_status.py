"""Console pipeline status helpers."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from sms_demo.services.pipeline import (
    PIPELINE_COMPLETE,
    PIPELINE_PROCESSING,
    PIPELINE_QUEUED,
    intake_is_complete,
    intake_is_pending,
    intake_is_processing,
    intake_is_queued,
)


def _intake(*, status: str | None, raw: str = "hello", routing=None, extractions=None):
    return SimpleNamespace(
        raw_body=raw,
        pipeline_status=status,
        routing_decisions=routing or [],
        extractions=extractions or [],
        partial_referrals=[],
    )


class PipelineStatusTests(unittest.TestCase):
    def test_complete_intake_is_not_pending(self) -> None:
        intake = _intake(status=PIPELINE_COMPLETE, routing=[object()])
        self.assertTrue(intake_is_complete(intake))
        self.assertFalse(intake_is_pending(intake))
        self.assertFalse(intake_is_queued(intake))
        self.assertFalse(intake_is_processing(intake))

    def test_queued_intake_is_pending_without_results(self) -> None:
        intake = _intake(status=PIPELINE_QUEUED, routing=[object()], extractions=[object()])
        self.assertFalse(intake_is_complete(intake))
        self.assertTrue(intake_is_pending(intake))
        self.assertTrue(intake_is_queued(intake))
        self.assertFalse(intake_is_processing(intake))

    def test_processing_intake(self) -> None:
        intake = _intake(status=PIPELINE_PROCESSING)
        self.assertTrue(intake_is_processing(intake))
        self.assertFalse(intake_is_queued(intake))


if __name__ == "__main__":
    unittest.main()
