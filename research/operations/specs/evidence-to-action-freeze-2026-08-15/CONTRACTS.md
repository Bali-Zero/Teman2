---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Research OS Canonical Contracts

**Contract family:** `research-os/v1.0.0`
**Status:** frozen semantic contract; Work Packet 04 owns the canonical validators, repositories, and additive persistence core

## 1. Contract rules

1. IDs are globally unique, immutable, and never reused.
2. Timestamps are timezone-aware UTC in storage; interfaces may render WITA.
3. `observed_at` is not `published_at`; valid time is not system time.
4. Canonical objects are never overwritten. Corrections and state changes append a successor object plus an explicit edge; only named noncanonical delivery or projection rows may be mutable.
5. Derived objects carry input IDs and hashes, producer version, code/model/prompt version where applicable, and a deterministic or explicitly random run identity.
6. Every external or consequential operational side effect outside append-only canonical evidence, decision, verification, sanitization, risk-reclassification, approval, and revocation issuance has an `ActionIntent`, an idempotency key, a specific `ApprovalReceipt`, an immutable started `ExecutionAttempt`, and a separate typed `OperationalReceipt` for the result. Those canonical receipts follow their own stricter issuance invariants; every mutable or external propagation/use that follows them returns to the full action chain.
7. Risk and sensitivity may stay equal or increase downstream. Sensitivity may decrease only through a valid, purpose- and destination-bound `SanitizationReceipt`; risk may decrease only on a distinct corrected/remediated successor covered by a valid `RiskReclassificationReceipt`. The output hash is computed without embedding either receipt. The lowered output, its required receipt, and—when it is a successor—its `ObjectSuccessorEdge` commit in one transaction with deferred cross-object constraints; a revision that decreases both dimensions commits both exact receipts in that same write-set. An incomplete bundle rolls back.
8. Free-form LLM prose is never a contract object until strict validation succeeds.
9. Missing evidence is not negative evidence. `unknown`, `inconclusive`, and `insufficient_evidence` are valid outcomes.
10. Schema changes use semantic versions. Additive optional fields are minor; meaning changes, removals, enum additions, and required-field changes are major unless the compatibility matrix proves otherwise.
11. No packet may redefine a canonical object locally. Surface-specific fields live in a namespaced extension or a versioned specialization that imports the canonical object unchanged.

## 2. Canonical representation, hashes, and extensions

Canonical objects are JSON-compatible. Before hashing, implementations must:

1. validate against the exact contract version;
2. serialize with RFC 8785 JSON Canonicalization Scheme semantics;
3. encode as UTF-8 without a byte-order mark; and
4. compute lowercase hexadecimal SHA-256.

Every canonical field typed `sha256`, including an `object_hash`, content hash, arguments hash, input revision hash, or hash-derived artifact identity, uses the wire-level regex `^[0-9a-f]{64}$` with no algorithm prefix. Interfaces may label a value as SHA-256 outside the field, but `sha256:<hex>` is never a canonical value.

`object_hash` always means the hash of the complete canonical object with the `object_hash` field itself and fields explicitly marked as transport metadata omitted. The omission set is versioned and identical in every implementation; a producer cannot choose it ad hoc. `input_revision_hash` binds a decision to the exact revision it reviewed. References to mutable files or URLs are insufficient without a content or revision hash.

Core objects reject unknown top-level fields. Producer-specific additions may appear only under:

```yaml
extensions:
  reverse.dns.namespace:
    extension_version: semver
    payload: validated object
```

An extension cannot change a core field's meaning, weaken a risk class, authorize an action, or participate in a release gate until promoted through the freeze-change protocol.

## 3. Closed enum registry and shared primitives

The following enums are closed in `research-os/v1.0.0`. Unknown values fail validation.

| Enum | Allowed values |
|---|---|
| `risk_class` | `green`, `amber`, `red` |
| `sensitivity` | `public`, `internal`, `confidential`, `restricted_osint`, `client_pii` |
| `review_state` | `unreviewed`, `machine_checked`, `human_approved`, `human_rejected`, `superseded` |
| `publication_state` | `generated`, `staged`, `human_approved`, `publishing`, `deployed`, `indexed_verified` |
| `verification_state` | `unverified`, `verified`, `stale` |
| `availability_state` | `active`, `correction_required`, `withdrawal_requested`, `withdrawn` |
| `evidence_stance` | `supports`, `contradicts`, `contextualizes`, `inconclusive` |
| `claim_status` | `supported`, `contradicted`, `inconclusive`, `superseded`, `expired` |
| `workflow_state` | `created`, `running`, `waiting_for_input`, `blocked`, `succeeded`, `failed`, `cancelled` |
| `queue_state` | `new`, `triaged`, `assigned`, `awaiting_decision`, `ready`, `closed` |
| `approval_subject_kind` | `decision_packet`, `topic_lock`, `creative_lock`, `media_script_lock`, `media_shot_lock`, `content_revision`, `action_intent` |
| `approval_decision` | `select`, `approve`, `reject`, `request_changes`, `request_evidence`, `defer` |
| `execution_attempt_state` | `started` |
| `execution_terminal_outcome` | `succeeded`, `failed`, `cancelled`, `unknown` |
| `effect_status` | `confirmed`, `not_observed`, `failed`, `unknown` |
| `reconciliation_state` | `pending`, `confirmed`, `mismatch`, `not_applicable` |
| `verification_verdict` | `pass`, `pass_with_limits`, `fail`, `insufficient_evidence` |
| `attribution_strength` | `direct`, `deterministic`, `modeled`, `correlational`, `unattributed` |
| `metric_result_state` | `measured`, `insufficient_evidence`, `invalidated` |
| `gate_disposition` | `pass`, `fail`, `insufficient_evidence`, `not_applicable` |
| `lock_state` | `current`, `stale`, `superseded` |
| `handoff_state` | `draft`, `operator_confirmed`, `stale`, `superseded`, `rejected` |
| `handoff_outcome` | `content`, `action`, `request_evidence`, `defer`, `reject` |
| `outcome_family` | `compliance_protection`, `client_journey`, `revenue_partnerships`, `product_self_service`, `decision_intelligence`, `authority_demand`, `team_enablement`, `memory_learning`, `platform_governance` |

All contracts share these primitives:

| Primitive | Meaning |
|---|---|
| `contract_version` | Exact schema and semantics, initially `research-os/v1.0.0` |
| `tenant` | `bali-zero` unless a separately approved tenant exists |
| `lineage` | Input IDs/hashes plus the activity or run that produced the object |
| `producer` | Service, agent, script, or human role plus version |
| `valid_time` | Half-open interval `[valid_from, valid_to)` in the represented world; `null` end means open |
| `recorded_at` | Immutable system-time instant at which this object version entered Nuzantara; its effective interval is derived as `[recorded_at, successor.recorded_at)` without mutating the predecessor |
| `actor_ref` | Purpose-bound pseudonym, never raw identity in general ledgers |
| `retention` | Policy, expiry, legal hold, and rights expiry; revocation is a separate immutable receipt |
| `exact_object_ref` | `{object_kind, object_id, object_hash}`; a family ID alone is never exact identity |

