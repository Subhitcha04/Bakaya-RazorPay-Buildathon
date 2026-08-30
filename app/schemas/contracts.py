"""
Typed contracts for everything that flows between the decision plane and
the control plane. All frozen (immutable) -- once an agent emits one of
these, it doesn't get mutated on the way to the control plane. The
control plane reads a ProposedAction and independently re-derives what's
allowed; it never trusts fields like `justification` for authorization.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, ConfigDict

RootCause = Literal[
    "insufficient_funds", "expired_card", "issuer_risk_decline",
    "gateway_timeout", "mandate_lapsed", "fraud_flag",
    "customer_intent", "other",
]

Surface = Literal[
    "payment_failure", "checkout_abandonment", "mandate_failure",
    "receivable", "retention_risk", "cohort_degradation",
]

Category = Literal["conversion", "billing", "retention"]
Verdict = Literal["ALLOW", "BLOCK", "ESCALATE"]
LadderLevel = Literal["L0", "L1", "L2", "L3", "L4", "L5", "L6"]


class RiskCaseIn(BaseModel):
    """What a Detector emits."""
    model_config = ConfigDict(frozen=True)

    merchant_id: str
    customer_id: str
    surface: Surface
    category: Category
    kind: str
    amount_paise: int = Field(ge=0)
    ltv_band: Literal["low", "mid", "high", "unknown"] = "unknown"
    executes: bool = True   # False for retention_risk -- detect-and-escalate ONLY, never


class DiagnosisOut(BaseModel):
    """
    What the Diagnostician emits. Determines WHICH intervention is tried
    -- never WHETHER one is authorized. A wrong diagnosis costs recovery
    efficacy, not safety, because the control plane doesn't condition
    authorization on the diagnosis being correct.
    """
    model_config = ConfigDict(frozen=True)

    case_id: str
    root_cause: RootCause
    confidence: float = Field(ge=0.0, le=1.0)
    model_id: str
    prompt_hash: str = ""
    tier1_hit: bool = False   # True = Tier-1 deterministic lookup, no LLM call made
    rationale: str | None = None


class ProposedActionOut(BaseModel):
    """
    What the Strategist proposes. This is a CLAIM about what should
    happen -- it is never treated as a credential. The control plane
    independently re-derives the ceiling and every gate result; it does
    not read `justification` when deciding ALLOW/BLOCK.
    """
    model_config = ConfigDict(frozen=True)

    case_id: str
    attempt_no: int = 1
    ladder_level: LadderLevel
    channel: str | None = None
    offer_tier: str | None = None
    amount_paise: int = Field(ge=0)   # proposed -- NEVER used directly as the authorization ceiling
    send_at: datetime | None = None
    copy_text: str | None = None
    proposer_model: str
    trace_id: str
    justification: str | None = None   # logged for observability only; never read by the executor


class PolicyDecisionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    proposed_action_id: str
    verdict: Verdict
    failed_gate: str | None = None
    gate_results: dict[str, bool] = Field(default_factory=dict)
    policy_version: str


class CapabilityOut(BaseModel):
    """
    The only artifact that authorizes execution. Minted by the control
    plane's mint_capability(), never constructed by an agent. See
    control_plane/capability.py.
    """
    model_config = ConfigDict(frozen=True)

    token_id: str
    case_id: str
    merchant_id: str
    action_type: str
    max_amount_paise: int
    channel: str | None
    minted_at: datetime
    expires_at: datetime
    policy_version: str
    mint_reason: str

