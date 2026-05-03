"""Tests for SEO Guardian Agent — DECIDE + ACT."""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


# We need to patch paths before importing the module
@pytest.fixture
def agent_dir(tmp_path):
    """Create a temporary agent workspace with all required files."""
    config = {
        "decide": {
            "risk_levels": {
                "LOW": ["submit_indexing_batch", "update_meta_description", "report_anomaly"],
                "MEDIUM": ["add_faq_schema", "modify_article_metadata", "create_redirect"],
                "HIGH": ["edit_article_body", "remove_page", "change_url_structure"],
            },
            "max_actions_per_run": {"LOW": 10, "MEDIUM": 3},
        }
    }

    state = {
        "paused": False,
        "last_observe_run": None,
        "baseline": {"total_kbli_pages": 1563, "kbli_indexed": 700},
        "current_metrics": {},
    }

    corrections = [
        {"rule": "never_touch", "scope": "/lifestyle/*", "reason": "owner preference"},
        {"rule": "max_indexing_batch", "scope": "kbli_indexing_submit.py", "value": 50},
        {"rule": "no_content_edit", "scope": "/kbli/*", "reason": "SSG pages"},
    ]

    (tmp_path / "config.yaml").write_text(yaml.dump(config))
    (tmp_path / "state.json").write_text(json.dumps(state))
    (tmp_path / "patterns.json").write_text("[]")
    (tmp_path / "memory.jsonl").write_text("")
    (tmp_path / "decisions.log").write_text("")

    with open(tmp_path / "corrections.jsonl", "w") as f:
        for c in corrections:
            f.write(json.dumps(c) + "\n")

    return tmp_path


@pytest.fixture
def patch_agent_paths(agent_dir):
    """Patch all module-level paths to use tmp dir."""
    import apps.evaluator.seo_guardian_agent as mod

    orig = {
        "AGENT_DIR": mod.AGENT_DIR,
        "CONFIG_PATH": mod.CONFIG_PATH,
        "STATE_PATH": mod.STATE_PATH,
        "PATTERNS_PATH": mod.PATTERNS_PATH,
        "CORRECTIONS_PATH": mod.CORRECTIONS_PATH,
        "MEMORY_PATH": mod.MEMORY_PATH,
        "DECISIONS_LOG": mod.DECISIONS_LOG,
    }

    mod.AGENT_DIR = agent_dir
    mod.CONFIG_PATH = agent_dir / "config.yaml"
    mod.STATE_PATH = agent_dir / "state.json"
    mod.PATTERNS_PATH = agent_dir / "patterns.json"
    mod.CORRECTIONS_PATH = agent_dir / "corrections.jsonl"
    mod.MEMORY_PATH = agent_dir / "memory.jsonl"
    mod.DECISIONS_LOG = agent_dir / "decisions.log"

    yield mod

    # Restore
    for k, v in orig.items():
        setattr(mod, k, v)


