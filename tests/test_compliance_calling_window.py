"""
Closes the second gap found by scripts/mutate_gates.py: calling_window
had never been tested in a scenario where it actually BLOCKS. Every
prior test either used a non-time-sensitive channel (email) or never
set an out-of-window `now`, so the gate's only real branch -- refusing
a voice/sms/whatsapp contact outside 8am-7pm -- had zero coverage.
"""
from datetime import datetime

from app.control_plane.gates import calling_window
from app.schemas.contracts import ProposedActionOut


def _action(channel: str | None) -> ProposedActionOut:
    return ProposedActionOut(case_id="c1", ladder_level="L4", channel=channel,
                              amount_paise=1000, proposer_model="s", trace_id="t")


def test_blocks_whatsapp_contact_late_at_night():
    late_night = datetime(2026, 9, 10, 23, 30)
    result = calling_window.check(db=None, case=None, proposed=_action("whatsapp"),
                                   context={"now": late_night})
    assert result.passed is False
    assert result.reason == "outside voluntary 8am-7pm contact window"


def test_blocks_sms_contact_early_morning():
    early_morning = datetime(2026, 9, 10, 5, 0)
    result = calling_window.check(db=None, case=None, proposed=_action("sms"),
                                   context={"now": early_morning})
    assert result.passed is False


def test_blocks_voice_contact_outside_window():
    late = datetime(2026, 9, 10, 20, 0)
    result = calling_window.check(db=None, case=None, proposed=_action("voice"),
                                   context={"now": late})
    assert result.passed is False


def test_allows_whatsapp_contact_during_daytime():
    midday = datetime(2026, 9, 10, 14, 0)
    result = calling_window.check(db=None, case=None, proposed=_action("whatsapp"),
                                   context={"now": midday})
    assert result.passed is True


def test_allows_contact_exactly_at_the_window_boundaries():
    start = datetime(2026, 9, 10, 8, 0)
    end = datetime(2026, 9, 10, 19, 0)
    assert calling_window.check(None, None, _action("sms"), {"now": start}).passed is True
    assert calling_window.check(None, None, _action("sms"), {"now": end}).passed is True


def test_email_is_never_time_restricted_regardless_of_hour():
    late_night = datetime(2026, 9, 10, 3, 0)
    result = calling_window.check(None, None, _action("email"), {"now": late_night})
    assert result.passed is True


def test_no_channel_silent_action_is_always_allowed():
    late_night = datetime(2026, 9, 10, 3, 0)
    result = calling_window.check(None, None, _action(None), {"now": late_night})
    assert result.passed is True
