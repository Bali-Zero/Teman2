#!/usr/bin/env python3
"""Redaction + fail-open trap-table for session_budget.py (K3 artifact-on-death).

Proves: (1) a git diff containing an OpenAI-shaped secret (`sk-abc123...`)
never appears verbatim in the written handoff markdown, replaced by a
[REDACTED] marker, while the harmless diff --stat filename survives; (2) the
handoff file actually lands at ~/.claude/state/handoff/<session_id>.md
(HOME-overridden to a tempdir); (3) the hook exits 0 on garbage/empty stdin
(never blocks the Stop-shaped event that invoked it).

Run: python3 scripts/tests/test_session_budget_handoff.py  (exit 0 = all green)
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / "infra" / "claude-hooks" / "session_budget.py"
LEAKED_SECRET = "sk-abc123def456ghi789"


def _init_repo_with_secret_diff(repo: pathlib.Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.local"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
    f = repo / "config.py"
    f.write_text("API_KEY = 'placeholder'\n")
    subprocess.run(["git", "-C", str(repo), "add", "config.py"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    f.write_text(f"API_KEY = '{LEAKED_SECRET}'\n")  # uncommitted — shows up in `git diff`


def _run_hook(env_home: pathlib.Path, payload) -> tuple:
    env = dict(os.environ)
    env["HOME"] = str(env_home)
    stdin = json.dumps(payload) if payload is not None else ""
    r = subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True, env=env, timeout=20)
    return r.stdout, r.returncode


def main() -> int:
    fails = 0

    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        home = tmp / "home"
        home.mkdir()
        repo = tmp / "repo"
        _init_repo_with_secret_diff(repo)

        session_id = "sess-redact-cccc"
        payload = {"session_id": session_id, "hook_event_name": "SubagentStop", "cwd": str(repo)}
        out, rc = _run_hook(home, payload)
        handoff = home / ".claude" / "state" / "handoff" / f"{session_id}.md"

        ok = rc == 0
        fails += 0 if ok else 1
        print(f"  [{'OK ' if ok else 'FAIL'}] exit code: rc={rc} (expect 0)")

        ok = handoff.exists()
        fails += 0 if ok else 1
        print(f"  [{'OK ' if ok else 'FAIL'}] handoff file written: {handoff}")

        if handoff.exists():
            text = handoff.read_text()

            leaked = LEAKED_SECRET in text
            ok = not leaked
            fails += 0 if ok else 1
            print(f"  [{'OK ' if ok else 'FAIL'}] secret NOT in handoff (leaked={leaked})")

            ok = "[REDACTED]" in text
            fails += 0 if ok else 1
            print(f"  [{'OK ' if ok else 'FAIL'}] redaction marker present")

            ok = "config.py" in text  # the filename itself is not a secret — must survive
            fails += 0 if ok else 1
            print(f"  [{'OK ' if ok else 'FAIL'}] diff --stat filename survived redaction")

            ok = "session-redact-cccc" not in text.replace(session_id, "")  # sanity: no crash-junk
            # (weak self-check, real assertions are above)

        # --- empty stdin: still exits 0, never raises past main() ---
        out2, rc2 = _run_hook(home, None)
        ok = rc2 == 0
        fails += 0 if ok else 1
        print(f"  [{'OK ' if ok else 'FAIL'}] empty stdin: rc={rc2} (expect 0)")

        # --- malformed json stdin: still exits 0 ---
        env = dict(os.environ)
        env["HOME"] = str(home)
        r = subprocess.run([sys.executable, str(HOOK)], input="{not valid json", capture_output=True, text=True, env=env, timeout=20)
        ok = r.returncode == 0
        fails += 0 if ok else 1
        print(f"  [{'OK ' if ok else 'FAIL'}] malformed json stdin: rc={r.returncode} (expect 0)")

    print("=== ALL GREEN ===" if not fails else f"=== {fails} FAIL ===")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
