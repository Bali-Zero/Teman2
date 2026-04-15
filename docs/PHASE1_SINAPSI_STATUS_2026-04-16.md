# Phase 1 — SINAPSI — Status audit (2026-04-16)

> Companion to `docs/superpowers/plans/2026-04-14-organism-phase1-sinapsi.md`.
> Verified against running production state on Pro + Fly.io at 2026-04-16 ~05:00 WITA.

## Summary (TL;DR)

**Phase 1 is ~90% delivered.** 15 of 16 tasks are in `main`, LaunchAgents are
loaded, Redis streams are live (`garuda:raw=463`, `nexus:gaps=828`), bridge
router registered on both light + heavy Fly paths.

Meanwhile Phase 3 (COSCIENZA) metrics shipped **parallel to this audit** —
PR #57 (commit `fce0b783a`) landed Metabolic Pillar 7 with 4 metabolic
metrics (TTR/DO/IA/FE) + Agentic RAG SOTA + HGT. The organism is not
moving strictly phase-by-phase; some late phases ship when their design is
cheap and their consumers exist. Phase 1 is still the structural floor and
has one deliverable missing.

The plan's sole remaining task not merged is **Task 16 — end-to-end
verification** (the plan expected an explicit `tests/test_phase1_e2e*` that
does not exist in the tree). Everything else is merged and running.

Two open gaps discovered during audit, not in the original plan:

1. **`LPSE harvester` never shipped.** The foundational organism doc
   (`docs/superpowers/plans/2026-04-14-mata-garuda-organism-prompt.md`) listed
   "2 harvester nuovi (LHKPN + LPSE) che chiudono il loop OSINT". LHKPN is
   live; LPSE was never started.

2. **`intel:articles` stream is empty** (0 entries). War Room has not yet
   been wired to publish through the bridge. The Intel→Content→SEO→Revenue
   cycle has no producer in production.

Also worth noting (ambient, not a gap of Phase 1):

- **Legacy streams use old format.** `garuda:raw` (463) and `nexus:gaps`
  (828) entries were written before the 5-field envelope existed. Plan
  said "not urgent, migrate when consumers rewritten". For `nexus:gaps`
  the new `gap_consumer.py` IS the consumer, so a `_coerce` helper is
  overdue — one hour of work.

## Per-task verification

Deliverables from `docs/superpowers/plans/2026-04-14-organism-phase1-sinapsi.md`,
cross-checked against files + git log + launchctl + redis-cli state.

| #  | Task                                         | Status | Evidence                                                                             |
| -- | -------------------------------------------- | ------ | ------------------------------------------------------------------------------------ |
| 1  | Bridge envelope model (Pydantic)             | ✅     | `apps/mata-garuda/mata_garuda/bridge/envelope.py`                                    |
| 2  | Bridge cursor (atomic file I/O)              | ✅     | `apps/mata-garuda/mata_garuda/bridge/cursor.py`                                      |
| 3  | Backend migration `bridge_outbox`            | ✅     | `apps/backend-rag/backend/migrations/migration_107_bridge_outbox.py` (renamed from `101` in the plan) |
| 4  | Backend `outbox` service helper              | ✅     | `apps/backend-rag/backend/services/bridge/outbox.py` + `retention.py` + `low_confidence_emitter.py` |
| 5  | Backend `bridge` router (3 endpoints)        | ✅     | `apps/backend-rag/backend/app/routers/bridge.py` — registered in both include_light + include_heavy |
| 6  | EventBus → outbox triggers                   | ✅     | `apps/backend-rag/backend/services/events/handlers.py` (grep 'outbox' matches)        |
| 7  | RAG low-confidence trigger                   | ✅     | `low_confidence_emitter.py` + streaming path wired (commits `c6fd58899`, `0df523a8c`) |
| 8  | MG config — bridge constants                 | ✅     | `apps/mata-garuda/mata_garuda/config.py` (commit `b256fc0f5`)                         |
| 9  | Bridge nerve — pull (Fly→Pro)                | ✅     | `apps/mata-garuda/mata_garuda/bridge/nerve.py` (pull_once, commit `c92580da1`)        |
| 10 | Bridge nerve — push (Pro→Fly)                | ✅     | `nerve.py` push_once + `bridge_main` (commit `c0e0b211f`)                             |
| 11 | Gap consumer worker                          | ✅     | `apps/mata-garuda/mata_garuda/workers/gap_consumer.py` (commit `04aa0b02e`)           |
| 12 | LHKPN scraper tools                          | ✅     | `apps/mata-garuda/mata_garuda/tools/lhkpn_tools.py` (commit `57e640e8c`)              |
| 13 | LHKPN harvester agent + GENOME               | ✅     | `apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py` + `_GENOME.md` (commit `cedad9d1f`) |
| 14 | Bridge LaunchAgent + shell wrapper           | ✅     | `~/Library/LaunchAgents/com.matagaruda.bridge.adaptive.plist` loaded (launchctl PID 40737) |
| 15 | Gap consumer LaunchAgent                     | ✅     | `com.matagaruda.gap.consumer.plist` loaded (launchctl present, PID 0 = idle)          |
| 16 | End-to-end verification (`test_phase1_e2e`)  | ❌     | No `test_phase1_e2e*` file in `apps/mata-garuda/tests/`. Plan expected it.            |

