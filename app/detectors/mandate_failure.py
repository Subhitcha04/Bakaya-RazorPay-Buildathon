"""
Surface: mandate_failure. Fires on subscription.pending / subscription.halted.

Razorpay's own subscription lifecycle already gives detection for
free: a failed auto-charge moves a subscription to 'pending', Razorpay
retries automatically, and once retries are exhausted it moves to
'halted'. This detector watches for those two states -- it does not
reinvent the retry logic Razorpay already runs, and it should be built
against Razorpay's real event vocabulary, verified from their
subscriptions webhook docs, not invented.
"""
from __future__ import annotations

from app.schemas.contracts import RiskCaseIn
from .base import DetectionResult

SURFACE = "mandate_failure"
CATEGORY = "billing"
EXECUTES = True
RATIONALE = "Collect mode: a recurring charge failed or a mandate is halted. Fully autonomous, bounded by the 9 RBI gates."

TRIGGER_EVENTS = {"subscription.pending", "subscription.halted"}


def on_event(event_type: str, payload: dict) -> DetectionResult | None:
    if event_type not in TRIGGER_EVENTS:
        return None

    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    merchant_id = payload.get("account_id") or "unknown_merchant"
    customer_id = entity.get("customer_id") or "unknown_customer"
    amount = entity.get("current_invoice_amount") or entity.get("plan_amount") or 0

    risk_case = RiskCaseIn(
        merchant_id=merchant_id, customer_id=customer_id,
        surface=SURFACE, category=CATEGORY,
        kind=event_type.split(".")[-1],
        amount_paise=amount, executes=EXECUTES,
    )
    return DetectionResult(risk_case=risk_case, raw_event=payload, rzp_entity_id=entity.get("id"))
