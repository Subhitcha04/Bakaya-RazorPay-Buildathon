"""
Population Stability Index (PSI) drift detector -- SIMPLIFIED, real
math, ~30 lines. <0.10 no significant shift, 0.10-0.25 moderate shift,
>0.25 significant shift -- standard industry PSI convention.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

PSI_NO_SHIFT = 0.10
PSI_MODERATE_SHIFT = 0.25


@dataclass(frozen=True)
class DriftReport:
    psi: float
    verdict: str
    per_category: dict[str, tuple[float, float]]


def _distribution(items: list[str]) -> dict[str, float]:
    counts = Counter(items)
    total = len(items)
    return {k: v / total for k, v in counts.items()} if total else {}


def compute_psi(baseline: list[str], current: list[str], epsilon: float = 1e-4) -> DriftReport:
    if not baseline or not current:
        return DriftReport(psi=0.0, verdict="insufficient_data", per_category={})

    baseline_dist = _distribution(baseline)
    current_dist = _distribution(current)
    categories = set(baseline_dist) | set(current_dist)

    psi = 0.0
    per_category: dict[str, tuple[float, float]] = {}
    for cat in categories:
        b = baseline_dist.get(cat, 0.0) + epsilon
        c = current_dist.get(cat, 0.0) + epsilon
        psi += (c - b) * math.log(c / b)
        per_category[cat] = (baseline_dist.get(cat, 0.0), current_dist.get(cat, 0.0))

    if psi < PSI_NO_SHIFT:
        verdict = "stable"
    elif psi < PSI_MODERATE_SHIFT:
        verdict = "moderate_shift"
    else:
        verdict = "significant_shift"

    return DriftReport(psi=round(psi, 4), verdict=verdict, per_category=per_category)
