#!/usr/bin/env python3
"""CLI dashboard for nb_monitor.

Reads ~/.agent/nb-mitochondrial/metrics.db and prints a table with the
latest snapshot per UUID, plus delta vs the row from ~7 days ago.

Usage:
    python scripts/nb-monitor/show.py
    python scripts/nb-monitor/show.py --db /path/to/metrics.db
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".agent" / "nb-mitochondrial" / "metrics.db"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="nb-monitor-show")
    p.add_argument("--db", default=str(DEFAULT_DB))
    args = p.parse_args(argv)

    db = Path(args.db)
    if not db.exists():
        print(f"metrics.db not found at {db} — has the cron run yet?")
        return 1

    conn = sqlite3.connect(db)
    try:
        latest = conn.execute(
            """
            SELECT uuid, MAX(ts_capture) AS ts, tier, read_freq_7d, read_freq_30d,
                   push_success_rate, source_freshness_age_days, instrumentation_status
              FROM nb_metrics
             GROUP BY uuid
             ORDER BY tier ASC, read_freq_7d DESC
            """
        ).fetchall()

        if not latest:
            print("(no rows yet)")
            return 0

        header = (
            f"{'UUID-PREFIX':12} {'TIER':6} {'rf7':>5} {'rf30':>6} "
            f"{'Δ':>5} {'psr':>5} {'fresh_d':>7}  STATUS"
        )
        print(header)
        print("-" * len(header))
        for uuid, ts, tier, rf7, rf30, psr, fresh, status in latest:
            prev_rf7 = conn.execute(
                """
                SELECT read_freq_7d FROM nb_metrics
                 WHERE uuid=? AND ts_capture <= ?
                 ORDER BY ts_capture DESC LIMIT 1 OFFSET 1
                """,
                (uuid, ts),
            ).fetchone()
            delta = (
                (rf7 - prev_rf7[0])
                if (prev_rf7 and rf7 is not None and prev_rf7[0] is not None)
                else None
            )
            print(
                f"{uuid[:12]:12} {tier:6} "
                f"{_fmt(rf7, 5)} {_fmt(rf30, 6)} {_fmt(delta, 5)} "
                f"{_fmt_rate(psr, 5)} {_fmt(fresh, 7)}  {status or ''}"
            )
    finally:
        conn.close()
    return 0


def _fmt(v, width: int) -> str:
    return f"{v:>{width}d}" if v is not None else f"{'N/A':>{width}}"


def _fmt_rate(v, width: int) -> str:
    return f"{v:>{width}.2f}" if v is not None else f"{'N/A':>{width}}"


if __name__ == "__main__":
    raise SystemExit(main())
