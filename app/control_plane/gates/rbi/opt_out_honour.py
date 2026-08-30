"""
Customer must be able to opt out of a SPECIFIC transaction, distinct
from opting out of the mandate/relationship entirely. This gate checks
the per-transaction signal. The permanent, mandate-level opt-out is
enforced separately by the Suppression DB UNIQUE constraint plus
gates/suppression.py -- two different scopes of "no," both real and
both enforced.

TODO: verify clause number against the primary circular before shipping.
"""
from __future__ import annotations

from ..base import GateResult

NAME = "rbi_opt_out_honour"


def check(db, case, proposed, context: dict) -> GateResult:
    if context.get("customer_opted_out_of_this_transaction", False):
        return GateResult(False, NAME, reason="customer opted out of this specific transaction")
    return GateResult(True, NAME)
