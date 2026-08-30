"""
Surface: retention_risk. executes=False, ALWAYS. Voluntary churn
carries the highest sleeping-dog risk in the system: autonomous contact
can CAUSE the cancellation it aims to prevent. Detected, diagnosed,
priced (ARR at risk), and escalated to a human. Never auto-contacted --
there is no execution path for this surface at all, by construction
(EXECUTES is a hardcoded constant here, not computed from any input),
not by a runtime check that a future change could accidentally bypass.

NOTE on TRIGGER_EVENTS: these are APPLICATION-level signals (from a
cancellation flow, a support-ticket tag, a low-usage trigger), not
native Razorpay webhook event names -- Razorpay's own event vocabulary
doesn't include a "cancellation intent" event. Whatever emits these in
the real system needs its own integration; this detector only defines
what happens once such a signal arrives.
"""
from __future__ import annotations

from app.schemas.contracts import RiskCaseIn
from .base import DetectionResult

SURFACE = "retention_risk"
CATEGORY = "retention"
EXECUTES = False
RATIONALE = ("Voluntary churn: contact can cause the cancellation it aims to prevent. "
             "Detected and escalated to a human. Never auto-contacted.")

TRIGGER_EVENTS = {"subscription.cancellation_requested", "subscription.pause_requested"}


def on_event(event_type: str, payload: dict) -> DetectionResult | None:
    if event_type not in TRIGGER_EVENTS:
        return None

    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})
    merchant_id = payload.get("account_id") or "unknown_merchant"
    customer_id = entity.get("customer_id") or "unknown_customer"
    amount = entity.get("plan_amount", 0)

    risk_case = RiskCaseIn(
        merchant_id=merchant_id, customer_id=customer_id,
        surface=SURFACE, category=CATEGORY, kind=event_type.split(".")[-1],
        amount_paise=amount, executes=EXECUTES,
    )
    return DetectionResult(risk_case=risk_case, raw_event=payload, rzp_entity_id=entity.get("id"))