Purpose-bound actors use:

```yaml
actor_ref:
  scheme: hmac-sha256
  key_version: non-secret key identifier
  purpose: approval | verification | queue_decision | assignment | execution | audit
  pseudonym: lowercase hex HMAC over tenant + purpose + internal subject ID
```

The HMAC key remains in the approved secret store. A pseudonym created for one purpose must not be reused to correlate a person across unrelated datasets.

Retention uses:

```yaml
retention:
  retention_class: public_record | operational | audit | restricted
  retain_until: timestamp?
  legal_hold: boolean
  rights_expires_at: timestamp?
```

### 3.1 `ObjectSuccessorEdge`

Purpose: make every correction, revision, and state change queryable without mutating either canonical object.

```yaml
object_successor_edge_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
object_kind: registered contract kind
family_id: stable namespaced family identifier
predecessor_ref: {object_kind, object_id, object_hash}
successor_ref: {object_kind, object_id, object_hash}
reason_code: registered namespaced string
recorded_at: timestamp
actor_ref?: purpose-bound actor reference
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- Predecessor and successor have the same `object_kind`, tenant, and `family_id`; both exact hashes must pass schema and hash validation. Cross-object classification policy may be deferred only to the end of the same atomic write transaction described in Rule 7; the bundle is not visible unless every required receipt validates.
- The successor has a later `recorded_at`; the graph is acyclic and a committed predecessor has at most one outgoing successor edge.
- The current object is the unique valid family member with no outgoing successor edge. Forks, missing nodes, hash mismatches, or cycles quarantine the family instead of selecting a winner.
- A successor object and its edge commit atomically. A risk- or sensitivity-lowering successor also includes its exact required receipt or receipts in that same transaction under deferred constraints. Replay resolves to the same bundle and never creates a second branch.
- This edge records succession only. It does not grant authority, execute an effect, or erase the predecessor.

### 3.2 `RevocationReceipt`

Purpose: invalidate one exact canonical object without changing the object or pretending that it never existed.

```yaml
revocation_receipt_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
target_ref: {object_kind, object_id, object_hash}
reason_code: registered namespaced string
authority: {role, scope, verified_at}
actor_ref: purpose-bound actor reference
required_propagation_targets: [{system, object_ref}]
classification: {risk_class, sensitivity}
issued_at: timestamp
idempotency_key: string
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- A valid receipt permanently invalidates only the exact target hash. The target and the receipt are immutable; no `unrevoke` mutation exists.
- If usable material must replace a revoked object, create a new canonical object and, where applicable, an `ObjectSuccessorEdge`; the revoked revision never becomes current again.
- Validators consult the canonical revocation index before accepting an approval, sanitization, risk reclassification, manifest, evidence, or other gate-bearing object.
- Issuing the `RevocationReceipt` itself is the fail-safe validity operation: its exact target, authority, and idempotency checks are its gate, so it can invalidate compromised authority immediately. Every downstream effect—withdrawal, cache purge, reindex, notification, reroute, or other propagation—requires its own `ActionItem`/`ActionIntent`, unexpired effect-specific `ApprovalReceipt`, immutable started `ExecutionAttempt`, typed terminal `OperationalReceipt`, and `OutcomeEvent`. Missing confirmation remains a blocking gap; revocation never silently implies that propagation succeeded.
- Duplicate idempotency keys for the same target resolve to the same receipt. Conflicting authority, target hash, or reason is quarantined.

## 4. `IntelEvent`

Purpose: immutable description of an observed or emitted event. Intel Lake owns the canonical record.

```yaml
event_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
event_type: registered namespaced string
producer: {name, version, machine_class}
source: {uri, native_id?, canonical_url?, source_type, jurisdiction?}
times: {published_at?, observed_at, ingested_at}
identity: {content_hash, normalized_hash?, idempotency_key}
classification: {language?, domain?, risk_class, sensitivity, rights?}
lineage: {pipeline_run_id, input_event_refs: [{event_id, object_hash}], parser_version?, model_version?, prompt_version?}
payload_ref: durable reference or validated inline public payload
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- `(producer.name, identity.idempotency_key)` is unique.
- `restricted_osint` or `client_pii` payloads are references to protected Pro storage, never copied into general event payloads.
- Replay creates delivery attempts, not duplicate canonical events.
- Mutable delivery truth lives in outbox and delivery receipts, not in the event.

## 5. `Evidence`

Purpose: an addressable source unit supporting or contradicting a claim.

```yaml
evidence_id: uuid
evidence_family_id: stable namespaced family identifier
supersedes_evidence_ref?: {evidence_id, object_hash}
contract_version: research-os/v1.0.0
tenant: bali-zero
source_event_ref: {event_id, object_hash}
document_id: stable identity of the source-document family
document_version_id: immutable source revision identity
document_content_hash: sha256
source_span: {locator, start?, end?, page?, section?, quote_hash}
source_tier: registered enum value
stance: supports | contradicts | contextualizes | inconclusive
times: {published_at?, observed_at, valid_from?, valid_to?, recorded_at}
provenance: {extractor, extractor_version, run_id, extraction_input_hash}
classification: {risk_class, sensitivity, rights}
review_state: closed enum
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- The document revision and its bytes are bound by `document_version_id` and `document_content_hash`; a stable URL alone is not evidence identity.
- A source span is reproducibly locatable and hash-verified when the format permits it.
- Short excerpts are stored only where rights and privacy policy permit; otherwise retain locator and hash.
- Syndicated copies do not count as independent corroboration.
- `evidence_family_id` maps to `ObjectSuccessorEdge.family_id`. Source replacement, review-state change, or later correction binds the exact current predecessor in `supersedes_evidence_ref` and atomically appends the new evidence object plus its successor edge; it never mutates or re-hashes the old object. The successor has a later `times.recorded_at`; forks or stale predecessors quarantine the family. The effective system interval is derived from the successor chain.

## 6. `Claim`

Purpose: smallest consequential proposition that can be checked, timed, contradicted, expired, or superseded. NAGA owns the canonical ledger; NEXUS may hold restricted projections linked by ID.

