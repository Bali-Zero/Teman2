"""Tests for pipeline.py — dry-run, preflight, phase execution, NLMPipeline."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.evaluator.nlm_deep_research.pipeline import (
    CLUSTER_ROTATION,
    DegradationLevel,
    NLMPipeline,
    PipelinePhase,
)


# =====================================================================
# Helpers
# =====================================================================


def _setup_pipeline(
    tmp_path: Path,
    dry_run: bool = False,
    nlm_query_fn=None,
    pre_state: dict | None = None,
    pre_registry: dict | None = None,
) -> NLMPipeline:
    """Create a pipeline with temporary files and optional pre-seeded data."""
    state_file = tmp_path / "pipeline_state.json"
    claims_file = tmp_path / "claims.jsonl"
    registry_file = tmp_path / "sources.json"

    if pre_state:
        state_file.write_text(json.dumps(pre_state, indent=2))

    if pre_registry is None:
        pre_registry = _minimal_registry()
    registry_file.write_text(json.dumps(pre_registry, indent=2))

    pipeline = NLMPipeline(
        state_file=str(state_file),
        claims_file=str(claims_file),
        registry_file=str(registry_file),
        nlm_query_fn=nlm_query_fn,
        dry_run=dry_run,
    )
    return pipeline


def _minimal_registry() -> dict:
    """Create a minimal valid source registry with master digests."""
    sources = {}
    for i in range(5):
        sources[f"MD-{i:03d}"] = {
            "stage": "ACTIVE",
            "status": "ACTIVE",
            "category": "master_digest",
            "source_type": "MASTER_DIGEST",
            "title": f"Master Digest {i}",
            "url": f"https://imigrasi.go.id/md-{i}",
            "tier": 0,
            "tier_label": "T0",
            "language": "id",
            "scores": {"svs_total": 0.85, "times_cited": 3, "claims_backed": ["c1"]},
            "dates": {"published": "2026-03-01"},
            "flags": {"pinned": True},
            "dedup": {},
        }
    for i in range(10):
        sources[f"SRC-{i:03d}"] = {
            "stage": "ACTIVE",
            "status": "ACTIVE",
            "category": "canonical",
            "source_type": "REGULATION",
            "title": f"Source {i}",
            "url": f"https://kemenkumham.go.id/src-{i}",
            "tier": 2,
            "tier_label": "T2",
            "language": "id",
            "scores": {"svs_total": 0.60, "times_cited": 1, "claims_backed": []},
            "dates": {"published": "2026-03-15"},
            "flags": {},
            "dedup": {},
        }
    return {
        "schema_version": 1,
        "notebook_id": "NB-2",
        "last_updated": "2026-03-28T00:00:00+00:00",
        "summary": {"total_tracked": 15, "active": 15, "quarantine": 0, "archived": 0},
        "domain_denylist": ["tripadvisor.com", "balizero.com"],
        "sources": sources,
    }


def _make_nlm_query_fn(success: bool = True, answer: str = "Test answer"):
    """Create a mock NLM query function."""
    def mock_fn(notebook_id, query, conversation_id=None):
        if success:
            return {
                "status": "success",
                "answer": answer,
                "sources_used": ["SRC-001", "SRC-002"],
                "conversation_id": conversation_id or "conv-test",
            }
        else:
            return {
                "status": "error",
                "error": "NLM API timeout",
            }
    return mock_fn


# =====================================================================
# PipelinePhase and DegradationLevel enums
# =====================================================================


class TestEnums:
    """Tests for pipeline enums."""

    def test_pipeline_phases(self):
        assert PipelinePhase.IDLE.value == "IDLE"
        assert PipelinePhase.PREFLIGHT.value == "PREFLIGHT"
        assert PipelinePhase.HALTED.value == "HALTED"
        assert PipelinePhase.COMPLETE.value == "COMPLETE"

    def test_degradation_levels(self):
        assert DegradationLevel.NOMINAL.value == "NOMINAL"
        assert DegradationLevel.HALTED.value == "HALTED"

    def test_cluster_rotation_weekdays(self):
        assert len(CLUSTER_ROTATION) == 5  # Mon-Fri
        for day in range(5):
            letter, name = CLUSTER_ROTATION[day]
            assert letter in "ABCDE"
            assert len(name) > 0


# =====================================================================
# Pipeline state management
# =====================================================================


class TestPipelineState:
    """Tests for load_state and save_state."""

    def test_load_creates_default_state(self, tmp_path):
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        pipeline.load_state()
        assert pipeline._state.get("schema_version") == 1
        assert pipeline._phase == PipelinePhase.IDLE

    def test_load_from_existing_state(self, tmp_path):
        pre_state = {
            "schema_version": 1,
            "current_state": "COMPLETE",
            "degradation_level": "NOMINAL",
            "budget": {"daily_queries": 2, "weekly_calls": 10},
            "previous_claims_count": 50,
            "circuit_breakers": {},
        }
        pipeline = _setup_pipeline(tmp_path, dry_run=True, pre_state=pre_state)
        pipeline.load_state()
        assert pipeline._state.get("budget", {}).get("weekly_calls") == 10

    def test_save_state_creates_file(self, tmp_path):
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        pipeline.load_state()
        pipeline.save_state()
        state_path = Path(pipeline.state_file)
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert "current_state" in data
        assert "circuit_breakers" in data

    def test_save_preserves_budget(self, tmp_path):
        pre_state = {
            "schema_version": 1,
            "budget": {"daily_queries": 5, "weekly_calls": 15},
            "circuit_breakers": {},
        }
        pipeline = _setup_pipeline(tmp_path, dry_run=True, pre_state=pre_state)
        pipeline.load_state()
        pipeline.save_state()
        data = json.loads(Path(pipeline.state_file).read_text())
        assert data["budget"]["weekly_calls"] == 15


# =====================================================================
# Dry-run execution
# =====================================================================


class TestDryRun:
    """Tests for pipeline dry-run mode."""

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_dry_run_completes(self, mock_wita, tmp_path):
        # Set to a weekday within deadline
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()
        assert result["dry_run"] is True
        assert "run_id" in result
        assert "phases" in result

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_dry_run_preflight_passes(self, mock_wita, tmp_path):
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()
        assert result["phases"]["preflight"]["passed"] is True

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_dry_run_skips_nlm_calls(self, mock_wita, tmp_path):
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()
        if "l1" in result.get("phases", {}):
            l1 = result["phases"]["l1"]
            assert l1.get("success") is True
            assert "[DRY RUN]" in l1.get("answer", "")


# =====================================================================
# Preflight checks
# =====================================================================


class TestPreflight:
    """Tests for the 12-point preflight checklist."""

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_weekend_blocks_non_dryrun(self, mock_wita, tmp_path):
        # Saturday
        mock_wita.return_value = datetime(2026, 3, 28, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=False, nlm_query_fn=_make_nlm_query_fn())
        pipeline.load_state()
        result = pipeline.run()
        assert result.get("halted_at") == "preflight"

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_past_deadline_blocks_non_dryrun(self, mock_wita, tmp_path):
        # 03:00 WITA on Thursday
        mock_wita.return_value = datetime(2026, 3, 26, 3, 0, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=False, nlm_query_fn=_make_nlm_query_fn())
        pipeline.load_state()
        result = pipeline.run()
        assert result.get("halted_at") == "preflight"

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_no_query_fn_blocks_non_dryrun(self, mock_wita, tmp_path):
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=False, nlm_query_fn=None)
        pipeline.load_state()
        result = pipeline.run()
        assert result.get("halted_at") == "preflight"

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_budget_exhausted_blocks(self, mock_wita, tmp_path):
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pre_state = {
            "schema_version": 1,
            "budget": {"daily_queries": 0, "weekly_calls": 50},
            "circuit_breakers": {},
        }
        pipeline = _setup_pipeline(
            tmp_path, dry_run=False,
            nlm_query_fn=_make_nlm_query_fn(),
            pre_state=pre_state,
        )
        pipeline.load_state()
        result = pipeline.run()
        assert result.get("halted_at") == "preflight"


# =====================================================================
# Full pipeline with mock NLM
# =====================================================================


class TestPipelineWithMockNLM:
    """Tests for full pipeline execution with a mocked NLM query."""

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_successful_run(self, mock_wita, tmp_path):
        # Thursday 01:30 WITA
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        answer = (
            "Berdasarkan Peraturan Pemerintah Nomor 34 Tahun 2021 pasal 12 ayat 3, "
            "prosedur pengajuan RPTKA telah diperbarui melalui sistem TKA Online yang berlaku sejak Januari 2026.\n"
        )
        pipeline = _setup_pipeline(
            tmp_path,
            dry_run=False,
            nlm_query_fn=_make_nlm_query_fn(success=True, answer=answer),
        )
        pipeline.load_state()
        result = pipeline.run()
        assert "error" not in result
        assert result["phases"]["preflight"]["passed"] is True

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_nlm_failure_recorded(self, mock_wita, tmp_path):
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(
            tmp_path,
            dry_run=False,
            nlm_query_fn=_make_nlm_query_fn(success=False),
        )
        pipeline.load_state()
        result = pipeline.run()
        # L1 failed => circuit breaker should have recorded failure
        assert pipeline.circuit_breakers.nlm.failure_count >= 1

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_state_saved_after_run(self, mock_wita, tmp_path):
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        pipeline.load_state()
        pipeline.run()
        # State file should exist after run (save_state called in finally)
        assert Path(pipeline.state_file).exists()

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_exception_in_query_recorded_as_failure(self, mock_wita, tmp_path):
        """When the NLM query function raises, _run_query catches it and
        returns success=False, which triggers circuit breaker failure recording."""
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))

        def exploding_fn(**kwargs):
            raise RuntimeError("Connection refused")

        pipeline = _setup_pipeline(
            tmp_path,
            dry_run=False,
            nlm_query_fn=exploding_fn,
        )
        pipeline.load_state()
        result = pipeline.run()
        # Exception is caught inside _run_query, so L1 returns success=False
        l1 = result.get("phases", {}).get("l1", {})
        assert l1.get("success") is False
        # Circuit breaker should have recorded the failure
        assert pipeline.circuit_breakers.nlm.failure_count >= 1

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_elapsed_time_recorded(self, mock_wita, tmp_path):
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()
        assert "elapsed_seconds" in result
        assert result["elapsed_seconds"] >= 0

    @patch("apps.evaluator.nlm_deep_research.pipeline._now_wita")
    def test_cluster_in_summary(self, mock_wita, tmp_path):
        # Thursday = day 3 = cluster D
        mock_wita.return_value = datetime(2026, 3, 26, 1, 30, tzinfo=timezone(timedelta(hours=8)))
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()
        if result["phases"]["preflight"]["passed"]:
            assert "cluster" in result
            assert result["cluster"] in "ABCDE"


# =====================================================================
# Pipeline — _build_query
# =====================================================================


class TestBuildQuery:
    """Tests for query template building."""

    def test_l1_templates_exist_for_all_clusters(self, tmp_path):
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        for cluster_letter in "ABCDE":
            query = pipeline._build_query("L1", cluster_letter)
            assert len(query) > 50
            assert "dokumen sumber" in query.lower() or "sumber" in query.lower()

    def test_l2_templates_exist_for_all_clusters(self, tmp_path):
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        for cluster_letter in "ABCDE":
            query = pipeline._build_query("L2", cluster_letter)
            assert len(query) > 50

    def test_l3_generic_template(self, tmp_path):
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        query = pipeline._build_query("L3", "A")
        assert "Cluster A" in query

    def test_unknown_cluster_falls_back(self, tmp_path):
        pipeline = _setup_pipeline(tmp_path, dry_run=True)
        query = pipeline._build_query("L1", "Z")
        # Should fall back to cluster A template
        assert len(query) > 50
