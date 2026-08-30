"""
Refuses to spend more deliberating on a decision than the decision is
worth. For a Rs99 subscription in a low-uplift segment, spending
Rs0.18 of Claude reasoning is a loss -- this gate turns that into a
design constraint enforced in code, not just a metric reported after
the fact. Uses the INCREMENTAL expected value (uplift-weighted), never
the gross amount at risk -- using gross here would justify
deliberating on every case, which defeats the entire point.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EconomicDecision:
    proceed: bool
    reason: str
    expected_value_paise: float
    estimated_cost_paise: float


def should_deliberate(
    amount_paise: int, uplift_estimate: float, margin_rate: float, estimated_cost_paise: float
) -> EconomicDecision:
    expected_value_paise = uplift_estimate * amount_paise * margin_rate
    if expected_value_paise < estimated_cost_paise:
        return EconomicDecision(
            proceed=False, reason="negative expected value of deliberation",
            expected_value_paise=expected_value_paise, estimated_cost_paise=estimated_cost_paise,
        )
    return EconomicDecision(
        proceed=True, reason="expected value clears the cost bar",
        expected_value_paise=expected_value_paise, estimated_cost_paise=estimated_cost_paise,
    )
