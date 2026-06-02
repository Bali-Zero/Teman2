#!/usr/bin/env python3
"""SOTA L1 (2026-05-24) — Agent Worktree Broker.

Closes the sibling-collision class documented in cicatrix incidents
2026-04-29 #1 + #2 (untracked file loss when sibling automation switches
branches mid-session) and the 17 stash orphans accumulated 2026-05-23.

Convergence 4/4 from the 4-LLM panel (Gemini 3.1 / GPT-5.5 codex /
DeepSeek V4 Pro / Claude Opus 4.7) on the invariant:

    ∀ w₁,w₂ : session(w₁) ∧ session(w₂)
    ⇒ working_tree(w₁) ∩ working_tree(w₂) = ∅

Reference: research/operations/2026-05-24-sota-multi-agent-repo-architecture-synthesis.md

Each agent session (subagent dispatch / cron-spawned claude / parallel
Claude Code window) MUST run inside a dedicated worktree under
`<REPO_ROOT>/.worktrees/<LANE>-<TASK_ID>/`. The main checkout is
reserved for operator interactive use + cicatrix hotfixes.

Subcommands:
    --lane / --task-id      Create a new worktree (default action).
    --list                  Show active worktrees + age + WIP indicator.
    --cleanup               Remove worktrees whose TTL expired (WIP-safe).
    --release <task-id>     Tear down a specific worktree + branch.

Kill switch:
    AGENT_BROKER_ENABLED=false   Disables every create/cleanup/release op
                                  (lesson W33). --list stays available.

Logs:
    ~/logs/agent-broker.log     Rotating (RotatingFileHandler 1MB x 5).
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import re
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKTREES_DIR = REPO_ROOT / ".worktrees"
TASK_METADATA_FILENAME = ".agent-task.json"
# Broker-generated files that must NOT count as user WIP (otherwise every
# freshly created worktree reads as dirty and is never cleanup-eligible).
BROKER_GENERATED_FILES = frozenset({".agent-task.json", ".env.worktree"})

# Lanes documented in CLAUDE.md + research synthesis.
# This is an ALLOW-list for create; --list/--cleanup/--release accept any lane
# that already has a metadata file on disk (forward-compat for new lanes).
KNOWN_LANES: set[str] = {
    "wr2",
    "wr3",
    "infra",
    "docs",
    "db",
    "cicatrix-fix",
    "mouth",  # reserved for Subhi per CLAUDE.md §12
    "intel",
    "cell",
    "organism",
    "mata-garuda",
    "backend-rag",
    "frontend",
    "ops",
}

# Lane / task-id validation: lowercase, digits, dash. No slashes (would break
# the branch ref and the directory path).
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,63}$")

# Symlinks created from main checkout into the new worktree (env-safe).
# Targets are relative paths inside the repo. If the target does not exist in
# main, the symlink is skipped silently — the agent will still get a working
# worktree, just without that helper artifact.
SYMLINK_TARGETS: tuple[tuple[str, str], ...] = (
    ("apps/backend-rag/.venv", "apps/backend-rag/.venv"),
    ("apps/backend-rag/.env", "apps/backend-rag/.env"),
    ("node_modules", "node_modules"),
)

LOG_DIR = Path.home() / "logs"
LOG_FILE = LOG_DIR / "agent-broker.log"

KILL_SWITCH_ENV = "AGENT_BROKER_ENABLED"

# W62 ANTIBODY #1: cleanup must not reap a TTL-expired-but-clean worktree that
# is still being actively worked on. A worktree touched more recently than this
# threshold is treated as a live session and skipped (override with --force or
# skip_recent_minutes=0).
RECENT_ACTIVITY_MINUTES = 10

# W62 ANTIBODY #2/#3: a worktree older than this multiple of its TTL is a
# suspected orphan (surfaced by --list, gated by the CI hygiene test).
ORPHAN_TTL_MULTIPLE = 2


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _init_logger() -> logging.Logger:
    logger = logging.getLogger("agent_broker")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s agent_broker[%(process)d] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    # File handler with rotation (best-effort — failure must not crash the CLI).
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(
            LOG_FILE, maxBytes=1_048_576, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


logger = _init_logger()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _kill_switch_active() -> bool:
    """True if the broker is disabled via env var (lesson W33)."""
    val = os.environ.get(KILL_SWITCH_ENV, "").strip().lower()
    return val in {"false", "0", "no", "off", "disabled"}


def _hostname_short() -> str:
    """Return the short hostname (first dotted segment), lowercased.

    The hostname is reused as a branch-path segment, so we lowercase + strip
    anything outside [a-z0-9-].
    """
    raw = socket.gethostname().split(".")[0].lower()
    cleaned = re.sub(r"[^a-z0-9-]", "-", raw).strip("-")
    return cleaned or "unknown-host"


def _validate_id(label: str, value: str) -> None:
    if not ID_PATTERN.match(value):
        raise SystemExit(
            f"ERROR: invalid {label} '{value}' — must match {ID_PATTERN.pattern}"
        )


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(ts: str) -> datetime:
    # Accept both `...Z` and `...+00:00`.
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    return datetime.fromisoformat(ts)


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Thin wrapper around `git ...` that captures output.

    Returns the CompletedProcess. When check=True (default) raises
    CalledProcessError with stderr piped into the exception for diagnosis.
    """
    cmd = ["git", *args]
    cwd = cwd or REPO_ROOT
    logger.debug("git: %s (cwd=%s)", " ".join(cmd), cwd)
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
    )
    if check and proc.returncode != 0:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, proc.stdout, proc.stderr
        )
    return proc