```yaml
claim_id: uuid
claim_family_id: uuid
supersedes_claim_ref?: {claim_id, object_hash}
contract_version: research-os/v1.0.0
tenant: bali-zero
statement: {subject_ref, predicate, object_ref_or_value, unit?, currency?, modality?}
scope: {jurisdiction?, audience?, domain}
time: {valid_from?, valid_to?, recorded_at}
status: supported | contradicted | inconclusive | superseded | expired
evidence_refs: [{evidence_id, object_hash, stance}]
confidence: {score, method, calibrated_on?}
classification: {risk_class, sensitivity}
review: {state, reviewer_ref?, reviewed_at?, rationale_code?}
lineage: {run_id, extractor, model_version?, prompt_version?, input_claim_refs: [{claim_id, object_hash}]}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- `claim_id` identifies one immutable claim version. `claim_family_id` connects versions of the same proposition; `supersedes_claim_ref` binds the exact predecessor and forms an acyclic chain.
- Each claim is atomic enough for one truth status and one valid-time interval. Automated atomization is optional until its evaluator passes; atomic storage is mandatory.
- Consequential numeric and regulatory claims require evidence and explicit valid time before approval.
- Valid intervals are stored half-open. Effective system-time intervals are derived from immutable `recorded_at` values and the successor chain; appending the successor claim and its supersession edge is one transaction, and the predecessor is never updated.
- `status` is the status recorded for this immutable version. A later contradiction, expiry, review, or supersession appends another claim version; current status is projected from the latest valid, unsuperseded version.
- Confidence is not truth and cannot override a contradiction or missing mandatory evidence.
- No red claim enters a public `ContentObject`.

## 7. `DecisionPacket`

Purpose: concise, traceable proposal presented to the operator or team.

```yaml
decision_packet_id: uuid
decision_packet_family_id: stable namespaced family identifier
revision: positive integer
supersedes_decision_packet_ref?: {decision_packet_id, object_hash}
contract_version: research-os/v1.0.0
tenant: bali-zero
title: string
why_now: string
outcome_family: closed enum
claim_refs: [{claim_id, object_hash}]
evidence_refs: [{evidence_id, object_hash}]
source_document_refs: [{document_id, document_version_id, document_content_hash}]
evidence_summary: structured citation-bearing summary
novelty: {score, basis, compared_window}
risk_analysis: {reasons: [], unresolved_questions: []}
recommended_action: {action_type, target_surface, owner_ref?, due_at?, expected_outcome?}
alternatives: []
downstream_candidates: []
classification: {risk_class, sensitivity}
recorded_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: [], code_version?, model_version?, prompt_version?}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- `why_now` is grounded in time, change, opportunity, or risk.
- A packet may be selected, rejected, returned for changes or evidence, or deferred through a separate exact `ApprovalReceipt` with `subject.kind=decision_packet`. Editing creates a successor packet plus `ObjectSuccessorEdge`, not a receipt. Queue assignment, snooze, triage, split, merge, and closure operate on `ActionItem` successors with registered typed `OperationalReceipt` objects; they never mutate or approve the packet.
- Every cited claim, evidence item, and source-document revision is an exact immutable reference. `evidence_summary` is explanatory and cannot substitute for those references. Producer and lineage fields bind the packet to the exact workflow and inputs that created it.
- `decision_packet_family_id` maps to `ObjectSuccessorEdge.family_id`. An edited packet is a new revision that binds the exact current predecessor, has a later `recorded_at`, and commits atomically with its successor edge; a queue decision never mutates the packet.
- NEXUS-derived packets require a separate valid `SanitizationReceipt` indexed by the exact packet hash and carry no protected graph details. The packet never embeds that receipt ID because the receipt binds the packet hash.

## 8. Operator decision objects

These objects preserve human editorial judgment and action requests without turning conversational text into authority. They are immutable proposals or selections; every approval remains a separate `ApprovalReceipt` bound to the exact object hash.

### 8.1 `TopicLock`

```yaml
topic_lock_id: uuid
topic_lock_family_id: stable namespaced family identifier
contract_version: research-os/v1.0.0
tenant: bali-zero
decision_packet_ref: {decision_packet_id, object_hash}
topic: string
angle: string
audience: structured audience
why_now: string
claim_refs: [{claim_id, object_hash}]
source_refs: [{source_id, version_id, content_hash}]
must_resolve_before_use: []
classification: {risk_class, sensitivity}
lock_version: positive integer
state: current | stale | superseded
supersedes_topic_lock_ref?: {topic_lock_id, object_hash}
recorded_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

### 8.2 `CreativeLock`

```yaml
creative_lock_id: uuid
creative_lock_family_id: stable namespaced family identifier
contract_version: research-os/v1.0.0
tenant: bali-zero
topic_lock_ref: {topic_lock_id, object_hash}
promise: string
tone: structured register
narrative_arc: structured beats
must_keep: [structured constraint]
must_avoid: [structured constraint]
channel_intent: [{surface, objective, cta}]
reference_assets: [{asset_ref: {asset_id, content_hash}, purpose, rights_state, risk_class, sensitivity}]
classification: {risk_class, sensitivity}
lock_version: positive integer
state: current | stale | superseded
supersedes_creative_lock_ref?: {creative_lock_id, object_hash}
recorded_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

### 8.3 `RequestedActionSpec`

Purpose: a side-effect-free action proposal produced during Conductor deliberation. It is not an Action Inbox record, an `ActionIntent`, or execution authority.

```yaml
requested_action_spec_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
decision_packet_ref: {decision_packet_id, object_hash}
action_type: registered namespaced string
target: {system, object_ref, surface?}
arguments_ref: protected or public durable reference
arguments_hash: sha256
input_revision_hash: sha256
risk_class: green | amber | red
sensitivity: public | internal | confidential | restricted_osint | client_pii
authority_required: {role, scope, expires_after_seconds}
expected_outcome_types: [registered namespaced string]
suggested_owner_ref?: purpose-bound actor reference
suggested_due_at?: timestamp
recorded_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Shared invariants:

- A Topic or Creative Lock is selected only when a separate, unexpired `ApprovalReceipt` binds its exact proposal hash. Locks never embed their own approval receipt IDs.
- A Topic Lock approval authorizes only selection of that topic revision. A Creative Lock approval authorizes only selection of that creative revision. Neither authorizes content approval, rendering, spend, staging, publication, send, or another external effect.
- Every referenced asset carries an immutable asset identity/content hash and both classification axes. A `CreativeLock` cannot weaken the risk, sensitivity, unresolved questions, or must-keep constraints inherited through its Topic Lock. Its mandatory classification is the component-wise maximum of the exact Topic Lock and every exact referenced asset. A distinct successor may lower sensitivity only with an exact `SanitizationReceipt`, lower risk only with an exact `RiskReclassificationReceipt`, and lower both only with both receipts indexed by the exact output hash.
- Each lock-family field maps to `ObjectSuccessorEdge.family_id`. A revised lock binds the exact current predecessor, has a later `recorded_at`, and commits atomically with its successor edge; forks or stale predecessors quarantine the family.
- A `RequestedActionSpec` carries no queue state, approval state, execution state, or receipt ID. Packet 04 provides the one canonical, side-effect-free repository primitive that atomically materializes one `ActionItem` and one `ActionIntent` from its exact hash; replay must resolve to the same pair. Packet 12 is the sole general runtime service around that primitive. Before Packet 12 exists, Packet 01 Task 7 may invoke it only through the separately reviewed containment/manual adapter restricted to its five enumerated NEXUS effects and only when the spec binds the exact sanitized containment `DecisionPacket` and its exact `WorkflowRun`; this is not a parallel action path and cannot execute an effect.

## 9. `ContentObject`

Purpose: one editorial or product object from which channel-specific derivatives are created.

```yaml
content_object_id: uuid
content_object_family_id: stable namespaced family identifier
contract_version: research-os/v1.0.0
tenant: bali-zero
origin_decision_packet_ref: {decision_packet_id, object_hash}
revision: positive integer
supersedes_content_object_ref?: {content_object_id, revision, object_hash}
topic_lock_ref: {topic_lock_id, object_hash}
creative_lock_ref: {creative_lock_id, object_hash}
claim_refs: [{claim_id, object_hash}]
evidence_refs: [{evidence_id, object_hash}]
source_document_refs: [{document_id, document_version_id, document_content_hash}]
classification: {risk_class: green | amber | red, sensitivity: public | internal | confidential | restricted_osint | client_pii}
channel_plan: [{surface, objective, cta, status}]
publication_state: generated | staged | human_approved | publishing | deployed | indexed_verified
verification_state: unverified | verified | stale
availability:
  state: active | correction_required | withdrawal_requested | withdrawn
  severity: low | medium | high | critical
  reason_code: string?
  requested_at: timestamp?
  required_by: timestamp?
  resolved_at: timestamp?
