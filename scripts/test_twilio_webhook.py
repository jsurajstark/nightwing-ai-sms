#!/usr/bin/env python3
"""POST a Twilio-signed inbound SMS to the demo webhook (local and/or public URL).

Uses the same signature algorithm as Twilio (see sms_demo.services.twilio_signature).
Signature is built with PUBLIC_BASE_URL from .env — even when posting to localhost.

Requires:
  - ENABLE_TWILIO_WEBHOOK=true, TWILIO_AUTH_TOKEN, PUBLIC_BASE_URL in .env
  - `make demo` (or uvicorn) running

Examples:
  python scripts/test_twilio_webhook.py
  python scripts/test_twilio_webhook.py --all
  python scripts/test_twilio_webhook.py --index 3
  python scripts/test_twilio_webhook.py --local-only
  python scripts/test_twilio_webhook.py --public-only
  python scripts/test_twilio_webhook.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import uuid

import httpx

from sms_demo.config import get_settings
from sms_demo.services.twilio_signature import compute_signature

WEBHOOK_PATH = "/webhooks/twilio/sms"

# 10 sample inbound SMS bodies — different patients and clinical needs/services.
SAMPLE_SMS_BODIES: list[str] = [
    "yashraj patel needs medical examination this week",
    "Referral for eric defrancis needs MRI lumbar spine this week.",
    "Patient Maria Garcia needs cardiology workup — chest tightness, PCP wants stress test or echo.",
    "Robert Chen +1 415-555-0192 needs physical therapy for rotator cuff tear after work injury.",
    "Urgent: James O'Brien needs CT scan abdomen — rule out appendicitis, pain since yesterday.",
    "Sofia Martinez needs dermatology consult for suspicious mole on left shoulder.",
    "Patient Raj Patel, mobile +91 98765 43210, needs ortho consult in Mumbai.",
    "Emily Nguyen needs endocrinology referral — newly diagnosed type 2 diabetes, A1C 9.2.",
    "William Thompson needs neurology evaluation for recurring migraines and vision changes.",
    "Ana Kowalski needs OB/GYN prenatal visit — 12 weeks pregnant, first appointment.",
]

DEFAULT_BODY = SAMPLE_SMS_BODIES[0]


def _twilio_params(body: str, message_sid: str) -> dict[str, str]:
    return {
        "Body": body,
        "MessageSid": message_sid,
        "From": "+15550001111",
        "To": "+18147133377",
        "AccountSid": "AC_test_script",
        "NumMedia": "0",
    }


def _signature(auth_token: str, public_base_url: str, params: dict[str, str]) -> str:
    base = public_base_url.rstrip("/")
    full_url = f"{base}{WEBHOOK_PATH}"
    return compute_signature(auth_token, full_url, params)


def _post(
    client: httpx.Client,
    *,
    target_base: str,
    auth_token: str,
    public_base_url: str,
    params: dict[str, str],
) -> tuple[str, int]:
    url = f"{target_base.rstrip('/')}{WEBHOOK_PATH}"
    sig = _signature(auth_token, public_base_url, params)
    resp = client.post(url, data=params, headers={"X-Twilio-Signature": sig})
    return url, resp.status_code


def _resolve_bodies(args: argparse.Namespace) -> list[str]:
    if args.body is not None:
        return [args.body]
    if args.all:
        return list(SAMPLE_SMS_BODIES)
    if args.index is not None:
        if not 1 <= args.index <= len(SAMPLE_SMS_BODIES):
            raise SystemExit(f"--index must be 1–{len(SAMPLE_SMS_BODIES)}")
        return [SAMPLE_SMS_BODIES[args.index - 1]]
    return [DEFAULT_BODY]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--body",
        default=None,
        help="SMS Body form field (overrides samples)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=f"POST all {len(SAMPLE_SMS_BODIES)} sample messages (one per MessageSid)",
    )
    parser.add_argument(
        "--index",
        type=int,
        metavar="N",
        help=f"Use sample message 1–{len(SAMPLE_SMS_BODIES)} from built-in list",
    )
    parser.add_argument(
        "--message-sid",
        default=None,
        help="MessageSid (default: SM_test_<random>; ignored with --all)",
    )
    parser.add_argument("--local-port", type=int, default=8000, help="Local uvicorn port")
    parser.add_argument("--local-only", action="store_true", help="Only POST to localhost")
    parser.add_argument(
        "--public-only",
        action="store_true",
        help="Only POST to PUBLIC_BASE_URL (e.g. ngrok)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print signature URL and MessageSid; do not POST",
    )
    args = parser.parse_args()

    if args.local_only and args.public_only:
        parser.error("Use at most one of --local-only and --public-only")
    if args.all and args.index is not None:
        parser.error("Use at most one of --all and --index")
    if args.body is not None and (args.all or args.index is not None):
        parser.error("--body cannot be combined with --all or --index")

    bodies = _resolve_bodies(args)

    settings = get_settings()
    if not settings.enable_twilio_webhook:
        print("ENABLE_TWILIO_WEBHOOK must be true in .env", file=sys.stderr)
        sys.exit(1)
    token = settings.twilio_auth_token
    public = settings.public_base_url
    if not token or not public:
        print("TWILIO_AUTH_TOKEN and PUBLIC_BASE_URL must be set in .env", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(f"Signature URL: {public.rstrip('/')}{WEBHOOK_PATH}")
        print(f"Messages: {len(bodies)}")
        for i, body in enumerate(bodies, start=1):
            preview = body if len(body) <= 72 else f"{body[:69]}..."
            print(f"  [{i}] {preview}")
        return

    targets: list[tuple[str, str]] = []
    if args.public_only:
        targets.append(("public", public))
    elif args.local_only:
        targets.append(("local", f"http://127.0.0.1:{args.local_port}"))
    else:
        targets.append(("local", f"http://127.0.0.1:{args.local_port}"))
        targets.append(("public", public))

    ok = True
    message_sids: list[str] = []
    with httpx.Client(timeout=60.0) as client:
        for msg_num, body in enumerate(bodies, start=1):
            if len(bodies) > 1:
                print(f"\n--- message {msg_num}/{len(bodies)} ---")
                print(body)
            message_sid = (
                args.message_sid
                if args.message_sid and len(bodies) == 1
                else f"SM_test_{uuid.uuid4().hex[:12]}"
            )
            message_sids.append(message_sid)
            params = _twilio_params(body, message_sid)
            for label, base in targets:
                url, status = _post(
                    client,
                    target_base=base,
                    auth_token=token,
                    public_base_url=public,
                    params=params,
                )
                mark = "OK" if status == 200 else "FAIL"
                print(f"{label}: {url} → HTTP {status} {mark}")
                if status != 200:
                    ok = False
            if len(bodies) > 1:
                print(f"MessageSid: {message_sid}")

    if len(message_sids) == 1:
        print(f"\nMessageSid: {message_sids[0]}")
    else:
        print(f"\nSent {len(message_sids)} messages.")
    print("Console: http://127.0.0.1:8000/demo/console")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
