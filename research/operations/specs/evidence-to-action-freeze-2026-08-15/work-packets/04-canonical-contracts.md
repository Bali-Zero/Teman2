---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 04 — Canonical Contracts and Compatibility Layer

**Wave:** 0
**Unlocks:** Packets 05–15
**Risk:** high architectural leverage, low external side-effect risk
**Execution mode:** additive schemas, validators, adapters, and shadow dual writes

## Session prompt

You are the execution session responsible for turning the frozen semantics in `CONTRACTS.md` into strict, reusable, versioned contracts without forcing an immediate rewrite of existing producers and consumers.

You are not alone in the codebase. Work in a dedicated worktree, declare exact ownership before editing, preserve all concurrent changes, and hold the central contract/migration lease. Migration `270` is reserved for this packet's canonical core. Refresh the authoritative Pro head; if it is occupied, stop the entire downstream migration block and request a versioned Conductor ledger revision. Never merge, deploy, publish, or remove a legacy field in this packet.

## Mission

Create one validated compatibility layer for every object in `CONTRACTS.md`, including decision/authority separation, immutable attempts and typed operational results, explicit succession and revocation, verification, Conductor handoff, outcomes, preregistered metric profiles, immutable correction-aware metric results, sensitivity sanitization, and evidence-bound risk reclassification.

Success means each system can adopt the contracts incrementally while preserving existing data, replay, privacy, and rollback.

## Baseline to establish

Inventory the current schemas and state machines in Intel Lake, NAGA, NEXUS, WR2, WR3, Magazine, the News Room, workflow services, outboxes, and outcome tables. Produce a field-level compatibility matrix. Identify identical names with different meanings—especially `published`, `auto_publish`, `approved`, `claim`, `source`, `status`, and `manifest`.

Do not assume a model is canonical because its filename says `contract`. Verify actual writers and readers.

## File ownership

Preferred new ownership boundary:

- new `packages/core/research_os/` schemas, JSON Schema exports, validators, and fixtures;
- new `apps/backend-rag/backend/services/research_os/` adapters and repositories;
- migration `apps/backend-rag/backend/db/migrations_v2/270_research_os_contract_core.sql` with the mandatory rollback marker, including the one canonical `OutcomeEvent` repository;
- focused tests under the corresponding package/backend test paths;
- contract documentation generated from or verified against the code.

Existing domain models remain owned by their domain packets. This packet may add adapters beside them, but may not refactor Intel Lake, NAGA, NEXUS, WR2, WR3, or publishing behavior.

## Frozen semantic input

The authoritative source is `research/operations/specs/evidence-to-action-freeze-2026-08-15/CONTRACTS.md`. If implementation evidence conflicts with a frozen invariant, stop and write a change proposal; do not silently reinterpret it.

## Deliverables

1. Strict typed models with forbidden unknown fields at ingestion boundaries and explicit extension maps where flexibility is required.
2. JSON Schema artifacts and canonical positive/negative fixtures for every contract.
3. Semantic-version registry and compatibility checker.
4. Legacy-to-canonical adapters with loss reports; no silent field dropping.
5. Additive persistence for object identities, versions, lineage, `ObjectSuccessorEdge`, `RevocationReceipt`, `SanitizationReceipt`, `RiskReclassificationReceipt`, approvals, immutable started attempts, typed `OperationalReceipt`, the one canonical `OutcomeEvent` repository, immutable correction-aware `MetricProfile`/`MetricResult` pairs, and references where missing.
6. A contract registry that identifies owning system, producer versions, consumer versions, risk/sensitivity rules, operational receipt types and their required fields, revocation behavior, and deprecation state.
7. Deterministic hashing/canonicalization rules for idempotency and approval invalidation.
8. A field-level compatibility matrix and phased dual-write/read plan for Packets 05–15.
9. Sanitization-receipt validation that prevents a sensitivity downgrade without exact source/output hashes, a reviewer, purpose, destination, and expiry; separate risk-reclassification validation that requires a distinct successor, exact remediation evidence, deterministic policy re-evaluation, and independent review.
10. One reusable, side-effect-free atomic repository primitive that losslessly materializes an exact `RequestedActionSpec` into one `ActionItem` plus one `ActionIntent`. Expose it to Packet 12 as the basis of the general runtime service and through one separately reviewed, fail-closed containment/manual adapter for Packet 01 Task 7 only. That adapter accepts only the five enumerated NEXUS containment action types and exact target/argument hashes, and validates the exact durable source-document revision, canonical `IntelEvent` → `Evidence` → `Claim` chain, upstream `DecisionPacket`, `WorkflowRun`, independent pre-cutover `VerificationReceipt`, and required packet `SanitizationReceipt`; it rejects any unreceipted intermediate classification decrease and is not a second inbox, action ledger, approval path, or executor.
11. One atomic classification-change persistence primitive with deferred cross-object constraints: a lower-risk successor, its exact `ObjectSuccessorEdge`, and `RiskReclassificationReceipt` commit or roll back together; a sensitivity decrease includes its exact `SanitizationReceipt` in the same write-set. Canonical hashes never embed the receipts.
12. A closed `ApprovalReceipt` subject/decision compatibility matrix plus registered queue-only `OperationalReceipt` profiles, proving Action Inbox transitions are not approvals and only exact `action_intent + approve` may authorize an attempt.

