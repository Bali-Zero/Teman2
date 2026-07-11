"""Guilt+innocence tests for the dirty-worktree self-heal in wr2-deploy-pull.sh
(W81/#2, incident 2026-07-05->07).

A sibling session left a tracked-deleted plist (unstaged) in the deploy clone
~/Desktop/nuzantara-deploy. The OLD single DIRTY block treated every porcelain
line the same: log first entry, alert once (6h cooldown), exit 1 -- forever,
because the clone stays dirty until a human intervenes. Code propagation to
the WR2 runtime froze for 2+ days while the alert rotted behind cooldown.

The deploy clone is BY CONTRACT read-only runtime: any local modification is
drift, never valuable work. This suite proves the classifier:
  (a) untracked (`?? `)                 -> not blocking, proceeds+advances
  (b) unstaged tracked mod/del (` M`/` D`) -> self-healed via `git checkout --`,
      proceeds+advances, status ok:self-healed
  (c) staged / index-mutated entries    -> still refuses, exit 1, no self-heal
  (d) WR2_DEPLOY_PULL_SELFHEAL=0        -> old freeze behavior preserved
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
DEPLOY_PULL = SCRIPTS_DIR / "wr2-deploy-pull.sh"


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _setup_deploy_world(tmp_path: Path):
    """origin bare repo + deploy clone under a fake HOME (same pattern as
    test_wr2_runtime_stamp.py's _setup_deploy_world -- kept independent here
    so this file runs standalone)."""
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    _git(src, "config", "user.email", "t@t")
    _git(src, "config", "user.name", "t")
    (src / "f.txt").write_text("v1\n")
    (src / "tracked.plist").write_text("<plist>v1</plist>\n")
    _git(src, "add", ".")
    _git(src, "commit", "-qm", "v1")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(origin)], check=True)
    deploy = home / "Desktop" / "nuzantara-deploy"
    subprocess.run(["git", "clone", "-q", str(origin), str(deploy)], check=True)
    return home, src, origin, deploy


def _run_pull(home: Path, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["HOME"] = str(home)
    env.pop("TELEGRAM_BOT_TOKEN", None)
    # Hermetic: never let the real tg_notify.py touch a live spool/secrets.
    env["TG_DRY_RUN"] = "1"
    env["TG_SPOOL_DIR"] = str(home / ".organism" / "tg_spool")
    env["TG_SECRETS_FILE"] = "/dev/null"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(DEPLOY_PULL)], capture_output=True, text=True, env=env, timeout=60
    )


def _outcome(home: Path) -> dict:
    p = home / ".organism" / "last_seen" / "wr2.deploy_pull.json"
    assert p.is_file(), "outcome heartbeat missing -- the trap did not fire"
    return json.loads(p.read_text())


def _advance_remote(src: Path, origin: Path, marker: str = "v2") -> None:
    (src / "f.txt").write_text(f"{marker}\n")
    _git(src, "add", ".")
    _git(src, "commit", "-qm", marker)
    _git(src, "push", "-q", str(origin), "main")


def _log_text(home: Path) -> str:
    return (home / "logs" / "wr2-deploy-pull.log").read_text()


# ─────────────────────────────────────────────────────────────────────────
# (a) untracked junk -> not blocking, proceeds and advances
# ─────────────────────────────────────────────────────────────────────────
def test_untracked_junk_proceeds_and_advances(tmp_path):
    home, src, origin, deploy = _setup_deploy_world(tmp_path)
    (deploy / "venv-leftover.tmp").write_text("junk\n")  # untracked, not ours
    _advance_remote(src, origin)

    res = _run_pull(home)
    assert res.returncode == 0, res.stderr
    out = _outcome(home)
    assert out["status"] == "ok:advanced"
    log = _log_text(home)
    assert "not blocking" in log
    assert "venv-leftover.tmp" in log
    # untracked junk must survive the run untouched (never git-checkout'd)
    assert (deploy / "venv-leftover.tmp").is_file()


# ─────────────────────────────────────────────────────────────────────────
# (b) tracked file deleted locally (unstaged) -> self-healed, advances
# ─────────────────────────────────────────────────────────────────────────
def test_tracked_deleted_file_self_heals_and_advances(tmp_path):
    home, src, origin, deploy = _setup_deploy_world(tmp_path)
    (deploy / "tracked.plist").unlink()  # exactly the real incident's shape
    _advance_remote(src, origin)

    res = _run_pull(home)
    assert res.returncode == 0, res.stderr
    out = _outcome(home)
    assert out["status"] == "ok:self-healed"
    assert out["old_head"] != out["new_head"]
    log = _log_text(home)
    assert "self-healed dirty" in log
    assert "tracked.plist" in log
    # healed: the file is back, worktree clean
    assert (deploy / "tracked.plist").is_file()
    assert _git(deploy, "status", "--porcelain") == ""


def test_tracked_modified_file_self_heals_when_up_to_date(tmp_path):
    """No remote advance available -> still heals, terminal status reflects
    the heal even though there was nothing to fast-forward."""
    home, src, origin, deploy = _setup_deploy_world(tmp_path)
    (deploy / "tracked.plist").write_text("<plist>LOCAL MUTATION</plist>\n")

    res = _run_pull(home)
    assert res.returncode == 0, res.stderr
    out = _outcome(home)
    assert out["status"] == "ok:self-healed"
    assert out["old_head"] == out["new_head"]
    assert _git(deploy, "status", "--porcelain") == ""


# ─────────────────────────────────────────────────────────────────────────
# (c) staged local change -> refuses, exit 1, no self-heal, P0 notified
# ─────────────────────────────────────────────────────────────────────────
def test_staged_change_refuses_no_selfheal(tmp_path):
    home, src, origin, deploy = _setup_deploy_world(tmp_path)
    (deploy / "new-staged.txt").write_text("staged content\n")
    _git(deploy, "add", "new-staged.txt")

    res = _run_pull(home)
    assert res.returncode == 1, res.stderr
    out = _outcome(home)
    assert out["status"] == "error:dirty"
    log = _log_text(home)
    assert "non-healable" in log
    # never touched: still staged, nothing checked out
    status = _git(deploy, "status", "--porcelain")
    assert "new-staged.txt" in status


# ─────────────────────────────────────────────────────────────────────────
# (d) WR2_DEPLOY_PULL_SELFHEAL=0 -> old freeze behavior preserved
# ─────────────────────────────────────────────────────────────────────────
def test_selfheal_opt_out_preserves_old_freeze_behavior(tmp_path):
    home, src, origin, deploy = _setup_deploy_world(tmp_path)
    (deploy / "tracked.plist").unlink()

    res = _run_pull(home, extra_env={"WR2_DEPLOY_PULL_SELFHEAL": "0"})
    assert res.returncode == 1, res.stderr
    out = _outcome(home)
    assert out["status"] == "error:dirty"
    # untouched: the deletion persists, no checkout happened
    assert not (deploy / "tracked.plist").exists()
