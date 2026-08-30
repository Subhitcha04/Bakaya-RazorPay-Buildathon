"""
Variable-amount mandates must carry a declared maximum transaction
limit. Blocks any proposal that would exceed the customer-agreed cap,
regardless of what the merchant's system computed the "true" amount to
be -- the mandate's own declared ceiling is the authority here, same
principle as the general offer_ceiling gate applied to mandate law
specifically.

TODO: verify clause number against the primary circular before shipping.
"""
from __future__ import annotations

from ..base import GateResult

NAME = "rbi_variable_mandate_cap"


def check(db, case, proposed, context: dict) -> GateResult:
    if not context.get("is_variable_mandate", False):
        return GateResult(True, NAME, evidence={"reason": "fixed-amount mandate"})

    declared_max = context.get("variable_mandate_max_paise")
    if declared_max is None:
        return GateResult(False, NAME, reason="variable mandate has no declared maximum limit on file")
    if proposed.amount_paise > declared_max:
        return GateResult(False, NAME, reason="amount exceeds declared variable mandate maximum",
                           evidence={"amount_paise": proposed.amount_paise, "declared_max_paise": declared_max})
    return GateResult(True, NAME, evidence={"declared_max_paise": declared_max})
