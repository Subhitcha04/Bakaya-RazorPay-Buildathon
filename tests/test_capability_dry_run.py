from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Merchant, Customer, Consent, RiskCase, CapabilityToken, AuditEntry
from app.control_plane.capability import mint_capability, evaluate_only
from app.schemas.contracts import ProposedActionOut


def _seeded_db_and_case():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    merchant = Merchant(name="M", spend_cap_paise_daily=1_000_000)
    db.add(merchant); db.commit()
    customer = Customer(merchant_id=merchant.id, contact_hash="h", ltv_band="mid")
    db.add(customer); db.commit()
    db.add(Consent(customer_id=customer.id, channel="email", state="granted", source="test"))
    db.commit()
    case = RiskCase(
        merchant_id=merchant.id, customer_id=customer.id, surface="payment_failure",
        category="billing", kind="insufficient_funds", amount_paise=49900, ltv_band="mid",
        experiment_arm="treatment", ladder_level="L3", executes=True,
    )
    db.add(case); db.commit()
    return db, case


def test_dry_run_never_creates_a_token_row():
    db, case = _seeded_db_and_case()
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t")
    result = mint_capability(db, case, proposed, dry_run=True)
    assert result is None
    assert db.query(CapabilityToken).count() == 0


def test_dry_run_never_writes_an_audit_entry():
    db, case = _seeded_db_and_case()
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t")
    mint_capability(db, case, proposed, dry_run=True)
    assert db.query(AuditEntry).count() == 0


def test_dry_run_on_a_blocking_case_also_writes_nothing():
    db, case = _seeded_db_and_case()
    over_ceiling = ProposedActionOut(case_id=case.id, ladder_level="L4", channel="email",
                                      amount_paise=999_999, proposer_model="s", trace_id="t")
    mint_capability(db, case, over_ceiling, dry_run=True)
    assert db.query(CapabilityToken).count() == 0
    assert db.query(AuditEntry).count() == 0


def test_evaluate_only_reports_the_real_verdict_without_writing():
    db, case = _seeded_db_and_case()
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t")
    passed, gate_results = evaluate_only(db, case, proposed)
    assert passed is True
    assert len(gate_results) > 0
    assert db.query(CapabilityToken).count() == 0
    assert db.query(AuditEntry).count() == 0


def test_evaluate_only_reports_a_block_verdict_correctly():
    db, case = _seeded_db_and_case()
    over_ceiling = ProposedActionOut(case_id=case.id, ladder_level="L4", channel="email",
                                      amount_paise=999_999, proposer_model="s", trace_id="t")
    passed, gate_results = evaluate_only(db, case, over_ceiling)
    assert passed is False
    failed = [r for r in gate_results if not r.passed]
    assert len(failed) >= 1


def test_normal_mint_still_writes_as_before_dry_run_did_not_break_the_default_path():
    db, case = _seeded_db_and_case()
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t")
    token = mint_capability(db, case, proposed)
    assert token is not None
    assert db.query(CapabilityToken).count() == 1
    assert db.query(AuditEntry).count() == 1
