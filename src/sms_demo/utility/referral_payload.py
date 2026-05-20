"""Core-aligned referral body (Nightwing API shape)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClinicalServiceItem(BaseModel):
    clinicId: int | None = None
    uber_service: str | None = None
    clinical_servicesId: list[dict[str, Any]] | None = None
    locationId: int | None = None


class ReferralPayload(BaseModel):
    """Real Core referral create fields; only first_name / last_name required for completeness."""

    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    mobile: str | None = None
    email: str | None = None
    dob: str | None = None
    gender: str | None = None
    language: list[str] | str | None = None
    injury_date: str | None = None
    injury_time: str | None = None
    synopsis: str | None = None
    clinical_services: list[ClinicalServiceItem] | list[dict[str, Any]] | None = None
    address1: str | None = None
    address2: str | None = None
    postal_code: str | None = None
    state_name: str | None = None
    city_name: str | None = None
    postal_flag: str | None = None
    clientId: int | None = None
    caseManagerId: int | None = None
    fax_number: str | None = None
    accident_type: str | None = None
    notes: str | None = None
    documents: list[Any] | None = None
    parent_relationId: int | None = None
    pharmacyId: int | None = None
    commercial_case: str | None = None
    permission_type: str | None = None
    source: str = Field(default="sms")
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