def _branch_name(host: str, lane: str, task_id: str) -> str:
    return f"agent/{host}/{lane}/{task_id}"


def _worktree_path(lane: str, task_id: str) -> Path:
    return WORKTREES_DIR / f"{lane}-{task_id}"


# ---------------------------------------------------------------------------
# Metadata dataclass
# ---------------------------------------------------------------------------


@dataclass
class TaskMetadata:
    task_id: str
    lane: str
    branch: str
    host: str
    created_at: str
    ttl_minutes: int
    pid: int
    base_branch: str
    worktree_path: str

    def to_json(self) -> str:
        return json.dumps(
            {
                "task_id": self.task_id,
                "lane": self.lane,
                "branch": self.branch,
                "host": self.host,
                "created_at": self.created_at,
                "ttl_minutes": self.ttl_minutes,
                "pid": self.pid,
                "base_branch": self.base_branch,
                "worktree_path": self.worktree_path,
            },
            indent=2,
            sort_keys=True,
        )

    @classmethod
    def from_path(cls, path: Path) -> "TaskMetadata":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            task_id=data["task_id"],
            lane=data["lane"],
            branch=data["branch"],
            host=data["host"],
            created_at=data["created_at"],
            ttl_minutes=int(data["ttl_minutes"]),
            pid=int(data["pid"]),
            base_branch=data.get("base_branch", "main"),
            worktree_path=data.get("worktree_path", ""),
        )

    def is_expired(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        try:
            created = _parse_iso(self.created_at)
        except ValueError:
            return False  # malformed timestamp → operator must intervene
        age_minutes = (now - created).total_seconds() / 60.0
        return age_minutes > self.ttl_minutes

    def age_minutes(self, *, now: datetime | None = None) -> float:
        now = now or datetime.now(timezone.utc)
        try:
            created = _parse_iso(self.created_at)
        except ValueError:
            return -1.0
        return (now - created).total_seconds() / 60.0


# ---------------------------------------------------------------------------
# Symlink helper
# ---------------------------------------------------------------------------


def _create_symlinks(worktree: Path) -> list[str]:
    """Create env-safe symlinks from main checkout into the new worktree.

    Returns the list of relative symlink targets actually created (skips any
    target that does not exist in main, plus any that would clobber an existing
    file/dir in the worktree).
    """
    created: list[str] = []
    for source_rel, dest_rel in SYMLINK_TARGETS:
        source = REPO_ROOT / source_rel
        dest = worktree / dest_rel
        if not source.exists():
            logger.debug("symlink skip (no source): %s", source_rel)
            continue
        if dest.exists() or dest.is_symlink():
            logger.debug("symlink skip (dest exists): %s", dest_rel)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.symlink(source, dest)
            created.append(dest_rel)
        except OSError as exc:
            logger.warning("symlink failed %s -> %s: %s", dest_rel, source, exc)
    return created


# ---------------------------------------------------------------------------
# Subcommand: create
# ---------------------------------------------------------------------------


def cmd_create(
    lane: str,
    task_id: str,
    *,
    ttl_minutes: int = 60,
    base_branch: str = "main",
    allow_unknown_lane: bool = False,
) -> Path:
    """Create a new worktree + branch + metadata.

    Returns the absolute path to the new worktree.

    Raises SystemExit on validation or git error so the CLI exits non-zero.
    """
    if _kill_switch_active():
        raise SystemExit(
            f"ERROR: broker disabled ({KILL_SWITCH_ENV}=false). "
            "Unset or set to 'true' to re-enable."
        )

    _validate_id("lane", lane)
    _validate_id("task-id", task_id)

    if lane not in KNOWN_LANES and not allow_unknown_lane:
        known = ", ".join(sorted(KNOWN_LANES))
        raise SystemExit(
            f"ERROR: unknown lane '{lane}'. Known: {known}.\n"
            f"Pass --allow-unknown-lane to override."
        )

    if ttl_minutes <= 0:
        raise SystemExit("ERROR: --ttl-min must be > 0")

    host = _hostname_short()
    branch = _branch_name(host, lane, task_id)
    worktree = _worktree_path(lane, task_id)

    if worktree.exists():
        raise SystemExit(
            f"ERROR: worktree already exists at {worktree}. "
            f"Use --release {task_id} first or pick a different task-id."
        )

    # Pre-flight: branch must not already exist (worktree add -b would fail
    # with a less-clear error otherwise).
    existing_branches = _run_git(["branch", "--list", branch]).stdout.strip()
    if existing_branches:
        raise SystemExit(
            f"ERROR: branch '{branch}' already exists. "
            "Choose a different task-id or delete the stale branch."
        )

    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)

    logger.info(
        "creating worktree lane=%s task_id=%s branch=%s base=%s ttl_min=%d",
        lane,
        task_id,
        branch,
        base_branch,
        ttl_minutes,
    )

    try:
        _run_git(["worktree", "add", "-b", branch, str(worktree), base_branch])
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise SystemExit(f"ERROR: git worktree add failed: {stderr}") from exc

    symlinks = _create_symlinks(worktree)

    metadata = TaskMetadata(
        task_id=task_id,
        lane=lane,
        branch=branch,
        host=host,
        created_at=_utc_now_iso(),
        ttl_minutes=ttl_minutes,
        pid=os.getpid(),
        base_branch=base_branch,
        worktree_path=str(worktree),
    )
    (worktree / TASK_METADATA_FILENAME).write_text(
        metadata.to_json(), encoding="utf-8"
    )

    # W59 auto-export (cicatrix 2026-05-27): write .env.worktree with BRANCH_EXPECTED
    # for opt-in adoption of W59 hook (PR #899). Operator/agent sources via:
    #   source .env.worktree
    # to auto-protect atomic git sequences from sibling HEAD-race.
    env_worktree_content = (
        "# Auto-generated by scripts/agent_start.py — W59 sibling-race guard env\n"
        "# Source this file before any atomic git sequence:\n"
        "#   source .env.worktree\n"
        f"export BRANCH_EXPECTED={branch}\n"
        f"export AGENT_TASK_ID={task_id}\n"
        f"export AGENT_LANE={lane}\n"
    )
    (worktree / ".env.worktree").write_text(env_worktree_content, encoding="utf-8")

    logger.info(
        "worktree ready path=%s symlinks=%s", worktree, ",".join(symlinks) or "(none)"
    )
    return worktree


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------


