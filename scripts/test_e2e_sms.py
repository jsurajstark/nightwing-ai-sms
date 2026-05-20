#!/usr/bin/env python3
"""End-to-end: SMS → LLM extraction → routing → Core partial-referral.

Run from nightwing_ai_sms_demo (requires .env LLM + Core settings):

  python scripts/test_e2e_sms.py
  python scripts/test_e2e_sms.py "Referral for Jane Doe, phone +15551234567, needs MRI."
  python scripts/test_e2e_sms.py --file samples/clean.txt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy.orm import sessionmaker

from sms_demo.config import get_settings
from sms_demo.db import get_engine
from sms_demo.services.pipeline import run_intake

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_SAMPLE = _ROOT / "samples" / "clean.txt"


def _load_sms(*, text: str | None, file_path: Path | None) -> str:
    if text is not None:
        return text
    path = file_path or _DEFAULT_SAMPLE
    if not path.is_file():
        print(f"Sample file not found: {path}", file=sys.stderr)
        sys.exit(2)
    return path.read_text(encoding="utf-8").strip()


def _json_loads(raw: str | None) -> dict | None:
    if not raw:
        return None
    try:
        val = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return val if isinstance(val, dict) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SMS intake pipeline end-to-end.")
    parser.add_argument(
        "sms",
        nargs="?",
        help="SMS body text (default: samples/clean.txt)",
    )
    parser.add_argument(
        "--file",
        "-f",
        type=Path,
        help="Read SMS body from file",
    )
    parser.add_argument(
        "--source",
        default="e2e_script",
        help="Intake source label (default: e2e_script)",
    )
    args = parser.parse_args()

    sms = _load_sms(text=args.sms, file_path=args.file)
    if not sms:
        print("SMS body is empty", file=sys.stderr)
        return 2

    settings = get_settings()
    Session = sessionmaker(bind=get_engine())

    print("=== E2E SMS test ===")
    print(f"LLM provider: {settings.llm_provider}")
    print(f"Core enabled: {settings.core_partial_referral_enabled}")
    print(f"Core base URL: {settings.core_api_base_url}")
    print(f"SMS ({len(sms)} chars): {sms!r}")
    print()

    try:
        with Session() as db:
            intake = run_intake(db, settings, sms, source=args.source)
            db.commit()

            ext = intake.extractions[0] if intake.extractions else None
            route = intake.routing_decisions[0] if intake.routing_decisions else None
            partial = intake.partial_referrals[0] if intake.partial_referrals else None
    except Exception as exc:
        print(f"PIPELINE FAILED: {exc}", file=sys.stderr)
        return 2

    parsed = _json_loads(ext.parsed_json if ext else None)
    core_response = _json_loads(partial.stub_response_json if partial else None)

    print(f"intake_id: {intake.id}")
    print(f"routing: {route.decision if route else '—'} ({route.reason if route else '—'})")
    if ext and ext.error:
        print(f"extraction error: {ext.error}")
    elif parsed:
        print(
            "extracted:",
            {
                k: parsed.get(k)
                for k in ("first_name", "last_name", "mobile", "synopsis", "confidence")
                if parsed.get(k) is not None
            },
        )
    else:
        print("extracted: —")

    if partial:
        print(f"partial_referral status: {partial.status}")
        print(f"core referral_id: {partial.referral_id}")
        if core_response:
            print("core response:", json.dumps(core_response, indent=2, default=str))
    else:
        print("partial_referral: not created (routing was not auto, or pipeline error)")

    if route and route.decision == "auto" and partial and partial.status == "created":
        print()
        print("SUCCESS: partial referral created on Core")
        return 0

    if partial and partial.status == "error":
        print()
        print("FAILED: Core partial-referral returned error (see core response above)", file=sys.stderr)
        return 1

    print()
    print(
        "INCOMPLETE: pipeline finished but no Core partial referral "
        "(check routing, CORE_* settings, or token)",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
