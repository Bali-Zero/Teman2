"""Wave 2 — sensor name contract tripwire.

This suite exists because of anomaly A1 discovered in Wave 1 (see
`tests/NOTES.md` §A1 and `WAVE2_NOTES.md`): the 6 sensor classes expose
`.name` attributes (`war_room_event`, `competitor_serp`, etc.) while an
earlier version of `bayesian_calibrator.SENSOR_NAMES` declared shorter
aliases (`war_room`, `competitor`). Once Sprint 3 wires the calibrator to
real `Brief` rows keyed by sensor instance name, any residual drift
would silently feed zeros into 2 of the 6 features — a 33% signal loss
hidden from the caller.

The tests below fail on any re-introduction of that drift. They also
guarantee that `BayesianCalibrator._fit` actually reads the non-zero
scores a real Brief row carries, by reconstructing the Brief → X
projection end-to-end.

Sprint 2 added a 7th sensor (`lead_attribution`) that feeds the
pre_natal unlock gate exclusively, NOT the post-graduation Bayesian
scoring path. It is intentionally excluded from SENSOR_NAMES — the
contract here is about scoring weights, not sensor inventory. The
exclusion is asserted explicitly to prevent a future wave from
silently re-adding lead_attribution to SENSOR_NAMES (which would
require a corresponding DEFAULT_WEIGHTS rebalance and a calibrator
training change).
"""
from __future__ import annotations

import math

from apps.evaluator.seo_cell.bayesian_calibrator import (
    BayesianCalibrator,
    Brief,
    DEFAULT_WEIGHTS,
    SENSOR_NAMES,
)
from apps.evaluator.seo_cell.sensors import (
    CannibalizationSensor,
    CompetitorSERPSensor,
    GA4Sensor,
    GSCSensor,
    KGSensor,
    LeadAttributionSensor,
    WarRoomEventSensor,
)


# Sensors that participate in the Bayesian scoring contract.
# `lead_attribution` is excluded by design (gate-feeding only).
_SCORING_SENSOR_CLASSES = (
    GSCSensor,
    GA4Sensor,
    CompetitorSERPSensor,
    KGSensor,
    WarRoomEventSensor,
    CannibalizationSensor,
)


def _live_sensor_names() -> set[str]:
    """Names of sensors that are part of the calibrator scoring contract.

    Returns the 6 v2.1 scoring sensors. `lead_attribution` is checked
    separately by `test_lead_attribution_excluded_from_scoring_contract`.
    """
    return {cls().name for cls in _SCORING_SENSOR_CLASSES}


def test_sensor_names_match_live_sensor_instances():
    """SENSOR_NAMES must equal the live sensor `.name` set.

    Fails if either side drifts. This is the tripwire for A1.
    """
    assert set(SENSOR_NAMES) == _live_sensor_names(), (
        f"drift between SENSOR_NAMES and sensor .name attributes: "
        f"symmetric_diff={set(SENSOR_NAMES) ^ _live_sensor_names()}"
    )


def test_default_weights_keys_match_live_sensor_instances():
    """DEFAULT_WEIGHTS is derived from SENSOR_NAMES; this pins the
    consequence of that derivation against the live sensor contract.

    If a future refactor unpins DEFAULT_WEIGHTS from SENSOR_NAMES, this
    test still guards the thinker read path.
    """
    assert set(DEFAULT_WEIGHTS) == _live_sensor_names()


def test_calibrator_fit_reads_nonzero_scores_for_every_sensor():
    """End-to-end drift check: a Brief whose sensor_scores are keyed by
    the LIVE sensor `.name` values must be seen by `BayesianCalibrator._fit`
    with all 6 columns non-zero.

    With the bug (A1), two of the six columns of `X` would be read via
    `.get(<wrong key>, 0.0)` and silently come back as 0.0, yielding a
    degenerate fit. We reconstruct the Brief → X projection the same
    way `_fit` does and assert every column carries the intended signal.
    """
    names = _live_sensor_names()
    # Distinct non-zero score per sensor so "all zero" cannot be mistaken
    # for "happened to land on 0".
    scores = {name: (i + 1) * 0.1 for i, name in enumerate(sorted(names))}

    brief = Brief(
        brief_id="contract-probe",
        sensor_scores=scores,
        outcome_lift=0.25,
        outcome_window_days=28,
    )

    # Mirror the projection done inside `_fit`: look up each SENSOR_NAMES
    # entry in the brief's scores dict with the same default the
    # calibrator uses.
    projected = [
        float(brief.sensor_scores.get(s, 0.0)) for s in SENSOR_NAMES
    ]

    assert len(projected) == 6
    assert all(v > 0.0 for v in projected), (
        f"A1 drift: calibrator would read zeros for some sensors. "
        f"projected={dict(zip(SENSOR_NAMES, projected))}, "
        f"brief_keys={set(scores)}"
    )


def test_lead_attribution_excluded_from_scoring_contract():
    """Sprint 2 sensor feeds the pre_natal unlock gate, NOT the
    Bayesian calibrator. SENSOR_NAMES + DEFAULT_WEIGHTS must NOT
    contain `lead_attribution`.

    A future wave that wants to weight leads in the post-graduation
    scoring must (a) add it to SENSOR_NAMES, (b) rebalance
    DEFAULT_WEIGHTS, (c) retrain the calibrator with Brief rows that
    carry a `lead_attribution` score, and (d) update this test. Doing
    only (a)+(b) without (c)+(d) would silently feed zeros into the
    fit — exactly the A1 class of bug.
    """
    leads = LeadAttributionSensor()
    assert leads.name == "lead_attribution"
    assert leads.name not in SENSOR_NAMES
    assert leads.name not in DEFAULT_WEIGHTS


def test_calibrator_mutates_when_briefs_keyed_by_live_sensor_names():
    """Tripwire: feed the calibrator 40 Briefs keyed by LIVE sensor
    names. With the fix the calibrator performs a real ridge fit and
    reports `mutated=True`; with the bug the X matrix would hold zero
    columns for war_room_event / competitor_serp, the fit would still
    complete (ridge keeps XᵀX + λI non-singular) but the projected
    weights for those two sensors would collapse to 0.0 — a clear
    signal-loss regression we pin here.
    """
    names = sorted(_live_sensor_names())
    # Build a synthetic corpus where every sensor contributes
    # deterministically, so that any column read as 0 is directly
    # observable in the fitted weights.
    briefs: list[Brief] = []
    for i in range(40):
        scores = {n: ((i + k + 1) * 7 % 11) / 10.0 + 0.05
                  for k, n in enumerate(names)}
        lift = sum(scores.values()) / len(scores)
        briefs.append(Brief(
            brief_id=f"b{i:03d}",
            sensor_scores=scores,
            outcome_lift=lift,
            outcome_window_days=28,
        ))

    result = BayesianCalibrator(min_briefs=30).calibrate(briefs)
    assert result.mutated is True
    assert math.isclose(sum(result.weights.values()), 1.0, abs_tol=1e-9)

    # Core tripwire assertion: EVERY sensor under the live contract
    # received non-trivial signal. If SENSOR_NAMES drifts away from the
    # live sensor .name attributes, the two misaligned sensors get
    # zero-scores and project onto weight 0.0 after the simplex step.
    zero_sensors = [k for k, v in result.weights.items() if v == 0.0]
    assert not zero_sensors, (
        f"A1 regression: these sensors collapsed to zero weight "
        f"(likely key drift SENSOR_NAMES ↔ sensor.name): {zero_sensors}; "
        f"full weights={result.weights}"
    )
