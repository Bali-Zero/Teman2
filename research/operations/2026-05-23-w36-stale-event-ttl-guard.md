---
date: 2026-05-23
domain: compliance
client_case: NB-automations hardening loop W36 — Cell/Organism auto-heal safety
sources: 5
---

# W36 — stale-event TTL guard on outbox replay path

## Context

The W27 + W31 + W33 Cell/Organism auto-heal chain wires `cell_pulse_observed`
PG events through `scripts/pg-to-organism-bridge.py` to the Organism
supervisor, which can fire `fly_machines_restart` (and other actuators)
via rules like `cell_sustained_red_restart`
(`apps/organism/organism/rules/base.yaml:75-79`).

W27 panel synthesis listed "stale-event TTL on replay" as a deferred
hardening item: after `pg-to-organism-bridge` reconnects (or after
`EventBus._replay_outbox_on_reconnect` runs on its listener), OLD events
that were never acked could re-fire and trigger actuators against
machines whose state has already recovered.

## Investigation — was the gap real?

Two-stage audit.

### Bridge (`scripts/pg-to-organism-bridge.py`)

Read in full. The bridge uses `asyncpg.add_listener` for live `LISTEN`
events only. `grep -n "replay\|outbox" scripts/pg-to-organism-bridge.py`
returns ONE hit — `payload.get("_outbox_id")` inside `_build_event` (used
only as a correlation id). **No replay path exists on the bridge.**
Bridge restart → only live NOTIFYs from the moment of reconnect onward
are processed. Verdict: bridge-level TTL **not needed**.

### EventBus (`apps/backend-rag/backend/services/events/event_bus.py`)

The PG `EventBus._replay_outbox_on_reconnect` (line 376) calls
`outbox.replay_unconsumed` on every reconnect for every
`PG_CHANNEL_MAP` entry — including `cell_pulse_observed`. Each dispatched
row goes through `_handle_pg_event`, which feeds the same listener
callbacks that drive the live system. After dispatch, the row is acked.

`outbox.replay_unconsumed` already has a TTL — but only row-level:
`WHERE created_at > NOW() - INTERVAL '60 minutes'`. The hardcoded
`max_age_minutes=60` in `event_bus.py:419` is the de-facto safety net
today.

**The W36 gap is real but narrow.** A row can be fresh (`created_at`
recent because of a long-running PG transaction that finally committed)
while its in-payload `pulse_timestamp` is hours older. That is exactly
the failure mode for `cell_pulse_observed` payloads, which carry
`pulse_timestamp` in ms-since-epoch (per
`packages/cell-core/cell_core/observatory.py:113`).

The row-level TTL alone cannot catch this. A payload-level TTL is the
defense-in-depth.

## Design

In `apps/backend-rag/backend/services/events/outbox.py`:

1. **Module-level constants**
   - `_DEFAULT_PAYLOAD_TTL_MIN = 60`
   - `_PAYLOAD_TTL_ENV_VAR = "BRIDGE_STALE_EVENT_TTL_MIN"`
   - `_PAYLOAD_TIMESTAMP_FIELDS = ("pulse_timestamp", "timestamp", "ts")`
     (ordered priority)

2. **`_resolve_payload_ttl_minutes(explicit=None)`** — precedence:
   explicit arg > env > default. Malformed or negative env values log a
   WARNING and fall back to the default (no silent disabling of the
   guard via typo).

3. **`_payload_timestamp_seconds(payload)`** — extract first recognised
   timestamp. Heuristic for unit detection: values > 1e12 are assumed
   ms (1e12 ms is 2001-09-09; 1e12 s is year 33658 — safe boundary).

4. **`_is_payload_stale(payload, ttl_minutes)`** — **open by default**:
   payloads without any recognised timestamp field return `False` (not
   stale). This is intentional: closing-by-default would mass-drop
   channels like `practice_changed` that have no pulse timestamp.

5. **`replay_unconsumed`** picks up a new kwarg
   `payload_ttl_minutes: int | None = None`. When a stale row is
   detected:
   - `dispatch_fn` is NOT called
   - The row is **acked** (with `consumer_id="<base>_stale_skip"`) so it
     stops re-firing on subsequent replays
   - A WARNING log line surfaces the skip with `id`, `channel`, and TTL
   - The skip counts toward the returned `acked` value (the docstring
     defines `acked` as "rows removed from the unconsumed backlog")

The live (real-time) NOTIFY path through `_on_notification` is
**unchanged** — only `replay_unconsumed` is gated. Live events that fire
within their own propagation window are by definition fresh; the TTL is
a replay-only safety.

## Test coverage

19 tests in `backend/tests/services/events/test_outbox_stale_ttl.py`:

| Group                           | Tests | Coverage                                                                                            |
| ------------------------------- | ----- | --------------------------------------------------------------------------------------------------- |
| `_resolve_payload_ttl_minutes`  | 5     | default, env, explicit-wins, malformed-env, negative-env                                            |
| `_payload_timestamp_seconds`    | 5     | ms field, sec fallback, missing, invalid, non-dict                                                  |
| `_is_payload_stale`             | 4     | fresh, old, no-timestamp open-default, ttl=0 disables                                               |
| `replay_unconsumed` integration | 5     | stale-skip+ack, no-timestamp pass-through, env override, explicit-arg override, WARNING log emitted |

All 19 PASS in 0.08s. Regression sweep against the 4 existing event-outbox
test files: 32 PASS + 6 SKIP (pre-existing skips, unrelated).

## Why ack-on-skip rather than drop-without-ack

Alternatives considered:

- **Drop without ack** — leaves the row in the unconsumed backlog,
  re-fires on every replay, WARNING emits forever. Bad ergonomics.
- **DELETE the row** — destroys audit trail. Bad.
- **Ack with stale_skip consumer_id** (chosen) — backlog drains,
  `consumer_id` field carries the stale-skip annotation for forensic
  queries, single WARNING line per stale row, no replay storm.

The `consumed_at` field still says "consumed" but the `consumer_id`
column (`<base>_stale_skip`) lets operators distinguish stale skips from
real dispatches in post-mortem.

## Trade-offs

- **Heuristic for ms vs seconds is a magic number.** 1e12 cutoff works
  for the next ~30000 years for the seconds case; not a real risk.
- **Open-by-default on missing timestamps** means a future channel that
  carries a timestamp under a non-standard key won't benefit from the
  guard until added to `_PAYLOAD_TIMESTAMP_FIELDS`. Acceptable: the
  row-level TTL is still in force.
- **Env var read on every replay call** (no caching). Acceptable for
  the call frequency (one call per channel per reconnect, ~14 channels).

## Open follow-ups

- `event_bus.py:419` still passes `max_age_minutes=60` hardcoded. Could
  be wired to the same env var for row-level/payload-level parity.
  Deferred — the row-level filter is a SQL `WHERE` clause and is already
  doing the right thing under normal conditions.
- The bridge (`pg-to-organism-bridge.py`) is LISTEN-only and is fine;
  no changes shipped to that file.

## References

- Source: `apps/backend-rag/backend/services/events/outbox.py`
- Tests: `apps/backend-rag/backend/tests/services/events/test_outbox_stale_ttl.py`
- Cell pulse producer: `packages/cell-core/cell_core/observatory.py:83-148`
- Bridge: `scripts/pg-to-organism-bridge.py`
- Rule: `apps/organism/organism/rules/base.yaml:75-79`
- W27 cicatrix (panel-deferred TTL): `.claude/rules/cicatrix-scars.md`
