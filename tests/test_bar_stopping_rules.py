"""
Named after the bar phrase, not a function: "stopping rules" is one of
Razorpay's own five clauses in the track brief. Every test here proves
a specific rule from the ladder, not just "the function runs."
"""
from app.control_plane.stopping_rules import (
    evaluate, LadderLevel, is_terminal_reachable_from, LADDER_ORDER,
)


def test_explicit_refusal_hard_stops_regardless_of_attempts_remaining():
    decision = evaluate(
        current_level=LadderLevel.L1, attempts_at_current_level=0,
        hours_since_last_attempt=None, customer_refused=True,
        total_contacts_today_all_surfaces=0,
    )
    assert decision.should_stop is True
    assert decision.reason == "explicit_refusal"
    assert decision.next_level == LadderLevel.L6


def test_no_escalating_offer_ladder_after_refusal_even_at_low_level():
    decision = evaluate(
        current_level=LadderLevel.L1, attempts_at_current_level=0,
        hours_since_last_attempt=100, customer_refused=True,
        total_contacts_today_all_surfaces=0,
    )
    assert decision.next_level == LadderLevel.L6


def test_daily_contact_cap_shared_across_surfaces_stops_and_escalates_to_human():
    decision = evaluate(
        current_level=LadderLevel.L3, attempts_at_current_level=0,
        hours_since_last_attempt=100, customer_refused=False,
        total_contacts_today_all_surfaces=3, contact_cap_per_day=3,
    )
    assert decision.should_stop is True
    assert decision.reason == "daily_contact_cap_reached"
    assert decision.next_level == LadderLevel.L5


def test_max_attempts_at_level_advances_rather_than_stops():
    decision = evaluate(
        current_level=LadderLevel.L1, attempts_at_current_level=3,
        hours_since_last_attempt=100, customer_refused=False,
        total_contacts_today_all_surfaces=0,
    )
    assert decision.should_stop is False
    assert decision.next_level == LadderLevel.L2


def test_cooldown_not_elapsed_stops_without_advancing():
    decision = evaluate(
        current_level=LadderLevel.L3, attempts_at_current_level=0,
        hours_since_last_attempt=2,
        customer_refused=False, total_contacts_today_all_surfaces=0,
    )
    assert decision.should_stop is True
    assert decision.reason == "cooldown_not_elapsed"


def test_already_terminal_always_stops():
    decision = evaluate(
        current_level=LadderLevel.L6, attempts_at_current_level=0,
        hours_since_last_attempt=None, customer_refused=False,
        total_contacts_today_all_surfaces=0,
    )
    assert decision.should_stop is True
    assert decision.reason == "already_terminal"


def test_every_level_has_a_path_to_terminal():
    for level in LADDER_ORDER:
        assert is_terminal_reachable_from(level), f"{level} cannot reach L6"
