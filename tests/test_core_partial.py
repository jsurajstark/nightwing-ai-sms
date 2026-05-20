"""Tests for Core partial-referral payload builder."""

from __future__ import annotations

import unittest

from sms_demo.utility.core_partial import to_partial_referral_request


class ToPartialReferralRequestTest(unittest.TestCase):
    def test_mobile_strips_non_digits(self) -> None:
        body = to_partial_referral_request(
            {
                "first_name": "Maria",
                "last_name": "Garcia",
                "mobile": "+15551234567",
            }
        )
        self.assertEqual(body["mobile"], "5551234567")

    def test_mobile_strips_formatting(self) -> None:
        body = to_partial_referral_request(
            {
                "first_name": "Maria",
                "last_name": "Garcia",
                "mobile": "(555) 123-4567",
            }
        )
        self.assertEqual(body["mobile"], "5551234567")

    def test_mobile_omitted_when_no_digits(self) -> None:
        body = to_partial_referral_request(
            {
                "first_name": "Maria",
                "last_name": "Garcia",
                "mobile": "+--",
            }
        )
        self.assertNotIn("mobile", body)

    def test_mobile_strips_india_country_code(self) -> None:
        body = to_partial_referral_request(
            {
                "first_name": "Raj",
                "last_name": "Patel",
                "mobile": "+919876543210",
            }
        )
        self.assertEqual(body["mobile"], "9876543210")

    def test_sms_text_included_when_provided(self) -> None:
        body = to_partial_referral_request(
            {"first_name": "Maria", "last_name": "Garcia"},
            sms_text="Referral for Maria Garcia, phone +15551234567",
        )
        self.assertEqual(
            body["sms_text"],
            "Referral for Maria Garcia, phone +15551234567",
        )

    def test_sms_text_omitted_when_empty(self) -> None:
        body = to_partial_referral_request(
            {"first_name": "Maria", "last_name": "Garcia"},
            sms_text="   ",
        )
        self.assertNotIn("sms_text", body)


if __name__ == "__main__":
    unittest.main()
