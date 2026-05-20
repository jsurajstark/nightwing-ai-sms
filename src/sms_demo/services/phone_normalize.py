"""Normalize phones for extraction (+1 display) and Core partial-referral (digits only)."""

from __future__ import annotations

import re

# Longest-first so e.g. 91 matches before 9.
_COUNTRY_PREFIXES = (
    "91",
    "44",
    "61",
    "49",
    "34",
    "33",
    "39",
    "81",
    "86",
    "55",
    "52",
    "1",
)

_MIN_SUBSCRIBER_DIGITS = 7


def digits_only(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\D", "", str(value))


def strip_country_code(digits: str) -> str:
    """Return subscriber digits with any detected country prefix removed."""
    if not digits:
        return ""

    # US NANP: 11 digits starting with 1
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]

    # Non-US prefixes only when length implies international (avoids stripping 55 from 555-xxx)
    if len(digits) > 10:
        for prefix in _COUNTRY_PREFIXES:
            if prefix == "1":
                continue
            if digits.startswith(prefix) and len(digits) > len(prefix) + _MIN_SUBSCRIBER_DIGITS - 1:
                return digits[len(prefix) :]

    return digits


def subscriber_digits(value: object) -> str:
    """Digits from a phone string with country code stripped."""
    return strip_country_code(digits_only(value))


def format_mobile_us_display(value: str) -> str | None:
    """Extraction / parsed JSON: +1 plus subscriber digits."""
    sub = subscriber_digits(value)
    if len(sub) < _MIN_SUBSCRIBER_DIGITS:
        return None
    return f"+1{sub}"


def normalize_mobile_for_core(value: object) -> str | None:
    """
    Core partial-referral mobile: subscriber digits only, no country prefix.
    US NANP must be exactly 10 digits after stripping leading 1.
    Other countries: return stripped subscriber digits when valid length.
    """
    raw = digits_only(value)
    sub = strip_country_code(raw)
    if not sub or len(sub) < _MIN_SUBSCRIBER_DIGITS:
        return None

    # US: 11-digit with leading 1 stripped, or bare 10-digit local
    if len(sub) == 10 and (
        (len(raw) == 11 and raw.startswith("1")) or (len(raw) == 10 and sub == raw)
    ):
        return sub

    # International: non-US country prefix was removed
    if sub != raw:
        return sub

    return None
