"""Tests for NLM Source Snapshot + Rollback System (ARCH-8).

All subprocess calls are mocked — no real nlm CLI is needed.
"""

import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from apps.evaluator.nlm_deep_research.source_snapshot import (
    SNAPSHOTS_DIR,
    _parse_source_list,
    cleanup_old_snapshots,
    diff_snapshots,
    pipeline_snapshot_guard,
    rollback_to_snapshot,
    take_snapshot,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOTEBOOK_ID = "cff93ab0-813a-42f2-a8de-36987e724271"
NOTEBOOK_LABEL = "immigration"

SAMPLE_SOURCES = [
    {"source_id": "src-001", "title": "Visa Regulations 2025", "type": "url"},
    {"source_id": "src-002", "title": "KITAS Guide", "type": "url"},
    {"source_id": "src-003", "title": "Work Permit FAQ", "type": "text"},
]

SAMPLE_SOURCES_AFTER = [
    {"source_id": "src-001", "title": "Visa Regulations 2025", "type": "url"},
    {"source_id": "src-002", "title": "KITAS Guide", "type": "url"},
    {"source_id": "src-003", "title": "Work Permit FAQ", "type": "text"},
    {"source_id": "src-004", "title": "CAPTCHA Error Page", "type": "url"},
    {"source_id": "src-005", "title": "Bad Decomposition Result", "type": "text"},
]


def _make_nlm_output(sources: list) -> str:
    """Create mock nlm CLI JSON output."""
    return json.dumps(sources)


def _make_completed_process(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Create a mock subprocess.CompletedProcess."""
    cp = MagicMock()
    cp.stdout = stdout
    cp.stderr = stderr
    cp.returncode = returncode
    return cp


@pytest.fixture
def tmp_snapshots(tmp_path, monkeypatch):
    """Override SNAPSHOTS_DIR to use a temp directory."""
    snap_dir = tmp_path / "snapshots"
    snap_dir.mkdir()
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.source_snapshot.SNAPSHOTS_DIR",
        snap_dir,
    )
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.source_snapshot.ROLLBACK_LOG",
        snap_dir / "rollback_log.jsonl",
    )
    return snap_dir


@pytest.fixture
def tmp_heartbeat(tmp_path, monkeypatch):
    """Override HEARTBEAT_DIR to use a temp directory."""
    hb_dir = tmp_path / "heartbeat"
    hb_dir.mkdir()
    monkeypatch.setattr(
        "apps.evaluator.nlm_deep_research.source_snapshot.HEARTBEAT_DIR",
        hb_dir,
    )
    return hb_dir


# ---------------------------------------------------------------------------
# Tests: _parse_source_list
# ---------------------------------------------------------------------------


class TestParseSourceList:
    """Tests for parsing nlm source list output."""

    def test_parse_plain_list(self):
        raw = json.dumps(SAMPLE_SOURCES)
        result = _parse_source_list(raw)
        assert len(result) == 3
        assert result[0]["source_id"] == "src-001"
        assert result[1]["title"] == "KITAS Guide"
        assert result[2]["type"] == "text"

    def test_parse_value_wrapped(self):
        raw = json.dumps({"value": SAMPLE_SOURCES})
        result = _parse_source_list(raw)
        assert len(result) == 3

    def test_parse_sources_key(self):
        raw = json.dumps({"sources": SAMPLE_SOURCES})
        result = _parse_source_list(raw)
        assert len(result) == 3

    def test_parse_empty(self):
        assert _parse_source_list("") == []
        assert _parse_source_list("[]") == []

    def test_parse_alternative_keys(self):
        """Test with 'id' and 'name' instead of 'source_id' and 'title'."""
        alt_sources = [
            {"id": "alt-1", "name": "Alt Source", "source_type": "pdf"},
        ]
        result = _parse_source_list(json.dumps(alt_sources))
        assert len(result) == 1
        assert result[0]["source_id"] == "alt-1"
        assert result[0]["title"] == "Alt Source"
        assert result[0]["type"] == "pdf"

    def test_parse_skips_empty_ids(self):
        sources = [
            {"source_id": "", "title": "No ID", "type": "url"},
            {"source_id": "valid-1", "title": "Valid", "type": "url"},
        ]
        result = _parse_source_list(json.dumps(sources))
        assert len(result) == 1
        assert result[0]["source_id"] == "valid-1"


# ---------------------------------------------------------------------------
# Tests: take_snapshot
# ---------------------------------------------------------------------------


class TestTakeSnapshot:
    """Tests for take_snapshot function."""

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_creates_snapshot_file(self, mock_run, tmp_snapshots):
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        path = take_snapshot(NOTEBOOK_ID, NOTEBOOK_LABEL)

        assert path.exists()
        assert path.parent == tmp_snapshots
        assert NOTEBOOK_LABEL in path.name
        assert "_pre_" in path.name
        assert path.suffix == ".json"

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_snapshot_content(self, mock_run, tmp_snapshots):
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        path = take_snapshot(NOTEBOOK_ID, NOTEBOOK_LABEL)
        data = json.loads(path.read_text())

        assert data["notebook_id"] == NOTEBOOK_ID
        assert data["label"] == NOTEBOOK_LABEL
        assert data["source_count"] == 3
        assert len(data["sources"]) == 3
        assert "timestamp" in data

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_calls_nlm_source_list(self, mock_run, tmp_snapshots):
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        take_snapshot(NOTEBOOK_ID, NOTEBOOK_LABEL)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "nlm"
        assert cmd[1] == "source"
        assert cmd[2] == "list"
        assert cmd[3] == NOTEBOOK_ID

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_raises_on_nlm_failure(self, mock_run, tmp_snapshots):
        mock_run.return_value = _make_completed_process(
            returncode=1,
            stderr="Authentication failed",
        )

        with pytest.raises(RuntimeError, match="Authentication failed"):
            take_snapshot(NOTEBOOK_ID, NOTEBOOK_LABEL)

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_snapshot_empty_notebook(self, mock_run, tmp_snapshots):
        mock_run.return_value = _make_completed_process(stdout="[]")

        path = take_snapshot(NOTEBOOK_ID, NOTEBOOK_LABEL)
        data = json.loads(path.read_text())

        assert data["source_count"] == 0
        assert data["sources"] == []


# ---------------------------------------------------------------------------
# Tests: diff_snapshots
# ---------------------------------------------------------------------------


class TestDiffSnapshots:
    """Tests for diff_snapshots function."""

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_no_changes(self, mock_run, tmp_snapshots):
        # Create a snapshot file
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        # Current state is the same
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        diff = diff_snapshots(snap_path, NOTEBOOK_ID)

        assert diff["added"] == []
        assert diff["removed"] == []
        assert diff["unchanged_count"] == 3

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_sources_added(self, mock_run, tmp_snapshots):
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        # Current state has 2 extra sources
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES_AFTER),
        )

        diff = diff_snapshots(snap_path, NOTEBOOK_ID)

        assert len(diff["added"]) == 2
        added_ids = {s["source_id"] for s in diff["added"]}
        assert "src-004" in added_ids
        assert "src-005" in added_ids
        assert diff["removed"] == []
        assert diff["unchanged_count"] == 3

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_sources_removed(self, mock_run, tmp_snapshots):
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        # Current state has only 1 source left
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output([SAMPLE_SOURCES[0]]),
        )

        diff = diff_snapshots(snap_path, NOTEBOOK_ID)

        assert diff["added"] == []
        assert len(diff["removed"]) == 2
        removed_ids = {s["source_id"] for s in diff["removed"]}
        assert "src-002" in removed_ids
        assert "src-003" in removed_ids
        assert diff["unchanged_count"] == 1

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_mixed_changes(self, mock_run, tmp_snapshots):
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        # src-003 removed, src-004 added
        after = [
            SAMPLE_SOURCES[0],
            SAMPLE_SOURCES[1],
            {"source_id": "src-004", "title": "New Source", "type": "url"},
        ]
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(after),
        )

        diff = diff_snapshots(snap_path, NOTEBOOK_ID)

        assert len(diff["added"]) == 1
        assert diff["added"][0]["source_id"] == "src-004"
        assert len(diff["removed"]) == 1
        assert diff["removed"][0]["source_id"] == "src-003"
        assert diff["unchanged_count"] == 2


# ---------------------------------------------------------------------------
# Tests: rollback_to_snapshot
# ---------------------------------------------------------------------------


class TestRollbackToSnapshot:
    """Tests for rollback_to_snapshot function."""

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_dry_run_no_deletes(self, mock_run, tmp_snapshots):
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        # Current state has extra sources
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES_AFTER),
        )

        result = rollback_to_snapshot(NOTEBOOK_ID, snap_path, dry_run=True)

        assert result["dry_run"] is True
        assert result["rolled_back"] == 0
        assert len(result["details"]) == 2
        for d in result["details"]:
            assert d["status"] == "would_delete"

        # Only one call: source list. No deletes in dry run.
        assert mock_run.call_count == 1

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_live_rollback_deletes_added(self, mock_run, tmp_snapshots):
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        def side_effect(cmd, **kwargs):
            if cmd[1] == "source" and cmd[2] == "list":
                return _make_completed_process(
                    stdout=_make_nlm_output(SAMPLE_SOURCES_AFTER),
                )
            elif cmd[1] == "source" and cmd[2] == "delete":
                return _make_completed_process(stdout='{"status": "deleted"}')
            return _make_completed_process()

        mock_run.side_effect = side_effect

        result = rollback_to_snapshot(NOTEBOOK_ID, snap_path, dry_run=False)

        assert result["dry_run"] is False
        assert result["rolled_back"] == 2
        assert len(result["details"]) == 2
        for d in result["details"]:
            assert d["status"] == "deleted"

        # 1 source list + 2 deletes = 3 calls
        assert mock_run.call_count == 3

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_rollback_logs_to_jsonl(self, mock_run, tmp_snapshots):
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        rollback_to_snapshot(NOTEBOOK_ID, snap_path, dry_run=True)

        log_path = tmp_snapshots / "rollback_log.jsonl"
        assert log_path.exists()
        log_entry = json.loads(log_path.read_text().strip())
        assert log_entry["notebook_id"] == NOTEBOOK_ID
        assert log_entry["dry_run"] is True

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_rollback_nothing_to_do(self, mock_run, tmp_snapshots):
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        result = rollback_to_snapshot(NOTEBOOK_ID, snap_path, dry_run=False)

        assert result["rolled_back"] == 0
        assert result["details"] == []

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_rollback_partial_failure(self, mock_run, tmp_snapshots):
        """Test rollback when one delete succeeds and one fails."""
        snapshot_data = {
            "notebook_id": NOTEBOOK_ID,
            "sources": SAMPLE_SOURCES,
        }
        snap_path = tmp_snapshots / "test_snap.json"
        snap_path.write_text(json.dumps(snapshot_data))

        call_count = 0

        def side_effect(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if cmd[1] == "source" and cmd[2] == "list":
                return _make_completed_process(
                    stdout=_make_nlm_output(SAMPLE_SOURCES_AFTER),
                )
            elif cmd[1] == "source" and cmd[2] == "delete":
                # First delete succeeds, second fails
                if cmd[4] == "src-004":
                    return _make_completed_process(stdout='{"status": "deleted"}')
                else:
                    return _make_completed_process(
                        returncode=1,
                        stderr="Rate limited",
                    )
            return _make_completed_process()

        mock_run.side_effect = side_effect

        result = rollback_to_snapshot(NOTEBOOK_ID, snap_path, dry_run=False)

        assert result["rolled_back"] == 1  # only one succeeded
        statuses = {d["source_id"]: d["status"] for d in result["details"]}
        assert statuses["src-004"] == "deleted"
        assert statuses["src-005"] == "error"


# ---------------------------------------------------------------------------
# Tests: cleanup_old_snapshots
# ---------------------------------------------------------------------------


class TestCleanupOldSnapshots:
    """Tests for cleanup_old_snapshots function."""

    def test_cleanup_keeps_recent(self, tmp_snapshots):
        # Create 10 snapshots for "immigration"
        for i in range(10):
            f = tmp_snapshots / f"immigration_pre_2026-04-{i+1:02d}_01-10.json"
            f.write_text("{}")
            # Set modification time to ensure ordering
            os.utime(f, (time.time() - (10 - i) * 86400, time.time() - (10 - i) * 86400))

        result = cleanup_old_snapshots(max_per_notebook=7)

        assert len(result["deleted"]) == 3
        assert result["kept"] == 7

        # Verify the 7 most recent survive
        remaining = list(tmp_snapshots.glob("immigration_pre_*.json"))
        assert len(remaining) == 7

    def test_cleanup_multiple_notebooks(self, tmp_snapshots):
        # Create snapshots for two notebooks
        for i in range(5):
            f1 = tmp_snapshots / f"immigration_pre_2026-04-{i+1:02d}_01-10.json"
            f1.write_text("{}")
            os.utime(f1, (time.time() - (5 - i) * 86400, time.time() - (5 - i) * 86400))

            f2 = tmp_snapshots / f"company_pre_2026-04-{i+1:02d}_01-10.json"
            f2.write_text("{}")
            os.utime(f2, (time.time() - (5 - i) * 86400, time.time() - (5 - i) * 86400))

        result = cleanup_old_snapshots(max_per_notebook=3)

        assert len(result["deleted"]) == 4  # 2 from each
        assert result["kept"] == 6  # 3 from each

    def test_cleanup_no_snapshots(self, tmp_snapshots):
        result = cleanup_old_snapshots(max_per_notebook=7)
        assert result["deleted"] == []
        assert result["kept"] == 0

    def test_cleanup_ignores_non_snapshot_files(self, tmp_snapshots):
        # Create a non-snapshot file
        (tmp_snapshots / "rollback_log.jsonl").write_text("{}")
        (tmp_snapshots / "random.txt").write_text("hello")
        # Create one snapshot
        (tmp_snapshots / "immigration_pre_2026-04-01_01-10.json").write_text("{}")

        result = cleanup_old_snapshots(max_per_notebook=7)

        assert result["deleted"] == []
        assert result["kept"] == 1

    def test_cleanup_under_limit(self, tmp_snapshots):
        """No deletions when count is within limit."""
        for i in range(3):
            f = tmp_snapshots / f"immigration_pre_2026-04-{i+1:02d}_01-10.json"
            f.write_text("{}")

        result = cleanup_old_snapshots(max_per_notebook=7)

        assert result["deleted"] == []
        assert result["kept"] == 3


# ---------------------------------------------------------------------------
# Tests: pipeline_snapshot_guard
# ---------------------------------------------------------------------------


class TestPipelineSnapshotGuard:
    """Tests for the pipeline_snapshot_guard context manager."""

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_success_path(self, mock_run, tmp_snapshots, tmp_heartbeat):
        """Pipeline succeeds — snapshot + change record + heartbeat ok."""
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        with pipeline_snapshot_guard(
            NOTEBOOK_ID, NOTEBOOK_LABEL, "test_pipeline"
        ) as ctx:
            assert "snapshot_path" in ctx
            assert ctx["snapshot_path"].exists()

        # Check change record was written
        change_files = list(tmp_snapshots.glob("*.changes.json"))
        assert len(change_files) == 1
        change_data = json.loads(change_files[0].read_text())
        assert change_data["status"] == "success"
        assert change_data["added"] == 0

        # Check heartbeat
        hb = tmp_heartbeat / "test_pipeline.last.json"
        assert hb.exists()
        hb_data = json.loads(hb.read_text())
        assert hb_data["status"] == "ok"

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_failure_with_new_sources_triggers_rollback(
        self, mock_run, tmp_snapshots, tmp_heartbeat
    ):
        """Pipeline fails after adding sources — auto-rollback."""
        call_idx = 0

        def side_effect(cmd, **kwargs):
            nonlocal call_idx
            call_idx += 1

            if cmd[1] == "source" and cmd[2] == "list":
                # First call: pre-snapshot (3 sources)
                # Second call: post-pipeline diff (5 sources — 2 were added)
                # Third call: rollback source list (5 sources)
                if call_idx <= 1:
                    return _make_completed_process(
                        stdout=_make_nlm_output(SAMPLE_SOURCES),
                    )
                else:
                    return _make_completed_process(
                        stdout=_make_nlm_output(SAMPLE_SOURCES_AFTER),
                    )
            elif cmd[1] == "source" and cmd[2] == "delete":
                return _make_completed_process(stdout='{"status": "deleted"}')
            return _make_completed_process()

        mock_run.side_effect = side_effect

        with pytest.raises(ValueError, match="Pipeline broke"):
            with pipeline_snapshot_guard(
                NOTEBOOK_ID, NOTEBOOK_LABEL, "test_pipeline"
            ) as ctx:
                raise ValueError("Pipeline broke")

        # Check heartbeat indicates rollback
        hb = tmp_heartbeat / "test_pipeline.last.json"
        hb_data = json.loads(hb.read_text())
        assert hb_data["status"] == "failed_rollback"
        assert "sources_rolled_back" in hb_data

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_failure_without_new_sources_no_rollback(
        self, mock_run, tmp_snapshots, tmp_heartbeat
    ):
        """Pipeline fails but no sources were added — no rollback."""
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        with pytest.raises(RuntimeError, match="Timeout"):
            with pipeline_snapshot_guard(
                NOTEBOOK_ID, NOTEBOOK_LABEL, "test_pipeline"
            ) as ctx:
                raise RuntimeError("Timeout")

        hb = tmp_heartbeat / "test_pipeline.last.json"
        hb_data = json.loads(hb.read_text())
        assert hb_data["status"] == "failed"
        assert "Timeout" in hb_data["error"]

        # No rollback log should have delete entries
        log_path = tmp_snapshots / "rollback_log.jsonl"
        if log_path.exists():
            lines = log_path.read_text().strip().split("\n")
            for line in lines:
                entry = json.loads(line)
                assert entry.get("sources_deleted", 0) == 0

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_snapshot_failure_raises_immediately(
        self, mock_run, tmp_snapshots, tmp_heartbeat
    ):
        """If pre-snapshot fails, error is raised before pipeline runs."""
        mock_run.return_value = _make_completed_process(
            returncode=1,
            stderr="Auth expired",
        )

        with pytest.raises(RuntimeError, match="Auth expired"):
            with pipeline_snapshot_guard(
                NOTEBOOK_ID, NOTEBOOK_LABEL, "test_pipeline"
            ) as ctx:
                # This line should never be reached
                pytest.fail("Pipeline body should not execute")

        # Heartbeat should be written as failed
        hb = tmp_heartbeat / "test_pipeline.last.json"
        hb_data = json.loads(hb.read_text())
        assert hb_data["status"] == "failed"

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_context_receives_snapshot_path(self, mock_run, tmp_snapshots, tmp_heartbeat):
        """The yielded context dict contains snapshot_path."""
        mock_run.return_value = _make_completed_process(
            stdout=_make_nlm_output(SAMPLE_SOURCES),
        )

        with pipeline_snapshot_guard(
            NOTEBOOK_ID, NOTEBOOK_LABEL, "test_pipeline"
        ) as ctx:
            snap_path = ctx["snapshot_path"]
            assert isinstance(snap_path, Path)
            assert snap_path.exists()
            data = json.loads(snap_path.read_text())
            assert data["notebook_id"] == NOTEBOOK_ID

    @patch("apps.evaluator.nlm_deep_research.source_snapshot.subprocess.run")
    def test_success_records_source_counts(
        self, mock_run, tmp_snapshots, tmp_heartbeat
    ):
        """On success, change record contains correct source counts."""
        call_idx = 0

        def side_effect(cmd, **kwargs):
            nonlocal call_idx
            call_idx += 1
            if call_idx == 1:
                # Pre-snapshot: 3 sources
                return _make_completed_process(
                    stdout=_make_nlm_output(SAMPLE_SOURCES),
                )
            else:
                # Post-pipeline diff: 4 sources (1 added)
                after = SAMPLE_SOURCES + [
                    {"source_id": "src-new", "title": "Legit New Source", "type": "url"},
                ]
                return _make_completed_process(
                    stdout=_make_nlm_output(after),
                )

        mock_run.side_effect = side_effect

        with pipeline_snapshot_guard(
            NOTEBOOK_ID, NOTEBOOK_LABEL, "test_pipeline"
        ) as ctx:
            pass  # Pipeline succeeds

        change_files = list(tmp_snapshots.glob("*.changes.json"))
        change_data = json.loads(change_files[0].read_text())
        assert change_data["added"] == 1
        assert change_data["unchanged"] == 3
        assert change_data["removed"] == 0
