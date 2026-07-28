"""Run the LLM credit sentinel once. Designed to be invoked inside the prod machine.

    python3 -m backend.services.hardening.llm_credit_sentinel_cli

Exit codes: 0 = credit fine (or state could not be established), 1 = depleted.
The cron reads the exit code, so "unknown" deliberately exits 0 — an
unreachable API is not a billing event and must not page anyone.

It runs inside the Fly machine because that is the only place holding every
credential it needs (Gemini key, WhatsApp token, Telegram token) — the GitHub
Action only needs FLY_API_TOKEN, which it already has.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from backend.services.hardening.llm_credit_sentinel import (
    ALERT_TEXT,
    CreditState,
    LLMCreditSentinel,
)

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr
)
logger = logging.getLogger("llm_credit_sentinel_cli")

# The cron parses `STATE=` / `DETAIL=` off stdout, so those lines need a bare
# format with no level prefix. A dedicated non-propagating logger keeps that
# machine-readable contract while still honouring Golden Rule #8 (no stdout
# builtins in backend code — every line here goes through logging).
_result = logging.getLogger("llm_credit_sentinel.result")
_result.propagate = False
if not _result.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _result.addHandler(_handler)
    _result.setLevel(logging.INFO)

# Surya is the operational owner of this alert (Zero, 2026-07-28).
ALERT_WHATSAPP_ENV = "LLM_CREDIT_ALERT_WHATSAPP"
ALERT_WHATSAPP_FALLBACK_NAME = "Surya"


async def _probe() -> str:
    from backend.llm.genai_client import get_genai_client

    reply = await get_genai_client().generate_content("Reply with exactly: PONG")
    return reply if isinstance(reply, str) else str(reply)[:120]


async def _resolve_alert_number() -> str | None:
    """Prefer an explicit env override; otherwise read Surya's number from HR."""
    explicit = (os.getenv(ALERT_WHATSAPP_ENV) or "").strip()
    if explicit:
        return explicit.lstrip("+")

    dsn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not dsn:
        return None
    import asyncpg

    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchval(
            """
            SELECT whatsapp FROM team_members
             WHERE lower(btrim(name)) = lower($1)
               AND department IS NOT NULL
               AND coalesce(whatsapp, '') <> ''
             LIMIT 1
            """,
            ALERT_WHATSAPP_FALLBACK_NAME,
        )
    finally:
        await conn.close()
    return row.lstrip("+") if row else None


def _build_notifiers(number: str | None) -> dict:
    notifiers: dict = {}

    if number:

        async def whatsapp(text: str) -> bool:
            from backend.services.integrations.whatsapp_service import WhatsAppService

            svc = WhatsAppService()
            try:
                res = await svc.send_message(number, text)
            finally:
                await svc.close()
            # Meta answers 200 with a messages[] array on a real send. Outside the
            # 24h service window it refuses instead — which is expected at night
            # and is exactly why Telegram below is not optional.
            return bool(res and res.get("messages"))

        notifiers["whatsapp:surya"] = whatsapp
    else:
        logger.warning(
            "nessun numero WhatsApp per l'alert (%s vuoto e HR senza numero) — "
            "resta solo Telegram",
            ALERT_WHATSAPP_ENV,
        )

    async def telegram(text: str) -> bool:
        from backend.services.integrations.telegram_bot_service import (
            TelegramBotService,
        )

        chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID")
        if not chat_id:
            return False
        return bool(await TelegramBotService().send_message(chat_id, text))

    notifiers["telegram:owner"] = telegram
    return notifiers


async def main() -> int:
    number = await _resolve_alert_number()
    verdict = await LLMCreditSentinel(_probe, _build_notifiers(number)).check()
    _result.info("STATE=%s", verdict.state.value)
    _result.info("DETAIL=%s", verdict.detail[:200])
    if verdict.state is CreditState.DEPLETED:
        _result.info("ALERT_SENT=1")
        _result.info("%s", ALERT_TEXT.splitlines()[0])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