def _iter_metadata(worktrees_dir: Path | None = None) -> Iterable[TaskMetadata]:
    # Resolve at call-time (not import-time) so test fixtures that patch
    # the module-level WORKTREES_DIR after import take effect.
    worktrees_dir = worktrees_dir if worktrees_dir is not None else WORKTREES_DIR
    if not worktrees_dir.is_dir():
        return []
    out: list[TaskMetadata] = []
    for entry in sorted(worktrees_dir.iterdir()):
        meta_path = entry / TASK_METADATA_FILENAME
        if not meta_path.is_file():
            continue
        try:
            out.append(TaskMetadata.from_path(meta_path))
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.warning("skip malformed metadata at %s: %s", meta_path, exc)
    return out


def _worktree_has_wip(worktree: Path) -> bool:
    """True if the worktree has uncommitted changes (tracked or untracked)."""
    proc = _run_git(
        ["status", "--porcelain"], cwd=worktree, check=False
    )
    if proc.returncode != 0:
        # If git can't read the worktree (corrupt) treat as WIP to be safe.
        return True
    # Ignore broker-generated files (.agent-task.json, .env.worktree) when
    # computing WIP, otherwise every freshly created worktree reports dirty.
    relevant = []
    for line in proc.stdout.splitlines():
        # Porcelain v1: first 2 cols are status, then a space, then path.
        if len(line) < 4:
            continue
        path = line[3:].strip()
        # Strip "->" rename targets.
        path = path.split(" -> ")[-1].strip().strip('"')
        if path in BROKER_GENERATED_FILES:
            continue
        relevant.append(line)
    return bool(relevant)


