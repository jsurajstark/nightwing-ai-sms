"""Validate Twilio X-Twilio-Signature per https://www.twilio.com/docs/usage/security"""

from __future__ import annotations

import base64
import hashlib
import hmac


def compute_signature(auth_token: str, full_url: str, post_params: dict[str, str]) -> str:
    # Twilio: concatenate full URL + sorted key/value pairs (key + value)
    data = full_url
    for key in sorted(post_params.keys()):
        data += key
        data += post_params.get(key) or ""
    digest = hmac.new(
        auth_token.encode("utf-8"),
        data.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def is_valid_twilio_request(
    *,
    auth_token: str,
    public_base_url: str,
    request_path_with_query: str,
    post_params: dict[str, str],
    twilio_signature: str | None,
) -> bool:
    if not twilio_signature:
        return False
    base = public_base_url.rstrip("/")
    path = request_path_with_query if request_path_with_query.startswith("/") else f"/{request_path_with_query}"
    full_url = f"{base}{path}"
    expected = compute_signature(auth_token, full_url, post_params)
    return hmac.compare_digest(expected, twilio_signature)
