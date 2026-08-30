"""
Every customer-facing template must surface grievance redressal details
(a contact path for disputes). Implemented as a template lint over the
Composer's drafted copy -- cheap, real, and it's the one gate that runs
on TEXT rather than structured context, which is worth having in the
suite precisely because it exercises a different failure mode than the
others.

TODO: verify clause number against the primary circular before shipping.
"""
from __future__ import annotations

from ..base import GateResult

NAME = "rbi_redressal_in_templates"
REDRESSAL_MARKERS = ("grievance", "complaint", "redressal", "contact us", "support@")


def check(db, case, proposed, context: dict) -> GateResult:
    text = (proposed.copy_text or "").lower()
    if not text:
        return GateResult(True, NAME, evidence={"reason": "no customer-facing copy on this action"})
    if not any(marker in text for marker in REDRESSAL_MARKERS):
        return GateResult(False, NAME, reason="template lacks a grievance redressal reference")
    return GateResult(True, NAME)
