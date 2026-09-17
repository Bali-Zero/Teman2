#!/usr/bin/env python3
"""cc_context_cost_report — what this machine's Claude Code sessions actually cost,
read from the transcripts on disk.

WHY. `/usage` answers for the session you are sitting in and OTEL needs a
collector nobody here runs, so the fleet has never had a per-machine number: the
only cost signal available today is a model's guess. Every session already writes
its own usage into `~/.claude/projects/<slug>/<session>.jsonl`, one record per
assistant turn. This reads those files and aggregates them. No model is asked
anything, nothing is sent anywhere.

CONSUMER: a human or an Opus session comparing M5/Pro/Mini, and the O1 row of
research/agent-craft/cc-meta-loop/BACKLOG.md. Run it per machine over ssh.

PII: reads ONLY the `usage` object and `model`/timestamp fields of assistant
records. Message content is never parsed, never printed, never stored.

Usage:
    python3 scripts/cc_context_cost_report.py                 # last 7 days
    python3 scripts/cc_context_cost_report.py --days 1 --json
    python3 scripts/cc_context_cost_report.py --top-sessions 10
"""

from __future__ import annotations

import argparse
import json
import socket
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS = Path.home() / ".claude" / "projects"


def scan(days: int) -> tuple[dict, dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    per_day: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_session: dict[str, dict] = {}
    for jf in PROJECTS.glob("*/*.jsonl"):
        try:
            if datetime.fromtimestamp(jf.stat().st_mtime, timezone.utc) < cutoff:
                continue
        except OSError:
            continue
        sess = {"turns": 0, "in": 0, "cache_read": 0, "cache_write": 0, "out": 0, "models": set()}
        try:
            with jf.open(errors="replace") as fh:
                for line in fh:
                    # cheap prefilter: the vast majority of lines carry no usage
                    if '"usage"' not in line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    msg = rec.get("message") or {}
                    u = msg.get("usage") or {}
                    if not u:
                        continue
                    day = str(rec.get("timestamp", ""))[:10] or "unknown"
                    d = per_day[day]
                    for key, field in (
                        ("in", "input_tokens"),
                        ("cache_read", "cache_read_input_tokens"),
                        ("cache_write", "cache_creation_input_tokens"),
                        ("out", "output_tokens"),
                    ):
                        v = int(u.get(field) or 0)
                        d[key] += v
                        sess[key] += v
                    d["turns"] += 1
                    sess["turns"] += 1
                    if msg.get("model"):
                        sess["models"].add(msg["model"])
        except OSError:
            continue
        if sess["turns"]:
            sess["models"] = sorted(sess["models"])
            per_session[jf.stem[:8]] = sess
    return per_day, per_session


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--top-sessions", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    per_day, per_session = scan(args.days)
    host = socket.gethostname()
    if args.json:
        print(json.dumps({"host": host, "days": args.days, "per_day": per_day,
                          "per_session": per_session}, indent=1, default=list))
        return 0

    print(f"host {host} · last {args.days} day(s) · source: transcripts on disk\n")
    print(f"{'day':12} {'turns':>7} {'input':>12} {'cache read':>13} {'cache write':>13} {'output':>10}")
    tot = defaultdict(int)
    for day in sorted(per_day):
        d = per_day[day]
        print(f"{day:12} {d['turns']:>7} {d['in']:>12,} {d['cache_read']:>13,} {d['cache_write']:>13,} {d['out']:>10,}")
        for k, v in d.items():
            tot[k] += v
    print(f"{'TOTAL':12} {tot['turns']:>7} {tot['in']:>12,} {tot['cache_read']:>13,} {tot['cache_write']:>13,} {tot['out']:>10,}")
    billed = tot["in"] + tot["cache_write"] + tot["cache_read"]
    print(f"\ncontext tokens read across all turns: {billed:,}")
    if tot["turns"]:
        print(f"average context per turn: {billed // tot['turns']:,}")
    print(f"\ntop {args.top_sessions} sessions by context read:")
    for sid, s in sorted(per_session.items(), key=lambda kv: -(kv[1]["in"] + kv[1]["cache_read"] + kv[1]["cache_write"]))[: args.top_sessions]:
        ctx = s["in"] + s["cache_read"] + s["cache_write"]
        print(f"  {sid}  turns {s['turns']:>4}  context {ctx:>14,}  out {s['out']:>9,}  {','.join(m.split('-')[1] if '-' in m else m for m in s['models'])[:28]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
