"""Tests for SEO Guardian — LEARN phase."""

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def agent_dir(tmp_path):
    """Create a temporary agent workspace."""
    (tmp_path / "state.json").write_text(json.dumps({"paused": False}))
    (tmp_path / "memory.jsonl").write_text("")
    (tmp_path / "patterns.json").write_text("[]")
    return tmp_path


@pytest.fixture
def patch_learn_paths(agent_dir):
    """Patch module-level paths."""
    import apps.evaluator.seo_guardian_learn as mod

    orig = {
        "AGENT_DIR": mod.AGENT_DIR,
        "MEMORY_PATH": mod.MEMORY_PATH,
        "PATTERNS_PATH": mod.PATTERNS_PATH,
        "STATE_PATH": mod.STATE_PATH,
    }

    mod.AGENT_DIR = agent_dir
    mod.MEMORY_PATH = agent_dir / "memory.jsonl"
    mod.PATTERNS_PATH = agent_dir / "patterns.json"
    mod.STATE_PATH = agent_dir / "state.json"

    yield mod

    for k, v in orig.items():
        setattr(mod, k, v)


def seed_memory(agent_dir, entries):
    with open(agent_dir / "memory.jsonl", "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


class TestPatternExtraction:
    def test_no_data_returns_no_data(self, patch_learn_paths):
        mod = patch_learn_paths
        result = mod.run_learn()
        assert result["status"] == "no_data"

    def test_insufficient_samples_skipped(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        # Only 3 measured entries — need 5
        entries = [
            {"action": "submit_indexing_batch", "measured": True, "dry_run": False,
             "result": {"success": True}, "timestamp": "2026-03-10T00:00:00"}
            for _ in range(3)
        ]
        seed_memory(agent_dir, entries)

        result = mod.run_learn()
        assert result["patterns_extracted"] == 0

    def test_sufficient_samples_extracts_pattern(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        entries = [
            {"action": "submit_indexing_batch", "measured": True, "dry_run": False,
             "result": {"success": True}, "timestamp": f"2026-03-{10+i}T00:00:00"}
            for i in range(6)
        ]
        seed_memory(agent_dir, entries)

        result = mod.run_learn()
        assert result["patterns_extracted"] == 1
        assert result["patterns"][0]["action"] == "submit_indexing_batch"
        assert result["patterns"][0]["success_rate"] == 1.0
        assert result["patterns"][0]["sample_size"] == 6

    def test_mixed_success_rate(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        entries = []
        for i in range(5):
            entries.append({
                "action": "submit_indexing_batch",
                "measured": True,
                "dry_run": False,
                "result": {"success": i < 3},  # 3 success, 2 failure
                "timestamp": f"2026-03-{10+i}T00:00:00",
            })
        seed_memory(agent_dir, entries)

        result = mod.run_learn()
        assert result["patterns_extracted"] == 1
        assert result["patterns"][0]["success_rate"] == 0.6

    def test_dry_run_entries_excluded(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        entries = [
            {"action": "submit_indexing_batch", "measured": True, "dry_run": True,
             "result": {"success": True}, "timestamp": f"2026-03-{10+i}T00:00:00"}
            for i in range(10)
        ]
        seed_memory(agent_dir, entries)

        result = mod.run_learn()
        assert result["patterns_extracted"] == 0

    def test_unmeasured_entries_excluded(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        entries = [
            {"action": "submit_indexing_batch", "measured": False, "dry_run": False,
             "result": {"success": True}, "timestamp": f"2026-03-{10+i}T00:00:00"}
            for i in range(10)
        ]
        seed_memory(agent_dir, entries)

        result = mod.run_learn()
        # No measured entries → returns no_data status
        assert result["status"] == "no_data"


class TestConfidence:
    def test_high_confidence_recommends_continue(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        entries = [
            {"action": "submit_indexing_batch", "measured": True, "dry_run": False,
             "result": {"success": True}, "timestamp": f"2026-03-{10+i}T00:00:00"}
            for i in range(10)
        ]
        seed_memory(agent_dir, entries)

        result = mod.run_learn()
        assert result["patterns"][0]["recommendation"] == "continue"

    def test_low_confidence_recommends_review(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        # 5 samples, 2 success = 40% rate, confidence will be low
        entries = []
        for i in range(5):
            entries.append({
                "action": "submit_indexing_batch",
                "measured": True,
                "dry_run": False,
                "result": {"success": i < 2},
                "timestamp": f"2026-03-{10+i}T00:00:00",
            })
        seed_memory(agent_dir, entries)

        result = mod.run_learn()
        assert result["patterns"][0]["recommendation"] == "review"


class TestStateUpdate:
    def test_updates_state_after_learn(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        entries = [
            {"action": "submit_indexing_batch", "measured": True, "dry_run": False,
             "result": {"success": True}, "timestamp": f"2026-03-{10+i}T00:00:00"}
            for i in range(6)
        ]
        seed_memory(agent_dir, entries)

        mod.run_learn()

        state = json.loads((agent_dir / "state.json").read_text())
        assert "last_learn_run" in state
        assert state["patterns_count"] == 1

    def test_patterns_saved_to_file(self, patch_learn_paths, agent_dir):
        mod = patch_learn_paths
        entries = [
            {"action": "submit_indexing_batch", "measured": True, "dry_run": False,
             "result": {"success": True}, "timestamp": f"2026-03-{10+i}T00:00:00"}
            for i in range(6)
        ]
        seed_memory(agent_dir, entries)

        mod.run_learn()

        patterns = json.loads((agent_dir / "patterns.json").read_text())
        assert len(patterns) == 1
        assert patterns[0]["action"] == "submit_indexing_batch"
