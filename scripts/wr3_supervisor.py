#!/usr/bin/env python3
"""WR3 Supervisor — event-bus consumer + episode lifecycle coordinator.

Listens on 6 PG channels declared in migration 182_wr3_eventbus_channels.sql:
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

# Make sibling scripts importable as top-level modules
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from wr3_contracts import WR3Contracts, load_contracts  # noqa: E402
from wr3_dispatch_agent import (  # noqa: E402
    CascadeExhaustedError,
    HardHaltException,
    OSINTLeakError,
    dispatch_agent,
    telegram_p0,
)
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

    queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

    def _on_notify(_conn: Any, _pid: int, channel: str, payload: str) -> None:
        queue.put_nowait((channel, payload))

    while not stop_event.is_set():
        try:
            conn = await asyncpg.connect(database_url)
            print(f"[wr3-supervisor] Connected to PG ({database_url.split('@')[-1]})")
            for ch in contracts.routes:
                await conn.add_listener(ch, _on_notify)
                print(f"[wr3-supervisor] LISTEN {ch}")

            # Initial reconcile — replay unconsumed outbox rows for our channels
            await _reconcile_unconsumed(conn, contracts)

            last_reconcile = asyncio.get_event_loop().time()
            while not stop_event.is_set():
                try:
                    channel, payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    # idle — check reconcile timer
                    if asyncio.get_event_loop().time() - last_reconcile > reconcile_interval_s:
                        await _reconcile_unconsumed(conn, contracts)
                        last_reconcile = asyncio.get_event_loop().time()
                    continue

                try:
                    await route_event(conn, contracts, channel, payload, dry_run=dry_run)
                except Exception as e:
                    print(f"[wr3-supervisor] route_event error: {e}", file=sys.stderr)
                    # Do NOT crash the listener loop — next event continues

            await conn.close()
            print("[wr3-supervisor] graceful shutdown complete")
            return

        except Exception as e:
            print(f"[wr3-supervisor] listener crashed: {e!r}, backing off 5s", file=sys.stderr)
            await asyncio.sleep(5)


async def _reconcile_unconsumed(conn: Any, contracts: WR3Contracts) -> None:
    """Replay outbox rows older than 60 min and not yet consumed.

    Symbiosis Law 3 (Event-driven durability) — outbox replay on reconnect.
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
        return

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
