# Exact implementation scope — future file list, lease list, migration note

**Nothing in this document was created or edited outside this bundle.** Every path below is
either (a) confirmed to already exist (read this session) or (b) explicitly marked NEW.

## 1. Migration numbering — corrected, and re-derive again before use

The dispatching session's prompt asserted `SESSION-BOARD.md`'s "272" figure was wrong and gave
287 as the real head with 282 missing. **Independently re-measured this session**, not accepted
on the prompt's word:

```
$ ls apps/backend-rag/backend/db/migrations_v2/ | grep -oE '^[0-9]+' | sort -n | tail -5
283
284
285
286
287
$ for n in 278 279 280 281 282 283 284 285 286 287; do ...; done
278: 278_reassign_orphaned_clients_setup_team.sql
279: 279_research_os_contract_core.sql
280: 280_research_os_objects_truncate_guard.sql
281: 281_garuda_voa_retention.sql
282: MISSING
283: 283_wa_reply_claims.sql
284: 284_garuda_orders.sql
285: 285_garuda_magic_link.sql
286: 286_garuda_voa_check_results.sql
287: 287_garuda_practices.sql
```

Confirmed: head is `287`, `282` is a genuine gap (not a counting error — "count the files" would
give a different, wrong answer than "max + 1"), and `272` (`272_wa_broker_package_text.sql`,
confirmed present, WhatsApp-broker-owned) is unrelated to this packet.

