"""Shared referral utilities (stub Core today; email / real Core later)."""

from sms_demo.utility.mapper import extraction_to_core_payload
from sms_demo.utility.referral_payload import ReferralPayload
from sms_demo.utility.stub_core import apply_partial_referral

__all__ = [
    "ReferralPayload",
    "apply_partial_referral",
    "extraction_to_core_payload",
]
