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
    * On ABSTAIN → discard the model's answer field and return the localized
      source-honest refusal from the reasoning SSOT. This keeps the channel
      safe without silently abandoning the client. Transport/empty-response
      errors still raise into the worker's retry/backoff guard.
    * The 24h Meta customer-care window is enforced by the worker AFTER us, so
      we do not re-check it here.

Reference spec: docs/superpowers/specs/2026-06-04-wa-outbox-scheduler.md
(§ bot_generate_fn — v1 scope decision, Option B).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any

import asyncpg
import httpx

from backend.app.core.config import settings
from backend.app.rag_proxy import get_rag_worker_url
from backend.channels.format import format_rich_text
from backend.services.integrations.human_escalation_notifier import notify_human_telegram
from backend.services.integrations.wa_bot_outcomes import BotStandingCondition
from backend.services.rag.agentic._reasoning_stubs import get_localized_stub
from backend.services.rag.agentic.query_helpers import detect_query_language

logger = logging.getLogger("zantara.backend")

# ── KG workflow-scaffold strip (client-voice hardening, 2026-07-25) ──────
# `orchestrator_core.py::_format_workflow_for_prompt` appends an internal
# diagnostics block to the RAG answer on some queries — a "## SUGGESTED
# WORKFLOW (from <source>, confidence: NN%)" heading, the workflow name,
# a numbered step list, and an optional "**Confidence**: ..." line — ALWAYS
# closed by the literal trailer sentence below (`_KG_WORKFLOW_TRAILER`,
# copied verbatim from orchestrator_core.py). That block is internal
# diagnostics for an operator reading the raw answer, not a WhatsApp
# client, and has been observed CONTRADICTING the actual answer (e.g. an
# E33G remote-worker answer followed by a local-employment IMTA/TKA
# workflow it never asked for).
#
# We do NOT edit orchestrator_core.py (another lane owns it, and the block
# may be legitimate for other consumers like the web chat UI) — this strip
# lives at the WhatsApp channel boundary instead.
#
# Anchored on the two literal strings the emitter ALWAYS writes together
# (heading prefix + closing sentence, both from the SAME
# `_format_workflow_for_prompt` call) rather than a loose "workflow"
# keyword — see .claude/rules/cicatrix-superscar.md family #3
# (guard-over-match) for why a bare-substring match would be unsafe: a
# legitimate client answer ("il nostro workflow di onboarding...") must
# never be caught by this. The non-greedy DOTALL match between the two
# anchors also means only the block itself is removed, never content that
# happens to follow it (e.g. the KG fast-path's reasoning text, which is
# appended AFTER the workflow block in some code paths and must survive).
_KG_WORKFLOW_TRAILER = (
    "IMPORTANT: This is a suggested workflow. Always verify current requirements with the user."
)
_KG_WORKFLOW_SCAFFOLD_RE = re.compile(
    r"\s*##\s+SUGGESTED WORKFLOW \(from .*?" + re.escape(_KG_WORKFLOW_TRAILER),
    re.DOTALL,
)

# The 2026-08-11 KBLI baseline caught Gemini starting otherwise client-visible
# answers with the prompt's private XML section name (three of 25 probes).
# Do not try to recover a "final" paragraph from such a payload: the leaked
# block has no guaranteed delimiter and any guessed split could still expose
# chain-of-thought or unsupported claims.  At the WhatsApp boundary the safe
# behavior is to discard the entire payload and serve the normal localized
# source-honest refusal.  Anchor at the beginning so a legitimate discussion
# *about* an internal-monologue bug is not caught mid-answer.
_INTERNAL_MONOLOGUE_LEAK_RE = re.compile(
    r"^[^A-Za-z0-9]{0,32}internal[ _-]+monologue"
    r"(?:[ _-]+instructions)?(?:[^A-Za-z0-9]|$)",
    re.IGNORECASE,
)


def _strip_kg_workflow_scaffold(answer: str) -> str:
    """Remove the internal KG-workflow diagnostics block, if present.

    Safe to call on any answer text — a no-op when the block is absent
    (the common case).
    """
    return _KG_WORKFLOW_SCAFFOLD_RE.sub("", answer).strip()


def _safe_abstain_reply(query: str) -> str:
    """Return the reasoning engine's localized, source-honest refusal.

    This is intentionally derived from the customer query, never from the
    endpoint's ``answer`` field: a low-evidence response can still contain
    fluent unsupported claims even when the endpoint correctly labels it
    ``abstain=true``.
    """
    language = detect_query_language(query)
    return get_localized_stub("abstain", language)


