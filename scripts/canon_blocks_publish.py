#!/usr/bin/env python3
"""canon_blocks_publish.py — publish this machine's canon-block digests to the fleet.

The read half lives in `scripts/proprioception.py::probe_canon_blocks`. This is
the write half, and it is deliberately a SEPARATE, explicitly-invoked script:
the probe must never write, because the file it watches is control-plane and
per-machine, and a watcher that can also write is one `--fix` away from becoming
the thing that makes the three copies diverge (superscar family #1).

It follows `claude_seat_quota.py`'s shape on purpose — one machine measures and
pushes, the others read — because that pattern is already in the fleet's hands
and a second, differently-shaped channel is a second thing to remember.

WHAT IT PUBLISHES: digests only. Never the block text. A canon block is doctrine
rather than secret, but a fleet report that carried content would be a fourth
copy of the file, and the whole point is that there are three.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPORT_PATH = Path.home() / ".claude" / "canon-blocks.json"
DEFAULT_PEERS = ("pro", "mini")


def _load_probe():
    """Import the digest function from the probe, rather than reimplementing it.

    Two implementations of "what is a canon block" would drift, and the drift
    would be invisible: the publisher would report digests the reader computes
    differently, and every machine would look DIVERGED from every other for a
    reason that is not in the doctrine at all.
    """
    import importlib.util

    src = Path(__file__).resolve().parent / "proprioception.py"
    spec = importlib.util.spec_from_file_location("proprioception", src)
    if spec is None or spec.loader is None:  # pragma: no cover - import shape
        raise SystemExit(f"canon-publish: cannot load {src}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="canon_blocks_publish")
    ap.add_argument("--claude-md", default="~/.claude/CLAUDE.md")
    ap.add_argument("--report-path", type=Path, default=REPORT_PATH)
    ap.add_argument(
        "--peers",
        default=",".join(DEFAULT_PEERS),
        help="comma-separated ssh hosts to push the report to",
    )
    ap.add_argument(
        "--no-push", action="store_true", help="write locally, push nowhere"
    )
    args = ap.parse_args(argv)

    src = Path(os.path.expanduser(args.claude_md))
    if not src.is_file():
        print(f"canon-publish: {src} not found", file=sys.stderr)
        return 2

    blocks = _load_probe()._canon_blocks(
        src.read_text(encoding="utf-8", errors="replace")
    )
    if not blocks:
        # Publishing an empty map would make every reader report "agreed" against
        # nothing. Refuse, and say which state this is.
        print(
            f"canon-publish: {src} has no <!-- CANON:<id> --> markers — nothing to publish. "
            "Mark the doctrine blocks first; an empty report reads as agreement.",
            file=sys.stderr,
        )
        return 3

    me = socket.gethostname().split(".")[0]
    report: dict = {"machines": {}}
    if args.report_path.is_file():
        try:
            report = json.loads(args.report_path.read_text())
            report.setdefault("machines", {})
        except (OSError, json.JSONDecodeError):
            report = {"machines": {}}
    now = time.time()
    report["machines"][me] = blocks
    # Per-machine freshness, because the report is MERGED: a machine that stops
    # publishing keeps its old digests in the file forever, and the file's own
    # mtime only ever reflects the LAST publisher. Without this, a peer that went
    # quiet a month ago is compared against as if it had answered this morning.
    report.setdefault("seen_at", {})[me] = now
    report["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    report["published_by"] = me

    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"canon-publish: {len(blocks)} block(s) from {me} -> {args.report_path}")

    if args.no_push:
        return 0

    failures = 0
    for host in [h.strip() for h in args.peers.split(",") if h.strip()]:
        if host == me:
            continue
        r = subprocess.run(
            ["scp", "-q", str(args.report_path), f"{host}:{args.report_path}"],
            capture_output=True,
            text=True,
        )
        ok = r.returncode == 0
        print(f"  push {host}: {'ok' if ok else 'FAILED — ' + r.stderr.strip()[:120]}")
        failures += 0 if ok else 1
    if failures:
        # Loud, because a peer that did not receive the report keeps comparing
        # against an older one until it goes stale — and a stale comparison is
        # exactly the confident lie this whole organ exists to prevent.
        print(f"canon-publish: {failures} peer push(es) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
