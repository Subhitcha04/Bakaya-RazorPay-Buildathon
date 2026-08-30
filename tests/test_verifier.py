from datetime import datetime, timedelta

from app.execution.verifier import verify, PaymentEvent, ATTRIBUTION_WINDOW


EXECUTED_AT = datetime(2026, 9, 1, 10, 0)


def _event(event_id: str, hours_after: float, amount_paise: int = 49900,
           is_missed_cycle_charge: bool = True) -> PaymentEvent:
    return PaymentEvent(
        event_id=event_id, amount_paise=amount_paise,
        occurred_at=EXECUTED_AT + timedelta(hours=hours_after),
        is_missed_cycle_charge=is_missed_cycle_charge,
    )


def test_no_candidate_events_gives_no_payment_seen():
    result = verify("a1", EXECUTED_AT, 49900, [], now=EXECUTED_AT + timedelta(days=1))
    assert result.outcome_kind == "no_payment_seen"
    assert result.recovered_paise == 0
    assert result.attribution_window_ok is False


def test_causality_excludes_events_before_the_attempt():
    before = _event("e1", hours_after=-1)
    result = verify("a1", EXECUTED_AT, 49900, [before], now=EXECUTED_AT + timedelta(days=1))
    assert result.outcome_kind == "no_payment_seen"


def test_event_within_window_is_attributed():
    within = _event("e1", hours_after=48)
    result = verify("a1", EXECUTED_AT, 49900, [within], now=EXECUTED_AT + timedelta(days=3))
    assert result.outcome_kind == "same_cycle_recovered"
    assert result.recovered_paise == 49900
    assert result.attributed_to_attempt_id == "a1"


def test_event_outside_window_is_excluded():
    late = _event("e1", hours_after=ATTRIBUTION_WINDOW.total_seconds() / 3600 + 24)
    result = verify("a1", EXECUTED_AT, 49900, [late], now=EXECUTED_AT + timedelta(days=20))
    assert result.outcome_kind == "no_payment_seen"


def test_event_exactly_at_window_boundary_is_included():
    at_boundary_hours = ATTRIBUTION_WINDOW.total_seconds() / 3600
    boundary = _event("e1", hours_after=at_boundary_hours)
    result = verify("a1", EXECUTED_AT, 49900, [boundary], now=EXECUTED_AT + timedelta(days=20))
    assert result.outcome_kind == "same_cycle_recovered"


def test_reactivation_without_retroactive_charge_is_not_counted_as_recovery():
    future_cycle_charge = _event("e1", hours_after=48, amount_paise=49900, is_missed_cycle_charge=False)
    result = verify("a1", EXECUTED_AT, 49900, [future_cycle_charge], now=EXECUTED_AT + timedelta(days=3))
    assert result.outcome_kind == "future_cycle_resumed_only"
    assert result.recovered_paise == 0
    assert result.attributed_to_attempt_id is None
    assert "does not retroactively charge" in result.rationale


def test_same_cycle_event_wins_over_future_cycle_event_even_if_future_cycle_is_earlier():
    future_first = _event("e_future", hours_after=10, is_missed_cycle_charge=False)
    same_cycle_later = _event("e_same", hours_after=100, is_missed_cycle_charge=True)
    result = verify("a1", EXECUTED_AT, 49900, [future_first, same_cycle_later],
                     now=EXECUTED_AT + timedelta(days=10))
    assert result.outcome_kind == "same_cycle_recovered"
    assert result.attributed_to_attempt_id == "a1"


def test_multiple_same_cycle_candidates_picks_the_earliest():
    first = _event("e_first", hours_after=10, is_missed_cycle_charge=True)
    second = _event("e_second", hours_after=50, is_missed_cycle_charge=True)
    result = verify("a1", EXECUTED_AT, 49900, [second, first], now=EXECUTED_AT + timedelta(days=10))
    assert "e_first" in result.rationale
