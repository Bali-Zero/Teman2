---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 07 — NEXUS Temporal Entity Resolution with NAGA Evidence (Contract-Gated)

**Wave:** 1; golden-set preparation may begin early, but graph mutation is blocked until the dependency gates below pass.
**Depends on:** Packets 01, 04, 05, and 06.
**Execution mode:** run graph and raw-OSINT work on the authoritative Pro only.

**Goal:** Replace name-centric, destructive entity merging with source-backed temporal identity decisions that preserve history, consume reviewed NAGA evidence, and emit reviewable candidates before any canonical graph mutation.

**Architecture:** Treat identity, roles, aliases, declarations, and relationships as evidence-bearing observations with valid time and effective system time derived from immutable recorded versions. NAGA supplies reviewed claim evidence through the canonical contract but never decides identity or promotion. NEXUS resolves locally, stages candidates, and promotes only through the existing explicit, receipt-producing, fail-closed gate.

**Tech Stack:** Python 3.11+, dataclasses, Neo4j 5 Community, pytest, JSONL evidence envelopes, NAGA Claims DB as a read-only upstream evidence provider.

**Primary implementation repository:** /Users/nuzantara/Desktop/OSINT-Nexus on Pro.

**Read-only dependency repository:** /Users/nuzantara/Desktop/nuzantara on Pro, specifically NAGA under apps/backend-rag/backend/services/naga and the canonical claim contract under apps/backend-rag/backend/core/claims.

## Mission

Build a temporal entity-resolution layer that can answer four distinct questions without collapsing them:

1. Which canonical public entity, if any, does a new observation refer to?
2. During what valid-time interval was the observed role, alias, asset declaration, or relationship true?
3. When did NEXUS retrieve and accept the evidence?
4. What evidence and review decision authorized any canonical attachment?

The implementation must prevent silent merges, preserve contradictory observations, and make uncertainty visible. A fuzzy name match may create a candidate but can never auto-attach a person.

LHKPN means Laporan Harta Kekayaan Penyelenggara Negara, a public KPK/eLHKPN wealth declaration. It is not a bank statement or transaction history. The legacy BankAccount graph concept represents only the declared Kas dan Setara Kas aggregate and must be modeled in new temporal outputs as DeclaredCashAggregate, with CashEquivalent as an accepted explanatory synonym.

## Live Baseline to Re-Verify

The following was observed on Pro on 2026-08-15 WITA:

- OSINT-Nexus runtime commit: c4a619d, with substantial uncommitted runtime work.
- Graph: 23,559 nodes and 16,648 relationships, including 48 Official, 44 LhkpnReport, 11 legacy BankAccount nodes, 5,011 SourceDocument, and 16,152 Claim nodes.
- Canonical LHKPN relation in the populated graph: Official to LhkpnReport through FILED.
- REPORTED_LHKPN count was zero.
- osint_nexus/resolver/entity_resolver.py used in-memory indexes and four tiers: exact NIP, exact public identifier, role plus office, fuzzy name, then new entity.
- Non-strict fuzzy matches could merge properties immediately.
- Property merging was non-destructive only in the narrow sense that empty fields were filled; it did not preserve source-specific temporal assertions.
- osint_nexus/provenance/models.py already required source-document references, confidence, PII class, review state, and explicit promotability.
- NAGA persisted sessions, sources, claims, evidence links, review state, valid_as_of, expiry, quality, deduplication, and claim transitions.
- NAGA ClaimRecord and persisted claim rows were primarily text claims and did not provide a complete subject-predicate-object plus valid interval contract.
- GET /api/naga/session/{session_id} and GET /api/naga/claims/search were stubs in the observed router. This packet must not build against a stub or silently query production tables through an ad hoc bypass.

Re-verify all of these at implementation time. Record only aggregate counts and opaque IDs. Never place real names, identifiers, addresses, source excerpts, or graph payloads in test output or review artifacts.

## Dependency Gates

This packet is blocked until every gate passes:

### Gate A: Wave 0 containment

- Work Packet 01 has passed independent review.
- NEXUS UI and Neo4j are loopback-only.
- Runtime secrets are no longer present in source or plist files.
- Exact property locations are suppressed from API serialization.

