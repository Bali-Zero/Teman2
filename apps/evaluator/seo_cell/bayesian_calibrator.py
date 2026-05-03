"""BayesianCalibrator — Sprint 3 replacement for the Council 4-LLM theater.

Responsibility
--------------
Re-estimate the 6-sensor `seo_scoring_weights` pattern from a history of
SEO briefs with observed commercial lift, using a ridge-regularised
non-negative least-squares fit. Output weights are written to the
genome as `type='pattern', id='seo_scoring_weights'` so the thinker can
read them on the next pulse.

Rules enforced (from dna.json and the v2.1 decision memo):

* Lift measurement only at 28/60/90 days — 7-day windows are rejected.
* Weights mutate only when >=30 briefs with a valid outcome window are
  available (post-neonato rule).
* No LLM is touched — the call graph is pure numpy-free pure-Python.
* The pattern is written with `type='pattern'`, overwrite-in-place on
  re-calibration.

Numerical method
----------------
We solve ``min_w ||Xw - y||² + λ||w||²`` via the closed-form normal
equations (small problem: 6x6 matrix), then project onto the simplex
(non-negative, sum=1) so the output remains interpretable as relative
sensor weights. This is deliberately simple — Sprint 4+ may introduce a
proper Bayesian posterior with credible intervals, but the decision
memo explicitly says "no Goodhart — weights mutate only via Bayesian
calibrator", leaving the door open for ridge as the starting point.

No external dependency beyond Python's stdlib: a 6x6 solve is cheap
enough to do by hand via Gauss-Jordan.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from cell_core.genome import Genome

logger = logging.getLogger("seo_cell.bayesian_calibrator")

# ── Public constants ────────────────────────────────────────────────────

SENSOR_NAMES: tuple[str, ...] = (
    "gsc",
    "ga4",
    "kg",
    "war_room_event",
    "competitor_serp",
    "cannibalization",
)

DEFAULT_WEIGHTS: dict[str, float] = {k: 1.0 / len(SENSOR_NAMES) for k in SENSOR_NAMES}

# dna.json rule §4: never measure lift on windows <28 days.
ALLOWED_LIFT_WINDOWS_DAYS: tuple[int, ...] = (28, 60, 90)

PATTERN_ID = "seo_scoring_weights"
PATTERN_TYPE = "pattern"


# ── Data classes ────────────────────────────────────────────────────────

@dataclass
class Brief:
    """One historical brief + the lift we observed after `outcome_window_days`."""

    brief_id: str
    sensor_scores: dict[str, float]
    outcome_lift: float
    outcome_window_days: int


@dataclass
class CalibrationResult:
    weights: dict[str, float]
    mutated: bool
    reason: str
    sample_count: int = 0
    persisted_to_genome: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Lift helper ─────────────────────────────────────────────────────────

def measure_lift(*, before: float, after: float, window_days: int) -> float:
    """Relative lift between two point measurements.

    Raises
    ------
    ValueError
        If ``window_days`` is not one of ``ALLOWED_LIFT_WINDOWS_DAYS``.
    """
    if window_days not in ALLOWED_LIFT_WINDOWS_DAYS:
        raise ValueError(
            f"lift window_days={window_days} not allowed; "
            f"must be one of {ALLOWED_LIFT_WINDOWS_DAYS} (dna rule §4)"
        )
    if before == 0:
        # Edge case: cold-start brief. Define lift as `after` itself so
        # the downstream fit still sees a finite signal.
        return float(after)
    return float(after - before) / float(before)


# ── Linear algebra helpers (pure Python, 6x6) ──────────────────────────

def _transpose(m: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*m)]


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    rows_a, cols_a = len(a), len(a[0])
    cols_b = len(b[0])
    out = [[0.0] * cols_b for _ in range(rows_a)]
    for i in range(rows_a):
        for k in range(cols_a):
            aik = a[i][k]
            if aik == 0.0:
                continue
            row_out = out[i]
            row_b = b[k]
            for j in range(cols_b):
                row_out[j] += aik * row_b[j]
    return out


def _matvec(a: list[list[float]], v: list[float]) -> list[float]:
    return [sum(aij * vj for aij, vj in zip(row, v)) for row in a]


def _solve_linear_system(A: list[list[float]], b: list[float]) -> list[float]:
    """Gauss-Jordan with partial pivoting on an augmented matrix.

    A is n×n, b is length n. Returns the solution vector or raises
    ``ValueError`` if the system is singular.
    """
    n = len(b)
    # Build augmented matrix.
    M = [A[i][:] + [b[i]] for i in range(n)]

    for col in range(n):
        # Partial pivot
        pivot = col
        for r in range(col + 1, n):
            if abs(M[r][col]) > abs(M[pivot][col]):
                pivot = r
        if abs(M[pivot][col]) < 1e-12:
            raise ValueError("singular matrix in ridge solver")
        if pivot != col:
            M[col], M[pivot] = M[pivot], M[col]

        # Normalise pivot row
        inv = 1.0 / M[col][col]
        for j in range(col, n + 1):
            M[col][j] *= inv

        # Eliminate other rows
        for r in range(n):
            if r == col:
                continue
            factor = M[r][col]
            if factor == 0.0:
                continue
            for j in range(col, n + 1):
                M[r][j] -= factor * M[col][j]

    return [M[i][n] for i in range(n)]


def _project_onto_simplex(w: list[float]) -> list[float]:
    """Clip negatives to 0, renormalise to sum=1.

    If the vector is all-zero (or all-negative) after clipping, fall
    back to the uniform distribution to avoid div-by-zero.
    """
    w = [max(0.0, x) for x in w]
    total = sum(w)
    if total <= 1e-12:
        n = len(w)
        return [1.0 / n] * n
    return [x / total for x in w]


# ── The calibrator ──────────────────────────────────────────────────────

class BayesianCalibrator:
    """Ridge-regularised non-negative weight fitter for SEO sensors.

    Parameters
    ----------
    min_briefs :
        Minimum number of briefs with a valid 28/60/90-day outcome
        required before the calibrator will mutate weights. Below this
        threshold the default uniform weights are returned and the
        genome is not touched. The decision memo sets this to 30.
    ridge_lambda :
        L2 regularisation strength. Keeps the fit stable when
        collinearity is high (e.g. gsc and ga4 both correlated with
        organic traffic).
    genome :
        Optional :class:`cell_core.genome.Genome` instance used when
        ``calibrate(persist=True)`` is invoked.
    """

    def __init__(
        self,
        *,
        min_briefs: int = 30,
        ridge_lambda: float = 0.05,
        genome: Genome | None = None,
    ) -> None:
        self._min_briefs = min_briefs
        self._ridge_lambda = ridge_lambda
        self._genome = genome

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calibrate(
        self,
        briefs: list[Brief],
        *,
        cell_name: str = "seo-guardian",
        persist: bool = False,
    ) -> CalibrationResult:
        """Fit weights from *briefs* and optionally persist to the genome.

        Returns a :class:`CalibrationResult` describing the outcome. The
        default weights are returned and ``mutated=False`` when the
        min-sample gate is not met — at that point nothing is written
        even if ``persist=True``.
        """
        valid = [
            b for b in briefs
            if b.outcome_window_days in ALLOWED_LIFT_WINDOWS_DAYS
        ]
        n = len(valid)

        if n < self._min_briefs:
            logger.info(
                "[calibrator] %d valid briefs <%d min → keeping default weights",
                n, self._min_briefs,
            )
            return CalibrationResult(
                weights=dict(DEFAULT_WEIGHTS),
                mutated=False,
                reason=f"below min_briefs gate ({n} < {self._min_briefs})",
                sample_count=n,
                persisted_to_genome=False,
            )

        weights = self._fit(valid)
        result = CalibrationResult(
            weights=weights,
            mutated=True,
            reason=f"ridge fit on {n} briefs (lambda={self._ridge_lambda})",
            sample_count=n,
        )

        if persist:
            if self._genome is None:
                raise ValueError(
                    "persist=True but no genome was supplied at construction"
                )
            self._write_pattern(cell_name=cell_name, weights=weights)
            result.persisted_to_genome = True

        return result

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _fit(self, briefs: list[Brief]) -> dict[str, float]:
        """Solve ``(XᵀX + λI) w = Xᵀy`` then project onto the simplex."""
        n = len(briefs)
        p = len(SENSOR_NAMES)

        # Build X (n×p) and y (n).
        X: list[list[float]] = []
        y: list[float] = []
        for b in briefs:
            X.append([float(b.sensor_scores.get(s, 0.0)) for s in SENSOR_NAMES])
            y.append(float(b.outcome_lift))

        Xt = _transpose(X)
        XtX = _matmul(Xt, X)
        # Ridge: add λ·I.
        for i in range(p):
            XtX[i][i] += self._ridge_lambda
        Xty = _matvec(Xt, y)

        try:
            raw = _solve_linear_system(XtX, Xty)
        except ValueError:
            logger.warning("[calibrator] singular XtX — falling back to defaults")
            return dict(DEFAULT_WEIGHTS)

        projected = _project_onto_simplex(raw)
        return {SENSOR_NAMES[i]: projected[i] for i in range(p)}

    def _write_pattern(
        self,
        *,
        cell_name: str,
        weights: dict[str, float],
    ) -> None:
        """Record weights as a genome pattern, upsert semantics."""
        assert self._genome is not None
        procedure = json.dumps(weights, sort_keys=True)
        precondition = (
            "Apply these sensor weights when scoring SEO action candidates."
        )
        success_criterion = (
            "Weighted score correlates with 28/60/90-day lift."
        )
        self._genome.record_skill(
            cell=cell_name,
            skill_id=PATTERN_ID,
            procedure=procedure,
            precondition=precondition,
            success_criterion=success_criterion,
            confidence=0.70,
            scope="Project",
            entry_type=PATTERN_TYPE,
            domain="seo",
        )
        logger.info(
            "[calibrator] wrote pattern %s to genome for cell %s",
            PATTERN_ID,
            cell_name,
        )


__all__ = [
    "ALLOWED_LIFT_WINDOWS_DAYS",
    "BayesianCalibrator",
    "Brief",
    "CalibrationResult",
    "DEFAULT_WEIGHTS",
    "PATTERN_ID",
    "SENSOR_NAMES",
    "measure_lift",
]
