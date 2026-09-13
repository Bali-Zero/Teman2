#!/usr/bin/env python3
"""PreToolUse hook (Edit|Write|MultiEdit|apply_patch) — protect main checkout.

L5.1 SOTA wave 2026-05-25 — Codex unique amendment (P0).

Closes the critical gap: L5.1 worktree_isolation.py covers ONLY Bash git ops.
But the empirical motivation cited in L5.1 §1 (`kg_bridge.py` orphan in main)
was created via Write tool, not git command. Bash-only enforcement is
incomplete against the very pattern it claims to prevent.

This hook blocks Edit/Write/MultiEdit file_path that resolves under
REPO_ROOT but NOT under any allowed worktree.

Escape: AGENT_WORKTREE_ENFORCEMENT=false (env var, NOT inline cmd prefix).

Exit code 2 + stderr = block tool call.
Exit code 0 + no stderr = allow.

Reference: research/operations/specs/L5.1-panel-synthesis-2026-05-25.md §"CRITICAL NEW FINDING".
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
    home_default = f"{os.path.expanduser('~')}/nuzantara"
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
BLOCK_COUNT_FILE = "/tmp/nuz_l5_1_blocks"
PROBE_LOG = pathlib.Path.home() / ".claude" / "l5_1_hook_probe.jsonl"


def _kill_switch_active() -> bool:
    val = os.environ.get("AGENT_WORKTREE_ENFORCEMENT", "true").strip().lower()
    return val in {"false", "0", "no", "off", "disabled"}


def _git_worktree_list() -> list[pathlib.Path]:
    try:
        result = subprocess.run(
            ["git", "-C", REPO_ROOT, "worktree", "list", "--porcelain"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode != 0:
            return []
        return [
            pathlib.Path(line.removeprefix("worktree ").strip()).resolve()
            for line in result.stdout.splitlines() if line.startswith("worktree ")
        ]
    except Exception:
        return []


def _is_path_under_allowed_worktree(path_real: pathlib.Path) -> bool:
    """True if path is under an allowed worktree (NOT under main checkout root directly)."""
    repo_real = pathlib.Path(REPO_ROOT).resolve()

    worktrees = _git_worktree_list()
    allowed_worktrees = [w for w in worktrees if w != repo_real]

    # W79 parity (2026-06-16 innocence-vaccine): any path under
    # REPO_ROOT/.worktrees/<anything> is the convention scratch area — allowed
    # even if not (yet) git-registered. Sibling hook worktree_isolation.py gained
    # this fallback in W79; this file lacked it, so a Write into a freshly-created
    # (unregistered) worktree was mis-classified as a main-checkout write and
    # BLOCKED — a false positive that breaks the very worktree discipline the hook
    # exists to enforce. Caught by infra/claude-hooks/test_hook_innocence.py.
    _repo_esc = re.escape(str(repo_real))
    worktrees_dir_re = re.compile(r"^" + _repo_esc + r"/\.worktrees/[^/]+(?:/|$)")
    if worktrees_dir_re.match(str(path_real)):
        return True

    _base = re.escape(os.path.dirname(REPO_ROOT))
    external_patterns = [
        re.compile(r"^" + _base + r"/nuzantara-deploy$"),
        re.compile(r"^" + _base + r"/nuzantara-wa-dashboard-[a-z0-9-]+$"),
        re.compile(r"^" + _base + r"/nuzantara-[a-z0-9-]+-2026-\d{2}-\d{2}$"),
    ]

    # Check external worktree convention by walking parents
    for parent in [path_real, *path_real.parents]:
        for pattern in external_patterns:
            if pattern.match(str(parent)):
                return True

    # Check discovered worktrees
    for allowed_wt in allowed_worktrees:
        try:
            if path_real == allowed_wt or path_real.is_relative_to(allowed_wt):
                return True
        except AttributeError:
            try:
                path_real.relative_to(allowed_wt)
                return True
            except ValueError:
                pass

    return False


def _probe_log(payload: dict, file_path: str, decision: str):
    try:
        PROBE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with PROBE_LOG.open("a") as f:
            json.dump({
                "tool_name": payload.get("tool_name", ""),
                "file_path": file_path[:200],
                "decision": decision,
                "pid": os.getpid(),
                "ppid": os.getppid(),
            }, f)
            f.write("\n")
    except Exception:
        pass


def _increment_block_counter():
    try:
        bc = pathlib.Path(BLOCK_COUNT_FILE)
        n = int(bc.read_text().strip()) if bc.exists() else 0
        bc.write_text(str(n + 1))
    except Exception:
        pass


def _patch_targets(command: object) -> list[str]:
    """Read canonical apply_patch targets, never patch content or shell text.

    Codex normalizes apply_patch to tool_input.command (not file_path). A
    malformed/unknown envelope cannot establish the write boundary: reject it.
    """
    if not isinstance(command, str):
        raise ValueError("invalid patch")
    lines = command.strip("\r\n").split("\n")
    lines = [line.removesuffix("\r") for line in lines]
    if not lines or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ValueError("invalid patch")
    targets: list[str] = []
    operation, body_seen, move_allowed, at_end = "", False, False, False
    marker_pending = False
    for line in lines[1:-1]:
        header = re.fullmatch(r"\*\*\* (Add File|Update File|Delete File|Move to): (.+)", line)
        if header:
            kind, target = header.groups()
            if target != target.strip() or any(ord(char) < 32 for char in target):
                raise ValueError("ambiguous path")
            if kind == "Move to":
                if not move_allowed:
                    raise ValueError("ambiguous move")
                move_allowed = False
            else:
                if operation == "Update File" and not body_seen:
                    raise ValueError("empty update")
                operation, body_seen, at_end, marker_pending = kind, False, False, False
                move_allowed = kind == "Update File"
            targets.append(target)
            continue
        move_allowed = False
        if at_end:
            raise ValueError("unexpected patch content")
        if operation == "Add File" and line.startswith("+"):
            body_seen = True
        elif operation == "Update File":
            if line == "@@" or line.startswith("@@ "):
                if marker_pending:
                    raise ValueError("empty hunk")
                body_seen = False
                marker_pending = True
            elif line == "*** End of File" and body_seen:
                at_end = True
            elif not line or line[0] in " +-":
                body_seen = True
                marker_pending = False
            else:
                raise ValueError("invalid update")
        else:
            raise ValueError("invalid patch body")
    if not targets or (operation == "Update File" and not body_seen):
        raise ValueError("empty patch")
    return targets


def _guard_patch(payload: dict) -> int:
    """Check every source/destination against event cwd; emit no patch data."""
    try:
        cwd = payload.get("cwd")
        if not isinstance(cwd, str) or not pathlib.Path(cwd).is_absolute():
            raise ValueError("ambiguous cwd")
        targets = _patch_targets(payload.get("tool_input", {}).get("command"))
        repo_real = pathlib.Path(REPO_ROOT).resolve()
        for target in targets:
            path_real = (pathlib.Path(cwd) / target).resolve()
            if path_real.is_relative_to(repo_real) and not _is_path_under_allowed_worktree(path_real):
                _increment_block_counter()
                sys.stderr.write("WORKTREE ISOLATION VIOLATION: apply_patch targets main checkout. Use a dedicated worktree.\n")
                return 2
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        sys.stderr.write("WORKTREE ISOLATION: cannot establish apply_patch targets; provide a canonical patch and absolute cwd.\n")
        return 2
    return 0


def main():
    if _kill_switch_active():
        sys.exit(0)

    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = payload.get("tool_name", "")
    if tool_name == "apply_patch":
        sys.exit(_guard_patch(payload))
    if tool_name not in {"Edit", "Write", "MultiEdit"}:
        sys.exit(0)

    file_path = payload.get("tool_input", {}).get("file_path", "")
    if not file_path:
        sys.exit(0)

    try:
        fp_real = pathlib.Path(file_path).resolve()
    except Exception:
        sys.exit(0)

    repo_real = pathlib.Path(REPO_ROOT).resolve()

    # Quick exit: file outside repo entirely (e.g. ~/.claude/, /tmp/, etc) → allow
    try:
        is_under_repo = fp_real.is_relative_to(repo_real)
    except AttributeError:
        try:
            fp_real.relative_to(repo_real)
            is_under_repo = True
        except ValueError:
            is_under_repo = False

    if not is_under_repo:
        _probe_log(payload, file_path, "allow_outside_repo")
        sys.exit(0)

    # File is under REPO_ROOT. Is it under an allowed worktree?
    if _is_path_under_allowed_worktree(fp_real):
        _probe_log(payload, file_path, "allow_worktree")
        sys.exit(0)

    # File is under main checkout (REPO_ROOT but not in worktree). BLOCK.
    _increment_block_counter()
    _probe_log(payload, file_path, "block")

    sys.stderr.write(
        f"WORKTREE ISOLATION VIOLATION (file write to main)\n"
        f"  tool: {tool_name}\n"
        f"  file_path: {file_path}\n"
        f"  resolved: {fp_real}\n\n"
        f"Reason: writing to main checkout would race with other AI agents.\n"
        f"This is the exact pattern that produced 32+ sibling-orphan stash in 24h.\n\n"
        f"Resolution:\n"
        f"  1. Create dedicated worktree:\n"
        f"     python scripts/agent_start.py --lane <lane> --task-id <task-id>\n"
        f"  2. Rewrite file_path to use worktree absolute path:\n"
        f"     {REPO_ROOT}/.worktrees/<lane>-<task-id>/<rest>\n\n"
        f"Emergency escape: AGENT_WORKTREE_ENFORCEMENT=false\n\n"
        f"See: docs/runbooks/agent-worktree-broker.md\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
