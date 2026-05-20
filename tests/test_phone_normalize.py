"""Tests for phone normalization and reconcile integration."""

from __future__ import annotations

import unittest

from sms_demo.services.phone_extract import reconcile_extraction_phones, reconcile_patient_phone
from sms_demo.services.phone_normalize import (
    format_mobile_us_display,
    normalize_mobile_for_core,
    strip_country_code,
    subscriber_digits,
)
from sms_demo.utility.core_partial import to_partial_referral_request


class StripCountryCodeTest(unittest.TestCase):
    def test_us_eleven_digit(self) -> None:
        self.assertEqual(strip_country_code("15551234567"), "5551234567")

    def test_india_ninety_one(self) -> None:
        self.assertEqual(strip_country_code("919876543210"), "9876543210")


class FormatMobileUsDisplayTest(unittest.TestCase):
    def test_us_formatted(self) -> None:
        self.assertEqual(format_mobile_us_display("(555) 123-4567"), "+15551234567")

    def test_india_from_message(self) -> None:
        self.assertEqual(format_mobile_us_display("+91 98765 43210"), "+19876543210")


class NormalizeMobileForCoreTest(unittest.TestCase):
    def test_us_plus_one(self) -> None:
        self.assertEqual(normalize_mobile_for_core("+15551234567"), "5551234567")

    def test_us_local_ten(self) -> None:
        self.assertEqual(normalize_mobile_for_core("5551234567"), "5551234567")

    def test_india(self) -> None:
        self.assertEqual(normalize_mobile_for_core("+919876543210"), "9876543210")

    def test_display_plus_one_india_subscriber(self) -> None:
        self.assertEqual(normalize_mobile_for_core("+19876543210"), "9876543210")


class ReconcilePatientPhoneTest(unittest.TestCase):
    def test_international_sms_us_display(self) -> None:
        raw = "Patient Raj Patel, mobile +91 98765 43210, needs ortho."
        self.assertEqual(reconcile_patient_phone(raw, "+19876543210"), "+19876543210")

    def test_no_phone_in_sms(self) -> None:
        self.assertIsNone(reconcile_patient_phone("Jane Doe needs MRI", "+15551234567"))


class ReconcileExtractionIntegrationTest(unittest.TestCase):
    def test_international_sample(self) -> None:
        raw = "Patient Raj Patel, mobile +91 98765 43210, needs ortho."
        parsed = reconcile_extraction_phones(
            raw,
            {"first_name": "Raj", "last_name": "Patel", "patient_phone": "+19876543210"},
        )
        self.assertEqual(parsed["mobile"], "+19876543210")
        body = to_partial_referral_request(parsed)
        self.assertEqual(body["mobile"], "9876543210")


if __name__ == "__main__":
    unittest.main()
