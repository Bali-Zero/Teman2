"""Threshold loader: defaults + YAML override + per-detector access."""
from __future__ import annotations

from pathlib import Path

import pytest

from osint_nexus.anomaly.thresholds import (
    DEFAULT_THRESHOLDS,
    Thresholds,
    load_thresholds,
)


def test_default_thresholds_has_all_5_detectors():
    for key in [
        "centrality_jump",
        "bridge_outlier",
        "temporal_burst",
        "angkatan_disjoint",
        "eigenvector_reverse",
    ]:
        assert key in DEFAULT_THRESHOLDS


def test_load_thresholds_returns_defaults_when_no_file():
    t = load_thresholds(path=None)
    assert isinstance(t, Thresholds)
    assert t.for_detector("centrality_jump") == DEFAULT_THRESHOLDS["centrality_jump"]


def test_load_thresholds_merges_yaml_over_defaults(tmp_path: Path):
    yaml_text = """
centrality_jump:
  sigma_multiplier: 5.0
eigenvector_reverse:
  lone_hub_min_ratio: 0.9
"""
    p = tmp_path / "th.yaml"
    p.write_text(yaml_text)
    t = load_thresholds(path=p)

    # Override applied
    assert t.for_detector("centrality_jump")["sigma_multiplier"] == 5.0
    # Defaults still present for unset keys
    default_min_degree = DEFAULT_THRESHOLDS["centrality_jump"]["min_degree"]
    assert t.for_detector("centrality_jump")["min_degree"] == default_min_degree
    # Partial override on a different detector
    assert t.for_detector("eigenvector_reverse")["lone_hub_min_ratio"] == 0.9


def test_load_thresholds_missing_file_raises(tmp_path: Path):
    p = tmp_path / "does-not-exist.yaml"
    with pytest.raises(FileNotFoundError):
        load_thresholds(path=p)


def test_for_detector_unknown_returns_empty_dict():
    t = load_thresholds(path=None)
    # Unknown detectors return empty dict — detectors can fall back to
    # their own class-level defaults.
    assert t.for_detector("does_not_exist") == {}
