"""In-process stub MyNightwing Core partial referral (no HTTP to self)."""

from __future__ import annotations

import uuid
from typing import Any


# Demo: only patient name required; phone and service are optional enrichments.
REQUIRED_FOR_COMPLETE = (
    "patient_first_name",
    "patient_last_name",
)


def apply_partial_referral(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Stub Core: always returns a synthetic referral id, Incomplete status,
    and missing_fields for any null/empty required field.
    """
    missing: list[str] = []
    for key in REQUIRED_FOR_COMPLETE:
        val = payload.get(key)
        if val is None or (isinstance(val, str) and not str(val).strip()):
            missing.append(key)

    ref = f"REF-{uuid.uuid4().hex[:8].upper()}"
    return {
        "referral_id": ref,
        "status": "Incomplete",
        "missing_fields": missing,
        "echo": {k: payload.get(k) for k in payload},
    }
