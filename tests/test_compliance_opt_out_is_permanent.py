from app.control_plane.gates.rbi import opt_out_honour


def test_blocks_when_customer_opted_out_of_this_transaction():
    result = opt_out_honour.check(
        db=None, case=None, proposed=None,
        context={"customer_opted_out_of_this_transaction": True},
    )
    assert result.passed is False


def test_allows_when_no_opt_out_signal():
    result = opt_out_honour.check(db=None, case=None, proposed=None, context={})
    assert result.passed is True
