"""Shared self-commit promotion helper for the SOTA M13 growth-loop crons.

The M13 checkpoint/weekly/monthly jobs (com.balizero.sota.m13-checkpoint /
-weekly / -monthly, dispatched through scripts/wr2-cron-wrapper.sh) write
their state (checkpoint_day_N.md, kpi_timeline.csv, weekly/monthly reports,
09_wr2_weights_<month>.json) straight into the main checkout's TRACKED tree
(research/sota-social-2026-v1/) and none of them ever committed it — roughly
3.5 months of drift sat dirty/untracked until PR #3756 promoted the backlog
one-shot (cure-C, explicitly deferred the structural fix: "Structural fix
(cure-A: make the M13 loop commit its own output) is tracked separately, not
part of this promotion.").

This module is that structural half (cure-A), same pattern as
scripts/translate-articles-cron-wrapper.sh (PR #3762, mouth hourly
translations) and infra/launchagents/wrappers/regulatory-watcher-run.sh's
promote_delta_via_pr() (regulatory-watcher daily delta): copy the file(s)
the caller just wrote into an ephemeral worktree (scripts/agent_start.py),
commit + push + open an auto-merge PR there. The main checkout itself is
never touched by git.

Kill switch (G5_kill_switch organ-conformance gene): SOTA_PROMOTE_ENABLED=false
disables promotion without touching the plists — the caller's own file writes
and DB work are unaffected, only the git/PR step is skipped.

Best-effort throughout: a promotion failure is logged and returns False, it
never raises into the caller's cron job — the M13 loop's own work (DB writes,
Telegram digest) must never be lost because a PR could not be opened.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path

logger = logging.getLogger("sota.m13.promote")

_GIT_TIMEOUT = 30
_GH_TIMEOUT = 30
_BROKER_TIMEOUT = 60


def _run(cmd: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False
    )


def promote_research_output(
    repo_root: Path,
    rel_paths: list[str],
    *,
    commit_subject: str,
    commit_body: str,
    lane: str = "wr2",
    task_prefix: str = "sota",
) -> bool:
    """Promote repo-relative paths already written under ``repo_root`` into
    git history via an ephemeral worktree + auto-merge PR.

    Returns True on a successful promotion OR a genuine no-op (nothing to
    promote / nothing changed). Returns False on any failure — always
    logged, never raised.
    """
    if os.environ.get("SOTA_PROMOTE_ENABLED", "true").strip().lower() == "false":
        logger.info("promote: SOTA_PROMOTE_ENABLED=false — skipping promotion (deliberate stop)")
        return True

    existing = [p for p in rel_paths if (repo_root / p).is_file()]
    if not existing:
        logger.info("promote: none of %s exist on disk under %s — nothing to promote", rel_paths, repo_root)
        return True

    try:
        # Opportunistic reap of a previous run's worktree, now that its PR
        # (if any) may have merged in the meantime. Best-effort — agent_start
        # .py's own merged-into-base guard refuses to touch a worktree whose
        # PR is still open, so this never races a pending promotion.
        _run(["python3", "scripts/agent_start.py", "--cleanup"], cwd=repo_root, timeout=_BROKER_TIMEOUT)

        task_id = f"{task_prefix}-{int(time.time())}"
        create = _run(
            [
                "python3", "scripts/agent_start.py",
                "--lane", lane, "--task-id", task_id, "--ttl-min", "30",
            ],
            cwd=repo_root,
            timeout=_BROKER_TIMEOUT,
        )
        wt_path: Path | None = None
        for line in create.stdout.splitlines():
            if line.startswith("WORKTREE_READY"):
                wt_path = Path(line.split(" ", 1)[1].strip())
        if create.returncode != 0 or wt_path is None or not wt_path.is_dir():
            logger.error(
                "promote: worktree creation failed rc=%s stdout=%r stderr=%r",
                create.returncode, create.stdout, create.stderr,
            )
            return False

        changed: list[str] = []
        for rel in existing:
            src = repo_root / rel
            dst = wt_path / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(src.read_bytes())
            status = _run(["git", "status", "--porcelain", "--", rel], cwd=wt_path, timeout=_GIT_TIMEOUT)
            if status.stdout.strip():
                changed.append(rel)

        if not changed:
            logger.info("promote: no diff after copy (%s) — releasing worktree", existing)
            _run(["python3", "scripts/agent_start.py", "--release", task_id], cwd=repo_root, timeout=_BROKER_TIMEOUT)
            return True

        add = _run(["git", "add", *changed], cwd=wt_path, timeout=_GIT_TIMEOUT)
        if add.returncode != 0:
            logger.error("promote: git add failed: %s", add.stderr)
            return False

        full_message = (
            f"{commit_subject}\n\n{commit_body}\n\n"
            "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
        )
        commit = _run(["git", "commit", "-m", full_message], cwd=wt_path, timeout=_GIT_TIMEOUT)
        if commit.returncode != 0:
            logger.error("promote: git commit failed: %s", commit.stderr)
            return False

        branch = _run(["git", "branch", "--show-current"], cwd=wt_path, timeout=_GIT_TIMEOUT).stdout.strip()
        if not branch:
            logger.error("promote: could not resolve current branch in %s", wt_path)
            return False

        push = _run(["git", "push", "-u", "origin", branch], cwd=wt_path, timeout=_GIT_TIMEOUT)
        if push.returncode != 0:
            logger.error(
                "promote: push failed — leaving worktree %s for manual recovery: %s",
                wt_path, push.stderr,
            )
            return False

        pr = _run(
            [
                "gh", "pr", "create", "--base", "main", "--head", branch,
                "--title", commit_subject,
                "--body", f"Automated promotion of {', '.join(changed)}. {commit_body}",
            ],
            cwd=wt_path,
            timeout=_GH_TIMEOUT,
        )
        if pr.returncode != 0:
            logger.error(
                "promote: gh pr create failed — branch %s pushed, PR NOT opened, "
                "manual recovery: gh pr create --head %s : %s",
                branch, branch, pr.stderr,
            )
            return False
        pr_url = pr.stdout.strip()
        logger.info("promote: opened PR %s", pr_url)

        pr_num = pr_url.rstrip("/").rsplit("/", 1)[-1]
        # NOT --squash: once a merge queue governs main, the ruleset owns the
        # merge method and --squash is rejected outright (pipeline-ship skill).
        merge = _run(["gh", "pr", "merge", pr_num, "--auto"], cwd=wt_path, timeout=_GH_TIMEOUT)
        if merge.returncode != 0:
            logger.warning("promote: could not arm auto-merge on PR %s (needs manual arm): %s", pr_url, merge.stderr)
        else:
            logger.info("promote: auto-merge armed on %s", pr_url)
        logger.info("promote: worktree %s left in place pending merge (next run's --cleanup collects it once merged)", wt_path)
        return True
    except Exception:
        logger.exception("promote: unexpected error promoting %s", rel_paths)
        return False
