"""Map LLM extraction JSON (Core field names) to full Core referral payload."""

from __future__ import annotations

from typing import Any

from sms_demo.utility.referral_payload import ReferralPayload

_EXTRACTION_KEYS = frozenset(
    {
        "first_name",
        "last_name",
        "username",
        "mobile",
        "email",
        "dob",
        "gender",
        "language",
        "injury_date",
        "injury_time",
        "synopsis",
        "clinical_services",
        "address1",
        "address2",
        "postal_code",
        "state_name",
        "city_name",
        "postal_flag",
        "clientId",
        "caseManagerId",
        "fax_number",
        "accident_type",
        "notes",
        "documents",
        "parent_relationId",
        "pharmacyId",
        "commercial_case",
        "permission_type",
    }
)


def extraction_to_core_payload(
    parsed: dict[str, Any],
    *,
    source: str = "sms",
    default_confidence: float = 0.75,
) -> dict[str, Any]:
    """Merge extraction into a full Core-shaped dict; unset fields stay null."""
    base = ReferralPayload(source=source, confidence=default_confidence).model_dump()

    for key in _EXTRACTION_KEYS:
        if key not in parsed:
            continue
        val = parsed[key]
        if val is not None:
            base[key] = val

    try:
        conf = parsed.get("confidence")
        if conf is not None:
            base["confidence"] = float(conf)
    except (TypeError, ValueError):
        pass

    base["source"] = source
    return base
