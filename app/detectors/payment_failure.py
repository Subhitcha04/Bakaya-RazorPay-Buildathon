"""
Surface: payment_failure. Fires on `payment.failed` webhook events.

Routing here is NOT probabilistic -- it's a direct mapping from
Razorpay's own event taxonomy to a surface, near-100% by construction.
The genuinely hard question (WHY it failed) is the Diagnostician's job
(agents/diagnostician.py), not this detector's -- this file only
decides WHERE a case belongs, never its root cause.
"""
from __future__ import annotations

from app.schemas.contracts import RiskCaseIn
from .base import DetectionResult

SURFACE = "payment_failure"
CATEGORY = "billing"
EXECUTES = True
RATIONALE = "Collect mode: money was expected, the charge attempt failed. Fully autonomous, bounded by the control plane."


def on_event(event_type: str, payload: dict) -> DetectionResult | None:
    if event_type != "payment.failed":
        return None

    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    amount = entity.get("amount", 0)
    merchant_id = payload.get("account_id") or "unknown_merchant"
    customer_id = entity.get("customer_id") or entity.get("email") or "unknown_customer"

    risk_case = RiskCaseIn(
        merchant_id=merchant_id, customer_id=customer_id,
        surface=SURFACE, category=CATEGORY, kind="payment_failed",
        amount_paise=amount, executes=EXECUTES,
    )
    return DetectionResult(
        risk_case=risk_case, raw_event=payload,
        error_code=entity.get("error_code"), error_source=entity.get("error_source"),
        error_step=entity.get("error_step"), error_description=entity.get("error_description"),
        rzp_entity_id=entity.get("id"),
    )