**This lane is forbidden from creating, editing, or applying any migration, by any number**
(dispatch prompt, explicit). The symbolic name reserved for this packet's eventual persistence
work is **`research_os_intel_lake_events`** (per the dispatching session's prompt). This
document does **not** bind an integer to that name. Whoever builds Packet 05 for real must
re-run the two commands above at that time — the head will have moved again by then, and
`282`'s gap is itself a fact that could theoretically close (a future PR could claim it) or
persist; neither this document nor any other should be trusted for that number later.

## 2. File ownership — packet's declared list, verified against disk

The packet's "File ownership" section (§ Primary monorepo ownership) names 8 items. Verified
presence this session:

| Packet-declared path | Exists today? | Notes |
|---|---|---|
| `apps/backend-rag/backend/services/intel/intel_lake_service.py` | yes, 260 lines | CONTRACT-MAP.md §1.1 |
| `apps/backend-rag/backend/services/intel/intel_lake_router.py` | yes, 549 lines | CONTRACT-MAP.md §1.1/§1.4 |
| `apps/backend-rag/backend/app/routers/intel_lake.py` | yes, 221 lines | CONTRACT-MAP.md §1.1 |
| "additive Intel Lake migrations and repositories" | migration `168` + later repairs (`171`,`174`,`192`) exist; no dedicated "repository" module exists yet (Intel Lake's persistence is inline in `intel_lake_service.py`, not a separate repository class like `IntelRepository` for dossiers) | any new repository class is NEW, not a rename |
| `scripts/intel-lake-outbox-drain/**` | yes, 3 files | CONTRACT-MAP.md §1.3 |
| `scripts/intel-lake-router-a2/**` | yes, 5 files | CONTRACT-MAP.md §1.4 |
| `scripts/intel-lake-nb-pusher-a2/**` | yes, 4 files | CONTRACT-MAP.md §3 |
| "Intel Lake probes and focused tests" | 4 files confirmed (below) | |
| "MATA GARUDA producer adapters and the specific bridge schema/consumer code required for canonical emission" | `apps/mata-garuda/mata_garuda/bridge/nerve.py` (consumer), `apps/mata-garuda/mata_garuda/agents/wr2_bridge_publisher.py` (the one producer this packet's mission specifically motivates — the broken bridge, CONTRACT-MAP.md §2.3) | scope note below |

Confirmed existing test files (packet says "and focused tests"):

```
apps/backend-rag/backend/tests/integration/test_intel_lake_e2e_probe_smoke.py
apps/backend-rag/backend/tests/db/test_migration_168_intel_lake.py
apps/backend-rag/backend/tests/unit/services/intel/test_intel_lake_router.py
apps/backend-rag/backend/tests/unit/services/intel/test_intel_lake_service.py
```

## 3. Exact future file list (NEW files an eventual build would create)

Derived from the packet's 9 deliverables + this bundle's gap analysis (CONTRACT-MAP.md §5,
METRICS-AND-GOLDEN-SET.md). Marked NEW where nothing by this name exists today (checked via
`find`/`ls` this session); this is a proposal for review, not a claim that these are the only
correct names.

```
apps/backend-rag/backend/services/intel/
  intel_event_adapter.py            NEW — maps intel_items/intel_observations rows to/from
                                     research_os.models.intel_event.IntelEvent (mirrors the
                                     existing action_intent_adapter.py pattern, confirmed present
                                     in apps/backend-rag/backend/services/research_os/)
  intel_lake_repository.py          NEW — extracts the inline SQL in intel_lake_service.py into
                                     a named repository, giving deliverable #1's producer
                                     registry and #8's replay tooling a stable seam to attach to
  story_cluster_dedup.py            NEW — the "preregistered deterministic dedup incumbent"
                                     (deliverable #3): exact/canonical-URL/hash/normalized layers
                                     ONLY at first; near/semantic stay separate per METRICS-AND-
                                     GOLDEN-SET.md §4
  story_cluster_repository.py       NEW — StoryCluster persistence (deliverable #4): canonical
                                     item, member relation, independent-source groups, decision
                                     trace, reversible split/merge

apps/backend-rag/backend/db/migrations_v2/
  <NNN>_research_os_intel_lake_events.sql   NEW, symbolic name only (§1) — adds
                                     classification.sensitivity-equivalent columns Intel Lake
                                     lacks today (PROTECTED-DATA-BOUNDARY.md §3), idempotency_key,
                                     lineage columns. Additive per repo migration convention
                                     (rollback section mandatory, per apps/backend-rag/CLAUDE.md's
                                     documented migration-runner rollback-stripping behavior).

apps/mata-garuda/mata_garuda/bridge/
  nerve.py                          TOUCHED — add "intel.research_dossier" (and any other
                                     currently-unrouted type) to a dead-letter path instead of
                                     ACK-drop (deliverable #5); PUSH_ROUTING dict itself likely
                                     gains one more entry once the canonical NB feed exists
  dead_letter.py                    NEW — the shared consumer-contract module both nerve.py's
                                     push_once() and workers/gap_consumer.py's process_gap() can
                                     import, so the fix lands once, not twice (CONTRACT-MAP.md §2.3
                                     names both call sites as sharing one defect shape)

apps/mata-garuda/mata_garuda/workers/
  gap_consumer.py                   TOUCHED — same dead-letter fix as nerve.py, via the shared
                                     module above

scripts/intel-lake-nb-pusher-a2/ AND apps/mata-garuda/scripts/run_nlm_feeder_stream.py
                                   BOTH TOUCHED (not retired — explicit non-goal) — add a shared
                                     dedup receipt so deliverable #6's "old and canonical feeds
                                     reconcile within a declared tolerance" is measurable; the
                                     exact receipt schema is a design task for the real build, not
                                     specified here

apps/backend-rag/backend/tests/unit/services/intel/
  test_intel_event_adapter.py       NEW
  test_story_cluster_dedup.py       NEW — must exercise the golden-set strata in
                                     METRICS-AND-GOLDEN-SET.md §3.1, once that set exists
  test_intel_lake_idempotency.py    NEW — packet's required test "idempotency and unique-key
                                     races"
  test_intel_lake_replay.py         NEW — required tests "transaction/outbox crash between write
                                     and deliver", "replay after partial delivery"

apps/mata-garuda/tests/
  test_bridge_dead_letter.py        NEW — required test "consumer retry and dead-letter
                                     behavior", "unknown event type" — covers both nerve.py and
                                     gap_consumer.py via the shared module
```

**Explicitly NOT in this list, per the packet's non-goals**: no new message-broker install
(Kafka/Pulsar), no graph-database promotion of Intel Lake, no retirement of any existing
producer/feed/bridge file, no publishing/rendering code path.

## 4. Lease list (for the hot-zone pre-commit gate, `docs/runbooks/redis-lease-registry.md`)

Files in the future list above that fall under this repo's documented hot-zone categories
(migrations, auth/billing/pricing, `.github/workflows/`, sentinel/DLQ scripts — per root
`CLAUDE.md` §7's `pre-commit lease-check` description) and would need an `agent_lock:<resource>`
lease held for the duration of real implementation work, so a concurrent lane does not collide:

```
apps/backend-rag/backend/db/migrations_v2/<NNN>_research_os_intel_lake_events.sql   (migration)
apps/mata-garuda/mata_garuda/bridge/nerve.py                                        (dead-letter/
                                                                                       sentinel-adjacent)
apps/mata-garuda/mata_garuda/bridge/dead_letter.py                                  (new, same class)
apps/mata-garuda/mata_garuda/workers/gap_consumer.py                                (DLQ-adjacent)
```

Everything else in the future-file list (adapters, repositories, tests, the two feeder scripts)
is not currently declared as hot-zone by the lease-check hook's own criteria and would rely on
ordinary worktree isolation (`scripts/agent_start.py`) rather than an explicit Redis lease — this
bundle does not recommend widening the hot-zone declaration; that is a call for whoever owns the
lease-check hook, not this lane.

## 5. Packet's 9-step implementation sequence, re-expressed against files that exist today

1. "Reconcile authoritative production topology and freeze a producer/consumer map" — this
   bundle (CONTRACT-MAP.md) is a first pass at this step, built without live DB access
   (UNKNOWNS.md §1); the real freeze needs the live counts this session could not obtain.
2. "Add canonical adapters and validation with feature flags off" — `intel_event_adapter.py`,
   `story_cluster_repository.py` (both NEW, §3), flag-gated per this repo's existing feature-flag
   convention (not inventoried in this session; whoever builds this should locate the repo's
   standard flag mechanism before inventing a new one).
3. "Introduce durable idempotency constraints and dead-letter handling" — the
   `identity.idempotency_key` gap (CONTRACT-MAP.md §5.1) plus the `dead_letter.py` module (§3).
4. "Build the labeled dedup/story-cluster golden set before semantic clustering" —
   METRICS-AND-GOLDEN-SET.md §3, not yet built.
5. "Run exact and deterministic layers, then benchmark near/semantic candidates" —
   `story_cluster_dedup.py` (§3), against the `MetricProfile` in METRICS-AND-GOLDEN-SET.md §2.
6. "Shadow MATA-to-Lake emissions and reconcile counts/hashes" — needs the shared dedup-receipt
   schema from §3's feeder-reconciliation item, not yet designed.
7. "Shadow the single NB feed while retaining the old feeds" — both existing feeders (§3)
   instrumented, neither retired.
8. "Replay a bounded historical window and compare canonical story/source counts" — needs
   `test_intel_lake_replay.py` (§3) and, per the packet's own metric, needs live counts this
   session could not obtain (UNKNOWNS.md §1) — flagged as a hard dependency for the real build,
   not something this bundle can pre-stage.
9. "Emit candidate DecisionPackets only after contract validation" — out of scope for the
   preparation bundle; the `DecisionPacket` frozen model exists in the 25-model list
   (CONTRACT-MAP.md §5) but was not read line-by-line this session (UNKNOWNS.md).
