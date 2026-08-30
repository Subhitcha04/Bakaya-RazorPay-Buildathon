"""
The fixed root-cause label space. MUST stay in sync with:
  - RootCause Literal in schemas/contracts.py
  - ROOT_CAUSE_TO_ENTRY_LEVEL in ladder/levels.py
  - ROOT_CAUSE_WEIGHTS in sim/reality_generator.py (a simulator prior, not a dependency)
tests/test_taxonomy_consistency.py asserts the first two of these stay
identical, so drift fails CI rather than surfacing as a silent runtime
KeyError months later.
"""
from __future__ import annotations

ROOT_CAUSES = [
    "insufficient_funds", "expired_card", "issuer_risk_decline",
    "gateway_timeout", "mandate_lapsed", "fraud_flag",
    "customer_intent", "other",
]

# Tier 1: deterministic lookup keyed on Razorpay's REAL `error_reason`
# field -- a flat field on the Payment entity in webhook payloads, and
# the `reason` field in the standalone API error response shape:
#   {"error": {"code": "BAD_REQUEST_ERROR", "description": "...",
#              "source": "customer", "step": "payment_authentication",
#              "reason": "invalid_otp", "metadata": {...}}}
# Confirmed against Razorpay's own docs (not invented):
#   https://razorpay.com/docs/errors/            (error structure)
#   https://razorpay.com/docs/api/payments/entity/ (Payment entity fields)
#   https://razorpay.com/docs/webhooks/payments/   (sample webhook payloads)
#
# error_reason is distinct from error_code: on the real entity,
# error_code is a coarse bucket (BAD_REQUEST_ERROR / GATEWAY_ERROR /
# SERVER_ERROR) -- too coarse to classify from alone. error_reason is
# the specific slug and is what Tier 1 actually keys on.
#
# Values below are Razorpay's own documented reason slugs, sourced
# from the full Bad Request Errors and Gateway Errors tables at
#   https://razorpay.com/docs/errors/payments/list/
# and the Cards/UPI-specific pages:
#   https://razorpay.com/docs/errors/payments/cards/
#   https://razorpay.com/docs/errors/payments/upi/
# not invented. A prior version of this file used composite strings
# like "GATEWAY_ERROR:issuer_declined" that didn't correspond to
# anything Razorpay actually sends, and caused a real, confirmed bug
# in the LLM diagnostician (see agents/diagnostician.py's
# call_llm_diagnostician docstring). An even earlier version of THIS
# real-data pass used "mandate_cancelled_by_customer" for mandate_
# lapsed, sourced from a secondary (Chargebee) doc rather than
# Razorpay's own authoritative reason list -- that value doesn't
# actually appear in Razorpay's real list and was replaced below with
# the reasons that do.
ERROR_REASON_TO_ROOT_CAUSE: dict[str, str] = {
    "insufficient_funds": "insufficient_funds",
    "card_expired": "expired_card",
    "payment_risk_check_failed": "fraud_flag",       # "bank declined ... citing it as fraudulent"
    "payment_amount_tampered": "fraud_flag",          # integrity/tampering -- a security concern, not a guess
    "payment_cancelled": "customer_intent",           # "customer explicitly cancelled the payment"
    "debit_instrument_blocked": "issuer_risk_decline",  # "blocked by customer or bank," no more specific reason given
    # The whole "transient, not the customer's fault, safe to retry"
    # family -- 14 distinct real reasons, all describing the same
    # semantic class (gateway/bank/PSP downtime, timeout, or overload):
    "payment_timed_out": "gateway_timeout",
    "payment_collect_request_expired": "gateway_timeout",
    "payment_session_expired": "gateway_timeout",
    "payment_declined_due_to_high_traffic": "gateway_timeout",
    "bank_technical_error": "gateway_timeout",
    "gateway_technical_error": "gateway_timeout",
    "issuer_technical_error": "gateway_timeout",
    "bank_not_available": "gateway_timeout",
    "bank_cutoff_in_progress": "gateway_timeout",
    "invalid_response_from_gateway": "gateway_timeout",
    "psp_app_not_available": "gateway_timeout",
    "psp_not_available": "gateway_timeout",
    "request_timed_out": "gateway_timeout",
    "server_error": "gateway_timeout",
    # Real mandate-specific reasons -- mandate creation/reauth failing
    # is functionally equivalent to a lapsed mandate for recovery
    # purposes (recurring payment cannot proceed without a working one):
    "mandate_creation_declined": "mandate_lapsed",
    "mandate_creation_expired": "mandate_lapsed",
    "mandate_creation_failed": "mandate_lapsed",
    "mandate_creation_timeout": "mandate_lapsed",
    "reqauth_mandate_not_acknowledged": "mandate_lapsed",
}

# Reasons Tier 1 CANNOT resolve confidently. Two genuinely different
# kinds of entry here, both real, both stated honestly rather than
# glossed over:
#
# (a) Razorpay's OWN docs describe these as non-specific by nature --
#     e.g. card_declined: "Razorpay may not have access to specific
#     details regarding the failure reason" (their words). Falling
#     through to Tier 2 here matches what Razorpay itself says it can
#     tell you, not a gap in our taxonomy.
#
# (b) Real, documented reasons that don't map cleanly onto any of our
#     8 root causes at all -- an honest, acknowledged coverage gap,
#     not silently forced into the nearest bucket. Doing that would
#     produce actively misleading customer messaging -- e.g. telling
#     someone to try a different card when the real issue is their
#     card isn't enabled for online payments at all, or a customer
#     data-entry mistake (wrong CVV/OTP/PIN) that needs "re-enter your
#     details," not any message our 8 categories currently produce.
#     This list is a representative sample of real (b)-category
#     reasons for testing, not an exhaustive enumeration of Razorpay's
#     full ~90-reason vocabulary -- many of the remainder (invalid_
#     amount, order_already_paid, live_mode_not_enabled, etc.) are
#     integration/business-config errors, not customer payment-failure
#     causes, and are out of scope for this taxonomy entirely; they
#     fall through to Tier 2 automatically via ERROR_REASON_TO_ROOT_
#     CAUSE.get() returning None for anything unlisted, without
#     needing an explicit entry here. See HONEST_LIMITATIONS.md.
AMBIGUOUS_REASONS: set[str | None] = {
    # (a) genuinely non-specific per Razorpay's own documentation
    "card_declined", "payment_failed", "payment_declined", "authentication_failed",
    # (b) real, but no clean home in our 8 categories -- representative sample
    "card_not_enrolled", "card_disabled_for_online_payments", "debit_instrument_inactive",
    "incorrect_cvv", "incorrect_otp", "incorrect_pin", "otp_attempts_exceeded",
    "transaction_limit_exceeded", "invalid_vpa", "vpa_resolution_failed", "credit_failed",
    "user_not_eligible", "bank_account_invalid",
    None,   # no error_reason at all -- e.g. checkout abandonment, no decline occurred
}