**Open items discovered outside the plan:**

| Scope                                          | Status | Note                                                                                  |
| ---------------------------------------------- | ------ | ------------------------------------------------------------------------------------- |
| 2nd harvester (**LPSE**, paired with LHKPN)    | ❌     | Mentioned in `mata-garuda-organism-prompt.md` as "LHKPN + LPSE". Only LHKPN shipped.   |
| Envelope migration of `garuda:raw` (463)       | ⚠️     | Legacy format, consumer is Normalizer (not rewritten yet). Plan says "not urgent".    |
| Envelope migration of `nexus:gaps` (828)       | ⚠️     | Legacy format BUT consumer IS the new `gap_consumer.py`. Coerce-on-read recommended.  |
| `intel:articles` stream (War Room producer)    | ❌     | 0 entries. Intel→Content→SEO→Revenue cycle has no producer yet.                       |
| Phase 1 metrics snapshot                       | ❌     | Plan required "before/after" numbers; no snapshot file committed.                     |

## Parallel work landing during this audit

Noted to avoid confusion next session — **these are NOT Phase 1, they're separate**:

- **PR #57** (`fce0b783a`, merged 2026-04-16 05:30 WITA) landed three large
  changes in parallel to our Phase 1 audit:
  - **Agentic RAG SOTA 2026** (6 components: Self-RAG, HyDE, reranker registry,
    CRAG, NLM orchestrator, deep research). All behind feature flags.
  - **Metabolic Pillar 7 v1** — 4 metrics (TTR / DO / IA / FE). These are
    the metrics `docs/superpowers/plans/2026-04-14-mata-garuda-organism-prompt.md`
    attributed to Phase 3. Pillar 7 shipping before Phase 2 means the
    organism is taking metrics as cross-phase infrastructure, not a
    phase-locked deliverable.
  - **HGT** (Horizontal Gene Transfer between cells).

Implication for Phase 1 closure: the P1-5 metrics snapshot (see below)
can piggyback on the new metric collectors — don't reinvent.

## Redis state (verified 2026-04-16)

```
garuda:raw        XLEN=463   (producer: harvesters, normalizer; consumer: normalizer → nexus)
nexus:gaps        XLEN=828   (producer: gap_detector 8 Cypher queries; consumer: gap_consumer.py)
intel:articles    XLEN=0     (producer: nobody — War Room not wired; consumer: bridge push)
```

The plan's before/after quoted `nexus:gaps=552` as "not consumed". It is now
consumed (gap_consumer runs on the LaunchAgent), but XLEN has grown to 828
— meaning the detector is outpacing the consumer, or entries are still in
the stream after being processed. **Verify whether `gap_consumer.py` XACK-s
or only reads.** If it doesn't ACK, we've not actually "closed the loop" —
we've just added a second reader.

## LaunchAgents loaded on Pro (2026-04-16)

```
com.matagaruda.bridge.adaptive    PID 40737   running
com.matagaruda.gap.consumer       PID 0       idle (expected: cron-triggered)
com.matagaruda.watcher.daily      PID 0       idle
com.matagaruda.sentinel.daily     PID 0       idle
com.garuda.consumer.daily         PID 0       idle
com.garuda.gap-detector.twice-daily
com.balizero.nlm-bridge           PID 56625   running (different bridge, pre-existing)
```

Also present: `com.garuda.gap-detector.twice-daily.plist.corrupted-20260412`
— a dead file from a failed schedule change. Safe to delete.

## What Phase 1 claims to deliver vs what's live

| Phase 1 "After" metric                          | Live on 2026-04-16                                                       |
| ----------------------------------------------- | ------------------------------------------------------------------------ |
| Bridge Pro↔Fly operational                      | ✅ adaptive bridge running, outbox populated via CRM+RAG handlers        |
| Envelope standard on all new streams            | ✅ for new streams. Legacy not migrated.                                 |
| Gap consumer consumes `nexus:gaps`              | ⚠️ LaunchAgent loaded, consumer exists, XACK semantics UNVERIFIED.       |
| 2 new harvesters (LHKPN + LPSE)                 | ⚠️ 1 of 2 (LHKPN only).                                                  |
| Intel scraper publishes to `intel:articles`     | ❌ stream is empty. Producer not wired.                                  |
| 4 cycles with ≥1 end-to-end signal              | ⚠️ Cycle 3 (Canali→KB→RAG) is wired via RAG low-confidence → outbox → bridge. Cycle 1 (Intel→Content→SEO→Revenue) has no producer. Cycles 2+4 not verified in this audit. |

