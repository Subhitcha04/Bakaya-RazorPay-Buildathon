"""
Exercises app/webhooks/router.py through an actual FastAPI app + TestClient
-- not just unit-testing verify_signature in isolation. Proves: valid
signature + new event -> 200 and one row written; same event replayed
(duplicate webhook delivery, which Razorpay does with backoff) -> 200
again but NO second row; invalid signature -> 400, rejected before
touching the DB.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")  # app/db.py reads this at import time

import hmac
import hashlib
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, InboundEvent
from app.webhooks.router import router
from app.db import get_db
import app.config as config_module

config_module.settings.razorpay_webhook_secret = "test_webhook_secret"

# StaticPool + check_same_thread=False: FastAPI's TestClient runs requests
# in a worker thread, and plain sqlite:///:memory: opens a FRESH (empty)
# database per connection -- this pins every connection to the same one,
# which is the standard fix for testing FastAPI+SQLite in-memory. Not
# relevant to the production Postgres path, which has no such issue.
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(engine)
TestSession = sessionmaker(bind=engine)

app = FastAPI()
app.include_router(router)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def sign(body: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


payload = {"id": "evt_test_001", "event": "payment.failed", "payload": {"amount": 49900}}
body = json.dumps(payload).encode()
valid_sig = sign(body, "test_webhook_secret")

# 1. Valid signature, new event -> 200, one row written
resp = client.post("/webhooks/razorpay", content=body,
                    headers={"X-Razorpay-Signature": valid_sig})
assert resp.status_code == 200, resp.text
db = TestSession()
rows = db.query(InboundEvent).all()
assert len(rows) == 1, f"expected 1 row, got {len(rows)}"
print("1. Valid signature + new event -> 200, 1 row written")

# 2. Same event replayed (Razorpay's own retry-with-backoff behaviour) -> 200, still 1 row
resp2 = client.post("/webhooks/razorpay", content=body,
                     headers={"X-Razorpay-Signature": valid_sig})
assert resp2.status_code == 200, resp2.text
rows2 = db.query(InboundEvent).all()
assert len(rows2) == 1, f"duplicate delivery must not create a second row, got {len(rows2)}"
print("2. Duplicate delivery of the SAME event -> 200 (ack'd), still 1 row (idempotent)")

# 3. Invalid signature -> 400, rejected before touching the DB
bad_sig = "deadbeef" * 8
resp3 = client.post("/webhooks/razorpay", content=body,
                     headers={"X-Razorpay-Signature": bad_sig})
assert resp3.status_code == 400, resp3.text
rows3 = db.query(InboundEvent).all()
assert len(rows3) == 1, "invalid signature must not touch the DB at all"
print("3. Invalid signature -> 400, rejected, no DB write attempted")

db.close()
print("\nALL WEBHOOK TESTS PASSED")
