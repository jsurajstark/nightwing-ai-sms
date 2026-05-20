"""Prefer email addresses copied from the raw SMS over LLM substitutions."""

from __future__ import annotations

import re

_EMAIL_PATTERN = re.compile(
    r"(?i)\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


def emails_in_text(text: str) -> list[str]:
    """Email addresses in message order (deduped case-insensitively)."""
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    for match in _EMAIL_PATTERN.finditer(text):
        candidate = match.group(0).strip().rstrip(".,;:")
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        found.append(candidate)
    return found


def _emails_match(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()


def reconcile_patient_email(raw: str, llm_email: str | None) -> str | None:
    """
    Use only emails that appear in ``raw``. If the SMS has no email, return null
    (do not keep a model-invented address).
    """
    in_message = emails_in_text(raw)
    if not in_message:
        return None

    if llm_email:
        for candidate in in_message:
            if _emails_match(llm_email, candidate):
                return candidate

    return in_message[0]


def reconcile_extraction_emails(raw: str, parsed: dict) -> dict:
    if not isinstance(parsed, dict):
        return parsed
    llm_email = parsed.get("email")
    if llm_email is not None and not isinstance(llm_email, str):
        return parsed
    fixed = reconcile_patient_email(raw, llm_email)
    if fixed == llm_email:
        return parsed
    if fixed is None:
        out = dict(parsed)
        out.pop("email", None)
        return out
    return {**parsed, "email": fixed}
