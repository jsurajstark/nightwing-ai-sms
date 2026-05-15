from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, Response
from sqlalchemy.orm import Session

from sms_demo.config import Settings, get_settings
from sms_demo.db import get_db
from sms_demo.services.pipeline import complete_intake, create_intake, intake_is_processing
from sms_demo.services.twilio_signature import is_valid_twilio_request

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])


@router.post("/sms")
async def twilio_sms(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    Body: Annotated[str, Form()] = "",
    MessageSid: Annotated[str | None, Form()] = None,
):
    if not settings.enable_twilio_webhook:
        raise HTTPException(status_code=404, detail="Twilio webhook disabled")

    token = settings.twilio_auth_token
    base = settings.public_base_url
    if not token or not base:
        raise HTTPException(
            status_code=503,
            detail="Twilio webhook enabled but TWILIO_AUTH_TOKEN or PUBLIC_BASE_URL missing",
        )

    form = await request.form()
    post_params: dict[str, str] = {}
    for k, v in form.multi_items():
        if isinstance(v, str):
            post_params[str(k)] = v
        else:
            post_params[str(k)] = str(v)

    sig = request.headers.get("X-Twilio-Signature")
    path_q = request.url.path
    if request.url.query:
        path_q = f"{path_q}?{request.url.query}"

    if not is_valid_twilio_request(
        auth_token=token,
        public_base_url=base,
        request_path_with_query=path_q,
        post_params=post_params,
        twilio_signature=sig,
    ):
        # Do not call LLM on bad signature
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    intake = create_intake(db, settings, Body, source="twilio", external_id=MessageSid)
    if intake_is_processing(intake):
        background_tasks.add_task(complete_intake, intake.id)

    # Twilio expects TwiML or empty 200
    return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")
