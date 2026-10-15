"""B33 S1: did the tick that just ended bear a verdict, so that the wrapper may start the next one at once?

Run by localci_merger_tick.sh from the copy it extracts at the tick's sha, with its stdlib interpreter:

    python -I tick_chain.py <decisions.jsonl> <offset> <rc>

It prints ``chain <kinds>`` or ``stop <why>`` and always exits 0: the wrapper chains only on a first word of ``chain``, so a crash,
a timeout or an empty output is "no chain", which is today's behaviour. It reads the journal bytes from ``offset`` on (the size the
wrapper took before the tick) and never writes. docs/specs/localci-sovereign-2026-10-07.md, B33 S1.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SEAL = re.compile(r"[0-9a-f]{64}")
CHAIN_KINDS = ("decision", "ready_refreshed", "ready_refresh_failed", "pushed")
STOP_KINDS = ("error", "evicted", "merge_error", "push_unlanded", "push_refused", "storage_diverged")


def verdict(journal: Path, offset: int, rc: int) -> tuple[bool, str]:
    if rc != 0:
        return False, f"tick rc={rc}"
    if not isinstance(offset, int) or offset < 0:
        return False, "offset unreadable"
    try:
        with journal.open("rb") as fh:
            size = fh.seek(0, 2)
            if offset > size:
                return False, "journal shorter than the offset taken before the tick"
            fh.seek(offset)
            data = fh.read()
    except OSError as exc:
        return False, f"journal unreadable: {type(exc).__name__}"
    kinds: list[str] = []
    for raw in data.split(b"\n"):
        if not raw.strip():
            continue   # journal() starts a line with "\n" after a torn tail: an empty line is no row
        try:
            row = json.loads(raw)
        except ValueError:
            return False, "an appended line is not JSON"
        if not isinstance(row, dict):
            return False, "an appended line is not a JSON object"
        kind = row.get("kind")
        if kind in STOP_KINDS:
            return False, f"{kind} row"
        if kind == "decision":
            if row.get("error") is not None:
                return False, "decision with an error"
            if row.get("host_no_verdict"):
                return False, "decision with a host no-verdict"
            if not (isinstance(row.get("seal"), str) and SEAL.fullmatch(row["seal"])):
                return False, "decision without a seal"
            kinds.append("decision")
        elif kind in CHAIN_KINDS:
            kinds.append(kind)
    if not kinds:
        return False, "no verdict row appended"
    return True, ",".join(sorted(set(kinds)))


def main(argv: list[str]) -> int:
    try:
        journal, offset, rc = Path(argv[1]), int(argv[2]), int(argv[3])
        ok, why = verdict(journal, offset, rc)
    except Exception as exc:  # noqa: BLE001 — any doubt is "no chain"
        ok, why = False, f"predicate failed: {type(exc).__name__}"
    print(f"{'chain' if ok else 'stop'} {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