def _worktree_recently_active(
    worktree: Path, *, threshold_minutes: int = RECENT_ACTIVITY_MINUTES
) -> bool:
    """True if the worktree shows filesystem activity within threshold_minutes.

    Distinct from age (created_at): this is a *liveness* probe so cleanup never
    reaps a worktree whose TTL clock expired while a session was still working
    in it (W62 ANTIBODY #1). Signal = newest mtime among the worktree dir, its
    `.git` pointer, and the REAL gitdir HEAD (the linked-worktree gitdir is
    under REPO_ROOT/.git/worktrees/<name>/; HEAD is bumped by commit/checkout —
    codex P2: the `.git` pointer alone is not enough for linked worktrees).

    NB: the gitdir `index` is deliberately NOT probed — `git status` (run by the
    WIP check that precedes this guard) rewrites the index mtime, so it would
    read as "active" on every cleanup pass. HEAD is stable under read-only
    status, so it tracks genuine commit/checkout activity only.

    This is a best-effort liveness heuristic, NOT a security control: an
    adversary could `touch` a path to keep an orphan alive. Its only job is to
    avoid reaping a genuinely active session; the 24h CI cap (find_stale_
    worktrees) is the hard ceiling no heuristic can opt out of.
    """
    if threshold_minutes <= 0:
        return False
    cutoff = time.time() - threshold_minutes * 60
    probes = [worktree, worktree / ".git"]
    real_gitdir = _resolve_worktree_gitdir(worktree)
    if real_gitdir is not None:
        probes.append(real_gitdir / "HEAD")
    try:
        return any(p.exists() and p.stat().st_mtime > cutoff for p in probes)
    except OSError:
        return True


def _resolve_worktree_gitdir(worktree: Path) -> Path | None:
    """Resolve the real gitdir of a linked worktree (REPO_ROOT/.git/worktrees/
    <name>). For a linked worktree, `worktree/.git` is a file
    `gitdir: <abs-path>`; return that path. Returns None on any error."""
    git_pointer = worktree / ".git"
    try:
        if git_pointer.is_file():
            text = git_pointer.read_text(encoding="utf-8").strip()
            if text.startswith("gitdir:"):
                return Path(text.split(":", 1)[1].strip())
        elif git_pointer.is_dir():
            return git_pointer
    except OSError:
        return None
    return None


def _is_orphan(meta: "TaskMetadata", *, now: datetime | None = None) -> bool:
    """True if age exceeds ORPHAN_TTL_MULTIPLE × ttl. Malformed timestamps
    (age_minutes == -1.0) are NOT orphans — operator must inspect them."""
    age = meta.age_minutes(now=now)
    if age < 0:
        return False
    return age > ORPHAN_TTL_MULTIPLE * meta.ttl_minutes


