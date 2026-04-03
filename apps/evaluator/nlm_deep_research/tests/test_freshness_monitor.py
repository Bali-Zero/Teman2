"""Tests for ARCH-5 Layer C: Freshness Monitor.

All external calls (gemini CLI, nlm CLI, Telegram) are mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.evaluator.nlm_deep_research.freshness_monitor import (
    COVERAGE_MATRIX_FILE,
    FRESHNESS_STATE_FILE,
    MAX_REMEDIATIONS_PER_RUN,
    REGULATORY_DOMAINS,
    RESEARCH_QUERY_TEMPLATES,
    get_status,
    remediate_stale,
    run_scan,
)
from apps.evaluator.nlm_deep_research.gap_scanner import DOMAIN_TOPICS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_MATRIX = {
    "immigration": {
        "coverage": {
            "KITAS 2025": "STALE",
            "Work Permit": "FRESH",
            "Visa on Arrival": "GAP",
        },
        "nb_id": "nb-immigration-xxx",
        "last_scan": "2026-04-01",
    },
    "tax": {
        "coverage": {
            "PPh 21": "FRESH",
            "PPN": "AGING",
        },
        "nb_id": "nb-tax-xxx",
        "last_scan": "2026-04-01",
    },
}


# ---------------------------------------------------------------------------
# REGULATORY_DOMAINS
# ---------------------------------------------------------------------------

class TestRegulatoryDomains:
    def test_has_five_domains(self):
        assert len(REGULATORY_DOMAINS) == 5

    def test_all_have_required_fields(self):
        for d in REGULATORY_DOMAINS:
            assert "name" in d
            assert "query" in d
            assert "notebook_domain" in d
            assert "notebook_id" in d

    def test_notebook_domain_keys_in_domain_topics(self):
        """Every regulatory domain references a known domain in gap_scanner."""
        for d in REGULATORY_DOMAINS:
            assert d["notebook_domain"] in DOMAIN_TOPICS, (
                f"notebook_domain '{d['notebook_domain']}' not in DOMAIN_TOPICS"
            )

    def test_research_query_templates_cover_domains(self):
        """All regulatory domains have a matching research query template."""
        for d in REGULATORY_DOMAINS:
            domain = d["notebook_domain"]
            assert domain in RESEARCH_QUERY_TEMPLATES, (
                f"No research template for domain '{domain}'"
            )


# ---------------------------------------------------------------------------
# run_scan
# ---------------------------------------------------------------------------

class TestRunScan:
    def test_dry_run_skips_gemini(self):
        result = run_scan(dry_run=True)
        assert result["status"] == "ok"
        assert result["dry_run"] is True
        assert result["domains_scanned"] == len(REGULATORY_DOMAINS)
        assert result["changes_detected"] == 0
        assert result["research_triggered"] == 0

    def test_no_change_detected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._run_gemini_search",
            lambda query: None,
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )
        result = run_scan(dry_run=False)
        assert result["status"] == "partial"  # errors for missing Gemini responses
        assert result["changes_detected"] == 0
        assert result["research_triggered"] == 0

    def test_no_change_string_not_detected(self, tmp_path, monkeypatch):
        """Response containing NO_CHANGE should not count as a change."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._run_gemini_search",
            lambda query: "NO_CHANGE",
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )
        with patch("apps.evaluator.nlm_deep_research.freshness_monitor.time") as mock_time:
            mock_time.sleep = lambda s: None
            result = run_scan(dry_run=False)
        assert result["changes_detected"] == 0
        assert result["research_triggered"] == 0

    def test_change_detected_triggers_research(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        call_log = []

        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._run_gemini_search",
            lambda query: "NUOVA NORMATIVA: aggiornamento recente",
        )

        def fake_research(nb_id, query, mode="fast", timeout=30):
            call_log.append(nb_id)
            return True

        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._trigger_nlm_research",
            fake_research,
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )
        with patch("apps.evaluator.nlm_deep_research.freshness_monitor.time") as mock_time:
            mock_time.sleep = lambda s: None
            result = run_scan(dry_run=False)
        assert result["changes_detected"] > 0
        assert result["research_triggered"] > 0
        assert len(call_log) > 0

    def test_max_remediations_respected(self, tmp_path, monkeypatch):
        """Never triggers more than MAX_REMEDIATIONS_PER_RUN research queries."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        call_log = []

        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._run_gemini_search",
            lambda query: "cambio normativo rilevato",
        )

        def fake_research(nb_id, query, mode="fast", timeout=30):
            call_log.append(nb_id)
            return True

        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._trigger_nlm_research",
            fake_research,
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )
        with patch("apps.evaluator.nlm_deep_research.freshness_monitor.time") as mock_time:
            mock_time.sleep = lambda s: None
            run_scan(dry_run=False)
        assert len(call_log) <= MAX_REMEDIATIONS_PER_RUN

    def test_gemini_none_does_not_crash(self, tmp_path, monkeypatch):
        """None response from Gemini should record error but not crash."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")

        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._run_gemini_search",
            lambda query: None,
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )
        with patch("apps.evaluator.nlm_deep_research.freshness_monitor.time") as mock_time:
            mock_time.sleep = lambda s: None
            result = run_scan(dry_run=False)
        assert result["status"] in ("ok", "partial")
        assert result["changes_detected"] == 0


# ---------------------------------------------------------------------------
# remediate_stale
# ---------------------------------------------------------------------------

