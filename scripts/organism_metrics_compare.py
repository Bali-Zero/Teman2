#!/usr/bin/env python3
"""Organism Metrics Comparator — Pro-Air side-by-side read-only CLI.

# Organo: scripts/ (read-only diagnostic, no state produced)
# Produce: terminal report (stdout)
# Consume: organism_metrics.db locale (+ Air via SSH se --remote)

SYMBIOSIS Law #3 (event-driven, no orchestrators): this is a pull-based
diagnostic tool, NOT a cron. Run on demand.

Usage::

    # Local only (Pro)
    python3 scripts/organism_metrics_compare.py

    # Include Air via SSH (remote read, zero writes)
    python3 scripts/organism_metrics_compare.py --remote

    # Filter by host / scope / metric
    python3 scripts/organism_metrics_compare.py --host pro --scope host
    python3 scripts/organism_metrics_compare.py --metric ia --since 2026-04-17

    # JSON output for programmatic use
    python3 scripts/organism_metrics_compare.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Config ─────────────────────────────────────────────────────────────────────

DEFAULT_DB_PATH = os.path.expanduser("~/.agent/decisions/organism_metrics.db")
AIR_REMOTE_DB = "~/.agent/decisions/organism_metrics.db"
AIR_SSH_HOST = "air"
DEFAULT_SINCE = "1970-01-01"  # all time by default


@dataclass
class Row:
    calculated_at: str
    collector_host: str | None
    metric_scope: str | None
    ttr: float | None
    do: float | None
    ia: float | None
    fe: float | None

    @classmethod
    def from_sqlite(cls, r: sqlite3.Row) -> Row:
        return cls(
            calculated_at=r["calculated_at"],
            collector_host=r["collector_host"] if "collector_host" in r.keys() else None,
            metric_scope=r["metric_scope"] if "metric_scope" in r.keys() else None,
            ttr=r["ttr_value"],
            do=r["do_value"],
            ia=r["ia_value"],
            fe=r["fe_value"],
        )

    @classmethod
    def from_pipe(cls, line: str) -> Row | None:
        parts = line.split("|")
        if len(parts) < 7:
            return None

        def _f(x: str) -> float | None:
            x = x.strip()
            return None if x in ("", "None") else float(x)

        return cls(
            calculated_at=parts[0].strip(),
            collector_host=parts[1].strip() or None,
            metric_scope=parts[2].strip() or None,
            ttr=_f(parts[3]),
            do=_f(parts[4]),
            ia=_f(parts[5]),
            fe=_f(parts[6]),
        )


# ── Readers ────────────────────────────────────────────────────────────────────


def read_local(db_path: str, since: str) -> list[Row]:
    """Read from local SQLite. Returns [] if DB missing."""
    if not os.path.isfile(db_path):
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(metabolic_snapshots)")}
        has_v2 = "collector_host" in cols and "metric_scope" in cols

        if has_v2:
            sql = """SELECT calculated_at, collector_host, metric_scope,
                            ttr_value, do_value, ia_value, fe_value
                       FROM metabolic_snapshots
                      WHERE calculated_at >= ?
                      ORDER BY calculated_at ASC"""
        else:
            sql = """SELECT calculated_at,
                            NULL AS collector_host, NULL AS metric_scope,
                            ttr_value, do_value, ia_value, fe_value
                       FROM metabolic_snapshots
                      WHERE calculated_at >= ?
                      ORDER BY calculated_at ASC"""

        rows = conn.execute(sql, (since,)).fetchall()
        return [Row.from_sqlite(r) for r in rows]
    finally:
        conn.close()


def read_remote_air(since: str, timeout: int = 10) -> list[Row]:
    """Read Air's DB via SSH. Returns [] if Air unreachable.

    Uses piped output (calculated_at|collector|scope|ttr|do|ia|fe) to stay
    robust across SQLite versions. Zero writes — SELECT only.
    """
    query = (
        "SELECT calculated_at, "
        "COALESCE(collector_host,''), COALESCE(metric_scope,''), "
        "COALESCE(ttr_value,''), COALESCE(do_value,''), "
        "COALESCE(ia_value,''), COALESCE(fe_value,'') "
        "FROM metabolic_snapshots "
        f"WHERE calculated_at >= '{since}' "
        "ORDER BY calculated_at ASC;"
    )
    cmd = [
        "ssh", "-o", f"ConnectTimeout={timeout}",
        AIR_SSH_HOST,
        f"sqlite3 -separator '|' {AIR_REMOTE_DB} \"{query}\"",
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 5
        )
        if result.returncode != 0:
            print(f"[warn] Air unreachable: {result.stderr.strip()}", file=sys.stderr)
            return []
        rows: list[Row] = []
        for line in result.stdout.splitlines():
            row = Row.from_pipe(line)
            if row:
                rows.append(row)
        return rows
    except subprocess.TimeoutExpired:
        print(f"[warn] Air SSH timeout after {timeout}s", file=sys.stderr)
        return []
    except Exception as e:
        print(f"[warn] Air SSH failed: {e}", file=sys.stderr)
        return []


# ── Filtering ──────────────────────────────────────────────────────────────────


def filter_rows(
    rows: list[Row],
    host: str | None,
    scope: str | None,
) -> list[Row]:
    out = rows
    if host and host != "both":
        out = [r for r in out if r.collector_host == host]
    if scope and scope != "both":
        out = [r for r in out if r.metric_scope == scope]
    return out


# ── Stats ──────────────────────────────────────────────────────────────────────


def summarize(rows: list[Row], metric: str) -> dict[str, Any]:
    """Return {count, non_null, min, max, median, mean, last} for metric."""
    values = [getattr(r, metric) for r in rows]
    non_null = [v for v in values if v is not None]
    if not non_null:
        return {
            "count": len(rows), "non_null": 0,
            "min": None, "max": None, "median": None, "mean": None, "last": None,
        }
    return {
        "count": len(rows),
        "non_null": len(non_null),
        "min": min(non_null),
        "max": max(non_null),
        "median": round(statistics.median(non_null), 4),
        "mean": round(statistics.mean(non_null), 4),
        "last": non_null[-1],
    }


# ── Rendering ──────────────────────────────────────────────────────────────────


def render_table(rows: list[Row], show_raw: bool) -> str:
    if not rows:
        return "(no rows match filters)"

    if show_raw:
        lines = ["when                           | host | scope  | TTR     | DO      | IA      | FE     "]
        lines.append("-" * 92)
        for r in rows:
            lines.append(
                f"{r.calculated_at:30s} | {(r.collector_host or '?'):4s} "
                f"| {(r.metric_scope or '?'):6s} "
                f"| {str(r.ttr) if r.ttr is not None else '  —  ':>7s} "
                f"| {str(r.do) if r.do is not None else '  —  ':>7s} "
                f"| {str(r.ia) if r.ia is not None else '  —  ':>7s} "
                f"| {str(r.fe) if r.fe is not None else '  —  ':>7s}"
            )
        return "\n".join(lines)

    # Grouped summary by (collector, scope)
    groups: dict[tuple[str, str], list[Row]] = {}
    for r in rows:
        key = (r.collector_host or "?", r.metric_scope or "?")
        groups.setdefault(key, []).append(r)

    lines = [
        "host | scope   | metric | N  | nn | min      | max      | median   | mean     | last    ",
        "-" * 100,
    ]
    for (host, scope), group_rows in sorted(groups.items()):
        for metric in ("ttr", "do", "ia", "fe"):
            s = summarize(group_rows, metric)
            if s["non_null"] == 0:
                continue  # skip all-null series
            lines.append(
                f"{host:4s} | {scope:7s} | {metric.upper():6s} "
                f"| {s['count']:2d} | {s['non_null']:2d} "
                f"| {s['min']!s:8s} | {s['max']!s:8s} "
                f"| {s['median']!s:8s} | {s['mean']!s:8s} | {s['last']!s:8s}"
            )
    return "\n".join(lines)


def render_compare(
    pro_rows: list[Row],
    air_rows: list[Row],
    metric: str,
) -> str:
    """Side-by-side Pro vs Air for a single metric (host scope only)."""
    pro_host = [r for r in pro_rows if r.metric_scope == "host"]
    air_host = [r for r in air_rows if r.metric_scope == "host"]
    air_global = [r for r in air_rows if r.metric_scope == "global"]

    pro_s = summarize(pro_host, metric)
    air_host_s = summarize(air_host, metric)
    air_global_s = summarize(air_global, metric)

    lines = [f"═══ {metric.upper()} — Pro vs Air ═══"]

    # Pro host
    if pro_s["non_null"] > 0:
        lines.append(
            f"  Pro  (host)   : n={pro_s['non_null']:2d}  median={pro_s['median']!s:<8s}  "
            f"last={pro_s['last']!s:<8s}  range=[{pro_s['min']!s}..{pro_s['max']!s}]"
        )
    else:
        lines.append(f"  Pro  (host)   : no data")

    # Air host
    if air_host_s["non_null"] > 0:
        lines.append(
            f"  Air  (host)   : n={air_host_s['non_null']:2d}  median={air_host_s['median']!s:<8s}  "
            f"last={air_host_s['last']!s:<8s}  range=[{air_host_s['min']!s}..{air_host_s['max']!s}]"
        )
    else:
        lines.append(f"  Air  (host)   : no data")

    # Air global (system-level, only when metric is TTR/DO)
    if metric in ("ttr", "do") and air_global_s["non_null"] > 0:
        lines.append(
            f"  Air  (global) : n={air_global_s['non_null']:2d}  median={air_global_s['median']!s:<8s}  "
            f"last={air_global_s['last']!s:<8s}  range=[{air_global_s['min']!s}..{air_global_s['max']!s}]"
        )

    # Delta Pro vs Air (host-level only)
    if pro_s["non_null"] > 0 and air_host_s["non_null"] > 0:
        delta_median = pro_s["median"] - air_host_s["median"]
        delta_last = pro_s["last"] - air_host_s["last"]
        lines.append(
            f"  Δ median (Pro − Air host): {delta_median:+.4f}   "
            f"Δ last: {delta_last:+.4f}"
        )

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare Pro vs Air metabolic_snapshots (read-only)"
    )
    parser.add_argument(
        "--db-path", default=DEFAULT_DB_PATH,
        help=f"Local SQLite path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--remote", action="store_true",
        help="Also pull Air's DB via SSH (read-only SELECT)",
    )
    parser.add_argument(
        "--host", choices=["pro", "air", "both"], default="both",
        help="Filter by collector_host",
    )
    parser.add_argument(
        "--scope", choices=["global", "host", "both"], default="both",
        help="Filter by metric_scope",
    )
    parser.add_argument(
        "--metric", choices=["ttr", "do", "ia", "fe", "all"], default="all",
        help="Zoom a single metric (side-by-side view)",
    )
    parser.add_argument(
        "--since", default=DEFAULT_SINCE,
        help="ISO date lower bound (default: all time)",
    )
    parser.add_argument(
        "--raw", action="store_true",
        help="Print each snapshot row instead of aggregates",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON for programmatic use",
    )
    args = parser.parse_args()

    # Read sources
    local_rows = read_local(args.db_path, args.since)
    remote_rows: list[Row] = []
    if args.remote:
        remote_rows = read_remote_air(args.since)

    all_rows = local_rows + remote_rows

    # Deduplicate by (calculated_at, collector_host, metric_scope) —
    # if --remote was used on Pro that already has air rows backfilled, avoid double count.
    seen = set()
    unique_rows: list[Row] = []
    for r in all_rows:
        key = (r.calculated_at, r.collector_host, r.metric_scope)
        if key not in seen:
            seen.add(key)
            unique_rows.append(r)

    filtered = filter_rows(unique_rows, args.host, args.scope)

    if args.json:
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "source_db": args.db_path,
            "remote_queried": args.remote,
            "total_rows": len(unique_rows),
            "filtered_rows": len(filtered),
            "filters": {"host": args.host, "scope": args.scope, "since": args.since},
            "summaries": {},
        }
        for metric in ("ttr", "do", "ia", "fe"):
            for host_key in ("pro", "air"):
                for scope_key in ("global", "host"):
                    subset = [
                        r for r in filtered
                        if r.collector_host == host_key and r.metric_scope == scope_key
                    ]
                    if subset:
                        payload["summaries"][f"{host_key}_{scope_key}_{metric}"] = \
                            summarize(subset, metric)
        print(json.dumps(payload, indent=2, default=str))
        return 0

    # Text output
    print(f"Organism Metrics Comparator — {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}")
    print(f"Source: {args.db_path}" + (" (+ Air via SSH)" if args.remote else ""))
    print(f"Filters: host={args.host}, scope={args.scope}, since={args.since}")
    print(f"Rows: {len(unique_rows)} total, {len(filtered)} after filter\n")

    if args.metric != "all":
        pro = [r for r in filtered if r.collector_host == "pro"]
        air = [r for r in filtered if r.collector_host == "air"]
        print(render_compare(pro, air, args.metric))
    else:
        print(render_table(filtered, show_raw=args.raw))

    return 0


if __name__ == "__main__":
    sys.exit(main())
