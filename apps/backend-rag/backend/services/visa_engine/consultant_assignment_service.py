"""Persistence + notification for ``ConsultantAssignmentEvent`` (C3).

Two functions, deliberately asymmetric in failure posture:

- :func:`record_consultant_assignment_request` is the load-bearing write.
  This durable Postgres row (``visa_oracle_consultant_requests``, migration
  281) IS "the CRM receiving a signal" — a failure here must surface as an
  error to the caller (``POST /api/visa-oracle/consultant-assignment``),
  never be swallowed.
- :func:`notify_consultant_assignment_request` is a best-effort amplifier
  on top of that durable write, not a substitute for it. It must never
  raise and must never delay or fail the caller's response — the durable
  row already exists by the time this runs.
"""

from __future__ import annotations

import logging
import os
import uuid

import asyncpg
import httpx

from backend.core.secret_log_redaction import install_telegram_token_redaction
from backend.services.visa_engine.consultant_assignment import ConsultantAssignmentEvent

install_telegram_token_redaction()

logger = logging.getLogger(__name__)

_TELEGRAM_SEND_TIMEOUT_S = 10.0
_DEFAULT_TELEGRAM_OWNER_CHAT_ID = "8847435604"


async def record_consultant_assignment_request(
    event: ConsultantAssignmentEvent,
    db_pool: asyncpg.Pool,
) -> uuid.UUID:
    """Insert the durable C3 event row. Returns the generated row id.

    Column set is exactly the seven frozen wire fields — see migration
    281's own comment for why no eighth (PII-shaped or otherwise) column
    may ever be added here without first breaking the Pydantic contract.
    """

    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO public.visa_oracle_consultant_requests
                (evaluation_id, client_id, requested_at, origin_screen,
                 tier, product_version_id, locale)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id
            """,
            event.evaluation_id,
            event.client_id,
            event.requested_at,
            event.origin_screen.value,
            event.tier.value,
            event.product_version_id,
            event.locale.value,
        )
    request_id = row["id"]
    logger.info(
        "consultant_assignment_request recorded id=%s evaluation_id=%s tier=%s origin_screen=%s",
        request_id,
        event.evaluation_id,
        event.tier.value,
        event.origin_screen.value,
    )
    return request_id


def _telegram_message(event: ConsultantAssignmentEvent, request_id: uuid.UUID) -> str:
    urgency = "URGENT — " if event.tier.value == "T3" else ""
    client_line = f"\nclient_id: {event.client_id}" if event.client_id is not None else ""
    return (
        f"{urgency}Visa Oracle: a visitor asked to talk to a consultant.\n"
        f"request_id: {request_id}\n"
        f"tier: {event.tier.value}\n"
        f"origin_screen: {event.origin_screen.value}\n"
        f"evaluation_id: {event.evaluation_id}"
        f"{client_line}"
    )


async def notify_consultant_assignment_request(
    event: ConsultantAssignmentEvent,
    request_id: uuid.UUID,
) -> None:
    """Best-effort Telegram alert. Never raises. No-ops if unconfigured.

    Async counterpart of ``services/canva_renderer_v2/_telegram.py``'s
    ``send_telegram`` (same env vars, same swallow-everything posture) —
    that helper's transport is synchronous ``urllib.request``, which would
    block the event loop if called from this async router path, so this is
    a from-scratch async equivalent rather than a reuse.
    """

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", _DEFAULT_TELEGRAM_OWNER_CHAT_ID)
    text = _telegram_message(event, request_id)
    try:
        async with httpx.AsyncClient(timeout=_TELEGRAM_SEND_TIMEOUT_S) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                data={"chat_id": chat_id, "text": text},
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning(
            "consultant_assignment_request Telegram notify failed (swallowed) request_id=%s: %s",
            request_id,
            exc,
        )
