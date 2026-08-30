from app.experiment.assignment import assign_arm_multi, assign_arm, ARM_LABELS_4WAY


def test_multi_assignment_always_returns_one_of_the_declared_arms():
    for i in range(200):
        arm = assign_arm_multi(seed=1, case_id=f"case_{i}")
        assert arm in ARM_LABELS_4WAY


def test_multi_assignment_is_deterministic():
    a = assign_arm_multi(seed=7, case_id="case_x")
    b = assign_arm_multi(seed=7, case_id="case_x")
    assert a == b


def test_multi_assignment_is_roughly_evenly_split():
    counts = {arm: 0 for arm in ARM_LABELS_4WAY}
    n = 4000
    for i in range(n):
        counts[assign_arm_multi(seed=99, case_id=f"case_{i}")] += 1
    for arm, count in counts.items():
        frac = count / n
        assert 0.20 < frac < 0.30, f"{arm} got {frac:.1%}, expected ~25%"


def test_multi_assignment_uses_a_different_salt_than_the_2arm_function():
    matches = 0
    n = 200
    for i in range(n):
        case_id = f"case_{i}"
        two_arm = assign_arm(seed=5, case_id=case_id)
        four_arm = assign_arm_multi(seed=5, case_id=case_id)
        if (two_arm == "holdout") == (four_arm == "holdout"):
            matches += 1
    assert matches < n * 0.9
