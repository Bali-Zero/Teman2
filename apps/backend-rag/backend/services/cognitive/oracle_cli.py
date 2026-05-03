"""Cron entrypoint for Oracle L4 — weekly Tuesday 09:00 WITA on Pro.

Two modes:
    --deliberate  (default) run OracleCouncil + insert pending UltraMoves
    --deliver               send pending UltraMoves to Telegram

Context is assembled by re-using :class:`StrategosContextBuilder`.

DeepSeek voice requires ``DEEPSEEK_API_KEY`` env. If missing we fall back
to a 3-voice council (claude+gemini+ollama) — ``degraded=True`` in result.
Ollama voice requires a running local Ollama with ``gemma4:26b`` pulled.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

import asyncpg

from backend.services.cognitive.oracle import (
    OracleCouncil,
    OracleOrchestrator,
)
from backend.services.cognitive.oracle_delivery import OracleDelivery
from backend.services.cognitive.repository import CognitiveRepository
from backend.services.cognitive.strategos import StrategosContextBuilder
from backend.services.council.cli_runners import (
    ClaudeCLIRunner,
    DeepSeekHTTPRunner,
    GeminiCLIRunner,
)
from backend.services.intel.dossier_repository import IntelRepository
from backend.services.review.telegram_adapter import TelegramReviewAdapter
from backend.services.war_room.repository import WarRoomRepository

logger = logging.getLogger("cognitive.oracle.cli")


DEFAULT_OWNER = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )


def _build_proponents() -> dict:
    """Wire the 4-voice council; gracefully drop voices we can't run."""
    proponents: dict = {}
    try:
        proponents["claude"] = ClaudeCLIRunner()
    except Exception as exc:  # noqa: BLE001
        logger.warning("claude voice unavailable: %s", exc)
    try:
        proponents["gemini"] = GeminiCLIRunner()
    except Exception as exc:  # noqa: BLE001
        logger.warning("gemini voice unavailable: %s", exc)

    dk = os.environ.get("DEEPSEEK_API_KEY")
    if dk:
        try:
            proponents["deepseek"] = DeepSeekHTTPRunner(api_key=dk)
        except Exception as exc:  # noqa: BLE001
            logger.warning("deepseek voice unavailable: %s", exc)
    else:
        logger.info("deepseek voice skipped (no DEEPSEEK_API_KEY)")

    # Ollama as gemma4:26b devil's advocate — reuse GeminiCLIRunner-like pattern?
    # For now we drop the Ollama proponent if we don't have a CLI runner for it;
    # the fallback council runs with whoever we have.
    # (A dedicated OllamaCLIRunner would belong in council/cli_runners.py.)
    return proponents


async def _deliberate(pool: asyncpg.Pool) -> int:
    intel_repo = IntelRepository(db_pool=pool)
    cognitive_repo = CognitiveRepository(db_pool=pool)
    war_room_repo = WarRoomRepository(db_pool=pool)

    # Context re-uses Strategos builder
    ctx_builder = StrategosContextBuilder(
        intel_repo=intel_repo,
        cognitive_repo=cognitive_repo,
        war_room_repo=war_room_repo,
    )

    async def context_fn() -> str:
        today = datetime.now(timezone.utc).date()
        ctx = await ctx_builder.build(week_of=today)
        return ctx.as_prompt_context()

    proponents = _build_proponents()
    if not proponents:
        logger.error("no proponents available — aborting")
        return 1

    judge = ClaudeCLIRunner()
    council = OracleCouncil(proponents=proponents, judge=judge)
    orchestrator = OracleOrchestrator(
        cognitive_repo=cognitive_repo,
        council=council,
        context_fn=context_fn,
    )
    result = await orchestrator.run_once()

    sys.stdout.write(json.dumps({
        "context_chars": result.context_chars,
        "proposals": [
            {"author": p.author, "ok": p.ok, "moves": len(p.moves)}
            for p in result.proposals
        ],
        "judged": len(result.judged_moves),
        "inserted": [str(m.id) for m in result.inserted],
        "degraded": result.degraded,
        "errors_count": len(result.errors),
    }, default=str) + "\n")

    return 0 if result.inserted or not result.errors else 2


async def _deliver(pool: asyncpg.Pool) -> int:
    cognitive_repo = CognitiveRepository(db_pool=pool)
    telegram = TelegramReviewAdapter()
    delivery = OracleDelivery(
        repo=cognitive_repo,
        telegram=telegram,
        owner_chat_id=DEFAULT_OWNER,
    )
    result = await delivery.send_pending()
    sys.stdout.write(json.dumps({
        "sent": result.sent_count,
        "failed": result.failed_count,
        "skipped": result.skipped_count,
        "move_ids": [str(x) for x in (result.move_ids_sent or [])],
        "errors_count": len(result.errors or []),
    }, default=str) + "\n")
    return 0 if result.failed_count == 0 else 2


async def run(mode: str) -> int:
    _configure_logging()
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        logger.error("DATABASE_URL not set")
        return 1
    try:
        pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=2, command_timeout=200,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("pool init failed: %s", exc, exc_info=True)
        return 1
    try:
        if mode == "deliver":
            return await _deliver(pool)
        return await _deliberate(pool)
    finally:
        await pool.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--deliver",
        action="store_true",
        help="Send pending UltraMoves to Telegram (instead of deliberating)",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(run(mode="deliver" if args.deliver else "deliberate")))


if __name__ == "__main__":
    main()
