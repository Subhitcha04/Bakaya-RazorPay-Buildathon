"""
An action on a channel requires ACTIVE consent for that specific
channel. No row, or a revoked row, blocks -- silent actions (channel is
None, e.g. L1 silent retry) are consent-exempt by construction.
"""
from __future__ import annotations

from app.models import Consent
from .base import GateResult

NAME = "consent"


def check(db, case, proposed, context: dict) -> GateResult:
    if proposed.channel is None:
        return GateResult(True, NAME, evidence={"reason": "no channel -- e.g. silent retry, consent N/A"})

    consent = (
        db.query(Consent)
        .filter(Consent.customer_id == case.customer_id, Consent.channel == proposed.channel)
        .first()
    )
    if consent is None or consent.state != "granted":
        return GateResult(False, NAME, reason="no active consent for this channel",
                           evidence={"channel": proposed.channel})
    return GateResult(True, NAME, evidence={"channel": proposed.channel, "consent_id": consent.id})
