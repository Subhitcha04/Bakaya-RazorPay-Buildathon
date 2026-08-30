"""
Pre-execution adversarial review. Runs on the Strategist+Composer's
output BEFORE it reaches the control plane -- catches proposals that
are technically authorizable but a bad idea: confidence/intensity
mismatches, structural inconsistencies between channel and copy, or an
offer disproportionate to the case. The control plane's gates
independently re-check everything safety-critical regardless of what
Critic decides -- Critic exists to improve QUALITY (fewer wasted
contacts, better copy) before a proposal is even tested for
authorization, not to replace the control plane's job. A proposal
Critic rejects can still be blocked again by the gates; a proposal
Critic approves is NOT thereby authorized -- mint_capability() is the
only thing that authorizes anything.

Capped at ONE revision cycle -- same bounded, logged, never-open-ended
philosophy as control_plane/stopping_rules.py. If the revised proposal
still fails critique, it passes through to the control plane AS-IS
with the critique attached to the audit trail; the gates are the
actual backstop, not Critic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.control_plane.stopping_rules import LadderLevel
from app.schemas.contracts import ProposedActionOut

MAX_REVISIONS = 1

# Below this confidence, a customer-facing contact (L3+) shouldn't
# happen at all -- a bad guess doesn't deserve a real customer's
# attention. This is a QUALITY bar, distinct from the control plane's
# authorization bar, and can be stricter than anything a gate checks.
#
# SET FROM MEASURED CALIBRATION, NOT A ROUND NUMBER: originally 0.55.
# scripts/calibration_report.py, run against the real Diagnostician on
# the real 50-case golden set, found the 0.4-0.6 confidence band is
# only 9.1% ACTUALLY accurate -- meaning the old threshold let customer
# contact proceed on diagnoses that were wrong over 90% of the time.
# Only the 0.8-1.0 band is calibrated (100% actual accuracy on the
# golden set); raised to 0.85 to sit inside it. Re-run
# calibration_report.py and revisit this constant if the Diagnostician
# changes -- this number is only as good as the calibration data behind it.
MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT = 0.85

CUSTOMER_FACING_LEVELS = {LadderLevel.L3, LadderLevel.L4}


@dataclass(frozen=True)
class CritiqueResult:
    approved: bool
    reason: str | None = None


def critique_structure_and_confidence(proposed: ProposedActionOut, diagnosis_confidence: float) -> CritiqueResult:
    level = LadderLevel(proposed.ladder_level)

    if proposed.channel is not None and not proposed.copy_text:
        return CritiqueResult(False, "channel is set but no copy_text was drafted")
    if proposed.channel is None and proposed.copy_text:
        return CritiqueResult(False, "copy_text drafted for a silent action with no channel")

    if level in CUSTOMER_FACING_LEVELS and diagnosis_confidence < MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT:
        return CritiqueResult(
            False,
            f"confidence {diagnosis_confidence:.2f} too low for customer-facing level {level.value} "
            f"(minimum {MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT})",
        )

    return CritiqueResult(True)


def critique_offer_proportionality(proposed: ProposedActionOut, case_amount_paise: int) -> CritiqueResult:
    if proposed.amount_paise > case_amount_paise:
        return CritiqueResult(
            False,
            f"proposed offer {proposed.amount_paise} paise exceeds the case amount "
            f"{case_amount_paise} paise itself -- disproportionate",
        )
    return CritiqueResult(True)


def _full_critique(proposed: ProposedActionOut, diagnosis_confidence: float, case_amount_paise: int) -> CritiqueResult:
    structural = critique_structure_and_confidence(proposed, diagnosis_confidence)
    if not structural.approved:
        return structural
    return critique_offer_proportionality(proposed, case_amount_paise)


def review_with_one_revision(
    proposed: ProposedActionOut,
    diagnosis_confidence: float,
    case_amount_paise: int,
    revise_fn: Callable[[], ProposedActionOut],
) -> tuple[ProposedActionOut, CritiqueResult, int]:
    result = _full_critique(proposed, diagnosis_confidence, case_amount_paise)
    if result.approved:
        return proposed, result, 0

    revised = revise_fn()
    revised_result = _full_critique(revised, diagnosis_confidence, case_amount_paise)
    return revised, revised_result, 1
