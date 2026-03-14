"""Tests for SEO Guardian — MEASURE phase."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def agent_dir(tmp_path):
    """Create a temporary agent workspace."""
    (tmp_path / "state.json").write_text(json.dumps({"paused": False}))
    (tmp_path / "memory.jsonl").write_text("")
    return tmp_path


@pytest.fixture
def patch_measure_paths(agent_dir, tmp_path):
    """Patch module-level paths."""
    import apps.evaluator.seo_guardian_measure as mod

    orig = {
        "AGENT_DIR": mod.AGENT_DIR,
        "MEMORY_PATH": mod.MEMORY_PATH,
        "STATE_PATH": mod.STATE_PATH,
        "PROJECT_ROOT": mod.PROJECT_ROOT,
    }

    mod.AGENT_DIR = agent_dir
    mod.MEMORY_PATH = agent_dir / "memory.jsonl"
    mod.STATE_PATH = agent_dir / "state.json"
    mod.PROJECT_ROOT = tmp_path / "project"
    mod.PROJECT_ROOT.mkdir()

    yield mod

    for k, v in orig.items():
        setattr(mod, k, v)


def seed_memory(agent_dir, entries):
    with open(agent_dir / "memory.jsonl", "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class TestPendingMeasurements:
    def test_no_entries_returns_empty(self, patch_measure_paths):
        mod = patch_measure_paths
        assert mod.get_pending_measurements([]) == []

    def test_already_measured_skipped(self, patch_measure_paths):
        mod = patch_measure_paths
        entries = [{"measured": True, "timestamp": "2026-03-10T00:00:00"}]
        assert mod.get_pending_measurements(entries) == []

    def test_dry_run_pending_skipped(self, patch_measure_paths):
        mod = patch_measure_paths
        entries = [{
            "measured": False,
            "dry_run": True,
            "result": {"type": "logged_for_review"},
            "timestamp": "2026-03-10T00:00:00",
        }]
        assert mod.get_pending_measurements(entries) == []

    def test_recent_entry_not_pending(self, patch_measure_paths):
        mod = patch_measure_paths
        entries = [{
            "measured": False,
            "dry_run": False,
            "result": {"success": True},
            "timestamp": datetime.now().isoformat(),
        }]
        assert mod.get_pending_measurements(entries) == []

    def test_old_entry_is_pending(self, patch_measure_paths):
        mod = patch_measure_paths
        old_ts = (datetime.now() - timedelta(hours=49)).isoformat()
        entries = [{
            "measured": False,
            "dry_run": False,
            "result": {"success": True},
            "timestamp": old_ts,
        }]
        assert mod.get_pending_measurements(entries) == [0]


class TestMeasureRun:
    def test_no_pending_returns_no_pending(self, patch_measure_paths):
        mod = patch_measure_paths
        import asyncio
        result = asyncio.run(mod.run_measure())
        assert result["status"] == "no_pending"

    def test_measures_old_indexing_action(self, patch_measure_paths, agent_dir):
        mod = patch_measure_paths
        old_ts = (datetime.now() - timedelta(hours=49)).isoformat()
        entries = [{
            "timestamp": old_ts,
            "action": "submit_indexing_batch",
            "measured": False,
            "dry_run": False,
            "result": {"success": True},
        }]
        seed_memory(agent_dir, entries)

        # Create indexing state
        evaluator_dir = mod.PROJECT_ROOT / "apps" / "evaluator"
        evaluator_dir.mkdir(parents=True)
        (evaluator_dir / "indexing_state.json").write_text(json.dumps({
            "total_submitted": 700,
            "failed": [],
        }))

        import asyncio
        result = asyncio.run(mod.run_measure())
        assert result["status"] == "completed"
        assert result["measured"] == 1

        # Verify entry updated in memory
        updated = mod.load_memory()
        assert updated[0]["measured"] is True
        assert "measurement" in updated[0]
        assert updated[0]["measurement"]["current_submitted"] == 700

    def test_measures_report_anomaly(self, patch_measure_paths, agent_dir):
        mod = patch_measure_paths
        old_ts = (datetime.now() - timedelta(hours=49)).isoformat()
        entries = [{
            "timestamp": old_ts,
            "action": "report_anomaly",
            "measured": False,
            "dry_run": False,
            "result": {"success": True},
        }]
        seed_memory(agent_dir, entries)

        import asyncio
        result = asyncio.run(mod.run_measure())
        assert result["measured"] == 1

        updated = mod.load_memory()
        assert updated[0]["measurement"]["type"] == "report_no_measurement"

    def test_updates_state_after_measure(self, patch_measure_paths, agent_dir):
        mod = patch_measure_paths
        old_ts = (datetime.now() - timedelta(hours=49)).isoformat()
        entries = [{
            "timestamp": old_ts,
            "action": "report_anomaly",
            "measured": False,
            "dry_run": False,
            "result": {"success": True},
        }]
        seed_memory(agent_dir, entries)

        import asyncio
        asyncio.run(mod.run_measure())

        state = json.loads((agent_dir / "state.json").read_text())
        assert "last_measure_run" in state


class TestMemoryIO:
    def test_save_and_load_roundtrip(self, patch_measure_paths, agent_dir):
        mod = patch_measure_paths
        entries = [
            {"action": "a1", "data": "v1"},
            {"action": "a2", "data": "v2"},
        ]
        mod.save_memory(entries)
        loaded = mod.load_memory()
        assert len(loaded) == 2
        assert loaded[0]["action"] == "a1"
        assert loaded[1]["action"] == "a2"
