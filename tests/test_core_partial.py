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
        self.assertEqual(body["mobile"], "15551234567")

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


if __name__ == "__main__":
    unittest.main()
