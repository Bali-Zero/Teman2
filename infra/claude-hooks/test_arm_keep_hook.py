#!/usr/bin/env python3
"""W80 arm-before-remove guard — guilt+innocence with REAL git worktrees.

The shared innocence vaccine (test_hook_innocence.py) runs against a SYNTHETIC
non-git repo, so it can only cover the W80 cases whose verdict needs no git state
(out-of-scope rm, quoted echo, read-only list, non-existent target). This suite
covers the part that DOES need state: a worktree that is dirty-and-unarmed must be
BLOCKED, while the same worktree once ARMED — and a clean one — must be ALLOWED.

It builds a throwaway git repo with three worktrees, invokes the real on-disk hook
exactly as Claude Code does (JSON on stdin, exit 2 = BLOCK), then tears everything
down. Skips cleanly if git is unavailable.

Run:  python3 infra/claude-hooks/test_arm_keep_hook.py
      pytest infra/claude-hooks/test_arm_keep_hook.py -q
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT_SRC = HERE.parent.parent                       # real repo (for arm_keep + hook source)
HOOK_SRC = HERE / "worktree_isolation.py"
ARM_KEEP_SRC = REPO_ROOT_SRC / "scripts" / "arm_keep_worktrees.py"


def _git(args: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd),
                          capture_output=True, text=True, timeout=30)


def _run_hook(hook: pathlib.Path, cmd: str, cwd: str, repo_root: str) -> int:
    env = dict(os.environ)
    env["NUZ_REPO_ROOT"] = repo_root
    env.pop("AGENT_WORKTREE_ENFORCEMENT", None)
    env.pop("HOST_BOUNDARY_OFF", None)
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": cwd}
    proc = subprocess.run([sys.executable, str(hook)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=20, env=env)
    return proc.returncode


def _build_repo(tmp: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a git repo carrying the agent_start.py signature + a first commit.
    Returns (repo_root, runnable_hook_path)."""
    root = tmp / "main"
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "agent_start.py").write_text("# signature\n")
    (root / "infra" / "claude-hooks").mkdir(parents=True)
    # bring the real hook + arm_keep into the synthetic repo so imports/paths line up
    shutil.copy2(HOOK_SRC, root / "infra" / "claude-hooks" / "worktree_isolation.py")
    shutil.copy2(ARM_KEEP_SRC, root / "scripts" / "arm_keep_worktrees.py")
    _git(["init", "-q"], root)
    _git(["config", "user.email", "t@t.t"], root)
    _git(["config", "user.name", "t"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-qm", "init"], root)
    return root, root / "infra" / "claude-hooks" / "worktree_isolation.py"


def _add_worktree(root: pathlib.Path, name: str) -> pathlib.Path:
    wt = root / ".worktrees" / name
    _git(["worktree", "add", "-q", "-b", f"b/{name}", str(wt), "HEAD"], root)
    return wt


def _arm(root: pathlib.Path, wt: pathlib.Path) -> None:
    sys.path.insert(0, str(root / "scripts"))
    try:
        import importlib
        import arm_keep_worktrees  # noqa
        importlib.reload(arm_keep_worktrees)
        # arm_keep resolves REPO_ROOT from its own __file__ → the synthetic root. Good.
        arm_keep_worktrees._arm_one(wt, apply=True)
    finally:
        sys.path.pop(0)


def evaluate() -> list[str]:
    if not shutil.which("git"):
        return []  # no git → skip (treated as pass)
    fails: list[str] = []
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="armkeep_hook_"))
    try:
        root, hook = _build_repo(tmp)
        rr = str(root)

        # 1) dirty + unarmed → BLOCK
        dirty = _add_worktree(root, "dirty")
        (dirty / "UNTRACKED.txt").write_text("work\n")
        for cmd, desc in [
            (f"git worktree remove --force {dirty}", "git worktree remove dirty+unarmed"),
            (f"rm -rf {dirty}", "rm -rf dirty+unarmed"),
        ]:
            if _run_hook(hook, cmd, rr, rr) != 2:
                fails.append(f"WENT-BLIND: {desc} → expected BLOCK")

        # 2) dirty + ARMED → ALLOW
        armed = _add_worktree(root, "armed")
        (armed / "UNTRACKED.txt").write_text("work\n")
        _arm(root, armed)
        if _run_hook(hook, f"git worktree remove --force {armed}", rr, rr) == 2:
            fails.append("BIT-INNOCENT: remove dirty+ARMED → expected ALLOW")

        # 3) clean → ALLOW
        clean = _add_worktree(root, "clean")
        if _run_hook(hook, f"git worktree remove {clean}", rr, rr) == 2:
            fails.append("BIT-INNOCENT: remove CLEAN worktree → expected ALLOW")
    finally:
        # best-effort: prune worktrees then nuke tmp
        try:
            _git(["worktree", "prune"], tmp / "main")
        except Exception:
            pass
        shutil.rmtree(tmp, ignore_errors=True)
    return fails


def test_arm_keep_hook():
    fails = evaluate()
    assert not fails, "W80 arm-before-remove regressions:\n" + "\n".join(fails)


if __name__ == "__main__":
    f = evaluate()
    if f:
        print(f"=== {len(f)} FAIL ===")
        for x in f:
            print("  [FAIL] " + x)
        sys.exit(1)
    print("=== W80 arm-before-remove guard OK (blocks dirty+unarmed, spares armed+clean) ===")
    sys.exit(0)
