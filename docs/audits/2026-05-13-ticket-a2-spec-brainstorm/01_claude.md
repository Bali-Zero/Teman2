# Claude Opus 4.7 max — Self-brainstorm TICKET A.2 caller location

**Date**: 2026-05-13 00:12 WITA
**Method**: deliberate weighing of 4 options against architectural fit, operational complexity, and prior NB-1 signal.

## My recommendation: **Option β** (new `crm_hgt_handlers.py` in `services/events/handlers/`)

### Rationale (3 reasons, ordered by weight)

1. **Canonical pattern dominance** (architectural weight: heavy). The empirical reading of `services/events/handlers/compliance_handlers.py` shows the production pattern is:
   - Dotted event types (`compliance.alert`, `intel.event`, `lkpm.ingest_completed`)
   - Handlers as async functions accepting `payload: dict[str, Any]`
   - `HANDLERS` module dict mapping event_type → coroutine
   - Single `register_handlers(bus)` call wires all

   This is **already wired in production** via `_background_init` (per the `__init__.py` historical note). Option β adds 1 new file following this pattern verbatim. Zero new infrastructure. New cell-cross-cutting concerns (CRM pattern detection) belong here, not in CRM-internal listener loops.

2. **Operational complexity ZERO** (operational weight: heavy). Option δ requires a new plist, new daemon, new monitoring, plist corruption antibody handling, restart-on-crash policy. Option β reuses an already-running asyncio task in the FastAPI app process.

3. **Aggregation state is solvable inside β**. Patterns like "30d Brevo bounce rate" need windowed state. β can:
   - Read from Redis Streams via XRANGE (existing infra)
   - Cache aggregates in `cache_manager.py` (existing namespace `zantara:crm_*`)
   - Query DB on-demand (FastAPI app already has pool)

   This is **not harder** in β than in δ — both need the same caching/query infra.

### Rejecting Options α, γ, δ

**Option α** (enhance practice_status_listener.py): mixes concerns. The listener's responsibility is "react to status transition → fire email". Adding pattern aggregation means double-duty in a hot path. Failure mode: a pattern-emit exception could kill the email flow. Listener already has heavy logic (M4 + M5 dispatch).

**Option γ** (extend on_lkpm_readypack_generated): too narrow. Only LKPM patterns. Other CRM signals (visa state, Brevo bounces) need additional handlers anyway, so γ becomes "a poor man's β". Skip the half-measure and go straight to β.

**Option δ** (crm-cell internal poller): NB-1 useful signal recommended this for "cell boundary clean" reasons. But:

- NB-1 snapshot is 2026-03-23 → predates the establishment of `services/events/handlers/` as the canonical CRM-cross-cutting hook location.
- Polling loses real-time signal (a status transition fires now; poll picks it up minutes later).
- Adds operational complexity (plist + monitoring + restart) for marginal architectural benefit.
- The "cell boundary" argument matters more for **scar recording** and **event bridging** (which crm-cell already does in-process via FastAPI cycle). HGT publish is naturally a **handler reaction**, not an internal poller responsibility.

NB-1 wasn't wrong, just incomplete: it weighted architectural cleanliness over operational complexity. β achieves both — handlers live in backend-rag (where the FastAPI app runs) but they call into `crm_cell.CrmHGTBridge` (the cell-owned production-ready bridge), which preserves the cell boundary via the **publisher import**, not via physical separation.

## Caveats for spec v2 (corrections I want before shipping)

### CAV-1: Aggregation cadence

Patterns like "Brevo template T123 bounces ≥80% over 30d" need windowed data. The handler fires per-event (e.g. per Brevo webhook), but aggregation requires reading history.

**Decision**: handler **does NOT recompute on every event**. It only triggers a recomputation when a threshold of new events arrives (e.g. every 50 new Brevo events for that template, or once per hour with a debounce). Use Redis ZADD with timestamp + ZREMRANGEBYSCORE for sliding window state.

