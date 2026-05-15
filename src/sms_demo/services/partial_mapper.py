from __future__ import annotations

import json
from typing import Any


def to_stub_payload(parsed: dict) -> dict[str, Any]:
    """Map LLM extraction JSON to stub Core partial-referral input shape."""
    conf = parsed.get("confidence")
    try:
        confidence = float(conf) if conf is not None else 0.75
    except (TypeError, ValueError):
        confidence = 0.75

    return {
        "patient_first_name": parsed.get("patient_first_name"),
        "patient_last_name": parsed.get("patient_last_name"),
        "patient_phone": parsed.get("patient_phone"),
        "service_requested": parsed.get("service_requested"),
        "notes": parsed.get("notes"),
        "source": "sms",
        "confidence": confidence,
    }


def stub_payload_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)
