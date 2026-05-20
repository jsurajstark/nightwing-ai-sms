"""Tests for email extraction from raw SMS."""

from __future__ import annotations

import unittest

from sms_demo.services.email_extract import (
    emails_in_text,
    reconcile_extraction_emails,
    reconcile_patient_email,
)
from sms_demo.services.extraction_normalize import normalize_extraction
from sms_demo.utility.core_partial import to_partial_referral_request


class EmailExtractTests(unittest.TestCase):
    def test_emails_in_text_finds_address(self) -> None:
        raw = "Madison Reed needs follow-up. Email: madison.reed@icloud.com"
        self.assertEqual(emails_in_text(raw), ["madison.reed@icloud.com"])

    def test_reconcile_uses_email_from_raw_when_llm_missing(self) -> None:
        raw = "Contact: patient@test.org for referral"
        fixed = reconcile_patient_email(raw, None)
        self.assertEqual(fixed, "patient@test.org")

    def test_reconcile_drops_invented_email(self) -> None:
        raw = "Referral for Jane Doe, phone +15551234567"
        self.assertIsNone(reconcile_patient_email(raw, "fake@example.com"))

    def test_reconcile_extraction_emails_adds_field(self) -> None:
        raw = "Madison Reed. Email madison.reed@icloud.com"
        parsed = reconcile_extraction_emails(
            raw,
            {"first_name": "Madison", "last_name": "Reed"},
        )
        self.assertEqual(parsed["email"], "madison.reed@icloud.com")

    def test_normalize_maps_patient_email(self) -> None:
        parsed = normalize_extraction(
            {"patient_email": "user@domain.com", "patient_first_name": "Ann"}
        )
        self.assertEqual(parsed["email"], "user@domain.com")
        self.assertEqual(parsed["first_name"], "Ann")

    def test_partial_referral_includes_email(self) -> None:
        body = to_partial_referral_request(
            {
                "first_name": "Madison",
                "last_name": "Reed",
                "email": "madison.reed@icloud.com",
                "synopsis": "prenatal follow-up",
            }
        )
        self.assertEqual(body["email"], "madison.reed@icloud.com")


if __name__ == "__main__":
    unittest.main()