### Gate B: Canonical evidence contract

The preceding canonical-contract work has merged and published one versioned contract. This packet consumes that contract and must not invent another.

Consume the Packet 04 `Evidence` and `Claim` objects exactly as frozen in `CONTRACTS.md`:

- `Evidence` supplies `evidence_id`, exact `source_event_ref`, exact source-document revision identity, `source_span`, `source_tier`, `stance`, evidence times, provenance, classification, and `review_state`.
- `Claim` supplies `claim_id`, the structured subject/predicate/object statement, scope, valid time, immutable `recorded_at`, successor-derived effective system time, status, exact evidence references, confidence, classification, review, and lineage.
- The NEXUS adapter may resolve a protected local source receipt from the exact source-document revision or `source_event_ref`, but it must not add raw source URLs, excerpts, or identifiers to the cross-system contract.
- Local-only fields such as `temporal_precision`, `public_identifier_digest`, `legal_basis`, and resolution reason codes belong to `EntityObservation` or `ResolutionDecision`; they do not redefine `Evidence` or `Claim`.
- Every local observation retains both canonical IDs, and an adapter test proves that no canonical field is silently dropped or assigned a different meaning.

Unknown dates remain null in the canonical valid-time fields. `temporal_precision=unknown` may annotate the local observation, but collection time must never be substituted for an unknown valid date.

### Gate C: Canonical LHKPN graph contract

- Mata Garuda emits the canonical typed message discriminator for LHKPN.
- All accepted declarations resolve to Official to LhkpnReport through FILED.
- No new REPORTED_LHKPN relation is written.
- Each declaration has a deterministic report identifier and source receipt.
- New cash aggregates use DeclaredCashAggregate or CashEquivalent semantics.
- The legacy BankAccount label may remain only as a compatibility read; it is not emitted by new contracts.

### Gate D: NAGA evidence availability

- NAGA provides a real, tested, read-only reviewed-claim export or service; the observed empty claims-search stub is not sufficient.
- Exported evidence conforms byte-for-byte to the canonical contract version.
- NAGA review state is explicit. auto_extracted, provisional, expired, conflicting, or missing-source claims are not promotable.
- NAGA remains an evidence provider. It does not emit final NEXUS canonical IDs, merge decisions, or graph mutations.

### Gate E: Sovereignty boundary

- Any person-specific resolution and raw OSINT processing run locally on Pro.
- No real official name, NIP, NHK, address, relationship, dossier row, or source excerpt is sent to a cloud LLM.
- If NAGA uses a cloud research tier, it may handle only non-PII institutional or aggregate research. Person-specific inputs require a local NAGA-compatible path or must remain unprocessed.
- Cross-system artifacts use opaque local references and sanitized claim text.

If any gate is incomplete, produce a blocked receipt naming the failed gate and stop. Do not implement a compatibility shortcut.

## Explicit Scope and File Ownership

Create a dedicated worktree in /Users/nuzantara/Desktop/OSINT-Nexus from an operator-approved snapshot. Do not edit its dirty runtime checkout.

This packet owns only:

- osint_nexus/resolver/temporal_models.py, new
- osint_nexus/resolver/temporal_entity_resolver.py, new
- osint_nexus/resolver/naga_claim_adapter.py, new
- osint_nexus/resolver/entity_resolver.py, compatibility-facade changes only
- osint_nexus/graph/temporal_projection.py, new
- osint_nexus/graph/schema.py, additive constraints and indexes only
- osint_nexus/promotion/promoter.py, temporal candidate validation only
- tests/fixtures/temporal_entity_resolution.json, new synthetic fixture
- tests/test_temporal_models.py, new
- tests/test_temporal_entity_resolver.py, new
- tests/test_naga_claim_adapter.py, new
- tests/test_temporal_projection.py, new
- tests/promotion/test_temporal_promoter.py, new
- docs/runbooks/nexus-temporal-entity-resolution.md, new

The following Nuzantara/NAGA files are read-only inputs and are not owned:

