"""Sunday 06:00 WITA cron — aggregate week, retrain if needed, Telegram digest.

Invoked by `com.balizero.sota.m13-weekly.plist` through
`scripts/wr2-cron-wrapper.sh backend.services.sota_loop.m13_weekly`.

Outputs:
- research/sota-social-2026-v1/weekly_report_YYYY-MM-DD.md
- research/sota-social-2026-v1/kpi_timeline.csv (append row)
- research/sota-social-2026-v1/retrain_log.jsonl (append if retrained)
- Telegram digest to Zero
"""
from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg

from backend.services.measurer.m13_feedback_loop import M13FeedbackLoop

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("sota.m13.weekly")


def _repo_root() -> Path:
    """Resolve monorepo root — set by wr2-cron-wrapper.sh as NUZANTARA_REPO_ROOT."""
    env = os.environ.get("NUZANTARA_REPO_ROOT")
    if env:
        return Path(env)
    # Fallback: from backend/services/sota_loop/m13_weekly.py go 4 up.
    return Path(__file__).resolve().parents[4]


async def kill_switch_on(conn) -> bool:
    value = await conn.fetchval(
        "SELECT value FROM system_settings WHERE key = 'sota_m13_weekly_enabled'"
    )
    return value == "true"


async def main() -> int:
    repo = _repo_root()
    research = repo / "research" / "sota-social-2026-v1"
    kpi_csv = research / "kpi_timeline.csv"
    retrain_log = research / "retrain_log.jsonl"

    dsn = os.environ["DATABASE_URL"]
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=3)
    try:
        async with pool.acquire() as conn:
            if not await kill_switch_on(conn):
                logger.info("weekly kill switch OFF — exit")
                return 0

        m13 = M13FeedbackLoop(db_pool=pool)

        channels = ["instagram", "linkedin", "tiktok", "threads", "newsletter"]
        pillars = ["lead", "authority", "audience"]
        deltas: dict[str, dict[str, float]] = {}
        for ch in channels:
            deltas[ch] = {}
            for p in pillars:
                deltas[ch][p] = await m13.compute_delta_vs_baseline(
                    channel=ch, pillar=p
                )

        today = datetime.now(timezone.utc).date().isoformat()
        kpi_csv.parent.mkdir(parents=True, exist_ok=True)
        new_file = not kpi_csv.exists()
        with kpi_csv.open("a", newline="") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["date"] + [f"{c}_{p}" for c in channels for p in pillars])
            row = [today] + [deltas[c][p] for c in channels for p in pillars]
            w.writerow(row)

        breaches: list[tuple[str, str, float]] = []
        retrain_needed = False
        for ch, pvals in deltas.items():
            for p, d in pvals.items():
                if m13.is_pillar_threshold_breach(delta=d):
                    breaches.append((ch, p, d))
                if m13.should_trigger_retrain(delta=d):
                    retrain_needed = True

        retrain_result = ""
        if retrain_needed:
            logger.info("retrain triggered")
            result = subprocess.run(
                [
                    "python",
                    str(repo / "scripts" / "sota_consiglio_playbook.py"),
                    "--wave=final",
                ],
                capture_output=True,
                text=True,
                timeout=1800,
                check=False,
            )
            retrain_result = (
                "OK" if result.returncode == 0 else f"FAIL rc={result.returncode}"
            )
            with retrain_log.open("a") as f:
                f.write(
                    json.dumps(
                        {
                            "date": today,
                            "trigger": "weekly",
                            "deltas": deltas,
                            "retrain_result": retrain_result,
                        }
                    )
                    + "\n"
                )

        report_path = research / f"weekly_report_{today}.md"
        md_lines = [
            f"# SOTA Weekly Report — {today}\n",
            "\n## Deltas vs baseline (per channel × pillar)\n",
        ]
        for ch in channels:
            md_lines.append(f"### {ch}")
            for p in pillars:
                d = deltas[ch][p]
                marker = "BREACH" if d < -0.2 else ("WARN" if abs(d) > 0.1 else "OK")
                md_lines.append(f"- [{marker}] {p}: {d:+.1%}")
            md_lines.append("")
        if breaches:
            md_lines.append(f"\n## Threshold breaches ({len(breaches)})\n")
            for ch, p, d in breaches:
                md_lines.append(f"- {ch} / {p}: {d:+.1%}")
        if retrain_needed:
            md_lines.append(f"\n## Retrain\nTriggered. Result: {retrain_result}")
        report_path.write_text("\n".join(md_lines), encoding="utf-8")
        logger.info("wrote %s", report_path)

        _notify_telegram(deltas, breaches, retrain_needed, retrain_result)

        async with pool.acquire() as conn:
            for ch, p, d in breaches:
                await conn.execute(
                    """
                    INSERT INTO system_settings(key, value)
                    VALUES ($1, 'false')
                    ON CONFLICT (key) DO UPDATE SET value='false'
                    """,
                    f"wr2_publisher_enabled_{ch}",
                )
                logger.warning(
                    "auto-toggled publisher OFF for %s (breach on %s: %.1f%%)",
                    ch,
                    p,
                    d * 100,
                )

        return 0
    finally:
        await pool.close()


def _notify_telegram(
    deltas: dict[str, dict[str, float]],
    breaches: list[tuple[str, str, float]],
    retrained: bool,
    retrain_result: str,
) -> None:
    """Send digest as plain text — Markdown nested with emoji + backticks
    triggers HTTP 400 from Telegram (Fase 0 lesson #8)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    import urllib.parse
    import urllib.request

    header = "[SOTA weekly] BREACHES" if breaches else "[SOTA weekly] OK"
    summary = [header, ""]
    for ch, pvals in deltas.items():
        line = f"{ch}: "
        line += " | ".join(f"{p}={d:+.0%}" for p, d in pvals.items())
        summary.append(line)
    if breaches:
        summary.append(f"\nBreaches: {len(breaches)}")
        for ch, p, d in breaches:
            summary.append(f"- {ch} / {p}: {d:+.1%} -> publisher OFF")
    if retrained:
        summary.append(f"\nRetrain: {retrain_result}")
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            urllib.parse.urlencode(
                {"chat_id": chat, "text": "\n".join(summary)}
            ).encode(),
            timeout=10,
        )
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