Spec v2 must specify:

- Window size per pattern type (LKPM: 90d, Brevo: 30d, practice transitions: 7d)
- Debounce interval (avoid recomputation on every event)
- Cache TTL alignment with window size

### CAV-2: Initial pattern catalog

What patterns does crm-cell actually publish? Phase 3 spec v2 mentions Brevo + practice transitions + CRM activity. A.2 spec needs to enumerate:

1. **brevo.template_bounce_rate** — confidence threshold per N samples
2. **practice.stage_cycle_time** — visa-c1 stage X→Y average days, by status path
3. **lkpm.ingestion_success_rate** — per company segment

Each pattern needs: `pattern_id` naming convention, aggregation query SQL/Redis, confidence formula, threshold for publish (above 0.7 floor).

### CAV-3: Event type subscription

Which EventBus dotted types does `crm_hgt_handlers.py` subscribe to?

From compliance_handlers.py HANDLERS dict + event_bus.py PG_CHANNEL_MAP:

- `practice.status_changed` (from practice_changed)
- `client.changed` (from client_changed)
- `lkpm.ingest_completed` (already used by compliance, will need careful coexistence)
- New event type `brevo.template_event` (NOT YET in PG_CHANNEL_MAP — needs migration)

If new event types are needed, A.2 scope balloons (new migration + new pg_notify triggers). Tight scope option: subscribe only to existing events for v1, expand later.

### CAV-4: Coupling with TICKET B/C

- TICKET B (intel-scraper-cell runner): independent. No coupling.
- TICKET C (sentinel cell-aware entry): independent. No coupling — TICKET C is the **consumer** side. A.2 is publisher side. They communicate via cell:skills Redis stream, decoupled.

## Effort estimate

| Sub-task                                                | Effort          |
| ------------------------------------------------------- | --------------- |
| Spec v2 (post 4-panel)                                  | 1h              |
| Pattern catalog (3 initial patterns)                    | 1h              |
| crm_hgt_handlers.py implementation                      | 4h              |
| Aggregation state (Redis sliding window)                | 2h              |
| Unit tests (12-15 tests)                                | 3h              |
| Integration test (events → handler → CrmHGTBridge xadd) | 2h              |
| Registration in setup/service_initializer.py            | 30m             |
| **Total A.2**                                           | **~1.5-2 days** |

## Sequencing

**A.2 ships AFTER A.1 (done) but BEFORE TICKET B/C**.

Rationale:

- A.2 + B together create publisher-side load on cell:skills (intel-scraper-cell + crm-cell both publishing)
- C consumes cell:skills via sentinel-1 consumer-group
- If C ships first, no entries to consume; idle consumer group
- If A.2 ships before B: only crm-cell publishing. Sentinel-1 (when C ships) can validate consumer pipeline with crm-cell entries only.

But pragmatically, A.2 is the largest remaining piece of work in Phase 3 (~1.5-2 days). B+C combined are ~3 days. Ordering for total time-to-FASE-4 is fungible — operator decides.

## What I want from the 3 external reviewers

- **Gemini Q1.1**: validate β recommendation OR argue for δ with new framing.
- **Gemini Q1.2**: cadence (per-event vs windowed batch) — design choice for spec v2.
- **DeepSeek Q2.2**: verify aggregation state can be event-driven (or argue for batch).
- **DeepSeek Q2.3**: hidden coupling with B/C that I might have missed.
- **NB-1 Q3.1**: ground-truth verification that compliance_handlers.py pattern was canonical as of March 23.
- **NB-1 Q3.3**: walk back or reaffirm the δ co-location signal.

## Confidence

**75%** β is the right answer. The 25% uncertainty is around:

- Aggregation cadence (might benefit from a hybrid: handler for events + periodic batch in same module)
- Whether NB-1 has new data suggesting δ is genuinely better despite operational cost

Will update after 3 external reviewers land.
