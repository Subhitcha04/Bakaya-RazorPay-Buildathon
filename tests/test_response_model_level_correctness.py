from app.sim.response_model import simulate_recovery, BASELINE_RECOVERY_RATE, INTERVENTION_UPLIFT


def test_default_level_correctness_matches_prior_behaviour_exactly():
    r1 = simulate_recovery("case_x", seed=5, root_cause="insufficient_funds", arm="treatment")
    r2 = simulate_recovery("case_x", seed=5, root_cause="insufficient_funds", arm="treatment",
                            level_correctness=1.0)
    assert r1 == r2


def test_holdout_gets_zero_uplift_regardless_of_level_correctness():
    r_full = simulate_recovery("c1", seed=1, root_cause="insufficient_funds",
                                arm="holdout", level_correctness=1.0)
    r_zero = simulate_recovery("c1", seed=1, root_cause="insufficient_funds",
                                arm="holdout", level_correctness=0.0)
    assert r_full == r_zero


def test_zero_level_correctness_makes_a_non_holdout_arm_behave_like_holdout():
    material_cause = "insufficient_funds"
    for case_id in ["c1", "c2", "c3", "c4", "c5"]:
        holdout = simulate_recovery(case_id, seed=9, root_cause=material_cause, arm="holdout")
        wrong_action = simulate_recovery(case_id, seed=9, root_cause=material_cause,
                                          arm="exhaustive_random", level_correctness=0.0)
        assert holdout == wrong_action


def test_partial_level_correctness_is_between_zero_and_full_uplift():
    base = BASELINE_RECOVERY_RATE["expired_card"]
    uplift = INTERVENTION_UPLIFT["expired_card"]
    p_full = base + uplift * 1.0
    p_half = base + uplift * 0.5
    p_none = base + uplift * 0.0
    assert p_none < p_half < p_full


def test_arm_other_than_holdout_or_treatment_still_gets_uplift():
    for case_id in [f"c{i}" for i in range(30)]:
        exhaustive = simulate_recovery(case_id, seed=3, root_cause="expired_card",
                                        arm="exhaustive_random", level_correctness=1.0)
        treatment = simulate_recovery(case_id, seed=3, root_cause="expired_card",
                                       arm="treatment", level_correctness=1.0)
        assert exhaustive == treatment