campaign_id?: string
recorded_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: [], code_version?, model_version?, prompt_version?}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- The three axes are independent. Publication history is monotonic; verification may become stale; availability may require correction or withdrawal. Receipt ledgers reference the content hash; the content object does not embed self-referential receipt IDs.
- `origin_decision_packet_ref`, every claim/evidence reference, and every source-document revision bind both stable identity and exact immutable content. `lineage.input_hashes` supplements these mappings and cannot substitute for them.
- `content_object_family_id` maps to `ObjectSuccessorEdge.family_id`. Revision greater than one requires the exact current predecessor and an atomic successor edge; revision forks or non-monotonic `recorded_at` quarantine the family.
- Internal fast-track never sets `human_approved`, `deployed`, or `indexed_verified`.
- `deployed` requires a live canonical URL proof and matching artifact or revision hash. Deployment logs alone are supporting evidence, not proof.
- `indexed_verified` requires an approved read-only index inspection receipt; URL submission, sitemap membership, HTTP 200, or crawl request is insufficient.
- A correction never rewrites publication history. It appends an availability event, opens an Action Inbox item under the severity SLA, and creates a new content revision if approved.
- `withdrawal_requested` is not removal. Only a specifically approved execution may set `withdrawn`, with a successful exact `OperationalReceipt`.
- Derivatives inherit topic, claims, sources, risk, sensitivity, approval requirements, rights, and revocations. A distinct output revision may lower sensitivity only with a valid `SanitizationReceipt`, lower risk only with a valid `RiskReclassificationReceipt`, and lower both only with both receipts indexed by that exact output hash.
- Expired, contradicted, superseded, or revoked inputs set `verification_state=stale` and require downstream propagation to caches, vectors, materialized views, media, and reports.

## 10. `MediaManifest`

Purpose: reproducible, rights-aware manifest for WR2, WR3, and other media.

```yaml
media_manifest_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
content_object_ref: {content_object_id, revision, object_hash}
media_type: carousel | video | image | audio
claim_refs: [{claim_id, object_hash}]
classification: {risk_class: green | amber | red, sensitivity: public | internal | confidential | restricted_osint | client_pii}
assets: [{asset_id, sha256, risk_class, sensitivity, source, derivation, rights, rights_expires_at?, prompt_ref?, model?, seed?, tool_version?}]
timeline_or_slides: durable structured reference with sha256
quality: {checks: [], critic_target_hash: sha256?}
platform_specs: [{platform, aspect_ratio, safe_zone, duration_or_count}]
audio?: {transcript_hash, subtitle_hash, loudness_lufs, sync_result}
identity?: {anchor_ref, verification_result}
producer: {name, version}
lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: [], code_version?, model_version?, prompt_version?}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- Silent placeholder or anchor reuse is forbidden; hashes make reuse explicit.
- `content_object_ref` and every claim reference are mandatory exact inputs; a family ID, mutable current lookup, or bare revision number is invalid.
- Every asset entry binds immutable asset identity/content hash and both classification axes. The manifest classification is the component-wise maximum of the exact ContentObject revision and every exact asset input. A distinct media derivative may lower sensitivity only with a purpose- and destination-bound `SanitizationReceipt`, lower risk only with a `RiskReclassificationReceipt`, and lower both only with both receipts indexed by that exact output hash; producer and lineage remain mandatory in every case.
- Every hero or clip declares source, derivation, and rights status.
- Rights expiry or source revocation creates a `RevocationReceipt` for the exact manifest or affected asset-bearing object and propagates to every derived cache and publication review queue. The manifest itself is never updated with a mutable revocation flag.
- Manifest completeness is required before staging. Critic, human-review, and publication receipts bind the manifest hash from their own ledgers; the manifest never embeds a receipt that depends on that same hash.
- C2PA, if adopted, supplements the manifest; it does not establish factual truth.

## 11. `StoryCluster`

Purpose: preserve one evolving story without mistaking syndication for corroboration.

```yaml
story_cluster_id: uuid
story_cluster_family_id: uuid
revision: positive integer
contract_version: research-os/v1.0.0
tenant: bali-zero
predecessor_refs: [{story_cluster_id, object_hash, operation: merge | split | canonical_change}]
canonical_event_ref: {event_id, object_hash}
members:
  - event_ref: {event_id, object_hash}
    relationship: exact | near | syndicated | translation | update | same_event
    source_group_id: string
    relation_score: 0..1
independent_source_groups: [string]
decision:
  layers_run: [exact, normalized, near, semantic, human]
  thresholds_version: string
  verdict: merged | split | review
  reasons: [code]
  decided_by: deterministic | model | human
  decided_at: timestamp
