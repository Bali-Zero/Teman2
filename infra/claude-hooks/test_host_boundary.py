#!/usr/bin/env python3
"""Trap-table for host_boundary.py (phase-aware BLOCK #1 / §9-A).

Mirror of test_w79_shell_write.py: a (command|file_path, cwd, expect_block)
table run against the REAL hook logic, plus a few process-level invocations to
prove exit codes. Each guard MUST: block writes into protected dirs/files,
ALLOW writes elsewhere (worktree, /tmp, repo), and never block on a read.

Run: python infra/claude-hooks/test_host_boundary.py  (exit 0 = all green)
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "host_boundary.py"


def _load_mod(fake_home: pathlib.Path):
    spec = importlib.util.spec_from_file_location("host_boundary_uut", str(HOOK))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    # Repoint the protected set at a FAKE home so the test never depends on the
    # real ~/.claude etc. (and never accidentally blocks on the tester's home).
    mod._HOME = fake_home
    mod.PROTECTED_DIRS = [
        fake_home / ".claude",
        fake_home / ".ssh",
        fake_home / ".aws",
        fake_home / ".agent" / "decisions",
    ]
    mod.PROTECTED_FILES = [
        fake_home / ".nuzantara-secrets.env",
        fake_home / ".zshenv",
        fake_home / ".zshrc",
    ]
    return mod


def main() -> int:
    # .resolve() up-front: on macOS tempfile gives /var/... which is a symlink to
    # /private/var/...; the hook's _resolve_target also .resolve()s, so the
    # protected set MUST be the resolved form or every match misses (W80/lsof
    # symlink-mismatch class).
    tmp = pathlib.Path(tempfile.mkdtemp()).resolve()
    home = tmp / "home"
    (home / ".claude" / "hooks").mkdir(parents=True)
    (home / ".ssh").mkdir(parents=True)
    (home / ".agent" / "decisions").mkdir(parents=True)
    repo = tmp / "Desktop" / "nuzantara"
    (repo / "apps").mkdir(parents=True)
    (repo / ".worktrees" / "lane-x").mkdir(parents=True)
    (tmp / "scratch").mkdir(parents=True)

    mod = _load_mod(home)
    H = str(home)
    R = str(repo)

    # --- Bash write/read trap table: (command, cwd, expect_block) ---
    bash_cases = [
        # BLOCK — writes into protected dirs/files
        (f"echo x > {H}/.claude/hooks/_phase.py", R, True),
        (f"sed -i 's/a/b/' {H}/.claude/settings.json", R, True),
        (f"cp /tmp/x {H}/.ssh/authorized_keys", R, True),
        (f"echo k >> {H}/.aws/credentials", R, True),
        (f"tee {H}/.nuzantara-secrets.env", R, True),
        (f"echo x > {H}/.zshrc", R, True),
        (f"echo j > {H}/.agent/decisions/state.json", R, True),
        # relative target resolving into protected dir (cwd = ~/.claude/hooks)
        ("echo x > _phase.py", f"{H}/.claude/hooks", True),
        # BLOCK survives heredoc/quote noise (W79 strip): real redirect into .claude
        (f"cat > {H}/.claude/x <<'EOF'\nbody with > and ssh words\nEOF", R, True),
        # ALLOW — writes elsewhere
        ("echo x > /tmp/scratch.txt", "/tmp", False),
        (f"echo x > {R}/apps/f.py", R, False),                     # repo (other hooks guard this)
        (f"echo x > {R}/.worktrees/lane-x/f.py", R, False),        # scratch worktree
        (f"echo x > {tmp}/scratch/note.md", R, False),             # neutral tmp dir
        # ALLOW — `>` inside quotes / heredoc body is NOT a real target
        (f'git commit -m "edit > .claude in message"', R, False),
        (f"echo \"writing to ~/.ssh someday\" > /tmp/note", "/tmp", False),
        # ALLOW — reads never block (secret read → WARN, exit 0, expect_block False)
        (f"cat {H}/.nuzantara-secrets.env", R, False),
        (f"cat {R}/apps/f.py", R, False),
        # ALLOW — fd-dup, sink
        ("python x.py 2>&1 | tail", R, False),
        ("echo ok > /dev/null", R, False),
    ]

    fails = 0
    for cmd, cwd, expect in bash_cases:
        got = mod._write_hits_sensitive(cmd, cwd) is not None
        ok = got == expect
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] block={got!s:5} expect={expect!s:5}  bash: {cmd[:60]}")

    # --- Edit/Write file_path cases (via _is_protected on resolved path) ---
    edit_cases = [
        (f"{H}/.claude/hooks/_phase.py", True),
        (f"{H}/.claude/settings.json", True),
        (f"{H}/.ssh/config", True),
        (f"{R}/apps/f.py", False),
        (f"{R}/.worktrees/lane-x/f.py", False),
        ("/tmp/x.py", False),
    ]
    for fp, expect in edit_cases:
        resolved = mod._resolve_target(fp, R)
        got = resolved is not None and mod._is_protected(resolved)
        ok = got == expect
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] block={got!s:5} expect={expect!s:5}  edit: {fp[:60]}")

    # --- Process-level exit-code check (real hook invocation) ---
    # Block case via Edit payload → expect exit 2; allow case → exit 0.
    # NB: the subprocess uses the REAL ~/.claude protected set, so we craft a
    # payload that targets the real home .claude path (read-only test of the
    # exit code path; nothing is written — the hook only inspects file_path).
    real_phase = str(pathlib.Path("~/.claude/hooks/_phase.py").expanduser())
    proc_cases = [
        ({"tool_name": "Edit", "tool_input": {"file_path": real_phase}, "cwd": R}, 2),
        ({"tool_name": "Edit", "tool_input": {"file_path": "/tmp/ok.py"}, "cwd": R}, 0),
        ({"tool_name": "Read", "tool_input": {"file_path": real_phase}, "cwd": R}, 0),  # Read tool not gated
    ]
    for payload, expect_rc in proc_cases:
        r = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                           capture_output=True, text=True)
        ok = r.returncode == expect_rc
        if not ok:
            fails += 1
        print(f"  [{'OK ' if ok else 'FAIL'}] rc={r.returncode} expect={expect_rc}  proc: {payload['tool_name']} {payload['tool_input']['file_path'][:40]}")

    print("=== ALL GREEN ===" if not fails else f"=== {fails} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
