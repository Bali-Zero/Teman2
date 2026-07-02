"""Unit tests for scripts/lib/wr2_runtime_stamp.py + empirical tests for the
wr2-deploy-pull.sh C2 additions (outcome heartbeat, guards, flag-gated kickstart).

The stamp tests run against a REAL throwaway git repo — the blob-per-file
compare (W88) is exactly the thing a mock would lie about.
"""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
LIB_PATH = SCRIPTS_DIR / "lib" / "wr2_runtime_stamp.py"
DEPLOY_PULL = SCRIPTS_DIR / "wr2-deploy-pull.sh"

spec = importlib.util.spec_from_file_location("wr2_runtime_stamp", LIB_PATH)
rs = importlib.util.module_from_spec(spec)
sys.modules["wr2_runtime_stamp"] = rs
spec.loader.exec_module(rs)


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q")
    _git(r, "config", "user.email", "t@t")
    _git(r, "config", "user.name", "t")
    (r / "mod.py").write_text("x = 1\n")
    _git(r, "add", ".")
    _git(r, "commit", "-qm", "init")
    return r


# ─────────────────────────────────────────────────────────────────────────
# compute_runtime_stamp
# ─────────────────────────────────────────────────────────────────────────

def test_clean_checkout_stamp(repo):
    stamp = rs.compute_runtime_stamp(repo, [repo / "mod.py"])
    assert stamp["head_sha"] == _git(repo, "rev-parse", "HEAD")
    assert stamp["dirty"] is False
    assert stamp["stale_modules"] == []
    assert stamp["errors"] == []


def test_modified_module_is_stale_by_blob(repo):
    """W88: content compare via blobs — a mutated live file must surface even
    though HEAD never moved."""
    (repo / "mod.py").write_text("x = 2\n")
    stamp = rs.compute_runtime_stamp(repo, [repo / "mod.py"])
    assert stamp["stale_modules"] == ["mod.py"]
    assert stamp["dirty"] is True


def test_module_outside_checkout_is_error(repo, tmp_path):
    outside = tmp_path / "elsewhere.py"
    outside.write_text("y = 1\n")
    stamp = rs.compute_runtime_stamp(repo, [outside])
    assert any(e.startswith("outside-checkout:") for e in stamp["errors"])
    assert stamp["stale_modules"] == []


def test_non_git_dir_fails_open(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "mod.py").write_text("x\n")
    stamp = rs.compute_runtime_stamp(plain, [plain / "mod.py"])
    assert stamp["head_sha"] is None
    assert "git-head-unavailable" in stamp["errors"]


def test_write_and_read_roundtrip(repo, tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    stamp = rs.compute_runtime_stamp(repo, [])
    path = rs.write_runtime_stamp("wr2.test_organ", stamp)
    assert path is not None and path.is_file()
    back = rs.read_runtime_stamp("wr2.test_organ")
    assert back["head_sha"] == stamp["head_sha"]


def test_read_missing_stamp_degrades_open(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert rs.read_runtime_stamp("wr2.never_written") is None


# ─────────────────────────────────────────────────────────────────────────
# gate_verdict
# ─────────────────────────────────────────────────────────────────────────

CLEAN = {"head_sha": "a" * 40, "dirty": False, "stale_modules": []}
DIRTY = {"head_sha": "a" * 40, "dirty": True, "stale_modules": []}


def test_gate_off_always_ok():
    assert rs.gate_verdict("off", DIRTY, "b" * 40)[0] == "ok"


def test_gate_clean_ok_in_any_mode():
    assert rs.gate_verdict("warn", CLEAN, "a" * 40)[0] == "ok"
    assert rs.gate_verdict("strict", CLEAN, "a" * 40)[0] == "ok"


def test_gate_warn_mode_never_blocks():
    verdict, reason = rs.gate_verdict("warn", DIRTY, "b" * 40)
    assert verdict == "warn"
    assert "dirty-checkout" in reason and "head-moved" in reason


def test_gate_strict_blocks_on_head_moved():
    verdict, reason = rs.gate_verdict("strict", CLEAN, "b" * 40)
    assert verdict == "block"
    assert "head-moved" in reason


def test_gate_strict_blocks_on_stale_modules():
    stamp = {"head_sha": "a" * 40, "dirty": False, "stale_modules": ["mod.py"]}
    verdict, reason = rs.gate_verdict("strict", stamp, "a" * 40)
    assert verdict == "block"
    assert "stale-modules:mod.py" in reason


def test_gate_strict_blocks_on_missing_head():
    verdict, reason = rs.gate_verdict("strict", {"head_sha": None}, None)
    assert verdict == "block"
    assert "no-head-provenance" in reason


# ─────────────────────────────────────────────────────────────────────────
# wr2-deploy-pull.sh — empirical (fake HOME, fake origin, fake launchctl)
# ─────────────────────────────────────────────────────────────────────────

def _setup_deploy_world(tmp_path):
    """origin bare repo + deploy clone under a fake HOME."""
    home = tmp_path / "home"
    (home / "Desktop").mkdir(parents=True)
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "main")
    _git(src, "config", "user.email", "t@t")
    _git(src, "config", "user.name", "t")
    (src / "f.txt").write_text("v1\n")
    _git(src, "add", ".")
    _git(src, "commit", "-qm", "v1")
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(src), str(origin)], check=True)
    deploy = home / "Desktop" / "nuzantara-deploy"
    subprocess.run(["git", "clone", "-q", str(origin), str(deploy)], check=True)
    return home, src, origin, deploy


