"""
Closes a real gap found by scripts/mutate_gates.py: the consent gate
was only exercised by smoke_test.py, which runs as a standalone script
and is NOT part of the pytest suite -- so a silent regression to
consent.py would never fail CI. This file is the actual pytest
coverage that was missing.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Merchant, Customer, Consent, RiskCase
from app.control_plane.gates import consent
from app.schemas.contracts import ProposedActionOut


def _seeded_case(with_consent_for: str | None = None):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    merchant = Merchant(name="M", spend_cap_paise_daily=1_000_000)
    db.add(merchant); db.commit()
    customer = Customer(merchant_id=merchant.id, contact_hash="h", ltv_band="mid")
    db.add(customer); db.commit()
    if with_consent_for:
        db.add(Consent(customer_id=customer.id, channel=with_consent_for,
                        state="granted", source="test"))
        db.commit()
    case = RiskCase(
        merchant_id=merchant.id, customer_id=customer.id, surface="payment_failure",
        category="billing", kind="insufficient_funds", amount_paise=49900, ltv_band="mid",
        experiment_arm="treatment", ladder_level="L3", executes=True,
    )
    db.add(case); db.commit()
    return db, case


def test_blocks_when_no_consent_row_exists_for_the_channel():
    db, case = _seeded_case(with_consent_for=None)
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=1000, proposer_model="s", trace_id="t")
    result = consent.check(db, case, proposed, context={})
    assert result.passed is False
    assert "no active consent" in result.reason


def test_allows_when_consent_is_granted_for_the_channel():
    db, case = _seeded_case(with_consent_for="email")
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=1000, proposer_model="s", trace_id="t")
    result = consent.check(db, case, proposed, context={})
    assert result.passed is True


def test_consent_granted_for_one_channel_does_not_cover_a_different_channel():
    db, case = _seeded_case(with_consent_for="email")
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L4", channel="whatsapp",
                                  amount_paise=1000, proposer_model="s", trace_id="t")
    result = consent.check(db, case, proposed, context={})
    assert result.passed is False


def test_revoked_consent_blocks_even_though_a_row_exists():
    db, case = _seeded_case(with_consent_for=None)
    from app.models import Consent as ConsentModel
    db.add(ConsentModel(customer_id=case.customer_id, channel="email",
                         state="revoked", source="test"))
    db.commit()
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=1000, proposer_model="s", trace_id="t")
    result = consent.check(db, case, proposed, context={})
    assert result.passed is False


def test_silent_action_with_no_channel_is_consent_exempt():
    db, case = _seeded_case(with_consent_for=None)
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L1", channel=None,
                                  amount_paise=0, proposer_model="s", trace_id="t")
    result = consent.check(db, case, proposed, context={})
    assert result.passed is True