# Hard ceiling (W62 ANTIBODY #3): no worktree should survive this long. Enforced
# at PR-time by tests/integration/test_no_stale_worktrees.py. Independent of any
# per-task TTL — a runaway TTL cannot opt out of the absolute cap.
STALE_WORKTREE_MAX_AGE_MINUTES = 24 * 60


def find_stale_worktrees(
    worktrees_dir: Path | None = None,
    *,
    max_age_minutes: int = STALE_WORKTREE_MAX_AGE_MINUTES,
    strict_missing_metadata: bool = False,
    now: datetime | None = None,
) -> list[tuple[str, float]]:
    """Return [(name, age_minutes)] for worktrees older than max_age_minutes.

    Age signal (W62 audit decision): primary is the broker's own `created_at`
    metadata (the canonical age axis used by --list/--cleanup).

    For a worktree dir WITHOUT a valid `.agent-task.json`:
      - strict_missing_metadata=False (default): fall back to directory mtime so
        non-broker orphans are still caught when they happen to be old.
      - strict_missing_metadata=True (CI gate): an unmanaged/malformed worktree
        is ALWAYS reported (age = +inf), because a fresh-but-untracked dir under
        .worktrees/ has a recent mtime and would slip past a 24h mtime check
        (codex P3 false-negative). At PR time there is no live session, so any
        metadata-less worktree is a defect to fix.
    """
    worktrees_dir = worktrees_dir if worktrees_dir is not None else WORKTREES_DIR
    if not worktrees_dir.is_dir():
        return []
    now = now or datetime.now(timezone.utc)
    now_ts = now.timestamp()
    stale: list[tuple[str, float]] = []
    for entry in sorted(worktrees_dir.iterdir()):
        if not entry.is_dir():
            continue
        meta_path = entry / TASK_METADATA_FILENAME
        managed = False
        age = -1.0
        if meta_path.is_file():
            try:
                meta = TaskMetadata.from_path(meta_path)
                age = meta.age_minutes(now=now)
                managed = age >= 0
            except (OSError, json.JSONDecodeError, KeyError, ValueError):
                managed = False
        if not managed:
            if strict_missing_metadata:
                stale.append((entry.name, float("inf")))
                continue
            age = max(0.0, (now_ts - entry.stat().st_mtime) / 60.0)
        if age > max_age_minutes:
            stale.append((entry.name, age))
    return stale


def cmd_list() -> int:
    rows = list(_iter_metadata())
    if not rows:
        print("(no active worktrees under .worktrees/)")
        return 0
    print(
        f"{'TASK':<24} {'LANE':<14} {'HOST':<14} "
        f"{'AGE_MIN':>8} {'TTL':>5} {'WIP':<4} {'ORPHAN':<7} BRANCH"
    )
    now = datetime.now(timezone.utc)
    orphan_count = 0
    for meta in rows:
        wt = Path(meta.worktree_path) if meta.worktree_path else _worktree_path(
            meta.lane, meta.task_id
        )
        wip_flag = "yes" if wt.is_dir() and _worktree_has_wip(wt) else "no"
        age = meta.age_minutes(now=now)
        orphan = _is_orphan(meta, now=now)
        if orphan:
            orphan_count += 1
        orphan_flag = "ORPHAN" if orphan else ""
        print(
            f"{meta.task_id:<24} {meta.lane:<14} {meta.host:<14} "
            f"{age:>8.1f} {meta.ttl_minutes:>5d} {wip_flag:<4} "
            f"{orphan_flag:<7} {meta.branch}"
        )
    if orphan_count:
        print(
            f"\nWARN: {orphan_count} orphan worktree(s) detected "
            f"(age > {ORPHAN_TTL_MULTIPLE}× TTL) — review then run "
            "--cleanup or --release."
        )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: cleanup
# ---------------------------------------------------------------------------


