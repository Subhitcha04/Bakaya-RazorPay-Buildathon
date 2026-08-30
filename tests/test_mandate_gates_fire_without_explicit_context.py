"""
Regression test for a real, severe bug found via independent judge
review (not internal testing): the 4 RBI mandate gates
(afa_threshold, pre_debit_window, post_debit_notification,
variable_mandate_cap) all no-op with passed=True and evidence
{"reason": "not a mandate debit"} when context["is_mandate_debit"] is
absent. Every test file explicitly set this key, so the suite stayed
green -- but scripts/seed_db.py and run_batch.py both call
mint_capability()/evaluate_only() with NO context at all, meaning
every genuinely mandate_lapsed case in the seeded dashboard and every
batch run was silently exempted from every mandate-specific compliance
check, while the audit ledger recorded a passing gate -- an
affirmatively false compliance record for a case whose diagnosed root
cause was literally mandate_lapsed.

Fixed in capability.py::_default_context_for(), which derives
is_mandate_debit from the case's own real fields (surface/kind) as a
setdefault at the single chokepoint every caller goes through, rather
than requiring every caller to remember to pass it.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Merchant, Customer, RiskCase
from app.control_plane.capability import evaluate_only, mint_capability
from app.schemas.contracts import ProposedActionOut


def _seeded_mandate_case(amount_paise: int = 19_000_00):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    merchant = Merchant(name="M", spend_cap_paise_daily=10_000_000)
    db.add(merchant); db.commit()
    customer = Customer(merchant_id=merchant.id, contact_hash="h", ltv_band="mid")
    db.add(customer); db.commit()

    case = RiskCase(
        merchant_id=merchant.id, customer_id=customer.id, surface="mandate_failure",
        category="billing", kind="mandate_lapsed", amount_paise=amount_paise, ltv_band="mid",
        experiment_arm="treatment", ladder_level="L3", executes=True,
    )
    db.add(case); db.commit()
    return db, case


def test_mandate_case_with_no_context_is_correctly_treated_as_a_mandate_debit():
    """
    THE regression pin. This is the EXACT production call pattern
    scripts/seed_db.py and run_batch.py use -- no context argument at
    all. Before the fix, this silently passed every mandate gate with
    "not a mandate debit" evidence. It must now correctly evaluate the
    real mandate requirements and block for lack of a scheduled
    pre-debit notification.
    """
    db, case = _seeded_mandate_case(amount_paise=19_000_00)
    proposed = ProposedActionOut(
        case_id=case.id, ladder_level="L3", channel="email",
        amount_paise=19_000_00, proposer_model="s", trace_id="t",
    )

    passed, gate_results = evaluate_only(db, case, proposed)   # no context -- the bug's exact trigger
    by_name = {r.gate_name: r for r in gate_results}

    assert passed is False, "a Rs 19,000 mandate debit with no notification setup must be blocked"
    assert by_name["rbi_pre_debit_window"].passed is False
    assert by_name["rbi_pre_debit_window"].reason != None
    assert "not a mandate debit" not in str(by_name["rbi_pre_debit_window"].evidence)
    assert by_name["rbi_post_debit_notification"].passed is False
    assert by_name["rbi_afa_threshold"].passed is False   # 19,000 > 15,000 standard threshold, no AFA


def test_mandate_case_never_silently_passes_with_not_a_mandate_debit_evidence():
    """
    Belt-and-suspenders: whatever the verdict, a real mandate_lapsed
    case must never again show "not a mandate debit" as the evidence
    for a mandate-specific gate -- that string is only correct for
    genuinely non-mandate cases.
    """
    db, case = _seeded_mandate_case()
    proposed = ProposedActionOut(
        case_id=case.id, ladder_level="L3", channel="email",
        amount_paise=case.amount_paise, proposer_model="s", trace_id="t",
    )
    _, gate_results = evaluate_only(db, case, proposed)
    for r in gate_results:
        if r.gate_name in ("rbi_pre_debit_window", "rbi_post_debit_notification",
                           "rbi_afa_threshold", "rbi_variable_mandate_cap"):
            assert r.evidence.get("reason") != "not a mandate debit", (
                f"{r.gate_name} incorrectly treated a real mandate_lapsed case as non-mandate"
            )


def test_non_mandate_case_still_gets_the_original_ceremony_free_behavior():
    """
    Confirms the fix didn't overcorrect: a genuinely non-mandate case
    (e.g. insufficient_funds) must still cleanly no-op on all 4 mandate
    gates with no context required, preserving the original design
    intent stated in mint_capability's docstring.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    merchant = Merchant(name="M", spend_cap_paise_daily=10_000_000)
    db.add(merchant); db.commit()
    customer = Customer(merchant_id=merchant.id, contact_hash="h", ltv_band="mid")
    db.add(customer); db.commit()
    case = RiskCase(
        merchant_id=merchant.id, customer_id=customer.id, surface="payment_failure",
        category="billing", kind="insufficient_funds", amount_paise=50000, ltv_band="mid",
        experiment_arm="treatment", ladder_level="L1", executes=True,
    )
    db.add(case); db.commit()

    proposed = ProposedActionOut(case_id=case.id, ladder_level="L1", channel=None,
                                  amount_paise=50000, proposer_model="s", trace_id="t")
    passed, gate_results = evaluate_only(db, case, proposed)
    by_name = {r.gate_name: r for r in gate_results}
    for gate_name in ("rbi_pre_debit_window", "rbi_post_debit_notification", "rbi_afa_threshold"):
        assert by_name[gate_name].passed is True
        assert by_name[gate_name].evidence.get("reason") == "not a mandate debit"


def test_explicit_caller_context_still_overrides_the_derived_default():
    """
    Confirms setdefault semantics: a caller explicitly passing
    is_mandate_debit (every existing gate-specific test does this) must
    still take priority over the derived default -- this fix must never
    override an explicit, intentional test scenario.
    """
    db, case = _seeded_mandate_case()
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=case.amount_paise, proposer_model="s", trace_id="t")

    # Explicitly override to False, even though this IS a real mandate case by surface/kind.
    _, gate_results = evaluate_only(db, case, proposed, context={"is_mandate_debit": False})
    by_name = {r.gate_name: r for r in gate_results}
    assert by_name["rbi_pre_debit_window"].evidence.get("reason") == "not a mandate debit"


def test_mint_capability_also_receives_the_fix_not_just_evaluate_only():
    db, case = _seeded_mandate_case(amount_paise=19_000_00)
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=19_000_00, proposer_model="s", trace_id="t")
    token = mint_capability(db, case, proposed)   # no context -- same production call pattern
    assert token is None, "a Rs 19,000 mandate debit with no notification setup must not mint a token"
