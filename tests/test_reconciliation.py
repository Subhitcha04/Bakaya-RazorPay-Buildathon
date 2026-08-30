from app.execution.reconciliation import reconcile


def test_all_matching_gives_perfect_accuracy():
    outcomes = [
        {"case_id": "c1", "recovered_paise": 49900, "attempt_id": "a1"},
        {"case_id": "c2", "recovered_paise": 0, "attempt_id": "a2"},
    ]
    true_states = {
        "a1": {"status": "captured", "amount_paise": 49900},
        "a2": {"status": "failed", "amount_paise": 0},
    }
    report = reconcile(outcomes, fetch_true_state_fn=lambda aid: true_states[aid])
    assert report.accuracy == 1.0
    assert report.mismatched_rows == []


def test_catches_the_exact_bug_it_exists_for_agent_believes_it_recovered_money_it_didnt():
    outcomes = [{"case_id": "c1", "recovered_paise": 49900, "attempt_id": "a1"}]
    true_states = {"a1": {"status": "failed", "amount_paise": 0}}

    report = reconcile(outcomes, fetch_true_state_fn=lambda aid: true_states[aid])

    assert report.accuracy == 0.0
    assert len(report.mismatched_rows) == 1
    row = report.mismatched_rows[0]
    assert row.case_id == "c1"
    assert row.internal_recovered_paise == 49900
    assert row.true_recovered_paise == 0
    assert "MISMATCH" in row.note


def test_partial_mismatch_reports_accurate_ratio():
    outcomes = [
        {"case_id": "c1", "recovered_paise": 49900, "attempt_id": "a1"},
        {"case_id": "c2", "recovered_paise": 10000, "attempt_id": "a2"},
        {"case_id": "c3", "recovered_paise": 0, "attempt_id": "a3"},
    ]
    true_states = {
        "a1": {"status": "captured", "amount_paise": 49900},
        "a2": {"status": "captured", "amount_paise": 8000},
        "a3": {"status": "failed", "amount_paise": 0},
    }
    report = reconcile(outcomes, fetch_true_state_fn=lambda aid: true_states[aid])
    assert report.total_checked == 3
    assert report.matched == 2
    assert abs(report.accuracy - (2 / 3)) < 1e-9
    assert len(report.mismatched_rows) == 1
    assert report.mismatched_rows[0].case_id == "c2"


def test_empty_outcomes_gives_vacuous_perfect_accuracy_not_a_crash():
    report = reconcile([], fetch_true_state_fn=lambda aid: {})
    assert report.total_checked == 0
    assert report.accuracy == 1.0
    assert report.mismatched_rows == []
