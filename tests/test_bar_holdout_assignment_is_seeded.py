"""
Named after the bar phrase: "measured money recovered" only means
anything if the batch is reproducible. Every test here proves
determinism explicitly, not just that the functions run without error.
"""
from app.experiment.assignment import assign_arm
from app.sim.reality_generator import generate_population
from app.sim.response_model import simulate_recovery
from app.ladder.router import entry_level_for
from app.control_plane.stopping_rules import LadderLevel


def test_arm_assignment_is_deterministic_for_same_seed_and_case():
    a1 = assign_arm(seed=42, case_id="case_abc")
    a2 = assign_arm(seed=42, case_id="case_abc")
    assert a1 == a2


def test_arm_assignment_differs_by_seed_at_least_sometimes():
    ids = [f"case_{i}" for i in range(200)]
    arms_seed1 = [assign_arm(seed=1, case_id=cid) for cid in ids]
    arms_seed2 = [assign_arm(seed=2, case_id=cid) for cid in ids]
    assert arms_seed1 != arms_seed2


def test_arm_assignment_respects_holdout_percentage_approximately():
    ids = [f"case_{i}" for i in range(5000)]
    arms = [assign_arm(seed=7, case_id=cid, holdout_pct=0.25) for cid in ids]
    holdout_frac = arms.count("holdout") / len(arms)
    assert 0.22 < holdout_frac < 0.28


def test_population_generation_is_deterministic_for_same_seed():
    pop1 = generate_population(n=100, seed=999)
    pop2 = generate_population(n=100, seed=999)
    assert [c.case_id for c in pop1] == [c.case_id for c in pop2]
    assert [c.root_cause for c in pop1] == [c.root_cause for c in pop2]


def test_population_generation_differs_for_different_seed():
    pop1 = generate_population(n=100, seed=1)
    pop2 = generate_population(n=100, seed=2)
    assert [c.case_id for c in pop1] != [c.case_id for c in pop2]


def test_simulated_recovery_is_deterministic():
    r1 = simulate_recovery("case_x", seed=5, root_cause="insufficient_funds", arm="treatment")
    r2 = simulate_recovery("case_x", seed=5, root_cause="insufficient_funds", arm="treatment")
    assert r1 == r2


def test_retention_risk_always_routes_to_human_regardless_of_root_cause():
    for cause in ["insufficient_funds", "expired_card", "fraud_flag", "unknown_cause"]:
        assert entry_level_for(cause, executes=False) == LadderLevel.L5


def test_unmapped_root_cause_fails_safe_to_human_not_silent_default():
    assert entry_level_for("some_never_seen_cause", executes=True) == LadderLevel.L5


def test_known_root_causes_map_to_their_declared_entry_level():
    assert entry_level_for("insufficient_funds", executes=True) == LadderLevel.L1
    assert entry_level_for("expired_card", executes=True) == LadderLevel.L3
    assert entry_level_for("fraud_flag", executes=True) == LadderLevel.L5
