"""
The Strategist is the only genuinely hard judgement call in the
decision plane -- routing, thresholds, and ceilings are all
deterministic elsewhere. Given a case already routed to a ladder entry
level, it decides channel, offer tier, and timing. It does NOT decide
whether the action is authorized -- that's the control plane's job,
independently, downstream. See AGENT-SECURITY.md: this function's
output is a CLAIM, never a credential, and its `justification` field
is logged for observability only, never read by the executor.

This stub is deliberately table-driven and fully deterministic (no
simulated LLM uncertainty needed here, unlike the Diagnostician's
TEACHER_STUB) -- swapping in a real Claude call replaces these lookup
tables with genuine reasoning over the same inputs, without changing
the function signature or what downstream code expects back.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.control_plane.stopping_rules import LadderLevel
from app.schemas.contracts import ProposedActionOut

MODEL_ID = "strategist_stub_v1"

# Silent levels (L0-L2) never get a channel -- no customer contact.
# L5 is human-routed; the agent proposes nothing for the agent to send.
CHANNEL_BY_LEVEL: dict[LadderLevel, str | None] = {
    LadderLevel.L0: None,
    LadderLevel.L1: None,
    LadderLevel.L2: None,
    LadderLevel.L3: "email",
    LadderLevel.L4: "whatsapp",
    LadderLevel.L5: None,
    LadderLevel.L6: None,
}

# Offer tier only applies at L4 (assisted) -- L3 is a plain nudge, no
# discount. Table-driven for now; the offer_ceiling gate independently
# re-derives the real cap regardless of what's proposed here.
OFFER_TIER_BY_LTV: dict[str, str | None] = {
    "low": None, "mid": "standard_grace", "high": "priority_grace", "unknown": None,
}
OFFER_AMOUNT_PAISE_BY_LTV: dict[str, int] = {
    "low": 0, "mid": 5_000, "high": 10_000, "unknown": 0,
}


@dataclass(frozen=True)
class StrategistInput:
    case_id: str
    trace_id: str
    amount_paise: int
    ladder_level: LadderLevel
    root_cause: str
    diagnosis_confidence: float
    ltv_band: str
    prior_failures: int
    now: datetime


def propose(inp: StrategistInput) -> ProposedActionOut:
    channel = CHANNEL_BY_LEVEL.get(inp.ladder_level)
    is_assisted = inp.ladder_level == LadderLevel.L4

    offer_tier = OFFER_TIER_BY_LTV.get(inp.ltv_band) if is_assisted else None
    offer_amount = OFFER_AMOUNT_PAISE_BY_LTV.get(inp.ltv_band, 0) if is_assisted else 0

    send_at = _timing_for(inp)

    return ProposedActionOut(
        case_id=inp.case_id,
        ladder_level=inp.ladder_level.value,
        channel=channel,
        offer_tier=offer_tier,
        amount_paise=offer_amount,   # proposed only -- the control plane independently caps this
        send_at=send_at,
        copy_text=None,              # Composer fills this in separately
        proposer_model=MODEL_ID,
        trace_id=inp.trace_id,
        justification=(
            f"root_cause={inp.root_cause}, confidence={inp.diagnosis_confidence:.2f}, "
            f"ltv_band={inp.ltv_band}, prior_failures={inp.prior_failures}"
        ),
    )


def _timing_for(inp: StrategistInput) -> datetime:
    """
    India-aware timing heuristic for silent retries: if it's late in
    the month, push toward the salary-cycle window (the 1st-7th) rather
    than retrying blind. This is a deliberately SIMPLE version of
    "modelled retry timing, not fixed schedule" -- full issuer-batch-
    window modelling is a stated future step, not claimed here. For
    customer-facing levels, timing is "now" -- the calling_window gate
    downstream is what actually enforces appropriate hours.
    """
    if inp.ladder_level != LadderLevel.L1:
        return inp.now

    if inp.now.day >= 25:
        next_month = inp.now.replace(day=1) + timedelta(days=32)
        return next_month.replace(day=2, hour=10, minute=0, second=0, microsecond=0)
    return inp.now + timedelta(hours=6 * (inp.prior_failures + 1))


# ---------------------------------------------------------------------
# REAL IMPLEMENTATION shape -- not called in this environment. Same
# pattern as agents/diagnostician.py::call_claude_diagnostician: the
# interface (StrategistInput in, ProposedActionOut out) is what stays
# fixed; only the body changes when this is wired to a live model.
# ---------------------------------------------------------------------
def call_claude_strategist(inp: StrategistInput) -> ProposedActionOut:
    """
    import anthropic
    client = anthropic.Anthropic()
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=(
            "You are a revenue-recovery strategist. Given a diagnosed "
            "case, propose a channel, offer tier, and timing for the "
            "given ladder level. You do not decide whether this is "
            "authorized -- only what to propose."
        ),
        messages=[{"role": "user", "content": (
            f"ladder_level: {inp.ladder_level.value}\n"
            f"root_cause: {inp.root_cause}\n"
            f"confidence: {inp.diagnosis_confidence}\n"
            f"ltv_band: {inp.ltv_band}\n"
            f"prior_failures: {inp.prior_failures}"
        )}],
    )
    # parse resp.content[0].text -> ProposedActionOut(..., proposer_model="claude-sonnet-4-6")
    """
    raise NotImplementedError("Wire in the real Anthropic client in the deployed repo.")
