"""WA outbox worker's codex broker leg (BOT-V4 S2 PR-5).

Route decision + offer + wait + consume + finalize for ONE claimed
``wa_outbox`` row (spec
research/operations/2026-08-19-bot-chatgpt-provider-broker-spec.md, section
2.1). The leg runs INSIDE the worker's claim, before the Gemini generation
call. ``attempt`` NEVER raises; it answers in exactly one of four shapes:

  text        — a consumed, finalized completion: the worker sends it.
  stand_down  — drift verdict: the leg has ALREADY terminalized the row
                atomically; the worker generates nothing.
  fall-off    — a CERTAIN pre-durable outcome (gates, load, build, offer
                admission refusals, typed FAILED/DEADLINE waits, consume
                lost, finalize DEFECT): the Gemini leg answers in the SAME
                claim, consuming zero retry attempts.
  fail        — an UNCERTAIN outcome at or after a durable boundary
                (``offer_uncertain`` / ``offer_contract_break`` /
                ``wait_error`` / ``post_completion`` /
                ``stand_down_fence_lost``): the worker raises into its
                retry ladder — generating in THIS claim could run Gemini
                beside a durable job or a completion whose drift was
                never ruled out. The retry re-claims with a fresh thread
                read; a durable offer answers it ``ALREADY_SPENT`` and the
                Gemini leg answers from CURRENT context.

The codex leg runs IFF all of (spec 2.1 route decision):
  1. ``is_bot_autoreply_enabled()`` — the SAME ``WA_INBOX_BOT_AUTOREPLY``
     kill switch the Gemini leg honors as its first statement. The leg
     steps aside when it is off so ``generate_bot_reply`` raises its
     ``BotStandingCondition`` exactly as today — the switch keeps ONE
     owner and the codex route cannot out-live it.
  2. ``WA_GENERATION_PROVIDER == "codex"`` — env, read live per claim;
     absent -> Gemini. S2 ships dark.
  3. The 24h customer-care window has >= 2 x T_exec of margin left — a row
     about to lose its send window never waits on a broker round-trip.
  4. The context package builds (``POST /api/wa-package/build``, the RAG
     process owns the retriever); unbuildable -> Gemini.
  5. ``offer_job`` returns OFFERED (a fresh job) or REATTACHED (a prior
     leg for this row is still alive) — admission lock, gauge liveness,
     breaker, depth and the wa_outbox fence are all checked inside the
     offer transaction; every other outcome -> Gemini, including the
     NAMED ``legs_exhausted`` (this row already spent its whole codex
     retry budget — spec gradino 2/5).

A consumed completion is NEVER returned raw: it runs through
``finalize_wa_answer(provider="codex")`` — the SHARED post-generation
pipeline both legs use (abstain policy from the FROZEN evidence, monologue
leak, scaffold strip, channel formatting, size cap, pricing veto against
the frozen package's price sources, secret-egress scan). A text DEFECT
falls off to the Gemini leg, which regenerates and re-enters the same
pipeline (spec 2.3 TEXT_DEFECT).

Connection discipline: this module NEVER touches the worker's claim
connection — every DB statement runs on a connection acquired from the
pool. The worker's lease heartbeat runs concurrently on the claim
connection for the whole duration of this leg, and asyncpg allows exactly
one operation in flight per connection: sharing it would make the
heartbeat and the leg race into ``InterfaceError``. The offer fence needs
no shared session state — it is a row-level CAS on ``claim_token`` +
status, visible from any connection.

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
from backend.services.integrations.wa_finalize import (
    FinalizeOutcome,
    finalize_wa_answer,
)

# Same-package deliberate reuse of the bot leg's lazy-singleton RAG client,
# thread-context loader, notifier and kill switch: ONE persistent HTTP
# client per process (Golden Rule #10) serving both legs, the codex leg
# answers from the SAME query/history the Gemini leg would see (two loaders
# would drift — W114), the human-notification wiring stays in the one
# module whose tests patch it, and the autoreply switch keeps ONE owner.
from backend.services.integrations.wa_inbox_bot import (
    _get_rag_client,
    _load_thread_context,
    _tell_a_human,
    is_bot_autoreply_enabled,
)
from backend.services.rag.agentic.wa_dlp import restore_text

logger = logging.getLogger(__name__)

CUSTOMER_WINDOW_HOURS = 24


class _StandDownFenceLost(Exception):
    """The atomic stand-down abort found the claim fence gone — another
    worker owns the row now. Raised inside the abort transaction so the
    discard rolls back with it: the new owner's own leg re-runs the drift
    protocol against the still-pending completion."""

# The package build is a route decision (embedding + Qdrant, target well
# under T_exec) — never borrow the RAG client's 120s chat timeout for it.
_BUILD_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


def _canary_tokens() -> tuple[str, ...]:
    """Canary values for the egress scan (spec 4.3), from the env.

    The daemon-side provisioning (`scripts/provision_zantara_codex.sh`)
    plants canary FILES in the `zantara-codex` sandbox precisely to be leak
    tripwires; the SAME values are set here (Fly secret
    ``WA_CODEX_CANARY_TOKENS``, comma-separated) so `finalize_wa_answer`
    can veto any answer that carries one. Unset/empty = no canary half —
    the pattern half of the secret scan stays armed regardless
    (`secret_scan=True` below is unconditional). Read per-call, not at
    import: a rotated Fly secret must take effect on restart without a
    code change, and tests can drive both states without reload tricks.
    """
    raw = os.getenv("WA_CODEX_CANARY_TOKENS", "")
    return tuple(token for token in (part.strip() for part in raw.split(",")) if token)


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
    """Exactly one of four shapes: text (send it), stand_down (abort the
    row, do NOT generate), fail (worker raises -> retry ladder, nothing
    may be generated in THIS claim), or none of those (fall off to the
    Gemini leg in the same claim)."""

    text: str | None = None
    stand_down: bool = False
    fail: str = ""
    reason: str = ""


async def attempt(
    pool: asyncpg.Pool,
    *,
    outbox_id: int,
    thread_id: int,
    message_id: int,
    claim_token: uuid.UUID,
    outbox_expected_status: str,
    thread: Any,
) -> CodexLegResult:
    """Run the codex leg for one claimed row.

    Never raises — except cancellation (``BaseException``), which must
    propagate: swallowing it would break asyncio shutdown semantics, and
    every acquire in this module is a real async-with, so a cancelled leg
    leaks no connection.
    """
    try:
        return await _attempt(
            pool,
            outbox_id=outbox_id,
            thread_id=thread_id,
            message_id=message_id,
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
    *,
    outbox_id: int,
    thread_id: int,
    message_id: int,
    claim_token: uuid.UUID,
    outbox_expected_status: str,
    thread: Any,
) -> CodexLegResult:
    if not is_bot_autoreply_enabled():
        # The Gemini leg raises BotStandingCondition for this as its FIRST
        # statement; the route steps aside so that owner still says so —
        # a provider switch must never out-rank the kill switch.
        return CodexLegResult(reason="autoreply_disabled")

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
            # dlp=True (G-P3): the codex leg is the ONLY caller of this
            # endpoint (grep-verified) and is the ONE route that hands
            # customer text to an external generator — the DLP gate applies
            # here and only here, never on the Gemini leg.
            json={"query": query, "history": history, "thread_epoch": epoch, "dlp": True},
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
    # G-P3: local variable of THIS coroutine only — never persisted, never
    # logged, never forwarded past the `restore_text` call below (same
    # invocation of `_attempt` that requested the build, per the ground
    # map's "provably never leaves Fly" verification).
    reversal_map: dict[str, str] = built.get("reversal_map") or {}
    if not wire or not package_hash:
        # A builder that answered 200 without either half of the sealed
        # envelope is a contract break, not a route decision.
        logger.warning(
            "wa_codex_leg: build response missing wire/hash (outbox=%s)",
            outbox_id,
        )
        return CodexLegResult(reason="build_contract_break")

    # ONE representation of the sealed fact (Codex r2 finding 1): every
    # downstream read — the offer row's evidence_inputs, the finalize
    # pipeline's frozen-evidence verdict, the pricing veto's sources —
    # parses from the WIRE, the exact bytes package_hash covers. A
    # response-level copy could diverge from the sealed one and steer the
    # abstain policy with values the hash never covered, which is why the
    # build response no longer carries one. A malformed wire raises here,
    # pre-offer, and falls off via the outer catch.
    parsed_wire = json.loads(wire)
    evidence_inputs = parsed_wire.get("evidence_inputs") or {}

    # The offer boundary is FAIL-CLOSED only where the outcome is
    # genuinely UNCERTAIN (Codex r3, sharpened by r4): the three phases
    # are separated because they carry three different certainties.
    #   entry   — acquiring the connection failed: offer_job never ran,
    #             nothing durable exists -> fall off (certain).
    #   call    — offer_job raised: the job and its generation_route
    #             marker may already be committed -> fail (uncertain; the
    #             retry answers ALREADY_SPENT or offers afresh).
    #   release — the connection release raised AFTER a known result: a
    #             certain non-OFFERED outcome stands (fall off with it);
    #             after OFFERED the durable job makes fail the safe
    #             reading of an unhealthy pool.
    # A REAL async-with does the acquire/release choreography (Codex r5):
    # CancelledError is a BaseException, so a manual __aexit__ call placed
    # outside a finally is SKIPPED by cancellation during offer_job — the
    # connection stays checked out and pool.close() hangs shutdown. The
    # with-protocol releases on every exit path, cancellation included;
    # cancellation itself then PROPAGATES (the one deliberate exception to
    # attempt's never-raises contract — swallowing it would break asyncio
    # semantics). ``entered`` distinguishes an acquire-ENTRY failure
    # (certain: offer_job never ran) from a RELEASE failure (classified
    # against the known offer outcome below).
    offer: wa_broker.OfferResult | None = None
    call_exc: Exception | None = None
    release_exc: Exception | None = None
    body_cancel: BaseException | None = None
    entered = False
    try:
        async with pool.acquire() as offer_conn:
            entered = True
            try:
                offer = await wa_broker.offer_job(
                    offer_conn,
                    outbox_id=outbox_id,
                    thread_id=thread_id,
                    claim_token=claim_token,
                    outbox_expected_status=outbox_expected_status,
                    package=wire,
                    evidence_inputs=json.dumps(evidence_inputs, sort_keys=True),
                    package_hash=package_hash,
                    thread_epoch=epoch,
                )
            except Exception as exc:
                call_exc = exc
            except BaseException as exc:
                # Cancellation (or another BaseException) — remember it
                # BEFORE it enters __aexit__ (Codex r6): if the release
                # then raises a plain Exception, PEP 3134 makes that
                # exception REPLACE the cancellation (burying it in
                # __context__), the outer except-Exception would swallow
                # it into a fail, and the worker would retry instead of
                # stopping. The re-raise below restores it.
                body_cancel = exc
                raise
    except Exception as exc:
        if body_cancel is not None:
            logger.error(
                "wa_codex_leg: connection release failed while cancelling "
                "(outbox=%s): %s",
                outbox_id,
                type(exc).__name__,
            )
            raise body_cancel
        if not entered:
            logger.warning(
                "wa_codex_leg: offer connection acquire failed "
                "(outbox=%s): %s",
                outbox_id,
                type(exc).__name__,
            )
            return CodexLegResult(
                reason=f"offer_acquire_error:{type(exc).__name__}"
            )
        release_exc = exc

    if call_exc is not None or offer is None:
        exc_name = type(call_exc).__name__ if call_exc is not None else "NoResult"
        logger.error(
            "wa_codex_leg: offer outcome uncertain (outbox=%s): %s",
            outbox_id,
            exc_name,
        )
        return CodexLegResult(fail=f"offer_uncertain:{exc_name}")
    # OFFERED (a job was just created — first leg or a fresh retry leg) and
    # REATTACHED (a prior leg for this outbox_id is still alive) both carry
    # a job_id worth waiting on and are handled identically from here.
    # Every other outcome is a certain non-durable fall-off (retry budget
    # gradino 2/5) — including the now-NAMED LEGS_EXHAUSTED, distinct in
    # the log/reason from the generic ALREADY_SPENT race fallback.
    if offer.outcome not in (
        wa_broker.OfferOutcome.OFFERED,
        wa_broker.OfferOutcome.REATTACHED,
    ):
        logger.info(
            "wa_codex_leg: offer fell off (outbox=%s outcome=%s)",
            outbox_id,
            offer.outcome.value,
        )
        return CodexLegResult(reason=f"offer:{offer.outcome.value}")
    if release_exc is not None:
        logger.error(
            "wa_codex_leg: connection release failed after durable offer "
            "(outbox=%s): %s",
            outbox_id,
            type(release_exc).__name__,
        )
        return CodexLegResult(fail=f"offer_uncertain:{type(release_exc).__name__}")
    if offer.job_id is None:
        # OFFERED/REATTACHED without an id is a broken transport contract
        # over a possibly-durable job — falling off would run Gemini
        # beside it with no way to ever wait/consume/discard (Codex r4
        # finding 1).
        logger.error(
            "wa_codex_leg: %s without job_id (outbox=%s)",
            offer.outcome.value,
            outbox_id,
        )
        return CodexLegResult(fail="offer_contract_break:missing_job_id")
    if offer.thread_epoch is None:
        # Same contract-break class as a missing job_id — the post-
        # completion drift check below has nothing safe to fence against.
        logger.error(
            "wa_codex_leg: %s without thread_epoch (outbox=%s job=%s)",
            offer.outcome.value,
            outbox_id,
            offer.job_id,
        )
        return CodexLegResult(fail="offer_contract_break:missing_thread_epoch")
    if offer.outcome is wa_broker.OfferOutcome.REATTACHED:
        logger.info(
            "wa_codex_leg: reattached to a still-alive prior leg "
            "(outbox=%s job=%s)",
            outbox_id,
            offer.job_id,
        )
    # The epoch the SERVING job actually runs under — for a fresh OFFERED
    # this equals the local `epoch` read above, but for REATTACHED it is
    # the PRIOR leg's own frozen thread_epoch, which can predate this
    # claim's own thread read (the prior leg may have been offered by an
    # earlier, since-failed claim). The post-completion drift check below
    # MUST fence against this value, not the local `epoch` — using the
    # wrong one would silently defeat the thread-epoch-drift protocol on
    # a reattach (spec 2.3).
    serving_epoch = offer.thread_epoch

    # From here on an OFFERED job is DURABLE: an untyped failure can no
    # longer be an in-claim fall-off — the daemon may complete the job and
    # the thread may drift while we cannot see it, so generating in this
    # claim would skip the drift protocol entirely (Codex r2 finding 2).
    # The typed non-COMPLETED outcomes below stay fall-offs: their
    # transitions leave no pending completion behind.
    try:
        wait = await wa_broker.wait_for_job(pool, offer.job_id)
    except Exception as exc:
        logger.error(
            "wa_codex_leg: wait failed after durable offer (outbox=%s "
            "job=%s): %s",
            outbox_id,
            offer.job_id,
            type(exc).__name__,
        )
        return CodexLegResult(fail=f"wait_error:{type(exc).__name__}")
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

    # Post-completion section — FAIL-CLOSED. A completion now exists; if
    # the drift verification (or the discard/consume it commands) breaks,
    # this claim may neither serve nor regenerate: classifying such a
    # failure as an ordinary fall-off would let the Gemini leg answer from
    # the pre-drift thread snapshot with the drift check silently skipped.
    # ``fail`` sends the worker down its retry ladder instead — the retry
    # re-claims with a fresh thread read, and the spent offer routes it to
    # Gemini on CURRENT context. The unconsumed completion is reaped by
    # the dead-consumer grace (its ``completed_at`` anchor is guaranteed
    # by migration 274).
    try:
        # Drift check (spec 2.3), BEFORE consuming: a takeover — or a
        # takeover+release, which moves handling_version without leaving
        # human_handling true — during exec means this completion must
        # never be sent AND must never trigger a fresh generation. Fenced
        # against serving_epoch (the epoch the JOB actually ran under),
        # not the local `epoch` — on a REATTACHED leg those two can
        # differ (see serving_epoch's definition above).
        async with pool.acquire() as check_conn:
            fresh = await check_conn.fetchrow(
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
            or int(fresh["handling_version"]) != serving_epoch
        ):
            # Stand-down is ATOMIC (Codex r2 finding 3): the drift verdict
            # terminalizes the outbox row, discards the completion and
            # writes the ledger sentinel in ONE transaction — a crash can
            # no longer lose the verdict between a committed discard and a
            # never-committed abort (where the reclaimer would requeue the
            # row and a retry would regenerate what the verdict forbade).
            # Fence FIRST: if the claim is gone, the raise rolls the whole
            # transaction back and the new owner re-runs the drift
            # protocol against the still-pending completion.
            async with pool.acquire() as abort_conn:
                async with abort_conn.transaction():
                    fenced = await abort_conn.fetchrow(
                        """
                        UPDATE wa_outbox SET status = 'failed'
                        WHERE id = $1 AND claim_token = $2 AND status = $3
                        RETURNING id
                        """,
                        outbox_id,
                        claim_token,
                        outbox_expected_status,
                    )
                    if fenced is None:
                        raise _StandDownFenceLost()
                    await wa_broker.discard_completion(
                        abort_conn, offer.job_id, reason="takeover"
                    )
                    await abort_conn.execute(
                        """
                        UPDATE meta_inbox_messages
                        SET status = 'failed',
                            error = 'aborted_human_takeover_codex_drift'
                        WHERE id = $1
                        """,
                        message_id,
                    )
            logger.info(
                "wa_codex_leg: completion discarded on drift, row aborted "
                "(outbox=%s job=%s)",
                outbox_id,
                offer.job_id,
            )
            return CodexLegResult(stand_down=True, reason="drift")

        async with pool.acquire() as consume_conn:
            text = await wa_broker.consume_result(consume_conn, offer.job_id)
    except _StandDownFenceLost:
        logger.warning(
            "wa_codex_leg: stand-down fence lost (outbox=%s job=%s)",
            outbox_id,
            offer.job_id,
        )
        return CodexLegResult(fail="stand_down_fence_lost")
    except Exception as exc:
        logger.error(
            "wa_codex_leg: post-completion verification failed (outbox=%s "
            "job=%s): %s",
            outbox_id,
            offer.job_id,
            type(exc).__name__,
        )
        return CodexLegResult(fail=f"post_completion:{type(exc).__name__}")

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

    # G-P3 restore: the generator answered against a REDACTED package (its
    # prompt carried `[PII-CATEGORY-N]` placeholders, never the customer's
    # real values), so its completion may echo those same placeholders back
    # — substitute them for the real values HERE, before the shared
    # finalize pipeline and before this ever becomes CodexLegResult.text. A
    # placeholder shape the generator invented (never issued for this
    # package) is stripped, not restored to garbage (wa_dlp.restore_text).
    # No-op when reversal_map is empty (dlp=False build, or a redaction
    # that found nothing to redact).
    text = restore_text(text, reversal_map)

    # Finalize — the SHARED pipeline, provider="codex" (spec 2.3): abstain
    # verdict from the FROZEN evidence, text-defect checks, channel
    # formatting, and the codex-only egress vetoes (pricing against the
    # frozen package's own price sources; secret-egress scan — both
    # MANDATORY, the pipeline refuses a fail-open configuration). Price
    # sources come from the SAME sealed wire the executor answered from
    # (parsed once, above) so the veto can never run against a different
    # retrieval than the answer used. canary_tokens come from the env
    # (PR-6 wiring, spec 4.3): provisioning plants canary files in the
    # zantara-codex sandbox and the same values arrive here as the
    # WA_CODEX_CANARY_TOKENS Fly secret — the pattern half of the scan is
    # armed regardless of whether any canaries are configured.
    price_sources: list[str] = [
        str(chunk.get("text", "")) for chunk in parsed_wire.get("chunks", [])
    ]
    if parsed_wire.get("pricing_block") is not None:
        price_sources.append(
            json.dumps(parsed_wire["pricing_block"], ensure_ascii=False, sort_keys=True)
        )

    phone = str(thread["counterpart_phone"])

    async def _tell(reason: str) -> bool:
        return await _tell_a_human(phone=phone, reason=reason, thread_id=thread_id)

    result = await finalize_wa_answer(
        data={
            "answer": text,
            "abstain": bool(evidence_inputs.get("abstain")),
            "abstain_reason": (
                "frozen_evidence_label" if evidence_inputs.get("abstain") else None
            ),
            "context_length": evidence_inputs.get("context_length"),
            "evidence_score": evidence_inputs.get("evidence_score"),
        },
        query=query,
        thread_id=thread_id,
        tell_a_human=_tell,
        provider="codex",
        price_sources=price_sources,
        secret_scan=True,
        canary_tokens=_canary_tokens(),
    )
    if result.outcome is FinalizeOutcome.DEFECT or not result.text.strip():
        # TEXT_DEFECT (spec 2.3): a different generator can legitimately
        # cure a defective text — fall off so the Gemini leg regenerates
        # and re-enters the same pipeline. The blank-text guard is
        # defensive: SEND promises non-empty text, and a blank slipping
        # through would otherwise cascade into a Gemini generation AFTER
        # a consumed completion.
        logger.info(
            "wa_codex_leg: finalize rejected completion (outbox=%s job=%s "
            "reason=%s)",
            outbox_id,
            offer.job_id,
            result.defect_reason or "blank_send_text",
        )
        return CodexLegResult(
            reason=f"finalize:{result.defect_reason or 'blank_send_text'}"
        )

    return CodexLegResult(text=result.text, reason="completed")
