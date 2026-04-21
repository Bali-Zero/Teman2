"""Thinker reads seo_scoring_weights pattern from the genome.

Sprint 3 contract: the thinker exposes ``current_weights(genome)`` that
returns the calibrated weights if the genome has a
``seo_scoring_weights`` pattern recorded for the cell, otherwise the
safe defaults. This keeps the write path (Bayesian calibrator only) and
the read path (thinker) separate — no LLM ever writes this pattern.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from cell_core.genome import Genome

from apps.evaluator.seo_cell.bayesian_calibrator import (
    BayesianCalibrator,
    DEFAULT_WEIGHTS,
    SENSOR_NAMES,
    Brief,
)
from apps.evaluator.seo_cell.thinker import SEOThinker


def _brief(i: int) -> Brief:
    scores = {k: ((i * 7 + hash(k)) % 11) / 10.0 for k in SENSOR_NAMES}
    lift = sum(scores.values()) / len(scores)
    return Brief(
        brief_id=f"b{i}",
        sensor_scores=scores,
        outcome_lift=lift,
        outcome_window_days=28,
    )


def test_thinker_current_weights_defaults_when_no_pattern():
    thinker = SEOThinker()
    with tempfile.TemporaryDirectory() as tmp:
        genome = Genome(db_path=str(Path(tmp) / "g.db"))
        weights = thinker.current_weights(genome=genome, cell_name="seo-guardian")
    assert weights == DEFAULT_WEIGHTS


def test_thinker_current_weights_reads_pattern_after_calibration():
    thinker = SEOThinker()
    briefs = [_brief(i) for i in range(40)]

    with tempfile.TemporaryDirectory() as tmp:
        genome = Genome(db_path=str(Path(tmp) / "g.db"))
        calibrator = BayesianCalibrator(min_briefs=30, genome=genome)
        result = calibrator.calibrate(
            briefs, cell_name="seo-guardian", persist=True,
        )
        assert result.mutated is True

        weights = thinker.current_weights(
            genome=genome, cell_name="seo-guardian",
        )

    # Post-calibration weights are NOT the defaults.
    assert set(weights) == set(DEFAULT_WEIGHTS)
    # Must still be a simplex.
    assert abs(sum(weights.values()) - 1.0) < 1e-6
    # At least one sensor weight has moved from the uniform default.
    assert any(
        abs(weights[k] - DEFAULT_WEIGHTS[k]) > 1e-6 for k in SENSOR_NAMES
    )


def test_thinker_current_weights_falls_back_when_pattern_malformed():
    """If a legacy pattern row has non-JSON procedure, default weights
    win — no exception bubbles to the pulse loop."""
    thinker = SEOThinker()
    with tempfile.TemporaryDirectory() as tmp:
        genome = Genome(db_path=str(Path(tmp) / "g.db"))
        genome.record_skill(
            cell="seo-guardian",
            skill_id="seo_scoring_weights",
            procedure="not-json-at-all",
            confidence=0.5,
            entry_type="pattern",
        )
        weights = thinker.current_weights(
            genome=genome, cell_name="seo-guardian",
        )
    assert weights == DEFAULT_WEIGHTS
