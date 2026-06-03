#!/usr/bin/env python3
"""
scar_probes.py — concrete replay probes compiled from cicatrix-scars.md.

Each probe is a lived production failure turned into a deterministic,
network-free, ephemeral replay. The BASELINE must fail (that's the headroom);
the antibody must make it pass on the original + hidden variants.

The candidate (DeepSeek) sees ONLY `incident_summary` + `contract`. It never
sees the fixture code, the assertion, or the variants. This is the anti-overfit
firewall (council 2026-06-04).

ANTIBODY CONTRACT (shared by the git-worktree family)
-----------------------------------------------------
The antibody snippet is sourced with these env vars set, BEFORE the risky op:
  SHARED_WORKTREE   absolute path of the protected deploy worktree
  PINNED_BRANCH     the branch the shared worktree must stay on (e.g. deploy/main)
  EVOLVER_CWD       the directory the evolver wants to do git-ops in
  REQUESTED_BRANCH  the branch the evolver wants to checkout
It must guarantee: the evolver's git checkout does NOT move SHARED_WORKTREE's
HEAD off PINNED_BRANCH. Acceptable strategies: refuse if EVOLVER_CWD resolves
into SHARED_WORKTREE and spawn/redirect to an isolated worktree; or block the
branch op in the shared path. The antibody may export a variable
ISOLATED_WORKTREE pointing to a safe path it created, and/or exit non-zero to
abort the unsafe op.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from scar_replay import Probe, ReplayOutcome


# --------------------------------------------------------------------------- #
# helpers                                                                      #
# --------------------------------------------------------------------------- #


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("GIT_CONFIG_NOSYSTEM", "1")
    env["GIT_AUTHOR_NAME"] = env["GIT_COMMITTER_NAME"] = "scar-replay"
    env["GIT_AUTHOR_EMAIL"] = env["GIT_COMMITTER_EMAIL"] = "noreply@balizero.com"
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _make_repo_with_deploy_worktree(sandbox: Path, pinned_branch: str) -> tuple[Path, Path]:
    """Build a bare-ish repo + a 'deploy' worktree pinned to `pinned_branch`.

    Returns (main_repo, deploy_worktree).
    """
    main_repo = sandbox / "repo"
    main_repo.mkdir(parents=True)
    _git(main_repo, "init", "-q", "-b", "main")
    (main_repo / "README.md").write_text("seed\n")
    _git(main_repo, "add", "-A")
    _git(main_repo, "commit", "-q", "-m", "seed")
    # create the pinned deploy branch
    _git(main_repo, "branch", pinned_branch)
    # add a deploy worktree checked out on the pinned branch
    deploy_wt = sandbox / "deploy-worktree"
    _git(main_repo, "worktree", "add", "-q", str(deploy_wt), pinned_branch)
    return main_repo, deploy_wt


def _risky_checkout(
    sandbox: Path,
    antibody_path: Optional[Path],
    pinned_branch: str,
    requested_branch: str,
    cwd_subpath: Optional[str] = None,
    extra_pre: str = "",
) -> Path:
    """Run the risky operation: evolver wants to checkout `requested_branch`
    inside the deploy worktree. WITHOUT antibody this drifts the shared tree.

    cwd_subpath: if given, the evolver cwd is this path RELATIVE to the freshly
    created deploy worktree (tests containment resolution, not exact-path match).
    The subdir is created so it is a real directory inside the shared tree.

    Returns the deploy worktree path so the assertion can inspect its HEAD.
    """
    main_repo, deploy_wt = _make_repo_with_deploy_worktree(sandbox, pinned_branch)
    if cwd_subpath:
        cwd = deploy_wt / cwd_subpath
        cwd.mkdir(parents=True, exist_ok=True)
    else:
        cwd = deploy_wt

    antibody_src = ""
    if antibody_path is not None:
        antibody_src = f'source "{antibody_path}" || true\n'

    # The evolver's intent, expressed as a shell op. The antibody (if present)
    # gets a chance to redirect/abort. If the antibody exported ISOLATED_WORKTREE
    # or aborted (exit / set GIT_TARGET away from shared), the shared tree stays.
    script = f"""
set -u
export SHARED_WORKTREE="{deploy_wt}"
export PINNED_BRANCH="{pinned_branch}"
export EVOLVER_CWD="{cwd}"
export REQUESTED_BRANCH="{requested_branch}"
{extra_pre}
{antibody_src}
# Where does the evolver actually operate? The antibody may have redirected it.
TARGET_DIR="${{ISOLATED_WORKTREE:-$EVOLVER_CWD}}"
# Guard: if antibody aborted via exit, we never get here. If it set a flag to
# skip, honor it.
if [ "${{EVOLVER_ABORT:-0}}" = "1" ]; then
    exit 0
