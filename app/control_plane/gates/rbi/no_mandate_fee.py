"""
No customer charges are permitted for the e-mandate facility itself
(separate from the underlying transaction amount, which is what's being
collected in the first place).

TODO: verify clause number against the primary circular before shipping.
"""
from __future__ import annotations

from ..base import GateResult

NAME = "rbi_no_mandate_fee"


def check(db, case, proposed, context: dict) -> GateResult:
    fee = context.get("mandate_facility_fee_paise", 0)
    if fee > 0:
        return GateResult(False, NAME, reason="a fee is being charged for the e-mandate facility itself",
                           evidence={"fee_paise": fee})
    return GateResult(True, NAME)
