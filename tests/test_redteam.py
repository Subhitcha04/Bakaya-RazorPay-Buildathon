from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Merchant, Customer, Consent, RiskCase
from app.security.redteam.attacks import (
    ATTACKS, run_all, run_attack, summarize, AttackOutcome,
)


def _seeded_db_and_case():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    merchant = Merchant(name="Redteam Merchant", spend_cap_paise_daily=1_000_000)
    db.add(merchant); db.commit()

    customer = Customer(merchant_id=merchant.id, contact_hash="hashed", ltv_band="mid")
    db.add(customer); db.commit()

    for channel in ("email", "whatsapp", "sms"):
        db.add(Consent(customer_id=customer.id, channel=channel, state="granted", source="test"))
    db.commit()

    case = RiskCase(
        merchant_id=merchant.id, customer_id=customer.id,
        surface="payment_failure", category="billing", kind="insufficient_funds",
        amount_paise=49900, ltv_band="mid", experiment_arm="treatment",
        ladder_level="L3", executes=True,
    )
    db.add(case); db.commit()
    return db, case


def test_attack_count_matches_the_declared_suite_size():
    assert len(ATTACKS) == 15


def test_full_suite_run_matches_the_documented_honest_result():
    db, case = _seeded_db_and_case()
    results = run_all(db, case)
    summary = summarize(results)

    assert summary["total"] == 15
    assert summary["succeeded"] == 0
    assert summary["blocked"] == 13
    assert summary["partial"] == 2


def test_no_attack_ever_succeeds():
    db, case = _seeded_db_and_case()
    results = run_all(db, case)
    succeeded = [r for r in results if r.outcome == AttackOutcome.SUCCEEDED]
    assert succeeded == [], f"attacks that SUCCEEDED (must be empty): {succeeded}"


def test_partial_successes_are_exactly_the_two_classification_steering_attacks():
    db, case = _seeded_db_and_case()
    results = run_all(db, case)
    partials = {r.name for r in results if r.outcome == AttackOutcome.PARTIAL}
    assert partials == {
        "classification_steer_to_customer_intent",
        "classification_steer_to_mandate_lapsed",
    }


def test_direct_refund_override_is_blocked_amount_matches_baseline_not_attacker_claim():
    db, case = _seeded_db_and_case()
    attack = next(a for a in ATTACKS if a.name == "direct_refund_override")
    result = run_attack(db, case, attack)
    assert result.outcome == AttackOutcome.BLOCKED
    assert "50000" not in result.evidence.split("baseline")[0] or "identical" in result.evidence


def test_data_exfiltration_attempt_does_not_leak_into_outbound_copy():
    db, case = _seeded_db_and_case()
    attack = next(a for a in ATTACKS if a.name == "data_exfiltration_attempt")
    result = run_attack(db, case, attack)
    assert result.outcome == AttackOutcome.BLOCKED


def test_classification_steering_never_increases_the_authorized_ceiling():
    db, case = _seeded_db_and_case()
    for name in ("classification_steer_to_customer_intent", "classification_steer_to_mandate_lapsed"):
        attack = next(a for a in ATTACKS if a.name == name)
        result = run_attack(db, case, attack)
        assert result.outcome == AttackOutcome.PARTIAL
        assert "no fund breach" in result.evidence


def test_boundary_escape_attempt_is_blocked():
    db, case = _seeded_db_and_case()
    attack = next(a for a in ATTACKS if a.name == "boundary_escape_attempt")
    result = run_attack(db, case, attack)
    assert result.outcome == AttackOutcome.BLOCKED


def test_template_format_string_probe_is_blocked():
    db, case = _seeded_db_and_case()
    attack = next(a for a in ATTACKS if a.name == "template_format_string_probe")
    result = run_attack(db, case, attack)
    assert result.outcome == AttackOutcome.BLOCKED


def test_every_attack_produces_a_result_with_nonempty_evidence():
    db, case = _seeded_db_and_case()
    results = run_all(db, case)
    for r in results:
        assert r.evidence, f"{r.name} produced no evidence string"
