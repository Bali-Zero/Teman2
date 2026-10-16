#!/usr/bin/env python3
"""B33 S2 reader: per-context p95 memory / disk / setup of the candidate containers, from the receipts under one or more run dirs.

    capacity_report.py ~/.nuzantara-pilots/local-ci/merger/runs            # every run dir below it
    capacity_report.py RUN_DIR [RUN_DIR ...] [--json]

Consumer: whoever sizes B33 S3's `resources:` declarations (p95 + 25 %) and prices S4 from the copy-in. The tick does not call it; it reads,
it never writes, and nothing in a verdict reads what it prints. Setup = create + copy-in + junit + remove; nulls are ignored per column."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

SETUP = ("t_create", "t_copy_in", "t_junit", "t_remove")


def probes_of(receipt: dict) -> list:
    res = receipt.get("result") if isinstance(receipt, dict) else None
    if not isinstance(res, dict):
        return []
    rows = [res.get("sandbox")] + [j.get("sandbox") for j in res.get("jobs") or [] if isinstance(j, dict)]
    return [p for r in rows if isinstance(r, list) for p in r if isinstance(p, dict)]


def p95(values: list) -> float | None:
    """Nearest rank."""
    v = sorted(x for x in values if isinstance(x, (int, float)))
    return v[max(0, math.ceil(0.95 * len(v)) - 1)] if v else None


def setup_of(p: dict) -> float | None:
    parts = [p.get(k) for k in SETUP]
    return round(sum(x for x in parts if isinstance(x, (int, float))), 3) if any(isinstance(x, (int, float)) for x in parts) else None


def collect(dirs: list) -> dict:
    by_ctx: dict[str, list] = {}
    for d in dirs:
        for rp in sorted(Path(d).glob("**/receipts/*.json")):
            try:
                rec = json.loads(rp.read_text())
            except (OSError, ValueError):
                continue
            if isinstance(rec, dict) and (ps := probes_of(rec)):
                by_ctx.setdefault(str(rec.get("check") or rp.stem), []).extend(ps)
    return by_ctx


def table(by_ctx: dict) -> list:
    rows = []
    for ctx, ps in sorted(by_ctx.items()):
        mem, disk = p95([p.get("mem_peak_bytes") for p in ps]), p95([p.get("disk_rw_bytes") for p in ps])
        rows.append({"context": ctx, "n": len(ps), "p95_mem_gib": None if mem is None else round(mem / 2**30, 2),
                     "p95_disk_mib": None if disk is None else round(disk / 2**20, 1), "p95_setup_s": p95([setup_of(p) for p in ps]),
                     "p95_copy_in_s": p95([p.get("t_copy_in") for p in ps])})
    return rows


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    rows = table(collect(a.dirs))
    if a.json:
        print(json.dumps(rows, indent=1))
        return 0
    cols = ("context", "n", "p95_mem_gib", "p95_disk_mib", "p95_setup_s", "p95_copy_in_s")
    cell = lambda v: "-" if v is None else str(v)   # noqa: E731
    out = [cols, *[tuple(cell(r[c]) for c in cols) for r in rows]]
    w = [max(len(row[i]) for row in out) for i in range(len(cols))]
    for row in out:
        print("  ".join(c.ljust(w[i]) for i, c in enumerate(row)).rstrip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
