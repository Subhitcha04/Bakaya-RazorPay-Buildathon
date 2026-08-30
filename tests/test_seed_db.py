"""
Tests for scripts/seed_db.py against a REAL temp SQLite file -- not
in-memory, since the whole point of this script is producing a
persistent, file-backed database. Checks structure and reproducibility,
not exact ALLOW/BLOCK/ESCALATE counts, which are legitimate to shift if
simulator internals or gate logic ever change.

Every test explicitly closes its session and disposes its engine
before deleting the temp file -- required on Windows, which (unlike
POSIX/Linux) refuses to unlink a file that still has an open handle.
This was a real bug: the suite passed cleanly on Linux and failed
100% of the time on Windows for exactly this reason, because neither
seed() (fixed in scripts/seed_db.py) nor this file's own read-side
sessions ever explicitly released their SQLite connections.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from scripts.seed_db import seed
from app.models import (
    RiskCase, Diagnosis, ProposedAction, PolicyDecision, CapabilityToken,
    AuditEntry, Customer, Consent, Suppression,
)


def _seed_to_temp_db(n: int = 100, seed_value: int = 1) -> Path:
    tmp = Path(tempfile.mktemp(suffix=".db"))
    seed(n, seed_value, db_path=tmp)
    return tmp


def _db_for(path: Path):
    engine = create_engine(f"sqlite:///{path}", poolclass=NullPool)
    return sessionmaker(bind=engine)()


def _cleanup(path: Path, *sessions) -> None:
    for db in sessions:
        db.close()
    path.unlink()


def test_seed_produces_exactly_n_risk_cases():
    path = _seed_to_temp_db(n=100, seed_value=1)
    db = _db_for(path)
    assert db.query(RiskCase).count() == 100
    _cleanup(path, db)


def test_seed_is_fully_reproducible_for_the_same_seed():
    path1 = _seed_to_temp_db(n=50, seed_value=42)
    path2 = _seed_to_temp_db(n=50, seed_value=42)
    db1, db2 = _db_for(path1), _db_for(path2)

    levels1 = sorted(c.ladder_level for c in db1.query(RiskCase).all())
    levels2 = sorted(c.ladder_level for c in db2.query(RiskCase).all())
    assert levels1 == levels2

    verdicts1 = sorted(d.verdict for d in db1.query(PolicyDecision).all())
    verdicts2 = sorted(d.verdict for d in db2.query(PolicyDecision).all())
    assert verdicts1 == verdicts2

    arms1 = sorted(c.experiment_arm for c in db1.query(RiskCase).all())
    arms2 = sorted(c.experiment_arm for c in db2.query(RiskCase).all())
    assert arms1 == arms2

    _cleanup(path1, db1)
    _cleanup(path2, db2)


def test_holdout_cases_get_no_proposal_and_no_policy_decision():
    path = _seed_to_temp_db(n=200, seed_value=1)
    db = _db_for(path)
    holdout_cases = db.query(RiskCase).filter(RiskCase.experiment_arm == "holdout").all()
    assert len(holdout_cases) > 0, "expected at least one holdout case at n=200"
    for case in holdout_cases:
        if case.ladder_level != "L5":
            proposals = db.query(ProposedAction).filter(ProposedAction.case_id == case.id).count()
            assert proposals == 0, f"holdout case {case.id} at {case.ladder_level} got a proposal -- should have none"
    _cleanup(path, db)


def test_every_risk_case_has_exactly_one_diagnosis():
    path = _seed_to_temp_db(n=100, seed_value=1)
    db = _db_for(path)
    case_count = db.query(RiskCase).count()
    diagnosis_count = db.query(Diagnosis).count()
    assert diagnosis_count == case_count
    _cleanup(path, db)


def test_every_diagnosis_root_cause_is_valid():
    from app.agents.taxonomy import ROOT_CAUSES
    path = _seed_to_temp_db(n=100, seed_value=1)
    db = _db_for(path)
    for d in db.query(Diagnosis).all():
        assert d.root_cause in ROOT_CAUSES
    _cleanup(path, db)


def test_escalated_cases_have_no_channel_and_no_capability_token():
    path = _seed_to_temp_db(n=200, seed_value=1)
    db = _db_for(path)
    escalated = db.query(PolicyDecision).filter(PolicyDecision.verdict == "ESCALATE").all()
    assert len(escalated) > 0, "expected at least one ESCALATE case at n=200"
    for decision in escalated:
        proposed = db.get(ProposedAction, decision.proposed_action_id)
        assert proposed.channel is None
    _cleanup(path, db)


def test_allow_verdicts_have_a_minted_capability_token():
    path = _seed_to_temp_db(n=200, seed_value=1)
    db = _db_for(path)
    allowed = db.query(PolicyDecision).filter(PolicyDecision.verdict == "ALLOW").all()
    assert len(allowed) > 0
    for decision in allowed:
        proposed = db.get(ProposedAction, decision.proposed_action_id)
        token = db.query(CapabilityToken).filter(CapabilityToken.case_id == proposed.case_id).first()
        assert token is not None
    _cleanup(path, db)


def test_block_verdicts_never_have_a_capability_token():
    path = _seed_to_temp_db(n=200, seed_value=1)
    db = _db_for(path)
    blocked = db.query(PolicyDecision).filter(PolicyDecision.verdict == "BLOCK").all()
    assert len(blocked) > 0, "expected at least one real BLOCK at n=200 given realistic consent/suppression rates"
    for decision in blocked:
        proposed = db.get(ProposedAction, decision.proposed_action_id)
        token = db.query(CapabilityToken).filter(CapabilityToken.case_id == proposed.case_id).first()
        assert token is None
        assert decision.failed_gate is not None
    _cleanup(path, db)


def test_some_blocks_are_driven_by_real_consent_or_suppression_state():
    path = _seed_to_temp_db(n=300, seed_value=1)
    db = _db_for(path)
    blocked = db.query(PolicyDecision).filter(PolicyDecision.verdict == "BLOCK").all()
    failed_gates = {d.failed_gate for d in blocked}
    assert "consent" in failed_gates or "suppression" in failed_gates
    _cleanup(path, db)


def test_gate_results_are_persisted_on_every_non_escalated_decision():
    path = _seed_to_temp_db(n=100, seed_value=1)
    db = _db_for(path)
    non_escalated = db.query(PolicyDecision).filter(PolicyDecision.verdict != "ESCALATE").all()
    for decision in non_escalated:
        assert len(decision.gate_results_json) > 0
    _cleanup(path, db)


def test_audit_entries_exist_for_every_grant_and_block():
    path = _seed_to_temp_db(n=100, seed_value=1)
    db = _db_for(path)
    n_allow = db.query(PolicyDecision).filter(PolicyDecision.verdict == "ALLOW").count()
    n_block = db.query(PolicyDecision).filter(PolicyDecision.verdict == "BLOCK").count()
    n_grants = db.query(AuditEntry).filter(AuditEntry.event_type == "grant").count()
    n_blocks_audited = db.query(AuditEntry).filter(AuditEntry.event_type == "block").count()
    assert n_grants == n_allow
    assert n_blocks_audited == n_block
    _cleanup(path, db)


def test_suppressed_customers_never_get_an_allow():
    path = _seed_to_temp_db(n=300, seed_value=1)
    db = _db_for(path)
    suppressed_customer_ids = {s.customer_id for s in db.query(Suppression).all()}
    for case in db.query(RiskCase).filter(RiskCase.customer_id.in_(suppressed_customer_ids)).all():
        decisions = (
            db.query(PolicyDecision)
            .join(ProposedAction, PolicyDecision.proposed_action_id == ProposedAction.id)
            .filter(ProposedAction.case_id == case.id)
            .all()
        )
        for d in decisions:
            assert d.verdict != "ALLOW"
    _cleanup(path, db)
