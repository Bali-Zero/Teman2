"""W62 ANTIBODY #3 — CI hygiene gate for the agent worktree broker.

Two responsibilities:

1. **Live guard** — fail the PR if the real `.worktrees/` tree in this checkout
   contains a worktree older than 24h (a true orphan the broker never reaped).
   Runs against the repo root, on a fresh CI checkout where no live agent
   session exists, so strictness yields no false positives.

2. **Detector unit tests** — exercise `find_stale_worktrees` against a synthetic
   `.worktrees/` so the threshold logic (created_at primary, dir-mtime fallback)
   is covered independently of whatever happens to be on disk.

The detector lives in `scripts/agent_start.py` so test and the live guard share
one implementation (no drift between what CI checks and what `--cleanup` reaps).
"""
from __future__ import annotations

import importlib.util
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "agent_start.py"


def _load_broker(worktrees_dir: Path):
    spec = importlib.util.spec_from_file_location("agent_start_ci", SCRIPT_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = worktrees_dir.parent
    mod.WORKTREES_DIR = worktrees_dir
    return mod


def _write_metadata(wt: Path, *, created_minutes_ago: int, ttl: int = 60) -> None:
    wt.mkdir(parents=True, exist_ok=True)
    created = datetime.now(timezone.utc) - timedelta(minutes=created_minutes_ago)
    (wt / ".agent-task.json").write_text(
        json.dumps(
            {
                "task_id": wt.name,
                "lane": "infra",
                "branch": f"agent/test/infra/{wt.name}",
                "host": "test",
                "created_at": created.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ttl_minutes": ttl,
                "pid": 0,
                "base_branch": "main",
                "worktree_path": str(wt),
            }
        )
    )


# ---------------------------------------------------------------------------
# Detector unit tests
# ---------------------------------------------------------------------------


def test_detector_flags_worktree_older_than_24h(tmp_path):
    wtd = tmp_path / ".worktrees"
    mod = _load_broker(wtd)
    _write_metadata(wtd / "infra-old", created_minutes_ago=25 * 60)
    stale = mod.find_stale_worktrees(wtd)
    assert [name for name, _ in stale] == ["infra-old"]


def test_detector_ignores_fresh_worktree(tmp_path):
    wtd = tmp_path / ".worktrees"
    mod = _load_broker(wtd)
    _write_metadata(wtd / "infra-fresh", created_minutes_ago=30)
    assert mod.find_stale_worktrees(wtd) == []


def test_detector_uses_created_at_not_dir_mtime(tmp_path):
    """A dir whose mtime is recent (active edits) but whose created_at is >24h
    old IS stale — created_at is the authoritative age axis."""
    wtd = tmp_path / ".worktrees"
    mod = _load_broker(wtd)
    wt = wtd / "infra-touched"
    _write_metadata(wt, created_minutes_ago=25 * 60)
    # Bump dir mtime to "now" — must NOT rescue it from stale.
    os.utime(wt, None)
    stale = mod.find_stale_worktrees(wtd)
    assert "infra-touched" in [name for name, _ in stale]


def test_detector_falls_back_to_dir_mtime_without_metadata(tmp_path):
    """A worktree dir with NO .agent-task.json (not broker-created) is judged by
    dir mtime so non-broker orphans are still caught."""
    wtd = tmp_path / ".worktrees"
    mod = _load_broker(wtd)
    wt = wtd / "rogue-no-meta"
    wt.mkdir(parents=True)
    old = time.time() - 25 * 60 * 60
    os.utime(wt, (old, old))
    stale = mod.find_stale_worktrees(wtd)
    assert "rogue-no-meta" in [name for name, _ in stale]


def test_detector_strict_flags_fresh_metadata_less_dir(tmp_path):
    """strict_missing_metadata=True (CI gate): a metadata-less worktree is
    reported even if its dir mtime is brand new (codex P3 false-negative)."""
    wtd = tmp_path / ".worktrees"
    mod = _load_broker(wtd)
    wt = wtd / "fresh-no-meta"
    wt.mkdir(parents=True)
    os.utime(wt, None)  # mtime = now
    # Lax mode: NOT stale (fresh mtime). Strict mode: stale (unmanaged).
    assert mod.find_stale_worktrees(wtd) == []
    strict = mod.find_stale_worktrees(wtd, strict_missing_metadata=True)
    assert [name for name, _ in strict] == ["fresh-no-meta"]
    assert strict[0][1] == float("inf")


def test_detector_empty_when_no_worktrees_dir(tmp_path):
    mod = _load_broker(tmp_path / ".worktrees")
    assert mod.find_stale_worktrees(tmp_path / ".worktrees") == []


# ---------------------------------------------------------------------------
# Live guard against the real checkout
# ---------------------------------------------------------------------------


def test_no_stale_worktrees_in_checkout():
    """Hard gate: the live .worktrees/ must contain no worktree older than 24h.

    If this fails, an orphan survived the broker. Fix by:
      python scripts/agent_start.py --list      # inspect (ORPHAN-flagged)
      python scripts/agent_start.py --cleanup   # reap idle expired worktrees
      python scripts/agent_start.py --release <task-id>   # tear down one
    """
    mod = _load_broker(REPO_ROOT / ".worktrees")
    # strict: at PR time a metadata-less worktree under .worktrees/ is a defect,
    # not something to excuse via a (recent) dir mtime.
    stale = mod.find_stale_worktrees(
        REPO_ROOT / ".worktrees", strict_missing_metadata=True
    )
    if stale:
        listing = "\n".join(
            f"  - {name}: {('unmanaged' if age == float('inf') else f'{age/60:.1f}h old')}"
            for name, age in stale
        )
        pytest.fail(
            "Stale worktree(s) older than 24h detected (W62 orphan guard):\n"
            f"{listing}\n"
            "Run: python scripts/agent_start.py --cleanup  (or --release <id>)"
        )
