from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from sms_demo.config import Settings, get_settings
from sms_demo.db import get_db
from sms_demo.models import Intake
from sms_demo.services.pipeline import (
    complete_intake,
    create_intake,
    intake_is_processing,
    list_intakes_for_console,
)
from sms_demo.templating import templates

router = APIRouter(prefix="/demo", tags=["demo"])

_SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"
_SAMPLE_NAMES = frozenset({"clean", "messy", "ambiguous", "spanish", "international"})


def _read_sample(name: str) -> str | None:
    path = _SAMPLES_DIR / f"{name}.txt"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


@router.get("/console", response_class=HTMLResponse)
def console(
    request: Request,
    sample: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    hint = ""
    prefill = ""
    if sample in _SAMPLE_NAMES:
        content = _read_sample(sample)
        if content is not None:
            prefill = content
            hint = f"Loaded sample: {sample}"
        else:
            hint = f"Sample file missing for {sample}"

    intakes = list_intakes_for_console(db)
    has_processing = any(intake_is_processing(i) for i in intakes)
    return templates.TemplateResponse(
        request,
        "console.html",
        {
            "intakes": intakes,
            "prefill": prefill,
            "hint": hint,
            "twilio_enabled": settings.enable_twilio_webhook,
            "has_processing": has_processing,
        },
    )


@router.post("/simulate")
def simulate(
    background_tasks: BackgroundTasks,
    sms_body: str = Form(""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    intake = create_intake(db, settings, sms_body, source="console")
    if intake_is_processing(intake):
        background_tasks.add_task(complete_intake, intake.id)
        return RedirectResponse(url=f"/demo/console?submitted={intake.id}", status_code=303)
    return RedirectResponse(url="/demo/console", status_code=303)


@router.post("/intakes/{intake_id}/delete")
def delete_intake(intake_id: int, db: Session = Depends(get_db)):
    intake = db.get(Intake, intake_id)
    if intake is None:
        raise HTTPException(status_code=404, detail="Intake not found")
    db.delete(intake)
    db.commit()
    return RedirectResponse(url="/demo/console", status_code=303)


@router.post("/reset")
def reset(db: Session = Depends(get_db)):
    from sqlalchemy import delete

    db.execute(delete(Intake))
    db.commit()
    return RedirectResponse(url="/demo/console", status_code=303)
