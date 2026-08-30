from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base
from app.cost.ledger import record_llm_cost, record_channel_cost, total_cost_for_case, pct_cases_with_zero_llm_cost


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_tier1_lookup_costs_zero():
    db = _make_db()
    entry = record_llm_cost(db, case_id="c1", model_id="rule_table_v1")
    assert entry.paise == 0


def test_expensive_model_costs_more_than_cheap_model():
    db = _make_db()
    cheap = record_llm_cost(db, case_id="c1", model_id="diagnostician_stub_v1")
    expensive = record_llm_cost(db, case_id="c2", model_id="claude-sonnet-4-6")
    assert expensive.paise > cheap.paise


def test_total_cost_sums_multiple_entries_for_one_case():
    db = _make_db()
    record_llm_cost(db, case_id="c1", model_id="diagnostician_stub_v1")
    record_channel_cost(db, case_id="c1", channel="whatsapp")
    total = total_cost_for_case(db, "c1")
    assert total == 2 + 35


def test_pct_cases_with_zero_llm_cost_mixed_population():
    db = _make_db()
    record_llm_cost(db, case_id="c1", model_id="rule_table_v1")
    record_llm_cost(db, case_id="c2", model_id="claude-sonnet-4-6")
    record_llm_cost(db, case_id="c3", model_id="rule_table_v1")
    pct = pct_cases_with_zero_llm_cost(db, ["c1", "c2", "c3"])
    assert abs(pct - (2 / 3)) < 1e-9


def test_pct_cases_with_zero_llm_cost_empty_list():
    db = _make_db()
    assert pct_cases_with_zero_llm_cost(db, []) == 0.0


def test_case_with_no_llm_calls_at_all_counts_as_zero_llm():
    db = _make_db()
    pct = pct_cases_with_zero_llm_cost(db, ["never_diagnosed_case"])
    assert pct == 1.0
