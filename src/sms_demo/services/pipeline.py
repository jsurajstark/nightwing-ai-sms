from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker, selectinload

from sms_demo.config import Settings, get_settings, reload_settings
from sms_demo.db import get_engine
from sms_demo.llm import LLMError, get_provider
from sms_demo.llm.retry import extract_with_retries
from sms_demo.models import Extraction, Intake, PartialReferral, RoutingDecision
from sms_demo.services.extraction_normalize import normalize_extraction
from sms_demo.services.name_extract import extracted_names_match_raw
from sms_demo.services.phone_extract import reconcile_extraction_phones
from sms_demo.services.llm_queue import llm_extraction_lock
from sms_demo.services.routing import RoutingOutcome, decide
from sms_demo.services.timing import format_duration_ms, utc_now, wall_duration_ms
from sms_demo.utility.core_client import CorePartialReferralError, create_partial_referral
from sms_demo.utility.core_partial import to_partial_referral_request
from sms_demo.utility.stub_core import apply_partial_referral

logger = logging.getLogger(__name__)


def _load_extraction_prompt() -> str:
    path = Path(__file__).resolve().parent.parent / "prompts" / "extraction.txt"
    return path.read_text(encoding="utf-8")


def _persist_partial_referral(
    db: Session,
    settings: Settings,
    intake_id: int,
    parsed: dict,
    *,
    sms_text: str,
) -> None:
    """Create partial referral on Core (or local stub when Core is disabled)."""
    body = to_partial_referral_request(
        parsed,
        referral_source="sms",
        client_id=settings.core_default_client_id,
        sms_text=sms_text,
    )
    core_row: dict
    status = "created"

    use_core = (
        settings.core_partial_referral_enabled
        and settings.core_api_access_token
        and settings.core_api_base_url
    )
    if use_core:
        try:
            core_row = create_partial_referral(
                settings.core_api_base_url,
                settings.core_api_access_token,
                body,
                timeout=settings.core_api_timeout_s,
            )
            logger.info(
                "Core partial-referral created intake_id=%s core_id=%s",
                intake_id,
                core_row.get("id"),
            )
        except CorePartialReferralError as e:
            logger.exception(
                "Core partial-referral failed intake_id=%s: %s",
                intake_id,
                e,
            )
            status = "error"
            core_row = {
                "error": str(e),
                "status_code": e.status_code,
                "request": body,
                "body": e.body,
            }
    else:
        logger.info(
            "Core partial-referral skipped (disabled or no token); using stub intake_id=%s",
            intake_id,
        )
        core_row = apply_partial_referral(body)

    ref_id = core_row.get("id") or core_row.get("referral_id")
    db.add(
        PartialReferral(
            intake_id=intake_id,
            referral_id=str(ref_id) if ref_id is not None else None,
            status=status,
            stub_response_json=json.dumps(core_row, default=str),
        )
    )


def _model_name(settings: Settings, provider: object | None = None) -> str:
    if provider is not None:
        used = getattr(provider, "last_model_used", None)
        if used:
            return str(used)
    provider_key = (settings.llm_provider or "").lower()
    if provider_key == "ollama":
        return settings.ollama_model or "unknown"
    if provider_key == "gemini":
        return settings.gemini_model or "unknown"
    if provider_key == "openrouter":
        return settings.openrouter_model or "unknown"
    if provider_key == "github":
        return settings.github_models_model or "unknown"
    return settings.llm_provider or "unknown"


def llm_extraction_label(settings: Settings) -> str:
    """Display name for console UI while extraction runs."""
    provider = (settings.llm_provider or "ollama").lower()
    if provider == "gemini":
        return f"Gemini ({settings.gemini_model or 'unset'})"
    if provider == "openrouter":
        chain = settings.openrouter_model_chain
        label = chain[0] if chain else (settings.openrouter_model or "unset")
        if len(chain) > 1:
            return f"OpenRouter ({label} + {len(chain) - 1} fallback(s))"
        return f"OpenRouter ({label})"
    if provider == "github":
        chain = settings.github_models_model_chain
        label = chain[0] if chain else (settings.github_models_model or "unset")
        if len(chain) > 1:
            return f"GitHub Models ({label} + {len(chain) - 1} fallback(s))"
        return f"GitHub Models ({label})"
    if provider == "ollama":
        return f"Ollama ({settings.ollama_model or 'unset'})"
    return _model_name(settings)


PIPELINE_QUEUED = "queued"
PIPELINE_PROCESSING = "processing"
PIPELINE_COMPLETE = "complete"


def intake_is_pending(intake: Intake) -> bool:
    """True while extraction has not finished (no extraction row yet)."""
    if not (intake.raw_body or "").strip():
        return False
    return len(intake.extractions) == 0


def display_extraction(intake: Intake) -> Extraction | None:
    """Best extraction row for console display (prefer names that match raw SMS)."""
    if not intake.extractions:
        return None
    raw = intake.raw_body or ""
    first_attempt: Extraction | None = None
    for ext in intake.extractions:
        if first_attempt is None:
            first_attempt = ext
        if ext.error or not ext.parsed_json:
            continue
        try:
            parsed = json.loads(ext.parsed_json)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and extracted_names_match_raw(raw, parsed):
            return ext
    return first_attempt