def _starts_with_internal_monologue_leak(answer: str) -> bool:
    """Return whether a model payload opens with a private prompt marker."""
    return bool(_INTERNAL_MONOLOGUE_LEAK_RE.match(answer))


async def _tell_a_human(*, phone: str, reason: str, thread_id: Any) -> bool:
    """Tell a human this thread needs them. Never raises.

    Extracted so the SILENT exits can reach it. The notification used to live
    only at the very bottom of ``generate_bot_reply`` — which every ``raise``
    in that function jumps straight over. So the paths that leave the client
    with NOTHING were exactly the paths that told nobody, while every path
    that produced a reply did notify. That is the contract inverted: silence
    is the outcome that most needs a person, and one of those raises sits two
    statements after ``human_reason = "persona_escalate_marker"`` — the client
    asked for a human and the request died with the message.

    Swallows its own failures on purpose: on the silent paths this runs
    immediately before a ``raise``, and a notifier error must not replace the
    real cause with a Telegram stack trace.

    Returns whether Telegram accepted THIS call (see ``notify_human_telegram``).
    ``False`` also covers "suppressed by the 30-minute per-thread dedup", so it
    never means "nobody was ever told about this thread" — which is also why
    the outbox worker's five retries produce one alert, not five.

    **Scope, declared rather than left to be inferred: 3 of the 5 exits that
    raise out of ``generate_bot_reply`` call this.** The three are the
    ``RuntimeError`` ones — "we tried and produced nothing". The two
    ``BotStandingCondition`` exits (feature flag off; no customer message in
    the loaded window) deliberately do NOT, because that exception class
    exists precisely to say "standing condition, not an incident": the
    flag-off branch alone accounts for 44 of the give-ups recorded in
    ``meta_inbox_messages`` (3-19 June, the bot simply switched off), and
    alerting on those is the noise the per-thread dedup exists to prevent.
    If that judgement is ever revisited, revisit it here — do not add a
    fourth call site and leave this paragraph saying three.

    Why this is worth having at all, measured on the live tables rather than
    argued: 40 threads, **32** with at least one bot give-up, and **4** ever
    touched by a human (``handling_version > 0``, max 1) in the whole history.
    The five threads silenced on 2026-07-28 — the team-beta day — carry 34
    give-ups between them and ``handling_version = 0`` on every one. The
    module docstring's "the operator can take over the thread" was never
    honoured on the threads that invoked it.
    """
    try:
        accepted = await notify_human_telegram(
            phone=phone,
            message_text=None,
            reason=reason,
            thread_ref=str(thread_id),
        )
    # Broad on purpose — see docstring: a notifier failure must never replace
    # the real cause the caller is about to raise.
    except Exception as exc:
        logger.error(
            "wa-inbox bot: escalation for thread %s (reason=%s) raised: %s",
            thread_id,
            reason,
            exc,
        )
        return False
    logger.info(
        "wa-inbox bot: thread %s needs a human (reason=%s), telegram accepted=%s",
        thread_id,
        reason,
        accepted,
    )
    return accepted


# Mirrors backend/services/integrations/whatsapp_service.py's `text[:4096]`
# hard cutoff (WhatsApp Cloud API's message-body limit). Duplicated as a
# local constant rather than imported — this module's job ends at "the
# text to send"; the actual truncate+send belongs to whatsapp_service.py
# (another lane's file, out of scope here). Used only to log non-silently
# when a reply is about to be truncated downstream, so the eventual
# chunked-sending work has real data on how often/how badly this happens.
#
# NOT derived from backend/prompts/channel_overlays.py's
# ChannelConfig(name="whatsapp", max_words=150, ...): that number is a
# WORD-count *prompt instruction* to the LLM ("try to keep it short"),
# empirically NOT obeyed (the production evidence behind this PR was
# ~450 words / 2923 chars, generated WITH that overlay active) — which is
# exactly why this fix is deterministic post-processing instead of a
# stronger instruction. Converting a word budget into a char threshold
# here would answer a different question ("is this reply longer than our
# style guideline?") than the one this check needs to answer ("is real
# content about to be physically deleted by whatsapp_service.py's hard
# cutoff?"). Coupling to ChannelConfig.max_words was considered and
# rejected for that reason, not overlooked — see PR description.
_WHATSAPP_HARD_SEND_LIMIT = 4096

