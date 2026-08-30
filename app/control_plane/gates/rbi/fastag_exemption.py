"""
FASTag and NCMC auto-replenishment are EXEMPT from the pre-transaction
notification requirement (see rbi_pre_debit_window, which reads
context["notification_exempt"]).

This gate exists specifically to prove the exemption is modelled, not
just the headline rule -- see COMPLIANCE.md: handling an exception
correctly is the cheapest proof of having read the primary source
rather than a summary of it. It always passes; its role is declarative
-- it stamps the exemption reasoning into the evidence trail for this
case regardless of outcome.

TODO: verify clause number against the primary circular before shipping.
"""
from __future__ import annotations

from ..base import GateResult

NAME = "rbi_fastag_exemption"
EXEMPT_KINDS = {"fastag_replenishment", "ncmc_replenishment"}


def check(db, case, proposed, context: dict) -> GateResult:
    is_exempt = getattr(case, "kind", None) in EXEMPT_KINDS
    return GateResult(True, NAME, evidence={
        "exempt": is_exempt,
        "kind": getattr(case, "kind", None),
        "basis": "FASTag/NCMC auto-replenishment exempt from pre-txn notification" if is_exempt else None,
    })
