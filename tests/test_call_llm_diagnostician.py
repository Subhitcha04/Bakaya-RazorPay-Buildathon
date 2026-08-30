"""
Tests for call_llm_diagnostician. THE critical invariant tested here
is the last two -- diagnose() must NEVER call this function, under any
environment configuration, ever. If that ever silently changed, every
pinned test in this repo (golden-set accuracy, calibration bands, the
red-team suite's 13/2/0 result) would become non-deterministic without
anyone noticing why until a test flaked.
"""
from __future__ import annotations

import os

from app.agents.diagnostician import call_llm_diagnostician, diagnose, DiagnosticInput, TEACHER_STUB
from app.agents.llm_client import LLMClient
from app.agents.taxonomy import ROOT_CAUSES
from tests.test_llm_client import FakeTransport, _ok_response


def _client_returning(payload: dict) -> LLMClient:
    transport = FakeTransport(responses=[_ok_response(payload)])
    return LLMClient(transport=transport, api_key="fake_key", model="openai/gpt-oss-20b")


def _input() -> DiagnosticInput:
    return DiagnosticInput(
        case_id="c1", error_code="GATEWAY_ERROR", error_reason="card_declined", error_source="issuer_bank",
        error_step="authorization", error_description="card seems expired", prior_failures=0,
    )


def test_returns_a_valid_diagnosis_for_a_well_formed_response():
    client = _client_returning({"root_cause": "expired_card", "confidence": 0.88, "rationale": "mentions expired"})
    result = call_llm_diagnostician(_input(), client)

    assert result.case_id == "c1"
    assert result.root_cause == "expired_card"
    assert result.confidence == 0.88
    assert result.tier1_hit is False
    assert result.model_id == "openai/gpt-oss-20b"
    assert result.rationale == "mentions expired"


def test_fails_closed_to_other_for_an_out_of_taxonomy_root_cause():
    client = _client_returning({"root_cause": "made_up_category", "confidence": 0.9})
    result = call_llm_diagnostician(_input(), client)
    assert result.root_cause == "other"


def test_missing_confidence_defaults_to_a_neutral_value_not_a_crash():
    client = _client_returning({"root_cause": "insufficient_funds"})
    result = call_llm_diagnostician(_input(), client)
    assert result.confidence == 0.5


def test_confidence_is_clamped_to_valid_range():
    client = _client_returning({"root_cause": "insufficient_funds", "confidence": 1.7})
    result = call_llm_diagnostician(_input(), client)
    assert result.confidence == 1.0

    client2 = _client_returning({"root_cause": "insufficient_funds", "confidence": -0.3})
    result2 = call_llm_diagnostician(_input(), client2)
    assert result2.confidence == 0.0


def test_non_numeric_confidence_falls_back_to_neutral_rather_than_crashing():
    client = _client_returning({"root_cause": "insufficient_funds", "confidence": "very sure"})
    result = call_llm_diagnostician(_input(), client)
    assert result.confidence == 0.5


def test_rationale_is_bounded_in_length():
    huge_rationale = "x" * 10_000
    client = _client_returning({"root_cause": "other", "confidence": 0.5, "rationale": huge_rationale})
    result = call_llm_diagnostician(_input(), client)
    assert len(result.rationale) <= 500


def test_missing_rationale_defaults_to_empty_string_not_none():
    client = _client_returning({"root_cause": "other", "confidence": 0.5})
    result = call_llm_diagnostician(_input(), client)
    assert result.rationale == ""


def test_every_valid_root_cause_passes_through_unchanged():
    for cause in ROOT_CAUSES:
        client = _client_returning({"root_cause": cause, "confidence": 0.7})
        result = call_llm_diagnostician(_input(), client)
        assert result.root_cause == cause


def test_error_reason_is_included_in_the_prompt_sent_to_the_model():
    transport = FakeTransport(responses=[_ok_response({"root_cause": "expired_card", "confidence": 0.8})])
    client = LLMClient(transport=transport, api_key="fake_key", model="openai/gpt-oss-20b")

    call_llm_diagnostician(_input(), client)

    assert len(transport.calls) == 1
    user_message = transport.calls[0]["user"]
    assert "error_reason: card_declined" in user_message


def test_diagnose_never_calls_the_llm_even_with_a_key_in_the_environment():
    original = os.environ.get("GROQ_API_KEY")
    try:
        os.environ["GROQ_API_KEY"] = "some_key_that_should_be_ignored"

        inp = DiagnosticInput(
            case_id="c1", error_code="GATEWAY_ERROR", error_reason="card_declined", error_source="issuer_bank",
            error_step="authorization", error_description="payment declined by bank", prior_failures=0,
        )
        via_diagnose = diagnose(inp)
        via_stub_directly = TEACHER_STUB(inp)

        assert via_diagnose.root_cause == via_stub_directly.root_cause
        assert via_diagnose.confidence == via_stub_directly.confidence
        assert via_diagnose.tier1_hit == via_stub_directly.tier1_hit
        assert via_diagnose.model_id == via_stub_directly.model_id
    finally:
        if original is None:
            os.environ.pop("GROQ_API_KEY", None)
        else:
            os.environ["GROQ_API_KEY"] = original


def test_diagnose_function_source_contains_no_reference_to_call_llm_diagnostician():
    import inspect
    from app.agents import diagnostician
    source = inspect.getsource(diagnostician.diagnose)
    assert "call_llm_diagnostician" not in source

