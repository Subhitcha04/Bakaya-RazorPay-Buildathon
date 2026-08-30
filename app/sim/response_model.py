"""
Simulates whether a customer "recovers" (pays) after an intervention,
or would have recovered anyway with no intervention at all. Explicitly
declared as a model with named parameters -- not hidden inside a bare
random.random() call -- so EVALUATION.md can state exactly how ground
truth was constructed in a given batch run. This file is what makes the
"what is real vs simulated" table in the README literally true rather
than a formality.
"""
from __future__ import annotations

import hashlib

BASELINE_RECOVERY_RATE = {
    "insufficient_funds": 0.22,
    "expired_card": 0.05,
    "issuer_risk_decline": 0.10,
    "gateway_timeout": 0.35,
    "mandate_lapsed": 0.08,
    "customer_intent": 0.15,
    "fraud_flag": 0.02,
    "other": 0.10,
}

INTERVENTION_UPLIFT = {
    "insufficient_funds": 0.18,
    "expired_card": 0.30,
    "issuer_risk_decline": 0.05,
    "gateway_timeout": 0.10,
    "mandate_lapsed": 0.20,
    "customer_intent": -0.04,
    "fraud_flag": 0.00,
    "other": 0.05,
}


def simulate_recovery(
    case_id: str, seed: int, root_cause: str, arm: str, level_correctness: float = 1.0,
) -> bool:
    """
    Deterministic given (case_id, seed, root_cause, arm, level_correctness)
    -- identical inputs always produce the identical simulated outcome,
    required for `make demo` reproducibility.

    `level_correctness` (default 1.0, unchanged behaviour for every
    existing call site) scales the achieved uplift down when the
    ladder level chosen for this case wasn't the one the real routing
    table would pick -- e.g. a random-arm or dumb-default-arm ablation
    picking L4 for a case that actually needed silent L1 shouldn't get
    full credit for the uplift a CORRECT L1 choice would have earned.
    1.0 = fully correct action, 0.0 = achieves none of the uplift
    (equivalent to no action at all, though the intervention COST is
    still incurred -- that asymmetry is exactly what an ablation like
    scripts/ablation_arms.py exists to expose).

    Any arm other than "holdout" is treated as "some action was taken"
    and gets uplift scaled by level_correctness; "holdout" always gets
    zero uplift regardless, since no action was taken at all.
    """
    base = BASELINE_RECOVERY_RATE.get(root_cause, 0.10)
    raw_uplift = INTERVENTION_UPLIFT.get(root_cause, 0.0) if arm != "holdout" else 0.0
    uplift = raw_uplift * level_correctness
    p_recover = max(0.0, min(1.0, base + uplift))

    material = f"{seed}|{case_id}|outcome".encode()
    digest = hashlib.sha256(material).digest()
    draw = int.from_bytes(digest[:8], "big") / 2**64
    return draw < p_recover