- /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/core/claims/models.py
- /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/naga/orchestrator.py
- /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/naga/persist.py
- /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/naga/quality/dedup.py
- /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/services/naga/quality/expiry.py
- /Users/nuzantara/Desktop/nuzantara/apps/backend-rag/backend/app/routers/naga.py
- the NAGA table migrations and the merged canonical-contract implementation

If NAGA lacks the required export, return the task to the NAGA/canonical-contract owner. Do not modify NAGA in this packet and do not read its database through a new private query.

## Frozen Domain Model

### EntityObservation

Implement an immutable EntityObservation carrying:

- observation_id
- evidence_id
- source_document_id
- claim_id
- observed_at
- valid_from
- valid_to
- temporal_precision
- entity_type
- asserted_name
- normalized_name
- public_identifier_kind, nullable
- public_identifier_digest, nullable
- role, nullable
- organization_ref, nullable
- location_scope, nullable and coarse
- attributes as a policy-filtered mapping
- confidence
- review_state
- pii_class

Raw public identifiers must not appear in logs, candidate filenames, metrics, or review artifacts. The resolver may compare an exact identifier locally, but persisted candidate outputs use a deterministic keyed digest or an already-approved opaque reference.

### ResolutionDecision

Every resolution returns an immutable decision with:

- decision_id
- observation_id
- decision_type
- candidate_entity_id, nullable
- score
- reason_codes
- conflicting_entity_ids
- required_review
- evidence_refs containing each exact canonical `Evidence` ID/hash pair
- decided_at
- resolver_version

Allowed decision types:

- EXACT_IDENTIFIER_MATCH
- EXACT_APPROVED_ALIAS_MATCH
- LINK_CANDIDATE
- AMBIGUOUS
- NEW_ENTITY_CANDIDATE
- REJECTED_POLICY
- REJECTED_EVIDENCE

No decision type named AUTO_MERGE is permitted.

### Temporal semantics

- valid_from and valid_to describe when the assertion is true in the world.
- observed_at describes when NEXUS received the evidence.
- decided_at describes when the resolver made its decision.
- promoted_at, when present, describes when the reviewed decision entered the canonical graph.
- valid_to is exclusive.
- An unknown interval remains null; do not infer it from retrieval time, report year, or neighboring observations.
- A year-only LHKPN declaration uses temporal_precision=year and preserves its stated reporting period.
- Contradictory intervals coexist as competing claims until reviewed. Last-write-wins is forbidden.

### Identity matching

- Exact approved public identifiers may produce EXACT_IDENTIFIER_MATCH.
- An exact approved alias plus compatible institution or role context may produce EXACT_APPROVED_ALIAS_MATCH.
- Role plus office without an approved identifier produces at most LINK_CANDIDATE.
- Fuzzy name similarity produces at most LINK_CANDIDATE or AMBIGUOUS.
- A same-name collision with overlapping roles, incompatible institutions, or conflicting identifiers is AMBIGUOUS.
- A one-token name never auto-attaches.
- A new canonical entity is only created by reviewed promotion of NEW_ENTITY_CANDIDATE.
- Existing canonical IDs remain stable; do not regenerate them from a changed display name.

### Temporal graph projection

Use additive, evidence-backed graph structures:

- EntityObservation nodes are immutable.
- ResolutionDecision nodes are immutable.
- OBSERVES links an observation to its candidate or canonical entity only after review policy permits the link.
- SUPPORTED_BY links observations and decisions to SourceDocument or Claim receipts.
- RoleAssignment is a reified temporal fact with valid_from, valid_to, temporal_precision, observed_at, claim_id, and review state.
- AliasAssertion is a reified temporal fact with the same provenance fields.
- LhkpnReport remains attached through FILED.
- A declared cash aggregate is represented as DeclaredCashAggregate in new projection code and linked to its LhkpnReport. It is not an account and never carries bank or transaction fields.
- Existing OWNS relations may remain as compatibility projections, but new temporal truth must be recoverable from the report-linked, source-backed structures.

All new constraints and indexes in osint_nexus/graph/schema.py must be additive and idempotent. No existing label, node, relationship, property, or constraint may be deleted or renamed in this packet.

### NAGA boundary

