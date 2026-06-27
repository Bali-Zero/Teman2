# WA Meta Inbox — outbox scheduler (enable SEND)

> Date: 2026-06-04 · Domain: backend · Depends on: wa-meta-inbox backend (PR #1081, live)

## Problem

The backend captures + reads Meta WhatsApp threads, and `wa_outbox` rows are
enqueued (by the human-send endpoint `POST /threads/{id}/send` and, later, by
the bot path). But `process_outbox_once()` is never called by anything — the
scheduler loop was intentionally left as a TODO. So **nothing is sent**: rows
sit `pending` forever. This wires the loop so SEND works.

## Verified facts

| Fact | Value |
|---|---|
| Unit of work | `process_outbox_once(pool, whatsapp_service, bot_generate_fn) -> str` |
| Returns | `idle / sent / aborted_human / window_closed / retry / failed` |
| `whatsapp_service` | singleton `backend.services.integrations.whatsapp_service.whatsapp_service`, has `async send_message(phone, text, reply_to_message_id=None)` |
| `api` process group | always-on (`auto_stop='off'`, `min_machines_running=1`), single-worker (fly.toml comment: 2 workers duplicate background loops → keep single) |
| `rag` process group | no `[[services]]` block; not guaranteed always-on |
| Existing bg-loop host | `main_api.py::lifespan_light` already runs Notification Scheduler in an `asyncio.create_task`, gated by `DISABLE_BACKGROUND_WORKERS` |
| Existing bg-loop precedent | `app_factory.py::lifespan` (full/rag) runs `run_worker`, `legal_run_worker` |
| claim lease | `wa_outbox.claim_expires_at`, `FOR UPDATE SKIP LOCKED` → double-worker is safe (no double-send) but wasteful |

## Design

### Host: `lifespan_light` on the `api` process group

Add the scheduler as an `asyncio.create_task` in `main_api.py::lifespan_light`,
inside the existing `DISABLE_BACKGROUND_WORKERS` else-block, right after the
Notification Scheduler. Rationale:
- `api` is the only always-on, single-worker group → exactly one loop, never
  stopped, no double-worker waste.
- `lifespan_light` already owns `app.state.db_pool` and one bg loop — same
  pattern, same shutdown path.
- The webhook that enqueues also runs on `api` → producer + consumer co-located.

### The loop

```python
async def _run_wa_outbox_scheduler(pool, bot_generate_fn) -> None:
    from backend.services.integrations.whatsapp_service import whatsapp_service
    from backend.services.integrations.wa_outbox_worker import process_outbox_once
    interval = float(os.getenv("WA_OUTBOX_POLL_SECONDS", "3"))
    while True:
        try:
            status = await process_outbox_once(pool, whatsapp_service, bot_generate_fn)
            # tight loop while draining, back off when idle
            await asyncio.sleep(0 if status == "sent" else interval)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("wa-outbox scheduler tick failed")
            await asyncio.sleep(interval)
```

Cancelled cleanly on shutdown (store task on `app.state`, cancel in the
shutdown half of the lifespan — mirror the existing worker tasks).

### bot_generate_fn — v1 scope decision (panel must settle)

`process_outbox_once` only calls `bot_generate_fn` for rows with
`needs_generation = true`. Human-typed sends (`POST /threads/{id}/send`) carry
the text already (`needs_generation = false`) and never invoke it.

- **Option A — human-send only (v1):** pass a `bot_generate_fn` that raises
  `NotImplementedError`. The operator-typed sends work end-to-end immediately
  (this is the "prepare + monitor before publishing the number" need). Bot
  auto-reply stays off until a later PR wires the RAG orchestrator. Smallest,
  safest, ships the SEND the operator actually asked for. A bot row, if any
  somehow gets enqueued, would error → `retry`/`failed`, never a wrong send.
- **Option B — bot auto-reply now:** `bot_generate_fn` calls the RAG worker
  (HTTP `RAG_WORKER_URL` from the `api` machine, since RAG lives on the `rag`
  group). More moving parts, needs prompt/persona wiring + the human-in-the-loop
  `human_handling` interplay re-verified live. Larger surface, more risk.

Recommendation in the spec: **A** for this PR (matches the stated need —
prepare/monitor + human reply before publication), B as a follow-up.

## Kill switch & ops

- `DISABLE_BACKGROUND_WORKERS=1` already disables it (shared with other loops).
- `WA_OUTBOX_SCHEDULER_ENABLED=0` disables only the WA outbox scheduler while
  leaving the API-side Notification Scheduler and other background workers on.
- `WA_OUTBOX_POLL_SECONDS` (default 3) tunes cadence.
- Loop logs each non-idle status at INFO; exceptions at EXCEPTION (never crashes
  the app — the lifespan task swallows and backs off).

## Test plan

1. Unit: a fake pool/whatsapp_service driving `_run_wa_outbox_scheduler` for N
   ticks — asserts it calls `process_outbox_once`, sleeps 0 after `sent`,
   `interval` after `idle`, and survives a raised exception (logs, continues).
2. Unit: cancellation — task cancels cleanly on shutdown.
3. Existing `test_wa_outbox_worker.py` (21 tests) still green (worker unit
   unchanged).
4. Live (post-deploy): enqueue a human send via `POST /threads/{id}/send` from
   the local UI → observe `wa_outbox` row go `pending → done`, `meta_inbox_messages`
   status `sending → sent`, message delivered on WhatsApp.

## Rollback

Additive: the loop is one task gated by env vars. Revert = set
`WA_OUTBOX_SCHEDULER_ENABLED=0`, use the broader `DISABLE_BACKGROUND_WORKERS=1`,
or revert the diff. No schema, no data change.
