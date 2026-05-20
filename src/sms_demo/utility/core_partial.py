"""Build POST body for Core /api/v1/partial-referral from LLM extraction."""

from __future__ import annotations

from typing import Any

from sms_demo.services.phone_normalize import normalize_mobile_for_core
from sms_demo.utility.mapper import extraction_to_core_payload

# Columns on partial_referrals (writable via API; excludes id/timestamps/server-set FKs).
_CORE_PARTIAL_KEYS = frozenset(
    {
        "postedId",
        "referral_status",
        "clientId",
        "ownerPriority",
        "first_name",
        "middle_initial",
        "last_name",
        "dob",
        "email",
        "gender",
        "notes",
        "date",
        "clinicId",
        "clinic_typeId",
        "visit_date",
        "injury_details",
        "status",
        "injury_date",
        "injury_time",
        "synopsis",
        "state_name",
        "city_name",
        "postal_flag",
        "address1",
        "address2",
        "postal_code",
        "fax_number",
        "outBoundRefferalId",
        "uber_service",
        "latitude",
        "longitude",
        "caseManagerId",
        "lop_status",
        "lop_date",
        "pharmacyId",
        "username",
        "parent_relationId",
        "relation",
        "visit_status",
        "visit_description",
        "dos",
        "commercial_case",
        "accident_type",
        "userId",
        "locationId",
        "clientOfficeId",
        "isExisting",
        "service_time",
        "erfirst",
        "monday_item_id",
        "co_counsels",
        "rover_reference_id",
        "referral_source",
        "mobile",
        "language",
        "sms_text",
    }
)

# Demo-only / full-referral fields — never send to partial-referral endpoint.
_STRIP_KEYS = frozenset({"confidence", "source", "permission_type", "documents", "clinical_services"})


def _present(val: object) -> bool:
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    return True


def _normalize_mobile_for_core(value: object) -> str | None:
    """Core mobile: subscriber digits only (+15551234567 → 5551234567)."""
    return normalize_mobile_for_core(value)


def to_partial_referral_request(
    parsed: dict[str, Any],
    *,
    referral_source: str = "sms",
    client_id: int | None = None,
    sms_text: str | None = None,
) -> dict[str, Any]:
    """Map extraction → Core partial-referral JSON (non-null fields only; clientId optional)."""
    raw = extraction_to_core_payload(parsed, source=referral_source)
    body: dict[str, Any] = {}
    for key in _CORE_PARTIAL_KEYS:
        if key in _STRIP_KEYS:
            continue
        val = raw.get(key)
        if _present(val):
            body[key] = val
    body["referral_source"] = referral_source
    if client_id is not None and "clientId" not in body:
        body["clientId"] = client_id
    if "mobile" in body:
        normalized = _normalize_mobile_for_core(body["mobile"])
        if normalized:
            body["mobile"] = normalized
        else:
            del body["mobile"]
    if _present(sms_text):
        body["sms_text"] = str(sms_text).strip()
    return body
