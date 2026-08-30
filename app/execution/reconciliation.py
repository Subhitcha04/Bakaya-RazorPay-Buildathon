"""
Nightly job: for every case with a recorded internal outcome, fetch the
TRUE state from Razorpay and compare against Bakaya's internal state.
Catches "the agent believes it recovered money it didn't" -- the
failure mode that would most damage the headline incremental-recovery
number, and the reason this exists even though it feels redundant with
the Verifier (execution/verifier.py). The Verifier decides attribution
at outcome-recording time, from webhook events; reconciliation is an
independent, later, adversarial check against the source of truth
itself, catching cases where the internal record and reality quietly
drifted apart (a missed webhook, a race, a bug).

fetch_true_state_fn is injectable (same pattern as the rest of this
repo) so the comparison LOGIC is testable without live credentials;
wiring RazorpayClient.fetch_payment as the real fetch function happens
in the deployed repo's scheduled job, not here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class ReconciliationRow:
    case_id: str
    internal_recovered_paise: int
    true_recovered_paise: int
    matches: bool
    note: str


@dataclass(frozen=True)
class ReconciliationReport:
    total_checked: int
    matched: int
    mismatched_rows: list[ReconciliationRow]

    @property
    def accuracy(self) -> float:
        return self.matched / self.total_checked if self.total_checked else 1.0


def reconcile(
    internal_outcomes: list[dict],
    fetch_true_state_fn: Callable[[str], dict],
) -> ReconciliationReport:
    rows: list[ReconciliationRow] = []
    matched = 0

    for outcome in internal_outcomes:
        true_state = fetch_true_state_fn(outcome["attempt_id"])
        true_recovered = true_state["amount_paise"] if true_state.get("status") == "captured" else 0
        internal_recovered = outcome["recovered_paise"]
        is_match = true_recovered == internal_recovered

        if is_match:
            matched += 1
        rows.append(ReconciliationRow(
            case_id=outcome["case_id"], internal_recovered_paise=internal_recovered,
            true_recovered_paise=true_recovered, matches=is_match,
            note="OK" if is_match else "MISMATCH -- internal state does not match Razorpay's true state",
        ))

    mismatched = [r for r in rows if not r.matches]
    return ReconciliationReport(total_checked=len(rows), matched=matched, mismatched_rows=mismatched)
