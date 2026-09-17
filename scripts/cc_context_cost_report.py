#!/usr/bin/env python3
"""cc_context_cost_report — what this machine's Claude Code sessions actually cost,
read from the transcripts on disk.

WHY. `/usage` answers for the session you are sitting in and OTEL needs a
collector nobody here runs, so the fleet has never had a per-machine number: the
only cost signal available today is a model's guess. Every session already writes
its own usage into `~/.claude/projects/<slug>/<session>.jsonl`, one record per
assistant turn — and every subagent dispatched from that session writes its own
sidecar transcript into `<slug>/<session>/subagents/*.jsonl`, invisible to a glob
that only looks one level deep. This reads both shapes and aggregates them. No
model is asked anything, nothing is sent anywhere.

CONSUMER: a human or an Opus session comparing M5/Pro/Mini, and the O1 row of
research/agent-craft/cc-meta-loop/BACKLOG.md. Run it per machine over ssh.

PII: reads ONLY the `usage` object and `model`/`timestamp` fields of assistant
records. Message content is never parsed, never printed, never stored.

GOTCHAS fixed here (measured on M5 2026-09-17):
  - `~/.claude/projects/-Users-balizero-nuzantara` is a SYMLINK to
    `-Users-balizero-Desktop-nuzantara`. A glob over `*/*.jsonl` walks both
    names and counts every session under it twice. Fixed by deduping on
    `(st_dev, st_ino)` — the same physical file is counted once regardless of
    how many project-dir names resolve to it.
  - `--days N` used to gate on the FILE's mtime, which is the timestamp of the
    file's LAST write, not of every record inside it: a file touched today can
    still hold turns from three weeks ago, and they were being counted as
    "today". Each record now carries its own `timestamp`, and that field —
    not the file — decides whether a turn falls inside the window. File mtime
    is kept only as a cheap pre-filter (a file whose mtime is already older
    than the cutoff cannot contain a record inside it) and as a per-record
    fallback for the rare record with no timestamp of its own.
  - Subagent transcripts were never globbed at all, so every subagent turn —
    a large fraction of this machine's actual spend — was invisible.

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
from typing import Iterator

PROJECTS = Path.home() / ".claude" / "projects"

# (glob pattern relative to PROJECTS, kind label)
TRANSCRIPT_GLOBS = (
    ("*/*.jsonl", "main"),
    ("*/*/subagents/*.jsonl", "subagent"),
)


def _iter_transcript_files() -> Iterator[tuple[Path, str]]:
    """Every transcript file exactly once, main sessions and subagent sidecars
    alike. `~/.claude/projects` holds symlinked project dirs pointing at the
    same physical tree (observed: `-Users-balizero-nuzantara` ->
    `-Users-balizero-Desktop-nuzantara`), so a plain glob lists the same file
    under two names. Dedup on (st_dev, st_ino), not on path string."""
    seen: set[tuple[int, int]] = set()
    for pattern, kind in TRANSCRIPT_GLOBS:
        for jf in PROJECTS.glob(pattern):
            try:
                st = jf.stat()
            except OSError:
                continue
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
            yield jf, kind, st.st_mtime


def scan(days: int) -> tuple[dict, dict, dict]:
    """Returns (per_day, per_session, meta). meta carries the file-count and
    fallback counters the report header needs to state what it filtered."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    per_day: dict[str, dict[str, dict[str, int]]] = defaultdict(
        lambda: {"main": defaultdict(int), "subagent": defaultdict(int)}
    )
    per_session: dict[str, dict] = {}
    distinct = 0
    fallback_mtime_records = 0

    for jf, kind, mtime in _iter_transcript_files():
        distinct += 1
        file_dt = datetime.fromtimestamp(mtime, timezone.utc)
        if file_dt < cutoff:
            # the file's LAST write is already outside the window, so no
            # record inside it can be inside the window either — cheap skip.
            continue
        sess_key = f"{kind[0]}:{jf.stem[:8]}"
        sess = {
            "kind": kind,
            "turns": 0,
            "in": 0,
            "cache_read": 0,
            "cache_write": 0,
            "out": 0,
            "models": set(),
        }
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
                    ts_raw = rec.get("timestamp")
                    if ts_raw:
                        try:
                            rec_dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
                        except ValueError:
                            rec_dt = file_dt
                            fallback_mtime_records += 1
                    else:
                        rec_dt = file_dt
                        fallback_mtime_records += 1
                    if rec_dt < cutoff:
                        continue
                    day = rec_dt.strftime("%Y-%m-%d")
                    d = per_day[day][kind]
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
            per_session[sess_key] = sess

    meta = {
        "distinct_files": distinct,
        "fallback_mtime_records": fallback_mtime_records,
    }
    return per_day, per_session, meta


