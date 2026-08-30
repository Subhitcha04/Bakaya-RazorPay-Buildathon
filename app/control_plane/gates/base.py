"""
Shared contract for every gate. A gate is a pure function of
(db, case, proposed, context) -> GateResult. No gate calls an LLM. No
gate reads proposed.justification. Every gate result -- pass or fail --
gets folded into the audit payload, so a block is as visible in the
ledger as a grant. Gates run in full (no short-circuit) so a case that
fails on gate 1 still produces a complete evidence trail.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class GateResult:
    passed: bool
    gate_name: str
    reason: str | None = None                 # populated only when passed=False
    evidence: dict[str, Any] = field(default_factory=dict)  # for the audit payload / EVIDENCE.md


class Gate(Protocol):
    name: str
    def check(self, db, case, proposed, context: dict) -> GateResult: ...


class ModuleGate:
    """
    Adapts a plain module (NAME constant + check() function) to the Gate
    protocol, so both hand-written classes and simple rule modules (like
    every RBI gate) can sit in the same registry and run through the
    same run_gates() loop.
    """
    def __init__(self, module):
        self._module = module
        self.name = module.NAME

    def check(self, db, case, proposed, context: dict) -> GateResult:
        return self._module.check(db, case, proposed, context)


def run_gates(db, case, proposed, context: dict, gates: list[Gate]) -> tuple[bool, list[GateResult]]:
    """
    Runs every gate, always. Overall pass = every gate passed. Returning
    the full result list (not just the first failure) is deliberate --
    it's what makes the case-detail screen's evidence chain possible.
    """
    results = [g.check(db, case, proposed, context) for g in gates]
    overall = all(r.passed for r in results)
    return overall, results
