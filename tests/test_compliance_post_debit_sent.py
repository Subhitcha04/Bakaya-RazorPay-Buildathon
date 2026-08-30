from app.control_plane.gates.rbi import post_debit_notification


def test_blocks_when_post_debit_notification_not_sent():
    result = post_debit_notification.check(
        db=None, case=None, proposed=None,
        context={"is_mandate_debit": True, "post_debit_notification_sent": False},
    )
    assert result.passed is False


def test_allows_when_post_debit_notification_sent():
    result = post_debit_notification.check(
        db=None, case=None, proposed=None,
        context={"is_mandate_debit": True, "post_debit_notification_sent": True},
    )
    assert result.passed is True


def test_skips_non_mandate_debits():
    result = post_debit_notification.check(db=None, case=None, proposed=None, context={})
    assert result.passed is True
