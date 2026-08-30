"""
Permanent opt-out. Enforced primarily as a DB UNIQUE constraint on
Suppression (models/tenant.py) -- this gate is the decision-time
enforcement point: even a correct DB constraint doesn't stop the
control plane from PROPOSING to contact a suppressed customer, only
from creating a second suppression row. This is where "no exceptions"
actually gets checked before an action is authorized.
"""
from __future__ import annotations

from app.models import Suppression
from .base import GateResult

NAME = "suppression"


def check(db, case, proposed, context: dict) -> GateResult:
    suppressed = db.query(Suppression).filter(Suppression.customer_id == case.customer_id).first()
    if suppressed is not None:
        return GateResult(False, NAME, reason="customer is permanently suppressed",
                           evidence={"suppression_reason": suppressed.reason})
    return GateResult(True, NAME)
