#!/usr/bin/env python3
"""PreToolUse hook (Bash) — block dangerous git ops in main checkout.

L5.1 SOTA wave 2026-05-25. Closes Gap G1 (adoption enforcement) from
research/operations/2026-05-25-sota-workflow-gap-analysis-and-l5-spec.md.

Post-4-LLM-panel amendments (research/operations/specs/L5.1-panel-synthesis-2026-05-25.md):
- A1: Path canonicalization via os.path.realpath() + Path.is_relative_to()
- A3: Parse `git -C <path>` and `cd <path> && git` for effective target
- A4: Removed transcript marker bypass (env-only escape)
- A5: Probe-mode logging for empirical sub-agent inheritance test
- A6: Cached alive-agent count (zero subprocess on hot path)

Blocked patterns (only when effective git target is REPO_ROOT):
- git checkout / switch (branch op)
- git stash (sibling-orphan creator)
- git reset --hard
- git merge / rebase / pull
- git commit -a / git add -A / git add .

Allow:
- git status/log/diff/show/branch -l/worktree list (read-only)
- git -C <worktree> ... where <worktree> resolves under allowed
- git add <specific-file>
- git commit -m "..." (no -a)
- git push <branch>

Escape: AGENT_WORKTREE_ENFORCEMENT=false (env var set in session, NOT inline cmd prefix).

Exit code 2 + stderr = block tool call.
Exit code 0 + no stderr = allow.

Reference cicatrix: 2026-04-29 #1+#2, W50/W51/W52, 32+ sibling-orphan-2026-05-25.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys

import subprocess as _sp


def _is_nuzantara_root(root: str) -> bool:
    """Repo signature: only the nuzantara checkout carries scripts/agent_start.py."""
    return os.path.isfile(os.path.join(root, "scripts", "agent_start.py"))


def _derive_repo_root() -> str:
    """Machine-agnostic main-checkout root (Pro /Users/nuzantara, M5 /Users/balizero).

    git-common-dir derivation is correct ONLY when cwd is inside the nuzantara
    repo. When the session cwd sits in a DIFFERENT git repo (e.g. ~/.claude),
    it would silently resolve there and disarm the brake. The signature guard
    rejects any derived root that lacks scripts/agent_start.py.
    """
    home_default = f"{os.path.expanduser('~')}/Desktop/nuzantara"
    # 1) honor explicit override
    _env = os.environ.get("NUZ_REPO_ROOT")
    if _env:
        return _env.rstrip("/")
    # 2) main checkout = parent of git common dir (only if it is the nuzantara repo)
    try:
        cd = _sp.run(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            cwd=os.getcwd(), capture_output=True, text=True, timeout=3,
        )
        if cd.returncode == 0 and cd.stdout.strip():
            common = cd.stdout.strip()
            root = common[:-5] if common.endswith("/.git") else os.path.dirname(common)
            if _is_nuzantara_root(root):
                return root
    except Exception:
        pass
    # 3) fallback to home-based guess (works on both machines)
    return home_default


REPO_ROOT = _derive_repo_root()

# Blocked git subcommands.
BLOCKED_SUBCMD_RE = re.compile(
    r"\bgit\s+(?:-c\s+\S+\s+)*"  # optional -c key=val flags
    r"(?:-C\s+\S+\s+)?"  # optional -C path
    r"(checkout|switch|stash|reset|merge|rebase|pull)\b"
    r"|\bgit\s+commit\s+(?:[^\s]+\s+)*(?:-[A-Za-z]*a|--all\b)"  # commit -a / -am / -a -m / --all
    r"|\bgit\s+add\s+(?:-A|-a|--all|\.)"  # add -A / add -a / add --all / add .
)

# Extract `git -C <path>` target.
GIT_C_RE = re.compile(r"\bgit\s+(?:-c\s+\S+\s+)*-C\s+(\S+)")

# Extract `cd <path> && git ...` target.
CD_GIT_RE = re.compile(r"\bcd\s+(\S+)\s*(?:&&|;)\s*git\b")

ALIVE_COUNT_CACHE = "/tmp/nuz_alive_count"
BLOCK_COUNT_FILE = "/tmp/nuz_l5_1_blocks"
PROBE_LOG = pathlib.Path.home() / ".claude" / "l5_1_hook_probe.jsonl"


def _kill_switch_active() -> bool:
    val = os.environ.get("AGENT_WORKTREE_ENFORCEMENT", "true").strip().lower()
    return val in {"false", "0", "no", "off", "disabled"}


def _git_worktree_list() -> list[pathlib.Path]:
    """Parse `git worktree list --porcelain` for current worktree paths.

    Best-effort: empty list on error (defaults to only main).
    """
    try:
        result = subprocess.run(
            ["git", "-C", REPO_ROOT, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return []
        worktrees = []
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                p = line.removeprefix("worktree ").strip()
                try:
                    worktrees.append(pathlib.Path(p).resolve())
                except Exception:
                    pass
        return worktrees
    except Exception:
        return []


def _is_path_in_allowed_worktree(path_str: str) -> bool:
    """True if path resolves under an allowed worktree (NOT main checkout)."""
    if not path_str:
        return False
    try:
        path_real = pathlib.Path(path_str).resolve()
    except Exception:
        return False

    repo_real = pathlib.Path(REPO_ROOT).resolve()

    # Exactly main checkout → NOT allowed
    if path_real == repo_real:
        return False

    # Get all worktrees from git
    worktrees = _git_worktree_list()
    # Filter out main checkout itself
    allowed = [w for w in worktrees if w != repo_real]

    # Also accept external worktree convention paths
    _base = re.escape(os.path.dirname(REPO_ROOT))
    external_patterns = [
        re.compile(r"^" + _base + r"/nuzantara-deploy$"),
        re.compile(r"^" + _base + r"/nuzantara-wa-dashboard-[a-z0-9-]+$"),
        re.compile(r"^" + _base + r"/nuzantara-[a-z0-9-]+-2026-\d{2}-\d{2}$"),
    ]

    path_str_real = str(path_real)
    for pattern in external_patterns:
        # Check if path_real OR any parent matches
        for parent in [path_real, *path_real.parents]:
            if pattern.match(str(parent)):
                return True

    # is_relative_to check against discovered worktrees
    for allowed_wt in allowed:
        try:
            if path_real == allowed_wt or path_real.is_relative_to(allowed_wt):
                return True
        except AttributeError:
            # Python <3.9 fallback
            try:
                path_real.relative_to(allowed_wt)
                return True
            except ValueError:
                pass

    return False


def _effective_git_target(cmd: str, default_cwd: str) -> str:
    """Determine the effective working dir for git command.

    Priority: `git -C <path>` > `cd <path> && git` > default cwd.
    """
    m = GIT_C_RE.search(cmd)
    if m:
        return m.group(1)
    m = CD_GIT_RE.search(cmd)
    if m:
        return m.group(1)
    return default_cwd


def _n_alive_cached() -> int:
    try:
        return int(pathlib.Path(ALIVE_COUNT_CACHE).read_text().strip())
    except Exception:
        return -1


def _increment_block_counter():
    try:
        bc = pathlib.Path(BLOCK_COUNT_FILE)
        n = int(bc.read_text().strip()) if bc.exists() else 0
        bc.write_text(str(n + 1))
    except Exception:
        pass


def _probe_log(payload: dict, decision: str):
    """A5: probe-mode logging for empirical sub-agent inheritance test."""
    try:
        PROBE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with PROBE_LOG.open("a") as f:
            json.dump({
                "tool_name": payload.get("tool_name", ""),
                "cwd": payload.get("cwd", ""),
                "cmd": payload.get("tool_input", {}).get("command", "")[:200],
                "decision": decision,
                "pid": os.getpid(),
                "ppid": os.getppid(),
            }, f)
            f.write("\n")
    except Exception:
        pass


def main():
    if _kill_switch_active():
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if payload.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = payload.get("tool_input", {}).get("command", "")
    cwd = payload.get("cwd", "")

    # Quick exit: cmd doesn't look git-mutating
    if "git" not in cmd:
        sys.exit(0)

    if not BLOCKED_SUBCMD_RE.search(cmd):
        sys.exit(0)

    # Compute effective target
    target = _effective_git_target(cmd, cwd)

    # If effective target is in an allowed worktree → permit
    if _is_path_in_allowed_worktree(target):
        _probe_log(payload, "allow_worktree")
        sys.exit(0)

    # If target is NOT REPO_ROOT and we can't classify → permit (defense conservative)
    target_real = pathlib.Path(target).resolve() if target else pathlib.Path(REPO_ROOT)
    repo_real = pathlib.Path(REPO_ROOT).resolve()
    if target_real != repo_real:
        _probe_log(payload, "allow_external")
        sys.exit(0)

    # Block.
    _increment_block_counter()
    _probe_log(payload, "block")

    n_alive = _n_alive_cached()
    n_alive_str = f"{n_alive}" if n_alive >= 0 else "?"

    sys.stderr.write(
        f"WORKTREE ISOLATION VIOLATION (Bash git op in main)\n"
        f"  cwd: {cwd}\n"
        f"  effective target: {target_real}\n"
        f"  command: {cmd[:200]}\n"
        f"  alive AI processes: {n_alive_str}\n\n"
        f"Reason: this git op in main checkout would race with other agents.\n\n"
        f"Resolution:\n"
        f"  1. Create dedicated worktree:\n"
        f"     python scripts/agent_start.py --lane <lane> --task-id <task-id>\n"
        f"     cd <output-path>\n"
        f"  2. Then retry the git op there (use 'git -C <path> ...' since Bash resets cwd).\n\n"
        f"Emergency escape: AGENT_WORKTREE_ENFORCEMENT=false (env var set in shell)\n\n"
        f"See: docs/runbooks/agent-worktree-broker.md\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
