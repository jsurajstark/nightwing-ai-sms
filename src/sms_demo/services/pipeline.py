from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker, selectinload

from sms_demo.config import Settings, get_settings
from sms_demo.db import get_engine
from sms_demo.llm import LLMError, get_provider
from sms_demo.llm.retry import extract_with_retries
from sms_demo.models import Extraction, Intake, PartialReferral, RoutingDecision
from sms_demo.services.extraction_normalize import normalize_extraction
from sms_demo.services.name_extract import reconcile_extraction_names
from sms_demo.services.phone_extract import reconcile_extraction_phones
from sms_demo.services.llm_queue import llm_extraction_lock
from sms_demo.services.routing import RoutingOutcome, decide
from sms_demo.services.timing import format_duration_ms, utc_now, wall_duration_ms
from sms_demo.utility.mapper import extraction_to_core_payload
from sms_demo.utility.stub_core import apply_partial_referral

logger = logging.getLogger(__name__)


def _load_extraction_prompt() -> str:
    path = Path(__file__).resolve().parent.parent / "prompts" / "extraction.txt"
    return path.read_text(encoding="utf-8")


def _model_name(settings: Settings) -> str:
    provider = (settings.llm_provider or "").lower()
    if provider == "ollama":
        return settings.ollama_model
    if provider == "gemini":
        return settings.gemini_model
    return settings.llm_provider or "unknown"


def llm_extraction_label(settings: Settings) -> str:
    """Display name for console UI while extraction runs."""
    provider = (settings.llm_provider or "ollama").lower()
    if provider == "gemini":
        return f"Gemini ({settings.gemini_model})"
    if provider == "ollama":
        return f"Ollama ({settings.ollama_model})"
    return _model_name(settings)


PIPELINE_QUEUED = "queued"
PIPELINE_PROCESSING = "processing"
PIPELINE_COMPLETE = "complete"


def intake_is_pending(intake: Intake) -> bool:
    """True while extraction has not finished (saved intake, no routing yet)."""
    if not (intake.raw_body or "").strip():
        return False
    return len(intake.routing_decisions) == 0


def intake_is_queued(intake: Intake) -> bool:
    """True when waiting for the single LLM worker (another intake may be processing)."""
    if not intake_is_pending(intake):
        return False
    status = intake.pipeline_status
    return status in (None, PIPELINE_QUEUED)


def intake_is_processing(intake: Intake) -> bool:
    """True when this intake is actively calling the LLM."""
    if not intake_is_pending(intake):
        return False
    return intake.pipeline_status == PIPELINE_PROCESSING


def intake_timing_summary(intake: Intake) -> str:
    """Human-readable submit → extraction timing for console rows."""
    if intake_is_queued(intake):
        return "Queued"
    if intake_is_processing(intake):
        return "Extracting…"
    if intake.processing_duration_ms is not None:
        total = format_duration_ms(intake.processing_duration_ms)
        ext = intake.extractions[-1] if intake.extractions else None
        if ext and ext.llm_duration_ms is not None:
            llm = format_duration_ms(ext.llm_duration_ms)
            return f"{total} total · {llm} LLM"
        return f"{total} total"
    return "—"


