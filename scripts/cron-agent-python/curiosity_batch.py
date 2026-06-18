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
import sys
from datetime import datetime, timezone

import asyncpg
import httpx

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = "1125336968"  # Zero @zero0101010101010

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


def _html_escape(text: str) -> str:
    """Escape HTML special chars for Telegram HTML parse_mode."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


async def send_telegram_batch(
    findings: list[asyncpg.Record], stats: dict
) -> None:
    """Invia batch Telegram usando HTML parse_mode (piu robusto di MarkdownV2)."""
    if not findings:
        print("No findings to send", flush=True)
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = stats.get("total", "?")
    actionable = stats.get("actionable_cnt", "?")
    last_at = stats.get("last_finding_at")
    last_str = last_at.strftime("%Y-%m-%d") if last_at else "?"

    lines: list[str] = [
        "<b>Curiosita Pilastro 6 — Weekly Digest</b>",
        f"<i>{today}</i> | totale: {total} findings | actionable: {actionable} | ultimo: {last_str}",
        f"\n<b>Top {len(findings)} per information_gain:</b>",
    ]

    for i, f in enumerate(findings, 1):
        emoji = _source_emoji(f["source"])
        gain = f["information_gain"] or 0.0
        actionable_flag = "✅" if f["actionable"] else "—"
        question = _html_escape((f["question"] or "N/A")[:100])
        finding_preview = _html_escape(
            (f["finding"] or "")[:150].replace("\n", " ")
        )

        lines.append(
            f"\n{i}. {emoji} <b>{question}</b>\n"
            f"   gain={gain:.2f} {actionable_flag} | src={f['source']}\n"
            f"   <i>{finding_preview}</i>"
        )

    text = "\n".join(lines)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
            },
        )
        if resp.status_code != 200:
            print(
                f"Telegram error {resp.status_code}: {resp.text[:200]}", flush=True
            )
            resp.raise_for_status()

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
