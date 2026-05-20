"""Prefer patient names copied from the raw SMS over LLM substitutions."""

from __future__ import annotations

import re

# Order matters: specific labels before generic "patient" (avoid "Patient Referral:" false match).
_NAME_PATTERNS = (
    re.compile(
        r"(?i)\bnew\s+patient\s+referral\s*:\s*"
        r"([A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*(?:\s+[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*){0,3})"
    ),
    re.compile(
        r"(?i)\breferral\s*:\s*"
        r"([A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*(?:\s+[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*){0,3})"
    ),
    re.compile(
        r"(?i)\breferral\s+for\s+"
        r"([A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*(?:\s+[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*){0,3})"
    ),
    re.compile(
        r"(?i)\b(?:patient|pt\.?)\s+(?!referral\b)"
        r"([A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*(?:\s+[A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F'.-]*){0,3})"
    ),
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
    match = None
    for pattern in _NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            break
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


def extracted_names_match_raw(raw: str, parsed: dict) -> bool:
    """False when SMS clearly names a patient but extraction names are not in the message."""
    if not isinstance(parsed, dict):
        return True
    raw_first, raw_last = names_in_text(raw)
    if not raw_first:
        return True
    ext_first = parsed.get("first_name")
    ext_last = parsed.get("last_name")
    if not _present(ext_first):
        return False
    if not _token_in_text(str(ext_first), raw):
        return False
    if raw_last:
        if not _present(ext_last) or not _token_in_text(str(ext_last), raw):
            return False
    return True


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
