"""
RBI Digital Payments -- E-mandate Framework, 2026
(Circular RBI/DPSS/2026-27/396, 21 April 2026).

AFA (Additional Factor of Authentication) is required at: registration,
modification, withdrawal, first transaction, and customer opt-out.

TODO before shipping: verify the exact paragraph/clause number against
the primary circular at rbi.org.in and cite it here. This docstring
currently reflects secondary reporting of the circular, not the
circular text itself -- see COMPLIANCE.md for why that distinction
matters in front of a payments panel.
"""
from __future__ import annotations

from ..base import GateResult

NAME = "rbi_afa_required"

AFA_REQUIRING_EVENTS = {"registration", "modification", "withdrawal", "first_transaction", "opt_out"}


def check(db, case, proposed, context: dict) -> GateResult:
    mandate_event = context.get("mandate_event")
    if mandate_event not in AFA_REQUIRING_EVENTS:
        return GateResult(True, NAME, evidence={"mandate_event": mandate_event})

    if not context.get("afa_completed", False):
        return GateResult(False, NAME, reason=f"AFA required for '{mandate_event}' but not completed",
                           evidence={"mandate_event": mandate_event})
    return GateResult(True, NAME, evidence={"mandate_event": mandate_event, "afa_completed": True})
