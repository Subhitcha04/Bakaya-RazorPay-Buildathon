from app.control_plane.gates.rbi import variable_mandate_cap
from app.schemas.contracts import ProposedActionOut


def _action(amount_paise: int) -> ProposedActionOut:
    return ProposedActionOut(
        case_id="case1", ladder_level="L1", amount_paise=amount_paise,
        proposer_model="stub", trace_id="trace1",
    )


def test_blocks_variable_mandate_with_no_declared_max():
    proposed = _action(5_000_00)
    result = variable_mandate_cap.check(
        db=None, case=None, proposed=proposed,
        context={"is_variable_mandate": True},
    )
    assert result.passed is False
    assert "no declared maximum" in result.reason


def test_blocks_amount_exceeding_declared_max():
    proposed = _action(10_000_00)
    result = variable_mandate_cap.check(
        db=None, case=None, proposed=proposed,
        context={"is_variable_mandate": True, "variable_mandate_max_paise": 5_000_00},
    )
    assert result.passed is False


def test_allows_amount_within_declared_max():
    proposed = _action(3_000_00)
    result = variable_mandate_cap.check(
        db=None, case=None, proposed=proposed,
        context={"is_variable_mandate": True, "variable_mandate_max_paise": 5_000_00},
    )
    assert result.passed is True


def test_skips_fixed_amount_mandates():
    proposed = _action(999_999_00)
    result = variable_mandate_cap.check(db=None, case=None, proposed=proposed, context={})
    assert result.passed is True
