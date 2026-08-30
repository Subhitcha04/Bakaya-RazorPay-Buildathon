"""
Pre-declared uplift segments. COMMIT THIS FILE BEFORE GENERATING ANY
DATA -- the entire point of pre-registration is that the segmentation
existed before results were looked at, not after. This file's git
history (first commit timestamp, before any results/run-*.json exists)
IS the evidence that the segmentation wasn't reverse-engineered from
favourable numbers.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    id: str
    root_cause_group: str
    ticket_band: str
    prior_failure_band: str
    expected_archetype: str


SEGMENTS: list[Segment] = [
    Segment("seg_01", "insufficient_funds", "small", "first", "persuadable"),
    Segment("seg_02", "insufficient_funds", "small", "repeat", "sure_thing"),
    Segment("seg_03", "insufficient_funds", "large", "first", "persuadable"),
    Segment("seg_04", "expired_card", "small", "first", "persuadable"),
    Segment("seg_05", "expired_card", "large", "repeat", "lost_cause"),
    Segment("seg_06", "issuer_risk_decline", "small", "first", "sleeping_dog"),
    Segment("seg_07", "mandate_lapsed", "mid", "first", "persuadable"),
    Segment("seg_08", "customer_intent", "small", "first", "sleeping_dog"),
]

assert len(SEGMENTS) == 8, "keep EVALUATION.md's segment count in sync with this list"


def classify_segment(root_cause: str, amount_paise: int, prior_failures: int) -> str:
    ticket_band = "small" if amount_paise < 500_00 else ("mid" if amount_paise < 5000_00 else "large")
    failure_band = "first" if prior_failures == 0 else "repeat"
    for seg in SEGMENTS:
        if (seg.root_cause_group == root_cause
                and seg.ticket_band == ticket_band
                and seg.prior_failure_band == failure_band):
            return seg.id
    return "unclassified"
