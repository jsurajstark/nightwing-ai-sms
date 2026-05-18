"""In-process stub MyNightwing Core partial referral (extend via utility workflow later)."""

from __future__ import annotations

from typing import Any

from sms_demo.utility.referral_payload import ReferralPayload

REQUIRED_FOR_COMPLETE = ("first_name", "last_name")


def _present(val: object) -> bool:
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    return True


def apply_partial_referral(payload: dict[str, Any] | ReferralPayload) -> dict[str, Any]:
    """
    Stub Core response. referral_id is null until real Core creates a referral.
    missing_fields lists only first_name / last_name when absent.
    """
    if isinstance(payload, ReferralPayload):
        body = payload.model_dump()
    else:
        body = ReferralPayload.model_validate(payload).model_dump()

    missing: list[str] = []
    for key in REQUIRED_FOR_COMPLETE:
        if not _present(body.get(key)):
            missing.append(key)

    return {
        "referral_id": None,
        "status": "Incomplete",
        "missing_fields": missing,
        "echo": body,
    }
