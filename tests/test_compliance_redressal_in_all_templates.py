from app.control_plane.gates.rbi import redressal_in_templates
from app.schemas.contracts import ProposedActionOut


def _action(copy_text):
    return ProposedActionOut(
        case_id="case1", ladder_level="L3", amount_paise=1000,
        proposer_model="stub", trace_id="trace1", copy_text=copy_text,
    )


def test_blocks_template_missing_redressal_reference():
    proposed = _action("Your payment didn't go through, please retry.")
    result = redressal_in_templates.check(db=None, case=None, proposed=proposed, context={})
    assert result.passed is False


def test_allows_template_with_redressal_reference():
    proposed = _action("Your payment didn't go through. For help, contact us at support@merchant.test.")
    result = redressal_in_templates.check(db=None, case=None, proposed=proposed, context={})
    assert result.passed is True


def test_allows_actions_with_no_customer_facing_copy():
    proposed = _action(None)
    result = redressal_in_templates.check(db=None, case=None, proposed=proposed, context={})
    assert result.passed is True
