"""
Surface: cohort_degradation. SIMPLIFIED per the plan's own cut order
(FINAL-PLAN-v2 SS11, item #1): a full EWMA/CUSUM implementation is
listed as the FIRST thing to cut if behind schedule. This is that
simplification, done deliberately and stated as such -- a straight
percentage-drop comparison against a supplied baseline, not real EWMA.
Upgrading to EWMA/CUSUM is a stated future step, not a claimed current
one; say so in HONEST_LIMITATIONS.md.

EXECUTES = False, same reasoning as churn_intent.py: this is a
COHORT-level signal (an issuer/method route degrading), not a
per-customer one -- there's no single customer to contact, so it
routes to L5 as an ops alert rather than awkwardly forcing a customer
contact where none applies. Its real downstream effect is informing
the L1 "not into a degraded route" gate condition for OTHER cases
sharing that issuer/method, not executing anything itself.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from app.schemas.contracts import RiskCaseIn
from .base import DetectionResult

SURFACE = "cohort_degradation"
CATEGORY = "billing"
EXECUTES = False
RATIONALE = ("Cohort-level signal, not per-transaction: response is suppress-and-reschedule for "
             "OTHER cases on this route, plus a merchant ops alert -- never a direct customer contact.")

DROP_THRESHOLD = 0.20
MIN_SAMPLE_SIZE = 10


def sweep(candidates: list[dict], now: datetime) -> list[DetectionResult]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for c in candidates:
        groups[(c["issuer"], c["method"])].append(c)

    results = []
    for (issuer, method), txns in groups.items():
        if len(txns) < MIN_SAMPLE_SIZE:
            continue
        trailing_rate = sum(1 for t in txns if t["success"]) / len(txns)
        baseline = txns[0]["baseline_success_rate"]
        if baseline - trailing_rate < DROP_THRESHOLD:
            continue

        risk_case = RiskCaseIn(
            merchant_id=txns[0]["merchant_id"], customer_id="cohort",
            surface=SURFACE, category=CATEGORY,
            kind=f"degradation_{issuer}_{method}",
            amount_paise=0, executes=EXECUTES,
        )
        results.append(DetectionResult(
            risk_case=risk_case,
            raw_event={"issuer": issuer, "method": method, "trailing_rate": trailing_rate,
                       "baseline": baseline, "n": len(txns)},
        ))
    return results
