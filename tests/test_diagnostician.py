from app.agents.diagnostician import diagnose, DiagnosticInput, TIER1_CONFIDENCE
from app.agents.taxonomy import ROOT_CAUSES


def _input(**overrides) -> DiagnosticInput:
    defaults = dict(case_id="case_1", error_code=None, error_reason=None, error_source=None,
                     error_step=None, error_description=None, prior_failures=0)
    defaults.update(overrides)
    return DiagnosticInput(**defaults)


def test_tier1_resolves_known_error_reason_with_high_confidence():
    result = diagnose(_input(error_reason="insufficient_funds"))
    assert result.root_cause == "insufficient_funds"
    assert result.tier1_hit is True
    assert result.confidence == TIER1_CONFIDENCE


def test_tier1_resolves_every_mapped_reason_correctly():
    from app.agents.taxonomy import ERROR_REASON_TO_ROOT_CAUSE
    for reason, expected_cause in ERROR_REASON_TO_ROOT_CAUSE.items():
        result = diagnose(_input(error_reason=reason))
        assert result.root_cause == expected_cause, f"{reason} -> expected {expected_cause}, got {result.root_cause}"
        assert result.tier1_hit is True


def test_falls_through_to_tier2_on_ambiguous_reason():
    result = diagnose(_input(error_reason="card_declined"))
    assert result.tier1_hit is False


def test_falls_through_to_tier2_on_a_real_reason_with_no_clean_taxonomy_home():
    result = diagnose(_input(error_reason="incorrect_cvv"))
    assert result.tier1_hit is False


def test_falls_through_to_tier2_on_missing_reason():
    result = diagnose(_input(error_reason=None, error_description="payment declined by bank"))
    assert result.tier1_hit is False


def test_tier2_resolves_via_keyword_match_with_moderate_high_confidence():
    result = diagnose(_input(error_reason="card_declined", error_description="Card has expired"))
    assert result.root_cause == "expired_card"
    assert result.tier1_hit is False
    assert 0.80 <= result.confidence <= 0.95


def test_tier2_ambiguous_text_gets_lower_confidence_than_keyword_match():
    ambiguous = diagnose(_input(error_reason="card_declined", error_description="something unclear happened"))
    keyword_matched = diagnose(_input(error_reason="card_declined", error_description="Card has expired"))
    assert ambiguous.confidence < keyword_matched.confidence


def test_diagnosis_is_deterministic_for_the_same_input():
    inp = _input(error_reason="card_declined", error_description="unclear signal")
    r1 = diagnose(inp)
    r2 = diagnose(inp)
    assert r1.root_cause == r2.root_cause
    assert r1.confidence == r2.confidence


def test_every_diagnosis_returns_a_valid_root_cause():
    for i in range(20):
        result = diagnose(_input(case_id=f"case_{i}", error_reason="card_declined",
                                  error_description=f"unclear case {i}"))
        assert result.root_cause in ROOT_CAUSES

