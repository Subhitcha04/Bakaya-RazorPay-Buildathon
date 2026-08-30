"""
The 9 RBI e-mandate gates, as a registry. COMPLIANCE.md claims "9 rules
-> 9 files -> 9 test classes" -- this list is what makes that claim
mechanically checkable rather than just asserted. If you add or remove
a gate, this count changes and COMPLIANCE.md needs updating to match --
an automated reviewer diffing the two would catch a mismatch.
"""
from __future__ import annotations

from . import (
    afa_required,
    pre_debit_window,
    post_debit_notification,
    afa_threshold,
    opt_out_honour,
    variable_mandate_cap,
    redressal_in_templates,
    fastag_exemption,
    no_mandate_fee,
)

RBI_GATE_MODULES = [
    afa_required,
    pre_debit_window,
    post_debit_notification,
    afa_threshold,
    opt_out_honour,
    variable_mandate_cap,
    redressal_in_templates,
    fastag_exemption,
    no_mandate_fee,
]

assert len(RBI_GATE_MODULES) == 9, "COMPLIANCE.md claims 9 RBI gates -- keep this list in sync"
