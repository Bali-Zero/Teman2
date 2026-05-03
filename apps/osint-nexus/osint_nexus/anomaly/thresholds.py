"""Threshold management — loads from YAML config with sensible defaults.

All magic numbers live here so they can be tuned without touching detector code.
Each threshold has a comment explaining its calibration rationale.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Default thresholds per detector.
# These are conservative starting points — calibrate against real data.
DEFAULTS: dict[str, dict[str, Any]] = {
    # ── centrality_jump ──
    # Proxy: fraction of edges that are "recent" (created within window_days).
    # A node with >40% recent edges and degree above median signals sudden
    # importance growth. 40% chosen because organic growth rarely exceeds 20%
    # in a 30-day window for established nodes.
    "centrality_jump": {
        "window_days": 30,
        "recent_edge_fraction_threshold": 0.40,
        "min_degree": 5,
        "min_recent_edges": 3,
    },
    # ── bridge_outlier ──
    # A node is a bridge outlier if removing it increases the number of
    # weakly connected components. min_community_size filters noise from
    # tiny clusters. bridge_score_threshold filters low-impact bridges.
    "bridge_outlier": {
        "min_community_size": 3,
        "bridge_score_threshold": 0.5,
    },
    # ── temporal_burst ──
    # EWMA with span=30 days. z_threshold=3.0 means the 7-day count must
    # exceed 3 standard deviations above the EWMA. Chosen because z>3
    # corresponds to p<0.003 under normality — very unlikely by chance.
    # min_baseline_days ensures we have enough history for a stable EWMA.
    "temporal_burst": {
        "window_days": 7,
        "ewma_span_days": 30,
        "z_threshold": 3.0,
        "min_baseline_days": 14,
        "edge_types": [
            "MET_WITH",
            "ATTENDED",
            "WON_CONTRACT",
            "PROMOTED_TO",
            "POSTED_TO",
        ],
    },
    # ── angkatan_disjoint_alliance ──
    # Two officials from different angkatan connected by short path through
    # non-official edges is suspicious because angkatan loyalty is the
    # dominant alliance structure (Layer 9). max_path_length=3 because
    # 4+ hops dilute the signal. Only non-official edge types count.
    "angkatan_disjoint_alliance": {
        "max_path_length": 3,
        "non_official_edge_types": [
            "MARRIED_TO",
            "PARENT_OF",
            "SIBLING_OF",
            "PATRON_OF",
            "KNOWS",
            "FREQUENTS",
            "MEMBER_OF",
        ],
        "min_angkatan_gap": 1,
    },
    # ── eigenvector_reverse ──
    # A node with eigenvector centrality in the top 10% whose 1-hop
    # neighbors ALL have eigenvector below the 25th percentile.
    # This signals compartmentalization: the node is important but
    # deliberately isolated from other important nodes.
    "eigenvector_reverse": {
        "top_percentile": 0.10,
        "neighbor_max_percentile": 0.25,
        "min_neighbors": 2,
    },
}


def load_thresholds(config_path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load thresholds from YAML file, merging with defaults.

    If no config_path is provided or the file doesn't exist, returns defaults.
    YAML keys override defaults; unspecified keys keep default values.
    """
    merged = {k: dict(v) for k, v in DEFAULTS.items()}

    if config_path is None:
        return merged

    config_path = Path(config_path)
    if not config_path.exists():
        return merged

    try:
        import yaml

        with open(config_path) as f:
            user_config = yaml.safe_load(f) or {}

        for detector_name, overrides in user_config.items():
            if detector_name in merged and isinstance(overrides, dict):
                merged[detector_name].update(overrides)

    except ImportError:
        # PyYAML not installed — use defaults
        pass

    return merged
