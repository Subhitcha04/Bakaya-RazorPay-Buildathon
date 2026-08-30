"""
Generic cost-cascade wrapper: try a cheap classifier first, escalate to
an expensive one ONLY when the cheap model's own confidence is below
threshold. This is the single biggest cost lever in the whole system --
see the production-engineering addendum SS2.2 -- implemented once here,
rather than duplicated inside every agent that needs it.

THRESHOLD NOW SET FROM REAL CALIBRATION DATA, NOT A GUESS. Originally
0.75, chosen as a "starting point." scripts/calibration_report.py, run
against the real Diagnostician on the real 50-case golden set, found
the 0.6-0.8 confidence band is only 18.2% ACTUALLY accurate -- meaning
the cascade would have treated a cheap-tier diagnosis as trustworthy
at confidence levels that were wrong over 80% of the time. Only the
0.8-1.0 band is calibrated (100% actual accuracy); raised to 0.85 to
sit inside it. Re-run calibration_report.py and revisit this constant
if the Diagnostician changes -- it is only as good as the data behind it.
"""
from __future__ import annotations

from typing import Callable, TypeVar

T = TypeVar("T")

CONFIDENCE_ESCALATION_THRESHOLD = 0.85


def escalate_if_low_confidence(
    cheap_result: T,
    get_confidence: Callable[[T], float],
    expensive_fn: Callable[[], T],
    threshold: float = CONFIDENCE_ESCALATION_THRESHOLD,
) -> tuple[T, bool]:
    """
    Returns (result, escalated). expensive_fn is a zero-argument
    callable specifically so it is never evaluated -- and never costs
    anything -- when the cheap result already clears the threshold.
    """
    if get_confidence(cheap_result) >= threshold:
        return cheap_result, False
    return expensive_fn(), True
