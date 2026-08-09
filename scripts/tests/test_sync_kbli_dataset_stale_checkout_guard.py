"""Guilt AND innocence for the sync_kbli_dataset.sh main-checkout preflight guard (W106b).

The defect this pins: `sync` mode propagates canonical's CURRENT bytes over every
consumer copy. Read from the shared main checkout (M5's is ~235 commits behind BY
DESIGN — agents never pull it, work happens in worktrees), that propagation can
silently "sync backwards": overwriting consumer copies a merged PR has since moved
forward, the moment the resulting commit lands (same class as the app-repo Resources/
regression fixed alongside this PR).

The guard's guilt condition is the checked-out BRANCH (== "main"), not an
ancestor/commit-distance check against origin/main. An ancestor check was tried first
and measured broken live: a worktree branch that is completely healthy and freshly
created via scripts/agent_start.py can already be 1+ commits behind origin/main
minutes later, from ordinary unrelated activity elsewhere in this repo — that is
normal, not staleness, and a distance-based guard would refuse it. `test_worktree_
branch_a_full_day_behind_origin_still_syncs` pins exactly that: a non-main branch
stays fine no matter how far behind it is.

`--check` mode is deliberately NOT covered here — it is CI's read-only intra-repo
consistency gate (canonical vs. consumers within the SAME checkout), unrelated to
which branch is checked out, and this PR does not change its behavior.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "sync_kbli_dataset.sh"
LIB = REPO / "scripts" / "lib" / "kbli_fleet_notice.sh"

MAIN_CHECKOUT_REFUSED_RC = 4


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    )


def _write_canonical(repo: Path, content: str) -> None:
    (repo / "source_documents").mkdir(parents=True, exist_ok=True)
    (repo / "source_documents" / "KBLI_2025_FINAL_CLEAN.json").write_text(
        content, encoding="utf-8"
    )


def _install_script(repo: Path) -> Path:
    """Copy the real script (and its fleet-notice lib) into the fake checkout."""
    dst_scripts = repo / "scripts"
    dst_scripts.mkdir(parents=True, exist_ok=True)
    dst = dst_scripts / "sync_kbli_dataset.sh"
    dst.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    dst.chmod(0o755)
    dst_lib = dst_scripts / "lib"
    dst_lib.mkdir(parents=True, exist_ok=True)
    (dst_lib / "kbli_fleet_notice.sh").write_text(
        LIB.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return dst


def _init_repo(repo: Path, content: str, branch: str = "main") -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", branch)
    _git(repo, "config", "user.email", "test@test")
    _git(repo, "config", "user.name", "test")
    _write_canonical(repo, content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")


def _run_sync(checkout: Path, *extra_args: str) -> subprocess.CompletedProcess:
    script = _install_script(checkout)
    return subprocess.run(
        ["bash", str(script), *extra_args],
        cwd=checkout,
        capture_output=True,
        text=True,
        timeout=30,
        # HOME is referenced unconditionally by the (pre-existing, out of scope here)
        # fleet-notice default-path line even when CI short-circuits the block itself.
        env={
            "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
            "CI": "true",
            "HOME": str(checkout),
        },
    )


# ── guilt ──────────────────────────────────────────────────────────────────────────


def test_main_branch_checkout_is_refused_not_synced(tmp_path: Path) -> None:
    """THE regression: syncing from the shared, never-pulled main checkout."""
    repo = tmp_path / "main-checkout"
    _init_repo(repo, '{"kbli": "STALE — this is the never-pulled main checkout"}', branch="main")
    consumer = repo / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"

    res = _run_sync(repo)
    assert res.returncode == MAIN_CHECKOUT_REFUSED_RC, res.stdout + res.stderr
    assert "REFUSED" in (res.stdout + res.stderr)
    assert not consumer.exists(), "sync must not have run at all"


def test_local_canonical_bypasses_the_main_branch_refusal(tmp_path: Path) -> None:
    """--local-canonical is the explicit, documented override for a verified exception."""
    repo = tmp_path / "main-checkout"
    _init_repo(repo, '{"kbli": "V1"}', branch="main")

    res = _run_sync(repo, "--local-canonical")
    assert res.returncode == 0, res.stdout + res.stderr
    consumer = repo / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
    assert consumer.read_text(encoding="utf-8") == '{"kbli": "V1"}'


# ── innocence ──────────────────────────────────────────────────────────────────────


def test_worktree_branch_syncs_normally(tmp_path: Path) -> None:
    """A non-main (worktree-style) branch must sync exactly as before the fix."""
    repo = tmp_path / "worktree-style-checkout"
    _init_repo(repo, '{"kbli": "V1 — a normal cure edit"}', branch="agent/air-m5/ops/some-task")

    res = _run_sync(repo)
    assert res.returncode == 0, res.stdout + res.stderr
    consumer = repo / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
    assert consumer.read_text(encoding="utf-8") == '{"kbli": "V1 — a normal cure edit"}'


def test_worktree_branch_far_behind_origin_still_syncs(tmp_path: Path) -> None:
    """Pins the exact false-positive the ancestor-check design was measured to have:

    a healthy worktree branch can be commits behind origin/main purely from ordinary,
    unrelated activity elsewhere in the repo — that must never be read as staleness.
    Simulated here as a worktree-style checkout whose `origin` has advanced far past
    it (no fetch is ever attempted by the guard, so this must succeed regardless).
    """
    origin_src = tmp_path / "origin-src"
    _init_repo(origin_src, '{"kbli": "V1"}', branch="main")

    origin_bare = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", str(origin_src), str(origin_bare))

    worktree_style = tmp_path / "worktree-style-checkout"
    _git(tmp_path, "clone", "-q", "-b", "main", str(origin_bare), str(worktree_style))
    _git(worktree_style, "checkout", "-q", "-b", "agent/air-m5/ops/some-task")
    _git(worktree_style, "config", "user.email", "test@test")
    _git(worktree_style, "config", "user.name", "test")
    _write_canonical(worktree_style, '{"kbli": "V2 — the cure this session is applying"}')
    _git(worktree_style, "add", "-A")
    _git(worktree_style, "commit", "-q", "-m", "cure: update canonical")

    # origin/main races far ahead while this worktree-style checkout is open — many
    # unrelated commits landing from other sessions, exactly as happens on this repo.
    for i in range(5):
        _write_canonical(origin_src, f'{{"kbli": "unrelated main commit {i}"}}')
        _git(origin_src, "add", "-A")
        _git(origin_src, "commit", "-q", "-m", f"unrelated {i}")
    _git(origin_src, "push", "-q", str(origin_bare), "main")

    res = _run_sync(worktree_style)
    assert res.returncode == 0, res.stdout + res.stderr
    consumer = worktree_style / "data" / "source_documents" / "KBLI_2025_FINAL_CLEAN.json"
    assert consumer.read_text(encoding="utf-8") == '{"kbli": "V2 — the cure this session is applying"}'


def test_check_mode_is_not_guarded_regardless_of_branch(tmp_path: Path) -> None:
    """--check must never be blocked by the main-branch refusal (it isn't sync mode)."""
    repo = tmp_path / "main-checkout"
    _init_repo(repo, '{"kbli": "V1"}', branch="main")

    res = _run_sync(repo, "--check")
    assert res.returncode != MAIN_CHECKOUT_REFUSED_RC, res.stdout + res.stderr
