"""
Surface: checkout_abandonment. Sweep-based, not event-driven -- an
abandoned checkout is defined by the ABSENCE of an event (no
payment.captured) within a window, which a single webhook can never
tell you. `sweep()` takes explicit candidate orders rather than
querying a DB directly, keeping this a pure, independently-testable
function; a Day 9 orchestrator is responsible for fetching real
candidates and calling this.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.schemas.contracts import RiskCaseIn
from .base import DetectionResult

SURFACE = "checkout_abandonment"
CATEGORY = "conversion"
EXECUTES = True
RATIONALE = "Conversion risk: order created, no capture within the window. Passive-first (L2) -- never a nudge on first abandonment."

ABANDONMENT_WINDOW = timedelta(minutes=30)


def sweep(candidates: list[dict], now: datetime) -> list[DetectionResult]:
    results = []
    for order in candidates:
        if order.get("captured"):
            continue
        if now - order["created_at"] < ABANDONMENT_WINDOW:
            continue

        risk_case = RiskCaseIn(
            merchant_id=order["merchant_id"], customer_id=order["customer_id"],
            surface=SURFACE, category=CATEGORY, kind="checkout_abandoned",
            amount_paise=order["amount_paise"], executes=EXECUTES,
        )
        results.append(DetectionResult(risk_case=risk_case, raw_event=order, rzp_entity_id=order.get("order_id")))
    return results
