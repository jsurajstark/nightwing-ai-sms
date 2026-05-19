#!/usr/bin/env python3
"""Smoke-test Core partial-referral API using the same payload builder as the SMS pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

# Run from nightwing_ai_sms_demo: python scripts/test_core_partial.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sms_demo.config import get_settings
from sms_demo.services.extraction_normalize import normalize_extraction
from sms_demo.utility.core_client import CorePartialReferralError, create_partial_referral
from sms_demo.utility.core_partial import to_partial_referral_request


def main() -> int:
    settings = get_settings()
    token = (settings.core_api_access_token or "").strip()
    if not token:
        print("Set CORE_API_ACCESS_TOKEN in .env", file=sys.stderr)
        return 1
    client_id = settings.core_default_client_id

    parsed = normalize_extraction(
        {
            "patient_first_name": "Ana",
            "patient_last_name": "Garcia",
            "patient_phone": "+15554443567",
            "service_requested": "Needs ortho",
            "confidence": 0.9,
        }
    )
    body = to_partial_referral_request(parsed, client_id=client_id)
    print("Request body:", body)

    try:
        data = create_partial_referral(
            settings.core_api_base_url,
            token,
            body,
            timeout=settings.core_api_timeout_s,
        )
    except CorePartialReferralError as e:
        print(f"FAILED: {e} (status={e.status_code})", file=sys.stderr)
        if e.body is not None:
            print(e.body, file=sys.stderr)
        return 1

    print("SUCCESS:", data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
