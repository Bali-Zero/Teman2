#!/usr/bin/env python3
"""cc_hook_latency_bench.py — how long every PreToolUse handler takes on ONE Bash tool call,
on this machine, now.

WHY. The H10 row of research/agent-craft/cc-meta-loop/BACKLOG.md rests on a number (8 blocking
handlers, 364 ms serial on M5, 2026-09-17) that depends on which hooks are registered and how big
the session transcript is. A frozen number is a lie in a month; this script re-measures it.

WHAT. Builds a synthetic PreToolUse event for `Bash` (`ls -la`), points `transcript_path` at the
largest transcript under ~/.claude/projects (or --transcript), pipes the event on stdin to every
handler registered for PreToolUse in the project's .claude/settings.json and ~/.claude/settings.json
whose matcher covers Bash, and times each with perf_counter around subprocess.run. Plugin handlers
(${CLAUDE_PLUGIN_ROOT}) are skipped: their root is not resolvable outside a session. `--startup`
adds the interpreter/IO baseline (python3 -c pass, a 5-module import, full read of the transcript,
json.loads per line, a 64 KB tail seek), best of 5.

Read-only: nothing is written, no hook decision is acted on. A handler that exits 2 on the synthetic
event is reported, not treated as a defect — a context guard SHOULD trip on a 3 MB transcript.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HOME = Path.home()


def _handlers(settings: Path) -> list[tuple[str, bool, str]]:
    if not settings.exists():
        return []
    d = json.loads(settings.read_text())
    out = []
    for g in d.get("hooks", {}).get("PreToolUse", []):
        m = g.get("matcher", "*")
        if m not in ("*", "", "Bash") and "Bash" not in m:
            continue
        for h in g.get("hooks", []):
            c = h.get("command")
            if not c or "CLAUDE_PLUGIN_ROOT" in c:
                continue
            out.append((settings.name if settings.parent == HOME / ".claude" else str(settings), bool(h.get("async", False)), c))
    return out


def _largest_transcript() -> Path | None:
    best, size = None, -1
    for p in (HOME / ".claude" / "projects").glob("*/*.jsonl"):
        try:
            s = p.stat().st_size
        except OSError:
            continue
        if s > size:
            best, size = p, s
    return best


def _best_of(argv: list[str], n: int = 5) -> float:
    best = 1e9
    for _ in range(n):
        t0 = time.perf_counter()
        subprocess.run(argv, capture_output=True)
        best = min(best, time.perf_counter() - t0)
    return best * 1000


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--project", type=Path, default=Path.cwd())
    ap.add_argument("--transcript", type=Path, default=None)
    ap.add_argument("--startup", action="store_true", help="also print the interpreter/IO baseline")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    transcript = a.transcript or _largest_transcript()
    if transcript is None or not transcript.exists():
        print("no transcript found under ~/.claude/projects — pass --transcript", file=sys.stderr)
        return 2
    event = {
        "session_id": "bench", "transcript_path": str(transcript), "cwd": str(a.project),
        "hook_event_name": "PreToolUse", "tool_name": "Bash",
        "tool_input": {"command": "ls -la", "description": "bench"}, "permission_mode": "default",
    }
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(a.project)
    rows = []
    for src, is_async, cmd in _handlers(a.project / ".claude" / "settings.json") + _handlers(HOME / ".claude" / "settings.json"):
        c = cmd.replace("${CLAUDE_PROJECT_DIR}", str(a.project))
        t0 = time.perf_counter()
        try:
            r = subprocess.run(c, shell=True, input=json.dumps(event), capture_output=True, text=True, timeout=60, env=env)
            rc: int | str = r.returncode
        except subprocess.TimeoutExpired:
            rc = "TIMEOUT"
        rows.append({"ms": round((time.perf_counter() - t0) * 1000), "source": src, "async": is_async, "rc": rc, "command": cmd})
    rows.sort(key=lambda r: -r["ms"])
    blocking = [r for r in rows if not r["async"]]
    summary = {
        "transcript_bytes": transcript.stat().st_size,
        "handlers": len(rows), "blocking": len(blocking),
        "blocking_serial_ms": sum(r["ms"] for r in blocking),
    }
    if a.startup:
        t = str(transcript)
        summary["startup"] = {
            "python3 -c pass": round(_best_of(["python3", "-c", "pass"])),
            "import json,re,sys,os,pathlib": round(_best_of(["python3", "-c", "import json,re,sys,os,pathlib"])),
            "read transcript fully": round(_best_of(["python3", "-c", f"open({t!r}).read()"])),
            "json.loads each line": round(_best_of(["python3", "-c", f"import json\nfor l in open({t!r}):\n    json.loads(l)"])),
            "tail 64KB seek": round(_best_of(["python3", "-c", f"f=open({t!r},'rb');f.seek(-65536,2);f.read()"])),
        }
    if a.json:
        print(json.dumps({"summary": summary, "handlers": rows}, indent=1))
        return 0
    print(f"transcript: {transcript} ({summary['transcript_bytes']:,} bytes)")
    for r in rows:
        print(f"{r['ms']:6d} ms  {r['source']:14s} async={str(r['async']):5s} rc={r['rc']}  {r['command'][:80]}")
    print(f"handlers on a Bash PreToolUse: {summary['handlers']} — blocking {summary['blocking']}, serial sum {summary['blocking_serial_ms']} ms")
    for k, v in summary.get("startup", {}).items():
        print(f"  startup  {k:32s} {v:5d} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
