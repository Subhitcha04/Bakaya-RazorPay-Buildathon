"""
Cost ledger. Every cost-incurring action -- an LLM call, a channel send,
infra -- gets recorded here against the case it served. This is what
makes "cost per rupee recovered" measurable rather than asserted, and
what makes "% of cases resolved with zero LLM calls" a real, computed
number instead of a claim in a README.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import CostEntry

# Illustrative unit costs -- NOT measured. Replace with real provider
# pricing once wired to a live API, same "illustrative, not measured"
# labelling as distillation-demo/evaluate.py::cost_table().
LLM_COST_PAISE = {
    "rule_table_v1": 0,            # Tier 1, deterministic, zero cost by construction
    "diagnostician_stub_v1": 2,    # illustrative "cheap model" cost per call
    "claude-sonnet-4-6": 18,       # illustrative "expensive model" cost per call
}
CHANNEL_COST_PAISE = {
    "email": 0,        # effectively free at this volume
    "sms": 20,
    "whatsapp": 35,
    "voice": 150,
}


def record_llm_cost(db: Session, case_id: str, model_id: str, tokens_in: int = 0, tokens_out: int = 0) -> CostEntry:
    paise = LLM_COST_PAISE.get(model_id, 0)
    entry = CostEntry(case_id=case_id, kind="llm", paise=paise,
                       tokens_in=tokens_in, tokens_out=tokens_out, model=model_id)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def record_channel_cost(db: Session, case_id: str, channel: str) -> CostEntry:
    paise = CHANNEL_COST_PAISE.get(channel, 0)
    entry = CostEntry(case_id=case_id, kind="channel", paise=paise, model=None)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def total_cost_for_case(db: Session, case_id: str) -> int:
    entries = db.query(CostEntry).filter(CostEntry.case_id == case_id).all()
    return sum(e.paise for e in entries)


def pct_cases_with_zero_llm_cost(db: Session, case_ids: list[str]) -> float:
    """
    The single cheapest proof that the cascade design works: what
    fraction of cases never triggered a paid LLM call at all -- Tier 1
    resolved them, or L1 silent retry never needed diagnosis at all.
    """
    if not case_ids:
        return 0.0
    zero_llm = 0
    for cid in case_ids:
        llm_entries = db.query(CostEntry).filter(CostEntry.case_id == cid, CostEntry.kind == "llm").all()
        if all(e.paise == 0 for e in llm_entries):
            zero_llm += 1
    return zero_llm / len(case_ids)
