"""
Postgres transactional outbox. `claim_pending_batch` uses
FOR UPDATE SKIP LOCKED so multiple worker processes can pull from the
same queue without blocking each other or double-claiming a row. See
ARCHITECTURE.md ADR: "the money action and the state transition must
commit atomically; with an external broker (Celery/Redis) they can't."

NOTE ON PORTABILITY: FOR UPDATE SKIP LOCKED is Postgres-specific and has
no SQLite equivalent, so `claim_pending_batch` is written for
Postgres/Neon and is not exercised by the SQLite smoke test below. The
idempotency guarantee this whole design depends on --
`intervention_attempt.idempotency_key` UNIQUE -- IS dialect-agnostic and
IS tested directly (see the chaos test at the bottom of this file's
companion test, and the smoke test in the accompanying script).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InterventionAttempt, CapabilityToken
from app.control_plane.capability import execute_with_capability, CapabilityError
from app.audit import ledger as audit


def make_idempotency_key(case_id: str, attempt_no: int, action_type: str) -> str:
    material = f"{case_id}|{attempt_no}|{action_type}"
    return hashlib.sha256(material.encode()).hexdigest()


def claim_pending_batch(db: Session, limit: int = 20) -> list[InterventionAttempt]:
    """
    Postgres-only. Multiple workers can call this concurrently; SKIP
    LOCKED means a row already claimed by another worker is silently
    passed over rather than causing this worker to block on it.
    """
    rows = db.execute(text("""
        SELECT id FROM intervention_attempt
        WHERE status = 'pending'
        ORDER BY created_at
        FOR UPDATE SKIP LOCKED
        LIMIT :limit
    """), {"limit": limit}).fetchall()
    ids = [r[0] for r in rows]
    if not ids:
        return []
    return db.query(InterventionAttempt).filter(InterventionAttempt.id.in_(ids)).all()


def enqueue_attempt(
    db: Session, case_id: str, attempt_no: int, action_type: str, token: CapabilityToken
) -> InterventionAttempt | None:
    """
    Idempotent enqueue. The UNIQUE constraint on idempotency_key means a
    duplicate enqueue -- e.g. from a retried webhook re-triggering the
    same decision -- fails silently as a no-op rather than creating a
    second attempt at the same action. Returns None on duplicate; this
    is the correct, expected outcome, not an error condition.
    """
    key = make_idempotency_key(case_id, attempt_no, action_type)
    attempt = InterventionAttempt(
        case_id=case_id,
        attempt_no=attempt_no,
        token_id=token.token_id,
        idempotency_key=key,
        action_type=action_type,
        status="pending",
    )
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None   # already enqueued -- this IS the idempotency guarantee working
    db.refresh(attempt)
    return attempt


def process_attempt(db: Session, attempt: InterventionAttempt, razorpay_client, actual_amount_paise: int) -> None:
    """
    The core exactly-once step.

    If the worker crashes between the Razorpay call and marking the row
    executed, the row is still 'pending' on restart. That's SAFE: the
    capability token was already consumed (execute_with_capability sets
    `used=True` and commits BEFORE the Razorpay call), so if this
    function is re-entered for the same attempt, execute_with_capability
    will raise CapabilityError("capability already consumed") on the
    retry rather than allowing a second real financial action. This is
    the chaos-test invariant: kill the worker mid-execution, restart,
    assert exactly one financial action occurred.
    """
    token = db.get(CapabilityToken, attempt.token_id)
    try:
        execute_with_capability(db, token, actual_amount_paise)
    except CapabilityError as e:
        attempt.status = "failed"
        db.commit()
        audit.append(db, event_type="refuse", payload={
            "attempt_id": attempt.id,
            "case_id": attempt.case_id,
            "reason": str(e),
        })
        return

    response = razorpay_client.execute(
        attempt.action_type, actual_amount_paise, attempt.idempotency_key
    )

    attempt.status = "executed"
    attempt.executed_at = datetime.now(timezone.utc)
    attempt.rzp_response_json = response
    db.commit()
