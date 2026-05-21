"""HTTP client for Nightwing Core partial-referral API."""

from __future__ import annotations

from typing import Any

import httpx

_AUTH_HTTP_STATUSES = frozenset({401, 403})
_AUTH_MESSAGE_MARKERS = (
    "logged out",
    "log in again",
    "login again",
    "unauthorized",
    "invalid token",
    "access token",
    "token expired",
    "session expired",
)


class CorePartialReferralError(Exception):
    """Core API returned an error or unexpected response."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class CoreAuthError(CorePartialReferralError):
    """Core rejected the request because the access token is missing, invalid, or expired."""


def is_core_auth_failure(*, status_code: int | None, message: str | None) -> bool:
    """True when Core indicates the x-access-token is no longer valid."""
    if status_code in _AUTH_HTTP_STATUSES:
        return True
    if not message:
        return False
    lower = message.lower()
    return any(marker in lower for marker in _AUTH_MESSAGE_MARKERS)


def _raise_core_error(
    message: str,
    *,
    status_code: int | None = None,
    body: Any = None,
) -> None:
    if is_core_auth_failure(status_code=status_code, message=message):
        raise CoreAuthError(message, status_code=status_code, body=body)
    raise CorePartialReferralError(message, status_code=status_code, body=body)


def create_partial_referral(
    base_url: str,
    access_token: str,
    body: dict[str, Any],
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    POST /api/v1/partial-referral with x-access-token.
    Returns the `data` object from the Core envelope.
    """
    url = f"{base_url.rstrip('/')}/api/v1/partial-referral"
    headers = {
        "Content-Type": "application/json",
        "x-access-token": access_token,
    }
    try:
        resp = httpx.post(url, json=body, headers=headers, timeout=timeout)
    except httpx.HTTPError as e:
        raise CorePartialReferralError(f"Core request failed: {e}") from e

    try:
        envelope = resp.json()
    except ValueError:
        raise CorePartialReferralError(
            f"Core returned non-JSON (HTTP {resp.status_code})",
            status_code=resp.status_code,
            body=resp.text,
        ) from None

    if resp.status_code >= 400:
        msg = envelope.get("message") if isinstance(envelope, dict) else resp.text
        _raise_core_error(
            msg or f"HTTP {resp.status_code}",
            status_code=resp.status_code,
            body=envelope,
        )

    if not isinstance(envelope, dict):
        raise CorePartialReferralError("Unexpected Core response shape", body=envelope)

    if not envelope.get("success"):
        msg = envelope.get("message") or "Core partial-referral failed"
        _raise_core_error(msg, status_code=resp.status_code, body=envelope)

    data = envelope.get("data")
    if not isinstance(data, dict):
        raise CorePartialReferralError("Core response missing data object", body=envelope)

    return data
