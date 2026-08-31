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

REPORT_DIR = Path.home() / ".claude" / "canon-blocks.d"
DEFAULT_PEERS = ("pro", "mini")

# scp with no BatchMode prompts for a password on inherited stdin and blocks
# FOREVER when a peer resolves but has no key auth — from a scheduler that is a
# silently wedged job, and a wedged publisher is how the report goes stale
# (kimi-code/k3, 2026-08-31). The probe module already carries exactly these
# options; the publisher was not using them.
SCP_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15"]
SCP_TIMEOUT_S = 60


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
    ap.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    ap.add_argument(
        "--peers",
        default=",".join(DEFAULT_PEERS),
        help="comma-separated ssh hosts to push the report to",
    )
    ap.add_argument(
        "--no-push", action="store_true", help="write locally, push nowhere"
    )
    ap.add_argument(
        "--machine",
        help="name to publish under (default: this host). For a machine whose "
        "hostname changed, and for building a synthetic multi-machine fixture: "
        "the corpus cannot otherwise simulate a second machine, because every "
        "fragment would be written under this host's name.",
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

    me = args.machine or socket.gethostname().split(".")[0]

    # ONE FILE PER MACHINE, never a shared document each machine rewrites.
    # The previous shape merged locally and then scp'd the WHOLE file: A pushes
    # {A} to B, C pushes {C} to B, and A's entry is gone from B — with no lock,
    # no re-merge on receipt, and no way for the freshness stamps to tell an
    # ERASED peer from a quiet one (kimi-code/k3, 2026-08-31). A machine now
    # writes only its own fragment, so two publishers cannot destroy each other's
    # work and there is nothing to merge or lock.
    fragment = {
        "machine": me,
        "blocks": blocks,
        "seen_at": time.time(),
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    args.report_dir.mkdir(parents=True, exist_ok=True)
    path = args.report_dir / f"{me}.json"
    # Write-then-rename: a reader (or a peer's scp) hitting a half-written file
    # would report the whole organ unreadable, which is the guard lying about its
    # own health for a reason that has nothing to do with doctrine.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(fragment, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)
    print(f"canon-publish: {len(blocks)} block(s) from {me} -> {path}")

    if args.no_push:
        return 0

    # The remote destination is written as a TILDE, never as this machine's
    # absolute path. M5's home is /Users/balizero and Pro's is /Users/nuzantara,
    # so reusing the local absolute path publishes where the remote probe never
    # reads: the file lands, scp reports success, and every machine keeps
    # comparing against nothing (Codex sol + kimi-code/k3, 2026-08-31).
    remote = f"~/.claude/canon-blocks.d/{me}.json"

    failures = 0
    for host in [h.strip() for h in args.peers.split(",") if h.strip()]:
        # `host` is an SSH ALIAS (`pro`, `mini`) and `me` is a hostname
        # (`Air-M5`, `Nuzantara`), so they never compare equal: the old skip-self
        # guard could not fire, and a machine copying its own fragment onto
        # itself was reported as a successful peer push. Under the fragment
        # scheme that copy is a byte-identical no-op rather than a corruption,
        # but it is still a push that proves nothing, so it is named.
        r = subprocess.run(
            ["scp", "-q", *SCP_OPTS, str(path), f"{host}:{remote}"],
            capture_output=True,
            text=True,
            timeout=SCP_TIMEOUT_S,
        )
        ok = r.returncode == 0
        print(f"  push {host}: {'ok' if ok else 'FAILED — ' + r.stderr.strip()[:120]}")
        failures += 0 if ok else 1
    if failures:
        # Loud, because a peer that did not receive the fragment keeps comparing
        # against an older one until it goes quiet — and a stale comparison is
        # exactly the confident lie this whole organ exists to prevent.
        print(f"canon-publish: {failures} peer push(es) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
