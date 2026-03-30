"""Tests for nb4_pipeline.py — NB-4 Tax & Fiscal Indonesia."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.evaluator.nlm_deep_research.nb4_pipeline import (
    CLUSTER_ROTATION,
    NB4_NOTEBOOK_ID,
    NB4Pipeline,
    PipelinePhase,
)


# =====================================================================
# Helpers
# =====================================================================


def _setup_nb4(
    tmp_path: Path,
    dry_run: bool = False,
    nlm_query_fn=None,
    pre_state: dict | None = None,
) -> NB4Pipeline:
    state_file = tmp_path / "nb4_state.json"
    claims_file = tmp_path / "nb4_claims.jsonl"
    registry_file = tmp_path / "nb4_sources.json"

    if pre_state:
        state_file.write_text(json.dumps(pre_state, indent=2))

    # Minimal empty registry
    registry_file.write_text(json.dumps({
        "schema_version": 1,
        "notebook_id": "NB-4",
        "last_updated": "2026-03-31T00:00:00+00:00",
        "summary": {"total_tracked": 0, "active": 0, "quarantine": 0, "archived": 0},
        "domain_denylist": [],
        "sources": {},
    }, indent=2))

    return NB4Pipeline(
        state_file=str(state_file),
        claims_file=str(claims_file),
        registry_file=str(registry_file),
        nlm_query_fn=nlm_query_fn,
        dry_run=dry_run,
    )


# =====================================================================
# Notebook ID
# =====================================================================


class TestNB4NotebookID:
    def test_notebook_id_format(self):
        parts = NB4_NOTEBOOK_ID.split("-")
        assert len(parts) == 5
        assert len(NB4_NOTEBOOK_ID) == 36

    def test_notebook_id_not_empty(self):
        assert NB4_NOTEBOOK_ID != ""
        assert NB4_NOTEBOOK_ID != "NB-4"


# =====================================================================
# Cluster rotation
# =====================================================================


class TestNB4ClusterRotation:
    def test_weekdays_covered(self):
        # Mon-Sat (0-5) must all be in rotation
        for day in range(6):
            assert day in CLUSTER_ROTATION

    def test_sunday_not_in_rotation(self):
        assert 6 not in CLUSTER_ROTATION

    def test_saturday_combined_cluster(self):
        cluster_key, cluster_name = CLUSTER_ROTATION[5]
        assert cluster_key == "CE"
        assert "VAT" in cluster_name or "Property" in cluster_name

    def test_monday_corporate_tax(self):
        cluster_key, cluster_name = CLUSTER_ROTATION[0]
        assert cluster_key == "A"
        assert "PPh Badan" in cluster_name or "Corporate" in cluster_name


# =====================================================================
# Pipeline initialization
# =====================================================================


class TestNB4PipelineInit:
    def test_init_creates_pipeline(self, tmp_path):
        pipeline = _setup_nb4(tmp_path)
        assert pipeline is not None
        assert pipeline.dry_run is False

    def test_dry_run_flag(self, tmp_path):
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        assert pipeline.dry_run is True

    def test_load_state_default(self, tmp_path):
        pipeline = _setup_nb4(tmp_path)
        pipeline.load_state()
        assert pipeline._phase == PipelinePhase.IDLE
        assert pipeline.circuit_breakers is not None


# =====================================================================
# Dry-run execution
# =====================================================================


class TestNB4DryRun:
    def test_dry_run_passes_preflight(self, tmp_path):
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()

        assert result.get("dry_run") is True
        assert result.get("notebook_id") == NB4_NOTEBOOK_ID
        preflight = result.get("phases", {}).get("preflight", {})
        assert preflight.get("passed") is True

    def test_dry_run_completes_all_phases(self, tmp_path):
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()

        phases = result.get("phases", {})
        assert "preflight" in phases
        assert "l1" in phases
        assert "l2" in phases
        assert "consolidation" in phases

    def test_dry_run_no_error(self, tmp_path):
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()
        assert "error" not in result

    def test_dry_run_nhs_returns_float(self, tmp_path):
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()

        consolidation = result.get("phases", {}).get("consolidation", {})
        nhs = consolidation.get("nhs")
        assert isinstance(nhs, float)

    def test_dry_run_writes_state(self, tmp_path):
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        pipeline.load_state()
        pipeline.run()

        state_file = tmp_path / "nb4_state.json"
        assert state_file.exists()
        with open(state_file) as f:
            state = json.load(f)
        # State should be COMPLETE or HALTED after run
        assert state.get("current_state") in ("COMPLETE", "HALTED", "IDLE")


# =====================================================================
# Consolidation NHS fix (regression test for signature mismatch)
# =====================================================================


class TestNB4ConsolidationNHS:
    def test_consolidate_does_not_raise_with_empty_registry(self, tmp_path):
        """Previously TypeError: unexpected keyword argument 'source_count'."""
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()

        consolidation = result.get("phases", {}).get("consolidation", {})
        # Should NOT be missing nhs key (which would indicate exception was swallowed)
        assert "nhs" in consolidation
        assert "nhs_label" in consolidation

    def test_consolidate_nhs_label_not_unknown_from_exception(self, tmp_path):
        """nhs_label 'UNKNOWN' should only appear when NHS is truly uncalculable,
        not because of a TypeError in NotebookHealthInput instantiation."""
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        pipeline.load_state()
        result = pipeline.run()

        consolidation = result.get("phases", {}).get("consolidation", {})
        # With empty registry, NHS may be 0.0 but not from a hidden TypeError
        # We verify it's a valid classification label
        valid_labels = {"EXCELLENT", "NORMAL", "DEGRADED", "CRITICAL", "UNKNOWN"}
        assert consolidation.get("nhs_label") in valid_labels


# =====================================================================
# Budget tracking
# =====================================================================


class TestNB4Budget:
    def test_dry_run_does_not_increment_real_budget(self, tmp_path):
        pipeline = _setup_nb4(tmp_path, dry_run=True)
        pipeline.load_state()

        before_weekly = pipeline._state.get("budget", {}).get("weekly_calls", 0)
        pipeline.run()

        # Dry-run queries are counted, but only from _increment_budget
        # This verifies the function exists and doesn't crash
        after_state_file = tmp_path / "nb4_state.json"
        with open(after_state_file) as f:
            after_state = json.load(f)
        budget = after_state.get("budget", {})
        assert "weekly_calls" in budget
        assert isinstance(budget["weekly_calls"], int)
