from app.control_plane.gates.rbi import no_mandate_fee


def test_blocks_when_a_mandate_facility_fee_is_charged():
    result = no_mandate_fee.check(
        db=None, case=None, proposed=None,
        context={"mandate_facility_fee_paise": 500},
    )
    assert result.passed is False


def test_allows_when_no_facility_fee():
    result = no_mandate_fee.check(db=None, case=None, proposed=None, context={})
    assert result.passed is True
