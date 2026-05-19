#!/usr/bin/env python3
"""POST one Twilio-signed inbound SMS to the demo webhook.

Requires ENABLE_TWILIO_WEBHOOK=true, TWILIO_AUTH_TOKEN, PUBLIC_BASE_URL in .env
and the app running (`make demo` or uvicorn on port 8000).
"""

from __future__ import annotations

import sys
import uuid

import httpx

from sms_demo.config import get_settings
from sms_demo.services.twilio_signature import compute_signature

WEBHOOK_PATH = "/webhooks/twilio/sms"
DEFAULT_BODY = "Sarah Williams requires blood work and diabetes screening tomorrow morning."
LOCAL_PORT = 8000


def main() -> None:
    settings = get_settings()
    if not settings.enable_twilio_webhook:
        print("ENABLE_TWILIO_WEBHOOK must be true in .env", file=sys.stderr)
        sys.exit(1)

    token = settings.twilio_auth_token
    public = settings.public_base_url
    if not token or not public:
        print("TWILIO_AUTH_TOKEN and PUBLIC_BASE_URL must be set in .env", file=sys.stderr)
        sys.exit(1)

    message_sid = f"SM_test_{uuid.uuid4().hex[:12]}"
    params = {
        "Body": DEFAULT_BODY,
        "MessageSid": message_sid,
        "From": "+15550001111",
        "To": "+18147133377",
        "AccountSid": "AC_test_script",
        "NumMedia": "0",
    }

    sig_url = f"{public.rstrip('/')}{WEBHOOK_PATH}"
    sig = compute_signature(token, sig_url, params)

    post_url = f"http://127.0.0.1:{LOCAL_PORT}{WEBHOOK_PATH}"
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(
            post_url,
            data=params,
            headers={"X-Twilio-Signature": sig},
        )

    ok = resp.status_code == 200
    print(f"POST {post_url}")
    print(f"Body: {DEFAULT_BODY}")
    print(f"MessageSid: {message_sid}")
    print(f"HTTP {resp.status_code} {'OK' if ok else 'FAIL'}")
    print(f"Console: http://127.0.0.1:{LOCAL_PORT}/demo/console")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
