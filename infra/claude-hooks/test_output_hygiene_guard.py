#!/usr/bin/env python3
"""test_output_hygiene_guard.py — the spec's §6 case corpus (C01-C82), run
against the real hook as a subprocess exactly as Claude Code would (JSON on
stdin, exit 2 = DENY, exit 0 = ALLOW).

Spec: docs/specs/2026-09-18-output-hygiene-guard-shapes-spec.md
Fixtures (§6 preamble): bigdir/ (151 visible), middir/ (100 visible, proxy
for "a repo root's size"), smalldir/ (3), dotdir/ (30 visible + 160
dotfiles), small.py (1 KiB), big.log (25 KiB), huge.md (100 KiB in 1,600
lines), photo.png (200 KiB), oneline.txt (1 MiB, no newline); HOME is a
fixture with a 957-entry mailbox/broadcast and its own huge.md.

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
(_TMP / "huge.md").write_bytes((b"x" * 63 + b"\n") * 1600)
(_TMP / "photo.png").write_bytes(b"\x89PNG" + b"\0" * (200 * 1024 - 4))
(_TMP / "oneline.txt").write_bytes(b"z" * (1024 * 1024))
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
(_HOME / "huge.md").write_bytes((b"x" * 63 + b"\n") * 1600)

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
    ("C62", "cat big.log | sed -n '1,40p'", "ALLOW", "§4 sed -n range, quoted"),
    ("C63", "cat big.log | awk 'NR<=20'", "ALLOW", "§4 awk NR bound, quoted"),
    ("C64", "find /tmp/x -depth -delete", "ALLOW", "S5 own-bound: -delete prints nothing"),
    ("C65", "find . -name '*.pyc' -delete", "ALLOW", "S5 own-bound: -delete, glob irrelevant"),
    ("C66", "find . -delete -print", "DENY", "-print re-opens the walk's output"),
]

# (id, tool_name, tool_input, expect "DENY"/"ALLOW", why)
TOOL_CASES: list[tuple[str, str, dict, str, str]] = [
    ("C67", "Read", {"file_path": "huge.md"}, "DENY", "S9 default slice is 100 KiB"),
    ("C68", "Read", {"file_path": "huge.md", "limit": 200}, "ALLOW", "S9 own-bound"),
    ("C69", "Read", {"file_path": "huge.md", "offset": 1500}, "ALLOW", "S9 own-bound"),
    (
        "C70", "Read", {"file_path": "huge.md", "offset": 10, "limit": 1000},
        "DENY", "S9 slice exceeds 24 KiB",
    ),
    ("C71", "Read", {"file_path": "big.log"}, "DENY", "S9 one-line file has no byte cap"),
    ("C72", "Read", {"file_path": "small.py"}, "ALLOW", "S9 under threshold"),
    ("C73", "Read", {"file_path": "photo.png"}, "ALLOW", "S9 exempt suffix"),
    ("C74a", "Read", {"file_path": "missing.md"}, "ALLOW", "S9 missing file fail-open"),
    ("C74b", "Read", {"file_path": "bigdir"}, "ALLOW", "S9 directory fail-open"),
    (
        "C75", "Read", {"file_path": "huge.md", "limit": "200"},
        "ALLOW", "S9 non-integer bound fail-open",
    ),
    ("C76", "Skill", {"skill": "claude-api"}, "DENY", "S10 denied name"),
    (
        "C77", "Skill", {"skill": "anthropic-agent-skills:claude-api"},
        "DENY", "S10 bare name after last colon",
    ),
    ("C78", "Skill", {"skill": "modus"}, "ALLOW", "S10 allows every other skill"),
    ("C79a", "Read", {"file_path": "huge.md"}, "ALLOW", "S9 kill switch"),
    ("C79b", "Skill", {"skill": "claude-api"}, "ALLOW", "S10 kill switch"),
    ("C80a", "Read", {}, "ALLOW", "S9 missing file_path fail-open"),
    ("C80b", "Skill", {}, "ALLOW", "S10 missing skill fail-open"),
    ("C80c", "Skill", {"skill": 7}, "ALLOW", "S10 non-string skill fail-open"),
    ("C81", "Read", {"file_path": "~/huge.md"}, "DENY", "S9 tilde expanded against the fixture HOME"),
    ("C82", "Read", {"file_path": "oneline.txt"}, "DENY", "S9 1 MiB in ONE line, read in bounded chunks"),
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


def run_tool(tool: str, tool_input: dict, env_extra: dict | None = None) -> tuple[int, str]:
    payload = {"session_id": "t", "hook_event_name": "PreToolUse", "tool_name": tool,
               "tool_input": tool_input, "cwd": CWD}
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

    for cid, tool, tool_input, expect, desc in TOOL_CASES:
        seen_ids.add(cid.rstrip("abc"))
        env_extra = {"NUZ_OUTPUT_HYGIENE_OFF": "1"} if cid.startswith("C79") else None
        code, err = run_tool(tool, tool_input, env_extra)
        denied = code == 2
        if expect == "DENY" and not denied:
            failures.append(f"{cid}: WENT-BLIND: {desc}: expected DENY, got exit {code}")
        elif expect == "ALLOW" and denied:
            failures.append(
                f"{cid}: BIT-AN-INNOCENT: {desc}: expected ALLOW, got DENY\n"
                f"  stderr={err.strip()[:200]}"
            )
        if cid == "C67" and denied and ("KiB" not in err or "of 1600" not in err):
            failures.append(f"C67: denial message lacks KiB figure or total line count: {err[:200]}")
        if cid == "C81" and denied and "of 1600" not in err:
            failures.append(f"C81: denial message lacks the fixture HOME file's total line count: {err[:200]}")
        if cid == "C82" and denied and "1024 KiB (lines 1-1 of 1)" not in err:
            failures.append(f"C82: single-line denial must name 1024 KiB, lines 1-1 of 1: {err[:200]}")
        if cid == "C76" and denied and "claude-api" not in err:
            failures.append(f"C76: denial message lacks skill name: {err[:200]}")

    # completeness: every C01..C82 present (allow split row labels such as C58a/C80c)
    required = {f"C{n:02d}" for n in range(1, 83)}
    missing = required - seen_ids
    if missing:
        failures.append(f"INCOMPLETE-CORPUS: missing case IDs: {sorted(missing)}")

    # An unrelated tool must always allow, untouched.
    code, _ = _run_payload({"tool_name": "Edit", "tool_input": {"file_path": "x"}, "cwd": CWD})
    if code != 0:
        failures.append(f"UNRELATED-TOOL-BLOCKED: an Edit tool call was not exit 0 (got {code})")

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
VACCINE_MIN_IDS = {
    "C01", "C03", "C04", "C07", "C16", "C17", "C24", "C25", "C33",
    "C39", "C41", "C46", "C52", "C55", "C67", "C68", "C71", "C76", "C78",
}


def test_output_hygiene_guard():
    failures = evaluate()
    assert not failures, "OUTPUT-HYGIENE GUARD REGRESSIONS:\n" + "\n".join(failures)


if __name__ == "__main__":
    fails = evaluate()
    total = len(CASES) + len(TOOL_CASES) + 3
    if fails:
        print(f"=== {len(fails)}/{total} FAIL ===")
        for f in fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    case_ids = {c[0].rstrip("abc") for c in CASES} | {c[0].rstrip("abc") for c in TOOL_CASES}
    missing_vaccine = VACCINE_MIN_IDS - case_ids
    if missing_vaccine:
        print(f"=== VACCINE-MIN-SET INCOMPLETE: {missing_vaccine} ===")
        sys.exit(1)
    t0 = time.perf_counter()
    run("pytest -q bigdir")
    allow_ms = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    run("git log")
    deny_ms = (time.perf_counter() - t0) * 1000
    print(f"=== ALL {total} OK (C01..C82 present, no innocent bitten, no guilt missed) ===")
    print(f"latency: allow-case subprocess {allow_ms:.1f}ms, deny-case subprocess {deny_ms:.1f}ms")
    sys.exit(0)