- Consume only reviewed, non-expired canonical evidence objects.
- Reject absent source_document_id, absent evidence_id, unknown contract version, invalid interval, private PII class, non-approved review state, or confidence below the canonical promotion threshold.
- NAGA text similarity is evidence discovery, not identity resolution.
- NAGA duplicate or corroboration transitions may affect evidence ranking but cannot authorize a merge.
- A NAGA claim that supersedes another creates a temporal candidate; it does not overwrite the older claim.

### Promotion boundary

Preserve and extend the current fail-closed requirements:

- verified review state;
- confidence at or above the canonical threshold;
- source document and evidence receipt present;
- non-private PII class;
- allowed canonical contract version;
- explicit apply operation behind the canonical Packet 12 action chain;
- typed terminal `OperationalReceipt` for every real graph mutation, bound to its exact `ExecutionAttempt`;
- identity merge disabled unless the reviewed candidate explicitly authorizes that one merge.

Downstream blog, Magazine, SEO, WR2, WR3, messaging, and public APIs receive only sanitized, independently approved briefs. They never consume EntityObservation, ResolutionDecision, raw claims, or graph rows directly.

## Deliverables

1. Immutable typed temporal observation and decision models.
2. A deterministic resolver with no fuzzy auto-merge path.
3. A strict NAGA canonical-evidence adapter.
4. Additive Neo4j schema and a dry-run temporal projection planner.
5. An append-only candidate queue with content hashes and opaque IDs.
6. Promoter validation that accepts only independently reviewed temporal candidates.
7. A synthetic golden set and deterministic evaluation harness.
8. A read-only backfill preview for the existing LHKPN and identity subgraph.
9. Shadow comparison against the legacy resolver without graph writes.
10. A bounded future production-canary handoff plan. It specifies reversible typed `OperationalReceipt` records and exact `RequestedActionSpec`/`ActionIntent` requirements but performs no production graph write in this packet.
11. A runbook covering dependency checks, review, apply, rollback, and privacy.

## Non-Goals

- Do not repair NAGA, change its database, or replace its canonical contract.
- Do not change bridge transport, Redis stream ownership, or the canonical LHKPN message in this packet.
- Do not bulk-merge existing entities.
- Do not rewrite or delete historical nodes and relationships.
- Do not treat a missing LHKPN declaration as evidence of misconduct.
- Do not build accusation, corruption, influence, or guilt scores.
- Do not infer family, social, financial, or private relationships from name similarity.
- Do not send person-specific OSINT to cloud models.
- Do not expose the graph to editorial or public surfaces.
- Do not migrate the legacy BankAccount label destructively.

## Implementation Sequence

### Task 1: Verify dependencies and freeze baselines

- [ ] Confirm all five dependency gates with exact version/hash receipts.
- [ ] Record OSINT-Nexus commit, dirty-path inventory, aggregate graph counts, current resolver version, promoter policy, and canonical contract hash.
- [ ] Record NAGA export contract version and a sanitized count by review state; do not record claim text or entity names.
- [ ] Create the isolated OSINT-Nexus worktree from the approved source snapshot.
- [ ] Run the existing resolver, provenance, promoter, loader, and anomaly tests to establish baseline.

Expected result: either a complete sanitized gate receipt or a blocked receipt. No code changes are allowed after a failed gate.

### Task 2: Write the synthetic golden set and failing tests

- [ ] Add synthetic observations covering exact identifier, approved alias, same-name collision, role succession, overlapping conflicting roles, one-token names, unknown dates, year-only dates, supersession, rejected PII, missing source, and expired evidence.
- [ ] Add two annual synthetic LHKPN reports for one synthetic official with distinct DeclaredCashAggregate facts.
- [ ] Write model validation tests for invalid intervals, absent evidence, unsupported precision, and mutable payload attempts.
- [ ] Write resolver tests that require zero fuzzy auto-merges.
- [ ] Write NAGA adapter tests that reject every non-approved or incomplete evidence state.
- [ ] Write temporal projection and promoter tests before implementation.
- [ ] Run the focused suite and preserve expected RED output.

### Task 3: Implement immutable temporal models

