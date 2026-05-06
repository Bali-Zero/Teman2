"""Tests for Codex autonomy status rendering in AUTOMATIONS_REFERENCE."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import generate_automations_reference as gen  # noqa: E402


def _job(label: str) -> gen.Job:
    return gen.Job(
        name=label.replace(".", "_"),
        machine="Pro",
        kind="launchagent",
        schedule="RunAtLoad",
        command=label,
        plist_label=label,
        last_status="✅ OK",
        exit_code="0",
    )


def test_codex_state_key_matches_launchagent_label() -> None:
    job = _job("com.nuzantara.codex-coverage-improver")
    assert gen._codex_state_key_for_job(job) == "codex_com_nuzantara_codex_coverage_improver"


def test_load_codex_automation_states_ignores_malformed_json(tmp_path: Path) -> None:
    good = tmp_path / "codex_com_nuzantara_codex_coverage_improver.state.json"
    good.write_text(
        json.dumps(
            {
                "job": "com.nuzantara.codex-coverage-improver",
                "outcome": "action",
                "action": "pr_opened",
                "message": "opened PR",
                "ts": 1778069000.0,
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "codex_bad.state.json").write_text("{bad", encoding="utf-8")

    states = gen._load_codex_automation_states(tmp_path)

    assert set(states) == {"codex_com_nuzantara_codex_coverage_improver"}
    assert states["codex_com_nuzantara_codex_coverage_improver"]["action"] == "pr_opened"


def test_apply_codex_state_distinguishes_idle_action_skipped_and_blocked() -> None:
    jobs = [
        _job("com.nuzantara.codex-autofix-ci"),
        _job("com.nuzantara.codex-coverage-improver"),
        _job("com.nuzantara.codex-research-actor"),
        _job("com.nuzantara.codex-overnight-runner"),
    ]
    states = {
        "codex_com_nuzantara_codex_autofix_ci": {
            "outcome": "idle",
            "action": "no_failed_runs",
            "message": "No failed runs found",
            "ts": 1778069000.0,
        },
        "codex_com_nuzantara_codex_coverage_improver": {
            "outcome": "action",
            "action": "fallback_commit",
            "message": "Committed tests written by Codex",
            "ts": 1778069001.0,
        },
        "codex_com_nuzantara_codex_research_actor": {
            "outcome": "skipped",
            "action": "dirty_worktree",
            "message": "runtime worktree dirty",
            "ts": 1778069002.0,
        },
        "codex_com_nuzantara_codex_overnight_runner": {
            "outcome": "blocked",
            "action": "queue_empty",
            "message": "Queue empty",
            "ts": 1778069003.0,
        },
    }

    for job in jobs:
        gen._apply_codex_automation_state(job, states)

    assert jobs[0].autonomy_status == "✅ OK/idle"
    assert jobs[1].autonomy_status == "✅ ACTION"
    assert jobs[2].autonomy_status == "⚠️ SKIPPED"
    assert jobs[3].autonomy_status == "⛔ BLOCKED"
    assert jobs[1].notes == "Committed tests written by Codex"
