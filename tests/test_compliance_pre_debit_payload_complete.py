from datetime import datetime, timedelta

from app.control_plane.gates.rbi import pre_debit_window

COMPLETE_NOTIFICATION = {
    "merchant_name": "Acme", "amount_paise": 49900, "debit_at": "2026-09-01T10:00:00",
    "mandate_reference": "mnd_123", "transaction_reference": "txn_456",
    "reason_for_debit": "subscription renewal", "grievance_redressal": "support@acme.test",
}


def test_blocks_when_no_notification_scheduled():
    result = pre_debit_window.check(
        db=None, case=None, proposed=None,
        context={"is_mandate_debit": True},
    )
    assert result.passed is False
    assert result.reason == "no pre-debit notification scheduled"


def test_blocks_when_required_fields_missing():
    incomplete = dict(COMPLETE_NOTIFICATION)
    del incomplete["grievance_redressal"]
    result = pre_debit_window.check(
        db=None, case=None, proposed=None,
        context={"is_mandate_debit": True, "pre_debit_notification": incomplete,
                 "notification_sent_at": datetime(2026, 8, 31), "debit_at": datetime(2026, 9, 1)},
    )
    assert result.passed is False
    assert "grievance_redressal" in result.evidence["missing_fields"]


def test_blocks_when_lead_time_under_24_hours():
    debit_at = datetime(2026, 9, 1, 10, 0)
    notified_at = debit_at - timedelta(hours=2)
    result = pre_debit_window.check(
        db=None, case=None, proposed=None,
        context={"is_mandate_debit": True, "pre_debit_notification": COMPLETE_NOTIFICATION,
                 "notification_sent_at": notified_at, "debit_at": debit_at},
    )
    assert result.passed is False
    assert result.reason == "notification sent less than 24h before debit"


def test_allows_when_complete_and_24h_lead_time_met():
    debit_at = datetime(2026, 9, 1, 10, 0)
    notified_at = debit_at - timedelta(hours=25)
    result = pre_debit_window.check(
        db=None, case=None, proposed=None,
        context={"is_mandate_debit": True, "pre_debit_notification": COMPLETE_NOTIFICATION,
                 "notification_sent_at": notified_at, "debit_at": debit_at},
    )
    assert result.passed is True


def test_fastag_exemption_skips_the_notification_requirement_entirely():
    result = pre_debit_window.check(
        db=None, case=None, proposed=None,
        context={"is_mandate_debit": True, "notification_exempt": True},
    )
    assert result.passed is True


def test_skips_non_mandate_debits():
    result = pre_debit_window.check(db=None, case=None, proposed=None, context={})
    assert result.passed is True
