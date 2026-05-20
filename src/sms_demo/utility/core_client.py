"""HTTP client for Nightwing Core partial-referral API."""

from __future__ import annotations

from typing import Any

import httpx


class CorePartialReferralError(Exception):
    """Core API returned an error or unexpected response."""

    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


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
        raise CorePartialReferralError(
            msg or f"HTTP {resp.status_code}",
            status_code=resp.status_code,
            body=envelope,
        )

    if not isinstance(envelope, dict):
        raise CorePartialReferralError("Unexpected Core response shape", body=envelope)

    if not envelope.get("success"):
        raise CorePartialReferralError(
            envelope.get("message") or "Core partial-referral failed",
            status_code=resp.status_code,
            body=envelope,
        )

    data = envelope.get("data")
    if not isinstance(data, dict):
        raise CorePartialReferralError("Core response missing data object", body=envelope)

    return data
