"""
Mutation testing: disables one control-plane gate at a time (monkey-
patches its check() to always return passed=True) and re-runs the
FULL test suite in a subprocess. Every mutation should turn at least
one test red -- if a mutation SURVIVES (every test still passes with
the gate silently disabled), that's a gap in the test suite, not a
safe gate.

"39 compliance tests pass" only proves the tests pass against CORRECT
code. This proves they'd fail against BROKEN code, which is the
question that actually matters -- a test suite is only as good as
what it would catch, not what it currently reports.

The mutation works because control_plane/gates/base.py::ModuleGate
stores a reference to the MODULE object and looks up `.check` at CALL
TIME, not at import time -- so patching `gate_module.check` before the
gate registry is exercised (even after capability.py has already been
imported) correctly changes what every downstream call sees, because
Python caches modules by name in sys.modules and every importer shares
the same module object.
"""
from __future__ import annotations

import subprocess
import sys

GATE_MODULES = [
    "app.control_plane.gates.consent",
    "app.control_plane.gates.suppression",
    "app.control_plane.gates.calling_window",
    "app.control_plane.gates.frequency_cap",
    "app.control_plane.gates.offer_ceiling",
    "app.control_plane.gates.rbi.afa_required",
    "app.control_plane.gates.rbi.pre_debit_window",
    "app.control_plane.gates.rbi.post_debit_notification",
    "app.control_plane.gates.rbi.afa_threshold",
    "app.control_plane.gates.rbi.opt_out_honour",
    "app.control_plane.gates.rbi.variable_mandate_cap",
    "app.control_plane.gates.rbi.redressal_in_templates",
    "app.control_plane.gates.rbi.fastag_exemption",
    "app.control_plane.gates.rbi.no_mandate_fee",
]

assert len(GATE_MODULES) == 14, "keep in sync with control_plane/capability.py's GATES count"

_MUTATION_RUNNER = """
import sys
from app.control_plane.gates.base import GateResult
import {module_name} as gate_module

_original_name = gate_module.NAME

def always_pass(db, case, proposed, context):
    return GateResult(True, _original_name, evidence={{"MUTATED": True}})

gate_module.check = always_pass

import pytest
sys.exit(pytest.main(["tests/", "-q"]))
"""


def mutate_and_test(module_name: str, cwd: str = ".") -> tuple[bool, str]:
    """
    Returns (caught, summary_line). caught=True means some test failed
    with the gate disabled (good -- the mutation was detected).
    caught=False means the full suite passed anyway (bad -- a real
    regression here would ship undetected).
    """
    script = _MUTATION_RUNNER.format(module_name=module_name)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=cwd,
    )
    caught = result.returncode != 0
    last_line = next((l for l in reversed(result.stdout.strip().splitlines()) if l.strip()), "")
    return caught, last_line


def main() -> int:
    print(f"Mutation testing {len(GATE_MODULES)} gates -- each mutation disables ONE gate ")
    print("(forces it to always return passed=True) and re-runs the full test suite.\n")

    results: dict[str, bool] = {}
    for module_name in GATE_MODULES:
        short_name = module_name.split(".")[-1]
        caught, summary = mutate_and_test(module_name)
        results[module_name] = caught
        status = "caught" if caught else "SURVIVED -- test gap"
        print(f"  {short_name:32s} {status:22s} {summary}")

    survived = [m for m, c in results.items() if not c]
    print(f"\n{len(GATE_MODULES) - len(survived)}/{len(GATE_MODULES)} mutations caught")
    if survived:
        print("SURVIVED (these gates could regress silently):")
        for m in survived:
            print(f"  - {m}")
        return 1

    print("Every gate's disablement is caught by at least one test.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
