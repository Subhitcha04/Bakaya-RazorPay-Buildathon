"""
The webhook handler does exactly four things and nothing else:

    1. verify signature (constant-time)
    2. idempotent insert (race-safe -- see note below)
    3. return 200
    4. a worker picks the row up asynchronously

No LLM call. No business logic. No external API call beyond the DB write.
This is the ONE hard latency SLO in the whole system: p99 < 200ms,
because Razorpay retries with exponential backoff if you don't ACK fast
-- see RUNBOOK.md. The decision pipeline that runs afterward is allowed
to take 14 seconds; nobody is waiting on it. See PRODUCTION-ENGINEERING
addendum §1.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Header, HTTPException, Request, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.config import settings
from app.webhooks.signature import verify_signature
from app.models import InboundEvent

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/razorpay")
async def receive_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(default=""),
    db: Session = Depends(get_db),
):
    body = await request.body()

    if not verify_signature(body, x_razorpay_signature, settings.razorpay_webhook_secret):
        # The REJECT path needs its own test, not just the accept path --
        # see tests/test_webhook_signature_reject.py
        raise HTTPException(status_code=400, detail="invalid signature")

    payload = json.loads(body)
    event_id = payload.get("id") or payload.get("event_id")
    if not event_id:
        raise HTTPException(status_code=400, detail="missing event id")

    # Idempotent insert. Deliberately NOT "check-then-insert" -- that's a
    # TOCTOU race between two concurrent deliveries of the same retried
    # event. Instead: attempt the insert, and treat a UNIQUE-constraint
    # violation (event_id is the primary key) as "already have this one,
    # ack and move on" rather than an error. Race-safe under concurrency,
    # portable across Postgres and SQLite.
    try:
        db.add(InboundEvent(
            event_id=event_id,
            event_type=payload.get("event", "unknown"),
            payload_json=payload,
            processed=False,
        ))
        db.commit()
    except IntegrityError:
        db.rollback()  # duplicate delivery -- this IS the idempotency guarantee, not a failure

    return {"status": "ok"}
