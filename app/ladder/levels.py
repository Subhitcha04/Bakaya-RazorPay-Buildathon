"""
Maps a diagnosed root cause to its ladder ENTRY point. Re-exports
LadderLevel from control_plane.stopping_rules so there is exactly one
enum definition in the codebase.
"""
from __future__ import annotations

from app.control_plane.stopping_rules import LadderLevel

ROOT_CAUSE_TO_ENTRY_LEVEL: dict[str, LadderLevel] = {
    "insufficient_funds": LadderLevel.L1,
    "gateway_timeout": LadderLevel.L1,
    "issuer_risk_decline": LadderLevel.L1,
    "expired_card": LadderLevel.L3,
    "mandate_lapsed": LadderLevel.L3,
    "customer_intent": LadderLevel.L2,
    "fraud_flag": LadderLevel.L5,
    "other": LadderLevel.L5,
}

DEFAULT_ENTRY_LEVEL = LadderLevel.L5
