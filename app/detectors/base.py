"""
Shared contract for every detector. A detector is either event-driven
(fires on one webhook event, e.g. payment.failed) or sweep-based (fires
on the ABSENCE of an event within a window, e.g. checkout abandonment,
or on a cohort-level pattern across many events). Both shapes return
DetectionResult objects -- never a bare RiskCase row -- so the caller
decides persistence, keeping detectors pure and independently testable
without a live database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.schemas.contracts import RiskCaseIn


@dataclass(frozen=True)
class DetectionResult:
    risk_case: RiskCaseIn
    raw_event: dict[str, Any]
    error_code: str | None = None
    error_source: str | None = None
    error_step: str | None = None
    error_description: str | None = None
    rzp_entity_id: str | None = None


class ModuleDetector:
    """
    Adapts a plain module (SURFACE/CATEGORY/EXECUTES/RATIONALE constants
    + optional on_event()/sweep() functions) to a uniform object, the
    same pattern as ModuleGate in control_plane/gates/base.py. Records
    which capability the module actually provides, rather than
    pretending every detector supports both dispatch styles.
    """
    def __init__(self, module):
        self._module = module
        self.surface = module.SURFACE
        self.category = module.CATEGORY
        self.executes = module.EXECUTES
        self.rationale = module.RATIONALE
        self.is_event_driven = hasattr(module, "on_event")
        self.is_sweep_based = hasattr(module, "sweep")

    def on_event(self, event_type: str, payload: dict) -> DetectionResult | None:
        fn = getattr(self._module, "on_event", None)
        return fn(event_type, payload) if fn else None

    def sweep(self, candidates: list[dict], now: datetime) -> list[DetectionResult]:
        fn = getattr(self._module, "sweep", None)
        return fn(candidates, now) if fn else []
