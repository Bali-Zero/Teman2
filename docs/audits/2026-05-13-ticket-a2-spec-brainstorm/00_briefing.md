# TICKET A.2 Caller Decision — 4-LLM Brainstorm Briefing

**Date**: 2026-05-13 00:10 WITA
**Predecessor**: TICKET A.1 EXECUTION merged (PR #632 → main `84953041b` at 00:03 WITA)
**Mode**: Operator-gated decision — narrow brainstorm to recommend caller location
**Empirical survey**: 2026-05-13 00:08 WITA

## Question to answer

**Where in the codebase should CrmHGTBridge.publish() be called from?**

CrmHGTBridge accepts a `StructuralPattern(pattern_id, procedure, precondition, success_criterion, confidence, domain)` and broadcasts to `cell:skills` Redis stream. The bridge is production-ready but has no production caller (Phase 3 spec v2 refusal #2 — operator decides).

## 4 candidate locations (empirical refresh)

### Option α — Enhance `practice_status_listener.py`

**Existing**: `apps/backend-rag/backend/services/crm/practice_status_listener.py` (asyncio LISTEN on PG channel `practice_changed`, dispatched via `migration_075` trigger on status/payment_status transitions).

**Pattern**: Add HGT publish call inside the listener loop. When N consecutive practices transition through same path within window → publish pattern like `practice_visa_c1_avg_cycle_4d`.

**Pros**:

- Listener already wired in production (line 6 reference migration_075).
- Reuses existing asyncio loop, no new daemon.
- Direct access to status transition data (the most pattern-rich CRM signal).

**Cons**:

- Mixes "respond to event" (current responsibility) with "aggregate patterns" (new).
- Listener already has heavy email automation logic (M4 + M5).
- Aggregation requires state across events → caching layer needed.

### Option β — New `crm_hgt_handlers.py` in `services/events/handlers/`

**Existing canonical**: `services/events/handlers/compliance_handlers.py` follows the pattern:

- Each handler subscribes to dotted event type (e.g. `compliance.alert`)
- Registered via `HANDLERS` dict + `register_handlers(bus)`
- Currently handles `compliance.alert`, `compliance.alert_outcome`, `intel.event`, `lkpm.ingest_completed`

**Pattern**: New `crm_hgt_handlers.py` subscribes to CRM events (`practice.status_changed`, `client.changed`, `lkpm.ingest_completed`), computes patterns via aggregation, publishes via CrmHGTBridge.

**Pros**:

- **Matches canonical pattern verbatim** (Gemini and Claude self both prefer canonical pattern).
- Clean separation of concerns: handler does pattern logic only.
- Easy to test in isolation (mock EventBus + mock bridge).
- Bridge instantiated once at startup via dependency injection.

**Cons**:

- Aggregation across events still needs state (Redis cache or DB query).
- New file means 1 more PR + tests.

### Option γ — Hook into `on_lkpm_readypack_generated`

**Existing**: `compliance_handlers.py:53` — `on_lkpm_readypack_generated(payload)` logs `client_id/period/drive_url` after `lkpm.ingest_completed`.

**Pattern**: Extend this handler to compute LKPM-specific structural patterns (e.g. "Q3 LKPM ingestion success rate >95% for company segment X").

**Pros**:

- Smallest code delta (1 file edit, no new imports beyond CrmHGTBridge).
- LKPM data is structured and high-signal (compliance reports → patterns trivial to extract).
- Already in the canonical handlers location.

**Cons**:

- Limited scope — only LKPM patterns. Other CRM signals (visa progress, Brevo bounces) ignored.
- Doesn't establish the broader handler pattern, just bolts onto existing one.

### Option δ — New crm-cell internal poller

**Existing**: `apps/crm-cell/` has scar_recorder, event_bridge, hgt_publisher (now CrmHGTBridge), but no main daemon. NB-1 useful signal (from Phase 3 v2 brainstorm) recommends co-location with crm-cell to keep cell boundary clean.

**Pattern**: New `apps/crm-cell/crm_cell/poller.py` runs every N minutes, queries CRM DB for structural metrics, publishes patterns via CrmHGTBridge.

**Pros**:

- Architecturally cleanest — cell boundary preserved (NB-1 signal).
- Independent cadence (not tied to event flow timing).
- Future-proof for Phase 4 unified base class refactor (Option δ from Phase 3 spec).

**Cons**:

- **NEW daemon/cron** — operational complexity (plist setup, monitoring, restart).
- Polling vs event-driven loses real-time signal.
- More code (new file + tests + plist).

## Architectural decision factors

1. **Pattern density vs operational complexity**: Option β provides pattern density via events without new daemon. Option δ is cleanest but adds plist scar (chmod 0444 antibody).

2. **Reuse of existing handlers infrastructure**: Options β + γ leverage the EventBus + handlers pattern already in production. α reuses listener but mixes concerns. δ stands alone.

3. **Aggregation state**: Patterns like "bounce rate X% over 30d" need windowed state. Options α/β/γ need Redis or DB cache. Option δ can hit DB directly each poll cycle.

4. **NB-1 useful signal** (from Phase 3 v2 brainstorm): caller architecture should "prefer co-location with crm-cell (not backend-rag) to keep cell boundary clean". This nudges toward δ.

5. **Gemini Q1.1/Q1.2** (from TICKET A.1 narrow spec v2 review): emphasized canonical schema and shape consistency. Doesn't argue for or against location.

## Refusals already in force (Phase 3 spec v2 §14)

This brainstorm + future A.2 spec MUST respect:

- ❌ No plist edits without operator chmod 0444 workflow
- ❌ No changes to `apps/backend-rag/backend/app/dependencies.py` (SPOF guard)
- ❌ No edits to `packages/cell-core/cell_core/hgt/*` (TICKET A.0 only)
- ❌ No synchronous `asyncio.run` in HGT app code
- ❌ Operator approves caller choice before any code lands

## Reviewer questions

### For Gemini 3.1 Pro (architectural)

- Q1.1: Best option among α/β/γ/δ for production caller location?
- Q1.2: If β chosen, what aggregation cadence makes sense (per-event vs windowed batch every 5 min)?
- Q1.3: Should multiple options coexist (e.g. β for events + δ for periodic patterns), or pick one?

### For DeepSeek Reasoner (logical)

- Q2.1: Verify the 4 candidate file paths cited (practice_status_listener.py, compliance_handlers.py, lkpm.py, apps/crm-cell/).
- Q2.2: For windowed aggregation patterns (e.g. "30d bounce rate"), is event-driven viable or does it require periodic batch?
- Q2.3: Identify hidden coupling between any option and not-yet-shipped TICKET B (intel-scraper) or TICKET C (sentinel).

### For NB-1 (with stale snapshot caveat)

- Q3.1: ⚠️ NB-1 snapshot 2026-03-23 predates apps/crm-cell. Skip crm-cell architecture; instead verify EventBus + compliance_handlers.py canonical pattern was already production as of March 23.
- Q3.2: Are there CRM signals from your indexed corpus that suggest one caller location over another (e.g. specific aggregation needs from production traffic)?
- Q3.3: NB-1 previous useful signal nudged toward δ co-location — does it still hold with the new empirical findings (canonical handlers pattern is the dominant production pattern, not internal pollers)?

## Verdict format requested

Each reviewer should output:

1. **Recommendation**: α / β / γ / δ + rationale
2. **Effort estimate**: hours/days for implementation
3. **Hidden risks** specific to chosen option
4. **Sequencing**: should A.2 ship before TICKETS B+C or after?

## References

- Phase 3 spec v2: `docs/superpowers/specs/2026-05-12-phase3-hgt-execution-spec.md`
- TICKET A.1 narrow spec v2 (merged PR #629): `research/symbiosis/2026-05-12-ticket-a1-narrow-spec.md`
- TICKET A.1 EXECUTION (merged PR #632): `apps/crm-cell/crm_cell/hgt_publisher.py` (CrmHGTBridge async)
- Canonical EventBus handler pattern: `apps/backend-rag/backend/services/events/handlers/compliance_handlers.py`
- Practice listener (Option α context): `apps/backend-rag/backend/services/crm/practice_status_listener.py`
- Brainstorm archive: `docs/audits/2026-05-12-phase3-spec-brainstorm/` + `docs/audits/2026-05-12-ticket-a1-spec-brainstorm/`
