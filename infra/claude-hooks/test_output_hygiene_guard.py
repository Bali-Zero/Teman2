#!/usr/bin/env python3
"""test_output_hygiene_guard.py — the spec's §6 case corpus (C01-C61), run
against the real hook as a subprocess exactly as Claude Code would (JSON on
stdin, exit 2 = DENY, exit 0 = ALLOW).

Spec: docs/specs/2026-09-18-output-hygiene-guard-shapes-spec.md
Fixtures (§6 preamble): bigdir/ (151 visible), middir/ (100 visible, proxy
for "a repo root's size"), smalldir/ (3), dotdir/ (30 visible + 160
dotfiles), small.py (1 KiB), big.log (25 KiB); HOME is a fixture with a
957-entry mailbox/broadcast.

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

_TMP = pathlib.Path(tempfile.mkdtemp(prefix="output_hygiene_v2_"))
(_TMP / "bigdir").mkdir()
for _i in range(151):
    (_TMP / "bigdir" / f"f{_i}.txt").write_text("x")
(_TMP / "middir").mkdir()
for _i in range(100):
    (_TMP / "middir" / f"f{_i}.txt").write_text("x")
(_TMP / "smalldir").mkdir()
for _i in range(3):
    (_TMP / "smalldir" / f"f{_i}.txt").write_text("x")
(_TMP / "dotdir").mkdir()
for _i in range(30):
    (_TMP / "dotdir" / f"v{_i}.txt").write_text("x")
for _i in range(160):
    (_TMP / "dotdir" / f".h{_i}").write_text("x")
(_TMP / "big.log").write_text("x" * (25 * 1024))
(_TMP / "small.py").write_text("print(1)\n")
CWD = str(_TMP)

_HOME = pathlib.Path(tempfile.mkdtemp(prefix="output_hygiene_v2_home_"))
(_HOME / "mailbox" / "broadcast").mkdir(parents=True)
for _i in range(957):
    (_HOME / "mailbox" / "broadcast" / f"m{_i}.json").write_text("{}")
# HOME root itself: 30 visible entries (mailbox/ is one of them) + 160 dotfiles,
# so `ls ~` (30 visible, ALLOW) and `ls -a ~` (190, DENY) both have real fixtures.
for _i in range(29):
    (_HOME / f"v{_i}.txt").write_text("x")
for _i in range(160):
    (_HOME / f".h{_i}").write_text("x")

# (id, command, expect "DENY"/"ALLOW", why)
CASES: list[tuple[str, str, str, str]] = [
    ("C01", "ls", "ALLOW", "S1 under threshold (cwd itself, 6 entries)"),
    ("C02", "ls -la middir", "ALLOW", "100 entries, no dotfiles, still < 150"),
    ("C03", "ls ~/mailbox/broadcast", "DENY", "S1 957 visible"),
    ("C04", "ls ~/mailbox/broadcast 2>/dev/null", "DENY", "stderr redirect is not a bound"),
    ("C05", "ls ~/mailbox/broadcast | head -5", "ALLOW", "bounded by head"),
    ("C06", "ls ~/mailbox/broadcast > /tmp/x.txt", "ALLOW", "stdout redirected"),
    ("C07", "ls -R smalldir", "DENY", "recursive, count irrelevant"),
    ("C08", "eza -T smalldir", "DENY", "recursive"),
    ("C09", "ls ~", "ALLOW", "dotdir-as-HOME visible count 30, not raw"),
    ("C10", "ls -a ~", "DENY", "190 with -a"),
    ("C11", "ls middir smalldir bigdir", "DENY", "every target counted, bigdir wins"),
    ("C12", "ls -d bigdir", "ALLOW", "-d lists the dir itself"),
    ("C13", "cat big.log", "DENY", "S2 > 24 KiB"),
    ("C14", "cat big.log | jq .", "ALLOW", "consumer"),
    ("C15", "cat > out.txt <<'EOF'\nfind . -name x\nEOF", "ALLOW", "heredoc body stripped, stdout redirected"),
    ("C16", "git log", "DENY", "S3 unbounded"),
    ("C17", "git log --oneline origin/main..HEAD", "ALLOW", "range"),
    ("C18", "git log --oneline main..", "ALLOW", "one-sided range"),
    ("C19", "git log --format=%H", "DENY", "format does not bound"),
    ("C20", "git --no-pager log", "DENY", "global option peeled, still S3"),
    ("C21", "git -C . log", "DENY", "same"),
    ("C22", "git log -1 --format=%cd -- CLAUDE.md", "ALLOW", "-1"),
    ("C23", "git diff", "DENY", "S4"),
    ("C24", "git diff --stat", "ALLOW", "own-bound"),
    ("C25", "git diff --quiet && echo clean", "ALLOW", "prints nothing"),
    ("C26", "git show -s --format=%H HEAD", "ALLOW", "no patch"),
    ("C27", "git show --no-patch HEAD", "ALLOW", "no patch"),
    ("C28", "git -c core.pager=cat diff", "DENY", "global -c peeled, still S4"),
    ("C29", "find . -name '*.x'", "DENY", "S5 no depth, glob pattern does not bound"),
    ("C30", "find . -maxdepth 2 -name x", "ALLOW", "depth"),
    ("C31", "find . -name x | head", "ALLOW", "consumer"),
    ("C61", "find . -name x", "ALLOW", "literal -name is an S5 own-bound (§3 row)"),
    ("C32", "rg foo", "DENY", "S6 no target, no bound"),
    ("C33", "rg foo small.py", "ALLOW", "named file"),
    ("C34", 'rg "def main" small.py', "ALLOW", "quoted pattern stripped, file still named"),
    ("C35", "rg foo small.py bigdir", "DENY", "a directory target"),
    ("C36", "rg --max-count 5 foo bigdir", "ALLOW", "long-form -m"),
    ("C37", "grep -rn foo . | head", "ALLOW", "consumer"),
    ("C38", "grep -n foo small.py", "ALLOW", "not recursive"),
    ("C39", "pytest bigdir", "DENY", "S7"),
    ("C40", "pytest -q bigdir", "ALLOW", "-q"),
    ("C41", "pytest -xq bigdir", "ALLOW", "cluster contains q"),
    ("C42", "pytest -qq bigdir", "ALLOW", "cluster"),
    ("C43", "python3 -m pytest bigdir", "DENY", "python -m form"),
    ("C44", "timeout 300 pytest bigdir", "DENY", "prefix peeled"),
    ("C45", "FOO=1 pytest bigdir", "DENY", "assignment peeled"),
    ("C46", "npx vitest run", "DENY", "package runner"),
    ("C47", "npx jest -q", "ALLOW", "-q"),
    ("C48", "pytest bigdir 2>&1 | tail -20", "ALLOW", "consumer"),
    ("C49", "tail -f big.log", "DENY", "S8"),
    ("C50", "timeout 10 tail -f big.log", "ALLOW", "timeout bounds S8"),
    ("C51", "tail -n 20 big.log", "ALLOW", "not S8"),
    ("C52", "git status\ngit log", "DENY", "newline split"),
    ("C53", "cd smalldir\nls ~/mailbox/broadcast", "DENY", "newline split, cwd tracked"),
    ("C54", 'echo "git log"', "ALLOW", "quoted"),
    ("C55", "ssh pro 'git log'", "ALLOW", "remote"),
    ("C56", 'ls "$UNKNOWN_VAR/x"', "ALLOW", "unresolvable path, fail-open"),
    ("C57", "git log", "ALLOW", "kill switch (env-gated, see below)"),
    ("C58a", "not json at all", "ALLOW", "fail-open: malformed stdin"),
    ("C59", "ls ~/mailbox/broadcast &", "ALLOW", "background"),
    (
        "C60",
        "git log | git diff --stat $(git merge-base HEAD HEAD)",
        "DENY",
        "first segment unbounded (pipe into a non-consumer)",
    ),
]


def _run_payload(payload: dict, env_extra: dict | None = None) -> tuple[int, str]:
    env = dict(os.environ)
    env.pop("NUZ_OUTPUT_HYGIENE_OFF", None)
    env["HOME"] = str(_HOME)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload), capture_output=True, text=True, env=env, timeout=15,
    )
    return proc.returncode, proc.stderr


def run(cmd: str, env_extra: dict | None = None) -> tuple[int, str]:
    payload = {"session_id": "t", "hook_event_name": "PreToolUse", "tool_name": "Bash",
               "tool_input": {"command": cmd}, "cwd": CWD}
    return _run_payload(payload, env_extra)


def evaluate() -> list[str]:
    failures = []
    seen_ids = set()
    for cid, cmd, expect, desc in CASES:
        seen_ids.add(cid.rstrip("ab"))
        if cid == "C57":
            code, err = run(cmd, env_extra={"NUZ_OUTPUT_HYGIENE_OFF": "1"})
        elif cid == "C58a":
            proc = subprocess.run([sys.executable, str(HOOK)], input=cmd,
                                   capture_output=True, text=True, timeout=15)
            code, err = proc.returncode, proc.stderr
            denied = code == 2
            if expect == "ALLOW" and denied:
                failures.append(f"{cid}: BIT-AN-INNOCENT: {desc}: expected ALLOW got DENY\n  {err[:200]}")
            continue
        else:
            code, err = run(cmd)
        denied = code == 2
        if expect == "DENY" and not denied:
            failures.append(f"{cid}: WENT-BLIND: {desc}: expected DENY, got exit {code}")
        elif expect == "ALLOW" and denied:
            failures.append(f"{cid}: BIT-AN-INNOCENT: {desc}: expected ALLOW, got DENY\n  stderr={err.strip()[:200]}")

    # completeness: every C01..C61 present (allow the C58/C60 split naming)
    required = {f"C{n:02d}" for n in range(1, 62)}
    missing = required - seen_ids
    if missing:
        failures.append(f"INCOMPLETE-CORPUS: missing case IDs: {sorted(missing)}")

    # Non-Bash tool must always allow, untouched.
    code, _ = _run_payload({"tool_name": "Read", "tool_input": {"file_path": "x"}, "cwd": CWD})
    if code != 0:
        failures.append(f"NON-BASH-BLOCKED: a Read tool call was not exit 0 (got {code})")

    # A list / non-dict stdin must fail open.
    proc = subprocess.run([sys.executable, str(HOOK)], input="[1,2,3]",
                           capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        failures.append(f"MALFORMED-INPUT-BLOCKED: a JSON list was not exit 0 (got {proc.returncode})")

    # command: 123 (not a string) must fail open.
    code, _ = _run_payload({"tool_name": "Bash", "tool_input": {"command": 123}, "cwd": CWD})
    if code != 0:
        failures.append(f"NON-STRING-COMMAND-BLOCKED: exit {code}, expected 0")

    return failures


# ---- §7 vaccine minimum set: mirrored here too (also in test_hook_innocence.py) ----
VACCINE_MIN_IDS = {"C01", "C03", "C04", "C07", "C16", "C17", "C24", "C25", "C33", "C39", "C41", "C46", "C52", "C55"}


def test_output_hygiene_guard():
    failures = evaluate()
    assert not failures, "OUTPUT-HYGIENE GUARD REGRESSIONS:\n" + "\n".join(failures)


if __name__ == "__main__":
    fails = evaluate()
    total = len(CASES) + 3
    if fails:
        print(f"=== {len(fails)}/{total} FAIL ===")
        for f in fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    missing_vaccine = VACCINE_MIN_IDS - {c[0] for c in CASES}
    if missing_vaccine:
        print(f"=== VACCINE-MIN-SET INCOMPLETE: {missing_vaccine} ===")
        sys.exit(1)
    t0 = time.perf_counter()
    run("pytest -q bigdir")
    allow_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    run("git log")
    deny_ms = (time.perf_counter() - t0) * 1000
    print(f"=== ALL {total} OK (C01..C61 present, no innocent bitten, no guilt missed) ===")
    print(f"latency: allow-case subprocess {allow_ms:.1f}ms, deny-case subprocess {deny_ms:.1f}ms")
    sys.exit(0)
