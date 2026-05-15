from __future__ import annotations

import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker, selectinload

from sms_demo.config import Settings, get_settings
from sms_demo.db import get_engine
from sms_demo.llm import LLMError, get_provider
from sms_demo.models import Extraction, Intake, PartialReferral, RoutingDecision
from sms_demo.services.partial_mapper import to_stub_payload
from sms_demo.services.phone_extract import reconcile_extraction_phones
from sms_demo.services.routing import RoutingOutcome, decide
from sms_demo.services.stub_core import apply_partial_referral

logger = logging.getLogger(__name__)


def _load_extraction_prompt() -> str:
    path = Path(__file__).resolve().parent.parent / "prompts" / "extraction.txt"
    return path.read_text(encoding="utf-8")


def _model_name(settings: Settings) -> str:
    if (settings.llm_provider or "").lower() == "ollama":
        return settings.ollama_model
    return settings.llm_provider or "unknown"


def intake_is_processing(intake: Intake) -> bool:
    """True while LLM extraction has not finished (intake saved, no routing yet)."""
    if not (intake.raw_body or "").strip():
        return False
    return len(intake.routing_decisions) == 0


def _persist_empty_intake(db: Session, settings: Settings, intake: Intake, raw: str) -> Intake:
    db.add(
        Extraction(
            intake_id=intake.id,
            model_provider=settings.llm_provider,
            model_name=_model_name(settings),
            raw_json=None,
            parsed_json=None,
            error=None,
        )
    )
    route = decide(None, raw_body=raw)
    db.add(
        RoutingDecision(
            intake_id=intake.id,
            decision=route.decision,
            reason=route.reason,
            confidence=route.confidence,
        )
    )
    db.flush()
    db.commit()
    db.refresh(intake)
    return intake


def _run_llm_phase(db: Session, settings: Settings, intake: Intake, raw: str) -> None:
    logger.info(
        "Extraction start intake_id=%s provider=%s model=%s",
        intake.id,
        settings.llm_provider,
        _model_name(settings),
    )
    provider = get_provider(settings)
    system_prompt = _load_extraction_prompt()
    parsed: dict | None = None
    extraction_error: str | None = None
    raw_model_json: str | None = None

    try:
        parsed = provider.extract_referral(raw, system_prompt)
        parsed = reconcile_extraction_phones(raw, parsed)
        raw_model_json = json.dumps(parsed, default=str)
        logger.info(
            "Extraction done intake_id=%s first=%r last=%r phone=%r",
            intake.id,
            parsed.get("patient_first_name") if isinstance(parsed, dict) else None,
            parsed.get("patient_last_name") if isinstance(parsed, dict) else None,
            parsed.get("patient_phone") if isinstance(parsed, dict) else None,
        )
    except LLMError as e:
        extraction_error = str(e)
        logger.error("Extraction failed intake_id=%s: %s", intake.id, e)

    db.add(
        Extraction(
            intake_id=intake.id,
            model_provider=settings.llm_provider,
            model_name=_model_name(settings),
            raw_json=raw_model_json,
            parsed_json=raw_model_json,
            error=extraction_error,
        )
    )
    db.flush()

    if extraction_error:
        route = RoutingOutcome("review", f"llm_error:{extraction_error[:200]}", None)
    else:
        assert parsed is not None
        route = decide(parsed, raw_body=raw)

    logger.info(
        "Routing intake_id=%s decision=%s reason=%s",
        intake.id,
        route.decision,
        route.reason,
    )

    db.add(
        RoutingDecision(
            intake_id=intake.id,
            decision=route.decision,
            reason=route.reason,
            confidence=route.confidence,
        )
    )

    if route.decision == "auto" and parsed is not None:
        payload = to_stub_payload(parsed)
        stub_out = apply_partial_referral(payload)
        db.add(
            PartialReferral(
                intake_id=intake.id,
                referral_id=str(stub_out["referral_id"]),
                status=str(stub_out["status"]),
                stub_response_json=json.dumps(stub_out, default=str),
            )
        )


def create_intake(
    db: Session,
    settings: Settings,
    raw: str,
    *,
    source: str,
    external_id: str | None = None,
) -> Intake:
    """
    Persist intake and commit immediately for non-empty bodies so the console can show
    "processing" while Ollama runs (call ``complete_intake`` or background task after).
    """
    intake = Intake(raw_body=raw, source=source, external_id=external_id)
    db.add(intake)
    db.flush()

    if not (raw or "").strip():
        return _persist_empty_intake(db, settings, intake, raw)

    db.commit()
    db.refresh(intake)
    return intake


def complete_intake(intake_id: int) -> None:
    """Finish LLM extraction + routing in a fresh session (for background tasks)."""
    logger.info("Background extraction queued intake_id=%s", intake_id)
    settings = get_settings()
    Session = sessionmaker(bind=get_engine())
    with Session() as db:
        intake = db.get(Intake, intake_id)
        if intake is None:
            logger.warning("Background extraction skipped: intake_id=%s not found", intake_id)
            return
        if not intake_is_processing(intake):
            logger.info("Background extraction skipped: intake_id=%s already complete", intake_id)
            return
        _run_llm_phase(db, settings, intake, intake.raw_body)
        db.commit()
    logger.info("Background extraction finished intake_id=%s", intake_id)


def run_intake(
    db: Session,
    settings: Settings,
    raw: str,
    *,
    source: str,
    external_id: str | None = None,
) -> Intake:
    """Synchronous full pipeline (seed script, tests)."""
    intake = create_intake(db, settings, raw, source=source, external_id=external_id)
    if intake_is_processing(intake):
        _run_llm_phase(db, settings, intake, raw)
        db.commit()
        db.refresh(intake)
    return intake


def list_intakes_for_console(db: Session, limit: int = 50) -> list[Intake]:
    stmt = (
        select(Intake)
        .options(
            selectinload(Intake.extractions),
            selectinload(Intake.routing_decisions),
            selectinload(Intake.partial_referrals),
        )
        .order_by(Intake.created_at.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
