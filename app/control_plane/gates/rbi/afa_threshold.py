"""
No AFA required for recurring debits <= Rs 15,000. The no-AFA threshold
rises to Rs 1,00,000 for insurance premiums, mutual fund subscriptions,
and credit card bill payments. Above the applicable threshold without
AFA, auto-debit is not permitted -- the case must route to an
AFA-gated flow (in practice: L5 human / re-authorization link), never
silent retry.

TODO: verify clause number and exact threshold figures against the
primary circular before shipping -- these are the numbers most likely
to have been revised since secondary reporting was written.
"""
from __future__ import annotations

from ..base import GateResult

NAME = "rbi_afa_threshold"
STANDARD_THRESHOLD_PAISE = 15_000_00
HIGH_THRESHOLD_CATEGORIES = {"insurance_premium", "mutual_fund_subscription", "credit_card_bill"}
HIGH_THRESHOLD_PAISE = 1_00_000_00


def check(db, case, proposed, context: dict) -> GateResult:
    if not context.get("is_mandate_debit", False):
        return GateResult(True, NAME, evidence={"reason": "not a mandate debit"})

    category = context.get("mandate_category", "other")
    threshold = HIGH_THRESHOLD_PAISE if category in HIGH_THRESHOLD_CATEGORIES else STANDARD_THRESHOLD_PAISE

    if proposed.amount_paise > threshold and not context.get("afa_completed", False):
        return GateResult(False, NAME, reason="amount exceeds no-AFA threshold without AFA",
                           evidence={"amount_paise": proposed.amount_paise,
                                     "threshold_paise": threshold, "category": category})
    return GateResult(True, NAME, evidence={"threshold_paise": threshold, "category": category})
