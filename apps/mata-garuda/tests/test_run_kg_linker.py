"""Tests for scripts/run_kg_linker._track_dead_upstream — W4 cicatrix 2026-05-22."""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path


def _import_runner(repo_root: Path):
    """Import the runner module, ensuring sys.path is set up."""
    scripts_dir = repo_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import run_kg_linker
    importlib.reload(run_kg_linker)
    return run_kg_linker


def test_track_dead_upstream_increments_on_zero_entities(tmp_path: Path, monkeypatch):
    """Run that processed >0 items but extracted 0 entities must
    increment the persistent counter."""
    repo_root = Path(__file__).resolve().parent.parent
    runner = _import_runner(repo_root)
    monkeypatch.setattr(runner, "_STREAK_PATH", tmp_path / "streak.json")
    monkeypatch.setattr(runner, "_STREAK_THRESHOLD", 99)

    dead = {"processed": 10, "linked": 0, "skipped_no_entities": 10,
            "entities_total": 0, "relations_total": 0}
    runner._track_dead_upstream(dead)
    runner._track_dead_upstream(dead)

    assert (tmp_path / "streak.json").exists()
    assert json.loads((tmp_path / "streak.json").read_text())["count"] == 2


def test_track_dead_upstream_logs_warning_at_threshold(tmp_path, monkeypatch, caplog):
    """At threshold, runner must emit a logger.warning with the
    diagnostic message about the upstream pipeline."""
    import logging
    repo_root = Path(__file__).resolve().parent.parent
    runner = _import_runner(repo_root)
    monkeypatch.setattr(runner, "_STREAK_PATH", tmp_path / "streak.json")
    monkeypatch.setattr(runner, "_STREAK_THRESHOLD", 2)

    dead = {"processed": 5, "linked": 0, "skipped_no_entities": 5,
            "entities_total": 0, "relations_total": 0}

    with caplog.at_level(logging.WARNING, logger="kg_linker_runner"):
        runner._track_dead_upstream(dead)
        caplog.clear()
        runner._track_dead_upstream(dead)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    assert "dead-upstream alert" in msg
    assert "2 consecutive" in msg
    assert "ner_worker pipeline" in msg


def test_track_dead_upstream_resets_on_healthy_run(tmp_path, monkeypatch):
    """A run that extracts entities>0 deletes the counter so the next
    failure starts fresh from 1."""
    repo_root = Path(__file__).resolve().parent.parent
    runner = _import_runner(repo_root)
    monkeypatch.setattr(runner, "_STREAK_PATH", tmp_path / "streak.json")
    monkeypatch.setattr(runner, "_STREAK_THRESHOLD", 99)

    dead = {"processed": 5, "linked": 0, "skipped_no_entities": 5,
            "entities_total": 0, "relations_total": 0}
    healthy = {"processed": 5, "linked": 5, "skipped_no_entities": 0,
               "entities_total": 12, "relations_total": 8}

    runner._track_dead_upstream(dead)
    runner._track_dead_upstream(dead)
    assert (tmp_path / "streak.json").exists()

    runner._track_dead_upstream(healthy)
    assert not (tmp_path / "streak.json").exists()


def test_track_dead_upstream_idle_run_does_not_increment(tmp_path, monkeypatch):
    """A run with processed==0 (genuinely empty stream) must NOT bump
    the counter — there's nothing to judge. Counter should be unchanged."""
    repo_root = Path(__file__).resolve().parent.parent
    runner = _import_runner(repo_root)
    monkeypatch.setattr(runner, "_STREAK_PATH", tmp_path / "streak.json")
    monkeypatch.setattr(runner, "_STREAK_THRESHOLD", 99)

    # Prime counter with 1 dead run.
    dead = {"processed": 5, "linked": 0, "skipped_no_entities": 5,
            "entities_total": 0, "relations_total": 0}
    runner._track_dead_upstream(dead)
    assert json.loads((tmp_path / "streak.json").read_text())["count"] == 1

    # Idle run — no upstream signal, leave counter alone.
    idle = {"processed": 0, "linked": 0, "skipped_no_entities": 0,
            "entities_total": 0, "relations_total": 0}
    runner._track_dead_upstream(idle)
    # File still exists at count=1 (no increment, no reset).
    assert (tmp_path / "streak.json").exists()
    assert json.loads((tmp_path / "streak.json").read_text())["count"] == 1
