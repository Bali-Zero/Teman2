"""Tests for baseline_builder — assembles 00_baseline.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from backend.services.research.baseline_builder import (
    BaselineBuilder,
    BaselineSnapshot,
)


def test_snapshot_counts_metrics_correctly():
    snap = BaselineSnapshot(
        captured_at="2026-04-22T10:00:00Z",
        gsc={"clicks_total": 1500, "impressions_total": 45000, "query_count": 320, "ctr_pct": 3.3},
        ga4={"sessions_total": 2800, "conversions_total": 12, "page_count": 410, "bounce_rate": 0.42},
        instagram={"followers_count": 5123, "media_count": 245, "engagement_rate": 0.021},
        brevo={"total_subscribers": 932, "avg_open_rate": 0.34, "avg_click_rate": 0.04, "bounce_rate": 0.15},
        ahrefs={"domain_rating": 28, "backlinks_count": 1850, "sov_pct": 4.2, "ai_citations_30d": 6, "estimated_traffic": 3200},
        crm={"leads_total_90d": 6, "leads_social_90d": 2, "utm_coverage_pct": 0.35, "conversion_rate": 0.08},
    )
    assert snap.metric_count() >= 20


def test_build_and_persist_writes_valid_json(tmp_path: Path):
    builder = BaselineBuilder(output_dir=tmp_path)
    snap = BaselineSnapshot(
        captured_at="2026-04-22T10:00:00Z",
        gsc={"clicks_total": 100, "impressions_total": 5000, "query_count": 50},
        ga4={"sessions_total": 300, "conversions_total": 1, "page_count": 40},
        instagram={"followers_count": 5000, "media_count": 200},
        brevo={"total_subscribers": 800, "avg_open_rate": 0.3, "avg_click_rate": 0.03},
        ahrefs={"domain_rating": 25, "backlinks_count": 1200, "sov_pct": 3.0, "ai_citations_30d": 2},
        crm={"leads_total_90d": 3, "leads_social_90d": 1, "utm_coverage_pct": 0.2},
    )
    path = builder.build_and_persist(snap)
    assert path.name == "00_baseline.json"
    data = json.loads(path.read_text())
    assert data["captured_at"] == "2026-04-22T10:00:00Z"
    # persist test focuses on schema + file write; Gate 1 invariant is
    # covered by test_snapshot_counts_metrics_correctly which uses a
    # ≥20-metric sample.
    assert snap.metric_count() == 18  # sanity: this fixture is below Gate 1
    # All nested dicts present
    assert set(data.keys()) == {"captured_at", "gsc", "ga4", "instagram", "brevo", "ahrefs", "crm"}


def test_metric_count_excludes_nonnumeric_values():
    snap = BaselineSnapshot(
        captured_at="2026-04-22T10:00:00Z",
        gsc={"clicks_total": 100, "notes": "anomaly"},
        ga4={"sessions_total": 200},
        instagram={"followers_count": 500},
        brevo={"total_subscribers": 100},
        ahrefs={"domain_rating": 20},
        crm={"leads_total_90d": 1},
    )
    # Only 6 numeric metrics → should fail Gate 1
    assert snap.metric_count() == 6
