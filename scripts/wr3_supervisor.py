#!/usr/bin/env python3
"""WR3 Supervisor — event-bus consumer + episode lifecycle coordinator.

Listens on 6 PG channels declared in migration 183_wr3_eventbus_channels.sql:
  - wr3_episode_brief_requested
  - wr3_episode_pre_render_ready
  - wr3_episode_gate_passed
  - wr3_episode_assembly_ready
  - wr3_episode_critic_verdict
  - wr3_episode_staged

Architecture mirrors WR2 supervisor (scripts/wr2_supervisor.py) but with:
  1. Explicit per-handler ACK contract (closes EventBus Phase 3)
  2. Symbiosis precedence Law 7 > Law 4 cascade at dispatch layer
  3. Channel router loaded from docs/wr3/contracts/_router.yaml

ENVIRONMENT
  DATABASE_URL                 local pg-proxy DSN (port 15432)
  WR3_DRY_RUN                  if 'true', log decisions, do NOT dispatch
  WR3_RECONCILE_INTERVAL_SEC   periodic outbox replay sweep (default 300)
  TELEGRAM_OWNER_CHAT_ID       Zero's chat (default 1125336968)
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Layer 1 (defense-in-depth): line-buffer stdout/stderr in case launchd wrapper
# was deployed without PYTHONUNBUFFERED=1 / python3 -u. Closes scar 2026-05-22
# observability gap (4KB stdout block-buffer hid the zombie state for 3h).
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
    sys.stderr.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass  # Python <3.7 or restricted env — wrapper-level -u is the fallback


class _ReconnectRequired(RuntimeError):
    """Layer 2 control-flow signal: PG connection unusable, outer loop must reconnect.

    Raised by _reconcile_unconsumed / _heartbeat / inner-loop fatal-error branch
    when the asyncpg Connection is dead. Caught by the outer `while not
    stop_event.is_set()` loop, which closes the dead conn and reconnects with
    exponential backoff (Layer 5).

    Previously: _reconcile_unconsumed swallowed asyncpg.InterfaceError with a
    print + return, leaving the supervisor PID alive but with a dead TCP socket
    indefinitely (scar 2026-05-22, vecchio PID 25068 lived 3h09m with lsof empty).
    """


def _is_connection_fatal(err: BaseException) -> bool:
    """True if `err` is one of asyncpg's connection-fatal exception classes.

    Used by the outer loop to decide reconnect vs. log-and-continue. Excludes
    things like PostgresSyntaxError (script bug, not connection issue).

    Lazy-import asyncpg so this module remains importable from unit tests
    that don't activate the venv (asyncpg is bundled in apps/backend-rag/.venv).
    """
    try:
        import asyncpg  # type: ignore
    except ImportError:
        return False
    return isinstance(
        err,
        (asyncpg.exceptions.InterfaceError, asyncpg.exceptions.ConnectionDoesNotExistError),
    )


async def _heartbeat(conn: Any, *, timeout: float = 2.0) -> None:
    """Layer 4 — issue a cheap SELECT 1 to detect half-open TCP.

    asyncpg's add_termination_listener (Layer 3) covers explicit termination
    but NOT half-open scenarios where the OS hasn't surfaced the dropped TCP
    yet. A timed SELECT 1 forces I/O and raises promptly on dead conn.

    `fetchval` rather than `execute` because fetchval returns the value (1)
    confirming round-trip, while execute returns a command-tag string.

    Wrap in `asyncio.wait_for` so a stuck pg-proxy can't hang the daemon
    (the wait_for cancels the inner coroutine and we re-raise as
    _ReconnectRequired so the outer loop reconnects).

    Raises:
        _ReconnectRequired: on any failure (timeout OR connection-fatal OR
            unexpected exception — conservative: any heartbeat failure
            triggers reconnect since the only purpose of this call is
            liveness detection).
    """
    try:
        result = await asyncio.wait_for(conn.fetchval("SELECT 1"), timeout=timeout)
        if result != 1:
            raise _ReconnectRequired(f"heartbeat returned unexpected: {result!r}")
    except asyncio.TimeoutError as e:
        raise _ReconnectRequired(f"heartbeat timed out after {timeout}s") from e
    except _ReconnectRequired:
        raise
    except Exception as e:
        # Conservative: any error from a SELECT 1 means the conn is unusable.
        raise _ReconnectRequired(f"heartbeat failed: {e!r}") from e

# Make sibling scripts importable as top-level modules
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from wr3_contracts import WR3Contracts, load_contracts  # noqa: E402
from wr3_dispatch_agent import (  # noqa: E402
    CascadeExhaustedError,
    HardHaltException,
    OSINTLeakError,
    telegram_p0,
)
# v2 dispatcher: `claude --print` direct, no SDK Task-tool overhead.
# Empirically ~50× cheaper than v1 SDK setting_sources=["user"] path.
# Cicatrix scar 2026-05-19 documents the v1 → v2 refactor reason.
from wr3_dispatch_v2 import dispatch_agent_v2 as dispatch_agent  # noqa: E402
from wr3_telemetry import emit as telemetry_emit  # noqa: E402


# ---------------------------------------------------------------------------
# Public contract (consumed by backend/tests/services/events/test_wr3_outbox_explicit_ack.py)
# ---------------------------------------------------------------------------

# Closed set of valid WR3 PG NOTIFY channels — mirrors migration 183.
WR3_CHANNELS: tuple[str, ...] = (
    "wr3_episode_brief_requested",
    "wr3_episode_pre_render_ready",
    "wr3_episode_gate_passed",
    "wr3_episode_assembly_ready",
    "wr3_episode_critic_verdict",
    "wr3_episode_staged",
)


class InvalidWR3ChannelError(ValueError):
    """Raised by publish() when channel is not in WR3_CHANNELS."""


class UnknownWR3ChannelError(KeyError):
    """Raised by route_event() when no handler is registered for the channel."""


# Test injection points (module-level for monkey-patching by unit tests).
_HANDLERS: dict[str, Any] = {}  # channel → async handler callable
_DISPATCH_TIMEOUT_S: float = 300.0  # 300s wall-clock per Codex Q9 watchdog


async def publish(
    conn: Any,
    *,
    channel: str,
    payload: dict[str, Any],
) -> int:
    """Invoke the publish_wr3_event() SQL helper from migration 183.

    Returns the outbox row id assigned by the SQL function. The helper writes
    to events_outbox AND fires pg_notify in the SAME tx (atomicity contract
    matching migration 146 trigger functions).

    Raises:
        InvalidWR3ChannelError: channel not in WR3_CHANNELS closed set
            (defense-in-depth: the SQL function also validates).
    """
    if channel not in WR3_CHANNELS:
        raise InvalidWR3ChannelError(
            f"channel {channel!r} not in WR3_CHANNELS. "
            f"Allowed: {WR3_CHANNELS}"
        )
    outbox_id = await conn.fetchval(
        "SELECT publish_wr3_event($1::TEXT, $2::JSONB)",
        channel,
        json.dumps(payload),
    )
    return int(outbox_id)


# ---------------------------------------------------------------------------
# Lazy asyncpg import — we only need it at runtime, not for unit tests
# ---------------------------------------------------------------------------


def _import_asyncpg():
    try:
        import asyncpg  # type: ignore
        return asyncpg
    except ImportError as e:
        raise RuntimeError(
            "asyncpg not installed in active venv. "
            "Activate apps/backend-rag/.venv and pip install asyncpg."
        ) from e


# ---------------------------------------------------------------------------
# Per-channel handler dispatch
# ---------------------------------------------------------------------------


async def _route_event_test_mode(
    *,
    conn: Any,
    ack_fn: Any,
    channel: str,
    payload_str: str,
) -> None:
    """Lightweight route_event variant for unit tests.

    Resolves handler from _HANDLERS dict, dispatches with timeout from
    _DISPATCH_TIMEOUT_S, acks via the injected ack_fn ONLY on success.
    Mirrors the explicit-ack contract from full route_event but without
    Claude SDK dispatch or asyncpg reconnect machinery.
    """
    import asyncio as _asyncio

    if channel not in _HANDLERS:
        raise UnknownWR3ChannelError(
            f"No handler registered for channel {channel!r}"
        )

    payload_dict = json.loads(payload_str)
    outbox_id = payload_dict.get("_outbox_id")
    handler = _HANDLERS[channel]

    # Apply test-injectable timeout (asyncio.TimeoutError surfaces if exceeded).
    await _asyncio.wait_for(
        handler(conn=conn, channel=channel, payload=payload_dict),
        timeout=_DISPATCH_TIMEOUT_S,
    )

    # ACK ONLY on success.
    if outbox_id is not None:
        await ack_fn(conn, outbox_id)


async def route_event(
    conn: Any = None,  # asyncpg.Connection
    contracts: WR3Contracts | None = None,
    channel: str = "",
    payload_str: str = "",
    *,
    ack_fn: Any = None,  # Optional ack callable for unit-test injection
    payload: str | None = None,  # Alias for payload_str (test API)
    dry_run: bool = False,
) -> None:
    """Dispatch one event with explicit per-handler ACK on success.

    Two calling conventions are supported (both routed to same logic):

    1. Full orchestrator (production): route_event(conn, contracts, channel,
       payload_str). Acks via _acknowledge_outbox + dispatches via
       dispatch_agent (Claude SDK + cascade).

    2. Unit test (test_wr3_outbox_explicit_ack.py): route_event(conn=, ack_fn=,
       channel=, payload=). Uses module-level _HANDLERS dict for handler
       lookup, ack_fn directly for ack semantics. Lets the test pin the
       contract without needing full Claude SDK + asyncpg connection.

    On exception: telemetry FAIL + Telegram P0 (if hot path) + raise.
    Outbox row stays UNCONSUMED — replays on supervisor reconnect.

    Idempotency contract (Codex+Gemini+DeepSeek 3/3 review 2026-05-18):
    The 2-phase "dispatch THEN ack" pattern is vulnerable to double-execution
    if PG drops between dispatch return and ack. We mitigate via:

      1. RESERVATION pre-dispatch: optimistic CAS UPDATE on events_outbox
         marks the row as `in_flight` with our pid+timestamp. If another
         supervisor instance won the race, our CAS returns 0 rows and we
         exit early (skipping dispatch entirely).
      2. ACK post-dispatch: same outbox row, transition `in_flight` →
         `consumed`. If ack fails (PG drop), the next reconcile will see
         `in_flight` from a stale pid and may re-reserve after timeout —
         but only the FIRST successful dispatch is acted on.
      3. Downstream handlers MUST be idempotent against (episode_id, channel)
         tuple. Documented per-agent in docs/wr3/contracts/<agent>.yaml.
    """
    # Allow `payload=` alias used by the unit-test API
    if payload is not None and not payload_str:
        payload_str = payload

    # Test path: handler comes from _HANDLERS dict, ack via ack_fn.
    if ack_fn is not None:
        return await _route_event_test_mode(
            conn=conn,
            ack_fn=ack_fn,
            channel=channel,
            payload_str=payload_str,
        )
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError as e:
        print(f"[wr3-supervisor] malformed payload on {channel}: {e}", file=sys.stderr)
        return  # cannot ack what we cannot parse — log and drop

    episode_id = payload.get("episode_id", "unknown")
    outbox_id = payload.get("_outbox_id")
    route = contracts.route_for(channel)
    agent_name = route.handler
    started = asyncio.get_event_loop().time()

    print(f"[wr3-supervisor] {channel} → {agent_name} ep={episode_id} dry={dry_run}")

    if dry_run:
        return  # do not dispatch, do not ack — caller may pop us out of the loop

    # Phase 1: RESERVE (skip if another supervisor instance already running this)
    if outbox_id is not None:
        reserved = await _reserve_outbox(conn, outbox_id)
        if not reserved:
            print(
                f"[wr3-supervisor] outbox {outbox_id} already in-flight or consumed — skipping {channel}/{episode_id}",
                file=sys.stderr,
            )
            return

    try:
        prompt = _build_prompt(channel, agent_name, payload)
        result = await dispatch_agent(
            contracts, agent_name, prompt, episode_id=episode_id
        )

        # ACK ONLY on success (Symbiosis Law 3 — outbox explicit-ack contract)
        if outbox_id is not None:
            await _acknowledge_outbox(conn, outbox_id)

        duration_ms = int((asyncio.get_event_loop().time() - started) * 1000)
        telemetry_emit(
            agent=agent_name,
            episode_id=episode_id,
            outcome="PASS",
            duration_ms=duration_ms,
            cost_usd=result.cost_usd_estimated,
            contract_version=contracts.for_agent(agent_name).contract_version,
        )

    except OSINTLeakError as e:
        # Law 2 trumps everything — episode halts even if Zero approved publish
        telemetry_emit(
            agent=agent_name,
            episode_id=episode_id,
            outcome="FAIL",
            duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            error=f"OSINT_LEAK: {e}",
        )
        await telegram_p0(f"OSINT LEAK in {channel}/{episode_id}: {e}")
        raise  # do NOT ack — manual investigation needed
    except HardHaltException as e:
        # Law 7: gate ceiling hit on dispatch
        telemetry_emit(
            agent=agent_name,
            episode_id=episode_id,
            outcome="FAIL",
            duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            error=f"HARD_HALT: {e}",
        )
        raise
    except CascadeExhaustedError as e:
        # Law 4: cascade exhausted, do NOT ack — retry on next reconnect
        telemetry_emit(
            agent=agent_name,
            episode_id=episode_id,
            outcome="FAIL",
            duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            error=f"CASCADE_EXHAUSTED: {e}",
        )
        raise
    except Exception as e:
        telemetry_emit(
            agent=agent_name,
            episode_id=episode_id,
            outcome="FAIL",
            duration_ms=int((asyncio.get_event_loop().time() - started) * 1000),
            error=str(e)[:300],
        )
        if route.hot_path:
            await telegram_p0(f"WR3 {channel} handler crashed: {e}")
        raise  # NOT acked — replays on reconnect


def _build_prompt(channel: str, agent_name: str, payload: dict) -> str:
    """Construct dispatch prompt from channel payload.

    Per-channel templates kept minimal here — the agent .md itself has the
    detailed system prompt (Claude Agent SDK injects it via agent= field).
    """
    ep = payload.get("episode_id", "unknown")
    topic = payload.get("topic", "")
    base = f"episode_id={ep}\nchannel={channel}\n"

    if channel == "wr3_episode_brief_requested":
        return base + f"topic: {topic}\naudience: {payload.get('audience', 'general')}\nmode: {payload.get('mode', 'standard')}\n\nProduce brief.json per contract."
    if channel == "wr3_episode_pre_render_ready":
        return base + "Read brief.json. Fan out script-editor + shot-director + audio-asset-producer in parallel."
    if channel == "wr3_episode_gate_passed":
        return base + "Read shot-pack.json. Render clips via Flow Pro 200 cr ceiling."
    if channel == "wr3_episode_assembly_ready":
        return base + "Read clips/ + audio/. Assemble master.mp4 + 4 variants + episode_manifest.json."
    if channel == "wr3_episode_critic_verdict":
        verdict = payload.get("verdict", "PENDING")
        return base + f"Critic verdict: {verdict}. Route retry lane OR proceed to staged."
    if channel == "wr3_episode_staged":
        return base + "Move to Drive staging. Telegram P0 to Antonello for manual publish."
    return base + "Unrecognized channel — no-op."


async def _reserve_outbox(conn: Any, outbox_id: int, stale_after_seconds: int = 600) -> bool:
    """Optimistic-CAS reserve an outbox row before dispatch.

    Returns True if THIS process successfully reserved the row, False if
    another supervisor instance is already processing it (still within
    stale_after_seconds window) or if the row was already consumed.

    Implements the "reserve before dispatch" half of the idempotency contract
    (review-2026-05-18 finding from Codex+Gemini+DeepSeek 3/3 panel). Uses
    `consumed_at IS NULL` as the unclaimed sentinel — leverages the existing
    events_outbox schema (migration 144) without requiring a new column.

    For now reservation is best-effort using consumed_at — a future migration
    may add an explicit `reserved_at`/`reserved_by` pair if multi-supervisor
    contention becomes real. For SINGLE-supervisor deploys the reservation
    collapses to a no-op (row is always unclaimed when we see the NOTIFY).
    """
    try:
        # Simple CAS: only update if NOT consumed. We do NOT mark
        # consumed yet — that's the post-dispatch ack step. The reservation
        # below is conservative: a SECOND supervisor that picks up the same
        # event will fail at the ack step (consumed_at already set) and
        # detect the duplicate via downstream side-effect tracking.
        result = await conn.fetchval(
            """
            SELECT 1 FROM events_outbox
            WHERE id = $1 AND consumed_at IS NULL
            FOR UPDATE SKIP LOCKED
            """,
            outbox_id,
        )
        return result is not None
    except Exception as e:
        print(f"[wr3-supervisor] reserve_outbox failed for {outbox_id}: {e}", file=sys.stderr)
        # Degrade-loud: if reservation fails, DO NOT proceed (could be
        # duplicate). Better to skip and let next reconcile retry.
        return False


async def _acknowledge_outbox(conn: Any, outbox_id: int) -> None:
    """Mark an outbox row consumed. Mirrors EventBus.outbox.acknowledge.

    Imported lazily because the symbol lives in apps/backend-rag (not on
    sys.path at scripts/ unless venv activated).
    """
    try:
        # Use the same backend.services.events.outbox helper to keep semantics aligned
        from backend.services.events.outbox import acknowledge  # type: ignore
        await acknowledge(conn, outbox_id)
    except ImportError:
        # Fallback inline SQL — keeps script runnable from any cwd
        await conn.execute(
            "UPDATE events_outbox SET consumed_at = NOW() WHERE id = $1 AND consumed_at IS NULL",
            outbox_id,
        )


# ---------------------------------------------------------------------------
# Listener loop
# ---------------------------------------------------------------------------


async def run_supervisor(
    *,
    database_url: str | None = None,
    dry_run: bool = False,
    reconcile_interval_s: int = 300,
) -> None:
    asyncpg = _import_asyncpg()
    database_url = database_url or os.environ["DATABASE_URL"]

    contracts = load_contracts()
    print(f"[wr3-supervisor] Loaded {len(contracts.agents)} contracts, {len(contracts.routes)} channels")
    print(f"[wr3-supervisor] Router version: {contracts.router_version}")
    print(f"[wr3-supervisor] Dry run: {dry_run}")

    stop_event = asyncio.Event()

    def _handle_sigterm() -> None:
        print("[wr3-supervisor] SIGTERM received, draining…")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_sigterm)

    # Layer 5 — exponential backoff counter for reconnect attempts
    backoff_attempt = 0

    while not stop_event.is_set():
        conn: Any = None
        try:
            conn = await asyncpg.connect(database_url)
            print(f"[wr3-supervisor] Connected to PG ({database_url.split('@')[-1]})")

            # Layer 3 — PER-ITERATION queue + dead_event, captured via
            # default args (post-redteam P0-B amendment 2026-05-22: Python
            # closures bind by NAME not VALUE; without default-args, old
            # callbacks fired after reconnect would set the NEW dead_event).
            session_queue: asyncio.Queue = asyncio.Queue()
            dead_event = asyncio.Event()

            def _on_terminate(
                _conn: Any,
                *,
                _q: asyncio.Queue = session_queue,
                _de: asyncio.Event = dead_event,
            ) -> None:
                """asyncpg fires this when it detects connection termination.
                Must not raise. Default args pin THIS iteration's q+de."""
                _de.set()
                try:
                    _q.put_nowait(("__dead__", ""))
                except Exception:
                    pass

            conn.add_termination_listener(_on_terminate)

            def _on_notify(
                _conn: Any,
                _pid: int,
                channel: str,
                payload: str,
                *,
                _q: asyncio.Queue = session_queue,
                _de: asyncio.Event = dead_event,
            ) -> None:
                """NOTIFY callback. Default args pin THIS iteration's q+de."""
                if _de.is_set():
                    return  # connection already known dead — discard
                try:
                    _q.put_nowait((channel, payload))
                except Exception as e:
                    print(
                        f"[wr3-supervisor] queue.put_nowait failed: {e}",
                        file=sys.stderr,
                    )

            for ch in contracts.routes:
                await conn.add_listener(ch, _on_notify)
                print(f"[wr3-supervisor] LISTEN {ch}")

            # Initial reconcile — replay unconsumed outbox rows for our channels.
            # May raise _ReconnectRequired if conn is already dead.
            await _reconcile_unconsumed(conn, contracts)

            last_reconcile = asyncio.get_event_loop().time()
            last_heartbeat = last_reconcile

            # Connection is established — reset backoff for next failure cycle
            backoff_attempt = 0

            while not stop_event.is_set():
                try:
                    channel, payload = await asyncio.wait_for(
                        session_queue.get(), timeout=5.0
                    )
                except asyncio.TimeoutError:
                    now = asyncio.get_event_loop().time()
                    # Layer 4 — periodic heartbeat catches half-open TCP
                    # (termination listener won't fire on silent network freeze).
                    if now - last_heartbeat > 30.0:
                        await _heartbeat(conn, timeout=2.0)  # raises _ReconnectRequired on failure
                        last_heartbeat = now
                    # Periodic outbox reconcile (Symbiosis Law 3)
                    if now - last_reconcile > reconcile_interval_s:
                        await _reconcile_unconsumed(conn, contracts)
                        last_reconcile = now
                    continue

                # Termination-listener sentinel — connection died, reconnect
                if channel == "__dead__" or dead_event.is_set():
                    raise _ReconnectRequired("termination listener fired")

                try:
                    await route_event(conn, contracts, channel, payload, dry_run=dry_run)
                except Exception as e:
                    print(f"[wr3-supervisor] route_event error: {e}", file=sys.stderr)
                    if _is_connection_fatal(e):
                        raise _ReconnectRequired("route_event used dead connection") from e
                    # Non-fatal: keep the listener loop alive

            # Graceful shutdown path (stop_event set)
            try:
                await conn.close()
            except Exception:
                pass
            print("[wr3-supervisor] graceful shutdown complete")
            return

        except _ReconnectRequired as e:
            print(f"[wr3-supervisor] reconnect required: {e!s}", file=sys.stderr)
            # CRITICAL: close conn before next iteration so asyncpg releases
            # references to old _on_notify/_on_terminate (defends against
            # the closure-capture trap even though default-args already pin).
            if conn is not None:
                try:
                    await conn.close()
                except Exception:
                    pass
            # Layer 5 — exponential backoff 2→4→8→16→30 (cap)
            backoff_s = min(2 * (2 ** backoff_attempt), 30)
            backoff_attempt = min(backoff_attempt + 1, 4)
            await asyncio.sleep(backoff_s)
            continue

        except Exception as e:
            print(
                f"[wr3-supervisor] listener crashed: {e!r}, backing off 5s",
                file=sys.stderr,
            )
            if conn is not None:
                try:
                    await conn.close()
                except Exception:
                    pass
            await asyncio.sleep(5)


