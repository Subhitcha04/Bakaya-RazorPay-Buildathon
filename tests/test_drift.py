from app.mlops.drift import compute_psi


def test_identical_distributions_are_stable():
    baseline = ["A"] * 50 + ["B"] * 30 + ["C"] * 20
    current = ["A"] * 50 + ["B"] * 30 + ["C"] * 20
    report = compute_psi(baseline, current)
    assert report.psi == 0.0
    assert report.verdict == "stable"


def test_mild_shift_is_still_stable():
    baseline = ["A"] * 50 + ["B"] * 30 + ["C"] * 20
    current = ["A"] * 45 + ["B"] * 33 + ["C"] * 22
    report = compute_psi(baseline, current)
    assert report.verdict == "stable"


def test_moderate_shift_is_flagged_as_moderate():
    baseline = ["A"] * 50 + ["B"] * 30 + ["C"] * 20
    current = ["A"] * 30 + ["B"] * 40 + ["C"] * 30
    report = compute_psi(baseline, current)
    assert 0.10 <= report.psi < 0.25
    assert report.verdict == "moderate_shift"


def test_drastic_shift_is_significant():
    baseline = ["A"] * 100
    current = ["B"] * 100
    report = compute_psi(baseline, current)
    assert report.verdict == "significant_shift"
    assert report.psi > 0.25


def test_psi_is_symmetric_between_baseline_and_current():
    baseline = ["A"] * 70 + ["B"] * 30
    current = ["A"] * 40 + ["B"] * 60
    forward = compute_psi(baseline, current)
    backward = compute_psi(current, baseline)
    assert abs(forward.psi - backward.psi) < 1e-9


def test_empty_baseline_or_current_gives_insufficient_data():
    assert compute_psi([], ["A"]).verdict == "insufficient_data"
    assert compute_psi(["A"], []).verdict == "insufficient_data"


def test_per_category_reports_both_sides_even_when_a_category_is_new():
    baseline = ["A"] * 100
    current = ["A"] * 80 + ["B"] * 20
    report = compute_psi(baseline, current)
    assert report.per_category["B"] == (0.0, 0.2)
    assert report.per_category["A"] == (1.0, 0.8)


def test_category_disappearing_entirely_is_captured():
    baseline = ["A"] * 80 + ["B"] * 20
    current = ["A"] * 100
    report = compute_psi(baseline, current)
    assert report.per_category["B"] == (0.2, 0.0)
