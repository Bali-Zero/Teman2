"""Tests for ARCH-6: Multi-Modal Content Factory.

All nlm CLI calls are mocked — no real NLM network access.
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from apps.evaluator.nlm_deep_research.multimodal_pipeline import (
    ARTIFACT_META,
    NOTEBOOKS,
    WEEKLY_SCHEDULE,
    MIN_REGEN_INTERVAL,
    RunResult,
    _load_state,
    _save_state,
    _state_key,
    _get_last_generated,
    _record_success,
    generate_artifact,
    get_status,
    get_todays_tasks,
    run_pipeline,
    should_generate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WITA = timezone(timedelta(hours=8))


def _make_state_with_record(
    notebook_key: str,
    artifact_type: str,
    hours_ago: float = 0.0,
) -> dict:
    """Return a state dict with one artifact recorded hours_ago hours."""
    state: dict = {}
    if hours_ago >= 0:
        generated_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        _record_success(state, notebook_key, artifact_type, "/tmp/test.m4a")
        # Overwrite generated_at with our custom time
        key = _state_key(notebook_key, artifact_type)
        state[key]["generated_at"] = generated_at.isoformat()
    return state


# ---------------------------------------------------------------------------
# TestNotebookRegistry
# ---------------------------------------------------------------------------

class TestNotebookRegistry:
    def test_all_notebooks_have_required_keys(self):
        for key, info in NOTEBOOKS.items():
            assert "id" in info, f"{key} missing 'id'"
            assert "label" in info, f"{key} missing 'label'"
            assert "domain" in info, f"{key} missing 'domain'"
            assert len(info["id"]) == 36, f"{key} ID is not a UUID"

    def test_expected_notebooks_present(self):
        for nb in ("nb2", "nb3", "nb4", "nb6", "nb7"):
            assert nb in NOTEBOOKS, f"{nb} missing from NOTEBOOKS"

    def test_all_artifact_meta_present(self):
        for art_type in ("audio", "infographic", "mind-map", "report"):
            assert art_type in ARTIFACT_META
            meta = ARTIFACT_META[art_type]
            assert "download_cmd" in meta
            assert "ext" in meta
            assert "display" in meta


# ---------------------------------------------------------------------------
# TestWeeklySchedule
# ---------------------------------------------------------------------------

class TestWeeklySchedule:
    def test_schedule_has_7_days(self):
        assert len(WEEKLY_SCHEDULE) == 7

    def test_monday_has_nb2_audio(self):
        assert ("nb2", "audio") in WEEKLY_SCHEDULE[0]

    def test_tuesday_has_nb3_mindmap(self):
        assert ("nb3", "mind-map") in WEEKLY_SCHEDULE[1]

    def test_wednesday_has_nb4_infographic(self):
        assert ("nb4", "infographic") in WEEKLY_SCHEDULE[2]

    def test_sunday_is_full_suite(self):
        sun = WEEKLY_SCHEDULE[6]
        assert len(sun) >= 5, "Sunday should have at least 5 tasks"
        audio_nbs = [nb for nb, art in sun if art == "audio"]
        assert len(audio_nbs) >= 3, "Sunday should have multiple audio tasks"

    def test_all_schedule_notebooks_exist(self):
        for day, tasks in WEEKLY_SCHEDULE.items():
            for nb_key, art_type in tasks:
                assert nb_key in NOTEBOOKS, f"Day {day}: {nb_key} not in NOTEBOOKS"
                assert art_type in ARTIFACT_META, f"Day {day}: {art_type} not in ARTIFACT_META"

    def test_get_todays_tasks_monday(self):
        monday = datetime(2026, 4, 6, 10, 0, tzinfo=WITA)  # known Monday
        tasks = get_todays_tasks(now=monday)
        assert ("nb2", "audio") in tasks

    def test_get_todays_tasks_saturday_empty(self):
        saturday = datetime(2026, 4, 11, 10, 0, tzinfo=WITA)  # known Saturday
        tasks = get_todays_tasks(now=saturday)
        assert tasks == []


# ---------------------------------------------------------------------------
# TestStateManagement
# ---------------------------------------------------------------------------

class TestStateManagement:
    def test_record_success_stores_generated_at(self):
        state: dict = {}
        _record_success(state, "nb2", "audio", "/tmp/test.m4a")
        key = _state_key("nb2", "audio")
        assert key in state
        assert "generated_at" in state[key]
        assert state[key]["output_path"] == "/tmp/test.m4a"

    def test_get_last_generated_none_when_empty(self):
        result = _get_last_generated({}, "nb2", "audio")
        assert result is None

    def test_get_last_generated_returns_datetime(self):
        state = _make_state_with_record("nb2", "audio", hours_ago=2.0)
        result = _get_last_generated(state, "nb2", "audio")
        assert result is not None
        assert isinstance(result, datetime)

    def test_get_last_generated_age_matches(self):
        state = _make_state_with_record("nb2", "audio", hours_ago=5.0)
        result = _get_last_generated(state, "nb2", "audio")
        assert result is not None
        age_h = (datetime.now(timezone.utc) - result).total_seconds() / 3600
        assert 4.5 < age_h < 5.5

    def test_state_file_roundtrip(self, tmp_path):
        state_file = tmp_path / "multimodal_state.json"
        state = {"nb2:audio": {"generated_at": "2026-04-01T00:00:00+00:00"}}
        state_file.write_text(json.dumps(state))

        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline.STATE_FILE",
            state_file,
        ):
            loaded = _load_state()
        assert loaded == state


# ---------------------------------------------------------------------------
# TestShouldGenerate
# ---------------------------------------------------------------------------

class TestShouldGenerate:
    def test_never_generated_returns_true(self):
        ok, reason = should_generate({}, "nb2", "audio")
        assert ok is True
        assert "never" in reason

    def test_recent_generation_returns_false(self):
        state = _make_state_with_record("nb2", "audio", hours_ago=1.0)
        ok, reason = should_generate(state, "nb2", "audio")
        assert ok is False
        assert "ago" in reason

    def test_stale_generation_returns_true(self):
        min_hours = MIN_REGEN_INTERVAL.get("audio", 7 * 24)
        state = _make_state_with_record("nb2", "audio", hours_ago=min_hours + 1)
        ok, reason = should_generate(state, "nb2", "audio")
        assert ok is True

    def test_force_overrides_freshness(self):
        state = _make_state_with_record("nb2", "audio", hours_ago=0.0)
        ok, reason = should_generate(state, "nb2", "audio", force=True)
        assert ok is True
        assert reason == "forced"


# ---------------------------------------------------------------------------
# TestGenerateArtifact
# ---------------------------------------------------------------------------

class TestGenerateArtifact:
    def test_unknown_notebook_key_returns_error(self):
        result = generate_artifact("nb99", "audio", {})
        assert result.status == "error"
        assert "Unknown" in result.message

    def test_skipped_when_fresh(self):
        state = _make_state_with_record("nb2", "audio", hours_ago=1.0)
        result = generate_artifact("nb2", "audio", state)
        assert result.status == "skipped"

    def test_dry_run_returns_dry_run_status(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(True, "dry_run"),
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(True, "dry_run"),
        ):
            state: dict = {}
            result = generate_artifact("nb2", "audio", state, dry_run=True)
        assert result.status == "dry_run"

    def test_create_failure_returns_error(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(False, "Connection refused"),
        ):
            state: dict = {}
            result = generate_artifact("nb2", "audio", state, force=True)
        assert result.status == "error"
        assert "create failed" in result.message

    def test_download_failure_returns_error(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(True, "ok"),
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(False, "download timeout"),
        ):
            state: dict = {}
            result = generate_artifact("nb2", "audio", state, force=True)
        assert result.status == "error"
        assert "download failed" in result.message

    def test_successful_generation_records_state(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(True, "ok"),
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(True, "/tmp/test.m4a"),
        ):
            state: dict = {}
            result = generate_artifact("nb2", "audio", state, force=True)
        assert result.status == "ok"
        assert _state_key("nb2", "audio") in state

    def test_successful_generation_returns_output_path(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(True, "ok"),
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(True, "/tmp/out.m4a"),
        ):
            state: dict = {}
            result = generate_artifact("nb2", "audio", state, force=True)
        assert result.output_path is not None
        assert result.latency_s >= 0

    def test_force_bypasses_freshness(self):
        state = _make_state_with_record("nb2", "audio", hours_ago=1.0)
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(True, "ok"),
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(True, "/tmp/out.m4a"),
        ):
            result = generate_artifact("nb2", "audio", state, force=True)
        assert result.status == "ok"


# ---------------------------------------------------------------------------
# TestRunPipeline
# ---------------------------------------------------------------------------

class TestRunPipeline:
    def _patch_generation(self, success: bool = True):
        """Context manager that patches generate_artifact."""
        status = "ok" if success else "error"
        msg = "saved to /tmp/test.m4a" if success else "create failed"
        return patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline.generate_artifact",
            return_value=RunResult("nb2", "audio", status, msg),
        )

    def test_empty_tasks_returns_empty_list(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline.get_todays_tasks",
            return_value=[],
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value={},
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._save_state",
        ):
            results = run_pipeline()
        assert results == []

    def test_explicit_tasks_bypass_schedule(self):
        tasks = [("nb2", "audio")]
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value={},
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._save_state",
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._send_run_summary",
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(True, "ok"),
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(True, "/tmp/test.m4a"),
        ):
            results = run_pipeline(tasks=tasks, force=True)
        assert len(results) == 1
        assert results[0].notebook_key == "nb2"

    def test_multiple_tasks_all_processed(self):
        tasks = [("nb2", "audio"), ("nb3", "mind-map")]
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value={},
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._save_state",
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._send_run_summary",
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(True, "ok"),
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(True, "/tmp/test.bin"),
        ):
            results = run_pipeline(tasks=tasks, force=True)
        assert len(results) == 2

    def test_error_in_one_task_does_not_stop_others(self):
        tasks = [("nb2", "audio"), ("nb3", "audio")]
        call_count = 0

        def fake_create(art_type, nb_id, dry_run=False):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False, "Connection refused"
            return True, "ok"

        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value={},
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._save_state",
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._send_run_summary",
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            side_effect=fake_create,
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(True, "/tmp/test.m4a"),
        ):
            results = run_pipeline(tasks=tasks, force=True)
        assert len(results) == 2
        statuses = [r.status for r in results]
        assert "error" in statuses
        assert "ok" in statuses

    def test_dry_run_all_return_dry_run_status(self):
        tasks = [("nb2", "audio")]
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value={},
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._save_state",
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._send_run_summary",
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_create",
            return_value=(True, "dry_run"),
        ), patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._run_nlm_download",
            return_value=(True, "dry_run"),
        ):
            results = run_pipeline(tasks=tasks, dry_run=True)
        assert all(r.status == "dry_run" for r in results)


# ---------------------------------------------------------------------------
# TestGetStatus
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_status_returns_all_notebooks(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value={},
        ):
            status = get_status()
        for nb_key in NOTEBOOKS:
            assert nb_key in status

    def test_status_shows_never_for_empty_state(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value={},
        ):
            status = get_status()
        for nb_key in NOTEBOOKS:
            for art_type in ARTIFACT_META:
                assert status[nb_key]["artifacts"][art_type]["last_generated"] is None
                assert status[nb_key]["artifacts"][art_type]["age"] == "never"
                assert status[nb_key]["artifacts"][art_type]["fresh"] is False

    def test_status_shows_fresh_for_recent_generation(self):
        state: dict = {}
        _record_success(state, "nb2", "audio", "/tmp/test.m4a")
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value=state,
        ):
            status = get_status()
        assert status["nb2"]["artifacts"]["audio"]["fresh"] is True
        assert status["nb2"]["artifacts"]["audio"]["last_generated"] is not None

    def test_status_labels_match_notebooks(self):
        with patch(
            "apps.evaluator.nlm_deep_research.multimodal_pipeline._load_state",
            return_value={},
        ):
            status = get_status()
        for nb_key, nb_info in NOTEBOOKS.items():
            assert status[nb_key]["label"] == nb_info["label"]


# ---------------------------------------------------------------------------
# TestNlmCreateCommands
# ---------------------------------------------------------------------------

class TestNlmCreateCommands:
    """Verify that the correct nlm CLI commands are built for each artifact type."""

    def _capture_create_cmd(self, artifact_type: str, notebook_id: str = "test-nb-id") -> list[str]:
        """Run _run_nlm_create and capture the subprocess command."""
        captured = []

        def fake_run(cmd, **kwargs):
            captured.append(cmd)
            m = MagicMock()
            m.returncode = 0
            m.stdout = "ok"
            m.stderr = ""
            return m

        with patch("subprocess.run", side_effect=fake_run):
            from apps.evaluator.nlm_deep_research.multimodal_pipeline import _run_nlm_create
            _run_nlm_create(artifact_type, notebook_id)

        return captured[0] if captured else []

    def test_audio_uses_audio_create(self):
        cmd = self._capture_create_cmd("audio")
        assert "audio" in cmd
        assert "create" in cmd
        assert "--confirm" in cmd

    def test_report_uses_report_create(self):
        cmd = self._capture_create_cmd("report")
        assert "report" in cmd
        assert "create" in cmd

    def test_unknown_artifact_type_returns_false(self):
        from apps.evaluator.nlm_deep_research.multimodal_pipeline import _run_nlm_create
        ok, msg = _run_nlm_create("unknown_type", "some-id")
        assert ok is False

    def test_dry_run_does_not_call_subprocess(self):
        with patch("subprocess.run") as mock_run:
            from apps.evaluator.nlm_deep_research.multimodal_pipeline import _run_nlm_create
            ok, msg = _run_nlm_create("audio", "some-id", dry_run=True)
        mock_run.assert_not_called()
        assert ok is True
        assert msg == "dry_run"
