"""Cost advisor CLI — weekly report + daily cap alert.

Two entry points, wired via Pro launchd:
- Weekly (Mon 07:00 WITA): full analysis + top-3 recommendations → Telegram.
- Daily  (08:00 WITA):       check last 24h spend vs cap → Telegram alert if over.

Uses Claude OAuth Max (no ANTHROPIC_API_KEY) — see memory
``feedback_claude_oauth_only.md``. Telegram delivery via direct Bot API
(same pattern as ``backend.services.crm.drive_poll_service``).

Usage:
    PYTHONPATH=. python -m backend.scripts.cost_advisor_cli run
    PYTHONPATH=. python -m backend.scripts.cost_advisor_cli --check-daily-cap
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from typing import Any

from backend.llm.claude_oauth_client import complete_async as claude_complete
from backend.services.observability.cost_advisor import CostAdvisor

logger = logging.getLogger(__name__)

DAILY_SPEND_ALERT_THRESHOLD_USD: Decimal = Decimal("20.00")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")


# ---------------------------------------------------------------------------
# Adapter: CostAdvisor wants .complete(system=, messages=), ClaudeOAuth
# exposes complete_async(prompt=). Wrap into a thin shim with the expected
# interface so the advisor stays decoupled from the CLI layer.
# ---------------------------------------------------------------------------


class _ClaudeOAuthJudgeAdapter:
    """Thin sync→async shim exposing `.complete(system, messages)` to CostAdvisor."""

    async def complete(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        user_text = "\n\n".join(m["content"] for m in messages if m.get("role") == "user")
        prompt = f"{system}\n\n---\n\n{user_text}"
        resp = await claude_complete(prompt=prompt, endpoint="cost_advisor")
        return resp.text


# ---------------------------------------------------------------------------
# Telegram delivery
# ---------------------------------------------------------------------------


def send_telegram(*, text: str, chat_id: str = TELEGRAM_CHAT_ID) -> None:
    """Send a Telegram message via direct Bot API. Logs and swallows errors."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        logger.warning(
            "TELEGRAM_BOT_TOKEN not set — skipping Telegram delivery. "
            "Message would have been: %s",
            text[:200],
        )
        return
    try:
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — known URL
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data,
            timeout=15,
        )
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("Telegram delivery failed: %s", exc)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


async def run_weekly_report(pool: Any) -> None:
    """Full weekly analysis → persist recommendations → Telegram report."""
    advisor = CostAdvisor(pg_pool=pool, oauth_client=_ClaudeOAuthJudgeAdapter())

    summaries = await advisor.analyze_last_window(days=7)
    spikes = await advisor.detect_spikes(summaries)
    recs = await advisor.propose_substitutions(top_n=5)
    inserted = await advisor.persist_recommendations(recs)

    total = sum((s.total_cost_usd for s in summaries), Decimal("0"))
    top3 = recs[:3]

    lines: list[str] = [
        f"*Weekly LLM Cost Report*  (last 7d: ${total:.2f})",
        f"Endpoints analysed: *{len(summaries)}*",
        f"Anomalies (spikes): *{len(spikes)}*",
        f"New recommendations inserted: *{inserted}*",
        "",
        "*Top 3 recommendations*",
    ]
    if top3:
        for r in top3:
            lines.append(
                f"• `{r.endpoint}` {r.current_model} → {r.proposed_model} "
                f"(save ~${r.estimated_monthly_saving_usd}/mo, conf={r.confidence}"
                f"{', SPIKE' if r.spike_flag else ''})\n"
                f"  _{r.quality_tradeoff}_",
            )
    else:
        lines.append("_No substitutions proposed this week._")

    send_telegram(text="\n".join(lines))


async def run_daily_cap_check(pool: Any) -> None:
    """Alert Telegram if last-24h spend exceeds DAILY_SPEND_ALERT_THRESHOLD_USD."""
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            """
            SELECT COALESCE(SUM(cost_usd), 0)
            FROM llm_cost_events
            WHERE ts_utc >= NOW() - INTERVAL '1 day'
            """,
        )
    total_dec = Decimal(str(total or 0))
    if total_dec > DAILY_SPEND_ALERT_THRESHOLD_USD:
        send_telegram(
            text=(
                "🚨 *LLM daily cap ALERT*\n"
                f"Last 24h spend: *${total_dec:.2f}*\n"
                f"Cap: ${DAILY_SPEND_ALERT_THRESHOLD_USD}"
            ),
        )
    else:
        logger.info(
            "daily cap ok: $%s (< $%s)",
            total_dec,
            DAILY_SPEND_ALERT_THRESHOLD_USD,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _main(args: argparse.Namespace) -> None:
    from backend.app.core.database import get_db_pool

    pool = await get_db_pool()
    if pool is None:
        logger.error("get_db_pool() returned None — aborting")
        sys.exit(2)
    if args.check_daily_cap:
        await run_daily_cap_check(pool)
    else:
        await run_weekly_report(pool)


def _parse_argv(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-daily-cap",
        action="store_true",
        help="Run the daily cap check instead of the weekly report.",
    )
    # Positional "run" kept for legacy launchd compatibility — ignored otherwise.
    parser.add_argument("mode", nargs="?", default="run")
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(_main(_parse_argv()))
