"""
Minimal, provider-agnostic OpenAI-schema-compatible chat client, built
for the ONE genuine language task in this codebase: Tier-2 diagnosis
of ambiguous failure text (see agents/diagnostician.py::
call_llm_diagnostician). Groq is OpenAI-schema-compatible at
api.groq.com/openai/v1, so this needs no vendor-specific SDK -- only
base_url and api_key change to point at a different provider, matching
the "one env var to swap" pattern used by real recovery systems in
this space.

NO LIVE NETWORK ACCESS IS AVAILABLE IN THIS BUILD ENVIRONMENT --
api.groq.com is not in the sandbox's egress allowlist, same limitation
as execution/razorpay_client.py. Everything here is tested against a
fake transport (tests/test_llm_client.py) that proves the CLIENT LOGIC
is correct -- not that it has ever actually talked to Groq. Smoke-test
for real on your own machine once GROQ_API_KEY is set; see the real
transport sketch at the bottom of this file.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"


class LLMClientError(Exception):
    pass


@dataclass(frozen=True)
class ChatResponse:
    status_code: int
    json_body: dict[str, Any]


class LLMTransport(Protocol):
    def chat_completion(
        self, base_url: str, api_key: str, model: str,
        system: str, user: str, response_format_json: bool,
    ) -> ChatResponse: ...


_UNSET = object()   # sentinel distinct from None -- see class docstring


class LLMClient:
    """
    api_key defaults to _UNSET, not None -- this matters. If a caller
    doesn't pass api_key at all, we read GROQ_API_KEY from the
    environment (the normal path). If a caller explicitly passes
    api_key=None, that means "simulate having no key," and must NOT
    silently fall back to a real environment variable that happens to
    be set -- e.g. in a test suite run on a machine where GROQ_API_KEY
    is genuinely configured for other purposes. Using None as the
    "unspecified" sentinel made those two cases indistinguishable and
    caused a real test failure the first time this ran somewhere with
    a live key in the environment; this sentinel fixes that class of bug.
    """
    def __init__(
        self, transport: LLMTransport, base_url: str = DEFAULT_BASE_URL,
        api_key=_UNSET, model: str | None = None,
    ):
        self.transport = transport
        self.base_url = base_url
        self.api_key = os.getenv("GROQ_API_KEY") if api_key is _UNSET else api_key
        self.model = model or os.getenv("LLM_MODEL", DEFAULT_MODEL)

    def complete_json(self, system: str, user: str) -> dict:
        if not self.api_key:
            raise LLMClientError("no API key configured -- set GROQ_API_KEY")

        resp = self.transport.chat_completion(
            base_url=self.base_url, api_key=self.api_key, model=self.model,
            system=system, user=user, response_format_json=True,
        )
        if resp.status_code >= 400:
            raise LLMClientError(f"LLM API error {resp.status_code}: {resp.json_body}")

        try:
            content = resp.json_body["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError) as e:
            raise LLMClientError(f"unexpected response shape: {e}") from None
        except json.JSONDecodeError as e:
            raise LLMClientError(f"model did not return valid JSON: {e}") from None


# ---------------------------------------------------------------------
# REAL TRANSPORT -- not used in this environment (no network egress to
# api.groq.com and no live key here). Wire this in on your machine:
#
#   pip install openai
#
#   from openai import OpenAI
#   from app.agents.llm_client import ChatResponse
#
#   class OpenAICompatibleTransport:
#       def chat_completion(self, base_url, api_key, model, system, user, response_format_json):
#           client = OpenAI(base_url=base_url, api_key=api_key)
#           resp = client.chat.completions.create(
#               model=model,
#               messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
#               response_format={"type": "json_object"} if response_format_json else None,
#           )
#           return ChatResponse(status_code=200, json_body=resp.model_dump())
#
#   client = LLMClient(transport=OpenAICompatibleTransport())
# ---------------------------------------------------------------------