def _run_pull(home, extra_env=None, path_prefix=None):
    env = dict(os.environ)
    env["HOME"] = str(home)
    env.pop("TELEGRAM_BOT_TOKEN", None)
    if path_prefix:
        env["WR2_DEPLOY_PULL_TEST_PATH_PREFIX"] = str(path_prefix)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(DEPLOY_PULL)], capture_output=True, text=True, env=env, timeout=60
    )


def _outcome(home):
    p = home / ".organism" / "last_seen" / "wr2.deploy_pull.json"
    assert p.is_file(), "outcome heartbeat missing — the trap did not fire"
    return json.loads(p.read_text())


def test_deploy_pull_up_to_date_writes_outcome(tmp_path):
    home, _src, _origin, _deploy = _setup_deploy_world(tmp_path)
    res = _run_pull(home)
    assert res.returncode == 0, res.stderr
    out = _outcome(home)
    assert out["status"] == "ok:up-to-date"
    assert out["old_head"] == out["new_head"] != ""


def test_deploy_pull_advanced_writes_outcome_and_skips_kickstart(tmp_path):
    home, src, origin, deploy = _setup_deploy_world(tmp_path)
    (src / "f.txt").write_text("v2\n")
    _git(src, "add", ".")
    _git(src, "commit", "-qm", "v2")
    _git(src, "push", "-q", str(origin), "main")
    res = _run_pull(home)
    assert res.returncode == 0, res.stderr
    out = _outcome(home)
    assert out["status"] == "ok:advanced"
    assert out["advance_count"] == 1
    assert out["old_head"] != out["new_head"]
    log = (home / "logs" / "wr2-deploy-pull.log").read_text()
    assert "kickstart skipped" in log


def test_deploy_pull_advanced_kickstarts_when_armed(tmp_path):
    home, src, origin, deploy = _setup_deploy_world(tmp_path)
    (src / "f.txt").write_text("v3\n")
    _git(src, "add", ".")
    _git(src, "commit", "-qm", "v3")
    _git(src, "push", "-q", str(origin), "main")
    fake_bin = tmp_path / "fakebin"
    fake_bin.mkdir()
    calls = tmp_path / "launchctl-calls.txt"
    fake = fake_bin / "launchctl"
    fake.write_text(f'#!/bin/sh\necho "$@" >> "{calls}"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    res = _run_pull(home, extra_env={"WR2_DEPLOY_PULL_KICKSTART": "1"}, path_prefix=fake_bin)
    assert res.returncode == 0, res.stderr
    recorded = calls.read_text()
    assert "com.balizero.wr2.html-apply" in recorded
    assert f"kickstart -k gui/{os.getuid()}/com.balizero.wr2.supervisor" in recorded
    assert "com.balizero.wr2.supervisor-watchdog" in recorded


def test_deploy_pull_dirty_clone_is_honest_error(tmp_path):
    home, _src, _origin, deploy = _setup_deploy_world(tmp_path)
    (deploy / "f.txt").write_text("local mutation\n")
    res = _run_pull(home)
    assert res.returncode == 1
    assert _outcome(home)["status"] == "error:dirty"
