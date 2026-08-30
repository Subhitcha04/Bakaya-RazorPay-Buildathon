"""
Drafts the customer-facing message for a ladder action. Template-based
here, not a live LLM call -- same pluggable-stub pattern as the other
two agents.

Two hard constraints baked into EVERY template regardless of which one
fires: (1) always include a grievance/contact reference, so
rbi_redressal_in_templates passes by construction rather than by luck;
(2) tone is helpful-nudge, never urgency/pressure language. Point (2)
is enforced by template design here, not verified by a classifier --
the dark-pattern classifier is a Day 10 item; until it exists, treat
every template as reviewed-by-eye, not machine-verified, and say so in
HONEST_LIMITATIONS.md.
"""
from __future__ import annotations

REDRESSAL_LINE = "Need help? Contact us at support@{merchant_domain} anytime."

TEMPLATES: dict[tuple[str, str], str] = {
    ("payment_failure", "L3"): (
        "Hi, your recent payment of Rs {amount} didn't go through. "
        "No rush -- you can complete it anytime here: {payment_link}. " + REDRESSAL_LINE
    ),
    ("payment_failure", "L4"): (
        "Hi, we noticed your payment of Rs {amount} didn't go through. "
        "As a one-time courtesy we've added a small credit to make this easier: {payment_link}. " + REDRESSAL_LINE
    ),
    ("mandate_failure", "L3"): (
        "Your recurring payment of Rs {amount} needs a quick re-authorization: {payment_link}. " + REDRESSAL_LINE
    ),
    ("receivable", "L3"): (
        "This is a reminder that invoice {invoice_ref} for Rs {amount} is now overdue. "
        "You can settle it here: {payment_link}. " + REDRESSAL_LINE
    ),
    ("receivable", "L5"): (
        "Our team will be in touch shortly about invoice {invoice_ref} for Rs {amount}. " + REDRESSAL_LINE
    ),
}

DEFAULT_TEMPLATE = "We wanted to follow up on your recent transaction of Rs {amount}. " + REDRESSAL_LINE


def compose(
    surface: str, ladder_level: str, amount_paise: int,
    merchant_domain: str = "merchant.test",
    payment_link: str = "https://pay.example/x",
    invoice_ref: str = "",
) -> str:
    template = TEMPLATES.get((surface, ladder_level), DEFAULT_TEMPLATE)
    amount_rupees = amount_paise / 100
    return template.format(
        amount=f"{amount_rupees:,.2f}", payment_link=payment_link,
        merchant_domain=merchant_domain, invoice_ref=invoice_ref,
    )