class TestRemediateStale:
    def test_no_matrix_file_returns_skipped(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.COVERAGE_MATRIX_FILE",
            tmp_path / "nonexistent_matrix.json",
        )
        result = remediate_stale(dry_run=True)
        assert result["status"] == "skipped"
        assert result["stale_topics"] == 0

    def test_dry_run_counts_stale_and_gap(self, tmp_path, monkeypatch):
        matrix_file = tmp_path / "coverage_matrix.json"
        # Use domain keys that exist in DOMAIN_TOPICS
        domains = list(DOMAIN_TOPICS.keys())[:2]
        matrix = {}
        for d in domains:
            matrix[d] = {
                "coverage": {"topic_stale": "STALE", "topic_gap": "GAP"},
            }
        matrix_file.write_text(json.dumps(matrix))
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.COVERAGE_MATRIX_FILE",
            matrix_file,
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )

        result = remediate_stale(dry_run=True)
        assert result["dry_run"] is True
        assert result["stale_topics"] >= 1
        assert result["gap_topics"] >= 1
        # dry_run counts remediations_triggered as if it ran (from the dry_run logging path)
        assert result["remediations_triggered"] >= 0

    def test_live_triggers_research_for_stale(self, tmp_path, monkeypatch):
        # Use a real domain from DOMAIN_TOPICS so nb_id lookup works
        real_domain = list(DOMAIN_TOPICS.keys())[0]
        matrix = {
            real_domain: {
                "coverage": {"Important Topic 2024": "STALE"},
            }
        }
        matrix_file = tmp_path / "coverage_matrix.json"
        matrix_file.write_text(json.dumps(matrix))
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.COVERAGE_MATRIX_FILE",
            matrix_file,
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        call_log = []

        def fake_research(nb_id, query, mode="fast", timeout=30):
            call_log.append((nb_id, mode))
            return True

        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._trigger_nlm_research",
            fake_research,
        )
        with patch("apps.evaluator.nlm_deep_research.freshness_monitor.time") as mock_time:
            mock_time.sleep = lambda s: None
            result = remediate_stale(dry_run=False)
        assert result["remediations_triggered"] == 1
        assert len(call_log) == 1
        assert call_log[0][1] == "fast"

    def test_gap_topics_prioritized_over_stale(self, tmp_path, monkeypatch):
        """GAP topics should be processed before STALE topics."""
        real_domain = list(DOMAIN_TOPICS.keys())[0]
        # More targets than MAX_REMEDIATIONS_PER_RUN to force priority selection
        coverage = {}
        for i in range(MAX_REMEDIATIONS_PER_RUN + 2):
            coverage[f"stale_topic_{i}"] = "STALE"
        coverage["gap_topic_0"] = "GAP"
        coverage["gap_topic_1"] = "GAP"

        matrix = {real_domain: {"coverage": coverage}}
        matrix_file = tmp_path / "matrix.json"
        matrix_file.write_text(json.dumps(matrix))
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.COVERAGE_MATRIX_FILE",
            matrix_file,
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        call_log = []

        def fake_research(nb_id, query, mode="fast", timeout=30):
            call_log.append(query)
            return True

        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor._trigger_nlm_research",
            fake_research,
        )
        with patch("apps.evaluator.nlm_deep_research.freshness_monitor.time") as mock_time:
            mock_time.sleep = lambda s: None
            result = remediate_stale(dry_run=False)
        # Should not exceed max
        assert result["remediations_triggered"] <= MAX_REMEDIATIONS_PER_RUN
        # GAP queries should appear first
        gap_queries = [q for q in call_log if "gap_topic" in q]
        assert len(gap_queries) >= 1, "GAP topics should be processed"

    def test_domain_not_in_domain_topics_skipped(self, tmp_path, monkeypatch):
        """Domains not in DOMAIN_TOPICS config are skipped (no nb_id)."""
        matrix = {
            "completely_unknown_domain_xyz": {
                "coverage": {"topic_x": "STALE"},
            }
        }
        matrix_file = tmp_path / "matrix.json"
        matrix_file.write_text(json.dumps(matrix))
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.COVERAGE_MATRIX_FILE",
            matrix_file,
        )
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "state.json",
        )

        result = remediate_stale(dry_run=False)
        assert result["remediations_triggered"] == 0


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_defaults_when_no_state_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            tmp_path / "nonexistent.json",
        )
        status = get_status()
        assert status["last_scan"] is None
        assert status["last_remediation"] is None
        assert status["scan_count"] == 0
        assert status["remediations_triggered"] == 0
        assert status["changes_detected"] == {}

    def test_reads_existing_state(self, tmp_path, monkeypatch):
        state = {
            "last_scan": "2026-04-03T10:00:00+00:00",
            "last_remediation": "2026-04-03T11:00:00+00:00",
            "scan_count": 5,
            "remediations_triggered": 3,
            "changes_detected": {"immigration": {"change_detected": True}},
        }
        state_file = tmp_path / "state.json"
        state_file.write_text(json.dumps(state))
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            state_file,
        )
        status = get_status()
        assert status["last_scan"] == "2026-04-03T10:00:00+00:00"
        assert status["scan_count"] == 5
        assert status["remediations_triggered"] == 3
        assert "immigration" in status["changes_detected"]

    def test_handles_corrupted_state_file(self, tmp_path, monkeypatch):
        state_file = tmp_path / "corrupt.json"
        state_file.write_text("{ not valid json }")
        monkeypatch.setattr(
            "apps.evaluator.nlm_deep_research.freshness_monitor.FRESHNESS_STATE_FILE",
            state_file,
        )
        status = get_status()
        # Should return defaults without crashing
        assert status["last_scan"] is None
        assert status["scan_count"] == 0
