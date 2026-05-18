"""Prefer patient names copied from the raw SMS over LLM substitutions."""

from __future__ import annotations

import re

# "Patient Raj Patel", "Referral for Jane Doe", "pt. Maria Garcia", etc.
_NAME_AFTER_LABEL = re.compile(
    r"(?i)\b(?:patient|pt\.?|referral\s+for)\s+"
    r"([A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*(?:\s+[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*){0,3})"
)

# Words that follow a name in messy SMS (not part of the name).
_STOP_TOKENS = frozenset(
    {
        "need",
        "needs",
        "needed",
        "mobile",
        "phone",
        "tel",
        "referred",
        "referral",
        "for",
        "with",
        "at",
        "in",
        "on",
        "and",
        "or",
        "the",
        "a",
        "an",
        "mri",
        "ct",
        "xray",
        "x-ray",
        "ortho",
        "consult",
        "appointment",
        "appt",
    }
)


def _name_tokens(chunk: str) -> list[str]:
    tokens: list[str] = []
    for raw in chunk.strip().split():
        word = raw.strip(".,;:")
        if not word:
            continue
        if word.casefold() in _STOP_TOKENS:
            break
        tokens.append(word)
        if len(tokens) >= 4:
            break
    return tokens


def names_in_text(text: str) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    match = _NAME_AFTER_LABEL.search(text)
    if not match:
        return None, None
    parts = _name_tokens(match.group(1))
    if len(parts) >= 2:
        return parts[0], parts[-1]
    if len(parts) == 1:
        return parts[0], None
    return None, None


def _token_in_text(token: str, text: str) -> bool:
    if not token or not text:
        return False
    return token.casefold() in text.casefold()


def reconcile_extraction_names(raw: str, parsed: dict) -> dict:
    if not isinstance(parsed, dict):
        return parsed

    raw_first, raw_last = names_in_text(raw)
    if not raw_first:
        return parsed

    out = dict(parsed)
    llm_first = out.get("first_name")
    llm_last = out.get("last_name")

    if not _present(llm_first) or not _token_in_text(str(llm_first), raw):
        out["first_name"] = raw_first
    if raw_last:
        if not _present(llm_last) or not _token_in_text(str(llm_last), raw):
            out["last_name"] = raw_last
    return out


def _present(val: object) -> bool:
    if val is None:
        return False
    if isinstance(val, str) and not val.strip():
        return False
    return True
