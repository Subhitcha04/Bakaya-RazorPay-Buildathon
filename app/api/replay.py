"""
Deterministic replay: given a case_id, reconstructs the full decision
trail and re-runs the case's ORIGINAL proposed action through TODAY's
gate logic -- entirely read-only, via capability.evaluate_only() --
and diffs the result against what was actually recorded when the case
ran. This doubles as a debugger (reconstruct what happened) and a
lightweight offline-drift check (did the rules change under this
case's feet since it ran).

SCOPE, stated honestly: this replays a case's ORIGINAL inputs through
CURRENT code. It does not replay under an arbitrary NAMED historical
policy_version -- that would require every gate to be parameterized
by version, not just a single CURRENT_POLICY_VERSION constant, which
is a larger change than this file makes. Claiming full multi-version
replay would overstate what's actually implemented; this is the
honest version of "policy replay" that exists today.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import RiskCase, ProposedAction, PolicyDecision
from app.control_plane.capability import evaluate_only
from app.schemas.contracts import ProposedActionOut


class ReplayError(Exception):
    pass


@dataclass(frozen=True)
class ReplayResult:
    case_id: str
    original_verdict: str
    replayed_verdict: str
    matches: bool
    original_failed_gate: str | None
    replayed_failed_gate: str | None
    note: str


def _latest_proposal_and_decision(db: Session, case_id: str) -> tuple[ProposedAction, PolicyDecision]:
    proposed = (
        db.query(ProposedAction)
        .filter(ProposedAction.case_id == case_id)
        .order_by(ProposedAction.created_at.desc())
        .first()
    )
    if proposed is None:
        raise ReplayError(f"case {case_id!r} has no recorded ProposedAction to replay")

    decision = (
        db.query(PolicyDecision)
        .filter(PolicyDecision.proposed_action_id == proposed.id)
        .order_by(PolicyDecision.created_at.desc())
        .first()
    )
    if decision is None:
        raise ReplayError(f"case {case_id!r} has a ProposedAction but no recorded PolicyDecision")

    return proposed, decision


def replay_case(db: Session, case_id: str) -> ReplayResult:
    case = db.get(RiskCase, case_id)
    if case is None:
        raise ReplayError(f"no such case: {case_id!r}")

    original_proposed, original_decision = _latest_proposal_and_decision(db, case_id)

    proposed = ProposedActionOut(
        case_id=case.id,
        ladder_level=original_proposed.ladder_level,
        channel=original_proposed.channel,
        offer_tier=original_proposed.offer_tier,
        amount_paise=original_proposed.amount_paise,
        send_at=original_proposed.send_at,
        copy_text=original_proposed.copy_text,
        proposer_model=original_proposed.proposer_model,
        trace_id=original_proposed.trace_id,
    )

    replayed_passed, replayed_gate_results = evaluate_only(db, case, proposed)
    replayed_verdict = "ALLOW" if replayed_passed else "BLOCK"
    original_verdict = original_decision.verdict

    replayed_failed = next((r for r in replayed_gate_results if not r.passed), None)

    matches = replayed_verdict == original_verdict
    note = (
        "replayed decision matches the historical record"
        if matches else
        "REPLAYED DECISION DIFFERS from history -- investigate: gate logic changed, "
        "merchant config changed, or consent/suppression state changed since this case ran"
    )

    return ReplayResult(
        case_id=case_id,
        original_verdict=original_verdict,
        replayed_verdict=replayed_verdict,
        matches=matches,
        original_failed_gate=original_decision.failed_gate,
        replayed_failed_gate=replayed_failed.gate_name if replayed_failed else None,
        note=note,
    )
