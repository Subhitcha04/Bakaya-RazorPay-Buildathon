from dataclasses import dataclass, field

import pytest

from app.agents.llm_client import LLMClient, LLMClientError, ChatResponse


@dataclass
class FakeTransport:
    responses: list[ChatResponse]
    calls: list[dict] = field(default_factory=list)
    _idx: int = 0

    def chat_completion(self, base_url, api_key, model, system, user, response_format_json):
        self.calls.append({
            "base_url": base_url, "api_key": api_key, "model": model,
            "system": system, "user": user, "response_format_json": response_format_json,
        })
        resp = self.responses[self._idx]
        self._idx += 1
        return resp


def _ok_response(payload: dict) -> ChatResponse:
    import json
    return ChatResponse(status_code=200, json_body={
        "choices": [{"message": {"content": json.dumps(payload)}}],
    })


def test_complete_json_parses_the_model_response_correctly():
    transport = FakeTransport(responses=[_ok_response({"root_cause": "expired_card", "confidence": 0.9})])
    client = LLMClient(transport=transport, api_key="fake_key")

    result = client.complete_json(system="classify this", user="card expired")
    assert result == {"root_cause": "expired_card", "confidence": 0.9}


def test_complete_json_sends_the_correct_request_fields():
    transport = FakeTransport(responses=[_ok_response({"root_cause": "other", "confidence": 0.5})])
    client = LLMClient(transport=transport, api_key="fake_key", model="openai/gpt-oss-20b")

    client.complete_json(system="SYS", user="USR")
    call = transport.calls[0]
    assert call["api_key"] == "fake_key"
    assert call["model"] == "openai/gpt-oss-20b"
    assert call["system"] == "SYS"
    assert call["user"] == "USR"
    assert call["response_format_json"] is True


def test_missing_api_key_raises_without_calling_the_transport():
    transport = FakeTransport(responses=[])
    client = LLMClient(transport=transport, api_key=None)

    with pytest.raises(LLMClientError, match="no API key"):
        client.complete_json("s", "u")
    assert transport.calls == []


def test_non_2xx_status_raises_llm_client_error():
    transport = FakeTransport(responses=[
        ChatResponse(status_code=401, json_body={"error": "invalid api key"}),
    ])
    client = LLMClient(transport=transport, api_key="bad_key")

    with pytest.raises(LLMClientError, match="401"):
        client.complete_json("s", "u")


def test_malformed_json_content_raises_llm_client_error():
    transport = FakeTransport(responses=[
        ChatResponse(status_code=200, json_body={"choices": [{"message": {"content": "not json at all"}}]}),
    ])
    client = LLMClient(transport=transport, api_key="fake_key")

    with pytest.raises(LLMClientError, match="valid JSON"):
        client.complete_json("s", "u")


def test_unexpected_response_shape_raises_llm_client_error():
    transport = FakeTransport(responses=[ChatResponse(status_code=200, json_body={"unexpected": "shape"})])
    client = LLMClient(transport=transport, api_key="fake_key")

    with pytest.raises(LLMClientError, match="unexpected response shape"):
        client.complete_json("s", "u")


def test_default_model_is_gpt_oss_20b_when_not_specified():
    transport = FakeTransport(responses=[_ok_response({"root_cause": "other", "confidence": 0.5})])
    client = LLMClient(transport=transport, api_key="fake_key")
    assert client.model == "openai/gpt-oss-20b"


def test_explicit_none_api_key_means_no_key_even_when_environment_has_one():
    """
    Regression pin for a real bug: LLMClient used to treat api_key=None
    as "not specified, fall back to the environment" -- which meant an
    explicit "simulate no key" test could silently pick up a real key
    if GROQ_API_KEY happened to be set in the environment (e.g. a
    developer's shell where it's genuinely configured). A caller
    explicitly passing None must always mean no key, full stop,
    regardless of what's in the environment.
    """
    import os
    original = os.environ.get("GROQ_API_KEY")
    try:
        os.environ["GROQ_API_KEY"] = "a_real_key_that_must_be_ignored"
        transport = FakeTransport(responses=[])
        client = LLMClient(transport=transport, api_key=None)
        assert client.api_key is None
        with pytest.raises(LLMClientError, match="no API key"):
            client.complete_json("s", "u")
        assert transport.calls == []
    finally:
        if original is None:
            os.environ.pop("GROQ_API_KEY", None)
        else:
            os.environ["GROQ_API_KEY"] = original


def test_omitting_api_key_entirely_reads_from_the_environment():
    import os
    original = os.environ.get("GROQ_API_KEY")
    try:
        os.environ["GROQ_API_KEY"] = "picked_up_from_env"
        transport = FakeTransport(responses=[_ok_response({"root_cause": "other", "confidence": 0.5})])
        client = LLMClient(transport=transport)   # api_key not passed at all
        assert client.api_key == "picked_up_from_env"
    finally:
        if original is None:
            os.environ.pop("GROQ_API_KEY", None)
        else:
            os.environ["GROQ_API_KEY"] = original


def test_explicit_model_overrides_the_default():
    transport = FakeTransport(responses=[_ok_response({"root_cause": "other", "confidence": 0.5})])
    client = LLMClient(transport=transport, api_key="fake_key", model="openai/gpt-oss-120b")
    assert client.model == "openai/gpt-oss-120b"
