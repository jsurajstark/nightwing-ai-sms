from __future__ import annotations

import json
from dataclasses import dataclass

from sms_demo.services.name_extract import extracted_names_match_raw


@dataclass(frozen=True)
class RoutingOutcome:
    decision: str  # auto | review | spam
    reason: str
    confidence: float | None


def decide(parsed: dict | None, *, raw_body: str) -> RoutingOutcome:
    """Heuristic routing from extracted JSON + raw SMS (demo only; not production guardrails)."""
    text = (raw_body or "").strip()
    if not text:
        return RoutingOutcome("spam", "empty_message", None)

    lower = text.lower()
    if "ignore previous" in lower or "ignore all previous" in lower:
        return RoutingOutcome("spam", "prompt_injection_heuristic", None)

    if parsed is None:
        return RoutingOutcome("review", "no_parse", None)

    if (parsed.get("notes") or "").strip().lower() == "non_referral":
        return RoutingOutcome("spam", "model_marked_non_referral", _float(parsed.get("confidence")))

    # Required for auto-route: patient name only (phone/service optional for demo routing).
    # Extraction is normalized to first_name / last_name before routing (see extraction_normalize).
    required = ("first_name", "last_name")
    missing = [k for k in required if not _present(parsed.get(k))]
    if missing:
        return RoutingOutcome(
            "review",
            f"missing_fields:{','.join(missing)}",
            _float(parsed.get("confidence")),
        )

    if not extracted_names_match_raw(text, parsed):
        return RoutingOutcome(
            "review",
            "extraction_names_not_in_message",
            _float(parsed.get("confidence")),
        )

    return RoutingOutcome("auto", "complete_extraction", _float(parsed.get("confidence")))


def _present(v: object) -> bool:
    if v is None:
        return False
    if isinstance(v, str) and not v.strip():
        return False
    return True


def _float(v: object) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def outcome_to_dict(o: RoutingOutcome) -> dict:
    return {"decision": o.decision, "reason": o.reason, "confidence": o.confidence}


def outcome_json(o: RoutingOutcome) -> str:
    return json.dumps(outcome_to_dict(o))
