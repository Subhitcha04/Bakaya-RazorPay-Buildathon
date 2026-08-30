"""
Post-transaction notification is mandatory after every e-mandate debit.
TODO: verify clause number against the primary circular before shipping.
"""
from __future__ import annotations

from ..base import GateResult

NAME = "rbi_post_debit_notification"


def check(db, case, proposed, context: dict) -> GateResult:
    if not context.get("is_mandate_debit", False):
        return GateResult(True, NAME, evidence={"reason": "not a mandate debit"})
    if not context.get("post_debit_notification_sent", False):
        return GateResult(False, NAME, reason="post-debit notification not sent")
    return GateResult(True, NAME)