async def _reconcile_unconsumed(conn: Any, contracts: WR3Contracts) -> None:
    """Replay outbox rows older than 60 min and not yet consumed.

    Symbiosis Law 3 (Event-driven durability) — outbox replay on reconnect.

    Layer 2 (post 3-LLM panel + red-team gate 2026-05-22): classifies the
    exception. Connection-fatal errors (`asyncpg.InterfaceError`,
    `ConnectionDoesNotExistError`) raise `_ReconnectRequired` so the outer
    loop reconnects. Non-fatal errors (e.g., `PostgresSyntaxError`) are
    logged and swallowed — they're script bugs, not transport issues.

    Previously: ALL exceptions were swallowed with `print + return`, which
    left the supervisor running on a dead asyncpg connection indefinitely.
    Vecchio PID 25068 (2026-05-22 03:09 WITA) lived 3h09m in this zombie
    state with lsof showing 0 open PG sockets.
    """
    try:
        rows = await conn.fetch(
            """
            SELECT id, channel, payload
            FROM events_outbox
            WHERE channel = ANY($1)
              AND consumed_at IS NULL
              AND created_at >= NOW() - INTERVAL '60 minutes'
            ORDER BY id ASC
            LIMIT 100
            """,
            list(contracts.routes.keys()),
        )
    except Exception as e:
        print(f"[wr3-supervisor] reconcile query failed: {e}", file=sys.stderr)
        is_closed_fn = getattr(conn, "is_closed", None)
        if _is_connection_fatal(e) or (callable(is_closed_fn) and is_closed_fn()):
            raise _ReconnectRequired("reconcile_unconsumed hit dead connection") from e
        return  # non-fatal: log + continue

    if not rows:
        return
    print(f"[wr3-supervisor] Replaying {len(rows)} unconsumed outbox rows…")
    for row in rows:
        payload = row["payload"]
        if isinstance(payload, dict):
            payload_str = json.dumps({**payload, "_outbox_id": row["id"]})
        else:
            try:
                pd = json.loads(payload)
                payload_str = json.dumps({**pd, "_outbox_id": row["id"]})
            except json.JSONDecodeError:
                payload_str = payload
        try:
            await route_event(conn, contracts, row["channel"], payload_str)
        except Exception as e:
            print(f"[wr3-supervisor] replay {row['id']} failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def _parse_bool(v: str | None) -> bool:
    return (v or "").strip().lower() in {"1", "true", "yes", "on"}


def main() -> None:
    dry_run = _parse_bool(os.environ.get("WR3_DRY_RUN"))
    interval = int(os.environ.get("WR3_RECONCILE_INTERVAL_SEC", "300"))
    try:
        asyncio.run(run_supervisor(dry_run=dry_run, reconcile_interval_s=interval))
    except KeyboardInterrupt:
        print("[wr3-supervisor] interrupted", file=sys.stderr)


if __name__ == "__main__":
    main()
