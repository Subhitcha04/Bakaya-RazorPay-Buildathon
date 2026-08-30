"""
Minimum detectable effect / required sample size for the 2-arm holdout
test. Standard two-proportion z-test math -- stdlib only. Report the
detectable-effect number honestly in EVALUATION.md rather than picking
a batch size because it sounds like a round number.
"""
from __future__ import annotations

import math

Z_ALPHA_TWO_SIDED_05 = 1.959964
Z_BETA_POWER_80 = 0.841621


def required_n_per_arm(baseline_rate: float, mde_pp: float,
                        z_alpha: float = Z_ALPHA_TWO_SIDED_05, z_beta: float = Z_BETA_POWER_80) -> int:
    p1 = baseline_rate
    p2 = baseline_rate + mde_pp / 100
    p_bar = (p1 + p2) / 2
    numerator = (
        z_alpha * math.sqrt(2 * p_bar * (1 - p_bar)) + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    denominator = (p2 - p1) ** 2
    return math.ceil(numerator / denominator)


def detectable_effect_pp(n_per_arm: int, baseline_rate: float,
                          z_alpha: float = Z_ALPHA_TWO_SIDED_05, z_beta: float = Z_BETA_POWER_80) -> float:
    lo, hi = 0.1, 50.0
    for _ in range(50):
        mid = (lo + hi) / 2
        if required_n_per_arm(baseline_rate, mid, z_alpha, z_beta) <= n_per_arm:
            hi = mid
        else:
            lo = mid
    return round(hi, 2)
