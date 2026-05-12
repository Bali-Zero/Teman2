# TICKET A.2 — 4-Panel Brainstorm Synthesis

**Date**: 2026-05-13 00:15 WITA
**Inputs**: 4 reviews (Claude self + Gemini + DeepSeek + NB-1)

## Verdicts table — UNANIMOUS

| Reviewer                         | Recommendation         | Effort            | Sequencing                      |
| -------------------------------- | ---------------------- | ----------------- | ------------------------------- |
| Claude self-critique             | **β** (75% confidence) | 1.5-2 days        | Before B/C                      |
| Gemini 3.1 Pro                   | **β**                  | 0.5-1 day         | Before B/C                      |
| DeepSeek Reasoner                | **β**                  | 1.5 days (~11.5h) | After B, before/after C         |
| NB-1 NotebookLM (stale snapshot) | **β**                  | 4-6 hours         | Independent (zero coupling B/C) |

**Aggregate: 4/4 UNANIMOUS on Option β** (new `services/events/handlers/crm_hgt_handlers.py`)

## Convergent rejection of α/γ/δ

**α (practice_status_listener.py enhance)** — rejected unanimously:

- Mixes concerns (Claude self, DeepSeek)
- Coupling with critical M4/M5 email automation (Gemini F2: HIGH severity)
- Listener already too heavy

**γ (extend on_lkpm_readypack_generated)** — rejected unanimously:

- Too narrow scope (LKPM only)
- SRP violation (NB-1: compliance ≠ HGT evolution domains)
- Wastes A.1 investment

**δ (crm-cell internal poller)** — rejected unanimously:

- **Gemini F1 CRITICAL**: violates SYMBIOSIS.md:180 Law 3 "Nessun polling, nessun orchestratore centrale"
- NB-1 self-corrected: previous "co-location" signal was based on stale snapshot, dominant production pattern is now handlers
- DeepSeek: violates Phase 3 spec v2 refusal #1 (no plist edits without operator chmod 0444 workflow)
- Claude self: operational complexity (plist + daemon + monitoring) outweighs architectural cleanliness

## NB-1 self-correction (notable)

NB-1's previous Phase 3 v2 brainstorm signal was "prefer co-location with crm-cell (Option δ)". In this brainstorm, NB-1 **reverses** the signal: _"apps/crm-cell/ è vaporware [in March 23 snapshot]... Inseguire il purismo architetturale cercando di iniettare codice in una cellula fantasma (Opzione δ) non genererà alcun valore"_.

This is the right empirical re-calibration:

- NB-1's March 23 snapshot doesn't have crm-cell, so δ requires "writing in vaporware"
- The handlers infrastructure (compliance_handlers.py) was already production-canonical on March 23 (NB-1 Q3.1: "SÌ, assolutamente")
- Even if crm-cell exists now (post March 23), the operational complexity argument from Claude self + Gemini critical Law 3 violation kill δ

## Key risks for Option β (synthesis of all 4)

| Risk                                                   | Source                                     | Severity | Mitigation                                                             |
| ------------------------------------------------------ | ------------------------------------------ | -------- | ---------------------------------------------------------------------- |
| Aggregation state requires Redis cache                 | Claude CAV-1, DeepSeek F2, Gemini Top 3 #1 | HIGH     | Use Redis hash/ZADD with TTL — existing infra                          |
| Event loop blocking from sync xadd                     | Gemini F3, Gemini Top 3 #2                 | MEDIUM   | Already mitigated — A.1 CrmHGTBridge.publish is `async def` (verified) |
| DB N+1 load if handler bypasses cache                  | Gemini Top 3 #3                            | MEDIUM   | Spec mandates Redis-first; DB query only on cache miss                 |
| Handler trigger granularity (client.changed too noisy) | DeepSeek F3                                | MEDIUM   | Subscribe coarser events (practice.status_changed) + dedup window      |
| Coupling with TICKET C consumer scaling                | DeepSeek (note)                            | LOW      | Document for C's soak tests                                            |
| File ownership ambiguity (handler imports crm-cell)    | DeepSeek F5                                | VERY LOW | Acceptable — handler is consumer of bridge                             |

## Sequencing decision

**Claude self + Gemini say**: A.2 before B/C  
**DeepSeek says**: A.2 after B (let B shake out pipeline first), before or after C  
**NB-1 says**: independent

**Recommendation**: **A.2 after B** (DeepSeek rationale wins). B is the first production publisher to cell:skills; let it validate the bridge → stream pipeline end-to-end before adding CRM patterns. If pipeline has hidden failure (schema mismatch, consumer choke), debug isolation is easier with single publisher.

Pragmatic order: **A.0 ✅ → A.1 ✅ → B → A.2 → C → 14d soak → FASE 4 lift**.

## Caveats (Claude self + DeepSeek concur)

### CAV-1: Aggregation cadence

Event-driven primary, with debounce/dedup window. NO polling. For long-window aggregates (30d bounce rate), use Redis sorted set ZADD timestamps + ZREMRANGEBYSCORE expiry. Compute on event arrival, not on cron tick.

### CAV-2: Initial pattern catalog

Spec v2 must enumerate:

1. `brevo.template_bounce_rate` — domain="crm", trigger=brevo webhook event (NEW event type needs PG_CHANNEL_MAP entry — defer to v2 spec)
2. `practice.stage_cycle_time` — domain="crm", trigger=practice.status_changed
3. `lkpm.ingestion_success_rate` — domain="crm", trigger=lkpm.ingest_completed (coexist with compliance handler)

### CAV-3: Event type subscriptions

Subscribe ONLY to existing PG_CHANNEL_MAP entries for v1:

- practice.status_changed
- client.changed (with dedup gate per DeepSeek F3)
- lkpm.ingest_completed (coexist with on_lkpm_readypack_generated — different handler key)

NEW event types (brevo.template_event) need separate PR with PG migration. Scope-bound A.2 to existing events.

### CAV-4: Effort calibration

- Gemini: 0.5-1 day (most optimistic)
- NB-1: 4-6h (uses A.1's existing bridge, low complexity)
- DeepSeek: 1.5 days (includes 2h caching + 3h tests)
- Claude self: 1.5-2 days (most conservative)

**Aggregate**: **1-1.5 days** realistic.

## Spec v2 recommendation

Write narrow A.2 spec with:

1. Option β confirmed via 4-panel unanimous
2. Pattern catalog (3 initial patterns from CAV-2)
3. Aggregation cadence (event-driven + Redis sliding window per CAV-1)
4. Subscription map (existing PG channels only per CAV-3)
5. Handler stub with HANDLERS dict + register_handlers integration
6. Tests: 8-12 unit + 1 integration
7. Effort: 1-1.5 days
8. Sequencing: ship AFTER TICKET B (DeepSeek rationale)

## Operator decision needed

Confirm β + sequencing **A.2 after B**? Or override:

- ship A.2 before B (Claude self/Gemini opinion)
- ship A.2 standalone (NB-1 opinion)
- skip A.2 for now (defer to Phase 4)

Once operator confirms, next session:

- Write A.2 narrow spec v1
- 4-panel review v1
- Apply corrections → v2
- PR + auto-merge
- EXECUTION

OR if operator says "go" — write spec v2 directly (skip review, given 4-panel already unanimous on architecture).
