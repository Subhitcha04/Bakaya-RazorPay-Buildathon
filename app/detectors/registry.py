"""
The detector registry. Adding a new surface (e.g. disputes, per
ARCHITECTURE.md's stated future extension) means adding one module
here; nothing else in the codebase changes. That claim is only true if
this list is the SINGLE place surfaces are enumerated -- don't
special-case a new surface anywhere else.
"""
from __future__ import annotations

from datetime import datetime

from . import (
    payment_failure, checkout_abandonment, mandate_failure,
    receivables, churn_intent, cohort_degradation,
)
from .base import DetectionResult, ModuleDetector

DETECTOR_MODULES = [
    payment_failure, checkout_abandonment, mandate_failure,
    receivables, churn_intent, cohort_degradation,
]

DETECTORS = [ModuleDetector(m) for m in DETECTOR_MODULES]

assert len(DETECTORS) == 6, "keep ARCHITECTURE.md's surface count in sync with this list"

EVENT_DRIVEN = [d for d in DETECTORS if d.is_event_driven]
SWEEP_BASED = [d for d in DETECTORS if d.is_sweep_based]


def dispatch_event(event_type: str, payload: dict) -> list[DetectionResult]:
    results = []
    for d in EVENT_DRIVEN:
        r = d.on_event(event_type, payload)
        if r is not None:
            results.append(r)
    return results
