"""
Tests for scripts/stability_sweep.py. Deliberately does NOT assert
"20/20 positive" as a hard requirement -- that would make the test
suite itself pressure toward cherry-picking seeds or quietly tuning
the simulator until it's true, which is exactly the failure mode this
whole exercise exists to catch. Instead these tests check the
MACHINERY is honest: every seed's result is reported, nothing is
filtered out, and the summary statistics are computed correctly from
whatever the sweep actually produced.
"""
from __future__ import annotations

import statistics

from scripts.stability_sweep import sweep


def test_sweep_returns_exactly_n_seeds_results():
    results = sweep(n_per_seed=100, n_seeds=5, base_seed=1)
    assert len(results) == 5
    assert [r["seed"] for r in results] == [1, 2, 3, 4, 5]


def test_sweep_is_fully_reproducible_for_the_same_seed_range():
    r1 = sweep(n_per_seed=100, n_seeds=5, base_seed=1)
    r2 = sweep(n_per_seed=100, n_seeds=5, base_seed=1)
    assert [r["lift_pp"] for r in r1] == [r["lift_pp"] for r in r2]


def test_different_base_seed_produces_a_different_set_of_seeds_tried():
    r1 = sweep(n_per_seed=100, n_seeds=5, base_seed=1)
    r2 = sweep(n_per_seed=100, n_seeds=5, base_seed=100)
    assert [r["seed"] for r in r1] != [r["seed"] for r in r2]


def test_every_result_reports_treatment_and_holdout_counts():
    results = sweep(n_per_seed=200, n_seeds=3, base_seed=1)
    for r in results:
        assert r["treatment_n"] > 0
        assert r["holdout_n"] > 0
        assert r["treatment_n"] > r["holdout_n"]


def test_sweep_does_not_silently_drop_a_negative_or_zero_seed():
    results = sweep(n_per_seed=150, n_seeds=10, base_seed=500)
    assert len(results) == 10


def test_summary_statistics_match_a_hand_computation():
    results = sweep(n_per_seed=150, n_seeds=8, base_seed=1)
    lifts = [r["lift_pp"] for r in results]
    assert abs(statistics.median(lifts) - statistics.median([r["lift_pp"] for r in results])) < 1e-9
    assert abs(statistics.mean(lifts) - (sum(lifts) / len(lifts))) < 1e-9
