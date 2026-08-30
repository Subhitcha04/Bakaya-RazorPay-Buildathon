from app.agents.composer import compose, TEMPLATES, DEFAULT_TEMPLATE
from app.control_plane.gates.rbi.redressal_in_templates import check as redressal_check
from app.schemas.contracts import ProposedActionOut


def test_compose_fills_in_amount_correctly():
    text = compose("payment_failure", "L3", amount_paise=49900)
    assert "499.00" in text


def test_compose_falls_back_to_default_for_unknown_combination():
    text = compose("some_unmapped_surface", "L9", amount_paise=1000)
    assert text.startswith("We wanted to follow up")


def test_every_declared_template_passes_the_rbi_redressal_gate():
    """
    Integration test, not a unit test: proves Composer's actual output
    satisfies the RBI gate that will independently check it later,
    rather than trusting the two files to agree by inspection. If
    someone edits a template and drops the redressal line, this test
    -- not a human reviewer -- catches it.
    """
    for (surface, level) in TEMPLATES.keys():
        text = compose(surface, level, amount_paise=10_000, invoice_ref="INV-1")
        proposed = ProposedActionOut(
            case_id="c1", ladder_level=level, amount_paise=0,
            proposer_model="composer", trace_id="t1", copy_text=text,
        )
        result = redressal_check(db=None, case=None, proposed=proposed, context={})
        assert result.passed, f"{surface}/{level} template fails the redressal gate: {text!r}"


def test_default_template_also_passes_the_redressal_gate():
    text = compose("unmapped", "L9", amount_paise=1000)
    proposed = ProposedActionOut(
        case_id="c1", ladder_level="L3", amount_paise=0,
        proposer_model="composer", trace_id="t1", copy_text=text,
    )
    result = redressal_check(db=None, case=None, proposed=proposed, context={})
    assert result.passed


def test_no_template_contains_urgency_pressure_language():
    banned_phrases = ["act now", "last chance", "final warning", "immediately or",
                       "urgent action required", "your account will be"]
    all_templates = list(TEMPLATES.values()) + [DEFAULT_TEMPLATE]
    for template in all_templates:
        lowered = template.lower()
        for phrase in banned_phrases:
            assert phrase not in lowered, f"template contains pressure language {phrase!r}: {template!r}"
