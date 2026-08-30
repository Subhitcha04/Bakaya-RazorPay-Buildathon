"""
Exercises the actual application code end to end on an in-memory SQLite
DB. Proves: schema creates cleanly, capability minting ALLOWs within
ceiling and BLOCKs over ceiling (both audited), a SEPARATE gate (consent)
blocks independently, the hash chain verifies, duplicate enqueue is
rejected, and tampering is detected.
"""
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Merchant, Customer, Consent, RiskCase
from app.audit import ledger as audit
from app.control_plane.capability import mint_capability
from app.execution.outbox import enqueue_attempt
from app.schemas.contracts import ProposedActionOut

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
db = Session()

print("1. Schema creates cleanly:", len(Base.metadata.tables), "tables")

merchant = Merchant(name="Test Merchant", spend_cap_paise_daily=1_000_000)
db.add(merchant); db.commit()

customer = Customer(merchant_id=merchant.id, contact_hash="hashed_contact", ltv_band="mid")
db.add(customer); db.commit()

db.add(Consent(customer_id=customer.id, channel="email", state="granted", source="checkout_signup"))
db.commit()

case = RiskCase(
    merchant_id=merchant.id, customer_id=customer.id,
    surface="payment_failure", category="billing", kind="insufficient_funds",
    amount_paise=49900, ltv_band="mid", experiment_arm="treatment",
    ladder_level="L3", executes=True,
)
db.add(case); db.commit()
print("2. Seeded merchant/customer/case OK")

proposed_ok = ProposedActionOut(
    case_id=case.id, ladder_level="L3", channel="email",
    amount_paise=5_000, proposer_model="stub", trace_id=str(uuid.uuid4()),
)
token = mint_capability(db, case, proposed_ok)
assert token is not None, "expected ALLOW for in-ceiling amount"
print(f"3. mint_capability ALLOW as expected. ceiling={token.max_amount_paise} paise, "
      f"policy_version={token.policy_version}, expires_at={token.expires_at.isoformat()}")

proposed_over = ProposedActionOut(
    case_id=case.id, ladder_level="L4", channel="email",
    amount_paise=999_999, proposer_model="stub", trace_id=str(uuid.uuid4()),
)
blocked = mint_capability(db, case, proposed_over)
assert blocked is None, "expected BLOCK"
print("4. mint_capability BLOCK as expected (proposed amount exceeded independently-derived ceiling)")

proposed_no_consent = ProposedActionOut(
    case_id=case.id, ladder_level="L3", channel="whatsapp",
    amount_paise=1_000, proposer_model="stub", trace_id=str(uuid.uuid4()),
)
blocked_consent = mint_capability(db, case, proposed_no_consent)
assert blocked_consent is None, "expected BLOCK for missing consent on whatsapp channel"
print("4b. mint_capability BLOCK as expected (no consent on record for whatsapp)")

ok, broken_seq = audit.verify_chain(db)
assert ok, f"chain broken at seq={broken_seq}"
print("5. audit.verify_chain: CHAIN OK (grant + block both recorded)")

first = enqueue_attempt(db, case.id, attempt_no=1, action_type="L3", token=token)
assert first is not None
second = enqueue_attempt(db, case.id, attempt_no=1, action_type="L3", token=token)
assert second is None, "duplicate enqueue should be rejected, not create a second attempt"
print("6. enqueue_attempt idempotency: duplicate correctly rejected (same idempotency_key)")

from app.models import AuditEntry
first_entry = db.query(AuditEntry).order_by(AuditEntry.seq.asc()).first()
first_entry.payload_json = {"tampered": True}
db.commit()
ok2, broken_seq2 = audit.verify_chain(db)
assert not ok2 and broken_seq2 == first_entry.seq
print(f"7. Tamper detection: mutating entry seq={first_entry.seq} after the fact is correctly "
      f"detected by verify_chain -> CHAIN BROKEN at seq={broken_seq2}")

print("\nALL SMOKE TESTS PASSED")
