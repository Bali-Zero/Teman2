#!/usr/bin/env python3
"""
Curiosita Pilastro 6 -- weekly batch
Legge top 10 findings da cell_curiosity_findings (by information_gain DESC)
Invia Telegram batch ad Antonello per review.

Schema reale cell_curiosity_findings:
  id, source, question, method, finding, actionable,
  information_gain, related_goal_id, created_at
NOTE: no 'status' column -- tabella non ha approvazione; il batch e solo informativo.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# DB: DATABASE_URL from env (sourced from ~/.nuzantara-secrets.env by the wrapper).
# DB connection — env-only. The plaintext fallback that used to live
# here (a real backend_rag_v2 password) was a cleartext-secret leak
# (cicatrix #4) and was stripped when this file was promoted into the repo.
DATABASE_URL = os.environ["DATABASE_URL"]

TOP_N = 10


# ---------------------------------------------------------------------------
# DB query
# ---------------------------------------------------------------------------


async def get_top_findings(
    conn: asyncpg.Connection, limit: int = TOP_N
) -> list[asyncpg.Record]:
    """Top findings per information_gain DESC, poi per data recente."""
    return await conn.fetch(
        """
        SELECT id, source, question, method, finding,
               actionable, information_gain, created_at
        FROM cell_curiosity_findings
        ORDER BY information_gain DESC, created_at DESC
        LIMIT $1
        """,
        limit,
    )


async def get_summary_stats(conn: asyncpg.Connection) -> dict:
    """Stats aggregate per il report."""
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN actionable THEN 1 ELSE 0 END) AS actionable_cnt,
            MAX(created_at) AS last_finding_at
        FROM cell_curiosity_findings
        """
    )
    return dict(row) if row else {}


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def _source_emoji(source: str) -> str:
    if source == "pattern_mining":
        return "📊"
    if source == "retrospective_query":
        return "🤔"
    return "🔍"


async def send_telegram_batch(
    findings: list[asyncpg.Record], stats: dict
) -> None:
    """Route via the gateway (scripts/tg_notify.py) — never call the raw
    Telegram HTTP API directly (anti-regrowth lint, cicatrix-superscar #3). tier=digest: this
    file's own docstring already names it — "il batch e solo informativo" — a
    scheduled weekly informational report, never actionable-now.
    """
    if not findings:
        print("No findings to send", flush=True)
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = stats.get("total", "?")
    actionable = stats.get("actionable_cnt", "?")
    last_at = stats.get("last_finding_at")
    last_str = last_at.strftime("%Y-%m-%d") if last_at else "?"

    lines: list[str] = [
        "Curiosita Pilastro 6 — Weekly Digest",
        f"{today} | totale: {total} findings | actionable: {actionable} | ultimo: {last_str}",
        f"\nTop {len(findings)} per information_gain:",
    ]

    for i, f in enumerate(findings, 1):
        emoji = _source_emoji(f["source"])
        gain = f["information_gain"] or 0.0
        actionable_flag = "✅" if f["actionable"] else "—"
        question = (f["question"] or "N/A")[:100]
        finding_preview = (f["finding"] or "")[:150].replace("\n", " ")

        lines.append(
            f"\n{i}. {emoji} {question}\n"
            f"   gain={gain:.2f} {actionable_flag} | src={f['source']}\n"
            f"   {finding_preview}"
        )

    text = "\n".join(lines)

    gateway = Path(__file__).resolve().parent.parent / "tg_notify.py"
    if not gateway.exists():  # HOME-fork copy: fall back to the repo checkout (#1)
        gateway = Path.home() / "nuzantara" / "scripts" / "tg_notify.py"
    proc = subprocess.run(
        [sys.executable, str(gateway), "--tier", "digest", "--source", "curiosity-batch", "--", text],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        print(f"tg_notify gateway error: {(proc.stderr or '')[:200]}", flush=True)
    else:
        print(f"Telegram batch queued via gateway: {len(findings)} findings", flush=True)

    print(f"Telegram batch sent: {len(findings)} findings", flush=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    print(
        f"{datetime.now(timezone.utc).isoformat()} curiosity_batch starting",
        flush=True,
    )

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        stats = await get_summary_stats(conn)
        print(
            f"DB stats: total={stats.get('total')} actionable={stats.get('actionable_cnt')}",
            flush=True,
        )

        if not stats.get("total"):
            print("No findings in DB, skipping Telegram", flush=True)
            return

        findings = await get_top_findings(conn)
        print(f"Fetched {len(findings)} findings for batch", flush=True)

        await send_telegram_batch(findings, stats)
    finally:
        await conn.close()

    print(
        f"{datetime.now(timezone.utc).isoformat()} curiosity_batch done",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