# How many prior turns of the thread to feed the orchestrator as context.
_HISTORY_TURNS = 12

# Persistent client (Golden Rule #10 — never per-call). Bounded timeout: the
# agentic RAG path with tool calls can take a while, but the scheduler tick must
# not hang forever — cap at 120s (read) so a stuck RAG cannot wedge the drainer.
_rag_client: httpx.AsyncClient | None = None
_rag_client_lock = asyncio.Lock()

# P9 admission gate (spec zantara-wa-spec-v2 D2.5): bounds how many in-flight
# agentic-RAG calls THIS api process will ever have open against the separate
# 'rag' Fly process group (shared-2x, 2 vCPU) at once. Placed here rather than
# in wa_outbox_worker.py because this module owns the ONE call site that
# actually reaches the RAG process for this feature (main_api.py's K
# scheduler workers all funnel bot generation through generate_bot_reply) —
# K workers stampeding the rag process with more simultaneous calls than it
# can serve would just turn concurrency into RAG-side queueing/timeouts
# instead of outbox-side throughput. Module-level singleton, lazily built (no
# `await` between the None-check and the assignment, so this is safe without
# a lock on a single-threaded event loop — see _get_bot_generation_semaphore).
_bot_generation_semaphore: asyncio.Semaphore | None = None


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


def _get_bot_generation_semaphore() -> asyncio.Semaphore:
    """Lazily build (once) the admission-gate semaphore for RAG calls.

    Max concurrent = int(env WA_BOT_MAX_CONCURRENT_GENERATIONS, default 3).
    Read once, on first use — not re-read per call — matching the existing
    lazy-singleton pattern for ``_rag_client`` in this module. There is no
    `await` between the None-check and the assignment below, so on a
    single-threaded asyncio event loop this cannot race even without a lock
    (two concurrent callers can't interleave between those two lines).
    """
    global _bot_generation_semaphore
    if _bot_generation_semaphore is None:
        try:
            max_concurrent = int(os.getenv("WA_BOT_MAX_CONCURRENT_GENERATIONS", "3"))
        except ValueError:
            max_concurrent = 3
        _bot_generation_semaphore = asyncio.Semaphore(max(1, max_concurrent))
    return _bot_generation_semaphore


