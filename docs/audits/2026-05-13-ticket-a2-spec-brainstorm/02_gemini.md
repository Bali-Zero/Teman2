# TICKET A.2 Caller Decision Recommendation

## 1. Recommendation: Option β (New `crm_hgt_handlers.py` in `services/events/handlers/`)

**Rationale:** Option β is the only path that perfectly aligns with the established `backend-rag` EventBus pattern while maintaining strict adherence to SYMBIOSIS architectural mandates. It decouples pattern aggregation from operational side-effects (unlike Option α, which overloads the M4/M5 email listener) and avoids creating a new isolated daemon. Most importantly, Option δ (poller) is categorically disqualified because it violates the absolute mandate "Nessun polling" established in SYMBIOSIS Law 3 (`SYMBIOSIS.md:180`).

## 2. Answers to Reviewer Questions

- **Q1.1: Best option among α/β/γ/δ for production caller location?**
  Option β. It guarantees separation of concerns by isolating HGT logic in a dedicated handler and leverages the durable `events_outbox` architecture of the EventBus, satisfying SYMBIOSIS Law 3.
- **Q1.2: If β chosen, what aggregation cadence makes sense (per-event vs windowed batch every 5 min)?**
  Per-event with on-the-fly evaluation. Because scheduling a "batch every 5 min" implies polling/cron mechanics (violating Law 3), the handler must be purely reactive. When a CRM event fires, the handler updates a rolling state in Redis (e.g., sliding window counters) and evaluates if the threshold is met. If yes, it publishes the `StructuralPattern`.
- **Q1.3: Should multiple options coexist (e.g. β for events + δ for periodic patterns), or pick one?**
  Pick one (Option β). Introducing δ alongside β fractures the architecture and introduces a rogue polling daemon into an explicitly event-driven core. All temporal aggregations must be modeled as stateful reactions to incoming events.

## 3. Findings

1.  **F1: Option δ (Poller) explicitly violates SYMBIOSIS Law 3**
    - **Severity:** CRITICAL
    - **Evidence:** `SYMBIOSIS.md:180` ("3. Event-driven, durabilità per canale. Nessun polling, nessun orchestratore centrale.")
    - **Recommended Action:** Immediately discard Option δ and any polling-based daemon approaches for internal CRM event publication.
2.  **F2: Option α introduces dangerous coupling with critical M4/M5 automation**
    - **Severity:** HIGH
    - **Evidence:** `apps/backend-rag/backend/services/crm/practice_status_listener.py:112-250` (Dedicated listener loop heavily coupled with triggering critical client emails and handling internal HTTP API calls).
    - **Recommended Action:** Discard Option α. The EventBus pattern handles CRM events seamlessly via `practice.status_changed` subscriptions, as empirically verified in `apps/backend-rag/backend/services/crm/partners/events.py:44`.
3.  **F3: `CrmHGTPublisher` signature mismatch with Phase 3 Async mandate**
    - **Severity:** MEDIUM
    - **Evidence:** `apps/crm-cell/crm_cell/hgt_publisher.py:44` (`def publish(self, pattern: StructuralPattern) -> bool:`).
    - **Recommended Action:** The current file defines `publish` as a synchronous method. While acceptable as a stub, the Sprint 4 implementation must not block the event loop when executing Redis `XADD` operations. Ensure the final bridge implementation exposes an `async def` API, or run the sync method in a thread pool within the Option β handler.

## 4. Effort Estimate

**~0.5 to 1 day.**
Requires creating `services/events/handlers/crm_hgt_handlers.py`, registering it in `events.py` or the main handler registry, wiring the bridge dependency, and implementing Redis-backed state counters to handle windowed aggregations without polling.

## 5. Sequencing

**Before TICKETS B and C.**
A.2 relies on A.1 (domain registration and bridge implementation). Shipping A.2 concurrently with or just before TICKET B ensures that when TICKET C (Sentinel Consumer) ships, there are multiple publishers actively feeding `cell:skills`. This maximizes data availability for the Sentinel consumer group from day one and accelerates hitting the 14-day soak validation metric ("XLEN cell:skills >= 23").

## 6. Top 3 Risks for Option β

1.  **Distributed State Management:** Aggregating windowed patterns (e.g., "30d bounce rate") purely from discrete events requires robust, concurrent-safe state tracking in Redis to prevent race conditions during high event bursts.
2.  **Event Loop Blocking:** If the underlying publisher (`CrmHGTPublisher.publish`) performs blocking network I/O to Redis stream without an `await` (see Finding F3), it will stall the `backend-rag` asyncio EventBus loop, degrading the entire notification system.
3.  **Database N+1 Load:** If the event handler attempts to bypass Redis and queries the DB for historical context on _every_ status change event to compute aggregates, it could introduce severe database load spikes during batch CRM updates.
