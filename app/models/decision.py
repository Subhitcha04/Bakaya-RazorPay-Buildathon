from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_id


class ProposedAction(Base, TimestampMixin):
    """What the Strategist emits. A CLAIM, not a credential -- see
    CapabilityToken below, which is the only thing that authorizes."""
    __tablename__ = "proposed_action"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_case.id"), index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1)
    ladder_level: Mapped[str] = mapped_column(String(8))
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    offer_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer)   # proposed -- NEVER trusted as the ceiling
    send_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    copy_text: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    proposer_model: Mapped[str] = mapped_column(String(64))
    trace_id: Mapped[str] = mapped_column(String(36), index=True)


class PolicyDecision(Base, TimestampMixin):
    __tablename__ = "policy_decision"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    proposed_action_id: Mapped[str] = mapped_column(String(36), ForeignKey("proposed_action.id"), index=True)
    verdict: Mapped[str] = mapped_column(String(16))    # ALLOW / BLOCK / ESCALATE
    failed_gate: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gate_results_json: Mapped[dict] = mapped_column(JSON, default=dict)
    policy_version: Mapped[str] = mapped_column(String(32))


class CapabilityToken(Base, TimestampMixin):
    """
    The ONLY artifact that authorizes a money action. Single-use,
    short-TTL, scoped to exactly one case + action_type, with a ceiling
    computed INDEPENDENTLY of whatever the agent proposed. The model's
    belief about its own authorization is never the credential -- this
    row is. See control_plane/capability.py.
    """
    __tablename__ = "capability_token"
    token_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("risk_case.id"), index=True)
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(32))
    max_amount_paise: Mapped[int] = mapped_column(Integer)   # independently-derived ceiling
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    minted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    policy_version: Mapped[str] = mapped_column(String(32))
    mint_reason: Mapped[str] = mapped_column(String(255), default="")
    used: Mapped[bool] = mapped_column(Boolean, default=False)
