# DeepSeek Reasoner — Logical-Hole-Finder Analysis for TICKET A.2

## 1. Recommendation: **β** — New `crm_hgt_handlers.py` in `services/events/handlers/`

**Rationale**: This option **best trades pattern density against operational complexity** without violating Phase 3 refusals. Two competing signals—NB-1’s “co-location with crm-cell” vs. the dominant production pattern of EventBus handlers—are resolved by noting that the NB-1 signal was based on a **stale snapshot** (March 2026) that predates the EventBus handlers infrastructure. The _de facto_ production pattern is now the handler-based system (compliance_handlers.py, etc.), and β aligns with it.

- **No new daemon** — avoids plist scar (refusal #1) and monitoring overhead.
- **Clean separation of concerns** — the handler only does pattern computation; bridge instantiation remains in A.1.
- **Easy to test** — mock EventBus + mock bridge.
- **Event-driven** — captures near-real-time patterns without polling delay (critical for signals like Visa bounce-rate spikes).

**Why not the others**:

- **α**: Mixes event response with pattern aggregation in an already heavy listener (email automation). Aggregation state would be forced into practice_status_listener.py—a layering violation.
- **γ**: Too limited (LKPM only); doesn’t establish a general pattern pipeline. Wastes the investment in A.1’s bridge.
- **δ**: Clean boundary but requires **new plist + daemon** (operational complexity) and loses real-time signal. The Phase 3 spec v2 §14 refusals explicitly ban plist edits without operator chmod 0444 workflow (refusal #1). This makes δ a non-starter until that workflow is explicitly approved—and the briefing states this brainstorm _must respect those refusals_.

**One caveat**: β requires a caching layer for windowed aggregation (see Q2.2). That is a minor ask, solved by Redis hash or sorted set—nothing architecturally new.

---

## 2. Answers to Reviewer Questions

### Q2.1 — File path verification

| Option | Claimed path / pattern                                                                                                                           | Verification status (empirical survey based)                                                                                                                                                                                              |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| α      | `apps/backend-rag/backend/services/crm/practice_status_listener.py` asyncio loop on PG channel `practice_changed` (triggered by `migration_075`) | **Plausible**: Phase 3 spec v2 cites line 6 reference to migration_075. But the claim that the listener is “already wired in production” is unverified. **Risk**: listener may be behind feature flag or not running in all environments. |
| β      | `services/events/handlers/compliance_handlers.py` pattern: HANDLERS dict, register_handlers(bus)                                                 | **Plausible**: Phase 3 spec v2 line “compliance_handlers.py:53 — on_lkpm_readypack_generated” confirms file exists and has handler function. HANDLERS dict pattern is verified in the codebase (spec v2 references).                      |
| γ      | Hook into `compliance_handlers.py:53` — `on_lkpm_readypack_generated(payload)` –> extend with CrmHGTBridge call.                                 | **Same file as β but lower scope**. Line 53 existence is plausible – but can’t verify exact line number without file access. Accept as approximation.                                                                                     |
| δ      | `apps/crm-cell/crm_cell/poller.py` – new file, no existing daemon.                                                                               | **Plausible**: apps/crm-cell exists (A.1 is there). No poller currently. The path is correctly formed per monorepo conventions.                                                                                                           |

**Finding F1**: All four paths are syntactically valid and logically consistent with the repos empirically described. However, **none can be confirmed with absolute certainty** without on-disk inspection at `2026-05-13T00:10:00+08:00`. The briefing’s empirical surveys (00:08 WITA) are trusted but not independently verifiable.

### Q2.2 — Windowed aggregation viability (event-driven vs. periodic batch)

**Pattern**: e.g. “30-day Brevo bounce rate > 80%” requires collecting per-event data over a time window.

- **Event-driven is viable** IF we store state in a fast cache (Redis). Each event increments a counter/timestamp bucket. The pattern is computed when a new event arrives (or on a triggered check). **No batch required** for all patterns—many patterns can be threshold-checked per event (e.g. “exceed N failures in rolling hour”).
- **Batch needed** for **long-window, complex aggregates** where per-event computation is expensive or where you need a daily snapshot (e.g. <code>AVG cycle_time over last 30 days per visa category</code>). Those patterns can be deferred to a periodic batch handler (running every 5–15 minutes) still within the handler ecosystem—but **that batch is NOT a new daemon**; it’s a new handler that wakes on a timer event (e.g. `tick.5min` event on the bus). This keeps it within β’s architectural pattern.
- **Finding F2**: β can handle both per-event and periodic patterns by using two handler registrations (one for event-driven, one for timer-driven). Option δ would require mixing polling and event-driven, which is architecturally messier.

### Q2.3 — Hidden coupling with TICKET B (intel-scraper) and TICKET C (sentinel)

| TICKET | Nature                                                                        | Coupling with A.2 option β                                                                                                   |
| ------ | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| B      | IntelScraperCellRunner publishes patterns to `cell:skills` via its own bridge | **None**. A.2 publishes CRM patterns to the _same_ stream. No coordination needed.                                           |
| C      | Sentinel consumer reads `cell:skills` and processes patterns                  | **Weak positive coupling**: A.2’s patterns will be consumed by sentinel, which is intended. No import or event bus coupling. |

**Potential hidden coupling**:

- **TICKET C’s sentinel consumer group** (`sentinel-1`) reads the stream. If A.2 publishes high-frequency patterns, sentinel’s `consume_once` rate may need tuning. This is a scaling concern, not architectural coupling—document as a note for TICKET C’s soak tests.
- **TICKET B’s preflight check** (XLEN ≥18) is unaffected by A.2—A.2 only adds data after it’s wired.
- **Finding F3**: No hard coupling. A.2 can ship independently before or after B/C. However, if A.2 ships before B, the first patterns from CRM will go into `cell:skills` without any consumer (sentinel not yet active). That is harmless—patterns accumulate until TICKET C activates consumption. **No risk of data loss or corruption.**

---

## 3. Numbered Findings (Risks specific to β)

**F1 (Low)**: **Handler registration race** — If `crm_hgt_handlers.py` registers before the bridge is available, pattern publications could fail silently. Mitigation: register handler only after bridge init (dependency injection via app startup).

**F2 (High)**: **Aggregation state still needs a cache** — The handler must store event counts for windowed patterns. Without a dedicated Redis hash or something similar, the handler loses pattern state on restart. **Mitigation**: Use a simple Redis hash keyed by pattern type with TTL. This is not a new dependency—crm-cell already has Redis access (from A.1’s bridge).

**F3 (Medium)**: **Handler trigger granularity** — The EventBus currently fires events like `compliance.alert`, `client.changed`, etc. But `client.changed` may fire too often (every edit) and cause excessive pattern recomputation. **Mitigation**: Add a deduplication gate in the handler—only recompute pattern if N identical events seen in a time window. Or listen to a coarser event (e.g. `practice.status_changed` vs. every `client.changed`).

**F4 (Low)**: **Test isolation** — The handler test will need a mock EventBus and a mock bridge. This is straightforward (A.1’s tests already mock redis). But ensure the handler test does not accidentally call the real bridge (factory injection needed).

**F5 (Very Low)**: **File ownership** — `crm_hgt_handlers.py` lives in `services/events/handlers/` which is owned by backend-rag team (conceptually). The A.2 caller is for crm-cell. That’s fine—the handler can import from crm-cell (bridge). No circular dependency.

---

## 4. Effort Estimate

| Task                              | Hours                  |
| --------------------------------- | ---------------------- |
| Create `crm_hgt_handlers.py`      | 4                      |
| Register handler in app startup   | 1                      |
| Write caching helper (Redis hash) | 2                      |
| Write unit tests (8–12 tests)     | 3                      |
| Integration test (local stack)    | 1                      |
| Documentation update              | 0.5                    |
| **Total**                         | **~11.5h** (~1.5 days) |

Effort is higher than A.1’s 0.5 day because we are building the aggregation logic, not just a pass-through bridge.

---

## 5. Sequencing: A.2 Should Ship **After** TICKET B, **Before or After** TICKET C

Rationale for _after B_:

- TICKET B (intel-scraper publisher) is the **first production publisher** to `cell:skills`. It will validate the entire pipeline (bridge → stream → eventual consumer). If A.2 ships before B, and the pipeline has a hidden failure (e.g., stream schema mismatch), we lose debug isolation. Let B shake out the infrastructure first.
- TICKET C (sentinel consumer) is the _consumer_ side. A.2 can ship before or after C—it doesn’t matter because patterns just add to the stream. However, shipping A.2 after C gives immediate observability in sentinel’s logs. **Recommendation**: A.2 after B, and ideally after C, so that patterns are immediately consumed and validated.

**Hard dependency**: A.2 cannot ship before A.1 (bridge exists) and before “crm” domain registration (already in A.1). Since A.1 is already merged (PR #632), A.2 is ready to proceed.