def _rag_client_headers() -> dict[str, str]:
    """Service-to-service auth for the api→rag hop.

    ``/api/agentic-rag/query`` is NOT a public endpoint, so HybridAuthMiddleware
    rejects an unauthenticated hop with 401 "Authentication required". Send the
    X-Internal-Key header (settings.wa_mirror_internal_key, Fly secret
    WA_MIRROR_INTERNAL_KEY) — the middleware maps a matching key to a
    "role=internal" pseudo-user, the same channel Pro-side internal scripts use.
    Without this the bot can NEVER generate a reply (every call → 401 → worker
    marks the row failed).

    ALSO sends X-WA-Bot-Profile-Key (settings.wa_inbox_bot_profile_key, Fly
    secret WA_INBOX_BOT_PROFILE_KEY) — a SECOND secret exclusive to this
    process, distinct from X-Internal-Key (which other Pro-side scripts also
    hold). `agentic_rag.py::_verify_wa_inbox_bot_profile_key` gates WA
    sender-profile resolution (owner/team persona override) on THIS key
    specifically, not on the shared internal-key role (P0-ID hardening,
    2026-07-24). Missing → profile resolution simply never fires for this
    bot's calls (fail-safe degrade, not a 401 — the query itself still works).
    """
    headers: dict[str, str] = {}
    internal_key = getattr(settings, "wa_mirror_internal_key", None)
    if internal_key:
        headers["X-Internal-Key"] = internal_key
    else:
        logger.warning(
            "wa-inbox bot: WA_MIRROR_INTERNAL_KEY not configured — "
            "RAG calls will be rejected by HybridAuthMiddleware (401)"
        )
    profile_key = getattr(settings, "wa_inbox_bot_profile_key", None)
    if profile_key:
        headers["X-WA-Bot-Profile-Key"] = profile_key
    else:
        logger.warning(
            "wa-inbox bot: WA_INBOX_BOT_PROFILE_KEY not configured — "
            "owner/team persona override will never resolve for this bot's "
            "queries (query itself still works; degrades to client-shaped "
            "persona only)"
        )
    return headers


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
        BotStandingCondition: the feature flag is off, or the loaded window
            holds no customer message. A ``RuntimeError`` subclass, so the
            worker's retry/backoff policy applies UNCHANGED — the only thing it
            buys is a distinct line in the ledger. (Measured 2026-07-27: 49 of
            the 52 give-ups ever recorded were one of these two, all filed under
            the same sentinel as a genuine crash. See ``wa_bot_outcomes``.)
        RuntimeError: RAG returned an empty transport-level answer. The
            worker's guard turns this into retry/backoff. Semantic abstention
            is returned to the customer as a localized safe reply instead.
        httpx errors propagate (also caught by the worker guard) → retry.
    """
    if not is_bot_autoreply_enabled():
        raise BotStandingCondition("wa-inbox bot auto-reply disabled (WA_INBOX_BOT_AUTOREPLY off)")

    thread_id = thread["thread_id"]
    phone = thread["counterpart_phone"]

    query, history = await _load_thread_context(pool, thread_id)
    if not query:
        raise BotStandingCondition(f"wa-inbox bot: no customer message in thread {thread_id}")

    # Team-assistant V1 (2026-07-19) used to resolve the sender's identity
    # HERE and forward it as a `profile` request field. P0-ID containment
    # (2026-07-24) moved that same `resolve_sender_identity` lookup
    # server-side (`agentic_rag.py::_resolve_trusted_wa_profile`) — the
    # server no longer trusts a client-declared profile at all, so doing
    # the lookup here too would be a redundant DB round-trip on this
    # latency-critical path (research/operations/2026-07-20-wa-bot-latency.md)
    # for a value nobody reads anymore.
    payload: dict[str, Any] = {
        "query": query,
        "user_id": f"whatsapp_{phone}",
        "session_id": f"wa_meta_session_{thread_id}",
        "conversation_history": history,
        "channel": "whatsapp",
        # Latency: cap the ReAct loop at 2 steps (default 3) for this
        # real-time channel — observed 33-94s replies, ~15-17s/step, see
        # research/operations/2026-07-20-wa-bot-latency.md. Never raises the
        # cap. Full win on single-hop queries (the common case); a query
        # needing 2+ tool calls exits the loop before an in-loop synthesis
        # turn and falls to the post-loop context-synthesis path instead
        # (reasoning.py:428-429, :656) — same LLM-call count, a different
        # answer path, worth watching on the abstain/low-context-quality
        # rate post-rollout. Self-correction re-verify (post-loop, not a
        # ReAct step) is untouched — the answer-quality safety net stays.
        "max_steps": 2,
    }

    # P9 admission gate — bound in-flight RAG calls from this api process
    # (see _get_bot_generation_semaphore docstring). Scoped tightly around
    # the actual HTTP round-trip, not the cheap DB context-load above it.
    async with _get_bot_generation_semaphore():
        client = await _get_rag_client()
        resp = await client.post("/api/agentic-rag/query", json=payload)
        resp.raise_for_status()
        data = resp.json()

    # Why a human needs to look at this thread, or None. Set at most once —
    # every later site guards on `is None`, so the FIRST (most specific) cause
    # is the one reported rather than whichever check happens to run last.
    human_reason: str | None = None

    if data.get("abstain"):
        # Never surface the endpoint's raw answer on this branch. The baseline
        # caught an abstain-labelled payload that still asserted Rp 10bn.
        logger.info(
            "wa-inbox bot: serving localized safe abstention for thread %s (reason=%r)",
            thread_id,
            data.get("abstain_reason"),
        )
        answer = _safe_abstain_reply(query)
        human_reason = "rag_abstain"
    else:
        answer = (data.get("answer") or "").strip()
        if not answer:
            # Measured deterministic, not transient: the 2026-08-10 battery got
            # a 0-character answer 5 times out of 5 on the same question, so the
            # retry ladder below cannot rescue this — it only spends attempts
            # and ends in silence. Tell a human BEFORE the raise, because the
            # raise is precisely what makes this silent.
            await _tell_a_human(phone=phone, reason="empty_rag_answer", thread_id=thread_id)
            raise RuntimeError(f"wa-inbox bot: empty RAG answer for thread {thread_id}")

        if _starts_with_internal_monologue_leak(answer):
            logger.warning(
                "wa-inbox bot: internal-monologue marker at start of RAG output "
                "for thread %s; discarding payload and serving safe abstention",
                thread_id,
            )
            answer = _safe_abstain_reply(query)
            if human_reason is None:
                human_reason = "internal_monologue_leak"

        # Strip an [ESCALATE] marker if the persona emitted one (mirror whatsapp_chat.py).
        #
        # Until now this MIRRORED THE FORM AND NOT THE EFFECT: `whatsapp_chat.py`
        # captures the same marker, strips it, sends the answer and then calls
        # `notify_human_telegram`. This module deleted the marker and called
        # nothing — the persona asked for a human and the request was erased in
        # transit. Verified on main before this change: zero telegram/notify
        # references in the whole file.
        if "[ESCALATE]" in answer and human_reason is None:
            human_reason = "persona_escalate_marker"
        answer = answer.replace("[ESCALATE]", "").strip()
        if not answer:
            # `human_reason` is already "persona_escalate_marker" whenever the
            # marker was the whole payload — report THAT (first cause wins,
            # same rule as every other site), never the generic emptiness.
            await _tell_a_human(
                phone=phone,
                reason=human_reason or "empty_after_escalate_strip",
                thread_id=thread_id,
            )
            raise RuntimeError(
                f"wa-inbox bot: answer empty after ESCALATE strip, thread {thread_id}"
            )

        # Remove internal KG-workflow diagnostics before the answer ever reaches
        # the channel formatter — see _strip_kg_workflow_scaffold docstring.
        answer = _strip_kg_workflow_scaffold(answer)
        if not answer:
            logger.info(
                "wa-inbox bot: workflow-only RAG output for thread %s; "
                "serving localized safe abstention",
                thread_id,
            )
            if human_reason is None:
                human_reason = "workflow_only_output"
            answer = _safe_abstain_reply(query)

    # Channel boundary: convert the orchestrator's generic markdown into
    # WhatsApp-safe formatting (*bold*, unicode bullets, no raw ##/**/[N]
    # noise) — see backend/channels/format.py::format_rich_text. Length is
    # tracked pre- AND post-format (not enforced — see
    # _WHATSAPP_HARD_SEND_LIMIT docstring for why 150-word ChannelConfig
    # guidance is the wrong unit for this) so the eventual chunked-sending
    # lane inherits a real length distribution instead of a guess.
    pre_format_len = len(answer)
    answer = format_rich_text(answer, "whatsapp")
    if not answer:
        await _tell_a_human(
            phone=phone,
            reason=human_reason or "empty_after_channel_format",
            thread_id=thread_id,
        )
        raise RuntimeError(
            f"wa-inbox bot: answer empty after channel formatting, thread {thread_id}"
        )
    post_format_len = len(answer)

    if post_format_len > _WHATSAPP_HARD_SEND_LIMIT:
        logger.warning(
            "wa-inbox bot: reply for thread %s is %d chars post-format (%d "
            "pre-format), exceeds WhatsApp's %d-char single-message limit — "
            "whatsapp_service.py will hard-truncate it on send. Chunked "
            "sending is out of scope for this change.",
            thread_id,
            post_format_len,
            pre_format_len,
            _WHATSAPP_HARD_SEND_LIMIT,
        )

    logger.info(
        "wa-inbox bot generated reply for thread %s (%d chars post-format, %d chars pre-format)",
        thread_id,
        post_format_len,
        pre_format_len,
    )

    if human_reason is not None:
        # The REPLY-PRODUCING causes land here; the silent exits above call the
        # same helper before they raise. (An earlier version of this comment
        # said "one call site rather than four" — true then, and the reason the
        # silent paths were never covered: a single bottom-of-function call
        # site cannot be reached by a function that leaves via `raise`.)
        #
        # All causes mean the same thing operationally: the client did not get
        # an answer to what they asked (or explicitly asked for a person). The
        # copy the client reads is deliberately unchanged by this branch, so
        # nothing here can turn into a promise of a reply. Body withheld on
        # purpose (`message_text=None` inside the helper): routing a NEW trigger
        # through the cleartext payload would widen exactly the third-party
        # exposure CLAUDE.md §14 constrains. The thread ref is what makes the
        # omission workable — the notified human can open the thread.
        await _tell_a_human(phone=phone, reason=human_reason, thread_id=thread_id)

    return answer
