"""Threshold configuration for anomaly detectors.

Calibration notes
-----------------
Values here are defaults. Override via a YAML file passed to
``load_thresholds(path)``. The CLI ``run_anomaly_scan.py`` accepts
``--config`` pointing at such a file.

How defaults were chosen
------------------------
* ``centrality_jump.sigma_multiplier = 2.5`` — k-sigma rule for
  unilateral tail. 2.5 gives ~0.6% false-positive rate under Gaussian
  assumption; we raise it because degree deltas are heavy-tailed, so
  1.96 (95%) would fire constantly.
* ``bridge_outlier.min_communities = 2`` — a cut vertex only matters if
  it separates at least 2 non-trivial communities.
* ``temporal_burst.z_threshold = 3.0`` — standard burst detection
  literature (Kleinberg 2002). z>3 on a 7-day EWMA window is the
  accepted threshold for "meaningful" burst.
* ``angkatan_disjoint.max_path_len = 3`` — layer 9 memory: "angkatan =
  fratellanza a vita". If two officials from DIFFERENT cohorts are 2-3
  hops apart via family/patron edges, this is not a coincidence —
  networks of angkatan loyalty are usually either (a) same-cohort
  (short) or (b) cross-cohort but via many hops through the formal
  structure. A short non-official bridge is unusual.
* ``eigenvector_reverse.lone_hub_min_ratio = 0.75`` — if 75% of a node's
  neighbors have eigenvector score in the bottom quartile of the graph
  while the hub itself is in the top decile, that is
  "compartmentalized dependency" worth investigating.

All defaults err on the side of **precision over recall**. An analyst
reviews alerts by hand; we cannot afford noise. Lower the thresholds
once a known-truth test set exists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - graceful fallback
    yaml = None  # type: ignore[assignment]


DEFAULT_THRESHOLDS: dict[str, dict[str, Any]] = {
    "centrality_jump": {
        # k in "k * sigma over mean" for flagging a node's centrality delta
        "sigma_multiplier": 2.5,
        # Ignore nodes with fewer than N incident edges (noise floor)
        "min_degree": 3,
        # Fraction of edges treated as "recent" (proxy for temporal snapshot)
        "recent_fraction": 0.2,
        # Score floor — below this we don't emit an alert
        "min_score": 0.55,
    },
    "bridge_outlier": {
        "min_communities": 2,
        # Smallest community on EACH side of the cut to count
        "min_community_size": 3,
        "min_score": 0.6,
    },
    "temporal_burst": {
        "z_threshold": 3.0,
        "window_days": 7,
        # EWMA smoothing parameter (0 < alpha <= 1). Lower = longer memory.
        "ewma_alpha": 0.3,
        # Minimum absolute edge count per window to even consider a burst
        "min_edges_in_window": 5,
        # Relationship types that are eligible for burst detection
        "rel_types": ["MET_WITH", "ATTENDED", "PARTICIPATED_IN"],
        # Sources to EXCLUDE (batch ingestion spikes)
        "source_exclude": ["lhkpn", "lhkpn_batch", "ahu_batch"],
        "min_score": 0.6,
    },
    "angkatan_disjoint": {
        "max_path_len": 3,
        # Relationship types considered "non-official" bridges
        "non_official_rels": [
            "KNOWS", "MET_WITH", "MARRIED_TO", "PARENT_OF",
            "SIBLING_OF", "FREQUENTS",
        ],
        # Minimum angkatan distance to be suspicious (years apart)
        "min_angkatan_gap": 3,
        "min_score": 0.6,
    },
    "eigenvector_reverse": {
        "lone_hub_min_ratio": 0.75,
        # Hub must be in top decile of eigenvector centrality
        "hub_top_percentile": 0.90,
        # Neighbors must be in bottom quartile
        "neighbor_bottom_percentile": 0.25,
        "min_neighbors": 4,
        "min_score": 0.6,
    },
}


@dataclass(frozen=True)
class Thresholds:
    """Immutable threshold table. Per-detector access only."""

    table: dict[str, dict[str, Any]] = field(default_factory=dict)

    def for_detector(self, name: str) -> dict[str, Any]:
        """Return a *copy* of the threshold dict for ``name``.

        Returns ``{}`` for unknown detectors — each detector has its
        own class-level defaults anyway.
        """
        return dict(self.table.get(name, {}))


def load_thresholds(path: str | Path | None) -> Thresholds:
    """Load thresholds from YAML with defaults as the base layer.

    If ``path is None`` → returns pure defaults.
    If file exists → deep-merges over defaults (scalars overwrite; dicts
    are merged one level deep).
    If path is provided and file missing → raises FileNotFoundError.
    """
    table: dict[str, dict[str, Any]] = {k: dict(v) for k, v in DEFAULT_THRESHOLDS.items()}
    if path is None:
        return Thresholds(table=table)

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Thresholds YAML not found: {path}")

    if yaml is None:  # pragma: no cover
        raise RuntimeError("PyYAML not installed; cannot load threshold YAML")

    with path.open() as fh:
        loaded = yaml.safe_load(fh) or {}

    if not isinstance(loaded, dict):
        raise ValueError(f"Threshold YAML root must be a mapping, got {type(loaded)}")

    for detector_key, overrides in loaded.items():
        if detector_key not in table:
            table[detector_key] = {}
        if isinstance(overrides, dict):
            table[detector_key].update(overrides)
        else:
            raise ValueError(
                f"Detector '{detector_key}' overrides must be a mapping"
            )

    return Thresholds(table=table)
