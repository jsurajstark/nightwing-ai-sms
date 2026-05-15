from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from sms_demo.services.stub_core import apply_partial_referral

router = APIRouter(prefix="/stub/core/v1", tags=["stub-core"])


class PartialReferralIn(BaseModel):
    patient_first_name: str | None = None
    patient_last_name: str | None = None
    patient_phone: str | None = None
    service_requested: str | None = None
    notes: str | None = None
    source: str = Field(default="sms")
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)


@router.post("/referrals/partial")
def partial_referral(body: PartialReferralIn) -> dict[str, Any]:
    """Stub Core endpoint (same process as demo app)."""
    payload = body.model_dump()
    return apply_partial_referral(payload)
