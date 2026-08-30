"""
Regression test for a real bug: SQLite drops timezone info on stored
datetimes, so a ProposedAction.created_at read back from the DB is
naive while context["now"] is timezone-aware -- comparing them raises
TypeError. This wasn't caught until tests/test_replay.py exercised a
case with a PRIOR ProposedAction already persisted (every earlier test
only ever proposed once per case). Pinned here explicitly so it can
never silently regress.
"""
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Merchant, Customer, Consent, RiskCase, ProposedAction
from app.control_plane.gates import frequency_cap
from app.schemas.contracts import ProposedActionOut


def _seeded_case_with_a_prior_contact():
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

    prior = ProposedAction(
        case_id=case.id, attempt_no=1, ladder_level="L3", channel="email",
        amount_paise=0, proposer_model="s", trace_id="t",
    )
    db.add(prior); db.commit()
    return db, case


def test_frequency_cap_does_not_crash_comparing_against_a_persisted_prior_contact():
    db, case = _seeded_case_with_a_prior_contact()
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t2")
    result = frequency_cap.check(db, case, proposed, context={"now": datetime.now(timezone.utc)})
    assert result is not None


def test_frequency_cap_correctly_blocks_within_the_cooldown_window():
    db, case = _seeded_case_with_a_prior_contact()
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t2")
    result = frequency_cap.check(db, case, proposed, context={"now": datetime.now(timezone.utc)})
    assert result.passed is False
    assert result.reason == "cooldown not yet elapsed since last contact"