def display_routing(intake: Intake) -> RoutingDecision | None:
    """Routing decision paired with the displayed extraction attempt."""
    if not intake.routing_decisions:
        return None
    ext = display_extraction(intake)
    if ext is None:
        return intake.routing_decisions[-1]
    try:
        idx = intake.extractions.index(ext)
    except ValueError:
        return intake.routing_decisions[-1]
    if idx < len(intake.routing_decisions):
        return intake.routing_decisions[idx]
    return intake.routing_decisions[-1]


def display_partial_referral(intake: Intake) -> PartialReferral | None:
    """Core partial referral only when displayed routing is auto."""
    rd = display_routing(intake)
    if rd is None or rd.decision != "auto":
        return None
    return intake.partial_referrals[-1] if intake.partial_referrals else None


def intake_preview(raw: str, *, max_len: int = 32) -> str:
    """One-line snippet for console intake chips."""
    one_line = " ".join((raw or "").split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1] + "…"


def intake_is_finished(intake_id: int) -> bool:
    """True when an extraction row exists; used to skip duplicate queue jobs."""
    Session = sessionmaker(bind=get_engine())
    with Session() as db:
        intake = get_intake_with_relations(db, intake_id)
        return intake is not None and len(intake.extractions) > 0


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
    db: Session,
    intake: Intake,
    *,
    llm_duration_ms: float | None = None,
) -> None:
    """Persist pipeline_status=complete via explicit UPDATE (reliable across Celery fork sessions)."""
    from sqlalchemy import update

    completed_at = utc_now()
    duration = wall_duration_ms(intake.created_at, completed_at)
    db.execute(
        update(Intake)
        .where(Intake.id == intake.id)
        .values(
            pipeline_status=PIPELINE_COMPLETE,
            processing_completed_at=completed_at,
            processing_duration_ms=duration,
        )
    )
    db.flush()
    if intake in db:
        db.refresh(intake)
    if llm_duration_ms is not None:
        logger.info(
            "Intake timing intake_id=%s total=%.0fms llm=%.0fms",
            intake.id,
            duration,
            llm_duration_ms,
        )
    else:
        logger.info("Intake timing intake_id=%s total=%.0fms", intake.id, duration)


def backfill_intake_completion(db: Session, intake_id: int) -> None:
    """Fix rows that have routing but pipeline_status still queued/processing or missing timing."""
    from sqlalchemy import update

    intake = db.get(Intake, intake_id)
    if intake is None:
        return
    if intake.pipeline_status == PIPELINE_COMPLETE and intake.processing_completed_at is not None:
        return
    completed_at = intake.processing_completed_at or utc_now()
    duration = intake.processing_duration_ms
    if duration is None and intake.created_at is not None:
        duration = wall_duration_ms(intake.created_at, completed_at)
    db.execute(
        update(Intake)
        .where(Intake.id == intake_id)
        .values(
            pipeline_status=PIPELINE_COMPLETE,
            processing_completed_at=completed_at,
            processing_duration_ms=duration,
        )
    )
    db.flush()


def reconcile_pipeline_status(db: Session) -> int:
    """Fix intakes that finished extraction but pipeline_status was left queued/processing."""
    from sqlalchemy import update

    result = db.execute(
        update(Intake)
        .where(Intake.pipeline_status.in_((PIPELINE_QUEUED, PIPELINE_PROCESSING)))
        .where(Intake.id.in_(select(RoutingDecision.intake_id)))
        .values(pipeline_status=PIPELINE_COMPLETE)
    )
    db.commit()
    count = result.rowcount or 0
    pending = list(
        db.scalars(
            select(Intake.id).where(
                Intake.pipeline_status == PIPELINE_COMPLETE,
                Intake.processing_completed_at.is_(None),
                Intake.id.in_(select(RoutingDecision.intake_id)),
            )
        ).all()
    )
    for intake_id in pending:
        backfill_intake_completion(db, intake_id)
    if pending:
        db.commit()
    if count or pending:
        logger.info(
            "Reconciled pipeline_status for %s intake(s); backfilled timing for %s",
            count,
            len(pending),
        )
    return count + len(pending)


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
    _mark_intake_complete(db, intake)
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
    llm_routing_reason: str | None = None
    raw_model_json: str | None = None
    llm_duration_ms: float | None = None
    model_used = _model_name(settings)

    llm_started = time.perf_counter()
    try:
        parsed = extract_with_retries(provider, raw, system_prompt, settings)
        model_used = _model_name(settings, provider)
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
        llm_routing_reason = e.routing_reason
        logger.error(
            "Extraction failed intake_id=%s | reason=%s",
            intake.id,
            llm_routing_reason,
        )
    finally:
        llm_duration_ms = (time.perf_counter() - llm_started) * 1000.0

    db.add(
        Extraction(
            intake_id=intake.id,
            model_provider=settings.llm_provider,
            model_name=model_used,
            raw_json=raw_model_json,
            parsed_json=raw_model_json,
            error=extraction_error,
            llm_duration_ms=llm_duration_ms,
        )
    )
    db.flush()

    if extraction_error:
        route = RoutingOutcome(
            "review",
            llm_routing_reason or f"llm_error:{extraction_error[:200]}",
            None,
        )
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
        _persist_partial_referral(db, settings, intake.id, parsed, sms_text=raw)

    _mark_intake_complete(db, intake, llm_duration_ms=llm_duration_ms)


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
    if intake_is_finished(intake_id):
        logger.info("Skip enqueue intake_id=%s — already extracted", intake_id)
        return
    from sms_demo.queue import enqueue_extraction

    enqueue_extraction(intake_id)


