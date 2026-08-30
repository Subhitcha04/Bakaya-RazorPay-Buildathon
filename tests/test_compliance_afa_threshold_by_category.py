from app.control_plane.gates.rbi import afa_threshold
from app.schemas.contracts import ProposedActionOut


def _action(amount_paise: int) -> ProposedActionOut:
    return ProposedActionOut(
        case_id="case1", ladder_level="L1", amount_paise=amount_paise,
        proposer_model="stub", trace_id="trace1",
    )


def test_blocks_above_standard_threshold_without_afa():
    proposed = _action(20_000_00)
    result = afa_threshold.check(
        db=None, case=None, proposed=proposed,
        context={"is_mandate_debit": True, "mandate_category": "other", "afa_completed": False},
    )
    assert result.passed is False


def test_allows_above_standard_threshold_with_afa():
    proposed = _action(20_000_00)
    result = afa_threshold.check(
        db=None, case=None, proposed=proposed,
        context={"is_mandate_debit": True, "mandate_category": "other", "afa_completed": True},
    )
    assert result.passed is True


def test_uses_higher_threshold_for_insurance_premium():
    proposed = _action(50_000_00)
    result = afa_threshold.check(
        db=None, case=None, proposed=proposed,
        context={"is_mandate_debit": True, "mandate_category": "insurance_premium", "afa_completed": False},
    )
    assert result.passed is True


def test_high_category_still_blocks_above_its_own_threshold():
    proposed = _action(1_50_000_00)
    result = afa_threshold.check(
        db=None, case=None, proposed=proposed,
        context={"is_mandate_debit": True, "mandate_category": "insurance_premium", "afa_completed": False},
    )
    assert result.passed is False


def test_skips_non_mandate_debits():
    proposed = _action(999_999_00)
    result = afa_threshold.check(db=None, case=None, proposed=proposed, context={})
    assert result.passed is True
