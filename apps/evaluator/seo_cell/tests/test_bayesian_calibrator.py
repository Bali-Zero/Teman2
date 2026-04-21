"""BayesianCalibrator — Sprint 3 Thinker evolution.

The calibrator owns the `seo_scoring_weights` pattern: given a history of
SEO briefs with outcomes measured at 28/60/90 days, it re-estimates the
weights for the 6 sensors (gsc, ga4, kg, war_room, competitor,
cannibalization) via a ridge-regularised least-squares fit and writes the
pattern to the genome.

Hard guards verified here:
  - Min-sample gate: <30 briefs with >=28-day outcome → weights stay at
    default, no genome write.
  - No LLM path: the calibrator is pure numerical — no import of any
    llm_client module must appear in the call graph at runtime.
  - Only the calibrator mutates the pattern — written with
    type="pattern" and name seo_scoring_weights.
  - 7-day outcomes are rejected even if supplied (rule §4 of the dna).
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pytest

from cell_core.genome import Genome

from apps.evaluator.seo_cell.bayesian_calibrator import (
    DEFAULT_WEIGHTS,
    ALLOWED_LIFT_WINDOWS_DAYS,
    SENSOR_NAMES,
    Brief,
    BayesianCalibrator,
    measure_lift,
)


# ─── helpers ────────────────────────────────────────────────────────────

def _brief(
    *,
    scores: dict[str, float],
    outcome: float,
    outcome_window_days: int = 28,
) -> Brief:
    """Build a Brief row with sensor scores → outcome (lift)."""
    return Brief(
        brief_id=f"brief-{abs(hash(frozenset(scores.items()))) % 10**6}",
        sensor_scores=scores,
        outcome_lift=outcome,
        outcome_window_days=outcome_window_days,
    )


def _synthetic_corpus(n: int, true_weights: dict[str, float]) -> list[Brief]:
    """Deterministic signal: outcome = Σ wᵢ · xᵢ + tiny-bounded ripple.

    Uses a cheap deterministic hash in place of randomness so tests are
    reproducible on any platform.
    """
    out: list[Brief] = []
    for i in range(n):
        # 6 sensor scores in [0,1], varied per brief via prime rotations.
        x = {
            "gsc": (i * 7 % 11) / 10.0,
            "ga4": (i * 13 % 11) / 10.0,
            "kg": (i * 17 % 11) / 10.0,
            "war_room_event": (i * 19 % 11) / 10.0,
            "competitor_serp": (i * 23 % 11) / 10.0,
            "cannibalization": (i * 29 % 11) / 10.0,
        }
        lift = sum(true_weights[k] * x[k] for k in SENSOR_NAMES)
        # deterministic noise in [-0.01, 0.01]
        ripple = ((i * 97) % 21 - 10) / 1000.0
        out.append(_brief(scores=x, outcome=lift + ripple, outcome_window_days=28))
    return out


# ─── API shape ──────────────────────────────────────────────────────────

def test_default_weights_are_six_positive_sensors_summing_to_one():
    assert set(DEFAULT_WEIGHTS) == set(SENSOR_NAMES)
    assert all(v > 0 for v in DEFAULT_WEIGHTS.values())
    assert math.isclose(sum(DEFAULT_WEIGHTS.values()), 1.0, abs_tol=1e-9)


def test_sensor_names_match_dna_exactly():
    # Must align with the sensor instance `.name` attributes, which are
    # the user-facing API pinned by `tests/test_integration_wave1.py`
    # and pulled from the sensor classes themselves. See NOTES.md §A1
    # for the history of this contract (wave 1 ➜ wave 2 fix).
    assert SENSOR_NAMES == (
        "gsc",
        "ga4",
        "kg",
        "war_room_event",
        "competitor_serp",
        "cannibalization",
    )


def test_allowed_lift_windows_are_28_60_90_only():
    # Rule §4 dna.json — never measure lift on <28 days.
    assert ALLOWED_LIFT_WINDOWS_DAYS == (28, 60, 90)


# ─── lift measurement ───────────────────────────────────────────────────

def test_measure_lift_rejects_seven_day_window():
    with pytest.raises(ValueError) as exc:
        measure_lift(
            before=10.0, after=15.0, window_days=7,
        )
    assert "28" in str(exc.value) or "window" in str(exc.value)


def test_measure_lift_accepts_28_60_90():
    # Should not raise for any allowed window.
    for w in ALLOWED_LIFT_WINDOWS_DAYS:
        v = measure_lift(before=10.0, after=12.0, window_days=w)
        assert isinstance(v, float)


def test_measure_lift_zero_before_returns_zero_not_inf():
    # before=0 is edge case — avoid division blow-up.
    v = measure_lift(before=0.0, after=5.0, window_days=28)
    assert math.isfinite(v)


def test_measure_lift_normalises_relative_change():
    # (15 − 10) / 10 = 0.5 — exact, no noise.
    v = measure_lift(before=10.0, after=15.0, window_days=28)
    assert math.isclose(v, 0.5, abs_tol=1e-9)


# ─── min-sample gate ────────────────────────────────────────────────────

def test_calibrator_returns_default_weights_below_min_briefs():
    """<30 briefs → neonato not reached → NO mutation."""
    calibrator = BayesianCalibrator(min_briefs=30)
    briefs = _synthetic_corpus(
        n=10,
        true_weights={k: 1.0 / 6 for k in SENSOR_NAMES},
    )
    result = calibrator.calibrate(briefs)

    assert result.weights == DEFAULT_WEIGHTS
    assert result.mutated is False
    assert "min_briefs" in result.reason or "below" in result.reason


def test_calibrator_rejects_briefs_with_7day_outcome():
    """A 7-day outcome brief counts as 0 samples against the 30-gate."""
    calibrator = BayesianCalibrator(min_briefs=30)
    briefs = []
    for _ in range(40):
        briefs.append(_brief(
            scores={k: 0.5 for k in SENSOR_NAMES},
            outcome=0.1,
            outcome_window_days=7,  # invalid
        ))
    result = calibrator.calibrate(briefs)
    assert result.mutated is False
    assert result.weights == DEFAULT_WEIGHTS


def test_calibrator_accepts_mixed_28_60_90_as_valid_samples():
    true = {k: 1.0 / 6 for k in SENSOR_NAMES}
    briefs = _synthetic_corpus(n=30, true_weights=true)
    # Re-tag windows to 28/60/90 in rotation — all valid.
    for i, b in enumerate(briefs):
        b.outcome_window_days = (28, 60, 90)[i % 3]
    result = BayesianCalibrator(min_briefs=30).calibrate(briefs)
    assert result.mutated is True


# ─── numerical correctness ─────────────────────────────────────────────

def test_calibrator_recovers_true_weights_on_clean_signal():
    """With a deterministic synthetic signal, ridge fit + renormalisation
    must return weights within a modest tolerance of truth.

    We don't require millimetric recovery — we do require (a) each
    sensor's weight is within ±0.15 of the true weight, and (b) sum=1.0.
    """
    true = {
        "gsc": 0.30,
        "ga4": 0.20,
        "kg": 0.20,
        "war_room_event": 0.10,
        "competitor_serp": 0.10,
        "cannibalization": 0.10,
    }
    briefs = _synthetic_corpus(n=60, true_weights=true)
    result = BayesianCalibrator(min_briefs=30).calibrate(briefs)

    assert result.mutated is True
    assert math.isclose(sum(result.weights.values()), 1.0, abs_tol=1e-9)
    for k, v_true in true.items():
        diff = abs(result.weights[k] - v_true)
        assert diff < 0.15, f"{k}: got {result.weights[k]:.3f}, want {v_true} (±0.15)"


def test_calibrator_weights_never_negative():
    # Ridge + non-negative projection → non-negative weights.
    briefs = _synthetic_corpus(
        n=40,
        # Extreme case: one sensor contributes nothing — must not go neg.
        true_weights={
            "gsc": 0.50,
            "ga4": 0.00,
            "kg": 0.00,
            "war_room_event": 0.50,
            "competitor_serp": 0.00,
            "cannibalization": 0.00,
        },
    )
    result = BayesianCalibrator(min_briefs=30).calibrate(briefs)
    assert result.mutated is True
    assert all(w >= 0 for w in result.weights.values())


# ─── genome integration ────────────────────────────────────────────────

def test_calibrator_writes_pattern_seo_scoring_weights():
    true = {k: 1.0 / 6 for k in SENSOR_NAMES}
    briefs = _synthetic_corpus(n=40, true_weights=true)

    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "g.db")
        genome = Genome(db_path=db_path)

        calibrator = BayesianCalibrator(min_briefs=30, genome=genome)
        result = calibrator.calibrate(
            briefs, cell_name="seo-guardian", persist=True,
        )
        assert result.mutated is True

        rows = genome.get_active(
            cell="seo-guardian", entry_type="pattern",
        )
        # Must write exactly one row for seo_scoring_weights.
        matches = [r for r in rows if r["id"] == "seo_scoring_weights"]
        assert len(matches) == 1
        proc = matches[0]["procedure"]
        # Procedure carries the JSON weights so the thinker can read them.
        assert "gsc" in proc and "cannibalization" in proc


def test_calibrator_does_not_write_when_below_min_briefs():
    briefs = _synthetic_corpus(
        n=5, true_weights={k: 1.0 / 6 for k in SENSOR_NAMES},
    )
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "g.db")
        genome = Genome(db_path=db_path)
        BayesianCalibrator(min_briefs=30, genome=genome).calibrate(
            briefs, cell_name="seo-guardian", persist=True,
        )
        rows = genome.get_active(
            cell="seo-guardian", entry_type="pattern",
        )
        assert not any(r["id"] == "seo_scoring_weights" for r in rows)


def test_calibrator_never_uses_llm():
    """Import-time guard: the module must not pull any LLM client.

    The whole point of Sprint 3 per the decision memo is: 'NO council
    4-LLM voting, pesi mutati SOLO da Bayesian calibrator'. A regression
    that sneaks an LLM back in must trip the test.
    """
    import importlib
    import sys

    # Purge any pre-cached LLM module so we see fresh imports only if the
    # calibrator triggers them.
    for name in list(sys.modules):
        if "llm_client" in name or name.endswith(".llm"):
            # Leave alone — but snapshot current keys for delta check.
            pass
    before = set(sys.modules)

    mod = importlib.import_module(
        "apps.evaluator.seo_cell.bayesian_calibrator"
    )
    # Trigger a calibrate call so any lazy imports fire.
    mod.BayesianCalibrator(min_briefs=30).calibrate(
        _synthetic_corpus(40, {k: 1 / 6 for k in SENSOR_NAMES}),
    )
    newly = set(sys.modules) - before
    forbidden = {m for m in newly if "llm" in m.lower() or "openai" in m.lower()
                 or "anthropic" in m.lower() or "ollama" in m.lower()}
    assert not forbidden, f"BayesianCalibrator pulled LLM modules: {forbidden}"


# ─── determinism ───────────────────────────────────────────────────────

def test_calibrator_is_deterministic_same_input_same_output():
    true = {k: 1.0 / 6 for k in SENSOR_NAMES}
    briefs = _synthetic_corpus(n=40, true_weights=true)
    c = BayesianCalibrator(min_briefs=30)
    r1 = c.calibrate(briefs)
    r2 = c.calibrate(briefs)
    assert r1.weights == r2.weights
    assert r1.mutated == r2.mutated
