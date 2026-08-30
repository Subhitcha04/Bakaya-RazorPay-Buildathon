"""
Shadow mode: a candidate decision function (a new Strategist
implementation, a new confidence threshold, a new prompt version --
anything swappable) runs alongside the LIVE decision path on real
cases, records what it WOULD have decided, but never executes.
Compares agreement rate and surfaces every divergence for human review
before promotion.

This is how changes to money-touching logic should ship: shadow, then
canary at a small percentage, then full promotion -- never a direct
swap. See ModelVersion.status (shadow/canary/live/rolled_back) in
models/ops.py for where this fits alongside the registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol


class DecisionLike(Protocol):
    ladder_level: str
    channel: str | None
    amount_paise: int


@dataclass(frozen=True)
class ShadowComparison:
    case_id: str
    live_ladder_level: str
    shadow_ladder_level: str
    live_channel: str | None
    shadow_channel: str | None
    live_amount_paise: int
    shadow_amount_paise: int
    agrees: bool


@dataclass(frozen=True)
class ShadowRunReport:
    total: int
    agreements: int
    divergences: list[ShadowComparison]

    @property
    def agreement_rate(self) -> float:
        return self.agreements / self.total if self.total else 1.0


def run_shadow_comparison(
    cases: list[Any],
    live_decide_fn: Callable[[Any], DecisionLike],
    shadow_decide_fn: Callable[[Any], DecisionLike],
) -> ShadowRunReport:
    """
    Neither function's output is ever executed here -- this module
    only compares. live_decide_fn represents whatever is actually
    running today; shadow_decide_fn represents the candidate.
    """
    comparisons: list[ShadowComparison] = []
    agreements = 0

    for case in cases:
        live = live_decide_fn(case)
        shadow = shadow_decide_fn(case)
        agrees = (
            live.ladder_level == shadow.ladder_level
            and live.channel == shadow.channel
            and live.amount_paise == shadow.amount_paise
        )
        if agrees:
            agreements += 1
        comparisons.append(ShadowComparison(
            case_id=getattr(case, "id", str(case)),
            live_ladder_level=live.ladder_level, shadow_ladder_level=shadow.ladder_level,
            live_channel=live.channel, shadow_channel=shadow.channel,
            live_amount_paise=live.amount_paise, shadow_amount_paise=shadow.amount_paise,
            agrees=agrees,
        ))

    divergences = [c for c in comparisons if not c.agrees]
    return ShadowRunReport(total=len(cases), agreements=agreements, divergences=divergences)
