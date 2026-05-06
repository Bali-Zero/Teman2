"""Tests for nb_monitor.report."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from mata_garuda.scripts.nb_monitor.report import (
    ReportEntry,
    render_weekly_report,
    iso_year_week,
)
from mata_garuda.scripts.nb_monitor.tier import Tier


def _entry(**over) -> ReportEntry:
    base = dict(
        rank=1,
        uuid="1ed02e54-542f-426a-94f8-53c5ffde4b7d",
        name="NB-INTEL-Immigration",
        tier=Tier.ALIVE,
        read_freq_7d=120,
        read_freq_30d=480,
        delta_7d_vs_lastweek=10,
        age_days=30,
        skill_derivation_count=None,
        downstream_cite_rate=None,
        source_freshness_age_days=15,
        push_success_rate=0.99,
        instrumentation_status="ok",
    )
    base.update(over)
    return ReportEntry(**base)


def test_iso_year_week_format():
    assert iso_year_week(datetime(2026, 5, 7, tzinfo=timezone.utc)) == "2026-W19"


def test_render_weekly_report_includes_header():
    md = render_weekly_report(
        [_entry()],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "# NB Mitochondrial Value Monitor — 2026-W19" in md
    assert "Baseline period" in md


def test_render_weekly_report_includes_ranking_table():
    md = render_weekly_report(
        [_entry(), _entry(rank=2, uuid="x", name="NB-2", read_freq_7d=80)],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "| rank |" in md
    assert "NB-INTEL-Immigration" in md
    assert "NB-2" in md
    assert "120" in md
    assert "80" in md


def test_render_weekly_report_includes_diagnostic_block():
    md = render_weekly_report(
        [_entry()],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "<details>" in md
    assert "Diagnostic columns" in md
    assert "skill_derivation_count" in md
    assert "downstream_cite_rate" in md


def test_render_weekly_report_omits_baseline_after_window():
    md = render_weekly_report(
        [_entry()],
        generated_at=datetime(2026, 5, 30, tzinfo=timezone.utc),
        baseline_window=False,
    )
    assert "Baseline period" not in md


def test_render_weekly_report_renders_na_for_none_metrics():
    md = render_weekly_report(
        [
            _entry(
                skill_derivation_count=None,
                downstream_cite_rate=None,
                source_freshness_age_days=None,
            )
        ],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "N/A" in md


def test_render_weekly_report_handles_empty_entries():
    md = render_weekly_report(
        [],
        generated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        baseline_window=True,
    )
    assert "no entries" in md.lower() or "0 NB" in md
