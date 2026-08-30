from app.control_plane.gates.rbi import afa_required


def test_afa_required_blocks_registration_without_afa():
    result = afa_required.check(
        db=None, case=None, proposed=None,
        context={"mandate_event": "registration", "afa_completed": False},
    )
    assert result.passed is False
    assert result.gate_name == "rbi_afa_required"


def test_afa_required_allows_registration_with_afa():
    result = afa_required.check(
        db=None, case=None, proposed=None,
        context={"mandate_event": "registration", "afa_completed": True},
    )
    assert result.passed is True


def test_afa_required_blocks_opt_out_without_afa():
    result = afa_required.check(
        db=None, case=None, proposed=None,
        context={"mandate_event": "opt_out", "afa_completed": False},
    )
    assert result.passed is False


def test_afa_required_skips_non_mandate_lifecycle_events():
    result = afa_required.check(db=None, case=None, proposed=None, context={})
    assert result.passed is True
