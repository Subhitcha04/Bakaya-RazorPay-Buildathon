from datetime import datetime

from app.agents.strategist import propose, StrategistInput
from app.control_plane.stopping_rules import LadderLevel


def _input(ladder_level: LadderLevel, ltv_band: str = "mid", now: datetime | None = None,
           prior_failures: int = 0, amount_paise: int = 49900) -> StrategistInput:
    return StrategistInput(
        case_id="c1", trace_id="t1", amount_paise=amount_paise, ladder_level=ladder_level,
        root_cause="insufficient_funds", diagnosis_confidence=0.9, ltv_band=ltv_band,
        prior_failures=prior_failures, now=now or datetime(2026, 9, 10, 8, 0),
    )


def test_silent_levels_get_no_channel():
    for level in (LadderLevel.L0, LadderLevel.L1, LadderLevel.L2):
        result = propose(_input(level))
        assert result.channel is None


def test_l3_gets_email_no_offer():
    result = propose(_input(LadderLevel.L3))
    assert result.channel == "email"
    assert result.offer_tier is None
    assert result.amount_paise == 0


def test_l4_gets_whatsapp_and_an_offer_for_mid_ltv():
    result = propose(_input(LadderLevel.L4, ltv_band="mid"))
    assert result.channel == "whatsapp"
    assert result.offer_tier == "standard_grace"
    assert result.amount_paise == 5_000


def test_l4_gets_no_offer_for_low_ltv():
    result = propose(_input(LadderLevel.L4, ltv_band="low"))
    assert result.offer_tier is None
    assert result.amount_paise == 0


def test_l5_gets_no_channel_agent_never_sends_for_human_queue():
    result = propose(_input(LadderLevel.L5))
    assert result.channel is None


def test_proposal_never_reads_or_sets_authorization():
    result = propose(_input(LadderLevel.L3))
    assert not hasattr(result, "authorized")
    assert not hasattr(result, "approved")


def test_timing_pushes_to_next_month_when_late_in_month_for_l1():
    late_month = datetime(2026, 9, 27, 14, 0)
    result = propose(_input(LadderLevel.L1, now=late_month))
    assert result.send_at.month == 10
    assert result.send_at.day == 2


def test_timing_is_near_term_for_l1_earlier_in_month():
    early_month = datetime(2026, 9, 5, 14, 0)
    result = propose(_input(LadderLevel.L1, now=early_month, prior_failures=0))
    assert result.send_at.month == 9
    assert result.send_at > early_month


def test_timing_is_now_for_non_l1_levels():
    now = datetime(2026, 9, 27, 14, 0)
    result = propose(_input(LadderLevel.L3, now=now))
    assert result.send_at == now


def test_proposal_is_deterministic_for_the_same_input():
    inp = _input(LadderLevel.L4, ltv_band="high")
    r1 = propose(inp)
    r2 = propose(inp)
    assert r1.channel == r2.channel
    assert r1.offer_tier == r2.offer_tier
    assert r1.amount_paise == r2.amount_paise
