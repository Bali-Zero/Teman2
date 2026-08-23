---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 06 — NAGA Claim Ledger, Evidence, and Bitemporality

**Wave:** 1
**Depends on:** Packet 04
**Unlocks:** Packets 07, 08, 10, 11, 12, and 14
**Risk:** high factual-integrity risk; fail closed for consequential claims

## Session prompt

You own the transition from document-level research to a canonical, source-span-level claim ledger. Extend NAGA's existing foundations; do not build a third claim system.

You are not alone in the codebase. Work in a dedicated worktree, claim exact files, and preserve concurrent edits. Migration `273` is reserved for this packet. Refresh the authoritative Pro head; if the central reservation is stale or occupied, stop and request a versioned ledger revision. Do not deploy, publish, or rewrite domain consumers in this packet. Client PII and restricted OSINT never enter cloud prompts, fixtures, logs, or artifacts.

## Mission

Make each consequential proposition traceable to evidence, valid in a defined time interval, explicitly supported/contradicted/inconclusive/superseded/expired, and capable of invalidating stale downstream drafts or actions.

## Baseline to establish

Audit the actual current NAGA migrations, models, persistence, quality, expiry, convergence, source scoring, action engine, gateway, scripts, and consumers. Determine which tables and services are live, which are code-only, and where `claim`, `evidence`, `confidence`, `expiry`, and `conflict` carry inconsistent meanings.

Relevant ownership starts around:

- `apps/backend-rag/backend/migrations/migration_079_naga_tables.py`
- `apps/backend-rag/backend/migrations/migration_081_naga_claim_quality.py`
- `apps/backend-rag/backend/services/naga/**`
- `apps/backend-rag/backend/core/claims/**`
- `apps/backend-rag/scripts/*claims*` and `*naga*`
- NAGA routers and focused tests

## File ownership

Own additive NAGA models/repositories/services, migration 273 with rollback, strict adapters to Packet 04 contracts, and focused tests. Do not own Intel ingestion, NEXUS entity merging, Qdrant retrieval, WR2/WR3 content, or Action Inbox UI.

## Inputs and frozen contracts

- Validated `Evidence`, `Claim`, `IntelEvent`, and `WorkflowRun` objects from Packet 04.
- Intel Lake source/event identity from Packet 05 when available; use adapters until then.
- W3C PROV semantics may guide lineage, but RDF is not required.
- Valid time and system time are distinct and mandatory for consequential temporal facts. Canonical versions store immutable `recorded_at`; effective system-time intervals are derived from append-only successor edges and never closed by mutating a prior object.
- Atomic claim persistence and bitemporal history are mandatory now. Automated atomization/extraction is an evaluated candidate, not a prerequisite for canonical storage.

## Deliverables

1. One canonical NAGA persistence model for claims, evidence links, source spans, status transitions, supersession, contradiction, expiry, and review.
2. Bitemporal fields and queries: “what was true at date X?” and “what did Nuzantara believe at date Y?”
3. An atomic claim-creation contract with abstention and strict validation, supporting deterministic or human/rule-assisted creation as the safe incumbent and automated extraction only as a measured candidate.
4. Evidence independence model that distinguishes original, syndicated, translated, and derived sources.
5. Transition engine with allowed state transitions and immutable history.
6. Downstream dependency index mapping claims to DecisionPackets, ContentObjects, drafts, alerts, and pending client actions.
7. Invalidation events when evidence is withdrawn, a claim expires, is contradicted, or is superseded.
8. Human review queue for critical/ambiguous claims and calibrated confidence metadata.
9. Time-travel and provenance API for downstream readers.

## Non-goals

- Do not resolve or merge real-world entities; NEXUS owns that.
- Do not use confidence as a substitute for evidence.
- Do not infer that an absent record proves a negative fact.
- Do not auto-publish, answer a client, or mutate a draft from an unreviewed invalidation.
- Do not add a new vector or graph database.
- Do not send sensitive source content to an external model.

## Implementation sequence

1. Map existing claim schemas and select the canonical NAGA path.
2. Freeze a 200–300 claim golden set with exact source spans, temporal truth, contradictions, supersessions, and no-answer cases.
3. Add strict canonical adapters and additive storage.
4. Implement bitemporal transition rules and time-travel queries.
5. Add evidence-independence and contradiction semantics.
6. Build the dependency/invalidation outbox without changing consumers.
7. Dual-write and shadow-read a bounded public, non-PII domain.
8. Review mismatches and calibrate thresholds before expanding.

Automated extraction must have a preregistered `MetricProfile`, held-out source-span evaluation, abstention behavior, and independent review. If it does not pass, mark it `REJECTED_CANDIDATE`; human/rule-assisted atomic creation and canonical bitemporal storage remain the production path. Failure of the extractor must never defer the ledger's atomic or temporal semantics.

## Golden set and adversarial cases

Cover Indonesian regulatory changes, effective dates distinct from publication dates, amended/repealed rules, conflicting secondary sources, currency/units, ambiguous subjects, translated passages, expired prices/deadlines, missing official sources, and intentionally unanswerable questions.

Include adversarial cases where:

- a high-confidence model has no source span;
- five websites repeat one original story;
- a later correction predates Nuzantara's discovery;
- the same sentence contains two atomic claims;
- a claim is true nationally but false in a local jurisdiction;
- evidence is restricted and only a sanitized projection is permitted.

## Tests and metrics

- migration apply/rollback and temporal exclusion tests;
- transition property tests;
- source-span hash/locator tests;
- contradiction and supersession tests;
- time-travel correctness tests;
- invalidation idempotency and replay tests;
- privacy/sensitivity boundary tests;
- critical claim review authorization tests.

Exit thresholds:

- 100% source-span coverage for critical claims;
- at least 98% precision for reviewed supported critical claims on the golden set;
- zero unsupported critical claims eligible for public use;
- at least 95% bitemporal query correctness;
- every claim transition and downstream invalidation traceable;
- bounded invalidation emitted within 15 minutes in canary, with a 60-minute maximum operational SLA;
- independent legal/factual reviewer passes the sampled claims.

## Shadow, canary, and rollback

Dual-write one public domain first. Legacy readers remain authoritative until parity is demonstrated. Invalidation events initially create review actions only; they do not automatically withdraw public content. Rollback disables canonical writes/reads and invalidation consumers while preserving appended audit history.

## Reviewer handoff

Provide schema mapping, golden set, temporal query results, claim/evidence samples, transition audit, invalidation replay, privacy test, and a list of every consumer still using legacy semantics.
