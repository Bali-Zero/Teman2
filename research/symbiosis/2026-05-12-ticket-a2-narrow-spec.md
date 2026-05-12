---
date: 2026-05-13
domain: symbiosis
client_case: SYMBIOSIS Phase 3 — TICKET A.2 narrow spec v2 (post 4-panel)
status: spec-v2-execution-ready
empirical_survey_wita: 2026-05-13 00:08
review_completed_wita: 2026-05-13 00:15
---

# TICKET A.2 — CrmHGTBridge production caller (narrow spec v2)

**Date**: 2026-05-13 00:15 WITA · **Predecessor**: TICKET A.1 merged (PR #632 → main `84953041b` at 00:03 WITA)
**Author**: Claude Opus 4.7 max
**Mode**: Spec v2 direct (4-panel review already unanimous on Option β) — per operator authorization "skip review pass"
**Estimated effort**: 1-1.5 days code + tests
**Review status**: 4/4 UNANIMOUS on **Option β** (Claude self 75% conf + Gemini PROCEED + DeepSeek PROCEED + NB-1 PROCEED with self-correction on prior δ signal)

## Goal

Wire the first production caller of `CrmHGTBridge` (from A.1) by creating `apps/backend-rag/backend/services/events/handlers/crm_hgt_handlers.py`, subscribing to existing PG_CHANNEL_MAP events, computing structural patterns via Redis sliding-window aggregation, and publishing them to `cell:skills`.

After A.2 merge:

- `redis-cli XLEN cell:skills` starts incrementing from 18 as practice/lkpm events arrive
- Sentinel-1 consumer group (when TICKET C ships) has CRM patterns to consume in addition to intel-scraper-cell patterns (from TICKET B)
- The HGT HALT (commit `68efc17e3`) gets closer to lift conditions (≥3 nights with positive delta in 14 days)

## 4-panel UNANIMOUS verdict

| Reviewer          | Recommendation   | Effort | Notable                                                                         |
| ----------------- | ---------------- | ------ | ------------------------------------------------------------------------------- |
| Claude self       | **β** (75% conf) | 1.5-2d | NB-1's δ co-location satisfied via dependency import                            |
| Gemini 3.1 Pro    | **β**            | 0.5-1d | F1 CRITICAL: δ violates SYMBIOSIS.md:180 Law 3 "Nessun polling"                 |
| DeepSeek Reasoner | **β**            | 1.5d   | Rejects α/γ/δ on canonical pattern + Law 3 grounds                              |
| NB-1 NotebookLM   | **β**            | 4-6h   | Self-corrects prior δ signal ("vaporware" pursuit), confirms handlers canonical |

**4/4 UNANIMOUS on β**. Brainstorm artifacts in `docs/audits/2026-05-13-ticket-a2-spec-brainstorm/`.

## Rejected alternatives (all 4 reviewers concur)

### Option α — Enhance `practice_status_listener.py`

**Rejected** because:

- Mixes "react to event" responsibility with "aggregate patterns" (Gemini F2 HIGH)
- Listener already heavy with M4/M5 email automation in critical path
- HGT publish exception could kill email dispatch (single async loop)

### Option γ — Extend `on_lkpm_readypack_generated`

**Rejected** because:

- SRP violation — compliance ≠ HGT evolution domain (NB-1)
- Too narrow scope — only LKPM patterns, other CRM signals abandoned
- Wastes A.1 bridge investment

### Option δ — crm-cell internal poller

**Rejected** CRITICAL by Gemini F1: violates `SYMBIOSIS.md:180` Law 3:

> "3. Event-driven, durabilità per canale. Nessun polling, nessun orchestratore centrale."

NB-1 self-corrects its previous δ co-location signal: _"Inseguire il purismo architetturale cercando di iniettare codice in una cellula fantasma (Opzione δ) non genererà alcun valore"_. The handlers pattern (Option β) achieves cell boundary cleanliness via **dependency import** not physical separation.

## Empirical state (2026-05-13 00:08 WITA — re-verified)

| Item                                                                | Status                                            |
| ------------------------------------------------------------------- | ------------------------------------------------- |
| TICKET A.0 `HGTPublisher.cell_name` public property                 | ✅ merged main `6e92046d8`                        |
| TICKET A.1 `CrmHGTBridge.publish()` async                           | ✅ merged main `84953041b`                        |
| `cell:skills` XLEN                                                  | 18 (Phase 2.5 seed, unchanged)                    |
| `crm` in CANONICAL_DOMAINS                                          | ✅ line 18 (commit `09aadbdc5` 2026-04-16)        |
| `services/events/handlers/compliance_handlers.py` canonical pattern | ✅ exists, HANDLERS dict + register_handlers(bus) |
| EventBus + outbox pattern                                           | ✅ migration 144 + 146 + PG_CHANNEL_MAP           |
| `register_handlers(bus)` wired in app startup                       | ✅ via `_background_init` in app_factory.py       |

## Architecture (Option β)

```
┌──────────────────────────────────────────────────────────────┐
│   FastAPI app (backend-rag)                                  │
│                                                              │
│   ┌────────────────┐  pg_notify   ┌─────────────────────┐    │
│   │ migration 075/ │ ───────────▶ │  EventBus listener  │    │
│   │ practice_chg   │              │  (asyncio task)     │    │
│   └────────────────┘              └──────────┬──────────┘    │
│                                              │                │
│                                              │ dispatch       │
│                                              ▼                │
│   ┌────────────────────────────────────────────────────────┐ │
│   │  services/events/handlers/                             │ │
│   │  ┌──────────────────────┐  ┌──────────────────────┐    │ │
│   │  │ compliance_handlers  │  │ crm_hgt_handlers     │    │ │
│   │  │ (existing)           │  │ (NEW — A.2)          │    │ │
│   │  └──────────────────────┘  └──────────┬───────────┘    │ │
│   │                                       │                │ │
│   │              ┌────────────────────────┘                │ │
│   │              ▼                                         │ │
│   │  ┌──────────────────────┐  ┌─────────────────────┐    │ │
│   │  │ Pattern aggregator   │  │ CrmHGTBridge        │    │ │
│   │  │ (Redis ZADD sliding) │─▶│ (A.1)               │    │ │
│   │  └──────────────────────┘  └──────────┬──────────┘    │ │
│   │                                       │                │ │
│   └───────────────────────────────────────┼────────────────┘ │
│                                           │                  │
└───────────────────────────────────────────┼──────────────────┘
                                            ▼
                              redis cell:skills stream (XADD)
                                            │
                                            ▼ (TICKET C consumer)
                              sentinel-1 consumer group
```

## Implementation

### File 1: `apps/backend-rag/backend/services/events/handlers/crm_hgt_handlers.py` (NEW)

Subscribes to existing PG_CHANNEL_MAP events. NO new channel needed for v1 (CAV-3 — defer Brevo webhook channel to v2):

```python
"""EventBus handlers for crm-cell HGT pattern broadcasting.

Phase 3 TICKET A.2 — first production caller of ``CrmHGTBridge`` from
``crm_cell.hgt_publisher`` (PR #632, commit 84953041b).

Architecture (post 4-panel UNANIMOUS Option β):
- Handlers subscribe to existing PG_CHANNEL_MAP dotted event types
- Per-event aggregation via Redis sorted-set sliding window (ZADD + ZREMRANGEBYSCORE)
- Pattern published via ``CrmHGTBridge.publish()`` when threshold met
- Bridge instantiated once at startup, injected via module-level lazy init

UU PDP discipline (inherited from A.1):
- Pattern strings never contain client_id, email, NPWP, phone
- Bridge has defense-in-depth PII scan on procedure/precondition/success_criterion

Refusals respected (Phase 3 spec v2 §14):
- No polling (Option δ rejected per SYMBIOSIS.md:180 Law 3)
- No edits to packages/cell-core/cell_core/hgt/* (refusal #9)
- No edits to apps/evaluator/seo_cell/ (refusal #13)
- No synchronous asyncio.run (refusal #14 — bridge is async)
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Lazy module-level bridge — instantiated on first handler call
_bridge = None


async def _get_bridge():
    """Lazy CrmHGTBridge factory — runs once per process."""
    global _bridge
    if _bridge is None:
        try:
            import redis.asyncio as redis_async
            from crm_cell.hgt_publisher import CrmHGTBridge

            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379")
            client = redis_async.from_url(redis_url, decode_responses=False)
            _bridge = CrmHGTBridge.from_redis(redis_client=client, cell_name="crm-cell")
            logger.info("crm_hgt_handlers: bridge initialized url=%s", redis_url)
        except Exception as exc:
            logger.warning("crm_hgt_handlers: bridge init failed: %s", exc)
            _bridge = False  # sentinel — no retry this process
    return _bridge if _bridge else None


# Window state stored in Redis as sorted set: key="crm.window.<pattern_id>", score=ts, member=event_id
# TTL aligned to pattern window (7d for practice, 30d for Brevo, 90d for LKPM)
async def _ingest_event(redis_client, window_key: str, event_id: str, ts_epoch: float,
                         retention_seconds: int) -> int:
    """Add event to sliding window + prune expired. Returns current window count."""
    try:
        cutoff = ts_epoch - retention_seconds
        # Add + prune in 1 round-trip via pipeline
        async with redis_client.pipeline(transaction=False) as pipe:
            pipe.zadd(window_key, {event_id: ts_epoch})
            pipe.zremrangebyscore(window_key, "-inf", cutoff)
            pipe.zcard(window_key)
            pipe.expire(window_key, retention_seconds + 60)  # safety TTL
            results = await pipe.execute()
        return results[2]  # zcard result
    except Exception as exc:
        logger.warning("crm_hgt_handlers: window state failed key=%s err=%s", window_key, exc)
        return 0


# ---------------------------------------------------------------------------
# Pattern 1: practice.stage_cycle_time
# ---------------------------------------------------------------------------

# Threshold: 20 transitions in 7-day window before publishing pattern
_PRACTICE_WINDOW_SECONDS = 7 * 24 * 3600
_PRACTICE_THRESHOLD_N = 20


async def on_practice_status_changed(payload: dict[str, Any]) -> None:
    """Aggregate practice stage transitions; emit cycle-time pattern.

    Subscribes to PG channel ``practice_changed`` → event type ``practice.status_changed``.
    """
    bridge = await _get_bridge()
    if bridge is None:
        return

    practice_id = payload.get("practice_id")
    old_status = payload.get("old_status")
    new_status = payload.get("new_status")
    if not (practice_id and old_status and new_status):
        return

    # ... aggregation logic via _ingest_event ...
    # On threshold reached, build StructuralPattern + bridge.publish()
    # (Full impl in handler file)


# ---------------------------------------------------------------------------
# Pattern 2: lkpm.ingestion_success_rate
# ---------------------------------------------------------------------------

_LKPM_WINDOW_SECONDS = 90 * 24 * 3600
_LKPM_THRESHOLD_N = 10


async def on_lkpm_ingest_completed(payload: dict[str, Any]) -> None:
    """Aggregate LKPM ingestion outcomes; emit success-rate pattern per segment.

    Coexists with compliance_handlers.on_lkpm_readypack_generated — both
    subscribe to the same event type with different responsibilities.
    """
    bridge = await _get_bridge()
    if bridge is None:
        return
    # ... aggregation + pattern publish ...


# ---------------------------------------------------------------------------
# Pattern 3: client.engagement_rate (DEFERRED to A.2-followup)
# ---------------------------------------------------------------------------
# client.changed fires too often (per DeepSeek F3 — every CRM edit).
# Spec v2 ships practice + lkpm only. client.changed pattern needs
# dedup gate design (separate PR).


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

HANDLERS = {
    "practice.status_changed": on_practice_status_changed,
    "lkpm.ingest_completed": on_lkpm_ingest_completed,
}


def register_crm_hgt_handlers(bus) -> None:
    """Subscribe all crm-cell HGT handlers to EventBus.

    Call from app_factory._background_init AFTER the compliance handlers
    register, so they run in deterministic order on the same event types
    (where applicable — e.g. lkpm.ingest_completed has both compliance +
    crm_hgt subscribers).
    """
    for event_type, handler in HANDLERS.items():
        bus.subscribe(event_type, handler)
    logger.info("crm_hgt_handlers registered (%d handlers)", len(HANDLERS))
```

### File 2: Registration in `apps/backend-rag/backend/app/setup/service_initializer.py` (or app_factory.py — exact location TBD by reading file)

Add ONE call after `register_handlers(bus)`:

```python
from backend.services.events.handlers.crm_hgt_handlers import register_crm_hgt_handlers
register_crm_hgt_handlers(bus)
```

### File 3: `apps/backend-rag/backend/tests/services/events/handlers/test_crm_hgt_handlers.py` (NEW, 12 tests)

```python
"""Phase 3 TICKET A.2 — crm_hgt_handlers async tests.

12 tests covering:
- 2 handlers (on_practice_status_changed, on_lkpm_ingest_completed) × {
    - happy path (event → window ZADD → threshold check)
    - below threshold (no publish)
    - missing required payload fields (early return, no error)
    - bridge None (graceful degradation)
    - window state Redis error (logged, no propagation)
    - pattern publish call args (assert canonical StructuralPattern)
  }

Plus 1 registration test asserting HANDLERS dict + register_crm_hgt_handlers
subscribes to expected event types.
"""
```

### File 4: Integration smoke test (1 test)

`apps/backend-rag/backend/tests/integration/test_crm_hgt_e2e.py` (NEW):

- Mock Redis + mock EventBus
- Fire 25 practice.status_changed events in sequence
- Assert window key has 25 entries, threshold (20) crossed
- Assert `CrmHGTBridge.publish()` called with canonical 6-field StructuralPattern
- Assert xadd call args contain expected `skill_id=crm.pattern.practice_stage_cycle_time`

## Caveats (from 4-panel synthesis)

### CAV-1: Aggregation cadence

**Event-driven only**, NO polling (Gemini F1 CRITICAL).

- Per-event Redis ZADD + ZREMRANGEBYSCORE (1 pipeline round-trip)
- Threshold check on each event arrival
- Compute + publish only when threshold crossed
- TTL on window key prevents Redis memory leak

### CAV-2: Pattern catalog (v1 scope = 2 patterns)

1. `practice.stage_cycle_time` — domain="crm", trigger=practice.status_changed, window=7d, threshold=20
2. `lkpm.ingestion_success_rate` — domain="crm", trigger=lkpm.ingest_completed, window=90d, threshold=10

**Deferred to A.2-followup**:

- `brevo.template_bounce_rate` — needs NEW event type + PG migration (out of v1 scope)
- `client.engagement_rate` — needs dedup gate design (client.changed too noisy per DeepSeek F3)

### CAV-3: Event subscription (existing PG_CHANNEL_MAP only)

- ✅ `practice.status_changed` (from practice_changed PG channel, migration 075)
- ✅ `lkpm.ingest_completed` (already in PG_CHANNEL_MAP; coexist with compliance handler — both subscribe via EventBus.subscribe so multiple handlers per event type work)

NO new channels in v1. New event types require separate PR with PG trigger migration.

### CAV-4: Bridge initialization

Lazy module-level singleton via `_get_bridge()`. On first call:

- Reads `REDIS_URL` env (default `redis://localhost:6379`)
- Constructs `CrmHGTBridge.from_redis(redis_client, cell_name="crm-cell")`
- Caches for process lifetime
- On init failure → logs warning, returns None, sets sentinel to skip retry

## Acceptance criteria

1. ✅ CI tests green: `pytest apps/backend-rag/backend/tests/services/events/handlers/test_crm_hgt_handlers.py -v` → 12/12 pass
2. ✅ Integration test green: `pytest apps/backend-rag/backend/tests/integration/test_crm_hgt_e2e.py -v` → 1/1 pass
3. ✅ Regression: `pytest apps/crm-cell/tests/ -v` → 15/15 still pass (A.1 unaffected)
4. ✅ Regression: `pytest packages/cell-core/tests/hgt/ -v` → all pass (A.0 unaffected)
5. ✅ Registration verified: app startup log shows `crm_hgt_handlers registered (2 handlers)`
6. ✅ After 1st nightly with N≥20 practice transitions: `redis-cli XLEN cell:skills` increments by ≥1 with `skill_id=crm.pattern.practice_stage_cycle_time`
7. ✅ No regression in compliance handlers (`on_lkpm_readypack_generated` still fires)

## Refusals (inherits Phase 3 spec v2 §14)

This narrow spec inherits all 14 refusals. Key ones for A.2:

- ❌ No polling/cron daemon (Option δ rejected per SYMBIOSIS.md:180 Law 3)
- ❌ No edits to `packages/cell-core/cell_core/hgt/*` (refusal #9 — A.0 only)
- ❌ No edits to `apps/evaluator/seo_cell/` (refusal #13)
- ❌ No synchronous `asyncio.run` in HGT handler code (refusal #14)
- ❌ No new PG_CHANNEL_MAP entries (defer Brevo channel to v2)
- ❌ No edits to compliance_handlers.py (additive only — new file)
- ❌ No deployment of TICKET C before TICKET B in production (refusal #12)

## Effort estimate

| Component                                  | Hours                |
| ------------------------------------------ | -------------------- |
| Spec v2 (this doc)                         | 1                    |
| Pattern catalog refinement (2 patterns)    | 1                    |
| `crm_hgt_handlers.py` implementation       | 4                    |
| Redis sliding-window helper                | 1                    |
| Bridge lazy init + error handling          | 1                    |
| 12 unit tests                              | 3                    |
| 1 integration test                         | 1                    |
| Registration wire (service_initializer.py) | 0.5                  |
| Doc update (apps/crm-cell/CLAUDE.md?)      | 0.5                  |
| **Total A.2**                              | **~13h (~1.5 days)** |

Aligns with DeepSeek 1.5d / Claude self 1.5-2d. Gemini 0.5-1d and NB-1 4-6h were optimistic (didn't account for caching + 12 tests).

## Sequencing

**Operator decision**: A.2 ships AFTER TICKET B (per DeepSeek rationale).

Rationale:

- B is the first production publisher; let it shake out pipeline (bridge → stream → consumer) with single emitter
- If B has hidden failure (schema mismatch, consumer choke), debug isolation easier
- A.2 then adds CRM patterns to a validated pipeline
- No hard dependency between A.2 and B (both are publishers, decoupled via stream)

Pragmatic Phase 3 order: **A.0 ✅ → A.1 ✅ → B → A.2 → C → 14d soak → FASE 4 lift**

## Risk assessment (from 4-panel synthesis)

| Risk                                                   | Severity | Mitigation                                                                |
| ------------------------------------------------------ | -------- | ------------------------------------------------------------------------- |
| Aggregation state requires Redis cache                 | HIGH     | Redis ZADD/ZREMRANGEBYSCORE sliding window (existing infra)               |
| Event loop blocking                                    | MEDIUM   | Mitigated — A.1 CrmHGTBridge.publish is `async def`                       |
| DB N+1 load if handler queries DB per event            | MEDIUM   | Spec mandates Redis-first; no DB query in v1 (counters only)              |
| Handler trigger granularity (client.changed too noisy) | MEDIUM   | Resolved — `client.changed` deferred to v2; v1 ships practice + lkpm only |
| Coupling with TICKET C consumer scaling                | LOW      | Document for C's soak tests                                               |
| File ownership (handler imports crm-cell)              | VERY LOW | Acceptable — handler is consumer of bridge                                |

## What this PR produces (autonomous scope)

**Doc only**. Spec landed + brainstorm archive. Code execution gated to next PR:

- Operator can authorize execution autonomously (no plist/cron/secret changes)
- Execution scope ~1.5 days (single PR with 4 files: handler + tests + registration + doc)

## Brainstorm artifacts

Archive `docs/audits/2026-05-13-ticket-a2-spec-brainstorm/`:

- `00_briefing.md` — 4 candidates + reviewer questions
- `01_claude.md` — self-critique β@75%
- `02_gemini.md` — β + F1 CRITICAL on δ Law 3 violation
- `03_deepseek.md` — β + 5 risks
- `04_nb1.md` — β + self-correction on prior δ signal
- `05_synthesis.md` — unanimous β + risk table + sequencing decision

## Sources

1. `apps/crm-cell/crm_cell/hgt_publisher.py:43-160` (CrmHGTBridge async — merged PR #632)
2. `packages/cell-core/cell_core/hgt/publisher.py:33-49` (HGTPublisher.cell_name public property — merged PR #626)
3. `packages/cell-core/cell_core/hgt/domains.py:18` (`"crm"` in CANONICAL_DOMAINS since commit `09aadbdc5`)
4. `apps/backend-rag/backend/services/events/handlers/compliance_handlers.py` (canonical handler pattern)
5. `apps/backend-rag/backend/services/events/event_bus.py:54` (PG_CHANNEL_MAP entries)
6. `apps/backend-rag/backend/services/crm/practice_status_listener.py:6` (migration_075 trigger reference)
7. `SYMBIOSIS.md:180` (Law 3 "Nessun polling" — Gemini F1)
8. `redis-cli XLEN cell:skills` → 18 (unchanged seed)
9. Phase 3 spec v2: `docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md`
10. TICKET A.1 narrow spec v2: `research/symbiosis/2026-05-12-ticket-a1-narrow-spec.md`
11. 4-panel brainstorm artifacts: `/tmp/symbiosis-ticket-a2-brainstorm-2026-05-12/` + `docs/audits/2026-05-13-ticket-a2-spec-brainstorm/`
12. TICKET A.0 merge: PR #626 → main `6e92046d8` at 2026-05-12T15:19:56Z
13. TICKET A.1 merge: PR #632 → main `84953041b` at 2026-05-13T00:03:12Z
