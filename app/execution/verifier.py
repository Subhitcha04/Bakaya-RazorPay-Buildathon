"""
Post-execution verification: did money actually move, within the
attribution window, and attributable to a specific attempt? This is
the Verifier half of the Critic/Verifier pair -- Critic reviews a
proposal before execution (agents/critic.py); this module checks
reality after execution, against what actually happened, not what was
intended.

Includes the subscription-reactivation correctness fix flagged in the
master plan: Razorpay does NOT retroactively charge a missed cycle when
a halted subscription reactivates -- only future cycles resume. Naively
counting "the subscription started billing again" as recovery of the
specific missed amount would inflate the headline incremental-recovery
number. This module distinguishes the two explicitly, as a first-class
outcome kind, rather than conflating them into one boolean "recovered."
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

ATTRIBUTION_WINDOW = timedelta(days=14)

OutcomeKind = Literal[
    "same_cycle_recovered", "future_cycle_resumed_only", "no_payment_seen",
]


@dataclass(frozen=True)
class PaymentEvent:
    event_id: str
    amount_paise: int
    occurred_at: datetime
    is_missed_cycle_charge: bool


@dataclass(frozen=True)
class VerificationResult:
    outcome_kind: OutcomeKind
    recovered_paise: int
    attribution_window_ok: bool
    attributed_to_attempt_id: str | None
    rationale: str


def verify(
    attempt_id: str,
    attempt_executed_at: datetime,
    original_amount_paise: int,
    payment_events: list[PaymentEvent],
    now: datetime,
    window: timedelta = ATTRIBUTION_WINDOW,
) -> VerificationResult:
    candidates = [
        e for e in payment_events
        if attempt_executed_at < e.occurred_at <= attempt_executed_at + window
    ]

    if not candidates:
        return VerificationResult(
            outcome_kind="no_payment_seen", recovered_paise=0,
            attribution_window_ok=False, attributed_to_attempt_id=None,
            rationale="no payment event found within the attribution window after this attempt",
        )

    same_cycle = [e for e in candidates if e.is_missed_cycle_charge]
    if same_cycle:
        chosen = min(same_cycle, key=lambda e: e.occurred_at)
        return VerificationResult(
            outcome_kind="same_cycle_recovered", recovered_paise=chosen.amount_paise,
            attribution_window_ok=True, attributed_to_attempt_id=attempt_id,
            rationale=f"missed-cycle charge {chosen.event_id} succeeded within the attribution window",
        )

    earliest_future = min(candidates, key=lambda e: e.occurred_at)
    return VerificationResult(
        outcome_kind="future_cycle_resumed_only", recovered_paise=0,
        attribution_window_ok=True, attributed_to_attempt_id=None,
        rationale=(
            f"subscription resumed billing (event {earliest_future.event_id}) but Razorpay does not "
            "retroactively charge the originally missed cycle -- NOT counted as recovery of the "
            f"Rs{original_amount_paise / 100:.2f} originally at risk for this case"
        ),
    )