def cmd_cleanup(
    *, force: bool = False, skip_recent_minutes: int = RECENT_ACTIVITY_MINUTES
) -> int:
    """Remove expired worktrees. WIP-safe: emits WARNING and skips if dirty.

    Two guards protect a worktree from being reaped even when its TTL clock
    expired. Order matters — WIP is checked FIRST so a worktree that is BOTH
    recently-touched AND dirty still surfaces as a WIP failure (never silently
    swallowed as a "live session"):
      1. WIP guard — uncommitted changes present (tracked or untracked). This
         is a *failure* to clean (the operator must commit/stash) → exit 1.
      2. Recent-activity guard (W62 ANTIBODY #1) — applied only to CLEAN
         worktrees: filesystem activity within skip_recent_minutes marks a live
         session. This is *not* a failure; the next tick reaps it once idle.

    Pass force=True to override BOTH guards (operator escape hatch).
    skip_recent_minutes=0 disables only the recent-activity guard.
    Returns 0 if every expired worktree was removed cleanly OR no work
    needed; 1 if at least one removal was skipped for WIP / errored.
    """
    if _kill_switch_active():
        raise SystemExit(
            f"ERROR: broker disabled ({KILL_SWITCH_ENV}=false). Unset to cleanup."
        )

    rows = list(_iter_metadata())
    if not rows:
        print("(nothing to cleanup)")
        return 0

    now = datetime.now(timezone.utc)
    issues = 0
    for meta in rows:
        if not meta.is_expired(now=now):
            continue
        wt = Path(meta.worktree_path) if meta.worktree_path else _worktree_path(
            meta.lane, meta.task_id
        )
        # WIP guard FIRST: a dirty worktree is always a failure to clean,
        # even if it was touched recently (codex P2: recent+dirty must not
        # exit 0 silently).
        if wt.is_dir() and _worktree_has_wip(wt) and not force:
            logger.warning(
                "cleanup skip %s — uncommitted WIP present (use --force)",
                meta.task_id,
            )
            print(
                f"WARN: skip {meta.task_id} (WIP). "
                f"Commit or stash inside {wt}, then re-run --cleanup."
            )
            issues += 1
            continue
        # Recent-activity guard SECOND, on clean worktrees only: a live session
        # that simply outran its TTL clock — keep it, reap when idle.
        if (
            wt.is_dir()
            and not force
            and _worktree_recently_active(wt, threshold_minutes=skip_recent_minutes)
        ):
            logger.info(
                "cleanup skip %s — recent activity (<%dmin), likely live session",
                meta.task_id,
                skip_recent_minutes,
            )
            print(
                f"skip {meta.task_id} (recent activity <{skip_recent_minutes}min) "
                "— live session, will reap when idle"
            )
            continue
        try:
            _remove_worktree(wt, meta.branch, delete_branch=False)
            print(f"removed expired worktree {meta.task_id} ({wt})")
        except subprocess.CalledProcessError as exc:
            issues += 1
            logger.error(
                "cleanup failed %s: %s", meta.task_id, (exc.stderr or "").strip()
            )
            print(f"ERROR: cleanup failed for {meta.task_id}: {exc.stderr}")
    return 0 if issues == 0 else 1


# ---------------------------------------------------------------------------
# Subcommand: release
# ---------------------------------------------------------------------------


def _branch_is_merged(branch: str, base: str = "main") -> bool:
    """True if every commit on branch is reachable from base."""
    proc = _run_git(
        ["rev-list", "--count", f"{base}..{branch}"], check=False
    )
    if proc.returncode != 0:
        return False
    try:
        return int(proc.stdout.strip()) == 0
    except ValueError:
        return False


def _remove_worktree(worktree: Path, branch: str, *, delete_branch: bool) -> None:
    """Remove worktree via `git worktree remove` and optionally delete branch."""
    _run_git(["worktree", "remove", "--force", str(worktree)])
    if delete_branch:
        # -D allows deleting branches not merged into HEAD (we already verified
        # merged-into-base separately).
        _run_git(["branch", "-D", branch])


