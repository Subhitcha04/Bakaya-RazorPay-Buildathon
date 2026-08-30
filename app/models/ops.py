from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_id


class CostEntry(Base, TimestampMixin):
    __tablename__ = "cost_entry"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_case.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))   # llm/channel/infra
    paise: Mapped[int] = mapped_column(Integer)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiment"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(64))
    seed: Mapped[int] = mapped_column(Integer)
    holdout_pct: Mapped[float] = mapped_column(Float)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContactBudgetLedger(Base, TimestampMixin):
    """Shared cross-surface contact budget -- stops four independent
    detection surfaces from contacting the same customer four times in
    one day. See MASTER-PLAN §5 'link cases across surfaces'."""
    __tablename__ = "contact_budget_ledger"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(String(36), ForeignKey("customer.id"), index=True)
    date: Mapped[str] = mapped_column(String(10))  # YYYY-MM-DD
    contacts_used: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("customer_id", "date", name="uq_contact_budget_customer_date"),
    )


class ModelVersion(Base, TimestampMixin):
    __tablename__ = "model_version"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    component: Mapped[str] = mapped_column(String(32))  # strategist/diagnostician/...
    model_id: Mapped[str] = mapped_column(String(64))
    prompt_hash: Mapped[str] = mapped_column(String(64), default="")
    eval_scores_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="shadow")  # shadow/canary/live/rolled_back
    rollback_target: Mapped[str | None] = mapped_column(String(36), nullable=True)


class InboundEvent(Base, TimestampMixin):
    """
    Raw Razorpay webhook deliveries. event_id is the PRIMARY KEY -- that's
    the idempotency guard. Duplicate/out-of-order retries are expected
    (Razorpay retries failed deliveries with backoff), not exceptional.
    """
    __tablename__ = "inbound_event"
    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSON)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
