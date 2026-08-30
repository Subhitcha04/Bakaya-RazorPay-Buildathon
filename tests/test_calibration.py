"""
Tests for scripts/calibration_report.py. The last two tests PIN the
real finding this script surfaced (the 0.4-0.8 confidence range is
badly miscalibrated on the real golden set) so it can't silently
regress or silently "fix itself" without someone noticing why -- same
discipline as tests/test_golden_set_diagnosis.py's documented-gap tests.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.calibration_report import run_calibration, load_golden_set


def test_calibration_covers_every_golden_set_entry():
    rows = run_calibration()
    total_in_buckets = sum(r["n"] for r in rows)
    assert total_in_buckets == len(load_golden_set())


def test_every_bucket_reports_a_valid_accuracy_range():
    rows = run_calibration()
    for r in rows:
        assert 0.0 <= r["actual_accuracy"] <= 1.0
        assert 0.0 <= r["mean_stated_confidence"] <= 1.0


def test_the_high_confidence_band_is_well_calibrated():
    rows = run_calibration()
    high_band = next(r for r in rows if r["bucket"] == "0.8-1.0")
    assert high_band["actual_accuracy"] >= 0.90, (
        f"the 0.8-1.0 confidence band dropped to {high_band['actual_accuracy']:.1%} accuracy -- "
        "the two safety thresholds set from this calibration (critic.MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT, "
        "cost.cascade.CONFIDENCE_ESCALATION_THRESHOLD) may no longer be justified"
    )


def test_the_mid_confidence_bands_are_documented_as_unreliable():
    rows = run_calibration()
    for bucket_label in ("0.4-0.6", "0.6-0.8"):
        row = next((r for r in rows if r["bucket"] == bucket_label), None)
        if row is None:
            continue
        assert row["actual_accuracy"] < 0.50, (
            f"{bucket_label} accuracy rose to {row['actual_accuracy']:.1%} -- if the "
            "Diagnostician genuinely improved, this is good news, but the two safety "
            "thresholds were deliberately raised BECAUSE this band was unreliable; "
            "re-evaluate whether they should move back down, don't just update this assertion"
        )


def test_thresholds_are_set_inside_the_well_calibrated_band():
    from app.agents.critic import MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT
    from app.cost.cascade import CONFIDENCE_ESCALATION_THRESHOLD
    assert MIN_CONFIDENCE_FOR_CUSTOMER_CONTACT >= 0.8
    assert CONFIDENCE_ESCALATION_THRESHOLD >= 0.8