- [ ] Implement EntityObservation and ResolutionDecision as immutable typed structures.
- [ ] Validate UTC timestamps, interval ordering, temporal precision, confidence range, contract version, and required evidence references.
- [ ] Normalize display names without deriving a canonical identity from the name.
- [ ] Generate deterministic observation and decision IDs from policy-safe semantic parts.
- [ ] Ensure serialization drops raw identifier material and private attributes.
- [ ] Run model tests until GREEN.

### Task 4: Implement deterministic resolution

- [ ] Implement exact-identifier matching against local approved indexes.
- [ ] Implement approved-alias matching with compatible context.
- [ ] Implement candidate scoring for role, organization, temporal overlap, and fuzzy name signals.
- [ ] Encode collision and ambiguity reason codes.
- [ ] Make every non-exact person match require review.
- [ ] Keep the existing EntityResolver public API as a compatibility facade, but route strict public-profile decisions through the temporal resolver.
- [ ] Prove through tests that the compatibility facade does not mutate canonical properties before promotion.

### Task 5: Implement the NAGA adapter

- [ ] Parse only the merged canonical contract version.
- [ ] Reject unsupported versions, incomplete provenance, private PII, non-approved review state, expired claims, and invalid temporal fields.
- [ ] Convert accepted evidence into EntityObservation without allowing NAGA to specify a final canonical entity.
- [ ] Preserve supersession as a linked candidate rather than overwriting history.
- [ ] Emit reason-coded counters without names or claim text.
- [ ] Run adapter tests until GREEN.

### Task 6: Implement additive temporal projection

- [ ] Add idempotent constraints and indexes for observation, decision, role-assignment, alias-assertion, and declared-cash-aggregate identifiers.
- [ ] Implement a dry-run projection planner that returns intended Cypher parameters and content hashes without executing writes.
- [ ] Require source and claim receipts for every planned node or relationship.
- [ ] Link LHKPN cash aggregates to their LhkpnReport and expose DeclaredCashAggregate semantics only.
- [ ] Ensure repeated processing of the same evidence produces the same plan and no duplicate mutation.
- [ ] Validate against an isolated Neo4j test database on Pro.

### Task 7: Extend the promoter without weakening it

- [ ] Add temporal candidate validation before any mutation.
- [ ] Require an independent review decision bound to candidate hash, contract version, evidence hashes, and intended mutation hash.
- [ ] Keep production apply disabled by default and make the entry point reject any call that lacks the future canonical Packet 12 action chain.
- [ ] On the disposable synthetic clone only, emit an `execution.result` `OperationalReceipt` fixture bound to the exact test attempt for each applied candidate; never treat that fixture as production authority or proof.
- [ ] Make conflicting evidence or stale review hashes fail closed.
- [ ] Add an inverse or deactivation plan to each proposed production action and clone receipt; never encode destructive deletion as the default rollback.
- [ ] Run existing and new promotion tests until GREEN.

### Task 8: Produce a read-only backfill preview

- [ ] Scan the existing graph read-only and produce only aggregate counts for observations that could be projected.
- [ ] Report exact-identifier candidates, alias candidates, ambiguous collisions, invalid temporal data, missing evidence, legacy BankAccount compatibility reads, and blocked PII cases.
- [ ] Do not write to Neo4j.
- [ ] Do not include names, addresses, NIP, NHK, source excerpts, or raw properties.
- [ ] Hash the preview artifact and bind it to the source graph-count snapshot.

### Task 9: Shadow evaluation

- [ ] Run the legacy resolver and temporal resolver on the same synthetic golden set and an operator-approved, locally held adjudication sample.
- [ ] Log only opaque case IDs, decisions, scores, and reason codes.
- [ ] Keep all proposed matches in the candidate queue and perform zero graph writes.
- [ ] Have an independent human or reviewer adjudicate the sample without seeing the resolver label first.
- [ ] Produce a confusion matrix and error taxonomy.

### Task 10: Canary and closeout

