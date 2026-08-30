from app.ladder.random_policy import random_ladder_level, level_correctness_for, CANDIDATE_LEVELS
from app.control_plane.stopping_rules import LadderLevel


def test_random_level_is_always_one_of_the_candidate_levels():
    for i in range(50):
        level = random_ladder_level(f"case_{i}", seed=1)
        assert level in CANDIDATE_LEVELS


def test_random_level_is_deterministic_for_same_case_and_seed():
    a = random_ladder_level("case_x", seed=42)
    b = random_ladder_level("case_x", seed=42)
    assert a == b


def test_random_level_varies_across_cases():
    levels = {random_ladder_level(f"case_{i}", seed=1) for i in range(50)}
    assert len(levels) > 1


def test_random_level_differs_by_seed():
    seeds_differ = any(
        random_ladder_level(f"c{i}", seed=1) != random_ladder_level(f"c{i}", seed=2)
        for i in range(20)
    )
    assert seeds_differ


def test_correctness_is_full_when_random_matches_the_correct_level():
    assert level_correctness_for(LadderLevel.L3, LadderLevel.L3) == 1.0


def test_correctness_is_partial_when_random_misses():
    correctness = level_correctness_for(LadderLevel.L1, LadderLevel.L4)
    assert 0.0 < correctness < 1.0