def _mark_intake_complete(
    intake: Intake,
    *,
    llm_duration_ms: float | None = None,
) -> None:
    intake.pipeline_status = PIPELINE_COMPLETE
    completed_at = utc_now()
    intake.processing_completed_at = completed_at
    intake.processing_duration_ms = wall_duration_ms(intake.created_at, completed_at)
    if llm_duration_ms is not None:
        logger.info(
            "Intake timing intake_id=%s total=%.0fms llm=%.0fms",
            intake.id,
            intake.processing_duration_ms,
            llm_duration_ms,
        )
    else:
        logger.info(
            "Intake timing intake_id=%s total=%.0fms",
            intake.id,
            intake.processing_duration_ms,
        )


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
    intake.pipeline_status = PIPELINE_COMPLETE
    _mark_intake_complete(intake)
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
    llm_duration_ms: float | None = None

    llm_started = time.perf_counter()
    try:
        parsed = extract_with_retries(provider, raw, system_prompt, settings)
        parsed = normalize_extraction(parsed)
        parsed = reconcile_extraction_names(raw, parsed)
        parsed = reconcile_extraction_phones(raw, parsed)
        raw_model_json = json.dumps(parsed, default=str)
        logger.info(
            "Extraction done intake_id=%s first=%r last=%r mobile=%r",
            intake.id,
            parsed.get("first_name") if isinstance(parsed, dict) else None,
            parsed.get("last_name") if isinstance(parsed, dict) else None,
            parsed.get("mobile") if isinstance(parsed, dict) else None,
        )
    except LLMError as e:
        extraction_error = str(e)
        logger.error("Extraction failed intake_id=%s: %s", intake.id, e)
    finally:
        llm_duration_ms = (time.perf_counter() - llm_started) * 1000.0

    db.add(
        Extraction(
            intake_id=intake.id,
            model_provider=settings.llm_provider,
            model_name=_model_name(settings),
            raw_json=raw_model_json,
            parsed_json=raw_model_json,
            error=extraction_error,
            llm_duration_ms=llm_duration_ms,
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
        payload = extraction_to_core_payload(parsed, source="sms")
        stub_out = apply_partial_referral(payload)
        ref_id = stub_out.get("referral_id")
        db.add(
            PartialReferral(
                intake_id=intake.id,
                referral_id=str(ref_id) if ref_id is not None else None,
                status=str(stub_out["status"]),
                stub_response_json=json.dumps(stub_out, default=str),
            )
        )

    _mark_intake_complete(intake, llm_duration_ms=llm_duration_ms)


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
    intake = Intake(
        raw_body=raw,
        source=source,
        external_id=external_id,
        pipeline_status=PIPELINE_QUEUED,
    )
    db.add(intake)
    db.flush()

    if not (raw or "").strip():
        return _persist_empty_intake(db, settings, intake, raw)

    db.commit()
    db.refresh(intake)
    return intake


def schedule_intake_extraction(intake_id: int) -> None:
    """Enqueue extraction (Celery+Redis demo, or SQS in production)."""
    from sms_demo.queue import enqueue_extraction

    enqueue_extraction(intake_id)


def complete_intake(intake_id: int) -> None:
    """Finish LLM extraction + routing (serialized — one LLM call at a time)."""
    logger.info("Extraction worker start intake_id=%s", intake_id)
    settings = get_settings()
    Session = sessionmaker(bind=get_engine())

    with llm_extraction_lock():
        with Session() as db:
            intake = db.get(Intake, intake_id)
            if intake is None:
                logger.warning("Background extraction skipped: intake_id=%s not found", intake_id)
                return
            if not intake_is_pending(intake):
                logger.info("Background extraction skipped: intake_id=%s already complete", intake_id)
                return
            intake.pipeline_status = PIPELINE_PROCESSING
            db.commit()
            logger.info("LLM slot acquired intake_id=%s", intake_id)

        try:
            with Session() as db:
                intake = db.get(Intake, intake_id)
                if intake is None or not intake_is_pending(intake):
                    return
                _run_llm_phase(db, settings, intake, intake.raw_body)
                db.commit()
        except Exception as exc:
            logger.exception("Background extraction failed intake_id=%s", intake_id)
            with Session() as db:
                intake = db.get(Intake, intake_id)
                if intake is None or not intake_is_pending(intake):
                    raise
                db.add(
                    Extraction(
                        intake_id=intake.id,
                        model_provider=settings.llm_provider,
                        model_name=_model_name(settings),
                        raw_json=None,
                        parsed_json=None,
                        error=f"pipeline_error:{exc!s}"[:500],
                    )
                )
                db.add(
                    RoutingDecision(
                        intake_id=intake.id,
                        decision="review",
                        reason=f"pipeline_error:{type(exc).__name__}",
                        confidence=None,
                    )
                )
                _mark_intake_complete(intake)
                db.commit()
            raise

    logger.info("Background extraction finished intake_id=%s", intake_id)


def recover_queued_intakes() -> None:
    """Re-enqueue intakes left queued after API or broker restart."""
    Session = sessionmaker(bind=get_engine())
    with Session() as db:
        stmt = select(Intake.id).where(Intake.pipeline_status == PIPELINE_QUEUED)
        intake_ids = list(db.scalars(stmt).all())
    for intake_id in intake_ids:
        logger.info("Recovering queued intake_id=%s", intake_id)
        schedule_intake_extraction(intake_id)


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
    if intake_is_pending(intake):
        intake.pipeline_status = PIPELINE_PROCESSING
        db.commit()
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
