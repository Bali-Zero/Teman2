"""WA Meta-inbox bot reply generator (Option B — RAG auto-reply).

The wa_outbox scheduler (``main_api.py::_run_wa_outbox_scheduler``) drains the
send-queue and, for rows with ``needs_generation = true``, calls a
``bot_generate_fn(thread) -> str`` to produce the reply text. v1 shipped a
``NotImplementedError`` sentinel (human-send only). This module is the v1.1
follow-up the spec named "Option B": generate the reply via the RAG
orchestrator and return its text.

Architecture (Fly process groups):
    The scheduler runs on the ``api`` process group, which does NOT host the
    RAG orchestrator in-process (that lives on the ``rag`` group). So we reach
    it over Fly's private network via HTTP — the SAME hop the rag_proxy uses
    (``RAG_WORKER_URL`` → ``POST /api/agentic-rag/query``). This is the exact
    path the live WhatsApp webhook channel uses for non-Meta-inbox numbers
    (``whatsapp_chat.py`` → ``orchestrator.process_query``), just over HTTP
    instead of in-process because of the group split.

Safety contract (mirrors the worker's expectations in wa_outbox_worker.py):
    * Feature flag ``WA_INBOX_BOT_AUTOREPLY`` (default OFF) — when off, this
      raises so the worker marks the row failed/retry, NEVER a wrong send. Arm
      it via a Fly secret only when ready.
    * On ABSTAIN or any RAG error → raise. The worker has a retry/backoff guard
      (MAX_ATTEMPTS) and then marks ``failed`` — the operator can take over the
      thread. We NEVER fabricate a reply or send an empty/placeholder body.
    * The 24h Meta customer-care window is enforced by the worker AFTER us, so
      we do not re-check it here.

Reference spec: docs/superpowers/specs/2026-06-04-wa-outbox-scheduler.md
(§ bot_generate_fn — v1 scope decision, Option B).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import asyncpg
import httpx

from backend.app.core.config import settings
from backend.app.rag_proxy import get_rag_worker_url

logger = logging.getLogger("zantara.backend")

# How many prior turns of the thread to feed the orchestrator as context.
_HISTORY_TURNS = 12

# Persistent client (Golden Rule #10 — never per-call). Bounded timeout: the
# agentic RAG path with tool calls can take a while, but the scheduler tick must
# not hang forever — cap at 120s (read) so a stuck RAG cannot wedge the drainer.
_rag_client: httpx.AsyncClient | None = None
_rag_client_lock = asyncio.Lock()


def is_bot_autoreply_enabled() -> bool:
    """True only when the Fly secret WA_INBOX_BOT_AUTOREPLY is truthy.

    Default OFF so deploying this code does not silently start auto-replying.
    Arm with: ``fly secrets set WA_INBOX_BOT_AUTOREPLY=true -a nuzantara-rag``.
    Kill-switch: unset it (or set to false) — takes effect on next restart.
    """
    return os.getenv("WA_INBOX_BOT_AUTOREPLY", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _rag_client_headers() -> dict[str, str]:
    """Service-to-service auth for the api→rag hop.

    ``/api/agentic-rag/query`` is NOT a public endpoint, so HybridAuthMiddleware
    rejects an unauthenticated hop with 401 "Authentication required". Send the
    X-Internal-Key header (settings.wa_mirror_internal_key, Fly secret
    WA_MIRROR_INTERNAL_KEY) — the middleware maps a matching key to a
    "role=internal" pseudo-user, the same channel Pro-side internal scripts use.
    Without this the bot can NEVER generate a reply (every call → 401 → worker
    marks the row failed).
    """
    internal_key = getattr(settings, "wa_mirror_internal_key", None)
    if internal_key:
        return {"X-Internal-Key": internal_key}
    logger.warning(
        "wa-inbox bot: WA_MIRROR_INTERNAL_KEY not configured — "
        "RAG calls will be rejected by HybridAuthMiddleware (401)"
    )
    return {}


async def _get_rag_client() -> httpx.AsyncClient:
    global _rag_client
    headers = _rag_client_headers()
    if _rag_client is None or _rag_client.is_closed:
        async with _rag_client_lock:
            if _rag_client is None or _rag_client.is_closed:
                _rag_client = httpx.AsyncClient(
                    base_url=get_rag_worker_url(),
                    timeout=httpx.Timeout(120.0, connect=10.0),
                    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
                    headers=headers,
                )
    return _rag_client


async def close_rag_client() -> None:
    """Close the persistent client on shutdown (mirror rag_proxy.close_proxy_client)."""
    global _rag_client
    if _rag_client and not _rag_client.is_closed:
        await _rag_client.aclose()
        _rag_client = None


async def _load_thread_context(
    pool: asyncpg.Pool, thread_id: int
) -> tuple[str, list[dict[str, str]]]:
    """Return (latest_customer_text, conversation_history) for a thread.

    History is oldest→newest, mapped to the orchestrator's {role, content}
    shape: customer→user, bot/human→assistant. The latest customer message is
    the query; it is EXCLUDED from history so it is not duplicated.
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT direction, sender_role, body, created_at
            FROM meta_inbox_messages
            WHERE thread_id = $1 AND body IS NOT NULL AND body <> ''
            ORDER BY created_at DESC, id DESC
            LIMIT $2
            """,
            thread_id,
            _HISTORY_TURNS + 1,
        )

    # rows are newest→oldest; find the latest inbound customer message = query.
    latest_query = ""
    query_idx = -1
    for idx, r in enumerate(rows):
        if r["direction"] == "inbound" and r["sender_role"] == "customer":
            latest_query = r["body"]
            query_idx = idx
            break

    # Build history oldest→newest, excluding the query row.
    history: list[dict[str, str]] = []
    for idx in range(len(rows) - 1, -1, -1):
        if idx == query_idx:
            continue
        r = rows[idx]
        role = "user" if r["sender_role"] == "customer" else "assistant"
        history.append({"role": role, "content": r["body"]})

    return latest_query, history


async def generate_bot_reply(pool: asyncpg.Pool, thread: Any) -> str:
    """bot_generate_fn for process_outbox_once — produce the reply text.

    Args:
        pool: asyncpg pool (bound via closure in main_api).
        thread: asyncpg.Record with thread_id, counterpart_phone (the worker
            passes the meta_inbox_threads row).

    Returns:
        The bot reply text to send.

    Raises:
        RuntimeError: feature flag off, no customer message, RAG abstained, or
            RAG returned an empty answer. The worker's guard turns this into a
            retry/backoff and eventually ``failed`` — never a wrong send.
        httpx errors propagate (also caught by the worker guard) → retry.
    """
    if not is_bot_autoreply_enabled():
        raise RuntimeError("wa-inbox bot auto-reply disabled (WA_INBOX_BOT_AUTOREPLY off)")

    thread_id = thread["thread_id"]
    phone = thread["counterpart_phone"]

    query, history = await _load_thread_context(pool, thread_id)
    if not query:
        raise RuntimeError(f"wa-inbox bot: no customer message in thread {thread_id}")

    payload = {
        "query": query,
        "user_id": f"whatsapp_{phone}",
        "session_id": f"wa_meta_session_{thread_id}",
        "conversation_history": history,
        "channel": "whatsapp",
    }

    client = await _get_rag_client()
    resp = await client.post("/api/agentic-rag/query", json=payload)
    resp.raise_for_status()
    data = resp.json()

    if data.get("abstain"):
        # RAG refused — do not guess. Let the worker park it; operator can take over.
        raise RuntimeError(
            f"wa-inbox bot: RAG abstained for thread {thread_id} "
            f"(reason={data.get('abstain_reason')!r})"
        )

    answer = (data.get("answer") or "").strip()
    if not answer:
        raise RuntimeError(f"wa-inbox bot: empty RAG answer for thread {thread_id}")

    # Strip an [ESCALATE] marker if the persona emitted one (mirror whatsapp_chat.py).
    answer = answer.replace("[ESCALATE]", "").strip()
    if not answer:
        raise RuntimeError(f"wa-inbox bot: answer empty after ESCALATE strip, thread {thread_id}")

    logger.info(
        "wa-inbox bot generated reply for thread %s (%d chars)",
        thread_id,
        len(answer),
    )
    return answer