recorded_at: timestamp
classification: {risk_class, sensitivity}
producer: {name, version}
lineage: {run_id, code_version, model_version?, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- Deterministic layers run before semantic or model layers.
- Ambiguous clusters go to review. Merge, split, and canonical-change operations create new immutable cluster revisions; the predecessor graph preserves every old cluster and makes the operation reversible without a self-referential after-hash.
- Independent corroboration counts distinct `source_group_id` values, not member count.
- Every canonical event and member reference is exact. A single-family canonical correction uses `ObjectSuccessorEdge`; merge and split lineage uses the explicit exact `predecessor_refs` because those operations may cross cluster families. No merge or split edge is interpreted as authority or allowed to choose a current family member implicitly.

## 12. `WorkflowRun`

Purpose: replayable execution history for a versioned workflow.

```yaml
workflow_run_id: uuid
workflow_run_family_id: stable namespaced family identifier
run_revision: positive integer
supersedes_workflow_run_ref?: {workflow_run_id, object_hash}
contract_version: research-os/v1.0.0
tenant: bali-zero
workflow: {name, version}
state: closed workflow_state
inputs: [{object_kind, object_id, object_hash}]
steps:
  - step_id: string
    attempt_ids: [uuid]
    state: workflow_state
    input_hash: sha256
    output_hash?: sha256
    idempotency_key: string
    lease: {owner_ref?, acquired_at?, expires_at?}
    tools_models: [{name, version}]
    started_at?: timestamp
    ended_at?: timestamp
    error_code?: string
cost: {unit, estimated, actual?, ceiling}
classification: {risk_class, sensitivity}
started_at: timestamp
ended_at?: timestamp
recorded_at: timestamp
producer: {name, version}
lineage: {input_hashes: [], code_version, model_version?, prompt_version?}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- A `WorkflowRun` is an immutable coordination snapshot, never execution authority or terminal effect truth. Every state or step change appends a later run revision in the same family, binds the exact current predecessor, and atomically commits its `ObjectSuccessorEdge`; the current dashboard row is a rebuildable projection.
- Resume may rerun a step; all effects are idempotent and separately receipted through the canonical action chain.
- A run cannot claim success while any mandatory step is failed, unknown, or unreceipted.
- Cost ceilings fail closed before spend.
- Retention expiry removes or anonymizes payload references according to policy while preserving minimum audit receipts.

## 13. Decision, authority, and execution contracts

### 13.1 `ActionItem`

`ActionItem` is the Action Inbox queue record. It records attention and ownership, not approval or execution truth.

```yaml
action_item_id: uuid
action_item_family_id: stable namespaced family identifier
revision: positive integer
supersedes_action_item_ref?: {action_item_id, object_hash}
contract_version: research-os/v1.0.0
tenant: bali-zero
decision_packet_ref: {decision_packet_id, object_hash}
requested_action_spec_ref: {requested_action_spec_id, object_hash}
queue_state: new | triaged | assigned | awaiting_decision | ready | closed
owner_ref?: actor_ref
risk_class: green | amber | red
sensitivity: public | internal | confidential | restricted_osint | client_pii
priority: p0 | p1 | p2 | p3
sla: {opened_at, due_at, paused_at?, breached_at?}
current_intent_ref?: {action_intent_id, object_hash}
close_reason?: completed | rejected | duplicate | obsolete | invalid
created_at: timestamp
recorded_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

### 13.2 `ActionIntent`

```yaml
action_intent_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
action_item_ref: {action_item_id, object_hash}
requested_action_spec_ref: {requested_action_spec_id, object_hash}
action_type: registered namespaced string
target: {system, object_ref, surface?}
arguments_ref: protected or public durable reference
arguments_hash: sha256
input_revision_hash: sha256
risk_class: green | amber | red
sensitivity: public | internal | confidential | restricted_osint | client_pii
authority_required: {role, scope, expires_after_seconds}
idempotency_key: string
expected_outcome_types: [registered namespaced string]
created_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

### 13.3 `ApprovalReceipt`

```yaml
approval_receipt_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
subject: {kind: decision_packet | topic_lock | creative_lock | media_script_lock | media_shot_lock | content_revision | action_intent, object_id, object_hash}
context:
  action_item_ref?: {action_item_id, object_hash}
  workflow_run_ref?: {workflow_run_id, object_hash}
decision: select | approve | reject | request_changes | request_evidence | defer
actor_ref: purpose-bound actor reference
authority: {role, scope, verified_at}
bindings: {input_revision_hash, arguments_hash?}
before_hash?: sha256
after_hash?: sha256
authorized_effects: [registered namespaced string]
rationale_code: string
classification: {risk_class: green | amber | red, sensitivity: public | internal | confidential | restricted_osint | client_pii}
issued_at: timestamp
expires_at: timestamp
idempotency_key: string
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

### 13.4 `ExecutionAttempt`

```yaml
execution_attempt_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
action_intent_ref: {action_intent_id, object_hash}
approval_receipt_ref: {approval_receipt_id, object_hash}
attempt_number: positive integer
state: started
idempotency_key: string
executor: {name, version, actor_ref?}
started_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

### 13.5 `OperationalReceipt`

Purpose: record an immutable execution result or other typed operational acknowledgment without updating the originating attempt or action.

```yaml
operational_receipt_id: uuid
operational_receipt_family_id: stable namespaced family identifier
contract_version: research-os/v1.0.0
tenant: bali-zero
receipt_type: registered namespaced string
supersedes_operational_receipt_ref?: {operational_receipt_id, object_hash}
subject_refs: [{object_kind, object_id, object_hash}]
execution_attempt_ref?: {execution_attempt_id, object_hash}
classification: {risk_class, sensitivity}
actor_or_executor: {producer: {name, version}, actor_ref?}
terminal_outcome?: succeeded | failed | cancelled | unknown
outcome_code: registered namespaced string
effects: [{effect_type, target_ref?: {object_kind, object_id, object_hash}, status: confirmed | not_observed | failed | unknown}]
artifact_refs: [{object_kind, object_id, object_hash}]
evidence_refs: [{object_kind, object_id, object_hash}]
observed_at: timestamp
recorded_at: timestamp
idempotency_key: string
reconciliation: {state: pending | confirmed | mismatch | not_applicable, checked_at?, evidence_refs: [{object_kind, object_id, object_hash}]}
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

The v1 registry includes at least `execution.result`, `team.acknowledgment`, `team.partial`, `team.completion`, `team.blocked`, `team.cancelled`, `team.superseded`, `routing.assignment`, `queue.triage`, `queue.rejected`, `queue.snoozed`, `queue.split`, `queue.merge_duplicate`, `queue.evidence_requested`, and `revocation.propagation`. Domain packets may register additional receipt types through Packet 04 compatibility review; they may not redefine this envelope.

Shared invariants:

- Allowed subject/decision pairs are closed: `decision_packet` accepts `select`, `reject`, `request_changes`, `request_evidence`, or `defer`; `topic_lock`, `creative_lock`, `media_script_lock`, `media_shot_lock`, and `content_revision` accept `approve`, `reject`, or `request_changes`; `action_intent` accepts `approve`, `reject`, or `request_changes`. Every other pair fails validation.
- No action class executes without an unexpired `approve` receipt whose subject is the exact `ActionIntent` hash and whose bindings match the exact `arguments_hash` and `input_revision_hash`, including low-risk internal changes. Only this exact subject/decision pair may carry nonempty `authorized_effects` or authorize an `ExecutionAttempt`; every other valid pair requires `authorized_effects=[]` and creates no attempt.
- When an `ActionIntent` is materialized from a `RequestedActionSpec`, both the initial `ActionItem` and the `ActionIntent` retain the exact spec reference. The complete authorization-bearing fields—action type, target, arguments reference and hash, input revision hash, risk, sensitivity, authority, and expected outcomes—transfer losslessly into the `ActionIntent`; the `ActionItem` carries only queue semantics, exact source references, risk, sensitivity, ownership, priority, and SLA. Replay resolves to the same initial ActionItem/ActionIntent pair.
- `ActionItem` versions are immutable queue snapshots. Assignment, decision readiness, intent linkage, closure, or SLA change appends a new revision in the same `action_item_family_id`, binds `supersedes_action_item_ref`, and atomically commits its `ObjectSuccessorEdge`. When `current_intent_ref` is present it is exact; dashboards are rebuildable projections and never authority.
- An action approval requires exact `context.action_item_ref`, `bindings.arguments_hash`, and classification matching the action intent; lock and editorial approvals reject action-only fields unless their specialization explicitly requires them.
- A queue-only triage, assignment, snooze, rejection, split, merge-duplicate, evidence-request, or closure atomically appends the next `ActionItem` revision, its `ObjectSuccessorEdge`, and the registered typed `OperationalReceipt`. It requires role permission and exact before/after hashes, carries no `ExecutionAttempt`, has no `ApprovalReceipt` subject, and cannot authorize a downstream effect. If a queue rejection also rejects the underlying `DecisionPacket`, that substantive decision requires its own exact `decision_packet` `reject` receipt.
- An approval authorizes only named effects. Material input change invalidates it.
- A valid `RevocationReceipt` targeting an exact approval invalidates that approval permanently; neither the approval nor its revocation is mutated.
- `ExecutionAttempt` is created only when invocation actually starts and is immutable in `started` state. Planning belongs to the intent; terminal truth belongs to a separate `OperationalReceipt`.
- An `execution.result` receipt requires the exact attempt ID/hash and one terminal outcome. There is one current result per attempt; retries create new numbered attempts. Duplicate idempotency resolves to the same receipt.
- `operational_receipt_family_id` is the `family_id` used by `ObjectSuccessorEdge`. An initial receipt has no supersedes reference. A correction binds the exact current predecessor in `supersedes_operational_receipt_ref`, preserves tenant, receipt type, subject/attempt family, and family ID, has a later `recorded_at`, and commits atomically with the successor edge. Forks, hash mismatch, non-current predecessors, or two current receipts quarantine the family rather than choosing a result.
- Other operational receipt types bind every exact action/revision they concern and use their registered required-field profile. A team acknowledgment cannot be interpreted as approval, completion, or external success.
- Queue state, approval decision, execution attempt, operational result, and observed outcome are derived from their own records and never collapsed into one mutable status.
- Generator, consequential verifier, approver, and executor roles are distinct where independence is required.

## 14. `VerificationReceipt`

Purpose: independent, reproducible judgment over exact object revisions.

```yaml
verification_receipt_id: uuid
verification_receipt_family_id: stable namespaced family identifier
contract_version: research-os/v1.0.0
tenant: bali-zero
supersedes_verification_receipt_ref?: {verification_receipt_id, object_hash}
target_objects: [{object_kind, object_id, object_hash}]
verification_type: registered namespaced string
verifier: {name, version, actor_ref?, independence_class}
criteria_version: string
temporal_scope: {target_valid_from?, target_valid_to?, source_cutoff_at?, checked_at}
checks: [{check_id, result: pass | fail | not_applicable | insufficient_evidence, evidence_refs: [{object_kind, object_id, object_hash}], note_code?}]
verdict: pass | pass_with_limits | fail | insufficient_evidence
limits: []
source_versions: [{source_id, version_id, content_hash}]
classification: {risk_class, sensitivity}
issued_at: timestamp
recorded_at: timestamp
expires_at?: timestamp
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- A verifier cannot approve an object hash it generated when the gate requires independence.
- `verification_receipt_family_id` maps to `ObjectSuccessorEdge.family_id`. A correction—not a genuinely new verification attempt—binds the exact current predecessor, has a later `recorded_at`, and commits atomically with its successor edge; a fork cannot satisfy a gate.
- Changed target hash, criterion version, temporal scope, or required source version/hash invalidates the receipt.
- `pass_with_limits` cannot be interpreted as unrestricted approval.
- Domain findings such as support, contradiction, routing failure, or source staleness live in a namespaced extension; they never redefine the canonical verdict.

## 15. `ConductorHandoff`

Purpose: durable bridge between the operator–AI session and deterministic systems without storing hidden reasoning.

```yaml
conductor_handoff_id: uuid
conductor_handoff_family_id: stable namespaced family identifier
contract_version: research-os/v1.0.0
tenant: bali-zero
session_ref: {scheme, purpose, opaque_id, record_hash, protected_transcript_ref?}
operator_actor_ref: purpose-bound actor reference
assistant_producer: {provider, model, model_version, prompt_version}
operator_inputs: [{input_id, content_hash, sensitivity}]
decision_packet_refs: [{decision_packet_id, object_hash}]
verification_receipt_refs: [{verification_receipt_id, object_hash}]
considered_options: [{option_id, disposition: selected | rejected | deferred, reason_code}]
topic_lock_ref?: {topic_lock_id, object_hash}
creative_lock_ref?: {creative_lock_id, object_hash}
requested_action_spec_refs: [{requested_action_spec_id, object_hash}]
decision: {outcome: content | action | request_evidence | defer | reject, rationale_codes: []}
unresolved_questions: []
handoff_summary: concise decision record
classification: {risk_class, sensitivity}
workflow_run_ref: {workflow_run_id, object_hash}
state: draft | operator_confirmed | stale | superseded | rejected
supersedes_conductor_handoff_ref?: {conductor_handoff_id, object_hash}
created_at: timestamp
recorded_at: timestamp
expires_at?: timestamp
producer: {name, version}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- The contract stores decisions, hashed inputs, alternatives, and lock/spec references—not private chain-of-thought. A protected transcript reference is purpose-bound, access-controlled, and covered by the handoff retention policy.
- `conductor_handoff_family_id` maps to `ObjectSuccessorEdge.family_id`. A revised handoff binds the exact current predecessor and commits atomically with its successor edge; reconnect/replay cannot fork the family.
- A lower-sensitivity handoff requires a separate `SanitizationReceipt` indexed by the exact handoff hash; the handoff never embeds the receipt that binds it.
- No action follows from conversational text alone. The Packet 04 canonical primitive atomically turns a requested action spec into `ActionItem` plus `ActionIntent`; Packet 12 is its sole general runtime service, while Packet 01 has only the five-effect containment/manual exception defined above. Only a later exact `ApprovalReceipt` can authorize an `ExecutionAttempt`.
- A downstream foundry must preserve the exact hash of the lock it consumes.
- The normal flow is one-way: `DecisionPacket` → `ConductorHandoff` with `RequestedActionSpec` → Packet 12 calling the Packet 04 primitive to create `ActionItem` + `ActionIntent` → operator decision → `ApprovalReceipt` → immutable started `ExecutionAttempt` → typed `OperationalReceipt` → `OutcomeEvent`. The Packet 01 containment/manual exception starts from one exact sanitized, operator-authored containment `DecisionPacket` grounded in an exact durable source-document revision, a canonical `IntelEvent` → `Evidence` → `Claim` chain, an independent pre-cutover `VerificationReceipt`, and an exact `WorkflowRun`; its intermediate objects retain inherited classification and the lower-sensitivity packet has its exact `SanitizationReceipt`. It then creates five packet- and run-bound `RequestedActionSpec` objects, calls the same primitive, and rejoins this chain at `ActionItem` + `ActionIntent`; it never bypasses approval, fabricates upstream objects, lowers classification without the correct receipt, or creates a second ledger.
- The interactive assistant may critique and revise its own creative proposal with the operator, but cannot satisfy an independent factual verifier, release critic, approval, or execution authority.
- A single interface may show several decisions, but each selected lock, content approval, publication approval, and action approval receives a separate receipt. Bulk “approve all” is invalid.

## 16. `OutcomeEvent`

Purpose: return what happened to the evidence spine. Work Packet 04 owns the canonical event and repository; domain packets own adapters and projections.

```yaml
outcome_event_id: uuid
outcome_event_family_id: stable namespaced family identifier
contract_version: research-os/v1.0.0
tenant: bali-zero
supersedes_outcome_event_ref?: {outcome_event_id, object_hash}
subject_refs:
  decision_packet_ref?: {decision_packet_id, object_hash}
  content_object_ref?: {content_object_id, revision, object_hash}
  artifact_revision_ref?: {artifact_revision_id, artifact_sha256}
  verification_receipt_ref?: {verification_receipt_id, object_hash}
  action_intent_ref?: {action_intent_id, object_hash}
  execution_attempt_ref?: {execution_attempt_id, object_hash}
  operational_receipt_ref?: {operational_receipt_id, object_hash}
  claim_refs: [{claim_id, object_hash}]
  campaign_ref?: {campaign_id, revision?, object_hash}
  workflow_run_ref?: {workflow_run_id, object_hash}
metric_profile_ref?: {metric_profile_id, object_hash}
metric_result_ref?: {metric_result_id, object_hash}
outcome_type: registered namespaced string
value: typed value
window: {started_at, ended_at}
source_system: GSC | GA4 | CRM | social | workflow | human_review | platform | product | compliance
quality: {attribution_strength, completeness, caveats: [], collection_version}
cohort: {size?, minimum_required?, suppressed: boolean}
observed_at: timestamp
recorded_at: timestamp
classification: {risk_class, sensitivity, aggregation_level}
retention: retention object
idempotency_key: string
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: [], code_version?, model_version?, prompt_version?}
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- Submission is not indexing; engagement is not conversion; correlation is not causal attribution.
- Every subject reference resolves to the exact revision/hash observed. A family ID, URL, title, queue ID, or mutable current-state lookup is insufficient.
- A corrected or late-arriving replacement remains in the same `outcome_event_family_id`, binds the exact current predecessor, has a later `recorded_at`, and commits atomically with its `ObjectSuccessorEdge`. Independent observations use distinct families. Forks are quarantined and cannot feed a metric or release gate.
- An event reporting a publication/action side effect binds the applicable exact content/artifact, `ActionIntent`, immutable started `ExecutionAttempt`, and successful typed `OperationalReceipt`; it cannot advance state from a family ID alone. The read-only `deployed → indexed_verified` transition is different: it binds the exact content/artifact and an independent, unexpired `VerificationReceipt` over the canonical-URL observation. It does not fabricate an execution chain when no outward or consequential operational effect occurred.
- `metric_profile_ref` and `metric_result_ref` are jointly present or jointly absent. Every metric-bearing event must bind both exact hashes to a valid preregistered profile and its result; a non-metric operational event must bind neither and must not fabricate a measurement.
- General-ledger CRM projections suppress or aggregate cohorts smaller than 10. More restrictive domain policy wins. Unsuppressed client rows remain in the protected CRM only.
- Missing, incomplete, or too-small samples emit `insufficient_evidence`; they are not zero outcomes.
- Retention and consent revocation propagate to materialized views, vector indexes, caches, and derived reports.

## 17. `SanitizationReceipt`

Purpose: authorize one lower-sensitivity projection for a named purpose and destination. It does not lower factual, legal, editorial, or operational risk.

```yaml
sanitization_receipt_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
source_objects: [{object_kind, object_id, object_hash, classification: {risk_class, sensitivity}}]
output_object: {object_kind, object_id, object_hash, classification: {risk_class, sensitivity}}
policy: {name, version}
transformations: [{field_path, operation: remove | generalize | aggregate | pseudonymize, result_sensitivity}]
residual_risk: {rating, findings: []}
reviewer_ref: purpose-bound actor reference
permitted_use: {purpose, destination, consumer, expires_at}
issued_at: timestamp
propagation_scope: [{system, object_ref}]
producer: {name, version}
lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- Sanitization never changes the protected source.
- Every sensitivity decrease is explicit and field-level. The output may carry a lower sensitivity only when the receipt names that exact decrease, destination, residual risk, and expiry. This receipt cannot lower `risk_class`; a risk decrease requires a separate `RiskReclassificationReceipt` over a distinct corrected/remediated successor.
- The lower-sensitivity output and this receipt commit atomically with deferred cross-object constraints; if the output is a successor, its exact `ObjectSuccessorEdge` is in the same write-set. If risk also decreases, the exact `RiskReclassificationReceipt` is included too. Any missing, mismatched, or invalid member rolls back the entire bundle.
- Receipt expiry or a separate `RevocationReceipt` targeting its exact hash invalidates every descendant and opens an Action Inbox item.
- Revocation propagation to caches, Qdrant/vector projections, materialized views, generated media, reports, and pending drafts is recorded through typed `revocation.propagation` `OperationalReceipt` objects; unconfirmed targets remain a blocking gap.
- A receipt is purpose- and destination-bound and cannot be reused for another audience.
- The output object does not embed this receipt ID. The receipt is retrieved by its exact `output_object.object_hash`, avoiding a circular hash dependency.

## 18. `RiskReclassificationReceipt`

Purpose: justify a lower canonical risk class only after a distinct successor has corrected or remediated the reason the predecessor was riskier. It is not a privacy transformation, publication approval, or permission to ignore unresolved evidence.

```yaml
risk_reclassification_receipt_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
source_object: {object_kind, object_id, object_hash, risk_class, sensitivity}
output_object: {object_kind, object_id, object_hash, risk_class, sensitivity}
supersession_ref: {object_successor_edge_id, object_hash}
remediation:
  type: authoritative_source_added | contradiction_resolved | grounding_repaired | prohibited_scope_removed | classification_error_corrected
  reason_codes: [registered string]
  changed_field_paths: [field path]
claim_refs: [{claim_id, object_hash}]
evidence_refs: [{evidence_id, object_hash}]
verification_receipt_refs: [{verification_receipt_id, object_hash}]
policy: {name, version}
reviewer: {actor_ref, independence_class}
residual_risk: {risk_class, findings: []}
permitted_use: {purpose, destination, consumer, expires_at?}
issued_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- The output is a distinct immutable successor of the exact source object; the receipt never rewrites or relabels the predecessor.
- The corrected successor, exact `ObjectSuccessorEdge`, and this receipt commit atomically with deferred cross-object constraints. If sensitivity also decreases, the exact `SanitizationReceipt` for the same output hash and destination is in the same write-set. Any missing, mismatched, or invalid member rolls back the entire bundle; replay returns the same bundle.
- The new risk class must equal the deterministic policy result over the corrected output and exact current claim/evidence/verification inputs. Missing evidence, unresolved contradiction, expired verification, or a failed hard guard cannot support a decrease.
- The reviewer must be independent of the producer that performed the remediation when the policy gate requires independence.
- Sensitivity cannot decrease under this receipt. If the successor also lowers sensitivity, an exact valid `SanitizationReceipt` is separately required for the same output hash and destination.
- The receipt is retrieved by exact `output_object.object_hash`; the output does not embed the receipt and cannot create a circular identity.
- Expiry, source revocation, claim contradiction, or invalidated verification marks the successor stale and opens the applicable Action Inbox review; it does not silently restore or invent a class.

## 19. `MetricProfile`

Purpose: prevent thresholds and dashboards from becoming post-hoc narratives.

```yaml
metric_profile_id: uuid
contract_version: research-os/v1.0.0
tenant: bali-zero
metric_name: registered namespaced string
question: string
unit: string
numerator: exact definition or null
denominator: exact definition or null
window: {type, duration, timezone, late_arrival_policy}
baseline: {source, window, frozen_at}
evaluation_data:
  dataset_ref: {dataset_id, version, object_hash}
  split: {strategy, assignment_hash}
  exclusion_rules: [{rule_id, definition_hash}]
minimum_sample: {overall, per_subgroup?, power_target?}
estimator: {method, version, confidence_interval_or_bootstrap}
subgroups: [{name, definition}]
guardrails: [{metric_name, direction, threshold}]
decision_rule: preregistered expression
missing_data_policy: exclude | impute_registered | insufficient_evidence
owner_ref: purpose-bound actor reference
validity: {valid_from, expires_at}
classification: {risk_class, sensitivity}
created_at: timestamp
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- Dataset/version/hash, split assignment, numerator, denominator, sample floor or power target, window, exclusions, estimator, confidence method, owner, expiry, and decision rule are frozen before evaluation.
- No improvement claim is valid if a guardrail fails, a subgroup is silently dropped, or the sample floor is unmet.
- An expired profile cannot govern a new measurement or release decision.
- Operational reconciliation metrics cover the union of old and new paths; hiding a legacy source cannot count as deduplication.

## 20. `MetricResult`

Purpose: bind one observed measurement to the exact preregistered profile that governed it, without putting terminal results into the profile itself.

```yaml
metric_result_id: uuid
metric_result_family_id: stable namespaced identifier
supersedes_metric_result_ref?: {metric_result_id, object_hash}
contract_version: research-os/v1.0.0
tenant: bali-zero
metric_profile_ref: {metric_profile_id, object_hash}
subject_refs: [{object_kind, object_id, object_hash}]
source_observation_refs: [{object_kind, object_id, object_hash}]
window: {started_at, ended_at, data_cutoff_at}
sample: {overall, subgroups: [{name, size}], exclusions: [{reason_code, count}]}
measurement: {value, unit, numerator?, denominator?, uncertainty?}
guardrail_results: [{metric_name, result: pass | fail | insufficient_evidence, observed_value?}]
decision_rule_evaluation: {result: pass | fail | insufficient_evidence, reason_codes: []}
gate_disposition: pass | fail | insufficient_evidence | not_applicable
result_state: measured | insufficient_evidence | invalidated
reason_codes: [string]
classification: {risk_class, sensitivity, aggregation_level}
observed_at: timestamp
recorded_at: timestamp
idempotency_key: string
producer: {name, version}
lineage: {workflow_run_ref?: {workflow_run_id, object_hash}, input_hashes: []}
retention: retention object
object_hash: sha256
extensions?: namespaced extensions
```

Invariants:

- `MetricProfile` is frozen before candidate results are inspected; it contains no terminal result state.
- A `MetricResult` binds the exact profile, subjects, source observations, measurement window, sample, exclusions, guardrails, decision-rule evaluation, gate disposition, and observed values. It never references an `OutcomeEvent`, avoiding a circular identity dependency.
- The causal order is `MetricProfile` → `MetricResult` → `OutcomeEvent`. Every metric-bearing `OutcomeEvent` binds both exact hashes.
- Unmet sample floors, unavailable denominators, failed mandatory guardrails, expired profiles, or invalidated inputs cannot be encoded as a passing measurement.
- The canonical idempotency key covers profile hash, exact subject hashes, source-observation hashes, and measurement window. Replay resolves to the same result.
- Corrections and late arrivals append a new result in the same family with an exact `supersedes_metric_result_ref` plus an atomically committed `ObjectSuccessorEdge`. The current result is the unique unsuperseded valid member; forks or broken chains are quarantined and cannot satisfy a gate.

## 21. Compatibility and migration

1. Work Packet 04 maps existing schemas to these semantics and owns canonical validators and repositories.
2. Domain packets import the canonical models; they may add adapters and namespaced extensions, not parallel cores.
3. Validators and fixtures precede database migration.
4. Dual-write and shadow-read precede each consumer cutover.
5. Reconciliation covers counts, hashes, successor edges, states on all axes, approvals, attempts, typed operational receipts, side effects, revocations, metric-result families, and outcomes.
6. Consumers cut over one at a time behind flags that default off.
7. Replay and rollback survive at least two complete, predeclared operating windows.
8. Legacy fields retire only through Work Packet 16 and a target-specific approval.

If implementation evidence contradicts this freeze, stop and raise a versioned freeze-change proposal. Silent semantic drift is a failed gate.
