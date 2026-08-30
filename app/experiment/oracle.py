"""
Oracle ceiling: the theoretical best-possible incremental lift an
omniscient policy could achieve, computed directly from the
simulator's own ground-truth parameters (sim/response_model.py). This
is only computable because we wrote the simulator and therefore know
the TRUE per-cause baseline recovery rate and intervention uplift -- a
real deployment could never compute this. It belongs strictly in the
synthetic-data evaluation, never presented as a claim about production
performance. See EVALUATION.md's "what is real vs simulated" table.

The oracle acts only where uplift > 0 and skips everywhere uplift <= 0
(sleeping dogs, sure things) -- it is the optimal SELECTION policy,
not a better intervention. That isolates a specific question: how much
of the ceiling is "should we act on this case at all" versus "what
should the action be." Reporting "our policy captured X% of the
achievable lift" is a harder number to argue with than the raw pp
figure on its own, because it's normalized against the best any policy
could do on this exact population.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.sim.response_model import INTERVENTION_UPLIFT


@dataclass(frozen=True)
class OracleReport:
    oracle_incremental_pp: float
    oracle_would_act_on_pct: float
    per_cause_uplift: dict[str, float]


def compute_oracle_ceiling(root_causes: list[str]) -> OracleReport:
    """
    root_causes: the actual root-cause list from a real batch (e.g. the
    reality generator's output), so the ceiling reflects the real case
    mix rather than a uniform assumption across causes.
    """
    if not root_causes:
        return OracleReport(0.0, 0.0, {})

    uplifts = [INTERVENTION_UPLIFT.get(rc, 0.0) for rc in root_causes]
    positive_uplifts = [u for u in uplifts if u > 0]

    oracle_incremental_pp = (sum(positive_uplifts) / len(root_causes)) * 100
    act_pct = (len(positive_uplifts) / len(root_causes)) * 100

    per_cause = {rc: INTERVENTION_UPLIFT.get(rc, 0.0) for rc in set(root_causes)}

    return OracleReport(
        oracle_incremental_pp=oracle_incremental_pp,
        oracle_would_act_on_pct=act_pct,
        per_cause_uplift=per_cause,
    )


def captured_fraction(actual_incremental_pp: float, oracle_incremental_pp: float) -> float:
    """
    What fraction of the achievable lift did the actual policy
    capture? Clamped to [0, 1] -- a policy could in principle do worse
    than zero (net-negative from sleeping dogs) or, due to sampling
    noise on a small batch, appear to exceed the oracle; both are
    reported as 0.0 / 1.0 rather than a confusing out-of-range number.
    """
    if oracle_incremental_pp <= 0:
        return 0.0
    return max(0.0, min(1.0, actual_incremental_pp / oracle_incremental_pp))
