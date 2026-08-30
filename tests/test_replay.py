from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base, Merchant, Customer, Consent, Suppression, RiskCase, CapabilityToken,
)
from app.control_plane.capability import mint_capability
from app.api.replay import replay_case, ReplayError
from app.schemas.contracts import ProposedActionOut


def _seeded_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    merchant = Merchant(name="M", spend_cap_paise_daily=1_000_000)
    db.add(merchant); db.commit()
    customer = Customer(merchant_id=merchant.id, contact_hash="h", ltv_band="mid")
    db.add(customer); db.commit()
    db.add(Consent(customer_id=customer.id, channel="email", state="granted", source="test"))
    db.commit()
    return db, merchant, customer


def _case(db, merchant, customer):
    case = RiskCase(
        merchant_id=merchant.id, customer_id=customer.id, surface="payment_failure",
        category="billing", kind="insufficient_funds", amount_paise=49900, ltv_band="mid",
        experiment_arm="treatment", ladder_level="L3", executes=True,
    )
    db.add(case); db.commit()
    return case


def _run_and_record(db, case, proposed) -> None:
    from app.models import ProposedAction, PolicyDecision

    token = mint_capability(db, case, proposed)
    verdict = "ALLOW" if token is not None else "BLOCK"

    pa = ProposedAction(
        case_id=case.id, ladder_level=proposed.ladder_level, channel=proposed.channel,
        offer_tier=proposed.offer_tier, amount_paise=proposed.amount_paise,
        send_at=proposed.send_at, copy_text=proposed.copy_text,
        proposer_model=proposed.proposer_model, trace_id=proposed.trace_id,
    )
    db.add(pa); db.commit()

    pd = PolicyDecision(proposed_action_id=pa.id, verdict=verdict, policy_version="v1")
    db.add(pd); db.commit()


def test_replay_matches_history_for_an_unchanged_case():
    db, merchant, customer = _seeded_db()
    case = _case(db, merchant, customer)
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t")
    _run_and_record(db, case, proposed)

    result = replay_case(db, case.id)
    assert result.matches is True
    assert result.original_verdict == result.replayed_verdict == "ALLOW"


def test_replay_is_read_only_no_new_token_or_second_decision_created():
    db, merchant, customer = _seeded_db()
    case = _case(db, merchant, customer)
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t")
    _run_and_record(db, case, proposed)

    tokens_before = db.query(CapabilityToken).count()
    replay_case(db, case.id)
    tokens_after = db.query(CapabilityToken).count()
    assert tokens_before == tokens_after


def test_replay_detects_divergence_when_underlying_state_changed():
    db, merchant, customer = _seeded_db()
    case = _case(db, merchant, customer)
    proposed = ProposedActionOut(case_id=case.id, ladder_level="L3", channel="email",
                                  amount_paise=5000, proposer_model="s", trace_id="t")
    _run_and_record(db, case, proposed)

    db.add(Suppression(customer_id=customer.id, reason="opted out later"))
    db.commit()

    result = replay_case(db, case.id)
    assert result.matches is False
    assert result.original_verdict == "ALLOW"
    assert result.replayed_verdict == "BLOCK"
    assert "DIFFERS" in result.note


def test_replay_raises_for_unknown_case():
    db, merchant, customer = _seeded_db()
    try:
        replay_case(db, "nonexistent_case_id")
        assert False, "expected ReplayError"
    except ReplayError:
        pass


def test_replay_raises_when_case_has_no_recorded_decision():
    db, merchant, customer = _seeded_db()
    case = _case(db, merchant, customer)
    try:
        replay_case(db, case.id)
        assert False, "expected ReplayError"
    except ReplayError:
        pass
