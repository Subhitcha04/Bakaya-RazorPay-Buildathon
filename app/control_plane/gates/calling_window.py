"""
No RBI rule binds merchant dunning to specific calling hours -- the Fair
Practices Code'"'"'s 8am-7pm window governs REGULATED LENDERS and their
recovery agents, not a merchant chasing its own receivables. This gate
implements it anyway as a VOLUNTARY floor: the failure mode (contacting
someone at an inappropriate hour) is identical regardless of who'"'"'s
doing the contacting. See COMPLIANCE.md binds-vs-voluntary table -- this
is the clearest example of "adopted voluntarily, and here'"'"'s why."
"""
from __future__ import annotations

from datetime import datetime, time

from .base import GateResult

NAME = "calling_window"
WINDOW_START = time(8, 0)
WINDOW_END = time(19, 0)
TIME_SENSITIVE_CHANNELS = {"voice", "sms", "whatsapp"}


def check(db, case, proposed, context: dict) -> GateResult:
    if proposed.channel not in TIME_SENSITIVE_CHANNELS:
        return GateResult(True, NAME, evidence={"reason": "channel not time-sensitive"})

    now: datetime = context.get("now") or datetime.now()
    within_window = WINDOW_START <= now.time() <= WINDOW_END
    if not within_window:
        return GateResult(False, NAME, reason="outside voluntary 8am-7pm contact window",
                           evidence={"attempted_at": now.isoformat(), "binds": False,
                                     "source": "RBI Fair Practices Code -- adopted voluntarily, not binding on merchant dunning"})
    return GateResult(True, NAME)
