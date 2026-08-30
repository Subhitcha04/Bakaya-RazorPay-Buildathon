"""
Real tests for execute_with_capability -- found via independent judge
review to have ZERO test coverage before this file existed (grep for
the function name across tests/ returned exactly one hit, in
test_shadow.py, which only asserts it is NOT called during shadow
evaluation). The function whose own docstring says "nothing downstream
is allowed to touch money without passing through here first" was, as
a direct result, raising TypeError on every single real invocation --
see capability.py's docstring on this exact bug and its fix.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, CapabilityToken, Merchant, Customer, RiskCase
from app.control_plane.capability import execute_with_capability, CapabilityError


def _seeded_token(expires_in: timedelta = timedelta(minutes=5), used: bool = False,
                   max_amount_paise: int = 5000):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    merchant = Merchant(name="M", spend_cap_paise_daily=1_000_000)
    db.add(merchant); db.commit()
    customer = Customer(merchant_id=merchant.id, contact_hash="h", ltv_band="mid")
    db.add(customer); db.commit()
    case = RiskCase(merchant_id=merchant.id, customer_id=customer.id, surface="payment_failure",
                     category="billing", kind="insufficient_funds", amount_paise=1000,
                     ltv_band="mid", experiment_arm="treatment", ladder_level="L1", executes=True)
    db.add(case); db.commit()

    now = datetime.now(timezone.utc)
    token = CapabilityToken(
        case_id=case.id, merchant_id=merchant.id, action_type="L1",
        max_amount_paise=max_amount_paise, channel=None, minted_at=now,
        expires_at=now + expires_in, policy_version="v1", mint_reason="test", used=used,
    )
    db.add(token); db.commit()
    return db, token


def test_execute_with_capability_succeeds_and_flips_used():
    """
    THE regression pin for the TypeError bug: this exact call pattern
    (a real token round-tripped through SQLite, then compared against
    a fresh aware datetime) previously raised unconditionally.
    """
    db, token = _seeded_token()
    execute_with_capability(db, token, actual_amount_paise=1000)
    reloaded = db.get(CapabilityToken, token.token_id)
    assert reloaded.used is True


def test_execute_with_capability_raises_on_expired_token():
    db, token = _seeded_token(expires_in=timedelta(minutes=-1))
    try:
        execute_with_capability(db, token, actual_amount_paise=1000)
        assert False, "expected CapabilityError"
    except CapabilityError as e:
        assert "expired" in str(e)


def test_execute_with_capability_raises_on_already_used_token():
    db, token = _seeded_token(used=True)
    try:
        execute_with_capability(db, token, actual_amount_paise=1000)
        assert False, "expected CapabilityError"
    except CapabilityError as e:
        assert "consumed" in str(e)


def test_execute_with_capability_raises_when_amount_exceeds_ceiling():
    db, token = _seeded_token(max_amount_paise=5000)
    try:
        execute_with_capability(db, token, actual_amount_paise=999_999)
        assert False, "expected CapabilityError"
    except CapabilityError as e:
        assert "ceiling" in str(e)


def test_execute_with_capability_reads_fresh_state_not_the_stale_object():
    """
    The docstring specifically claims it re-reads from the DB rather
    than trusting the caller's in-memory object, in case it's stale.
    Confirm this: mutate the DB row directly (simulating a concurrent
    consumer), then call execute_with_capability with the STALE
    in-memory token object that still shows used=False.
    """
    db, token = _seeded_token()
    db.query(CapabilityToken).filter(CapabilityToken.token_id == token.token_id).update({"used": True})
    db.commit()

    try:
        execute_with_capability(db, token, actual_amount_paise=1000)
        assert False, "expected CapabilityError -- the fresh DB state shows used=True"
    except CapabilityError as e:
        assert "consumed" in str(e)


def test_execute_with_capability_writes_a_real_audit_entry():
    from app.models import AuditEntry
    db, token = _seeded_token()
    execute_with_capability(db, token, actual_amount_paise=1000)
    entries = db.query(AuditEntry).filter(AuditEntry.event_type == "execute").all()
    assert len(entries) == 1
    assert entries[0].payload_json["token_id"] == token.token_id
    assert entries[0].payload_json["actual_amount_paise"] == 1000