- [ ] Obtain independent approval of contracts, tests, shadow metrics, privacy evidence, and mutation plans.
- [ ] Apply first to an isolated Neo4j clone using synthetic records.
- [ ] If the clone passes, prepare—but do not execute—a future production candidate packet for a small set of independently reviewed, source-complete candidates represented by operator-held opaque IDs.
- [ ] For every proposed candidate, define an exact `RequestedActionSpec` and require Packet 12 to materialize the `ActionItem`/`ActionIntent`; a future execution also requires an unexpired effect-specific `ApprovalReceipt`, immutable started `ExecutionAttempt`, and terminal `OperationalReceipt`.
- [ ] Define the aggregate integrity and temporal-history queries that a future executor must run after every candidate.
- [ ] Make the future plan stop on the first mismatch, unreviewed attachment, provenance gap, privacy leak, missing receipt, or stale binding.
- [ ] Commit atomically on the feature branch. Never self-merge, push to main, publish, or deploy a public surface.

## Golden Set and Baseline

The committed golden set must be entirely synthetic and include at least these cases:

| Case | Evidence pattern | Required decision |
|---|---|---|
| G01 | Same approved public-identifier digest, spelling variation | EXACT_IDENTIFIER_MATCH, review still required for promotion |
| G02 | Same name and compatible approved alias plus institution | EXACT_APPROVED_ALIAS_MATCH |
| G03 | Same name, different identifiers | AMBIGUOUS |
| G04 | Same name, overlapping incompatible roles | AMBIGUOUS |
| G05 | Similar multi-token names without identifier | LINK_CANDIDATE |
| G06 | One-token name | LINK_CANDIDATE or AMBIGUOUS, never exact |
| G07 | New source-backed identity | NEW_ENTITY_CANDIDATE |
| G08 | Missing source document | REJECTED_EVIDENCE |
| G09 | Private or suppressed PII class | REJECTED_POLICY |
| G10 | valid_to earlier than valid_from | model validation failure |
| G11 | Unknown real-world date | null interval plus precision unknown |
| G12 | Year-only LHKPN filing | preserved year precision, no invented day |
| G13 | Two yearly cash aggregates | two report-linked DeclaredCashAggregate facts |
| G14 | NAGA auto_extracted claim | rejected |
| G15 | NAGA reviewed but expired claim | rejected |
| G16 | Reviewed superseding claim | linked temporal candidate; prior claim preserved |
| G17 | Replayed identical evidence | same IDs and zero duplicate mutation |
| G18 | Conflicting reviewed sources | competing candidates, no last-write-wins |

The locally adjudicated shadow sample must be chosen by opaque ID and remain on Pro. Its contents must never enter this plan, logs, cloud prompts, or review summaries.

## Tests and Evaluations

Run from the isolated OSINT-Nexus worktree:

    PYTHONPATH=. .venv/bin/python -m pytest \
      tests/test_resolver.py \
      tests/test_provenance_models.py \
      tests/test_provenance_gate.py \
      tests/promotion/test_promoter.py \
      tests/test_temporal_models.py \
      tests/test_temporal_entity_resolver.py \
      tests/test_naga_claim_adapter.py \
      tests/test_temporal_projection.py \
      tests/promotion/test_temporal_promoter.py -q

Required evaluations:

- deterministic serialization and hashing;
- invalid interval rejection;
- unsupported contract-version rejection;
- no fuzzy auto-merge;
- strict source and review-state gate;
- exact identifier collision handling;
- temporal overlap conflict detection;
- replay idempotency;
- additive schema idempotency;
- dry-run parity with intended mutations;
- promoter refusal when review or evidence hashes differ;
- privacy scan over logs and artifacts.

Neo4j integration tests run in an isolated Pro database or container. Never install or run Neo4j on Air-M5, and never point destructive test fixtures at the live graph.

## Shadow and Canary

Shadow phase:

- Minimum 100 adjudicated local observations or all available approved observations if fewer exist.
- Minimum seven calendar days or enough scheduled cycles to exercise replay and supersession.
- Zero canonical graph writes.
- Compare legacy and temporal decisions by opaque case ID.
- Review every proposed exact attachment and a stratified sample of candidate and ambiguous decisions.

Future canary handoff:

- Synthetic clone first.
- At most ten independently reviewed production candidates may be proposed after the clone passes; Packet 07 performs zero production mutations.
- Each future candidate must traverse the exact Packet 12/18 authority chain and yield one typed terminal `OperationalReceipt`; a local review decision or generic mutation receipt is not execution authority.
- No batch apply.
- A future executor must pause after each mutation for integrity, provenance, interval, and privacy checks.
- Do not enable continuous automatic promotion in this packet.

