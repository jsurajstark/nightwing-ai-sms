"""Shared referral utilities (Core partial-referral + local stub fallback)."""

from sms_demo.utility.core_client import (
    CoreAuthError,
    CorePartialReferralError,
    create_partial_referral,
)
from sms_demo.utility.core_partial import to_partial_referral_request
from sms_demo.utility.mapper import extraction_to_core_payload
from sms_demo.utility.referral_payload import ReferralPayload
from sms_demo.utility.stub_core import apply_partial_referral

__all__ = [
    "CoreAuthError",
    "CorePartialReferralError",
    "ReferralPayload",
    "apply_partial_referral",
    "create_partial_referral",
    "extraction_to_core_payload",
    "to_partial_referral_request",
]
