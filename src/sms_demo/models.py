from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Intake(Base):
    __tablename__ = "intakes"
    __table_args__ = (Index("ix_intakes_created_at", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    raw_body: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32))  # console | twilio
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    extractions: Mapped[list[Extraction]] = relationship(
        back_populates="intake",
        cascade="all, delete-orphan",
    )
    routing_decisions: Mapped[list[RoutingDecision]] = relationship(
        back_populates="intake",
        cascade="all, delete-orphan",
    )
    partial_referrals: Mapped[list[PartialReferral]] = relationship(
        back_populates="intake",
        cascade="all, delete-orphan",
    )


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(ForeignKey("intakes.id", ondelete="CASCADE"))
    model_provider: Mapped[str] = mapped_column(String(64))
    model_name: Mapped[str] = mapped_column(String(128))
    raw_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    intake: Mapped[Intake] = relationship(back_populates="extractions")


class RoutingDecision(Base):
    __tablename__ = "routing_decisions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(ForeignKey("intakes.id", ondelete="CASCADE"))
    decision: Mapped[str] = mapped_column(String(32))  # auto | review | spam
    reason: Mapped[str] = mapped_column(String(512), default="")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    intake: Mapped[Intake] = relationship(back_populates="routing_decisions")


class PartialReferral(Base):
    __tablename__ = "partial_referrals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    intake_id: Mapped[int] = mapped_column(ForeignKey("intakes.id", ondelete="CASCADE"))
    referral_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(64))
    stub_response_json: Mapped[str] = mapped_column(Text)

    intake: Mapped[Intake] = relationship(back_populates="partial_referrals")
