"""
Computes the authorization ceiling INDEPENDENTLY of whatever the agent
proposed, and blocks if the proposal exceeds it. This is the concrete
implementation of the security principle from AGENT-SECURITY.md: the
model's belief about how much it's allowed to offer is never trusted --
this function recomputes the real number from merchant config and
LTV band, and capability.py mints a token scoped to THIS number, never
to proposed.amount_paise directly.
"""
from __future__ import annotations

from app.models import Merchant
from .base import GateResult

NAME = "offer_ceiling"

LTV_MULTIPLIER = {"low": 0.05, "mid": 0.10, "high": 0.20, "unknown": 0.03}


def compute_ceiling(db, merchant_id: str, ltv_band: str) -> int:
    """
    Ground truth. Stand-in table for Day 3 -- replace with the real
    merchant coupon/offer table once it exists, without changing this
    function's signature (capability.py and this gate both depend on it).
    """
    merchant = db.get(Merchant, merchant_id)
    base_cap = merchant.spend_cap_paise_daily if merchant else 0
    return int(base_cap * LTV_MULTIPLIER.get(ltv_band, 0.03))


def check(db, case, proposed, context: dict) -> GateResult:
    ceiling = compute_ceiling(db, case.merchant_id, case.ltv_band)
    if proposed.amount_paise > ceiling:
        return GateResult(False, NAME, reason="proposed amount exceeds independently-derived ceiling",
                           evidence={"proposed_amount_paise": proposed.amount_paise, "ceiling_paise": ceiling})
    return GateResult(True, NAME, evidence={"ceiling_paise": ceiling})
