"""
Synthetic case population. Every distribution here is either (a) a
structural mapping traceable to Razorpay's own documented surfaces, or
(b) a cited, UNVALIDATED vendor prior used purely to shape the
simulator -- see calibration_sources.md. Never present numbers derived
from this generator as real-world benchmarks in the README; they are
priors for calibration, not measurements.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

ROOT_CAUSE_WEIGHTS = {
    "insufficient_funds": 0.30,
    "expired_card": 0.20,
    "issuer_risk_decline": 0.15,
    "gateway_timeout": 0.10,
    "mandate_lapsed": 0.08,
    "customer_intent": 0.12,
    "fraud_flag": 0.03,
    "other": 0.02,
}

SURFACE_BY_CAUSE = {
    "insufficient_funds": "payment_failure",
    "expired_card": "payment_failure",
    "issuer_risk_decline": "payment_failure",
    "gateway_timeout": "payment_failure",
    "mandate_lapsed": "mandate_failure",
    "customer_intent": "checkout_abandonment",
    "fraud_flag": "payment_failure",
    "other": "payment_failure",
}

TICKET_SIZES_PAISE = [9900, 49900, 99900, 499900, 4999900]
LTV_BANDS = ["low", "mid", "high"]


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    merchant_id: str
    customer_id: str
    surface: str
    root_cause: str
    amount_paise: int
    ltv_band: str
    prior_failures: int


def generate_population(n: int, seed: int, merchant_id: str = "merchant_demo") -> list[SyntheticCase]:
    rng = random.Random(seed)
    causes = list(ROOT_CAUSE_WEIGHTS.keys())
    weights = list(ROOT_CAUSE_WEIGHTS.values())

    population = []
    for i in range(n):
        root_cause = rng.choices(causes, weights=weights)[0]
        population.append(SyntheticCase(
            case_id=_deterministic_id(seed, i, salt="case"),
            merchant_id=merchant_id,
            customer_id=_deterministic_id(seed, i, salt="cust"),
            surface=SURFACE_BY_CAUSE[root_cause],
            root_cause=root_cause,
            amount_paise=rng.choice(TICKET_SIZES_PAISE),
            ltv_band=rng.choices(LTV_BANDS, weights=[0.5, 0.35, 0.15])[0],
            prior_failures=rng.choices([0, 1, 2, 3], weights=[0.5, 0.3, 0.15, 0.05])[0],
        ))
    return population


def _deterministic_id(seed: int, i: int, salt: str) -> str:
    material = f"{seed}|{salt}|{i}".encode()
    return hashlib.sha256(material).hexdigest()[:20]
