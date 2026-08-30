from app.experiment.oracle import compute_oracle_ceiling, captured_fraction
from app.sim.response_model import INTERVENTION_UPLIFT


def test_empty_population_gives_zero_ceiling():
    report = compute_oracle_ceiling([])
    assert report.oracle_incremental_pp == 0.0
    assert report.oracle_would_act_on_pct == 0.0


def test_all_positive_uplift_causes_oracle_acts_on_everything():
    report = compute_oracle_ceiling(["insufficient_funds"] * 10)
    assert report.oracle_would_act_on_pct == 100.0


def test_customer_intent_is_the_sleeping_dog_oracle_never_acts_on_it():
    assert INTERVENTION_UPLIFT["customer_intent"] < 0
    report = compute_oracle_ceiling(["customer_intent"] * 10)
    assert report.oracle_would_act_on_pct == 0.0
    assert report.oracle_incremental_pp == 0.0


def test_mixed_population_ceiling_matches_hand_computed_value():
    causes = ["insufficient_funds"] * 5 + ["customer_intent"] * 5
    report = compute_oracle_ceiling(causes)
    assert abs(report.oracle_incremental_pp - 9.0) < 1e-9
    assert report.oracle_would_act_on_pct == 50.0


def test_per_cause_uplift_reports_every_distinct_cause_present():
    causes = ["insufficient_funds", "expired_card", "insufficient_funds"]
    report = compute_oracle_ceiling(causes)
    assert set(report.per_cause_uplift.keys()) == {"insufficient_funds", "expired_card"}


def test_captured_fraction_full_capture():
    assert captured_fraction(actual_incremental_pp=9.0, oracle_incremental_pp=9.0) == 1.0


def test_captured_fraction_partial_capture():
    frac = captured_fraction(actual_incremental_pp=4.5, oracle_incremental_pp=9.0)
    assert abs(frac - 0.5) < 1e-9


def test_captured_fraction_clamps_above_oracle_to_one():
    frac = captured_fraction(actual_incremental_pp=12.0, oracle_incremental_pp=9.0)
    assert frac == 1.0


def test_captured_fraction_clamps_negative_to_zero():
    frac = captured_fraction(actual_incremental_pp=-2.0, oracle_incremental_pp=9.0)
    assert frac == 0.0


def test_captured_fraction_zero_oracle_returns_zero_not_a_crash():
    assert captured_fraction(actual_incremental_pp=5.0, oracle_incremental_pp=0.0) == 0.0
