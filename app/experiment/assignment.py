"""
Seeded, deterministic holdout assignment. Same seed + same case_id
always produces the same arm -- this is what makes a batch run
reproducible and is the entire basis for the incremental-lift claim in
EVALUATION.md. Never uses random.random() or any other non-reproducible
source: a re-run with the same seed over the same case_id set must
produce IDENTICAL arm assignments, byte for byte.
"""
from __future__ import annotations

import hashlib

DEFAULT_HOLDOUT_PCT = 0.25


def assign_arm(seed: int, case_id: str, holdout_pct: float = DEFAULT_HOLDOUT_PCT) -> str:
    material = f"{seed}|{case_id}".encode()
    digest = hashlib.sha256(material).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    return "holdout" if value < holdout_pct else "treatment"


ARM_LABELS_4WAY = ["holdout", "dumb_default", "exhaustive_random", "treatment"]


def assign_arm_multi(seed: int, case_id: str, arms: list[str] = ARM_LABELS_4WAY) -> str:
    """
    Deterministic equal-split assignment across N named arms, using a
    DIFFERENT hash salt ("multi", not the 2-arm function's bare
    seed|case_id) so the two assignment schemes never collide or
    correlate for the same (seed, case_id) pair -- a case's 2-arm and
    4-arm assignments are independent draws, which matters if a script
    ever needs to run both comparisons over the identical population.
    """
    material = f"{seed}|multi|{case_id}".encode()
    digest = hashlib.sha256(material).digest()
    value = int.from_bytes(digest[:8], "big") / 2**64
    idx = min(int(value * len(arms)), len(arms) - 1)
    return arms[idx]
