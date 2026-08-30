from __future__ import annotations

from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_id


class RiskCase(Base, TimestampMixin):
    __tablename__ = "risk_case"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant.id"), index=True)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customer.id"), index=True)

    surface: Mapped[str] = mapped_column(String(32))     # payment_failure/checkout_abandonment/mandate_failure/receivable/retention_risk
    category: Mapped[str] = mapped_column(String(32))    # conversion/billing/retention
    kind: Mapped[str] = mapped_column(String(64))
    amount_paise: Mapped[int] = mapped_column(Integer)
    ltv_band: Mapped[str] = mapped_column(String(16), default="unknown")

    experiment_arm: Mapped[str] = mapped_column(String(16))       # treatment/holdout
    ladder_level: Mapped[str] = mapped_column(String(8), default="L0")
    executes: Mapped[bool] = mapped_column(Boolean, default=True)  # False for retention_risk -- detect-only, always

    trace_id: Mapped[str] = mapped_column(String(36), default=new_id, index=True)
    state: Mapped[str] = mapped_column(String(24), default="open")  # open/resolved/terminal


class FailureEvent(Base, TimestampMixin):
    __tablename__ = "failure_event"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_case.id"), index=True)
    rzp_entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_step: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    raw_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Diagnosis(Base, TimestampMixin):
    __tablename__ = "diagnosis"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_case.id"), index=True)
    root_cause: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    model_id: Mapped[str] = mapped_column(String(64))
    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    tier1_hit: Mapped[bool] = mapped_column(Boolean, default=False)  # True = Tier-1 rule table, not LLM
    rationale: Mapped[str | None] = mapped_column(String(500), nullable=True)