def cmd_release(task_id: str, *, force: bool = False) -> int:
    """Tear down a worktree by task-id. Branch deleted only if merged into base.

    With --force, the branch is deleted unconditionally (operator escape).
    """
    if _kill_switch_active():
        raise SystemExit(
            f"ERROR: broker disabled ({KILL_SWITCH_ENV}=false). Unset to release."
        )

    _validate_id("task-id", task_id)
    matches = [m for m in _iter_metadata() if m.task_id == task_id]
    if not matches:
        raise SystemExit(f"ERROR: no worktree metadata for task-id '{task_id}'")
    if len(matches) > 1:
        raise SystemExit(
            f"ERROR: multiple worktrees for task-id '{task_id}' — "
            "pass full path manually"
        )
    meta = matches[0]
    wt = Path(meta.worktree_path) if meta.worktree_path else _worktree_path(
        meta.lane, meta.task_id
    )
    base = meta.base_branch or "main"

    if wt.is_dir() and _worktree_has_wip(wt) and not force:
        raise SystemExit(
            f"ERROR: worktree {wt} has uncommitted WIP. "
            "Commit, push, or pass --force."
        )

    merged = _branch_is_merged(meta.branch, base=base)
    if not merged and not force:
        raise SystemExit(
            f"ERROR: branch {meta.branch} not merged into {base}. "
            "Open a PR + merge it, or pass --force to delete unconditionally."
        )

    try:
        _remove_worktree(wt, meta.branch, delete_branch=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise SystemExit(f"ERROR: release failed: {stderr}") from exc

    logger.info("released worktree task_id=%s branch=%s", task_id, meta.branch)
    print(f"released {task_id} (branch {meta.branch} deleted)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agent-start",
        description=(
            "Agent Worktree Broker — enforces worktree-per-session for every "
            "concurrent Claude / subagent / cron session."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  agent-start --lane wr2 --task-id render-cleanup\n"
            "  agent-start --list\n"
            "  agent-start --cleanup\n"
            "  agent-start --release render-cleanup\n"
        ),
    )
    # Operations (mutually exclusive at the group-of-flags level).
    p.add_argument("--lane", help="Lane identifier (e.g. wr2, infra, docs)")
    p.add_argument("--task-id", help="Task id (short slug, ticket id, uuid)")
    p.add_argument(
        "--ttl-min",
        type=int,
        default=60,
        help="TTL in minutes after which cleanup may reclaim (default: 60)",
    )
    p.add_argument(
        "--base-branch",
        default="main",
        help="Base branch to fork from (default: main)",
    )
    p.add_argument(
        "--allow-unknown-lane",
        action="store_true",
        help="Permit creating a worktree with a lane not in the known list",
    )

    p.add_argument(
        "--list",
        action="store_true",
        help="List active worktrees with age + WIP indicator",
    )
    p.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove worktrees whose TTL has expired (WIP-safe)",
    )
    p.add_argument(
        "--release",
        metavar="TASK_ID",
        help="Tear down a specific worktree + branch (branch must be merged)",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="With --cleanup/--release: override WIP and merged-status guards",
    )
    p.add_argument(
        "--skip-recent-min",
        type=int,
        default=RECENT_ACTIVITY_MINUTES,
        help=(
            "With --cleanup: skip worktrees with filesystem activity in the last "
            f"N minutes (default: {RECENT_ACTIVITY_MINUTES}; 0 disables the guard)"
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Dispatch (subcommand flags are mutually exclusive at the semantic level).
    operations = sum(
        [bool(args.list), bool(args.cleanup), bool(args.release), bool(args.lane)]
    )
    if operations == 0:
        parser.print_help()
        return 2
    if operations > 1:
        print("ERROR: choose exactly one of --lane/--list/--cleanup/--release")
        return 2

    if args.list:
        return cmd_list()
    if args.cleanup:
        return cmd_cleanup(force=args.force, skip_recent_minutes=args.skip_recent_min)
    if args.release:
        return cmd_release(args.release, force=args.force)

    # Default: create.
    if not args.lane or not args.task_id:
        print("ERROR: --lane AND --task-id are both required to create a worktree")
        return 2

    worktree = cmd_create(
        args.lane,
        args.task_id,
        ttl_minutes=args.ttl_min,
        base_branch=args.base_branch,
        allow_unknown_lane=args.allow_unknown_lane,
    )
    # Single-line stdout contract for shell-glue:
    print(f"WORKTREE_READY {worktree}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
