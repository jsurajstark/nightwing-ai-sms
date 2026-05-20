"""Prefer phone numbers copied from the raw SMS over LLM substitutions (any country)."""

from __future__ import annotations

import re

# International-first patterns; avoid assuming US 3-3-4 only.
_PHONE_PATTERNS = (
    # +country code then subscriber digits (E.164-style in message)
    re.compile(r"\+\d{1,4}(?:[\s.\-()]*\d){5,14}"),
    # 00 prefix (common outside North America)
    re.compile(r"\b00\d{1,3}(?:[\s.\-]?\d){6,12}\b"),
    # North American optional +1 — only when number looks NANP (not default for all 10-digit)
    re.compile(r"\b\+?1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    # Grouped local/international (e.g. 020 7946 0958, 98765 43210)
    re.compile(r"\b\d{2,5}[-.\s/]?\d{3,4}[-.\s/]?\d{3,4}(?:[-.\s/]?\d{2,4})?\b"),
    # Compact 10–15 digits, optional leading +
    re.compile(r"(?<!\d)\+?\d{10,15}(?!\d)"),
)


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def phones_in_text(text: str) -> list[str]:
    """Phone-like substrings in message order (deduped by digit sequence)."""
    if not text:
        return []
    hits: list[tuple[int, str]] = []
    for pattern in _PHONE_PATTERNS:
        for match in pattern.finditer(text):
            hits.append((match.start(), match.group(0).strip()))
    hits.sort(key=lambda item: item[0])

    found: list[str] = []
    seen_digits: set[str] = set()
    for _, candidate in hits:
        digit_key = _digits(candidate)
        if len(digit_key) < 7 or digit_key in seen_digits:
            continue
        seen_digits.add(digit_key)
        found.append(candidate)
    return found


def _phones_match(left: str, right: str) -> bool:
    """Match without treating every number as US +1."""
    a, b = _digits(left), _digits(right)
    if not a or not b:
        return False
    if a == b:
        return True

    # Local vs +country: only if the longer form has '+' in the original text (real country code).
    if len(a) > len(b) and a.endswith(b) and left.strip().startswith("+"):
        return True
    if len(b) > len(a) and b.endswith(a) and right.strip().startswith("+"):
        return True
    return False


def reconcile_patient_phone(raw: str, llm_phone: str | None) -> str | None:
    """
    Use only phones that appear in ``raw``. If the SMS has no phone, return null
    (do not keep a model-invented number).
    """
    in_message = phones_in_text(raw)
    if not in_message:
        return None

    if llm_phone:
        for candidate in in_message:
            if _phones_match(llm_phone, candidate):
                return candidate

    return in_message[0]


def reconcile_extraction_phones(raw: str, parsed: dict) -> dict:
    if not isinstance(parsed, dict):
        return parsed
    llm_phone = parsed.get("mobile")
    if llm_phone is None:
        llm_phone = parsed.get("patient_phone")
    if llm_phone is not None and not isinstance(llm_phone, str):
        return parsed
    fixed = reconcile_patient_phone(raw, llm_phone)
    if fixed == llm_phone:
        return parsed
    out = dict(parsed)
    if fixed is None:
        out.pop("mobile", None)
        out.pop("patient_phone", None)
        return out
    out["mobile"] = fixed
    out.pop("patient_phone", None)
    return out
