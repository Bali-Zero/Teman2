"""One-shot helper — flip SOTA kill-switches ON/OFF in system_settings.

Used by docs/runbooks/sota-loop-90gg-operations.md Step 3 (activation) and
shutdown procedures.

Not a cron entry — invoke manually via the WR2 wrapper so it gets the same
DATABASE_URL resolution + pg-proxy check as the real cron modules:

    /Users/nuzantara/.openclaw/bin/wr2/wr2-cron-wrapper.sh backend.services.sota_loop._seed_killswitch

Edit the KEYS list below to flip specific switches. Default: all 5 SOTA
kill-switches ON (full Loop active).
"""
from __future__ import annotations

import asyncio
import os
import sys

import asyncpg

# Edit this list to change which switches flip and their target value.
# (key, value) — value must be string 'true' or 'false' (scripts compare
# == 'true' exactly, case-sensitive).
KEYS: list[tuple[str, str]] = [
    ("sota_m13_collect_enabled", "true"),   # m13-collect cron (every 6h)
    ("sota_m13_weekly_enabled", "true"),    # m13-weekly cron (Sun 06:00)
    ("sota_m13_monthly_enabled", "true"),   # m13-monthly cron (1st 04:30)
    ("sota_research_enabled", "true"),      # router /api/research/control/research
    ("sota_retrain_enabled", "true"),       # router /api/research/control/retrain
]


async def main() -> int:
    conn = await asyncpg.connect(os.environ["DATABASE_URL"])
    try:
        for k, v in KEYS:
            await conn.execute(
                """
                INSERT INTO system_settings(key, value, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (key) DO UPDATE
                  SET value = EXCLUDED.value,
                      updated_at = EXCLUDED.updated_at
                """,
                k,
                v,
            )
        rows = await conn.fetch(
            """
            SELECT key, value, updated_at
              FROM system_settings
             WHERE key LIKE 'sota_%' OR key LIKE 'wr2_publisher_%'
             ORDER BY key
            """
        )
        # One-shot CLI helper (see `if __name__ == "__main__"` below) —
        # output is meant for the human operator running the wrapper, not
        # for structured logs. Hence print(), suppressed from Golden Rule #8.
        print("=== SOTA kill-switches ===")  # noqa: T201
        for r in rows:
            print(f"  {r['key']:42s} = {r['value']:6s}  ({r['updated_at']})")  # noqa: T201
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
