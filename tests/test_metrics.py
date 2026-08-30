from app.observability.metrics import (
    SLOS, DIAGNOSTIC_METRIC_NAMES, Severity,
    check_duplicate_financial_actions, check_policy_violations,
    check_webhook_ingest_success_rate, check_webhook_ingest_p99_latency,
    check_workflow_completion_rate, check_cost_per_case,
)


def test_exactly_two_slos_page():
    paging = [s for s in SLOS if s.severity == Severity.PAGE]
    assert {s.name for s in paging} == {"duplicate_financial_actions", "policy_violations"}


def test_diagnostic_names_never_collide_with_slo_names():
    slo_names = {s.name for s in SLOS}
    assert slo_names.isdisjoint(DIAGNOSTIC_METRIC_NAMES)


def test_duplicate_financial_actions_zero_is_clean():
    assert check_duplicate_financial_actions(0) is None


def test_duplicate_financial_actions_nonzero_breaches():
    breach = check_duplicate_financial_actions(1)
    assert breach is not None
    assert breach.slo.severity == Severity.PAGE


def test_policy_violations_zero_is_clean():
    assert check_policy_violations(0) is None


def test_policy_violations_nonzero_breaches():
    breach = check_policy_violations(3)
    assert breach is not None
    assert breach.slo.severity == Severity.PAGE


def test_webhook_success_rate_above_threshold_is_clean():
    assert check_webhook_ingest_success_rate(0.9995) is None


def test_webhook_success_rate_below_threshold_breaches():
    breach = check_webhook_ingest_success_rate(0.995)
    assert breach is not None
    assert breach.slo.severity == Severity.ALERT


def test_webhook_p99_latency_under_threshold_is_clean():
    assert check_webhook_ingest_p99_latency(150) is None


def test_webhook_p99_latency_over_threshold_breaches():
    assert check_webhook_ingest_p99_latency(250) is not None


def test_workflow_completion_above_threshold_is_clean():
    assert check_workflow_completion_rate(0.99) is None


def test_workflow_completion_below_threshold_breaches():
    assert check_workflow_completion_rate(0.95) is not None


def test_cost_per_case_under_budget_is_clean():
    assert check_cost_per_case(avg_cost_paise=5, budget_paise=20) is None


def test_cost_per_case_over_budget_breaches():
    assert check_cost_per_case(avg_cost_paise=25, budget_paise=20) is not None
