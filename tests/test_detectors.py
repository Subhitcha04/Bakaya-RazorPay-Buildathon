from datetime import datetime, timedelta

from app.detectors import payment_failure, checkout_abandonment, mandate_failure
from app.detectors import receivables, churn_intent, cohort_degradation
from app.detectors.registry import DETECTORS, EVENT_DRIVEN, SWEEP_BASED, dispatch_event


def test_registry_count_reconciles():
    assert len(DETECTORS) == 6


def test_payment_failure_fires_only_on_payment_failed_event():
    payload = {"account_id": "acc_1", "payload": {"payment": {"entity": {
        "id": "pay_1", "amount": 49900, "customer_id": "cust_1",
        "error_code": "BAD_REQUEST_ERROR", "error_description": "insufficient balance",
    }}}}
    result = payment_failure.on_event("payment.failed", payload)
    assert result is not None
    assert result.risk_case.surface == "payment_failure"
    assert result.risk_case.executes is True
    assert result.risk_case.amount_paise == 49900


def test_payment_failure_ignores_other_event_types():
    assert payment_failure.on_event("payment.captured", {}) is None


def test_mandate_failure_fires_on_pending_and_halted():
    payload = {"account_id": "acc_1", "payload": {"subscription": {"entity": {
        "id": "sub_1", "customer_id": "cust_1", "plan_amount": 99900,
    }}}}
    for event_type in ("subscription.pending", "subscription.halted"):
        result = mandate_failure.on_event(event_type, payload)
        assert result is not None
        assert result.risk_case.surface == "mandate_failure"


def test_mandate_failure_ignores_unrelated_events():
    assert mandate_failure.on_event("subscription.activated", {}) is None


def test_checkout_abandonment_fires_only_after_window_and_if_uncaptured():
    now = datetime(2026, 9, 1, 12, 0)
    candidates = [
        {"order_id": "o1", "merchant_id": "m1", "customer_id": "c1", "amount_paise": 1000,
         "created_at": now - timedelta(minutes=45), "captured": False},
        {"order_id": "o2", "merchant_id": "m1", "customer_id": "c2", "amount_paise": 1000,
         "created_at": now - timedelta(minutes=5), "captured": False},
        {"order_id": "o3", "merchant_id": "m1", "customer_id": "c3", "amount_paise": 1000,
         "created_at": now - timedelta(minutes=45), "captured": True},
    ]
    results = checkout_abandonment.sweep(candidates, now)
    assert len(results) == 1
    assert results[0].rzp_entity_id == "o1"


def test_receivables_fires_only_on_overdue_unpaid_invoices():
    now = datetime(2026, 9, 1)
    candidates = [
        {"invoice_id": "i1", "merchant_id": "m1", "customer_id": "c1", "amount_paise": 500000,
         "due_at": datetime(2026, 8, 20), "paid": False},
        {"invoice_id": "i2", "merchant_id": "m1", "customer_id": "c2", "amount_paise": 500000,
         "due_at": datetime(2026, 9, 10), "paid": False},
        {"invoice_id": "i3", "merchant_id": "m1", "customer_id": "c3", "amount_paise": 500000,
         "due_at": datetime(2026, 8, 20), "paid": True},
    ]
    results = receivables.sweep(candidates, now)
    assert len(results) == 1
    assert results[0].rzp_entity_id == "i1"


def test_churn_intent_always_executes_false_no_matter_what():
    payload = {"account_id": "acc_1", "payload": {"subscription": {"entity": {
        "id": "sub_1", "customer_id": "cust_1", "plan_amount": 999999999,
        "urgent": True, "high_value": True, "override_execute": True,
    }}}}
    result = churn_intent.on_event("subscription.cancellation_requested", payload)
    assert result is not None
    assert result.risk_case.executes is False
    assert result.risk_case.surface == "retention_risk"


def test_churn_intent_ignores_unrelated_events():
    assert churn_intent.on_event("subscription.activated", {}) is None


def test_cohort_degradation_flags_significant_drop_with_enough_samples():
    now = datetime(2026, 9, 1)
    candidates = [
        {"issuer": "hdfc", "method": "netbanking", "success": False,
         "merchant_id": "m1", "baseline_success_rate": 0.90}
        for _ in range(15)
    ]
    results = cohort_degradation.sweep(candidates, now)
    assert len(results) == 1
    assert results[0].risk_case.executes is False


def test_cohort_degradation_ignores_small_samples_even_if_rate_is_bad():
    now = datetime(2026, 9, 1)
    candidates = [
        {"issuer": "hdfc", "method": "netbanking", "success": False,
         "merchant_id": "m1", "baseline_success_rate": 0.90}
        for _ in range(3)
    ]
    results = cohort_degradation.sweep(candidates, now)
    assert results == []


def test_cohort_degradation_ignores_normal_success_rates():
    now = datetime(2026, 9, 1)
    candidates = [
        {"issuer": "hdfc", "method": "netbanking", "success": True,
         "merchant_id": "m1", "baseline_success_rate": 0.90}
        for _ in range(15)
    ]
    results = cohort_degradation.sweep(candidates, now)
    assert results == []


def test_dispatch_event_routes_to_the_right_detector_only():
    payload = {"account_id": "acc_1", "payload": {"payment": {"entity": {
        "id": "pay_1", "amount": 1000, "customer_id": "c1",
    }}}}
    results = dispatch_event("payment.failed", payload)
    assert len(results) == 1
    assert results[0].risk_case.surface == "payment_failure"


def test_event_driven_and_sweep_based_partitions_are_disjoint_in_capability():
    for d in DETECTORS:
        assert d.is_event_driven or d.is_sweep_based
