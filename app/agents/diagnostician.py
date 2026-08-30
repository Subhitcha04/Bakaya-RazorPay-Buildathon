"""
Two-tier root-cause diagnosis: a deterministic lookup (Tier 1) that
resolves the majority of cases for free, with an LLM fallback (Tier 2)
only for genuinely ambiguous cases. This is the concrete implementation
of the cost-cascade principle from the production engineering addendum:
"don't call the LLM at all" is the biggest single cost lever, and it is
the DEFAULT path here, not an afterthought.

Tier 2 is a pluggable interface, not hardcoded to a live API call --
see call_llm_diagnostician() for the real, provider-agnostic implementation
(Groq by default via llm_client.py) and TEACHER_STUB for what runs in
an environment without live credentials, same pattern proven in
distillation-demo/teacher.py. diagnose() always calls TEACHER_STUB --
switching to call_llm_diagnostician is a deliberate, explicit choice
made by scripts/compare_llm_diagnosis.py, never automatic just because
an API key exists in the environment; nothing downstream needs to know
which one ran -- only that `tier1_hit` records which one DID run,
on every single diagnosis, permanently.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.schemas.contracts import DiagnosisOut
from .taxonomy import ROOT_CAUSES, ERROR_REASON_TO_ROOT_CAUSE, AMBIGUOUS_REASONS

TIER1_CONFIDENCE = 0.97   # deterministic lookup -- near-certain by construction, not measured
MODEL_ID_TIER1 = "rule_table_v1"
MODEL_ID_TIER2_STUB = "diagnostician_stub_v1"   # what diagnose() actually calls; see call_llm_diagnostician for the real path


@dataclass(frozen=True)
class DiagnosticInput:
    """
    Field names match Razorpay's real Payment entity, confirmed against
    their own docs (webhooks/payments/ and api/payments/entity/): a
    real payment.failed webhook payload carries error_code, error_reason,
    error_source, error_step, and error_description as flat sibling
    fields. error_code is a coarse bucket (BAD_REQUEST_ERROR /
    GATEWAY_ERROR / SERVER_ERROR); error_reason is the specific slug
    Tier 1 actually classifies on (see taxonomy.py).
    """
    case_id: str
    error_code: str | None
    error_reason: str | None = None
    error_source: str | None = None
    error_step: str | None = None
    error_description: str | None = None
    prior_failures: int = 0


def diagnose(inp: DiagnosticInput) -> DiagnosisOut:
    """The single entry point. Callers never need to know whether Tier 1
    or Tier 2 resolved a given case -- tier1_hit records that,
    permanently, on the Diagnosis row this produces."""
    tier1 = _tier1_lookup(inp)
    if tier1 is not None:
        return tier1
    return _tier2_classify(inp)


def _tier1_lookup(inp: DiagnosticInput) -> DiagnosisOut | None:
    if inp.error_reason in AMBIGUOUS_REASONS:
        return None
    root_cause = ERROR_REASON_TO_ROOT_CAUSE.get(inp.error_reason)
    if root_cause is None:
        return None   # unmapped reason -- fall through to Tier 2 rather than guessing
    return DiagnosisOut(
        case_id=inp.case_id, root_cause=root_cause, confidence=TIER1_CONFIDENCE,
        model_id=MODEL_ID_TIER1, tier1_hit=True,
        rationale=f"deterministic lookup: error_reason={inp.error_reason!r}",
    )


def _tier2_classify(inp: DiagnosticInput) -> DiagnosisOut:
    return TEACHER_STUB(inp)


# ---------------------------------------------------------------------
# REAL IMPLEMENTATION -- genuinely wired to a live LLM, not a sketch.
# Provider-agnostic via llm_client.LLMClient (Groq by default, any
# OpenAI-schema-compatible endpoint by swapping base_url/model).
#
# DELIBERATELY NEVER CALLED BY diagnose() ABOVE. Setting GROQ_API_KEY
# in your environment does NOT change diagnose()'s behavior -- it
# always calls TEACHER_STUB. This is what keeps every pinned test in
# this repo (golden-set accuracy, calibration bands, the red-team
# suite's 13/2/0 result, replay/capability tests) deterministic and
# reproducible on a clean clone regardless of whether a key is
# present. This function is invoked EXPLICITLY, by
# scripts/compare_llm_diagnosis.py, which is the honest way to measure
# it against the stub before anyone decides to switch the default over.
#
# NO LIVE NETWORK CALL HAS EVER BEEN MADE FROM THIS FUNCTION IN THIS
# BUILD ENVIRONMENT -- see llm_client.py's docstring. Tested against a
# fake transport (tests/test_llm_client.py, tests/test_call_llm_
# diagnostician.py); smoke-test for real on your own machine.
# ---------------------------------------------------------------------
def call_llm_diagnostician(inp: DiagnosticInput, client) -> DiagnosisOut:
    """
    `client` is an llm_client.LLMClient instance -- required, not
    defaulted, so a caller can never accidentally invoke this without
    consciously constructing (and therefore thinking about) which
    transport and model it's about to spend real money calling.
    """
    system = (
        "You are a payment failure root-cause classifier. "
        f"Classify into exactly one of: {list(ROOT_CAUSES)}.\n\n"
        "You are being asked to classify this case SPECIFICALLY because Tier 1 already "
        "checked its error_reason and found it not decisive enough to classify "
        "automatically -- that check already happened before this call. Use error_reason "
        "as context (it IS real signal here, e.g. distinguishing 'card_declined' from "
        "'authentication_failed'), but base your final judgment primarily on "
        "error_description, which carries the most specific information available.\n\n"
        "Guidance per category -- follow this over any general instinct:\n"
        "- insufficient_funds: mentions balance, funds, or amount available\n"
        "- expired_card: mentions the card being expired or expiry\n"
        "- issuer_risk_decline: describes a risk-based decline with NO more specific reason "
        "given anywhere in the description\n"
        "- gateway_timeout: mentions timeout, no response, a technical or processing error, "
        "or advice to 'try again'\n"
        "- mandate_lapsed: mentions a mandate, auto-payment, or recurring-payment setup issue\n"
        "- fraud_flag: mentions fraud, suspicious activity, or a risk-based block\n"
        "- customer_intent: describes the CUSTOMER abandoning, leaving, or not completing "
        "checkout themselves -- not a payment failure at all\n"
        "- other: the description gives NO SPECIFIC signal whatsoever -- generic phrases like "
        "'payment could not be completed', 'an error occurred', 'unknown error', "
        "'processing failed for unspecified reason', with no indication of WHY. "
        "For text this generic, 'other' is the CORRECT and HONEST answer, not a fallback to "
        "avoid. Do not invent a specific-sounding category when the text gives you nothing to "
        "go on -- a confident wrong guess is worse than an honest 'other'.\n\n"
        'Return ONLY a JSON object: {"root_cause": "...", "confidence": 0.0-1.0, "rationale": "..."}. '
        "No other text."
    )
    # error_code (the COARSE bucket) is DELIBERATELY EXCLUDED -- it's
    # too generic to help (BAD_REQUEST_ERROR/GATEWAY_ERROR/SERVER_ERROR
    # says almost nothing about root cause) and a PRIOR version of this
    # prompt included a fake composite code that caused a real,
    # confirmed bug: the model anchored on a literal substring in an
    # invented code ("issuer_declined") instead of reasoning from the
    # description. error_reason is different -- it's Razorpay's real,
    # specific field, and by construction only ambiguous-but-real
    # values ever reach this function (Tier 1 already resolved
    # anything unambiguous), so it's legitimate extra signal, not noise.
    user = (
        f"error_reason: {inp.error_reason}\n"
        f"error_description: {inp.error_description}\n"
        f"error_source: {inp.error_source}\n"
        f"prior_failures: {inp.prior_failures}"
    )

    result = client.complete_json(system, user)

    root_cause = result.get("root_cause")
    if root_cause not in ROOT_CAUSES:
        # Fails CLOSED to the catch-all bucket rather than crashing or
        # trusting an out-of-taxonomy label the model invented -- same
        # "never trust the model's stated authorization" principle
        # that governs the control plane, applied here to classification.
        root_cause = "other"

    try:
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5

    return DiagnosisOut(
        case_id=inp.case_id, root_cause=root_cause, confidence=confidence,
        model_id=client.model, tier1_hit=False,
        rationale=str(result.get("rationale", ""))[:500],   # bounded -- never let a model runaway into a huge field
    )


# ---------------------------------------------------------------------
# STUB used without live credentials. Fully DETERMINISTIC given
# case_id (no global random state) -- keyword-matches error_description
# the same way distillation-demo's TEACHER_STUB does, with lower
# confidence on genuinely ambiguous cases, so downstream
# confidence-gating tests behave the way they would against a real,
# imperfectly-calibrated classifier. Intentionally does NOT read
# error_reason -- it's a keyword-only stub by design, matching the
# "cheap classifier that only sees free text" framing established
# from the start of this project.
# ---------------------------------------------------------------------
_KEYWORD_HINTS = {
    "balance": "insufficient_funds",
    "expir": "expired_card",
    "timeout": "gateway_timeout",
    "mandate": "mandate_lapsed",
    "fraud": "fraud_flag",
    "suspicious": "fraud_flag",
    "abandon": "customer_intent",
    "did not complete": "customer_intent",
    "closed checkout": "customer_intent",
}


def TEACHER_STUB(inp: DiagnosticInput) -> DiagnosisOut:
    text = (inp.error_description or "").lower()
    for kw, cause in _KEYWORD_HINTS.items():
        if kw in text:
            confidence = _deterministic_confidence(inp.case_id, low=0.80, high=0.95)
            return DiagnosisOut(
                case_id=inp.case_id, root_cause=cause, confidence=confidence,
                model_id=MODEL_ID_TIER2_STUB, tier1_hit=False,
                rationale=f"keyword match on {kw!r} in error_description",
            )

    # Genuinely ambiguous -- no strong signal. Best-guess distribution,
    # deliberately imperfect and lower-confidence, so this behaves like
    # a real classifier that knows what it doesn't know, not an oracle.
    plausible = ["issuer_risk_decline", "fraud_flag", "other", "insufficient_funds"]
    weights = [0.55, 0.15, 0.10, 0.20]
    cause = _deterministic_choice(inp.case_id, plausible, weights)
    confidence = _deterministic_confidence(inp.case_id, low=0.45, high=0.70)
    return DiagnosisOut(
        case_id=inp.case_id, root_cause=cause, confidence=confidence,
        model_id=MODEL_ID_TIER2_STUB, tier1_hit=False,
        rationale="ambiguous signal -- best-guess classification, low confidence",
    )


def _deterministic_confidence(case_id: str, low: float, high: float) -> float:
    digest = hashlib.sha256(f"{case_id}|confidence".encode()).digest()
    frac = int.from_bytes(digest[:8], "big") / 2**64
    return round(low + frac * (high - low), 2)


def _deterministic_choice(case_id: str, options: list[str], weights: list[float]) -> str:
    digest = hashlib.sha256(f"{case_id}|choice".encode()).digest()
    frac = int.from_bytes(digest[:8], "big") / 2**64
    cumulative = 0.0
    for opt, w in zip(options, weights):
        cumulative += w
        if frac < cumulative:
            return opt
    return options[-1]

