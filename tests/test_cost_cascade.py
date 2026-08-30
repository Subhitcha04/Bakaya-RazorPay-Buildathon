from app.cost.cascade import escalate_if_low_confidence


def test_high_confidence_never_calls_expensive_fn():
    calls = []

    def expensive():
        calls.append(1)
        return "expensive_result"

    result, escalated = escalate_if_low_confidence(
        cheap_result="cheap_result", get_confidence=lambda r: 0.9, expensive_fn=expensive,
    )
    assert result == "cheap_result"
    assert escalated is False
    assert calls == []


def test_low_confidence_escalates_and_calls_expensive_fn():
    calls = []

    def expensive():
        calls.append(1)
        return "expensive_result"

    result, escalated = escalate_if_low_confidence(
        cheap_result="cheap_result", get_confidence=lambda r: 0.3, expensive_fn=expensive,
    )
    assert result == "expensive_result"
    assert escalated is True
    assert calls == [1]


def test_threshold_boundary_is_inclusive_on_the_cheap_side():
    from app.cost.cascade import CONFIDENCE_ESCALATION_THRESHOLD
    _, escalated = escalate_if_low_confidence(
        cheap_result="x", get_confidence=lambda r: CONFIDENCE_ESCALATION_THRESHOLD,
        expensive_fn=lambda: "y",
    )
    assert escalated is False
