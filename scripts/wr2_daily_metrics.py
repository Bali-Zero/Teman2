#!/usr/bin/env python3
"""WR2 pipeline daily metrics digest.

Audit (2026-05-10) found the WR2 pipeline had no observability layer:
nobody knew, on a given day, how many drafts had passed each stage,
how often the canva-apply step needed manual reconciliation, or what
the median skill duration was. This is the foundation.

Output: a single Telegram message to the owner chat per day, summarising
the last 24h of pipeline activity.

Metrics computed (all from war_room_drafts):
- topics → drafts (yesterday): count of drafts created in the window
- drafts → drafts_imaged: count of drafts with images attached
- drafts_imaged → rendered: count of drafts that reached canva-rendered
- rendered → published: count of drafts marked as published
- canva_applied_at deltas: median minutes from updated_at→canva_applied_at
  for the rendered set (proxy for skill duration variability)
- DB consistency check: count of drafts in (drafts_imaged, drafts) that
  have a non-NULL canva_design_id (= reconciliation gap, the failure mode
  observed 2026-05-10 03:48 WITA on draft de69f035)

Designed to run weekday mornings (Mon-Fri 06:00 WITA).

Usage:
    python scripts/wr2_daily_metrics.py
    python scripts/wr2_daily_metrics.py --window-hours 24 --silent
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

import asyncpg

logger = logging.getLogger("wr2.daily_metrics")


def _telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        import urllib.parse
        import urllib.request

        payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        urllib.request.urlopen(  # noqa: S310
            f"https://api.telegram.org/bot{token}/sendMessage",
            payload,
            timeout=10,
        )
    except Exception as e:
        logger.warning("Telegram send failed: %s", e)


async def _gather_metrics(
    conn: asyncpg.Connection, window_hours: int
) -> dict:
    metrics: dict = {"window_hours": window_hours}

    # Drafts created in window, by status.
    rows = await conn.fetch(
        """
        SELECT status, COUNT(*) AS n
          FROM war_room_drafts
         WHERE created_at >= NOW() - ($1 || ' hours')::interval
         GROUP BY status
         ORDER BY n DESC
        """,
        str(window_hours),
    )
    metrics["created_by_status"] = {r["status"]: int(r["n"]) for r in rows}
    metrics["created_total"] = sum(metrics["created_by_status"].values())

    # Skill duration proxy: minutes between updated_at and canva_applied_at
    # for drafts that finished rendering in the window. A high p95 here
    # means the skill is running slow (Claude Desktop throttled, network,
    # template thrash, etc.).
    duration_rows = await conn.fetch(
        """
        SELECT EXTRACT(EPOCH FROM (canva_applied_at - updated_at))/60 AS minutes
          FROM war_room_drafts
         WHERE canva_applied_at IS NOT NULL
           AND canva_applied_at >= NOW() - ($1 || ' hours')::interval
         ORDER BY canva_applied_at DESC
        """,
        str(window_hours),
    )
    durations = sorted(
        float(r["minutes"]) for r in duration_rows if r["minutes"] is not None
    )
    metrics["skill_runs_in_window"] = len(durations)
    if durations:
        n = len(durations)
        metrics["skill_min_min"] = round(durations[0], 1)
        metrics["skill_median_min"] = round(durations[n // 2], 1)
        metrics["skill_max_min"] = round(durations[-1], 1)

    # Reconciliation gap: drafts where Canva has a design_id but the
    # status is still pre-rendered. These need `wr2_canva_reconcile.py`
    # to recover (or were stuck because the script timed out before the
    # DB UPDATE).
    gap_rows = await conn.fetch(
        """
        SELECT id, topic, status, canva_design_id
          FROM war_room_drafts
         WHERE canva_design_id IS NOT NULL
           AND status NOT IN ('rendered', 'published')
        """,
    )
    metrics["reconciliation_gap"] = [
        {
            "id": str(r["id"])[:8],
            "topic": (r["topic"] or "")[:60],
            "status": r["status"],
            "canva_design_id": r["canva_design_id"],
        }
        for r in gap_rows
    ]

    # Currently stuck (no design at all, in a pre-render state, > 24h old).
    stuck_rows = await conn.fetch(
        """
        SELECT id, topic, status, EXTRACT(EPOCH FROM (NOW() - created_at))/3600 AS hours
          FROM war_room_drafts
         WHERE status IN ('drafts_imaged', 'drafts')
           AND canva_edit_url IS NULL
           AND created_at < NOW() - INTERVAL '24 hours'
         ORDER BY created_at ASC
        """,
    )
    metrics["stuck_drafts"] = [
        {
            "id": str(r["id"])[:8],
            "topic": (r["topic"] or "")[:60],
            "status": r["status"],
            "age_hours": round(float(r["hours"]), 1),
        }
        for r in stuck_rows
    ]

    return metrics


def _format_telegram(m: dict) -> str:
    lines = [f"WR2 daily metrics (last {m['window_hours']}h)"]
    lines.append("")
    lines.append(f"Drafts created: {m['created_total']}")
    if m.get("created_by_status"):
        for status, n in sorted(m["created_by_status"].items()):
            lines.append(f"  {status}: {n}")
    lines.append("")
    lines.append(f"Skill runs completed: {m['skill_runs_in_window']}")
    if m.get("skill_runs_in_window"):
        lines.append(
            f"  duration min/median/max: "
            f"{m['skill_min_min']}m / {m['skill_median_min']}m / {m['skill_max_min']}m"
        )
    lines.append("")
    if m["reconciliation_gap"]:
        lines.append(
            f"⚠️ Reconciliation gap ({len(m['reconciliation_gap'])} drafts):"
        )
        for r in m["reconciliation_gap"][:5]:
            lines.append(
                f"  {r['id']} | {r['status']} | design={r['canva_design_id']}"
            )
        lines.append("  Run: python scripts/wr2_canva_reconcile.py")
        lines.append("")
    if m["stuck_drafts"]:
        lines.append(
            f"⚠️ Stuck drafts ({len(m['stuck_drafts'])}, > 24h, no design):"
        )
        for r in m["stuck_drafts"][:5]:
            lines.append(
                f"  {r['id']} | {r['status']} | {r['age_hours']}h | {r['topic']}"
            )
    return "\n".join(lines)


async def run(window_hours: int, silent: bool) -> int:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.critical("DATABASE_URL not set")
        return 2
    conn = await asyncpg.connect(dsn, timeout=10)
    try:
        m = await _gather_metrics(conn, window_hours)
    finally:
        await conn.close()

    print(json.dumps(m, indent=2, default=str))
    if not silent:
        text = _format_telegram(m)
        _telegram(text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-hours", type=int, default=24)
    parser.add_argument(
        "--silent", action="store_true", help="Don't send the Telegram message."
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return asyncio.run(run(args.window_hours, args.silent))


if __name__ == "__main__":
    sys.exit(main())
