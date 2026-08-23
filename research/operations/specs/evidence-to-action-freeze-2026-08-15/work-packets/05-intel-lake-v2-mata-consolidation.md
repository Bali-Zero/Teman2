---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 05 — Intel Lake v2 and MATA GARUDA Consolidation

**Wave:** 1
**Depends on:** Packet 04
**Unlocks:** Packets 08, 12, and 14
**Risk:** high data-routing risk; all cutovers begin in shadow mode

## Session prompt

You own the consolidation of the research ingestion spine. Intel Lake becomes the canonical ledger; MATA GARUDA becomes a producer/enricher family. Preserve the working collection capacity while removing parallel truth paths through adapters and measured cutovers.

You are not alone in the codebase. Use a dedicated worktree and list exact files before editing. Do not revert concurrent work. Migration `272` is reserved for this packet. Refresh the authoritative Pro head; if the central reservation is stale or occupied, stop and request a versioned ledger revision. Do not retire a bridge, queue, or feeder in this packet—that is Packet 16 after parity. Do not deploy or arm LaunchAgents without explicit approval.

## Mission

Make every public research observation enter Intel Lake once with provenance, idempotency, lineage, freshness, and replay-safe delivery, then produce reversible `StoryCluster` objects without mistaking syndication for independent corroboration.

## Live baseline to refresh

- Intel Lake is live in production with canonical items, observations, outbox, router, pusher, and probes.
- A dated audit found more than half of non-probe items in `needs_review`, no working Tier-2 enrichment path, and no actual WR2 destination.
- MATA GARUDA is live and high-volume, but it has parallel raw/enriched streams, duplicated NotebookLM feeding, and a broken WR2 research-dossier bridge whose consumer acknowledges unsupported message types.
- Some documented producer counts and DB observations disagree because a prior external audit queried a non-authoritative database. Pro production state is authoritative and must be remeasured.
- Trend-hunter dedup has been observed as run-local rather than durable across runs.

Capture current producer inventory, event counts, unique canonical URLs/hashes, review rate, duplicates, outbox pending/abandoned, consumer lag, unknown-message ACKs, NB submissions, and actual downstream consumers.

## File ownership

Primary monorepo ownership:

- `apps/backend-rag/backend/services/intel/intel_lake_service.py`
- `apps/backend-rag/backend/services/intel/intel_lake_router.py`
- `apps/backend-rag/backend/app/routers/intel_lake.py`
- additive Intel Lake migrations and repositories
- `scripts/intel-lake-outbox-drain/**`
- `scripts/intel-lake-router-a2/**`
- `scripts/intel-lake-nb-pusher-a2/**`
- Intel Lake probes and focused tests
- MATA GARUDA producer adapters and the specific bridge schema/consumer code required for canonical emission

Do not change NAGA claim truth, NEXUS graph promotion, WR2 composition, or public publishing. If MATA GARUDA lives in a separate runtime boundary, document and coordinate that boundary rather than copying data.

## Inputs and contracts

- Packet 04 `IntelEvent`, `StoryCluster`, `WorkflowRun`, and delivery receipts.
- Existing Intel Lake transaction/outbox semantics.
- Frozen sensitivity rules: protected OSINT/PII remain references in protected storage.
- Existing producer data must be mapped, never silently discarded.

## Deliverables

1. A verified producer registry: owner, source, schedule, event types, sensitivity, health, dedup keys, and downstream purpose.
2. MATA GARUDA adapter emitting validated `IntelEvent` objects to Intel Lake with stable idempotency keys.
3. A preregistered deterministic dedup incumbent—native identity, canonical URL, exact hash, and normalized rules—plus separately measured near/semantic challengers and human/LLM review only for the ambiguous band.
4. `StoryCluster` persistence with canonical item, member relation, independent-source groups, decision trace, and reversible split/merge.
5. Consumer contract that dead-letters unsupported types; unknown messages are never ACKed as success.
6. Exactly one canonical NotebookLM feed with explicit domain routing and dedup receipt; the old parallel feed remains shadowed until Packet 16.
7. Tier-2 enrichment implementation or an explicit removal of the fictional tier from live status and docs.
8. Replay and reconciliation tooling that proves no duplicate external side effects.
9. A candidate queue for the Conductor/Action Inbox—not a direct autonomous WR2 call.

## Non-goals

- Do not install Kafka, Pulsar, or a new lake.
- Do not turn Intel Lake into a claim ledger or graph database.
- Do not let an LLM be the only dedup decision-maker.
- Do not count syndicated copies as independent confirmation.
- Do not retire old producers/feeds yet.
- Do not publish or render content.

## Implementation sequence

1. Reconcile authoritative production topology and freeze a producer/consumer map.
2. Add canonical adapters and validation with feature flags off.
3. Introduce durable idempotency constraints and dead-letter handling.
4. Build the labeled dedup/story-cluster golden set before semantic clustering.
5. Run exact and deterministic layers, then benchmark near/semantic candidates.
6. Shadow MATA-to-Lake emissions and reconcile counts/hashes.
7. Shadow the single NB feed while retaining the old feeds.
8. Replay a bounded historical window and compare canonical story/source counts.
9. Emit candidate DecisionPackets only after contract validation.

Before inspecting challenger results, freeze a `MetricProfile` containing the incumbent, labeled-set version, sample floors, precision/recall and critical-false-collapse thresholds, latency/cost/privacy guardrails, subgroup slices, confidence treatment, and operating window. The near/semantic challenger is adopted only if it delivers material preregistered lift without a safety, latency, privacy, or source-independence regression. Otherwise record `REJECTED_CANDIDATE` with evidence and keep the simpler deterministic incumbent canonical.

## Golden set and tests

Build 500–1,000 labeled item pairs/clusters including exact duplicates, tracking-URL variants, translations, syndication, updates, same event/different angle, similar headline/different event, and genuinely independent corroboration.

Required tests:

- idempotency and unique-key races;
- transaction/outbox crash between write and deliver;
- consumer retry and dead-letter behavior;
- unknown event type;
- replay after partial delivery;
- protected-payload reference enforcement;
- story split/merge reversibility;
- independent-source grouping;
- NB duplicate prevention.

## Metrics and exit criteria

- zero lost events in bounded replay;
- zero duplicate external side effects;
- exact-duplicate precision at least 99.5%;
- story-cluster precision at least 95% and recall at least 90% on the frozen set;
- critical false collapse below 1%;
- 100% producer/run/artifact lineage for the canary window;
- unknown-message success ACKs equal zero;
- old and canonical feeds reconcile within a declared tolerance for two complete windows;
- independent reviewer passes code, data sample, and live receipts.
- the chosen cascade is the simplest candidate that passes the preregistered profile; a semantic layer that does not demonstrate material lift is explicitly rejected rather than retained by default.

## Rollback

Feature flags disable canonical dual write/read independently. Preserve the existing producers and outbox while canarying. On divergence, stop the canonical consumer, retain events/dead letters for replay, and return readers to the legacy path without deleting canonical records.

## Reviewer handoff

Provide producer/consumer inventory, before/after counts, labeled set and confusion matrix, replay logs, dead letters, NB reconciliation, sensitivity audit, and explicit proof that no old path was retired.
