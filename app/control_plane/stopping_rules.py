"""
Ladder state machine + stopping rules. This is where "stopping rules"
as a bar phrase becomes actual code rather than a `max_retries = 3`
config constant. `evaluate()` is a pure function -- no DB access, no
LLM call -- called by the ladder router before a new ProposedAction is
even drafted. Every stop has a machine-readable reason, logged to the
audit trail alongside grants and blocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LadderLevel(str, Enum):
    L0 = "L0"  # prevent
    L1 = "L1"  # silent retry
    L2 = "L2"  # passive
    L3 = "L3"  # nudge
    L4 = "L4"  # assisted
    L5 = "L5"  # human
    L6 = "L6"  # terminal


LADDER_ORDER = [LadderLevel.L0, LadderLevel.L1, LadderLevel.L2, LadderLevel.L3,
                LadderLevel.L4, LadderLevel.L5, LadderLevel.L6]
_ORDER = LADDER_ORDER  # internal alias used below

TERMINAL_LEVELS = {LadderLevel.L6}

MAX_ATTEMPTS_PER_LEVEL = {
    LadderLevel.L1: 3,
    LadderLevel.L3: 1,   # single-nudge -- no escalating offer ladder after one attempt
    LadderLevel.L4: 2,
}
COOLDOWN_HOURS_PER_LEVEL = {
    LadderLevel.L1: 6,
    LadderLevel.L3: 20,
    LadderLevel.L4: 48,
}
DEFAULT_DAILY_CONTACT_CAP = 3   # shared across ALL surfaces for one customer -- see ContactBudgetLedger


@dataclass(frozen=True)
class StopDecision:
    should_stop: bool
    reason: str | None = None
    next_level: LadderLevel | None = None


def evaluate(
    current_level: LadderLevel,
    attempts_at_current_level: int,
    hours_since_last_attempt: float | None,
    customer_refused: bool,
    total_contacts_today_all_surfaces: int,
    contact_cap_per_day: int = DEFAULT_DAILY_CONTACT_CAP,
) -> StopDecision:
    """
    Every input here is an explicit fact, never the agent's narrative
    about why it should keep going -- this function has no visibility
    into ProposedAction.justification at all. That's deliberate: a
    hallucinating agent that "believes" escalation is warranted still
    has to pass through the same arithmetic as everyone else.
    """
    if customer_refused:
        return StopDecision(True, reason="explicit_refusal", next_level=LadderLevel.L6)

    if current_level in TERMINAL_LEVELS:
        return StopDecision(True, reason="already_terminal")

    if total_contacts_today_all_surfaces >= contact_cap_per_day:
        return StopDecision(True, reason="daily_contact_cap_reached", next_level=LadderLevel.L5)

    max_attempts = MAX_ATTEMPTS_PER_LEVEL.get(current_level)
    if max_attempts is not None and attempts_at_current_level >= max_attempts:
        return StopDecision(False, reason="attempts_exhausted_at_level", next_level=_next_level(current_level))

    cooldown = COOLDOWN_HOURS_PER_LEVEL.get(current_level)
    if cooldown is not None and hours_since_last_attempt is not None and hours_since_last_attempt < cooldown:
        return StopDecision(True, reason="cooldown_not_elapsed")

    return StopDecision(False, reason=None, next_level=current_level)


def _next_level(level: LadderLevel) -> LadderLevel:
    idx = _ORDER.index(level)
    return _ORDER[min(idx + 1, len(_ORDER) - 1)]


def is_terminal_reachable_from(level: LadderLevel) -> bool:
    """
    Sanity check used in tests: every level must have a path to L6.
    Guards against ever adding a level that traps a case forever.
    """
    seen = set()
    current = level
    for _ in range(len(_ORDER) + 1):
        if current in TERMINAL_LEVELS:
            return True
        if current in seen:
            return False
        seen.add(current)
        current = _next_level(current)
    return False
