"""
Routes a diagnosed case to its ladder entry point. Encodes the
retention-risk special case: those cases NEVER enter the executing
ladder -- they route straight to L5, matching executes=False on the
ChurnIntentDetector.
"""
from __future__ import annotations

from app.control_plane.stopping_rules import LadderLevel
from .levels import ROOT_CAUSE_TO_ENTRY_LEVEL, DEFAULT_ENTRY_LEVEL


def entry_level_for(root_cause: str, executes: bool) -> LadderLevel:
    if not executes:
        return LadderLevel.L5
    return ROOT_CAUSE_TO_ENTRY_LEVEL.get(root_cause, DEFAULT_ENTRY_LEVEL)
