#!/usr/bin/env python3
"""Innocence test suite — the immune system's immune system (cicatrix #3).

THE VACCINE. Every command-matching hook MUST prove it does NOT fire on a
corpus of LEGITIMATE inputs (innocence) while STILL firing on real danger
(guiltiness). Born from the opus-mythos hooks TAC (2026-06-16): a 3-part
census found that all 7 command-matching hooks shipped with ZERO innocence
tests, violating the superscar #3 antidote — "nessuna _guard_* mergiata senza
un test di innocenza". The over-match cancer (10/27 guardrail patterns using
`.*` greedy) is the symptom; this gate is the structural cure.

Each hook is invoked exactly as Claude Code invokes it: a JSON payload on
stdin, exit code 2 = BLOCK, exit code 0 = ALLOW. We run the REAL on-disk hook
file as a subprocess so the test exercises the true contract, not a mocked
internal function. INNOCENCE cases (expect ALLOW) are the false-positive
tripwires; GUILT cases (expect BLOCK) keep the hook honest so a lazy "always
allow" fix can't pass.

Run:  PYTHONPATH=. python3 infra/claude-hooks/test_hook_innocence.py
      (exit 0 = all clean, 1 = at least one hook bit an innocent OR went blind)

Also a pytest target:  pytest infra/claude-hooks/test_hook_innocence.py -q
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent              # infra/claude-hooks
SRC_ROOT = HERE.parent.parent                               # repo root (source of hooks)
SCRIPTS_HOOKS_SRC = SRC_ROOT / "scripts" / "hooks"

# The hooks treat the directory containing scripts/agent_start.py as the "main
# checkout" (their _is_nuzantara_root signature). We build a SYNTHETIC repo in a
# temp dir that carries that signature but is NOT under any .worktrees/ path, so
# the guilt cases (writes into "main") resolve correctly and the worktree
# allow-list logic is exercised honestly. The hook files are copied in. We pin
# REPO_ROOT for the hooks via NUZ_REPO_ROOT. Created once, reused by all cases.
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="hook_innocence_"))
REPO_ROOT = str(_TMP / "synthetic-main")
_SYN = pathlib.Path(REPO_ROOT)
(_SYN / "scripts" / "hooks").mkdir(parents=True, exist_ok=True)
(_SYN / "infra" / "claude-hooks").mkdir(parents=True, exist_ok=True)
(_SYN / "apps" / "backend-rag" / "backend" / "app").mkdir(parents=True, exist_ok=True)
# the repo signature the hooks look for
(_SYN / "scripts" / "agent_start.py").write_text("# synthetic signature\n")
# a registered worktree under the synthetic root's .worktrees/ for allow-list cases
(_SYN / ".worktrees" / "lane-x" / "apps").mkdir(parents=True, exist_ok=True)


def _copy_hook(name: str) -> pathlib.Path:
    """Copy the real hook into the synthetic repo and return the runnable path."""
    for src_dir, dst_dir in ((HERE, _SYN / "infra" / "claude-hooks"),
                             (SCRIPTS_HOOKS_SRC, _SYN / "scripts" / "hooks")):
        src = src_dir / name
        if src.exists():
            dst = dst_dir / name
            shutil.copy2(src, dst)
            return dst
    return HERE / name  # missing — report canonical location


# Resolve+stage every hook under test once.
_HOOK_CACHE: dict[str, pathlib.Path] = {}


def _hook_path(name: str) -> pathlib.Path:
    if name not in _HOOK_CACHE:
        _HOOK_CACHE[name] = _copy_hook(name)
    return _HOOK_CACHE[name]


# ---------------------------------------------------------------------------
# Case schema: (tool_name, command_or_filepath, expect) where expect in
# {"ALLOW","BLOCK","NUDGE"}.  NUDGE == never-blocks hooks: they must exit 0
# regardless, so for them every case is effectively ALLOW (we only assert the
# hook does not BLOCK; the systemMessage content is not load-bearing here).
# ---------------------------------------------------------------------------

def bash(cmd: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": REPO_ROOT}


def edit(path: str) -> dict:
    return {"tool_name": "Edit", "tool_input": {"file_path": path,
            "old_string": "a", "new_string": "b"}, "cwd": REPO_ROOT}


def write(path: str) -> dict:
    return {"tool_name": "Write", "tool_input": {"file_path": path,
            "content": "x"}, "cwd": REPO_ROOT}


WT = REPO_ROOT + "/.worktrees/lane-x"

CASES: dict[str, list[tuple[dict, str, str]]] = {
    # ---- worktree_isolation.py (Bash) — block git-mutate + shell-write into MAIN
    "worktree_isolation.py": [
        # INNOCENCE — these are real false-positives observed in-session or by design
        (bash("git log --oneline -5"), "ALLOW", "read-only git"),
        (bash("git status --short"), "ALLOW", "read-only git status"),
        (bash('git commit -m "fix: handle > redirect in parser"'), "ALLOW", "redirect glyph inside commit msg string"),
        (bash("git diff --name-only HEAD | grep -cE '^[<>]'"), "ALLOW", "regex '^[<>]' in single-quotes, not a redirect"),
        (bash("cat file.py 2>/tmp/err.log"), "ALLOW", "stderr redirect to /tmp"),
        (bash("npm install axios"), "ALLOW", "npm install != coreutils install into main"),
        (bash("pip3 install httpx"), "ALLOW", "pip install != coreutils install"),
        (bash("echo hello > /tmp/scratch.txt"), "ALLOW", "redirect to /tmp"),
        (bash(f"cp config.yaml {WT}/config.yaml"), "ALLOW", "cp into a worktree"),
        (bash(f"git -C {WT} checkout main"), "ALLOW", "git mutate inside worktree via -C"),
        (bash("grep -rn 'cp ' infra/ | head"), "ALLOW", "the word cp inside a grep pattern"),
        (bash("echo 'use tee to split output' "), "ALLOW", "the word tee inside a quoted string"),
        # GUILT — must still BLOCK
        (bash("git checkout main"), "BLOCK", "git checkout in main checkout"),
        (bash("git add ."), "BLOCK", "git add . in main"),
        (bash('git commit -a -m "x"'), "BLOCK", "git commit -a in main"),
        (bash("git stash"), "BLOCK", "git stash in main (sibling-orphan creator)"),
        (bash("echo poison > infra/claude-hooks/orchestrate_gate.py"), "BLOCK", "shell write into main checkout file"),
        (bash("sed -i 's/a/b/' apps/backend-rag/backend/app/main.py"), "BLOCK", "sed -i on main checkout file"),
    ],
    # ---- worktree_file_write_check.py (Edit/Write/MultiEdit)
    "worktree_file_write_check.py": [
        (write("/tmp/notes.md"), "ALLOW", "write outside repo (/tmp)"),
        (edit(os.path.expanduser("~/.claude/skills/x.md")), "ALLOW", "edit in $HOME (host_boundary's job, not this hook)"),
        (write(f"{WT}/apps/new.py"), "ALLOW", "write inside a worktree"),
        (write("/some/other/repo/file.py"), "ALLOW", "write in a different repo entirely"),
        # GUILT
        (write(REPO_ROOT + "/infra/brand_new_file.py"), "BLOCK", "write a new file into main checkout"),
        (edit(REPO_ROOT + "/apps/backend-rag/backend/app/main.py"), "BLOCK", "edit a main-checkout file"),
    ],
    # ---- orchestrate_gate.py (Bash/Edit/Write) — never blocks short/dispatched sessions
    # Without a long transcript on stdin it cannot reach the block branch → ALLOW.
    "orchestrate_gate.py": [
        (bash("ls -la"), "ALLOW", "no transcript path → cannot be a long undispatched session"),
        (edit("/tmp/x.py"), "ALLOW", "edit with no transcript context"),
    ],
    # ---- stadio_zero_nudge.py — NEVER blocks (soft nudge). Must always exit 0.
    "stadio_zero_nudge.py": [
        (edit("/tmp/x.py"), "NUDGE", "soft nudge never blocks"),
        (write(REPO_ROOT + "/apps/x.py"), "NUDGE", "even on a main-checkout edit, never blocks"),
    ],
    # ---- seam_verify.py — Stop hook, NEVER blocks. Different payload shape.
    "seam_verify.py": [
        ({"cwd": REPO_ROOT, "hook_event_name": "Stop"}, "NUDGE", "stop hook never blocks"),
    ],
}


def run_hook(hook: str, payload: dict) -> tuple[int, str]:
    """Invoke the real hook file as Claude Code does: JSON on stdin. Returns
    (exit_code, stderr)."""
    path = _hook_path(hook)
    if not path.exists():
        return (-1, f"HOOK MISSING: {path}")
    env = dict(os.environ)
    env["NUZ_REPO_ROOT"] = REPO_ROOT
    # ensure the kill switch is NOT set, or we'd test a disarmed hook
    env.pop("AGENT_WORKTREE_ENFORCEMENT", None)
    env.pop("HOST_BOUNDARY_OFF", None)
    try:
        proc = subprocess.run(
            [sys.executable, str(path)],
            input=json.dumps(payload),
            capture_output=True, text=True, timeout=15, env=env,
        )
        return (proc.returncode, proc.stderr)
    except subprocess.TimeoutExpired:
        return (-2, "TIMEOUT")


def evaluate() -> list[str]:
    failures: list[str] = []
    for hook, cases in CASES.items():
        for payload, expect, desc in cases:
            code, err = run_hook(hook, payload)
            if code < 0:
                failures.append(f"[{hook}] {desc}: hook error ({err.strip()[:80]})")
                continue
            blocked = code == 2
            if expect == "BLOCK":
                if not blocked:
                    failures.append(f"[{hook}] WENT-BLIND on guilt → {desc}: expected BLOCK, got exit {code}")
            else:  # ALLOW or NUDGE — must NOT block
                if blocked:
                    failures.append(
                        f"[{hook}] BIT-AN-INNOCENT → {desc}: expected ALLOW, got BLOCK\n"
                        f"        payload={json.dumps(payload)[:160]}\n"
                        f"        stderr={err.strip()[:160]}"
                    )
    return failures


def test_hook_innocence():
    failures = evaluate()
    assert not failures, "HOOK INNOCENCE/GUILT regressions:\n" + "\n".join(failures)


if __name__ == "__main__":
    fails = evaluate()
    total = sum(len(v) for v in CASES.values())
    if fails:
        print(f"=== {len(fails)}/{total} FAIL ===")
        for f in fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    print(f"=== ALL {total} OK (no innocent bitten, no guilt missed) ===")
    sys.exit(0)
