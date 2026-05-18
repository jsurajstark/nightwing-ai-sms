"""Map common LLM field aliases to Nightwing Core extraction keys."""

from __future__ import annotations

from typing import Any

# LLM outputs often use patient_* or camelCase; Core expects first_name, last_name, mobile, synopsis.
_FIELD_ALIASES: dict[str, str] = {
    "patient_first_name": "first_name",
    "patientFirstName": "first_name",
    "patient_last_name": "last_name",
    "patientLastName": "last_name",
    "patient_phone": "mobile",
    "patientPhone": "mobile",
    "phone": "mobile",
    "phone_number": "mobile",
    "service_requested": "synopsis",
    "serviceRequested": "synopsis",
    "service": "synopsis",
}


def normalize_extraction(parsed: dict[str, Any]) -> dict[str, Any]:
    """Return a copy with canonical keys; canonical values win over aliases."""
    if not isinstance(parsed, dict):
        return parsed

    out: dict[str, Any] = dict(parsed)
    for alias, canonical in _FIELD_ALIASES.items():
        if alias not in out:
            continue
        alias_val = out.pop(alias)
        if not _present(out.get(canonical)) and _present(alias_val):
            out[canonical] = alias_val
    return out


def _present(val: object) -> bool:
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    return True