## Non-goals

- Do not create a new general event broker.
- Do not replace existing databases.
- Do not migrate all historical records.
- Do not alter the frozen embedding model.
- Do not add business logic, ranking, publishing, or entity resolution.
- Do not make free-form LLM output a trusted object without validation.

## Implementation sequence

1. Map existing writers/readers and choose additive storage locations consistent with current conventions.
2. Write contract fixtures and validators before migrations.
3. Implement canonical hashing with the single `^[0-9a-f]{64}$` wire encoding, timestamps, closed subject/decision pairs, sensitivity propagation, and version rules.
4. Add adapters and explicit `losses`/`warnings` output.
5. Add canonical persistence and rollback migration 270; domain packets reference this core instead of creating parallel event/approval/outcome ledgers.
6. Implement and transaction-test the side-effect-free `RequestedActionSpec` → `ActionItem` + `ActionIntent` primitive. Wrap it in a fail-closed Packet 01 containment/manual adapter restricted to the five exact Task 7 action types; any other caller or action type is rejected. Packet 12 later owns the general runtime endpoint, queue integration, permissions, and presentation around the same primitive.
7. Dual-write in tests only; then provide feature flags defaulting off for domain packets.
8. Generate compatibility and adoption reports.

## Golden set

Include at least:

- one public green news event;
- one amber regulatory claim with source span and validity interval;
- one red NEXUS-derived internal packet with a lower-sensitivity projection and exact sanitization receipt;
- one remediated red publication object whose distinct amber successor has an exact evidence-bound `RiskReclassificationReceipt`, plus a case that attempts to use sanitization alone and fails;
- one atomic red-to-amber successor/edge/risk-receipt bundle, one dual-axis bundle containing both receipt families, and rollback cases with each member missing or mismatched;
- one superseded claim;
- one translated/syndicated story cluster;
- one WR2 carousel manifest with multiple hero slides;
- one WR3 video manifest with audio/timeline fields;
- one approval invalidated by an input hash change;
- valid and invalid examples for every closed approval subject/decision pair, including `decision_packet`, media script/shot locks, and an `action_intent + approve` receipt as the only attempt-authorizing pair;
- one approval invalidated by a separate immutable `RevocationReceipt` and one fully receipted propagation chain;
- one started `ExecutionAttempt` followed by a successful `execution.result` `OperationalReceipt`, plus failed, replayed, corrected, and mismatched-result cases;
- one team acknowledgment and one completion/blocked operational-receipt specialization proving that acknowledgment is not approval or completion;
- one outcome where URL submission is distinct from verified indexing;
- one preregistered dataset/split-bound `MetricProfile`, an idempotent `MetricResult`, a corrected late-arrival successor, and a bound `OutcomeEvent` for the current result;
- adversarial payloads with PII, unknown enums, missing timezone, duplicate idempotency key, unreceipted sensitivity downgrade, unreceipted risk downgrade, cross-use of the wrong receipt family, and free-form extra fields.

## Tests and exit criteria

- Schema round-trip tests for every valid fixture.
- Negative tests for every invariant and classification boundary.
- Property tests for deterministic canonical hashes.
- Cross-language tests rejecting prefixed, uppercase, short, long, or nonhex canonical hashes.
- Property tests for acyclic single-successor families, revocation lookup, current-result selection, attempt/result separation, and duplicate receipt idempotency.
- Deferred-constraint transaction and replay tests for risk-only, sensitivity-only, and dual-axis classification-change bundles, including rollback on any missing or mismatched member.
- Approval subject/decision matrix tests plus queue-successor/typed-receipt tests proving assignment, triage, snooze, split, merge, evidence request, and closure cannot authorize an attempt.
- Transaction, race, replay, lossless-field, durable-document/event/evidence/claim lineage, upstream-reference, intermediate-classification, sanitization-receipt, and allowlist tests for the core requested-action materializer and its Packet 01 containment/manual adapter, proving one stable pair, zero external effects, rejection of missing/fabricated lineage or unreceipted downgrades, and fail-closed rejection outside the five enumerated containment action types.
- Migration apply/rollback tests in an isolated database.
- Adapter parity tests showing every legacy field is mapped, intentionally omitted with a reason, or rejected.
- Cross-language fixture validation if TypeScript consumers are included.

Exit only when all fixtures validate consistently, forbidden downgrade cases fail closed, migrations roll back, adapters produce explicit loss reports, no legacy runtime behavior changes by default, and an independent reviewer signs the semantic compatibility matrix.

## Shadow and rollback

All domain dual-write flags default off. When a domain enables shadow mode, canonical write failures must be observable but must not corrupt legacy truth. Rollback disables the adapter/dual write and leaves additive canonical rows for audit; it never deletes legacy data.

## Reviewer handoff

Provide the reviewer with schemas, fixtures, compatibility matrix, migration proof, hash specification, adapter loss reports, and the list of unresolved semantic conflicts. The reviewer must sample the actual current writers/readers, not only the new tests.
