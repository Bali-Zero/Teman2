"""WA outbox worker's codex broker leg (BOT-V4 S2 PR-5).

Route decision + offer + wait + consume for ONE claimed ``wa_outbox`` row
(spec research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md,
section 2.1). The leg runs INSIDE the worker's claim, before the Gemini
generation call, and every broker outcome that is not a consumed completion
FALLS OFF to the Gemini leg in the same claim — consuming zero retry
attempts. ``attempt`` therefore NEVER raises: any internal failure is a
fall-off, never an exception into the worker's retry ladder.

The codex leg runs IFF all of (spec 2.1 route decision):
  1. ``WA_GENERATION_PROVIDER == "codex"`` — env, read live per claim
     (mirrors ``WA_INBOX_BOT_AUTOREPLY``); absent -> Gemini. S2 ships dark.
  2. The 24h customer-care window has >= 2 x T_exec of margin left — a row
     about to lose its send window never waits on a broker round-trip.
  3. The context package builds (``POST /api/wa-package/build``, the RAG
     process owns the retriever); unbuildable -> Gemini.
  4. ``offer_job`` returns OFFERED — admission lock, gauge liveness,
     breaker, depth and the wa_outbox fence are all checked inside the
     offer transaction; every other outcome -> Gemini.

Breaker discipline — this module records NOTHING into the breaker. Folds
belong to transition owners only (``wait_for_job``'s deadline CAS,
``complete_job``'s accepted branches, the reaper — see
``record_breaker_result``'s docstring): a worker-side fold would double
count a job its owner already folded. This deliberately supersedes the
pre-merge design note "DEFECT -> record_breaker_result(fail)", written
before the transition-owner doctrine landed in PR #4348.

PII discipline: log lines carry outbox/job ids, outcomes and short reasons
only — never query, history or result text.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg
import httpx

from backend.services.integrations import wa_broker

# Same-package deliberate reuse of the bot leg's lazy-singleton RAG client
# and thread-context loader: ONE persistent HTTP client per process (Golden
# Rule #10) serving both legs, and the codex leg answers from the SAME
# query/history the Gemini leg would see — two loaders would drift (W114).
from backend.services.integrations.wa_inbox_bot import (
    _get_rag_client,
    _load_thread_context,
)

logger = logging.getLogger(__name__)

CUSTOMER_WINDOW_HOURS = 24

# The package build is a route decision (embedding + Qdrant, target well
# under T_exec) — never borrow the RAG client's 120s chat timeout for it.
_BUILD_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def provider_is_codex() -> bool:
    """Env-read live on every claim; absent/anything-else -> Gemini leg."""
    return os.getenv("WA_GENERATION_PROVIDER", "").strip().lower() == "codex"


def _window_margin_ok(thread: Any, *, margin_s: float) -> bool:
    """True when the 24h window has at least ``margin_s`` seconds left.

    Local-clock heuristic mirroring the worker's ``_window_open_locally``:
    the authoritative window gate stays the SQL check at send time — this
    only decides whether a broker round-trip is worth starting.
    """
    last = thread["last_customer_at"]
    if last is None:
        return False
    remaining = timedelta(hours=CUSTOMER_WINDOW_HOURS) - (
        datetime.now(timezone.utc) - last
    )
    return remaining.total_seconds() >= margin_s


@dataclass
class CodexLegResult:
    """Exactly one of three shapes: text (send it), stand_down (abort the
    row, do NOT generate), or neither (fall off to the Gemini leg)."""

    text: str | None = None
    stand_down: bool = False
    reason: str = ""


async def attempt(
    pool: asyncpg.Pool,
    conn: asyncpg.Connection,
    *,
    outbox_id: int,
    thread_id: int,
    claim_token: uuid.UUID,
    outbox_expected_status: str,
    thread: Any,
) -> CodexLegResult:
    """Run the codex leg for one claimed row. Never raises."""
    try:
        return await _attempt(
            pool,
            conn,
            outbox_id=outbox_id,
            thread_id=thread_id,
            claim_token=claim_token,
            outbox_expected_status=outbox_expected_status,
            thread=thread,
        )
    except Exception as exc:  # any escape = fall off, never the retry ladder
        logger.warning(
            "wa_codex_leg: internal error, falling off to Gemini "
            "(outbox=%s): %s",
            outbox_id,
            type(exc).__name__,
        )
        return CodexLegResult(reason=f"internal_error:{type(exc).__name__}")


async def _attempt(
    pool: asyncpg.Pool,
    conn: asyncpg.Connection,
    *,
    outbox_id: int,
    thread_id: int,
    claim_token: uuid.UUID,
    outbox_expected_status: str,
    thread: Any,
) -> CodexLegResult:
    margin_s = 2.0 * wa_broker.deadline_seconds()
    if not _window_margin_ok(thread, margin_s=margin_s):
        return CodexLegResult(reason="window_margin")

    query, history = await _load_thread_context(pool, thread_id)
    if not query:
        # The Gemini leg raises BotStandingCondition for this; the ROUTE
        # decision just steps aside and lets it say so.
        return CodexLegResult(reason="no_customer_message")

    epoch = int(thread["handling_version"])

    try:
        client = await _get_rag_client()
        resp = await client.post(
            "/api/wa-package/build",
            json={"query": query, "history": history, "thread_epoch": epoch},
            timeout=_BUILD_TIMEOUT,
        )
        resp.raise_for_status()
        built = resp.json()
    except Exception as exc:
        logger.warning(
            "wa_codex_leg: package build failed (outbox=%s): %s",
            outbox_id,
            type(exc).__name__,
        )
        return CodexLegResult(reason="package_build_error")

    if built.get("unbuildable") is not None:
        return CodexLegResult(reason=f"unbuildable:{built['unbuildable']}")
    wire = built.get("package_wire")
    package_hash = built.get("package_hash")
    if not wire or not package_hash:
        # A builder that answered 200 without either half of the sealed
        # envelope is a contract break, not a route decision.
        logger.warning(
            "wa_codex_leg: build response missing wire/hash (outbox=%s)",
            outbox_id,
        )
        return CodexLegResult(reason="build_contract_break")

    offer = await wa_broker.offer_job(
        conn,
        outbox_id=outbox_id,
        thread_id=thread_id,
        claim_token=claim_token,
        outbox_expected_status=outbox_expected_status,
        package=wire,
        evidence_inputs=json.dumps(
            built.get("evidence_inputs") or {}, sort_keys=True
        ),
        package_hash=package_hash,
        thread_epoch=epoch,
    )
    if offer.outcome is not wa_broker.OfferOutcome.OFFERED or offer.job_id is None:
        logger.info(
            "wa_codex_leg: offer fell off (outbox=%s outcome=%s)",
            outbox_id,
            offer.outcome.value,
        )
        return CodexLegResult(reason=f"offer:{offer.outcome.value}")

    wait = await wa_broker.wait_for_job(pool, offer.job_id)
    if wait.outcome is not wa_broker.WaitOutcome.COMPLETED:
        # FAILED and DEADLINE were folded into the breaker by their
        # transition owners (complete_job / the wait CAS) — no fold here.
        logger.info(
            "wa_codex_leg: wait fell off (outbox=%s job=%s outcome=%s error=%s)",
            outbox_id,
            offer.job_id,
            wait.outcome.value,
            wait.error_class or "-",
        )
        return CodexLegResult(
            reason=f"wait:{wait.outcome.value}:{wait.error_class or ''}"
        )

    # Drift check (spec 2.3), BEFORE consuming: a takeover — or a
    # takeover+release, which moves handling_version without leaving
    # human_handling true — during exec means this completion must never
    # be sent AND must never trigger a fresh generation.
    fresh = await conn.fetchrow(
        """
        SELECT human_handling, handling_version
        FROM meta_inbox_threads
        WHERE thread_id = $1
        """,
        thread_id,
    )
    if (
        fresh is None
        or bool(fresh["human_handling"])
        or int(fresh["handling_version"]) != epoch
    ):
        await wa_broker.discard_completion(conn, offer.job_id, reason="takeover")
        logger.info(
            "wa_codex_leg: completion discarded on drift (outbox=%s job=%s)",
            outbox_id,
            offer.job_id,
        )
        return CodexLegResult(stand_down=True, reason="drift")

    text = await wa_broker.consume_result(conn, offer.job_id)
    if text is None or not text.strip():
        # Lost a race with the reaper's dead-consumer grace (or a defect no
        # owner may fold twice) — the job's fold already happened at its
        # transition. Fall off without a second fold.
        logger.warning(
            "wa_codex_leg: consume lost (outbox=%s job=%s)",
            outbox_id,
            offer.job_id,
        )
        return CodexLegResult(reason="consume_lost")

    return CodexLegResult(text=text, reason="completed")