## Metrics and Exit Criteria

This packet passes only when:

- Golden-set false person merges: 0.
- Fuzzy-name automatic person attachments: 0.
- Exact-identifier collision cases routed to AMBIGUOUS: 100 percent.
- Accepted observations with source_document_id, evidence_id, claim_id, observed_at, review state, and contract version: 100 percent.
- Unknown valid dates represented without invented precision: 100 percent.
- Replayed evidence produces duplicate graph mutations: 0.
- New LHKPN cash projections named DeclaredCashAggregate: 100 percent.
- New objects containing bank name, account number, or transaction fields: 0.
- Promoted decisions with matching independent-review and mutation hashes: 100 percent.
- Person-specific OSINT sent to cloud services: 0.
- Raw NEXUS rows delivered to editorial or messaging surfaces: 0.
- Shadow false-attachment rate on the adjudicated sample: 0.
- Candidate recall and coverage are measured at the preregistered accepted-merge precision floor and meet the `MetricProfile` minimum on every protected subgroup with enough samples.
- Future canary rollback plans, exact action specifications, and required receipt schemas present: 100 percent; production writes performed by Packet 07: 0.

Before results are inspected, freeze a `MetricProfile` with sample floors, candidate-recall/coverage targets, the accepted-merge precision floor, subgroup slices, operating window, exclusions, and uncertainty treatment. Candidate recall never lowers safety thresholds, but a reject-all resolver cannot pass by manufacturing perfect precision: if coverage misses the preregistered floor, the gate fails; if the sample floor is unmet, the result is `insufficient_evidence`. Unresolved and ambiguous cases remain acceptable individual outcomes.

## Rollback

- All new schema changes are additive; rollback first disables new readers and writers.
- Do not delete observations, decisions, claims, receipts, or historical relationships.
- A future mistaken canary attachment must be deactivated or superseded through a separately approved inverse action bound to the original exact receipt; Packet 07 only proves this behavior on the synthetic clone.
- Restore the legacy read path only; never restore its silent property merge behavior as a writer.
- Keep canonical IDs stable during rollback.
- If a contract mismatch appears, stop intake at the adapter and preserve the rejected envelope hash for diagnosis without preserving sensitive payload text.
- If privacy leakage appears, stop the resolver and candidate exporter immediately, quarantine only the affected local artifacts on Pro, and do not copy them into tickets or cloud prompts.

## Security and Privacy

- Raw OSINT remains on Pro.
- Tests and committed fixtures are synthetic.
- Metrics contain counts, opaque IDs, decision types, and reason codes only.
- Public availability does not waive the system's redaction and purpose-limitation policy.
- No adverse inference follows from a missing declaration, source outage, ambiguous identity, or unresolved candidate.
- Relationship candidates are hypotheses requiring evidence and review, not accusations.
- The NAGA adapter is read-only and contract-bound.
- Promotion remains explicit, independently reviewed, and receipt-producing.
- Downstream use is sanitized-brief-only.

## Independent Reviewer Handoff

The implementer stops before any production graph mutation and hands a reviewer who did not author the code:

1. dependency-gate receipt with canonical contract hash and NAGA export version;
2. exact owned-file diff;
3. RED then GREEN focused-test evidence;
4. synthetic golden-set results;
5. shadow confusion matrix and error taxonomy using opaque IDs;
6. additive schema plan and isolated-Neo4j results;
7. read-only backfill preview hash and aggregate counts;
8. candidate queue schema and sample with synthetic values only;
9. promoter refusal tests and mutation-receipt schema;
10. privacy scan proving no real PII or raw OSINT appears in artifacts;
11. proposed production canary list represented only by operator-held opaque IDs.

The independent reviewer must assess ontology correctness, temporal semantics, entity-resolution error modes, evidence completeness, NAGA boundary compliance, promotion safety, and privacy. A PASS authorizes only handoff of the bounded future production proposal to the canonical Packet 12/18 action path. It does not authorize a graph mutation, continuous promotion, public access, editorial publication, or deployment outside Pro.