class TestKillSwitch:
    def test_paused_returns_paused_status(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        state = json.loads((agent_dir / "state.json").read_text())
        state["paused"] = True
        (agent_dir / "state.json").write_text(json.dumps(state))

        import asyncio
        result = asyncio.run(mod.run_agent(dry_run=True))
        assert result["status"] == "paused"

    def test_unpaused_runs_normally(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        import asyncio
        result = asyncio.run(mod.run_agent(dry_run=True))
        assert result["status"] == "completed"

    def test_paused_logs_decision(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        state = json.loads((agent_dir / "state.json").read_text())
        state["paused"] = True
        (agent_dir / "state.json").write_text(json.dumps(state))

        import asyncio
        asyncio.run(mod.run_agent(dry_run=True))

        log = (agent_dir / "decisions.log").read_text()
        assert "PAUSED" in log


class TestCorrections:
    def test_never_touch_blocks_lifestyle(self, patch_agent_paths):
        mod = patch_agent_paths
        result = mod.check_corrections("update_meta_description", "/lifestyle/driving")
        assert result is not None
        assert "never_touch" in result

    def test_never_touch_allows_other_scope(self, patch_agent_paths):
        mod = patch_agent_paths
        result = mod.check_corrections("update_meta_description", "/services/visa")
        assert result is None

    def test_no_content_edit_blocks_kbli(self, patch_agent_paths):
        mod = patch_agent_paths
        result = mod.check_corrections("update_meta_description", "/kbli/47911")
        assert result is not None
        assert "no_content_edit" in result

    def test_no_content_edit_allows_non_kbli(self, patch_agent_paths):
        mod = patch_agent_paths
        result = mod.check_corrections("update_meta_description", "/services/company")
        assert result is None

    def test_max_indexing_batch_default(self, patch_agent_paths):
        mod = patch_agent_paths
        assert mod.get_max_indexing_batch() == 50

    def test_max_indexing_batch_from_corrections(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        # Rewrite with different value
        corrections = [
            {"rule": "max_indexing_batch", "scope": "kbli_indexing_submit.py", "value": 25},
        ]
        with open(agent_dir / "corrections.jsonl", "w") as f:
            for c in corrections:
                f.write(json.dumps(c) + "\n")

        assert mod.get_max_indexing_batch() == 25


class TestRiskClassification:
    def test_low_risk_actions(self, patch_agent_paths):
        mod = patch_agent_paths
        assert mod.classify_risk("submit_indexing_batch") == "LOW"
        assert mod.classify_risk("update_meta_description") == "LOW"
        assert mod.classify_risk("report_anomaly") == "LOW"

    def test_medium_risk_actions(self, patch_agent_paths):
        mod = patch_agent_paths
        assert mod.classify_risk("add_faq_schema") == "MEDIUM"
        assert mod.classify_risk("modify_article_metadata") == "MEDIUM"

    def test_high_risk_actions(self, patch_agent_paths):
        mod = patch_agent_paths
        assert mod.classify_risk("edit_article_body") == "HIGH"
        assert mod.classify_risk("remove_page") == "HIGH"

    def test_unknown_defaults_to_high(self, patch_agent_paths):
        mod = patch_agent_paths
        assert mod.classify_risk("some_unknown_action") == "HIGH"


class TestDecideAct:
    def test_high_risk_skipped(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        # Create observe data with HIGH risk opportunity
        observe_data = {
            "opportunities": [
                {"type": "content_edit", "suggested_action": "edit_article_body", "query": "test"}
            ]
        }
        (agent_dir / "last_observe.json").write_text(json.dumps(observe_data))

        import asyncio
        result = asyncio.run(mod.run_agent(dry_run=True))
        assert result["actions_skipped"] == 1
        assert result["actions_taken"] == 0

    def test_low_risk_executed(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        observe_data = {
            "opportunities": [
                {"type": "ctr_optimization", "suggested_action": "report_anomaly", "query": "test", "current_ctr": 0, "current_position": 15}
            ]
        }
        (agent_dir / "last_observe.json").write_text(json.dumps(observe_data))

        import asyncio
        result = asyncio.run(mod.run_agent(dry_run=True))
        assert result["actions_taken"] == 1

        # Verify memory entry written
        memory = (agent_dir / "memory.jsonl").read_text().strip()
        assert len(memory) > 0
        entry = json.loads(memory)
        assert entry["action"] == "report_anomaly"
        assert entry["risk"] == "LOW"
        assert entry["git_sha"] is None
        assert entry["measured"] is False

    def test_max_low_limit_respected(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        # Create 15 LOW opportunities — should stop at 10
        observe_data = {
            "opportunities": [
                {"type": "ctr", "suggested_action": "report_anomaly", "query": f"q{i}", "current_ctr": 0, "current_position": 15}
                for i in range(15)
            ]
        }
        (agent_dir / "last_observe.json").write_text(json.dumps(observe_data))

        import asyncio
        result = asyncio.run(mod.run_agent(dry_run=True))
        assert result["actions_taken"] == 10
        assert result["actions_skipped"] == 5

    def test_blocked_by_correction_logged(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        observe_data = {
            "opportunities": [
                {"type": "ctr", "suggested_action": "update_meta_description", "query": "/lifestyle/driving"}
            ]
        }
        (agent_dir / "last_observe.json").write_text(json.dumps(observe_data))

        import asyncio
        result = asyncio.run(mod.run_agent(dry_run=True))
        assert result["actions_blocked"] == 1

    def test_medium_logged_as_pending(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        observe_data = {
            "opportunities": [
                {"type": "schema", "suggested_action": "add_faq_schema", "query": "test"}
            ]
        }
        (agent_dir / "last_observe.json").write_text(json.dumps(observe_data))

        import asyncio
        result = asyncio.run(mod.run_agent(dry_run=True))
        assert result["actions_taken"] == 1

        entry = json.loads((agent_dir / "memory.jsonl").read_text().strip())
        assert entry["risk"] == "MEDIUM"
        assert entry["result"]["type"] == "pending_confirmation"


class TestUtilities:
    def test_load_json_missing_file(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        result = mod.load_json(agent_dir / "nonexistent.json")
        assert result == {}

    def test_load_jsonl_missing_file(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        result = mod.load_jsonl(agent_dir / "nonexistent.jsonl")
        assert result == []

    def test_append_jsonl(self, patch_agent_paths, agent_dir):
        mod = patch_agent_paths
        path = agent_dir / "test.jsonl"
        mod.append_jsonl(path, {"key": "value1"})
        mod.append_jsonl(path, {"key": "value2"})

        entries = mod.load_jsonl(path)
        assert len(entries) == 2
        assert entries[0]["key"] == "value1"
        assert entries[1]["key"] == "value2"
