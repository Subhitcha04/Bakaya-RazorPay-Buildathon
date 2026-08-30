"""
Pre-transaction notification must be sent >=24h before any e-mandate
debit, and must carry: merchant name, amount, date/time of debit,
mandate reference, transaction reference, reason for debit, and
grievance redressal details.

FASTag/NCMC auto-replenishment is EXEMPT from this requirement --
handled here via context["notification_exempt"], set by the caller when
case.kind matches the exemption (see rbi/fastag_exemption.py, which
proves the exemption is modelled explicitly rather than silently).

TODO: verify clause number against the primary circular before shipping.
"""
from __future__ import annotations

from datetime import timedelta

from ..base import GateResult

NAME = "rbi_pre_debit_window"
MIN_LEAD_TIME = timedelta(hours=24)
REQUIRED_FIELDS = {
    "merchant_name", "amount_paise", "debit_at", "mandate_reference",
    "transaction_reference", "reason_for_debit", "grievance_redressal",
}


def check(db, case, proposed, context: dict) -> GateResult:
    if not context.get("is_mandate_debit", False):
        return GateResult(True, NAME, evidence={"reason": "not a mandate debit"})

    if context.get("notification_exempt", False):
        return GateResult(True, NAME, evidence={"reason": "FASTag/NCMC auto-replenishment exemption"})

    notification = context.get("pre_debit_notification")
    if notification is None:
        return GateResult(False, NAME, reason="no pre-debit notification scheduled")

    missing = REQUIRED_FIELDS - set(notification.keys())
    if missing:
        return GateResult(False, NAME, reason="pre-debit notification missing required fields",
                           evidence={"missing_fields": sorted(missing)})

    notified_at = context.get("notification_sent_at")
    debit_at = context.get("debit_at")
    if notified_at is None or debit_at is None or (debit_at - notified_at) < MIN_LEAD_TIME:
        return GateResult(False, NAME, reason="notification sent less than 24h before debit",
                           evidence={"notified_at": str(notified_at), "debit_at": str(debit_at)})

    return GateResult(True, NAME, evidence={
        "lead_time_hours": (debit_at - notified_at).total_seconds() / 3600,
    })
