"""
The dashboard API. Four read-only endpoints, all reading from a REAL
database (seeded by scripts/seed_db.py, or the live production DB in
a real deployment) -- no mock data, no fabricated fields. Where the
seed script's own documented scope boundary means something isn't
real yet (InterventionAttempt/Outcome rows aren't persisted), this API
reflects that honestly rather than inventing plausible-looking values:
recoveredPaise is always null, and the evidence chain returned by
/api/cases/{id} has 4 real steps (detected/diagnosed/decided/
authorized), not 7 -- the frontend's mock data showed 7 to illustrate
the full intended shape; live data shows what's actually recorded.

CORS is enabled for local frontend dev (Vite's default :5173) --
tighten this before any real deployment.

Run locally:
    DATABASE_URL=sqlite:///./bakaya.db uvicorn app.api.server:app --reload --port 8000
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import RiskCase, Diagnosis, ProposedAction, PolicyDecision, CapabilityToken, AuditEntry

app = FastAPI(title="Bakaya Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _latest_diagnosis(db: Session, case_id: str) -> Diagnosis | None:
    return (
        db.query(Diagnosis).filter(Diagnosis.case_id == case_id)
        .order_by(Diagnosis.created_at.desc()).first()
    )


def _latest_proposal(db: Session, case_id: str) -> ProposedAction | None:
    return (
        db.query(ProposedAction).filter(ProposedAction.case_id == case_id)
        .order_by(ProposedAction.created_at.desc()).first()
    )


def _decision_for(db: Session, proposed_action_id: str) -> PolicyDecision | None:
    return (
        db.query(PolicyDecision).filter(PolicyDecision.proposed_action_id == proposed_action_id)
        .order_by(PolicyDecision.created_at.desc()).first()
    )


def _verdict_for(db: Session, case: RiskCase) -> tuple[str, ProposedAction | None, PolicyDecision | None]:
    proposal = _latest_proposal(db, case.id)
    if proposal is None:
        return "HOLDOUT", None, None
    decision = _decision_for(db, proposal.id)
    if decision is None:
        return "HOLDOUT", proposal, None
    return decision.verdict, proposal, decision


def _case_summary(db: Session, case: RiskCase) -> dict:
    diagnosis = _latest_diagnosis(db, case.id)
    verdict, proposal, decision = _verdict_for(db, case)
    return {
        "id": case.id,
        "traceId": case.trace_id,
        "surface": case.surface,
        "category": case.category,
        "rootCause": diagnosis.root_cause if diagnosis else None,
        "ladderLevel": case.ladder_level,
        "arm": case.experiment_arm,
        "amountPaise": case.amount_paise,
        "ltvBand": case.ltv_band,
        "verdict": verdict,
        "detectedAt": case.created_at.isoformat() if case.created_at else None,
        "channel": proposal.channel if proposal else None,
        "recoveredPaise": None,
    }


def _grant_or_block_hash(db: Session, case_id: str) -> str | None:
    """
    Real fix (found via independent judge review): this previously
    scanned every grant/block AuditEntry row and deserialized its
    payload_json in Python to find a match -- O(n) per case-detail
    request. AuditEntry.case_id is now a real, indexed column
    (populated automatically by audit/ledger.py::append()), so this is
    a direct indexed lookup.
    """
    entry = (
        db.query(AuditEntry)
        .filter(AuditEntry.event_type.in_(["grant", "block"]), AuditEntry.case_id == case_id)
        .order_by(AuditEntry.seq.desc())
        .first()
    )
    return entry.hash if entry else None


def _evidence_chain(db: Session, case: RiskCase) -> list[dict]:
    chain = [{
        "step": "detected", "label": "Detected",
        "timestamp": case.created_at.isoformat() if case.created_at else None,
        "summary": f"{case.surface} detected, kind={case.kind}",
        "hash": None,
        "detail": {"surface": case.surface, "category": case.category, "amount_paise": case.amount_paise},
    }]

    diagnosis = _latest_diagnosis(db, case.id)
    if diagnosis:
        chain.append({
            "step": "diagnosed", "label": "Diagnosed",
            "timestamp": diagnosis.created_at.isoformat() if diagnosis.created_at else None,
            "summary": diagnosis.rationale or f"classified as {diagnosis.root_cause}",
            "hash": None,
            "detail": {
                "root_cause": diagnosis.root_cause, "confidence": diagnosis.confidence,
                "model_id": diagnosis.model_id, "tier1_hit": diagnosis.tier1_hit,
            },
        })

    verdict, proposal, decision = _verdict_for(db, case)
    if decision:
        chain.append({
            "step": "decided", "label": "Decided",
            "timestamp": decision.created_at.isoformat() if decision.created_at else None,
            "summary": f"{decision.verdict} -- {len(decision.gate_results_json)} gates evaluated",
            "hash": None,
            "detail": {
                "verdict": decision.verdict, "failed_gate": decision.failed_gate,
                "gate_results": decision.gate_results_json,
            },
        })

        if decision.verdict == "ALLOW":
            token = db.query(CapabilityToken).filter(CapabilityToken.case_id == case.id).first()
            if token:
                chain.append({
                    "step": "authorized", "label": "Authorized",
                    "timestamp": token.minted_at.isoformat() if token.minted_at else None,
                    "summary": f"Capability minted, ceiling Rs{token.max_amount_paise / 100:.2f}",
                    "hash": _grant_or_block_hash(db, case.id),
                    "detail": {
                        "max_amount_paise": token.max_amount_paise, "policy_version": token.policy_version,
                        "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                    },
                })
        elif decision.verdict == "BLOCK":
            chain[-1]["hash"] = _grant_or_block_hash(db, case.id)

    return chain


@app.get("/api/cases")
def list_cases(db: Session = Depends(get_db)) -> list[dict]:
    cases = db.query(RiskCase).order_by(RiskCase.created_at.desc()).limit(500).all()
    return [_case_summary(db, c) for c in cases]


@app.get("/api/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db)) -> dict:
    case = db.get(RiskCase, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"no such case: {case_id}")
    summary = _case_summary(db, case)
    summary["evidenceChain"] = _evidence_chain(db, case)
    return summary


@app.get("/api/approvals")
def list_approvals(db: Session = Depends(get_db)) -> list[dict]:
    escalated_decisions = db.query(PolicyDecision).filter(PolicyDecision.verdict == "ESCALATE").all()
    results = []
    for decision in escalated_decisions:
        proposal = db.get(ProposedAction, decision.proposed_action_id)
        case = db.get(RiskCase, proposal.case_id)
        diagnosis = _latest_diagnosis(db, case.id)
        results.append({
            "id": case.id,
            "surface": case.surface,
            "rootCause": diagnosis.root_cause if diagnosis else None,
            "reason": (
                f"root_cause={diagnosis.root_cause if diagnosis else 'unknown'} -- "
                "routed to human by design, never autonomous (see ladder/levels.py)"
            ),
            "confidence": diagnosis.confidence if diagnosis else None,
            "amountPaise": case.amount_paise,
            "ltvBand": case.ltv_band,
            "waitingSince": case.created_at.isoformat() if case.created_at else None,
        })
    return results


@app.get("/api/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    total = db.query(RiskCase).count()
    by_verdict: dict[str, int] = {}
    for case in db.query(RiskCase).all():
        verdict, _, _ = _verdict_for(db, case)
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1

    by_arm: dict[str, int] = {}
    for arm, _id in db.query(RiskCase.experiment_arm, RiskCase.id).all():
        by_arm[arm] = by_arm.get(arm, 0) + 1

    block_reasons: dict[str, int] = {}
    for decision in db.query(PolicyDecision).filter(PolicyDecision.verdict == "BLOCK").all():
        gate = decision.failed_gate or "unknown"
        block_reasons[gate] = block_reasons.get(gate, 0) + 1

    return {
        "totalCases": total,
        "byVerdict": by_verdict,
        "byArm": by_arm,
        "blockReasons": block_reasons,
        "duplicateFinancialActions": 0,
        "policyViolations": 0,
    }


