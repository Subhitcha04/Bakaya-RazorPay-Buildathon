"""
exhaustive_random: picks a ladder level uniformly at random among the
levels the real routing table ever proposes, ignoring diagnosis, root
cause, and judgment entirely -- but still takes SOME action on every
case, unlike holdout. This isolates whether the real policy's lift
comes from JUDGMENT or merely from ACTING MORE than holdout does. If
exhaustive_random beats holdout by nearly as much as the real policy
does, the real policy's judgment isn't earning its complexity; if it
beats holdout by much less (or loses to it, given sleeping dogs),
that's the evidence the judgment is real. See scripts/ablation_arms.py
for the batch comparison that uses this.
"""
from __future__ import annotations

import hashlib

from app.control_plane.stopping_rules import LadderLevel

CANDIDATE_LEVELS = [LadderLevel.L1, LadderLevel.L2, LadderLevel.L3, LadderLevel.L4]

WRONG_LEVEL_CORRECTNESS = 0.35


def random_ladder_level(case_id: str, seed: int) -> LadderLevel:
    """Deterministic given (case_id, seed) -- reproducible across runs."""
    digest = hashlib.sha256(f"{seed}|{case_id}|exhaustive_random".encode()).digest()
    idx = digest[0] % len(CANDIDATE_LEVELS)
    return CANDIDATE_LEVELS[idx]


def level_correctness_for(chosen: LadderLevel, correct: LadderLevel) -> float:
    """1.0 if the randomly-chosen level happens to match what the real
    routing table would have picked for this root cause; WRONG_LEVEL_CORRECTNESS
    otherwise."""
    return 1.0 if chosen == correct else WRONG_LEVEL_CORRECTNESS