## Residual work to close Phase 1

In priority order. Each item links back to the plan's deliverable list.

### P0 — blockers to declaring Phase 1 done

1. **LPSE harvester** (Task 13 companion). Add `tools/lpse_tools.py` +
   `agents/lpse_harvester.py` + `lpse_harvester_GENOME.md` mirroring the
   LHKPN structure.

2. **End-to-end test (Task 16).** `apps/mata-garuda/tests/test_phase1_e2e.py`
   covering pull cycle + push cycle + envelope validation.

3. **`intel:articles` producer.** Wire War Room so every completed article
   emits an envelope to `intel:articles`. Without this, the bridge push is
   exercised only in tests; the cycle Intel→Content→SEO→Revenue never
   actually moves a byte in production.

### P1 — cleanup that's cheap and useful

4. **Envelope coerce-on-read for `nexus:gaps`.** `gap_consumer.py` should
   accept both legacy and envelope formats.

5. **Phase 1 metrics snapshot.** Commit `docs/PHASE1_METRICS_2026-04-16.md`
   with before/after counts. Can piggyback on PR #57's new metric
   collectors (TTR/DO/IA/FE) — don't reinvent instrumentation.

6. **Delete `com.garuda.gap-detector.twice-daily.plist.corrupted-20260412`.**
   Housekeeping.

### P2 — stuff the plan did NOT ask for but is close by

7. **Phase 2 RIFLESSI plan exists.** `docs/superpowers/plans/2026-04-14-organism-phase2-riflessi.md`
   (4679 lines, 24 tasks, 129 steps) + matching design spec. This means
   the next sprint is already planned. Do NOT start Phase 2 work until
   P0 items above close — Phase 1 acts as the test harness for Phase 2.

## Files referenced (absolute paths, so they're clickable)

### Phase 1 plan + specs

- `/Users/nuzantara/Desktop/nuzantara/docs/superpowers/plans/2026-04-14-organism-phase1-sinapsi.md`
- `/Users/nuzantara/Desktop/nuzantara/docs/superpowers/specs/2026-04-14-curator-agent-garuda-design-v2.md`
- `/Users/nuzantara/Desktop/nuzantara/docs/superpowers/plans/2026-04-14-mata-garuda-organism-prompt.md` (foundational organism doc)

### Phase 2 plan (scaffolded, parked until Phase 1 closes)

- `/Users/nuzantara/Desktop/nuzantara/docs/superpowers/plans/2026-04-14-organism-phase2-riflessi.md`
- `/Users/nuzantara/Desktop/nuzantara/docs/superpowers/specs/2026-04-14-organism-phase2-riflessi-design.md`

### Bridge implementation (Phase 1 core)

- `/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/mata_garuda/bridge/envelope.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/mata_garuda/bridge/cursor.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/mata_garuda/bridge/nerve.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/mata_garuda/config.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/mata_garuda/workers/gap_consumer.py`

### Backend bridge (Fly side)

- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/app/routers/bridge.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/bridge/outbox.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/bridge/retention.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/bridge/low_confidence_emitter.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/events/handlers.py`
- `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/migrations/migration_107_bridge_outbox.py`

### Harvesters

- `/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/mata_garuda/agents/lhkpn_harvester.py` ✅ done
- `/Users/nuzantara/Desktop/nuzantara/apps/mata-garuda/mata_garuda/tools/lhkpn_tools.py` ✅ done
- `apps/mata-garuda/mata_garuda/agents/lpse_harvester.py` ❌ missing
- `apps/mata-garuda/mata_garuda/tools/lpse_tools.py` ❌ missing

### LaunchAgents (on Pro)

- `~/Library/LaunchAgents/com.matagaruda.bridge.adaptive.plist`
- `~/Library/LaunchAgents/com.matagaruda.gap.consumer.plist`

### Foundational reading (for any agent picking this up)

- `/Users/nuzantara/Desktop/nuzantara/SYMBIOSIS.md` — 7 laws, 8 pillars
- `/Users/nuzantara/Desktop/nuzantara/VADEMECUM.md` — operative checklists
- `/Users/nuzantara/Desktop/nuzantara/INDEX.md` — atlas of organs
- `/Users/nuzantara/Desktop/nuzantara/CLAUDE.md` — project context

---

_Audited 2026-04-16 by Claude Opus 4.6 against live state on Pro (Nuzantara host) + `git log main` state._
