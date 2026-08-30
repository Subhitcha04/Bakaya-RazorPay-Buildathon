from app.cost.economic_gate import should_deliberate


def test_proceeds_when_expected_value_clears_cost():
    decision = should_deliberate(
        amount_paise=100_00, uplift_estimate=0.20, margin_rate=1.0, estimated_cost_paise=18,
    )
    assert decision.proceed is True


def test_refuses_low_value_case():
    decision = should_deliberate(
        amount_paise=99, uplift_estimate=0.05, margin_rate=1.0, estimated_cost_paise=18,
    )
    assert decision.proceed is False
    assert decision.reason == "negative expected value of deliberation"


def test_zero_uplift_always_refuses_when_cost_is_positive():
    decision = should_deliberate(
        amount_paise=999_999_00, uplift_estimate=0.0, margin_rate=1.0, estimated_cost_paise=1,
    )
    assert decision.proceed is False


def test_decision_reports_the_numbers_it_used():
    decision = should_deliberate(
        amount_paise=10_000, uplift_estimate=0.5, margin_rate=1.0, estimated_cost_paise=10,
    )
    assert decision.expected_value_paise == 5_000
    assert decision.estimated_cost_paise == 10
