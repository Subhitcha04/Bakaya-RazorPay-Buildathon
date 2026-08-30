from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_id


class InterventionAttempt(Base, TimestampMixin):
    """
    idempotency_key is UNIQUE -- this is what makes exactly-once
    financial actions possible. A duplicate enqueue (e.g. a retried
    webhook re-triggering the same decision) fails the UNIQUE
    constraint and is treated as a no-op, not an error.
    """
    __tablename__ = "intervention_attempt"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_case.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    token_id: Mapped[str] = mapped_column(String(36), ForeignKey("capability_token.token_id"))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(32))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rzp_response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/executed/failed

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_intervention_idempotency_key"),
    )


class Outcome(Base, TimestampMixin):
    __tablename__ = "outcome"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_case.id"), index=True)
    recovered_paise: Mapped[int] = mapped_column(Integer, default=0)
    recovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attribution_window_ok: Mapped[bool] = mapped_column(Boolean, default=False)
    attributed_to_attempt_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("intervention_attempt.id"), nullable=True
    )