def complete_intake(intake_id: int) -> None:
    """Finish LLM extraction + routing (serialized — one LLM call at a time)."""
    logger.info("Extraction worker start intake_id=%s", intake_id)
    settings = reload_settings()
    logger.info(
        "Extraction settings intake_id=%s llm_provider=%s model=%s",
        intake_id,
        settings.llm_provider,
        _model_name(settings),
    )
    Session = sessionmaker(bind=get_engine())

    with llm_extraction_lock():
        try:
            with Session() as db:
                intake = get_intake_with_relations(db, intake_id)
                if intake is None:
                    logger.warning(
                        "Background extraction skipped: intake_id=%s not found", intake_id
                    )
                    return
                if len(intake.extractions) > 0:
                    backfill_intake_completion(db, intake_id)
                    db.commit()
                    logger.info(
                        "Background extraction skipped: intake_id=%s already has extraction",
                        intake_id,
                    )
                    return
                intake.pipeline_status = PIPELINE_PROCESSING
                db.flush()
                logger.info("LLM slot acquired intake_id=%s", intake_id)
                _run_llm_phase(db, settings, intake, intake.raw_body)
                db.commit()
        except Exception as exc:
            logger.exception("Background extraction failed intake_id=%s", intake_id)
            with Session() as db:
                intake = get_intake_with_relations(db, intake_id)
                if intake is None or len(intake.extractions) > 0:
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
                _mark_intake_complete(db, intake)
                db.commit()
            raise

    logger.info("Background extraction finished intake_id=%s", intake_id)


def recover_queued_intakes() -> None:
    """Re-enqueue intakes left queued after API or broker restart (not already extracted)."""
    Session = sessionmaker(bind=get_engine())
    with Session() as db:
        reconcile_pipeline_status(db)
        stmt = (
            select(Intake.id)
            .where(Intake.pipeline_status == PIPELINE_QUEUED)
            .where(~Intake.id.in_(select(Extraction.intake_id)))
        )
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
        intake = get_intake_with_relations(db, intake.id)
        assert intake is not None
        intake.pipeline_status = PIPELINE_PROCESSING
        db.flush()
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


def get_intake_with_relations(db: Session, intake_id: int) -> Intake | None:
    stmt = (
        select(Intake)
        .options(
            selectinload(Intake.extractions),
            selectinload(Intake.routing_decisions),
            selectinload(Intake.partial_referrals),
        )
        .where(Intake.id == intake_id)
    )
    return db.scalars(stmt).first()


def intake_to_api_dict(intake: Intake) -> dict:
    """JSON-serializable intake snapshot for live console polling."""
    ext = display_extraction(intake)
    rd = display_routing(intake)
    pr = display_partial_referral(intake)

    if rd is not None:
        status = "complete"
        pipeline_status = PIPELINE_COMPLETE
    elif intake_is_queued(intake):
        status = "queued"
        pipeline_status = intake.pipeline_status
    elif intake_is_processing(intake):
        status = "processing"
        pipeline_status = intake.pipeline_status
    elif intake_is_pending(intake):
        status = "pending"
        pipeline_status = intake.pipeline_status
    else:
        status = "complete"
        pipeline_status = PIPELINE_COMPLETE

    parsed = None
    if ext and ext.parsed_json:
        try:
            parsed = json.loads(ext.parsed_json)
        except json.JSONDecodeError:
            parsed = ext.parsed_json

    core = None
    if pr and pr.stub_response_json:
        try:
            core = json.loads(pr.stub_response_json)
        except json.JSONDecodeError:
            core = pr.stub_response_json

    return {
        "id": intake.id,
        "created_at": str(intake.created_at),
        "source": intake.source,
        "raw_body": intake.raw_body,
        "preview": intake_preview(intake.raw_body or ""),
        "status": status,
        "pipeline_status": pipeline_status,
        "timing": intake_timing_summary(intake),
        "extraction": {
            "provider": ext.model_provider if ext else None,
            "model": ext.model_name if ext else None,
            "parsed": parsed,
            "error": ext.error if ext else None,
        }
        if ext
        else None,
        "routing": {
            "decision": rd.decision,
            "reason": rd.reason,
            "confidence": rd.confidence,
        }
        if rd
        else None,
        "partial_referral": core,
    }
