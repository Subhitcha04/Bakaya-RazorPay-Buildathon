"""
Per-case contact frequency: no more than N contacts on this case, with a
minimum cooldown between them. Distinct from ContactBudgetLedger, which
is cross-surface, per-customer, per-day (see stopping_rules.py) -- this
gate is scoped to one case's own ladder attempts.
"""
from __future__ import annotations

from datetime import timedelta, timezone

from app.models import ProposedAction
from .base import GateResult

NAME = "frequency_cap"
MAX_CONTACTS_PER_CASE = 3
MIN_COOLDOWN = timedelta(hours=20)


def _as_aware_utc(dt):
    """
    SQLite drops timezone info on stored datetimes -- a value written
    as timezone-aware UTC comes back naive on read. We always mean UTC
    everywhere in this codebase, so a naive value read from the DB is
    normalized to aware-UTC before comparison rather than silently
    crashing (or, worse, silently comparing wrong values without
    crashing on a DB that preserves tzinfo, e.g. Postgres). This
    function is the single place that assumption lives.
    """
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def check(db, case, proposed, context: dict) -> GateResult:
    if proposed.channel is None:
        return GateResult(True, NAME, evidence={"reason": "no channel -- not a contact"})

    # Excludes any persisted row sharing this proposal's OWN trace_id.
    # Without this, a proposal whose ProposedAction row already exists
    # (e.g. during replay, or if the orchestrator persists the proposal
    # before calling mint_capability) would count itself as a prior
    # contact against its own cooldown -- "how many DIFFERENT earlier
    # attempts happened," not "does this row exist yet."
    prior = (
        db.query(ProposedAction)
        .filter(ProposedAction.case_id == case.id, ProposedAction.channel.isnot(None),
                 ProposedAction.trace_id != proposed.trace_id)
        .order_by(ProposedAction.created_at.desc())
        .all()
    )
    if len(prior) >= MAX_CONTACTS_PER_CASE:
        return GateResult(False, NAME, reason="max contacts for this case reached",
                           evidence={"contacts_so_far": len(prior), "cap": MAX_CONTACTS_PER_CASE})

    if prior:
        last = prior[0]
        now = context.get("now")
        last_created = _as_aware_utc(last.created_at)
        if now and last_created and (now - last_created) < MIN_COOLDOWN:
            return GateResult(False, NAME, reason="cooldown not yet elapsed since last contact",
                               evidence={"last_contact_at": last_created.isoformat()})
    return GateResult(True, NAME, evidence={"contacts_so_far": len(prior)})
