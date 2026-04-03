"""CELL Weekly Report — ogni domenica alle 08:00 WITA.

Legge cell_pulse_log e cell_alerts degli ultimi 7 giorni,
costruisce un sommario e lo manda su Telegram.
"""
import asyncio
import os
from datetime import datetime, timedelta, timezone

import asyncpg
import httpx

DATABASE_URL = os.environ.get(
    "CELL_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_dev",
)
TELEGRAM_BOT_TOKEN = os.environ.get("CELL_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("CELL_TELEGRAM_CHAT_ID", "1125336968")


async def fetch_stats(conn: asyncpg.Connection) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    # Pulse stats
    pulse_row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE health_status = 'green')  AS green,
            COUNT(*) FILTER (WHERE health_status = 'yellow') AS yellow,
            COUNT(*) FILTER (WHERE health_status = 'red')    AS red,
            ROUND(AVG(response_time_ms))                     AS avg_rt_ms,
            MAX(response_time_ms)                            AS max_rt_ms,
            COUNT(DISTINCT action_taken)
                FILTER (WHERE action_taken IS NOT NULL)      AS unique_actions
        FROM cell_pulse_log
        WHERE created_at > $1
        """,
        cutoff,
    )

    # Actions taken
    action_rows = await conn.fetch(
        """
        SELECT action_taken, COUNT(*) AS cnt
        FROM cell_pulse_log
        WHERE created_at > $1 AND action_taken IS NOT NULL
        GROUP BY action_taken
        ORDER BY cnt DESC
        """,
        cutoff,
    )

    # Alerts
    alert_rows = await conn.fetch(
        """
        SELECT level, action, COUNT(*) AS cnt
        FROM cell_alerts
        WHERE created_at > $1
        GROUP BY level, action
        ORDER BY cnt DESC
        """,
        cutoff,
    )

    # Last pulse
    last_row = await conn.fetchrow(
        "SELECT health_status, response_time_ms, created_at FROM cell_pulse_log ORDER BY created_at DESC LIMIT 1"
    )

    # Pattern memory
    pattern_row = await conn.fetchrow("SELECT COUNT(*) AS cnt FROM cell_patterns")

    return {
        "pulse": dict(pulse_row) if pulse_row else {},
        "actions": [dict(r) for r in action_rows],
        "alerts": [dict(r) for r in alert_rows],
        "last": dict(last_row) if last_row else {},
        "patterns": pattern_row["cnt"] if pattern_row else 0,
    }


def build_message(stats: dict) -> str:
    p = stats["pulse"]
    total = p.get("total", 0)
    green = p.get("green", 0)
    yellow = p.get("yellow", 0)
    red = p.get("red", 0)
    avg_rt = p.get("avg_rt_ms") or 0
    max_rt = p.get("max_rt_ms") or 0

    uptime_pct = round(green / total * 100, 1) if total > 0 else 0

    # Health bar (20 chars)
    bar_len = 20
    g_chars = round(green / total * bar_len) if total > 0 else 0
    y_chars = round(yellow / total * bar_len) if total > 0 else 0
    r_chars = bar_len - g_chars - y_chars
    health_bar = "🟢" * g_chars + "🟡" * y_chars + "🔴" * r_chars

    lines = [
        "🧬 *CELL — Rapporto Settimanale*",
        f"📅 Settimana: {(datetime.now() - timedelta(days=7)).strftime('%d/%m')} → {datetime.now().strftime('%d/%m/%Y')}",
        "",
        "📊 *Salute Backend*",
        f"{health_bar}",
        f"Uptime: *{uptime_pct}%* ({green}/{total} pulse GREEN)",
        f"Yellow: {yellow} | Red: {red}",
        f"Latenza media: {avg_rt}ms | picco: {max_rt}ms",
        "",
    ]

    # Actions
    if stats["actions"]:
        lines.append("⚡ *Azioni Eseguite*")
        for a in stats["actions"]:
            lines.append(f"  • `{a['action_taken']}` × {a['cnt']}")
        lines.append("")
    else:
        lines.append("⚡ *Azioni Eseguite*: nessuna (tutto GREEN)")
        lines.append("")

    # Alerts
    if stats["alerts"]:
        lines.append("🚨 *Alert*")
        for a in stats["alerts"]:
            lines.append(f"  • [{a['level'].upper()}] `{a['action']}` × {a['cnt']}")
        lines.append("")

    # Memory
    lines.append(f"🧠 *Pattern in memoria*: {stats['patterns']}")

    # Last pulse
    last = stats["last"]
    if last:
        ts = last["created_at"]
        if hasattr(ts, "strftime"):
            ts_str = ts.strftime("%d/%m %H:%M UTC")
        else:
            ts_str = str(ts)
        status_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(
            last["health_status"], "⚪"
        )
        lines.append(f"🕐 *Ultimo pulse*: {status_emoji} {last['health_status'].upper()} @ {ts_str} ({last['response_time_ms']}ms)")

    return "\n".join(lines)


async def send_telegram(message: str) -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("No TELEGRAM_BOT_TOKEN — printing to stdout:\n")
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
            },
        )
        resp.raise_for_status()
        print(f"✅ Telegram message sent (status {resp.status_code})")


async def main() -> None:
    print(f"[{datetime.now().isoformat()}] CELL weekly report starting...")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        stats = await fetch_stats(conn)
        message = build_message(stats)
        await send_telegram(message)
        print("Done.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
