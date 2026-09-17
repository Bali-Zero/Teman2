#!/usr/bin/env python3
"""test_output_hygiene_guard.py — guilt+innocence proof (cicatrix #3: no guard
merges without both). Builds a throwaway cwd with the fixtures the guard's
checks need, invokes the real hook as a subprocess exactly as Claude Code
would (JSON on stdin, exit 2 = BLOCK, exit 0 = ALLOW).

Run: python3 infra/claude-hooks/test_output_hygiene_guard.py
Also: pytest infra/claude-hooks/test_output_hygiene_guard.py -q
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "output_hygiene_guard.py"

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="output_hygiene_"))
(_TMP / "bigdir").mkdir()
for _i in range(61):
    (_TMP / "bigdir" / f"f{_i}.txt").write_text("x")
(_TMP / "smalldir").mkdir()
for _i in range(3):
    (_TMP / "smalldir" / f"f{_i}.txt").write_text("x")
(_TMP / "big.log").write_text("x" * (25 * 1024))
(_TMP / "small.py").write_text("print(1)\n")
CWD = str(_TMP)

# (command, expect "BLOCK"/"ALLOW", description)
CASES: list[tuple[str, str, str]] = [
    # ---- GUILT (one per shape) ----
    ("ls bigdir", "BLOCK", "shape1: ls on a >60-entry directory"),
    ("eza bigdir", "BLOCK", "shape1: eza on a >60-entry directory"),
    ("cat big.log", "BLOCK", "shape2: cat of a >24KB file"),
    ("bat big.log", "BLOCK", "shape2: bat of a >24KB file"),
    ("git log", "BLOCK", "shape3: git log without -n"),
    ("git diff", "BLOCK", "shape4: git diff without --stat"),
    ("find .", "BLOCK", "shape5: find without -maxdepth"),
    ("grep -r foo .", "BLOCK", "shape6: grep -r without -l/-c/-m"),
    ("rg foo .", "BLOCK", "shape6: rg without -l/-c/-m"),
    ("pytest", "BLOCK", "shape7: pytest without -q"),
    ("tail -f big.log", "BLOCK", "shape8: tail -f never terminates"),
    # ---- INNOCENCE (every example named in the spec) ----
    ("ls | head", "ALLOW", "ls piped to head"),
    ("ls -1 bigdir | wc -l", "ALLOW", "ls -1 piped to wc -l"),
    ("ls smalldir", "ALLOW", "ls on a small directory"),
    ("cat small.py", "ALLOW", "cat of a small file"),
    ("cat big.log | tail -20", "ALLOW", "cat piped to tail (no -f)"),
    ("git log -3", "ALLOW", "git log with -n bound"),
    ("git log --oneline | head -5", "ALLOW", "git log piped to head"),
    ("git diff --stat", "ALLOW", "git diff --stat"),
    ("git diff HEAD~1 -- small.py | head -40", "ALLOW", "git diff piped to head"),
    ("find . -maxdepth 2 -name x", "ALLOW", "find with -maxdepth"),
    ("grep -rl foo .", "ALLOW", "grep -rl bounded by -l"),
    ("grep -rn foo . | head", "ALLOW", "grep -rn piped to head"),
    ("pytest -q", "ALLOW", "pytest -q"),
    ("pytest tests/x.py 2>&1 | tail -3", "ALLOW", "pytest piped to tail"),
    ('echo "git log"', "ALLOW", "quoted git log is text, not a command"),
    ("ssh pro 'git log'", "ALLOW", "remote dispatch runs off-box"),
    ("tail -20 big.log", "ALLOW", "bounded tail, no -f"),
    ("python3 small.py", "ALLOW", "arbitrary script is not a guilt shape"),
    (
        "cat <<'EOF'\nfind . -name x\ncat big.log\nEOF",
        "ALLOW",
        "heredoc body containing find/cat is data, not a command",
    ),
]


def run(cmd: str, env_extra: dict | None = None) -> tuple[int, str]:
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": CWD}
    env = dict(os.environ)
    env.pop("NUZ_OUTPUT_HYGIENE_OFF", None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=15,
    )
    return proc.returncode, proc.stderr


def evaluate() -> list[str]:
    failures = []
    for cmd, expect, desc in CASES:
        code, err = run(cmd)
        blocked = code == 2
        if expect == "BLOCK" and not blocked:
            failures.append(f"WENT-BLIND: {desc}: expected BLOCK, got exit {code}")
        elif expect == "ALLOW" and blocked:
            failures.append(f"BIT-AN-INNOCENT: {desc}: expected ALLOW, got BLOCK\n  stderr={err.strip()[:200]}")

    # Kill switch: a guilty command with NUZ_OUTPUT_HYGIENE_OFF=1 must ALLOW.
    code, _ = run("git log", env_extra={"NUZ_OUTPUT_HYGIENE_OFF": "1"})
    if code != 0:
        failures.append(f"KILL-SWITCH-DEAD: NUZ_OUTPUT_HYGIENE_OFF=1 did not allow, exit {code}")

    # Non-Bash tool must always allow, untouched.
    payload = {"tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": CWD}
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(payload),
        capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        failures.append(f"NON-BASH-BLOCKED: a Read tool call was not exit 0 (got {proc.returncode})")

    # Malformed stdin must fail open.
    proc = subprocess.run(
        [sys.executable, str(HOOK)], input="not json", capture_output=True, text=True, timeout=15,
    )
    if proc.returncode != 0:
        failures.append(f"MALFORMED-INPUT-BLOCKED: malformed stdin was not exit 0 (got {proc.returncode})")

    return failures


def test_output_hygiene_guard():
    failures = evaluate()
    assert not failures, "OUTPUT-HYGIENE GUARD REGRESSIONS:\n" + "\n".join(failures)


if __name__ == "__main__":
    fails = evaluate()
    total = len(CASES) + 3  # kill switch + non-Bash + malformed-input
    if fails:
        print(f"=== {len(fails)}/{total} FAIL ===")
        for f in fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    t0 = time.perf_counter()
    run("git log -3")
    allow_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    run("git log")
    deny_ms = (time.perf_counter() - t0) * 1000
    print(f"=== ALL {total} OK (no innocent bitten, no guilt missed) ===")
    print(f"latency: allow-case subprocess {allow_ms:.1f}ms, deny-case subprocess {deny_ms:.1f}ms")
    sys.exit(0)