fi
# The actual risky git op. -B creates-or-resets the branch and checks it out.
git -C "$TARGET_DIR" checkout -q -B "$REQUESTED_BRANCH" 2>/dev/null || true
"""
    subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=60)
    return deploy_wt


def _assert_shared_unchanged(deploy_wt: Path, pinned_branch: str) -> ReplayOutcome:
    """The shared deploy worktree HEAD must still be on the pinned branch."""
    if not deploy_wt.exists():
        return ReplayOutcome(False, "deploy worktree vanished")
    cur = _git(deploy_wt, "rev-parse", "--abbrev-ref", "HEAD")
    branch = (cur.stdout or "").strip()
    if branch == pinned_branch:
        return ReplayOutcome(True, f"shared tree still on {pinned_branch}")
    return ReplayOutcome(False, f"DRIFT: shared tree moved to {branch!r}")


# --------------------------------------------------------------------------- #
# Probe: shared_worktree_git_ops                                              #
# --------------------------------------------------------------------------- #

_PINNED = "deploy/main"

_INCIDENT_SUMMARY = (
    "Two autonomous cron jobs share ONE git worktree (the production 'deploy' "
    "checkout, pinned to branch 'deploy/main'). Job A (a weekly self-improvement "
    "loop) does `git checkout -B program/<name>` to checkpoint its output. Job B "
    "(an hourly deploy puller) does `git pull --ff-only` and asserts the worktree "
    "is on 'deploy/main'. When Job A checks out its branch INSIDE the shared "
    "worktree, the worktree's HEAD drifts off 'deploy/main'. Job B then fails "
    "every hour, the alert is cooldown-suppressed, and production runs stale code "
    "for 15-32 hours before anyone notices. Root issue: Job A performs git branch "
    "operations inside a directory that another job depends on staying pinned."
)

_CONTRACT = (
    "You receive (as env vars, already exported): SHARED_WORKTREE (the protected "
    "deploy worktree path), PINNED_BRANCH (branch it must stay on), EVOLVER_CWD "
    "(where Job A wants to run git ops), REQUESTED_BRANCH (branch Job A wants). "
    "After your snippet runs, a line `git -C \"${ISOLATED_WORKTREE:-$EVOLVER_CWD}\" "
    "checkout -B \"$REQUESTED_BRANCH\"` will execute (unless you set EVOLVER_ABORT=1, "
    "in which case it is skipped). Guarantee that SHARED_WORKTREE's HEAD stays on "
    "PINNED_BRANCH. You may: export ISOLATED_WORKTREE to a safe path you create "
    "(e.g. via `git -C <repo> worktree add` in a temp dir, or a fresh clone), OR "
    "set EVOLVER_ABORT=1 to refuse, OR otherwise ensure the checkout never targets "
    "SHARED_WORKTREE. Be idempotent. Do not rely on absolute paths not given to you."
)


def _build_original(sandbox: Path, antibody_path: Optional[Path]) -> None:
    deploy_wt = _risky_checkout(
        sandbox, antibody_path,
        pinned_branch=_PINNED,
        requested_branch="program/iter-skill-1",
    )
    # stash the deploy path for the assertion via a marker file
    (sandbox / ".deploy_wt").write_text(str(deploy_wt))


def _assert_original(sandbox: Path) -> ReplayOutcome:
    deploy_wt = Path((sandbox / ".deploy_wt").read_text().strip())
    return _assert_shared_unchanged(deploy_wt, _PINNED)


# --- variant builders (HIDDEN from the candidate) -------------------------- #


def _build_variant_diff_branch(sandbox: Path, antibody_path: Optional[Path]) -> None:
    """Same drift, but a different requested branch name (generalization check)."""
    deploy_wt = _risky_checkout(
        sandbox, antibody_path,
        pinned_branch=_PINNED,
        requested_branch="agent/nuzantara/infra/some-other-name",
    )
    (sandbox / ".deploy_wt").write_text(str(deploy_wt))


def _build_variant_subdir_cwd(sandbox: Path, antibody_path: Optional[Path]) -> None:
    """EVOLVER_CWD is a SUBDIRECTORY inside the shared worktree, not its root.

    Tests that the antibody resolves containment, not just an exact path match.
    """
    deploy_wt = _risky_checkout(
        sandbox, antibody_path,
        pinned_branch=_PINNED,
        requested_branch="program/iter-skill-2",
        cwd_subpath="agent-library",
    )
    (sandbox / ".deploy_wt").write_text(str(deploy_wt))


def _build_variant_concurrent_lock(sandbox: Path, antibody_path: Optional[Path]) -> None:
    """A concurrent lock file exists (Job B mid-operation). Antibody must still
    avoid drifting the shared tree (must not just blindly checkout)."""
    deploy_wt = _risky_checkout(
        sandbox, antibody_path,
        pinned_branch=_PINNED,
        requested_branch="program/iter-skill-3",
        extra_pre='touch "$SHARED_WORKTREE/.git/deploy-pull.lock" 2>/dev/null || true',
    )
    (sandbox / ".deploy_wt").write_text(str(deploy_wt))


def _assert_variant(sandbox: Path) -> ReplayOutcome:
    deploy_wt = Path((sandbox / ".deploy_wt").read_text().strip())
    return _assert_shared_unchanged(deploy_wt, _PINNED)


shared_worktree_probe = Probe(
    family="shared_worktree_git_ops",
    incident_summary=_INCIDENT_SUMMARY,
    contract=_CONTRACT,
    build_fixture=_build_original,
    assert_outcome=_assert_original,
    variants=[
        ("different_branch_name", _build_variant_diff_branch),
        ("subdir_cwd_containment", _build_variant_subdir_cwd),
        ("concurrent_deploy_lock", _build_variant_concurrent_lock),
    ],
)


# --------------------------------------------------------------------------- #
# registry                                                                     #
# --------------------------------------------------------------------------- #


def all_probes() -> list[Probe]:
    return [shared_worktree_probe]
