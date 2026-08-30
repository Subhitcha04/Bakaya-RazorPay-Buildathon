"""
Surface: receivable. Sweep-based over invoice due dates -- B2B overdue
receivables, distinct from consumer subscription mandates. Ladder entry
differs deliberately from the consumer surfaces: B2B receivables skip
the silent-retry tier entirely and go straight to a nudge, then human
-- an unpaid invoice isn't a technical failure that silent retry can
resolve.
"""
from __future__ import annotations

from datetime import datetime

from app.schemas.contracts import RiskCaseIn
from .base import DetectionResult

SURFACE = "receivable"
CATEGORY = "billing"
EXECUTES = True
RATIONALE = "Collect mode: a B2B invoice is past its due date. Ladder entry is L3-then-L5, never silent -- there's no technical failure to retry."


def sweep(candidates: list[dict], now: datetime) -> list[DetectionResult]:
    results = []
    for inv in candidates:
        if inv.get("paid"):
            continue
        if now <= inv["due_at"]:
            continue

        risk_case = RiskCaseIn(
            merchant_id=inv["merchant_id"], customer_id=inv["customer_id"],
            surface=SURFACE, category=CATEGORY, kind="invoice_overdue",
            amount_paise=inv["amount_paise"], executes=EXECUTES,
        )
        results.append(DetectionResult(risk_case=risk_case, raw_event=inv, rzp_entity_id=inv.get("invoice_id")))
    return results
