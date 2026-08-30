from app.agents.critic import (
    critique_structure_and_confidence, critique_offer_proportionality,
    review_with_one_revision, MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT,
)
from app.schemas.contracts import ProposedActionOut


def _action(**overrides) -> ProposedActionOut:
    defaults = dict(case_id="c1", ladder_level="L3", channel="email", offer_tier=None,
                     amount_paise=0, copy_text="Hi, please pay. Contact us at support@x.test.",
                     proposer_model="strategist", trace_id="t1")
    defaults.update(overrides)
    return ProposedActionOut(**defaults)


def test_rejects_channel_set_with_no_copy():
    result = critique_structure_and_confidence(_action(copy_text=None), diagnosis_confidence=0.9)
    assert result.approved is False
    assert "no copy_text" in result.reason


def test_rejects_copy_drafted_with_no_channel():
    result = critique_structure_and_confidence(
        _action(channel=None, ladder_level="L1"), diagnosis_confidence=0.9,
    )
    assert result.approved is False
    assert "no channel" in result.reason


def test_rejects_customer_contact_below_confidence_floor():
    result = critique_structure_and_confidence(
        _action(ladder_level="L3"), diagnosis_confidence=MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT - 0.01,
    )
    assert result.approved is False
    assert "too low" in result.reason


def test_allows_customer_contact_at_confidence_floor_exactly():
    result = critique_structure_and_confidence(
        _action(ladder_level="L3"), diagnosis_confidence=MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT,
    )
    assert result.approved is True


def test_low_confidence_is_fine_for_silent_levels():
    result = critique_structure_and_confidence(
        _action(ladder_level="L1", channel=None, copy_text=None), diagnosis_confidence=0.1,
    )
    assert result.approved is True


def test_rejects_offer_larger_than_the_case_amount():
    result = critique_offer_proportionality(_action(amount_paise=10_000), case_amount_paise=5_000)
    assert result.approved is False
    assert "disproportionate" in result.reason


def test_allows_offer_equal_to_case_amount():
    result = critique_offer_proportionality(_action(amount_paise=5_000), case_amount_paise=5_000)
    assert result.approved is True


def test_review_skips_revision_when_first_proposal_passes():
    calls = []

    def revise():
        calls.append(1)
        return _action()

    final, result, n_revisions = review_with_one_revision(
        _action(), diagnosis_confidence=0.9, case_amount_paise=999_999, revise_fn=revise,
    )
    assert result.approved is True
    assert n_revisions == 0
    assert calls == []


def test_review_revises_exactly_once_when_first_proposal_fails():
    calls = []

    def revise():
        calls.append(1)
        return _action(copy_text="Fixed copy with contact us at support@x.test.")

    bad = _action(copy_text=None)
    final, result, n_revisions = review_with_one_revision(
        bad, diagnosis_confidence=0.9, case_amount_paise=999_999, revise_fn=revise,
    )
    assert n_revisions == 1
    assert len(calls) == 1


def test_review_never_exceeds_one_revision_even_if_the_revision_also_fails():
    calls = []

    def revise():
        calls.append(1)
        return _action(copy_text=None)

    bad = _action(copy_text=None)
    final, result, n_revisions = review_with_one_revision(
        bad, diagnosis_confidence=0.9, case_amount_paise=999_999, revise_fn=revise,
    )
    assert n_revisions == 1
    assert len(calls) == 1
    assert result.approved is False