def count_listed_vs_distinct() -> tuple[int, int]:
    """Proof for the symlink dedup: how many paths the raw globs list vs how
    many distinct physical files that resolves to."""
    listed = 0
    seen: set[tuple[int, int]] = set()
    for pattern, _kind in TRANSCRIPT_GLOBS:
        for jf in PROJECTS.glob(pattern):
            listed += 1
            try:
                st = jf.stat()
            except OSError:
                continue
            seen.add((st.st_dev, st.st_ino))
    return listed, len(seen)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--top-sessions", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    listed, distinct = count_listed_vs_distinct()
    per_day, per_session, meta = scan(args.days)
    host = socket.gethostname()

    if args.json:
        print(json.dumps({
            "host": host, "days": args.days,
            "files_listed": listed, "files_distinct": distinct,
            "fallback_mtime_records": meta["fallback_mtime_records"],
            "per_day": per_day, "per_session": per_session,
        }, indent=1, default=list))
        return 0

    print(f"host {host} · last {args.days} day(s), windowed by each record's OWN "
          f"`timestamp` field (not file mtime) · source: transcripts on disk")
    print(f"files: {listed} listed by glob, {distinct} distinct after dedup by inode "
          f"({listed - distinct} were the same physical file under a symlinked project dir)")
    if meta["fallback_mtime_records"]:
        print(f"note: {meta['fallback_mtime_records']} record(s) had no usable timestamp "
              f"and fell back to file mtime for bucketing")
    print()

    header = f"{'day':12} {'kind':9} {'turns':>7} {'input':>12} {'cache read':>13} {'cache write':>13} {'output':>10}"
    print(header)
    tot = defaultdict(int)
    tot_by_kind = {"main": defaultdict(int), "subagent": defaultdict(int)}
    for day in sorted(per_day):
        for kind in ("main", "subagent"):
            d = per_day[day][kind]
            if not d:
                continue
            print(f"{day:12} {kind:9} {d['turns']:>7} {d['in']:>12,} {d['cache_read']:>13,} "
                  f"{d['cache_write']:>13,} {d['out']:>10,}")
            for k, v in d.items():
                tot[k] += v
                tot_by_kind[kind][k] += v

    turns_main = tot_by_kind["main"]["turns"]
    turns_sub = tot_by_kind["subagent"]["turns"]
    print(f"{'TOTAL':12} {'main':9} {turns_main:>7} {tot_by_kind['main']['in']:>12,} "
          f"{tot_by_kind['main']['cache_read']:>13,} {tot_by_kind['main']['cache_write']:>13,} "
          f"{tot_by_kind['main']['out']:>10,}")
    print(f"{'TOTAL':12} {'subagent':9} {turns_sub:>7} {tot_by_kind['subagent']['in']:>12,} "
          f"{tot_by_kind['subagent']['cache_read']:>13,} {tot_by_kind['subagent']['cache_write']:>13,} "
          f"{tot_by_kind['subagent']['out']:>10,}")
    print(f"{'TOTAL':12} {'combined':9} {tot['turns']:>7} {tot['in']:>12,} {tot['cache_read']:>13,} "
          f"{tot['cache_write']:>13,} {tot['out']:>10,}")

    billed = tot["in"] + tot["cache_write"] + tot["cache_read"]
    print(f"\ncontext tokens read across all turns (main + subagent): {billed:,}")
    print(f"turns: {turns_main:,} main + {turns_sub:,} subagent = {tot['turns']:,} total")
    if tot["turns"]:
        print(f"average context per turn: {billed // tot['turns']:,}")

    print(f"\ntop {args.top_sessions} sessions by context read:")
    for sid, s in sorted(
        per_session.items(),
        key=lambda kv: -(kv[1]["in"] + kv[1]["cache_read"] + kv[1]["cache_write"]),
    )[: args.top_sessions]:
        ctx = s["in"] + s["cache_read"] + s["cache_write"]
        models = ",".join(m.split("-")[1] if "-" in m else m for m in s["models"])[:28]
        print(f"  {sid}  {s['kind']:9} turns {s['turns']:>4}  context {ctx:>14,}  out {s['out']:>9,}  {models}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
