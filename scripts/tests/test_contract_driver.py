"""test_contract_driver.py — the host driver's three reads, each proven against the
real host (gh + git), never against a stub of it.

  merged     a seat claiming {merged:true, live_receipt:"/tmp/x"} on #6664 — closed,
             never merged, immutable — is BLOCKed; the same claim on #6704 (merged
             03516ea404) is OK. SAETTA's scheduler passes the first one today.
  post-merge #6673's pack, judged at its own BASE, is malformed (the observe script
             did not exist there — what CI saw); judged at origin/main it is executable
             and its observe exits 0 from this tree.
  collide    pure matrix via selftest; the live read is exercised for its shape.

Needs gh auth and the repo's apps/backend-rag/.venv (the observe runs pytest). FAILS,
not skips, when they are missing; CONTRACT_DRIVER_OFFLINE=1 opts out explicitly.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "contract_driver.py"
OFFLINE = os.environ.get("CONTRACT_DRIVER_OFFLINE") == "1"


def _run(*args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)


def test_selftest_passes():
    p = _run("selftest")
    assert p.returncode == 0 and "0 failure(s)" in p.stdout, p.stdout + p.stderr


def _online():
    if OFFLINE:
        pytest.skip("CONTRACT_DRIVER_OFFLINE=1 — opted out explicitly")


def test_merged_read_blocks_the_claim_saetta_passes_today():
    _online()
    p = _run("merged", "--pr", "6664", "--claim", json.dumps({"merged": True, "live_receipt": "/tmp/x"}), "--json")
    assert p.returncode == 1, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["verdict"] == "BLOCK" and out["read"]["mergedAt"] is None and out["read"]["state"] == "CLOSED"


def test_merged_read_agrees_with_a_true_claim():
    _online()
    p = _run("merged", "--pr", "6704", "--claim", json.dumps({"merged": True, "merge_commit": "03516ea404"}), "--json")
    assert p.returncode == 0, p.stdout + p.stderr
    out = json.loads(p.stdout)
    assert out["verdict"] == "OK" and out["read"]["mergeCommit"].startswith("03516ea404")


def test_collide_reads_open_and_recent_prs():
    _online()
    p = _run("collide", "--scope", "this/path/does/not/exist.py", "--json")
    assert p.returncode == 0, p.stdout + p.stderr
    assert json.loads(p.stdout)["collisions"] == []


def test_post_merge_6673_malformed_at_base_executable_at_main():
    _online()
    base = subprocess.run(["git", "merge-base", "origin/main", "9b30782aae468f8eeeaf949f4f5035bff34af47c"], cwd=str(ROOT),
                          capture_output=True, text=True).stdout.strip()
    assert len(base) == 40, "merge-base of #6673's head is not resolvable — fetch refs/pull/6673/head first"
    at_base = _run("post-merge", "--pr", "6673", "--at", base)
    assert at_base.returncode == 1 and "malformed" in at_base.stdout and "does not exist in the checkout" in at_base.stdout, at_base.stdout + at_base.stderr
    main = subprocess.run(["git", "rev-parse", "origin/main"], cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
    at_main = _run("post-merge", "--pr", "6673", "--at", main, timeout=900)
    assert at_main.returncode == 0 and "is executable" in at_main.stdout and "observe exit 0" in at_main.stdout, at_main.stdout + at_main.stderr
    stray = subprocess.run(["git", "worktree", "list"], cwd=str(ROOT), capture_output=True, text=True).stdout
    assert "contract-driver-wt-" not in stray
