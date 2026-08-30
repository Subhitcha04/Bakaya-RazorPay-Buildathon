"""
Day 5 checkpoint: generates a synthetic batch, assigns experiment arms,
routes each case to its ladder entry level, simulates an outcome, and
prints an incremental-lift table -- reproducibly, given a seed.
"""
from __future__ import annotations

import argparse
from collections import defaultdict

from app.sim.reality_generator import generate_population
from app.sim.response_model import simulate_recovery
from app.experiment.assignment import assign_arm, DEFAULT_HOLDOUT_PCT
from app.experiment.segments import classify_segment
from app.experiment.power import detectable_effect_pp
from app.ladder.router import entry_level_for


def run_batch(n: int, seed: int) -> list[dict]:
    population = generate_population(n=n, seed=seed)
    rows = []
    for case in population:
        arm = assign_arm(seed=seed, case_id=case.case_id)
        entry_level = entry_level_for(case.root_cause, executes=True)
        recovered = simulate_recovery(case.case_id, seed, case.root_cause, arm)
        segment = classify_segment(case.root_cause, case.amount_paise, case.prior_failures)
        rows.append({
            "case_id": case.case_id, "root_cause": case.root_cause, "arm": arm,
            "entry_level": entry_level.value, "recovered": recovered, "segment": segment,
        })
    return rows


def print_report(rows: list[dict], n: int, seed: int) -> None:
    treatment = [r for r in rows if r["arm"] == "treatment"]
    holdout = [r for r in rows if r["arm"] == "holdout"]

    t_rate = sum(r["recovered"] for r in treatment) / len(treatment) if treatment else 0.0
    h_rate = sum(r["recovered"] for r in holdout) / len(holdout) if holdout else 0.0
    lift_pp = (t_rate - h_rate) * 100

    print(f"Batch: n={n}, seed={seed}, holdout_pct={DEFAULT_HOLDOUT_PCT}")
    print(f"Treatment: n={len(treatment)}, recovery_rate={t_rate:.1%}")
    print(f"Holdout:   n={len(holdout)}, recovery_rate={h_rate:.1%}")
    print(f"Incremental lift: {lift_pp:+.1f}pp")

    mde = detectable_effect_pp(n_per_arm=len(holdout), baseline_rate=h_rate or 0.1)
    print(f"Detectable effect at this n (holdout arm, alpha=0.05, power=0.8): ~{mde}pp")

    print("\nRecovery rate by root cause (treatment vs holdout):")
    by_cause = defaultdict(lambda: {"treatment": [], "holdout": []})
    for r in rows:
        by_cause[r["root_cause"]][r["arm"]].append(r["recovered"])
    for cause, arms in sorted(by_cause.items()):
        t, h = arms["treatment"], arms["holdout"]
        t_r = sum(t) / len(t) if t else 0.0
        h_r = sum(h) / len(h) if h else 0.0
        print(f"  {cause:22s} treatment={t_r:5.1%} (n={len(t):4d})  "
              f"holdout={h_r:5.1%} (n={len(h):4d})  lift={((t_r - h_r) * 100):+5.1f}pp")

    print("\nEntry-level distribution:")
    by_level = defaultdict(int)
    for r in rows:
        by_level[r["entry_level"]] += 1
    for level, count in sorted(by_level.items()):
        print(f"  {level}: {count}")

    unclassified = sum(1 for r in rows if r["segment"] == "unclassified")
    print(f"\nUnclassified into a pre-declared segment: {unclassified} of {len(rows)} "
          f"({unclassified / len(rows):.1%}) -- report this honestly in EVALUATION.md if nonzero")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260901)
    args = parser.parse_args()
    rows = run_batch(args.n, args.seed)
    print_report(rows, args.n, args.seed)
