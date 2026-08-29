"""
Light API process entrypoint — CRUD, auth, webhooks, admin.

Process group: 'api' (shared-cpu-1x, 1GB RAM)
Routers: light routers (no RAG/ML dependencies)
Startup: <5s (DB + Redis only, skips SearchService + ZantaraAIClient)

Run via: uvicorn backend.app.main_api:app --host 0.0.0.0 --port 8080
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.setup.sentry_config import init_sentry

init_sentry()

logger = logging.getLogger("zantara.backend")


def _wa_outbox_scheduler_enabled() -> bool:
    return os.getenv("WA_OUTBOX_SCHEDULER_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def _wa_outbox_worker_count() -> int:
    """How many concurrent scheduler loops to spawn (P9, spec zantara-wa-spec-v2
    D2.5). K parallelism only ships AFTER the P2-P6 correctness fixes — the
    per-thread advisory lock in wa_outbox_worker.py is what makes >1 worker
    safe (two workers can now claim different rows without ever concurrently
    processing the same thread). Default 2. Any non-integer or non-positive
    value falls back to the default rather than crashing startup.
    """
    raw = os.getenv("WA_OUTBOX_WORKERS", "2")
    try:
        count = int(raw)
    except ValueError:
        logger.warning("WA_OUTBOX_WORKERS=%r is not an int — defaulting to 2", raw)
        return 2
    if count < 1:
        logger.warning("WA_OUTBOX_WORKERS=%d is not positive — defaulting to 2", count)
        return 2
    return count


def _make_wa_bot_generate(app: FastAPI):
    """Build the bot_generate_fn for the wa_outbox scheduler.

    v1.1 (Option B): wires the RAG orchestrator so the Meta-inbox bot actually
    auto-replies. Gated behind the WA_INBOX_BOT_AUTOREPLY flag inside
    generate_bot_reply — when off, it raises and the worker marks the row
    failed/retry (never a wrong send), preserving v1 behaviour by default.

    The pool is bound here via closure because process_outbox_once passes only
    the thread row to bot_generate_fn.
    """
    from backend.services.integrations.wa_inbox_bot import generate_bot_reply

    async def _bot_generate(thread: object) -> str:
        return await generate_bot_reply(app.state.db_pool, thread)

    return _bot_generate


async def _run_wa_outbox_scheduler(app: FastAPI, worker_id: int = 0) -> None:
    """Drain the wa_outbox send-queue by calling process_outbox_once in a loop.

    P9 (spec zantara-wa-spec-v2 D2.5): as of the F1a concurrency pass, up to
    WA_OUTBOX_WORKERS (default 2) instances of this loop run concurrently on
    the 'api' process group — safe because wa_outbox_worker.process_outbox_once
    now holds a per-thread advisory lock across the whole claim→send lifetime
    (P3), so two workers can never process the same thread simultaneously even
    when they claim different rows. `worker_id` is purely for log correlation.
    Tight-loops while draining (status == 'sent'), backs off to
    WA_OUTBOX_POLL_SECONDS when idle. Never crashes the app: per-tick exceptions
    are logged and the loop continues after a backoff.
    """
    from backend.services.integrations.wa_outbox_worker import process_outbox_once
    from backend.services.integrations.whatsapp_service import whatsapp_service

    interval = float(os.getenv("WA_OUTBOX_POLL_SECONDS", "3"))
    pool = app.state.db_pool
    bot_generate_fn = _make_wa_bot_generate(app)
    logger.info("✅ WA outbox scheduler started (worker=%d poll=%ss)", worker_id, interval)
    while True:
        try:
            status = await process_outbox_once(
                pool, whatsapp_service, bot_generate_fn
            )
            # Drain fast while sending, but always yield the loop (sleep(0)
            # would not starve asyncio, but a tiny throttle is safer under a
            # full queue per panel 2026-06-04). Back off fully when idle.
            await asyncio.sleep(0.1 if status == "sent" else interval)
        except asyncio.CancelledError:
            logger.info("🛑 WA outbox scheduler cancelled (worker=%d)", worker_id)
            raise
        except Exception:
            logger.exception("WA outbox scheduler tick failed (worker=%d); backing off", worker_id)
            await asyncio.sleep(interval)


def _garuda_outbox_poll_seconds() -> float:
    """Idle back-off between drain passes. Non-numeric or non-positive values
    fall back to the default rather than crashing startup — the same
    defensiveness `_wa_outbox_worker_count` applies to its own env."""

    raw = os.getenv("GARUDA_OUTBOX_POLL_SECONDS", "5")
    try:
        seconds = float(raw)
    except ValueError:
        logger.warning("GARUDA_OUTBOX_POLL_SECONDS=%r is not a number — defaulting to 5", raw)
        return 5.0
    if seconds <= 0:
        logger.warning("GARUDA_OUTBOX_POLL_SECONDS=%s is not positive — defaulting to 5", seconds)
        return 5.0
    return seconds


#: How often the drain loop asks `count_undrained` whether anything is stuck.
#: Five minutes: often enough that a burned job is seen the same hour it burns,
#: rare enough that it costs one aggregate query per five minutes rather than
#: one per 100ms pass.
_ALARM_PERIOD_SECONDS = 300.0

#: Advisory-lock name for the OP-04 checkout-expiry sweep. Exactly ONE `api`
#: machine runs the drain loop today (measured 2026-08-28: process group `api`
#: has one machine), which is a scaling accident and not a contract — two would
#: select the SAME candidate rows, because that sweep's query has no
#: `FOR UPDATE SKIP LOCKED` the way the drain's claim does.
_OP04_SWEEP_LOCK = "garuda-op04-checkout-expiry-sweep"

#: Hard bound on ONE sweep pass. It runs INLINE in the single drain coroutine,
#: and `reconcile_expired_checkouts` walks up to `limit` (200) rows strictly
#: sequentially, each one an HTTPS round trip to the payment provider on a
#: client built with `timeout=30.0`. Its per-row `except Exception: continue`
#: means a degraded provider does not cut the pass short — it GUARANTEES the
#: worst case instead: 200 x 30s is roughly 100 minutes with `drain_once` not
#: running, so no customer email and no staff money-anomaly page leaves the
#: queue for that whole window. Exactly the "green log, dead queue" shape the
#: alarm-send beside it is bounded against. A cut-off pass loses nothing: each
#: row commits on its own and the next tick re-selects whatever is left.
_OP04_SWEEP_TIMEOUT_SECONDS = 60.0

#: Rows per sweep pass. Passed EXPLICITLY rather than left to
#: `reconcile_expired_checkouts`'s own default, so the backlog warning below
#: compares against the number this call actually used — comparing against a
#: default we merely assume it kept would be an assertion about someone else's
#: code. Its validator accepts 1..1000.
_OP04_SWEEP_LIMIT = 200

#: Hard ceiling on one alarm delivery. `send_telegram_message` makes 3 attempts
#: with 1s/3s backoff against a 30s-timeout client, so left unbounded it can hold
#: the drain for ~94s. Being late with a page is acceptable; stalling customer
#: emails behind it is not.
_ALARM_SEND_TIMEOUT_SECONDS = 20.0


async def _send_outbox_alarm(client: "httpx.AsyncClient", text: str) -> None:  # noqa: F821
    """Best-effort page to the owner chat. NEVER raises.

    DESTINATION, and why it needs no SYMBIOSIS Law 2 derogation.
    `TELEGRAM_OWNER_CHAT_ID` is Zero's own chat — the same destination the five
    `staff_page_*` handlers already use. Nothing here carries applicant data:
    the message names counts and `job_type` strings, never an order id, an
    address or a name. That is not a promise this docstring makes on its own;
    `test_the_page_names_only_counts_and_job_types` pins the shape.

    A missing token or chat id is logged and swallowed. The caller is the drain
    loop, and an unreachable Telegram must never stop customer emails going out.

    The annotation is a STRING because `httpx` is imported inside the scheduler
    rather than at module scope — `test_no_httpx_violators_outside_http_files`
    only sanctions the `async with httpx.AsyncClient(...)` shape outside
    `*_http.py`, and a module-level import here would be a new violation.
    """

    from backend.services.wa_copilot.telegram_notifier import send_telegram_message

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID", "")
    if not token or not chat_id:
        logger.error(
            "GARUDA outbox alarm has something to report and NO WAY TO SEND IT: "
            "TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_CHAT_ID unset. The log line above "
            "is the only record."
        )
        return
    ok, err = await send_telegram_message(client, token, chat_id, text)
    if not ok:
        logger.error("GARUDA outbox alarm could not be delivered: %s", err)


async def _send_quarantine_alarm(client: "httpx.AsyncClient", text: str) -> None:  # noqa: F821
    """Best-effort page for a REFUSED payment callback. NEVER raises.

    DESTINATION, and why it needs no SYMBIOSIS Law 2 derogation. Both env var
    NAMES are read here and never their values from anywhere else — no token
    and no chat id is written in this repository (119 hardcoded fallbacks once
    pointed at a mailbox nobody can open; this is not the 120th).
    `TELEGRAM_OWNER_CHAT_ID` is Zero's own chat, the same destination the five
    `staff_page_*` handlers and the outbox alarm already use. Nothing here
    carries applicant data: the message names counts, the closed
    `quarantine_reason` vocabulary, provider event ids and order ids — never a
    name, email, phone or passport, none of which exist on
    `garuda_payment_inbox` at all. `test_the_quarantine_page_carries_no_pii`
    pins the shape rather than trusting this paragraph.

    A DELIBERATE NEAR-TWIN of `_send_outbox_alarm` rather than a shared helper
    it was refactored into: that function is the live money-page for a
    different queue, and rewriting it inside a PR about the payment inbox
    would put a working alarm at risk for a dozen saved lines. The one thing
    that MUST not drift — the re-alert discipline — is shared for real, by
    importing `REALERT_SECONDS` in `quarantine_alarm.py`.
    """

    from backend.services.wa_copilot.telegram_notifier import send_telegram_message

    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID", "")
    if not token or not chat_id:
        logger.error(
            "GARUDA payment quarantine alarm has something to report and NO WAY "
            "TO SEND IT: TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_CHAT_ID unset. The "
            "log line above is the only record."
        )
        return
    ok, err = await send_telegram_message(client, token, chat_id, text)
    if not ok:
        logger.error("GARUDA payment quarantine alarm could not be delivered: %s", err)


async def _run_garuda_outbox_scheduler(app: FastAPI) -> None:
    """Drain `garuda_order_outbox` by calling `drain_once` in a loop.

    THIS IS THE THING THAT WAS MISSING. `outbox_consumer.py` and
    `outbox_handlers.py` have existed and been tested for a while, and nothing
    in the repository ever called either of them outside tests — measured across
    every `.py`, `.sh`, `.plist`, `.yml` and `.toml`. So `garuda_order_outbox`
    accumulated rows that no code could consume: a customer who paid received no
    confirmation and produced no CRM practice, not because a handler was wrong
    but because the machine was never switched on. `outbox_consumer.py`'s own
    docstring already said as much — "Nothing schedules this module yet ...
    Built is not armed." This is that act.

    ONE WORKER, DELIBERATELY, unlike the WA scheduler's K. That one needs a
    per-thread advisory lock to make parallel loops safe because two rows of the
    same conversation must not be sent out of order. This queue has no such
    ordering constraint: `drain_once` claims one row at a time under
    `FOR UPDATE SKIP LOCKED` and holds the lock across the handler, so
    concurrency is already safe — it is throughput that a second loop would buy,
    and there is no evidence yet that one is needed. `batch_size` is the knob to
    reach for first.

    MULTIPLE MACHINES ARE SAFE FOR THE SAME REASON. If the `api` process ever
    runs on more than one Fly machine, each gets its own copy of this loop.
    That is the same bet the WA scheduler makes and it holds here too:
    `SKIP LOCKED` steps over a row another transaction holds rather than waiting
    on it, so duplicate schedulers contend at the row and never double-dispatch.
    There is deliberately no leader election, because adding one would be a
    second, weaker guarantee layered over a structural one.

    THE HTTP CLIENT IS OWNED HERE, VIA `async with`. `BrevoEmailSender` takes an
    injected `httpx.AsyncClient` precisely so it is not built per call (Golden
    Rule #10), which means somebody has to own and close it. The first draft did
    that with an explicit `try/finally`, which is behaviourally identical and
    still FAILED `test_no_httpx_violators_outside_http_files`: that guard
    recognises `async with httpx.AsyncClient(...)` and a lazy-singleton
    `is_closed` getter, and nothing else outside `*_http.py`. Taking the
    sanctioned shape is better than claiming `# golden-rule-10-exempt` — the
    exemption would have been true and would still have removed this line from
    every future audit of the rule.
    """

    import httpx

    from backend.services.garuda_orders.outbox_alarm import OutboxAlarm
    from backend.services.garuda_orders.outbox_consumer import count_undrained, drain_once
    from backend.services.garuda_orders.outbox_handlers import (
        BrevoEmailSender,
        TelegramStaffPageSender,
        build_handlers,
    )
    from backend.services.garuda_orders.payment_inbox_watch import count_quarantined
    from backend.services.garuda_orders.quarantine_alarm import QuarantineAlarm
    from backend.services.garuda_orders.reconciliation import (
        reconcile_expired_checkouts,
    )

    interval = _garuda_outbox_poll_seconds()
    pool = app.state.db_pool
    logger.info("✅ GARUDA outbox scheduler started (poll=%ss)", interval)
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Same injected client as the email sender (Golden Rule #10) — a
        # Telegram POST is just another HTTPS call, no reason for a second
        # long-lived client here.
        #
        # WRAPPED, because this runs OUTSIDE the per-tick try below and a failure
        # here killed the whole drain in silence (cross-family seat, Kimi K3,
        # 2026-08-28). `build_handlers` lazily imports `settings` and the portal
        # router at call time, so an import drift or a renamed settings
        # attribute raises HERE — after "scheduler started" was already logged,
        # and before the loop whose except could have reported it. Nothing
        # awaits this task until shutdown, where the exception is swallowed by a
        # bare `except (CancelledError, Exception): pass`. Net effect: the entire
        # GARUDA outbox — customer payment emails included — permanently dead
        # behind a green startup log, which is superscar #2 exactly.
        #
        # The task still dies (there is no safe way to drain without handlers),
        # but it dies LOUDLY: one CRITICAL naming the cause, then the re-raise.
        try:
            handlers = build_handlers(
                pool, BrevoEmailSender(client), TelegramStaffPageSender(client)
            )
        except Exception:
            logger.critical(
                "GARUDA outbox scheduler CANNOT START — build_handlers failed; "
                "the queue will accumulate and NOTHING will be dispatched "
                "(customer emails and staff money-anomaly pages both)",
                exc_info=True,
            )
            raise
        # THE PROBE THAT HAD NO CALLER. `count_undrained` was written as "the
        # numbers a probe needs to go red" and, measured 2026-08-28 on main, had
        # ZERO non-test callers — its only two non-test mentions in the whole
        # tree were COMMENTS promising a failure would "be visible in
        # count_undrained". A comment is not a caller (superscar #2, one stage
        # earlier than W120: there the sentinel read a key the reporter never
        # emitted; here the reporter was never asked). This loop is that caller.
        #
        # NOT ON EVERY PASS: the loop cycles every 100ms while work is flowing,
        # and an extra aggregate query at that rate is a self-inflicted load
        # problem. The cadence is wall-clock from a MONOTONIC source, so a system
        # clock adjustment cannot postpone the check indefinitely.
        alarm = OutboxAlarm()
        # THE THIRD WRITE-ONLY STATE IN THIS SUBSYSTEM. `count_undrained` above
        # and `reconcile_expired_checkouts` below were both armed on 2026-08-28
        # in the same tick; `garuda_payment_inbox.outcome = 'quarantined'` was
        # left behind, and measured 2026-08-29 it had five writers in
        # `repository.py` and zero non-test readers in the whole tree. A
        # quarantined row is an authentic provider callback we refused to act
        # on — the router answered 204, the provider will not retry, and until
        # this line nothing told anyone. Armed on the SAME tick as its two
        # siblings, deliberately: one cadence, one place to look.
        quarantine_alarm = QuarantineAlarm()
        next_alarm_check = 0.0
        seen_unroutable: frozenset[str] = frozenset()
        while True:
            try:
                async with pool.acquire() as conn:
                    stats = await drain_once(conn, handlers)

                # `unroutable_types` is PER PASS and the alarm runs far less
                # often, so the UNION since the last check is what it must see.
                # Reading only the latest pass would let a type that appeared
                # once and then had no row left to claim vanish unreported.
                seen_unroutable |= stats.unroutable_types

                now = time.monotonic()
                if now >= next_alarm_check:
                    next_alarm_check = now + _ALARM_PERIOD_SECONDS
                    # EVERY failure in here is swallowed on purpose. This block
                    # is observability; the drain is the product. An alarm that
                    # can kill the queue it watches is worse than no alarm.
                    try:
                        async with pool.acquire() as conn:
                            undrained = await count_undrained(conn)
                        page = alarm.decide(
                            exhausted=undrained.get("exhausted", 0),
                            unroutable_types=seen_unroutable,
                            now=now,
                        )
                        seen_unroutable = frozenset()
                        if page is not None:
                            # The log line goes out FIRST and unconditionally:
                            # it is the record that survives an unreachable
                            # Telegram.
                            logger.error(
                                "GARUDA outbox alarm: %s", page.replace(chr(10), " | ")
                            )
                            # BOUNDED, because `send_telegram_message` retries 3
                            # times with 1s/3s backoff against a client whose
                            # timeout is 30s — a worst case of roughly 94
                            # seconds with the drain stopped behind it. The
                            # alarm may be late; the queue may not be blocked.
                            await asyncio.wait_for(
                                _send_outbox_alarm(client, page),
                                timeout=_ALARM_SEND_TIMEOUT_SECONDS,
                            )
                            # Only NOW does the suppression window start. A page
                            # that never landed must not silence the next hour.
                            alarm.confirm_sent(time.monotonic())
                    except Exception:
                        logger.exception(
                            "GARUDA outbox alarm check failed; the DRAIN is unaffected"
                        )

                    # THIRD JOB THAT HAD NO CALLER, same tick — the payment
                    # inbox's quarantine. Its own try/except for the same
                    # reason as the block above: this is observability, the
                    # drain is the product, and an alarm that can kill the
                    # queue it watches is worse than no alarm. A separate
                    # block, not a shared one, so a failure reading the inbox
                    # cannot also suppress the outbox page.
                    try:
                        async with pool.acquire() as conn:
                            snapshot = await count_quarantined(conn)
                        page = quarantine_alarm.decide(snapshot, now=now)
                        if page is not None:
                            # The log line goes out FIRST and unconditionally:
                            # it is the record that survives an unreachable
                            # Telegram.
                            logger.error(
                                "GARUDA payment quarantine alarm: %s",
                                page.replace(chr(10), " | "),
                            )
                            await asyncio.wait_for(
                                _send_quarantine_alarm(client, page),
                                timeout=_ALARM_SEND_TIMEOUT_SECONDS,
                            )
                            # Only NOW does the suppression window start.
                            quarantine_alarm.confirm_sent(time.monotonic())
                    except Exception:
                        logger.exception(
                            "GARUDA payment quarantine check failed; the DRAIN is unaffected"
                        )

                    # SECOND JOB THAT HAD NO CALLER, same tick. On origin/main
                    # `git grep -l reconcile_expired_checkouts` outside tests
                    # returned exactly ONE path: its own definition. Its
                    # docstring says "Intended cadence: a scheduled job, not a
                    # request-path call" and no scheduler ever existed
                    # (superscar #2 — built is not armed; a docstring naming a
                    # cadence is not a cadence).
                    #
                    # Harmless TODAY only because the order lane answers 503
                    # until GARUDA_XENDIT_SECRET_KEY is set, and a landmine the
                    # moment it is: OP-04 commits ONLY from here, so an order
                    # whose checkout window elapsed would sit in
                    # `awaiting_payment` forever — no expiry mail, no terminal
                    # state, and a customer looking at a dead tracker. Arming it
                    # BEFORE the keys land is the whole point.
                    repository = getattr(app.state, "garuda_order_repository", None)
                    if repository is not None:
                        try:
                            async with pool.acquire() as lock_conn:
                                # Lock and unlock on the SAME connection:
                                # `pg_try_advisory_lock` is SESSION-scoped, so
                                # unlocking from a DIFFERENT pooled connection
                                # silently succeeds while releasing nothing.
                                # CORRECTED (adversarial review): that is a
                                # correctness bug in the unlock, not a permanent
                                # outage — asyncpg's reset query on release
                                # includes `SELECT pg_advisory_unlock_all()`
                                # (verified in asyncpg 0.31.0), so the lock
                                # cannot outlive this connection's next return
                                # to the pool. The explicit unlock is still the
                                # right shape: it frees the lock for the NEXT
                                # tick instead of for whenever the pool happens
                                # to recycle the connection.
                                acquired = await lock_conn.fetchval(
                                    "SELECT pg_try_advisory_lock(hashtext($1)::bigint)",
                                    _OP04_SWEEP_LOCK,
                                )
                                if acquired:
                                    summary = None
                                    try:
                                        summary = await asyncio.wait_for(
                                            reconcile_expired_checkouts(
                                                pool, repository, limit=_OP04_SWEEP_LIMIT
                                            ),
                                            timeout=_OP04_SWEEP_TIMEOUT_SECONDS,
                                        )
                                    except TimeoutError:
                                        # Its OWN line, not the generic handler
                                        # below: "the provider is slow" and "the
                                        # sweep is broken" need different
                                        # answers, and a backlog that times out
                                        # every tick is a standing condition
                                        # rather than an incident.
                                        logger.warning(
                                            "GARUDA OP-04 sweep exceeded %.0fs and was cut off; "
                                            "the drain is free again and the next tick resumes it",
                                            _OP04_SWEEP_TIMEOUT_SECONDS,
                                        )
                                    finally:
                                        await lock_conn.fetchval(
                                            "SELECT pg_advisory_unlock(hashtext($1)::bigint)",
                                            _OP04_SWEEP_LOCK,
                                        )
                                    # Quiet when there is nothing to do: this
                                    # fires every 300s forever, and a line per
                                    # tick would bury the ones that matter.
                                    if summary is not None and summary.candidates:
                                        logger.info(
                                            "GARUDA OP-04 sweep: %d candidate(s), %d expired, "
                                            "%d left for the webhook",
                                            summary.candidates,
                                            summary.expired,
                                            summary.left_for_webhook,
                                        )
                                        if summary.candidates >= _OP04_SWEEP_LIMIT:
                                            # The pass filled its own limit, so
                                            # there is almost certainly more
                                            # behind it. Visible BEFORE a
                                            # customer notices a stale tracker.
                                            logger.warning(
                                                "GARUDA OP-04 sweep hit its %d-row limit — "
                                                "backlog not drained this tick",
                                                _OP04_SWEEP_LIMIT,
                                            )
                        except Exception:
                            # Same rule as the alarm above: this is upkeep, the
                            # drain is the product.
                            logger.exception(
                                "GARUDA OP-04 checkout-expiry sweep failed; the DRAIN is unaffected"
                            )

                # Keep draining while the last pass did real work; back off once
                # it did not. `dispatched` and not `claimed` is the right signal:
                # a pass that only ever claims unroutable or failing rows has
                # nothing to hurry for, and spinning on it would burn their
                # attempt budgets in seconds — the very thing `exclude_ids`
                # exists inside one pass to prevent.
                await asyncio.sleep(0.1 if stats.dispatched else interval)
            except asyncio.CancelledError:
                logger.info("🛑 GARUDA outbox scheduler cancelled")
                raise
            except Exception:
                logger.exception("GARUDA outbox scheduler tick failed; backing off")
                await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan_light(app: FastAPI):
    """
    Light lifespan: initializes DB + Redis only, skips RAG services.
    Background init so Fly.io health checks pass within grace period.
    """
    logger.info("🚀 [API PROCESS] Starting light init (DB + Redis)...")
    app.state.process_mode = "light"

    async def _background_light_init():
        from backend.app.setup.service_initializer import initialize_services_light

        try:
            await initialize_services_light(app)
        except Exception as e:
            logger.error("❌ [API PROCESS] DB init failed (degraded mode): %s", e)
            app.state.db_pool = None
            return

        # Background workers kill switch — see service_initializer.py note (2026-04-12 incident)
        if os.getenv("DISABLE_BACKGROUND_WORKERS") == "1":
            logger.warning(
                "⚠️ DISABLE_BACKGROUND_WORKERS=1 — skipping Notification Scheduler "
                "+ WA outbox scheduler",
            )
            app.state.notification_scheduler = None
            app.state._wa_outbox_scheduler_tasks = []
        else:
            try:
                from backend.app.modules.notifications.scheduler import init_scheduler

                app.state.notification_scheduler = await init_scheduler(app.state.db_pool)
                logger.info("✅ Notification Scheduler initialized")
            except Exception as e:
                logger.warning("⚠️ Notification Scheduler failed: %s", e)

            # WA Meta inbox outbox scheduler — spawned HERE (not in the outer
            # lifespan) because app.state.db_pool is only set above, inside this
            # background init task; an outer-lifespan task could start with
            # db_pool=None (panel race-fix 2026-06-04). Guard on a real pool.
            #
            # P9: WA_OUTBOX_WORKERS (default 2) independent scheduler loops are
            # spawned, all sharing the same pool + bot_generate_fn closure
            # style (each builds its own closure — cheap, avoids any shared
            # mutable state across workers). Stored as a LIST on app.state
            # (was a single task pre-F1a) so shutdown can cancel every one.
            if not _wa_outbox_scheduler_enabled():
                app.state._wa_outbox_scheduler_tasks = []
                logger.warning(
                    "⚠️ WA outbox scheduler disabled by WA_OUTBOX_SCHEDULER_ENABLED",
                )
            elif getattr(app.state, "db_pool", None) is not None:
                worker_count = _wa_outbox_worker_count()
                app.state._wa_outbox_scheduler_tasks = [
                    asyncio.create_task(_run_wa_outbox_scheduler(app, worker_id=i))
                    for i in range(worker_count)
                ]
                logger.info("✅ WA outbox scheduler: %d worker(s) spawned", worker_count)
            else:
                app.state._wa_outbox_scheduler_tasks = []
                logger.warning(
                    "⚠️ WA outbox scheduler NOT started — db_pool unavailable",
                )

            # GARUDA order outbox. Gated by the consumer module's OWN switch
            # rather than a new one: `is_consumer_enabled()` accepts the literal
            # string "true" and nothing else, so an unset variable, a typo, "1",
            # "yes" or "TRUE" all leave this off. That fail-closed default is
            # what makes the queue deployable-but-dark — the code ships, the
            # drain does not start until someone sets the variable on purpose.
            from backend.services.garuda_orders.outbox_consumer import (
                is_consumer_enabled as _garuda_outbox_enabled,
            )

            if not _garuda_outbox_enabled():
                app.state._garuda_outbox_scheduler_task = None
                logger.info(
                    "GARUDA outbox scheduler disarmed "
                    "(GARUDA_OUTBOX_CONSUMER_ENABLED is not the string 'true')",
                )
            elif getattr(app.state, "db_pool", None) is not None:
                app.state._garuda_outbox_scheduler_task = asyncio.create_task(
                    _run_garuda_outbox_scheduler(app)
                )
                logger.info("✅ GARUDA outbox scheduler spawned")
            else:
                app.state._garuda_outbox_scheduler_task = None
                logger.warning(
                    "⚠️ GARUDA outbox scheduler NOT started — db_pool unavailable",
                )

    init_task = asyncio.create_task(_background_light_init())
    app.state._init_task = init_task

    yield

    # Shutdown: cancel every WA outbox scheduler worker BEFORE closing the
    # pool they use (P9 — up to WA_OUTBOX_WORKERS tasks now, was a single task
    # pre-F1a).
    logger.info("🛑 [API PROCESS] Shutting down...")
    wa_tasks = getattr(app.state, "_wa_outbox_scheduler_tasks", None) or []
    for wa_task in wa_tasks:
        wa_task.cancel()
    for wa_task in wa_tasks:
        try:
            await wa_task
        except (asyncio.CancelledError, Exception):
            pass

    # Same order and the same reason: cancel the drain BEFORE the pool it holds
    # a connection from is closed, and await it so its `finally` gets to close
    # the httpx client it owns.
    garuda_task = getattr(app.state, "_garuda_outbox_scheduler_task", None)
    if garuda_task is not None:
        garuda_task.cancel()
        try:
            await garuda_task
        except (asyncio.CancelledError, Exception):
            pass

    db_pool = getattr(app.state, "db_pool", None)
    if db_pool:
        await db_pool.close()
        logger.info("✅ DB pool closed")
    from backend.app.rag_proxy import close_proxy_client

    await close_proxy_client()
    from backend.services.integrations.wa_inbox_bot import close_rag_client

    await close_rag_client()


def create_api_app() -> FastAPI:
    from fastapi import HTTPException
    from fastapi.responses import ORJSONResponse
    from starlette.exceptions import HTTPException as StarletteHTTPException

    from backend.app.core.config import settings
    from backend.app.setup.exception_handlers import (
        general_exception_handler,
        http_exception_handler,
        starlette_http_exception_handler,
    )
    from backend.app.setup.logging_config import configure_logging
    from backend.app.setup.middleware_config import register_middleware
    from backend.app.setup.router_registration import include_light_routers

    configure_logging()

    api = FastAPI(
        title="Zantara API Worker",
        description="Light CRUD/auth/webhook process — no RAG",
        version=getattr(settings, "VERSION", "5.2.0"),
        lifespan=lifespan_light,
        docs_url="/docs"
        if getattr(settings, "ENVIRONMENT", "production") != "production"
        else None,
        redoc_url=None,
        default_response_class=ORJSONResponse,  # 3-10× faster JSON serialization (audit modernization 2026-05-18)
    )

    api.add_exception_handler(HTTPException, http_exception_handler)
    api.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    api.add_exception_handler(Exception, general_exception_handler)

    register_middleware(api)
    include_light_routers(api)

    # GARUDA VOA public router (`garuda_voa_public.py`) validates `result_id`
    # by hand, never as a Pydantic path constraint, so FastAPI's automatic
    # 422-on-any-parameterized-route default documents an outcome that
    # cannot occur on two of its operations. Same pattern as
    # `app_factory.py::create_app()`'s `_openapi_with_visa_decision_conditionals`
    # — chain onto `app.openapi`, never reassign it outright, so a future
    # wrapper here composes instead of clobbering this one.
    from backend.app.routers.garuda_voa_public import strip_unreachable_validation_errors

    default_openapi = api.openapi

    def _openapi_with_garuda_voa_fix() -> dict:
        return strip_unreachable_validation_errors(default_openapi())

    api.openapi = _openapi_with_garuda_voa_fix

    # Proxy router: catches heavy routes and forwards to rag process
    # Must be added LAST (after all light routers)
    from backend.app.rag_proxy import create_proxy_router, is_proxy_enabled

    if is_proxy_enabled():
        api.include_router(create_proxy_router())
        logger.info("✅ RAG proxy router registered (forwarding to rag process)")
    else:
        logger.info("ℹ️ RAG proxy disabled (RAG_PROXY_ENABLED=false)")

    return api


app = create_api_app()
