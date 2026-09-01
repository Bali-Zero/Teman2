---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 02 — Publishing Truth and Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this packet task by task. Track execution with the checkboxes in this document. A different, independent session must review the result before merge.

**Wave:** 0; policy/golden-set work may begin immediately, while implementation waits for Packet 04.

**Goal:** Establish one truthful, auditable publication policy and state machine so that generated, staged, approved, publishing, deployed, and indexed content can never be confused again.

**Architecture:** Import the Packet 04 canonical models and repository primitives, then add an append-only publication specialization and a pure deterministic policy/state-machine layer. Adapt the existing Intel submission, human approval, publishing, correction-request, and News Room paths while preserving the current human gate. All external side effects remain disabled during this packet.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, asyncpg/PostgreSQL, pytest, Next.js/TypeScript, Jest.

**Spec:** This file is the frozen execution contract. Work Packet 09 consumes the contracts defined here and must not redefine them.

**Depends on:** Packet 04 canonical validators, hashing, `ContentObject`, `ApprovalReceipt`, `VerificationReceipt`, `ActionIntent`, immutable `ExecutionAttempt`, typed `OperationalReceipt`, successor/revocation contracts, and repository core.

**Activation boundary:** This packet defines and tests the exact authorization requirements for `human_approved → publishing`, but no outward adapter may enable that transition until Packet 18 supplies an operator-confirmed handoff and Packet 12 materializes its exact requested-action spec.

## Execution-session prompt

You are implementing the Nuzantara publication-truth specialization after Packet 04 passes review. Work in a new isolated worktree created from the latest authoritative Pro branch. Read the repository `AGENTS.md` before any action, identify the machine, inspect the current files and tests, and verify that migration number 271 is still reserved for this packet. If migration 271 is occupied or Packet 04 is absent, stop and ask the Conductor to revise the central ledger; do not silently renumber or create a parallel contract core.

This is a build-and-test session, not a release session. Do not deploy, publish, install a LaunchAgent, send Telegram messages, create a GitHub pull request with production side effects, or call any outward publishing endpoint. All HTTP, GitHub, Vercel, Telegram, Google, and social effects must be mocked or run in explicit dry-run mode. Never weaken the existing human approval gate.

## Global constraints

- Canonical publication states are exactly: `generated` → `staged` → `human_approved` → `publishing` → `deployed` → `indexed_verified`.
- Canonical verification states are exactly: `unverified`, `verified`, and `stale`.
- Canonical availability states are exactly: `active`, `correction_required`, `withdrawal_requested`, and `withdrawn`.
- Canonical risk classes are exactly `green`, `amber`, and `red`, and canonical sensitivities are exactly the Packet 04 values; this packet consumes `ContentObject.classification = {risk_class, sensitivity}` and never creates a parallel evidence-band vocabulary.
- During this freeze, every outward publication still requires an authorized human approval, including green content.
- Amber content always requires an authorized human approval.
- Red content cannot transition directly to `human_approved`. It must be remediated, regenerated as a distinct successor revision, re-evaluated, and classified green or amber under an exact `RiskReclassificationReceipt`; sanitization alone cannot lower its risk class.
- No code in this packet may publish externally or activate an automation.
- Existing human approval surfaces — News Room and the authorized Telegram vote path — remain the only approval interfaces, but they must record content approval and publication-action approval as two separate explicit decisions. A single `Approve all` decision is invalid.
- An Indexing API acceptance is not proof of indexing and may never produce `indexed_verified`.
- A GitHub commit, branch, pull request, CI success, or deployment log is not proof of deployment. `deployed` requires a live canonical URL probe whose body or immutable revision identifier matches the approved artifact hash.
- Content mutation after approval invalidates that approval. A changed artifact becomes a new revision beginning at `generated`.
- State transitions and approval decisions are append-only and attributable. Never rewrite history in place.
- No client PII, OSINT raw rows, credentials, private chat identifiers, or secret values may enter publication records, logs, fixtures, or reviewer artifacts.
- Keep `apps/backend-rag/backend/prompts/zantara_core.py`, `fly.toml`, all `.env*` files, curated datasets, and live queue JSON writers out of scope.
- Use the backend virtual environment and absolute Python imports. Use typed async I/O and structured logging.

---

## Mission

Replace ambiguous publication vocabulary with a single source of truth and enforce the frozen evidence policy at every transition. The finished system must answer, for any content item:

1. What revision was generated?
2. What canonical risk class and reason codes were assigned?
3. What are its independent publication, verification, and availability states?
4. Who or what requested each transition?
5. Which artifact hash was approved?
6. Which live URL, returned revision/artifact hash, and verification receipt support `deployed` or `indexed_verified`?
7. Is a correction or withdrawal required, what is its severity/SLA, and which approved execution resolved it?

The answer must not depend on filenames such as `published_articles.json`, log prose such as `auto-publish`, or an internal pipeline step called `auto_approved`.

## Why now: verified live baseline

The following baseline was verified read-only on the authoritative Pro on 2026-08-15:

- `com.balizero.intel.nightly` is installed and runs daily at 01:00 WITA. Its command and schedule are in `/Users/nuzantara/Library/LaunchAgents/com.balizero.intel.nightly.plist:34` and `:62-68`.
- The 2026-08-15 run collected 188 candidates, validated 169, sent 163 through the quality gate, produced 20 dossiers, enriched and SEO-optimized seven articles, and submitted seven of seven to backend staging.
- Every successful submit log said `awaiting News Room approval`, and the final message said the seven articles were sent to News Room for approval: `/Users/nuzantara/.openclaw/workspace/logs/intel_nightly_20260815.log:911-925`.
- The scraper's `/api/intel/scraper/submit` call is a staging call, not a public publish call: `apps/bali-intel-scraper/scripts/run_intel_pipeline.py:1812-1849`.
- Backend staging records are created with `status: "pending"`: `apps/backend-rag/backend/app/routers/intel_scraper.py:482-509`.
- Public publication begins only after a News Room action or authorized Telegram vote: `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx:270-318` and `apps/backend-rag/backend/app/routers/telegram_webhook.py:179-210`.
- The current approval quorum is one authorized vote: `apps/backend-rag/backend/app/core/intel_approvers.py:26-42`. Do not copy approver identities or chat identifiers into tests or docs.
- After approval, the backend invokes the article composer/GitHub path, writes an approved news record, and enqueues post-publish work: `apps/backend-rag/backend/app/routers/intel_scraper.py:1030-1068`, `:1115-1173`, and `:1181-1202`.
- Three legacy labels are materially misleading:
  - quality action `auto_publish` only fast-tracks an item through generation; it does not make it public;
  - pipeline step `6_approval: auto_approved` can coexist with a pending News Room item;
  - `published_articles.json` is a generation-history/dedup ledger, not proof that a URL is live.
- Live public evidence does not show daily publication: on 2026-08-15 the newest article `lastmod` in `https://balizero.com/sitemap.xml` was 2026-07-25, and the newest approved item returned by the backend news API had `published_at` 2026-01-13.

This packet must turn those facts into enforced semantics, not another layer of labels.

## Explicit scope and file ownership

This execution session owns only the following implementation files. It may create or modify them and their named tests; it must not opportunistically refactor adjacent systems.

### Create

- `apps/backend-rag/backend/services/publishing/__init__.py`
- `apps/backend-rag/backend/services/publishing/contracts.py`
- `apps/backend-rag/backend/services/publishing/policy.py`
- `apps/backend-rag/backend/services/publishing/state_machine.py`
- `apps/backend-rag/backend/services/publishing/repository.py`
- `apps/backend-rag/backend/db/migrations_v2/271_publication_truth_state.sql`
- `apps/backend-rag/backend/tests/services/publishing/test_contracts.py`
- `apps/backend-rag/backend/tests/services/publishing/test_policy.py`
- `apps/backend-rag/backend/tests/services/publishing/test_state_machine.py`
- `apps/backend-rag/backend/tests/services/publishing/test_repository.py`
- `apps/backend-rag/backend/tests/app/routers/test_intel_publication_truth.py`

### Modify

- `apps/backend-rag/backend/app/routers/intel_scraper.py`
- `apps/backend-rag/backend/app/core/intel_approvers.py`
- `apps/backend-rag/backend/app/routers/telegram_webhook.py`
- `apps/bali-intel-scraper/scripts/run_intel_pipeline.py`
- `apps/mouth/src/lib/api/intelligence.api.ts`
- `apps/mouth/src/lib/api/intelligence.api.test.ts`
- `apps/mouth/src/app/(workspace)/intelligence/news-room/page.tsx`
- `apps/mouth/src/app/(workspace)/intelligence/news-room/page.test.tsx`

### Forbidden in this packet

- Magazine composer, publisher, wrappers, plists, and hosting configuration.
- Post-publish poller/webhook behavior beyond consuming the canonical state returned by the existing endpoint.
- SEO Cell, indexing scripts, sitemap logic, translation jobs, or article ranking.
- Production data backfills, production migration application, deployment, or scheduler installation.
- Existing live approval membership or quorum changes.

## Frozen contracts

### 1. Canonical enums

Import these exact values from the Packet 04 canonical package; do not create divergent local enums. The publication specialization may re-export them for compatibility:

```python
class PublicationState(str, Enum):
    GENERATED = "generated"
    STAGED = "staged"
    HUMAN_APPROVED = "human_approved"
    PUBLISHING = "publishing"
    DEPLOYED = "deployed"
    INDEXED_VERIFIED = "indexed_verified"


class VerificationState(str, Enum):
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    STALE = "stale"


class AvailabilityState(str, Enum):
    ACTIVE = "active"
    CORRECTION_REQUIRED = "correction_required"
    WITHDRAWAL_REQUESTED = "withdrawal_requested"
    WITHDRAWN = "withdrawn"
```

`classification.risk_class` is the canonical Packet 04 field with values `green`, `amber`, and `red`; `classification.sensitivity` carries the strongest input sensitivity. Do not define or re-export a local `EvidenceBand` enum. Do not add `pending`, `approved`, `published`, `auto_publish`, `auto_approved`, `building`, `failed`, `archived`, `corrected`, or `withdrawn` to `PublicationState`. Those may remain source-system fields behind adapters, but they are not canonical publication truth.

### 2. Canonical content identity and artifact revisions

- Every publication projection carries the exact canonical `content_object_ref = {content_object_id, revision, object_hash}` from Packet 04. It never replaces that identity with a publication-local ID.
- `artifact_revision = {artifact_revision_id, artifact_sha256}` identifies the normalized publishable artifact. Both values use exactly 64 lowercase hexadecimal characters matching `^[0-9a-f]{64}$`, with no `sha256:` prefix, over the frozen title, body, canonical category, locale, claims, source URLs, and hero-asset identity.
- `ContentObject.revision` is the positive integer revision of the canonical object. `artifact_revision_id` is an artifact-hash identity; the two fields are not aliases and cannot be substituted for each other.
- A content-revision approval binds the exact `ContentObject.object_hash`, `artifact_revision.artifact_sha256`, `policy_version`, and canonical `{risk_class, sensitivity}` classification.
- Every canonical state change appends a successor `ContentObject.revision` with a new `object_hash`; the artifact revision remains unchanged when the publishable bytes are unchanged.
- A publishable-artifact mutation creates both a new `artifact_revision` and a new canonical content-object revision beginning at `generated`. No earlier content approval or publication-action authorization survives that mutation.
- Legacy `content_id`, `revision_id`, and `evidence_band` may appear only at an adapter input. The adapter must resolve them to a canonical content reference, artifact revision, and full `{risk_class, sensitivity}` classification, or quarantine the event; they never appear in canonical outputs.
- Do not include author names, approver identifiers, source credentials, or raw evidence text in any identifier or hash input.

### 3. State transitions

Allowed forward transitions are:

| From | To | Required evidence |
|---|---|---|
| none | `generated` | valid canonical `content_object_ref` and `artifact_revision` |
| `generated` | `staged` | persisted review payload, policy decision, provenance summary |
| `staged` | `human_approved` | separate, unexpired `ApprovalReceipt` with `subject.kind=content_revision`, bound to the exact content-object and artifact hashes; `classification.risk_class` is green or amber and sensitivity is permitted for the target surface |
| `human_approved` | `publishing` | operator-confirmed Packet 18 handoff containing the publication `RequestedActionSpec`; Packet 12 materializes the exact publication `ActionIntent`; a second, unexpired `approve` receipt binds that intent hash, arguments hash, input revision hash, authorized surface/target/effect, and time window; canonical `ExecutionAttempt.state=started` exists with the same idempotency key |
| `publishing` | `deployed` | a successful exact `execution.result` `OperationalReceipt` binds the publication attempt and approved artifact; canonical URL is live and returns content or an immutable revision identifier matching that artifact hash; deployment/CI receipts are supporting lineage only |
| `deployed` | `indexed_verified` | an independent, unexpired `VerificationReceipt` binds the exact content/artifact/canonical-URL observation and confirms the URL is indexed through approved read-only inspection |

`human_approved` means that the editorial revision passed review; it never authorizes an outward effect. Publication requires its own `ActionIntent` and exact approval receipt. The action target fixes the channel, surface, canonical destination, and artifact revision; a generic, content-only, expired, cross-surface, or mismatched receipt fails closed.

Repeated identical requests are idempotent and append no duplicate transition. Failed work appends a separate `execution.result` `OperationalReceipt` bound to the immutable started `ExecutionAttempt`; it never updates that attempt or fabricates a forward state. A failed publishing attempt leaves canonical state at `publishing`; a retry creates the next numbered attempt under the canonical idempotency contract. A failed deployment or index probe leaves the item at its current state.

There are no backward publication transitions. Remediation creates a new revision and `ObjectSuccessorEdge`. Correction urgency and removal requests use the independent availability axis. `withdrawal_requested` does not remove content; a separately authorized executor and successful exact `OperationalReceipt` are required before `withdrawn`. This packet implements the request, SLA, and audit states but performs no live correction, deletion, or withdrawal.

### 4. Evidence policy v1

Set `policy_version = "publish-policy-v1"`. Evaluate red conditions first, then amber conditions, then green eligibility.

#### Red

Classify red if any condition is true:

- PII, a credential, a private record, or prohibited OSINT detail is detected.
- Source URL/provenance is absent.
- A source contradiction is unresolved.
- A claimed legal, regulatory, tax, immigration, company, property, financial, or numeric fact lacks an authoritative source.
- Grounding or validation reports a hard failure.
- The publishable artifact hash or required asset provenance is missing.
- The existing composite quality score is below 0.40.
- The content is defamatory, unsafe, or asserts unverified wrongdoing by an identifiable person.

Red content remains staged/quarantined. A human may request remediation but may not directly approve it for publication. A lower-risk successor is valid only when the deterministic policy no longer finds the red condition and a canonical `RiskReclassificationReceipt` binds the exact predecessor/output hashes, remediation evidence, current claims/evidence/verification receipts, policy version, and independent reviewer. If sensitivity also decreases, a separate exact `SanitizationReceipt` is required.

#### Amber

Classify amber if no red condition exists and any condition is true:

- Composite quality score is from 0.40 through 0.699999.
- The story relies on only one independent source.
- It contains any legal, regulatory, tax, immigration, company, property, financial, deadline, fee, penalty, or numeric claim, even when grounded.
- The source is not primary/official for a claim that an official source could verify.
- A translation, entity resolution, date, jurisdiction, or canonical URL carries unresolved non-hard uncertainty.
- The story is time-sensitive breaking news whose facts may materially change within 72 hours.

Amber always requires an authorized human approval.

#### Green

Classify green only when all conditions are true:

- No red or amber condition exists.
- Composite quality score is at least 0.70.
- Provenance contains either two independent corroborating sources, at least one of which is primary/official, or two independent primary sources.
- All factual claims have claim-to-source bindings.
- Required artifact and asset hashes are present.
- The item contains no restricted data and no unresolved validation warnings.

Green means `eligible for a future green-only automation experiment`. It does not authorize publication in this packet. Until a separate owner-approved activation changes the frozen contract, green also goes through `human_approved`.

### 5. Publication truth record

The API and repository must expose this minimum typed shape:

```json
{
  "content_object_ref": {
    "content_object_id": "00000000-0000-0000-0000-000000000001",
    "revision": 1,
    "object_hash": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "artifact_revision": {
    "artifact_revision_id": "1111111111111111111111111111111111111111111111111111111111111111",
    "artifact_sha256": "1111111111111111111111111111111111111111111111111111111111111111"
  },
  "surface": "blog",
  "source_kind": "intel",
  "publication_state": "staged",
  "verification_state": "verified",
  "availability": {
    "state": "active",
    "severity": "low",
    "reason_code": null,
    "requested_at": null,
    "required_by": null,
    "resolved_at": null
  },
  "classification": {
    "risk_class": "amber",
    "sensitivity": "public"
  },
  "policy_version": "publish-policy-v1",
  "reason_codes": ["REGULATORY_CLAIM_REQUIRES_HUMAN"],
  "canonical_url": null,
  "deployed_artifact_sha256": null,
  "deployment_probe_receipt_ref": null,
  "verification_receipt_refs": [],
  "content_approval_receipt_ref": null,
  "publication_action_intent_ref": null,
  "publication_approval_receipt_ref": null,
  "current_execution_attempt_ref": null,
  "current_operational_receipt_ref": null,
  "deployed_at": null,
  "indexed_verified_at": null,
  "version": 1
}
```

Reason codes are stable uppercase identifiers. Human-readable explanations belong in UI copy, not in the state-machine keyspace.

### 6. Approval and execution projections

Packet 04 is the sole owner of canonical `ApprovalReceipt`, `ActionIntent`, `ExecutionAttempt`, `OperationalReceipt`, `ObjectSuccessorEdge`, and `RevocationReceipt` objects. The publication ledger stores only exact ID/hash references and namespaced display metadata; it must not create a reduced local record.

The content decision uses an `ApprovalReceipt` whose subject is the exact `content_revision`. The outward publication decision uses a different `ApprovalReceipt` whose subject is the exact publication `ActionIntent`, whose context carries the exact `action_item_ref` ID/hash pair, and whose bindings match both `arguments_hash` and `input_revision_hash`. Its `authorized_effects` must name only the requested publication effect. Both receipts include canonical authority, before/after bindings where applicable, classification, issue/expiry times, retention, and object hash.

The publication projection may retain:

- canonical ID/hash references for the content approval receipt, publication `ActionIntent`, publication approval receipt, immutable started `ExecutionAttempt`, and typed result `OperationalReceipt`;
- a purpose-bound HMAC actor reference with key version already present in the canonical receipt, never a raw or reusable actor identifier;
- a namespaced presentation field for the interface channel (`news_room` or `telegram`) and a short reason code.

A single interface may collect the two decisions consecutively, but must label them independently and emit two receipts. Approval of content, topic, creative direction, assignment, or a different surface cannot be projected as publication authorization. Do not store chat IDs, email addresses, names, message bodies, or tokens in the publication ledger.

### 7. Legacy compatibility mapping

- Legacy staging `status="pending"` maps to canonical `staged`.
- Legacy `status="approved"` maps to `human_approved` only if a real approval event exists for the same artifact revision; otherwise it maps to `staged` and raises `LEGACY_APPROVAL_UNPROVEN`.
- Legacy quality action `auto_publish` contributes a score input only. It never maps to a publication state.
- Legacy pipeline step `auto_approved` maps to `staged` unless an authorized approval event exists.
- Membership in `published_articles.json` is ignored as publication proof.
- Existing genuinely live records may be imported as `deployed` only through a separate read-only reconciliation that proves URL and artifact identity. Do not run that reconciliation against production in this packet.

## Deliverables

1. Typed contracts and serialization tests for all frozen enums and records.
2. A pure, deterministic `classify_evidence` function returning canonical `{risk_class, sensitivity}`, policy version, and ordered reason codes.
3. A pure transition validator that rejects skipped, backward, cross-revision, unapproved, red, or unverifiable transitions.
4. Additive PostgreSQL publication projections referencing the Packet 04 canonical IDs:
   - `publication_truth_items` for current materialized state;
   - `publication_truth_events` for append-only transitions and attempts.
5. An async repository with compare-and-swap versioning and idempotency enforcement.
6. Integration adapters in the Intel submit and approval paths.
7. A News Room response and UI that display truthful labels:
   - Generated
   - Awaiting human approval
   - Human approved
   - Publishing
   - Live
   - Indexed and verified
8. Removal of user-facing/log assertions that equate `auto_publish`, `auto_approved`, or dedup history with public publication.
9. Structured audit logs containing the canonical content-object ref, artifact-revision ref, from/to state, policy version, classification, action/approval/attempt/operational-receipt refs, and reason codes, with no PII.
10. A dry-run reconciliation report for fixture data only. Production backfill remains a separately reviewed operation.
11. An append-only correction/withdrawal request path with severity, SLA, stale verification propagation, specific approval binding, and mocked execution receipt.

## Non-goals

- Enabling green auto-publication.
- Changing who may approve or changing the quorum.
- Improving article prose, research ranking, image generation, translation, or SEO.
- Activating the dormant Magazine jobs.
- Verifying Google indexing.
- Reworking GitHub/Vercel deployment architecture.
- Migrating or deleting legacy dedup files.
- Publishing a test article.

## Dependencies

- The current Intel submit, approval, and internal publish code must remain available.
- Packet 09 depends on the exported `PublicationState`, canonical classification, canonical content/artifact references, repository read API, and transition event schema.
- Packet 09 may not begin integration against these interfaces until Packet 02 contract tests pass and an independent reviewer signs the contract.
- Packet 04 owns canonical models/repositories and the `research_os_contract_core` migration (a symbolic name — its integer is bound at integration time, not 270; see `research-os-v1.0.0/SESSION-BOARD.md` §0, Migration-ledger decision 001). Migration 271 is reserved for this packet. Packet 09 owns migration 274.

## Implementation sequence

### Task 1: Freeze contracts and policy with tests

- [ ] Write failing enum, serialization, policy precedence, threshold-boundary, and reason-order tests.
- [ ] Add failing tests proving a red predecessor cannot become amber/green without a distinct corrected successor and exact `RiskReclassificationReceipt`, that sanitization alone cannot lower risk, and that a simultaneous sensitivity decrease requires both receipt families.
- [ ] Run only the new contract and policy tests and confirm they fail because the package does not exist.
- [ ] Implement `contracts.py` and `policy.py` with no I/O.
- [ ] Run the new tests and confirm exact green/amber/red boundary behavior.
- [ ] Commit only Task 1 files with `feat(publishing): freeze truth and evidence contracts`.

### Task 2: Enforce the state machine

- [ ] Write failing tests for every allowed transition and every forbidden skip/backward/cross-revision transition.
- [ ] Add tests proving red cannot be approved, amber cannot bypass human approval, and green cannot bypass human approval while the freeze is active.
- [ ] Implement `state_machine.py` as a pure transition function.
- [ ] Run state-machine tests twice and verify deterministic event output.
- [ ] Commit Task 2 with `feat(publishing): enforce canonical state transitions`.

### Task 3: Add append-only persistence

- [ ] Write migration-contract tests for checks, unique idempotency keys, append-only events, timestamps, versioning, indexes, and the mandatory `-- === ROLLBACK ===` marker.
- [ ] Create migration 271 with additive publication-specialization tables and no destructive backfill.
- [ ] Write repository tests using the existing backend database-test pattern.
- [ ] Implement typed async repository operations and compare-and-swap updates.
- [ ] Prove concurrent duplicate transitions yield one event and one current-state update.
- [ ] Prove publication, verification, and availability events remain independently append-only and cannot overwrite each other.
- [ ] Commit Task 3 with `feat(publishing): add publication truth ledger`.

### Task 4: Adapt Intel generation and staging

- [ ] Add route tests proving a scraper submit creates `generated` then `staged` and never `human_approved`.
- [ ] Add regression fixtures for legacy `auto_publish`, `auto_approved`, and `published_articles.json` semantics.
- [ ] Adapt `run_intel_pipeline.py` payload/log vocabulary without changing its candidate-selection behavior.
- [ ] Adapt `intel_scraper.py` to persist the canonical record and return it in the submit response.
- [ ] Verify the submit path performs no GitHub, Vercel, Telegram, or public-network publish in tests.
- [ ] Commit Task 4 with `fix(intel): make staging publication state truthful`.

### Task 5: Bind content approval to the exact revision

- [ ] Write failing News Room and Telegram tests for authorized approval, unauthorized approval, stale revision, red item, replay, and quorum.
- [ ] Bind the `content_revision` approval to the canonical content-object and artifact hashes and store only canonical receipt references plus the Packet 04 purpose-bound HMAC actor reference, including key version and approval purpose.
- [ ] Preserve the existing authorized-actor and quorum logic.
- [ ] Prove a body/title/source mutation invalidates the content approval and cannot enter `publishing`.
- [ ] Add contract tests proving a content approval alone cannot authorize publication; the separate exact publication `ActionIntent`, approval receipt, and started execution attempt are mandatory.
- [ ] Commit Task 5 with `feat(intel): bind approval to content revision`.

### Task 6: Make API and News Room labels truthful

- [ ] Update TypeScript types and API fixtures to include the canonical record.
- [ ] Add component tests for each of the six labels and canonical risk classes.
- [ ] Remove user-facing `auto-approved` or `published` wording when the canonical state is `staged`.
- [ ] Ensure amber/red warnings are accessible and reason-code driven.
- [ ] Run focused frontend tests.
- [ ] Commit Task 6 with `fix(news-room): show canonical publication truth`.

### Task 7: Integrated no-side-effect verification

- [ ] Run the complete backend and frontend focused suites listed below.
- [ ] Replay the golden set entirely against local fixtures.
- [ ] Run a forbidden-side-effect spy and prove zero outward calls.
- [ ] Produce a reviewer handoff containing test commands, results, changed files, and state-transition coverage.
- [ ] Do not merge, deploy, or activate anything.

### Task 8: Correction and withdrawal-request safety

- [ ] Add property tests for `active → correction_required`, `active|correction_required → withdrawal_requested`, and specifically approved `withdrawal_requested → withdrawn` events.
- [ ] Prove critical corrections open an Action Inbox item under the frozen SLA and set `verification_state=stale` without rewriting publication history.
- [ ] Prove removal cannot occur from an expired, mismatched, or generic approval and that all executors are mocked in this packet.
- [ ] Prove revocation invalidation reaches registered caches, vector/materialized projections, media manifests, and derived reports or remains a blocking unconfirmed target.

## Golden set and baseline

Create deterministic, public-data-only fixtures for these cases:

| Case | Inputs | Expected risk/state behavior |
|---|---|---|
| G1 | score 0.70, two independent sources including one official, no sensitive/legal/numeric claim | green; generated → staged; still requires human approval |
| G2 | score 0.95, two primary sources, complete hashes | green |
| A1 | score exactly 0.40 | amber |
| A2 | score 0.699999 | amber |
| A3 | score 0.90 with a grounded regulatory claim | amber with regulatory-manual reason |
| A4 | score 0.90 with one source | amber with single-source reason |
| A5 | breaking claim likely to change within 72 hours | amber |
| R1 | score 0.399999 | red |
| R2 | missing provenance | red |
| R3 | unresolved contradiction | red |
| R4 | PII/credential detector hit | red; no sensitive value retained |
| R5 | ungrounded legal or numeric claim | red |
| R6 | red predecessor gains authoritative evidence and resolves its hard failure, but has no risk-reclassification receipt | distinct successor remains ineligible for approval |
| R7 | same remediated successor with exact policy/evidence/verification-bound `RiskReclassificationReceipt` | successor may be classified amber/green according to deterministic policy; predecessor remains red |
| R8 | remediation also removes restricted fields but supplies only one receipt family | rejected until both risk reclassification and sensitivity sanitization receipts bind the exact output hash |
| S1 | legacy `auto_approved` with no approval event | staged |
| S2 | dedup-ledger membership with no live proof | staged |
| S3 | amber item attempts staged → publishing | rejected |
| S4 | approved revision hash differs from publish artifact hash | rejected; new revision required |
| S5 | publishing attempt fails | remains publishing; immutable failed `execution.result` receipt appended for the exact attempt |
| S6 | deployment probe fails | remains publishing |
| S7 | Indexing API notification accepted but no inspection proof | remains deployed |
| S8 | content revision is approved but no publication ActionIntent exists | remains human-approved; no execution attempt |
| S9 | publication approval targets another surface, artifact, arguments hash, or expired window | remains human-approved; fails closed |
| S10 | operator-confirmed handoff, exact materialized publication intent, exact approval, and started mocked attempt | enters publishing; no real outward effect |
| B1 | sanitized replay of the seven 2026-08-15 submissions | seven staged, zero human-approved, zero publishing |
| C1 | deployed content receives a critical verified contradiction | publication unchanged; verification stale; correction required; P0 action opened |
| C2 | withdrawal requested with generic or stale approval | no removal; request remains open |
| C3 | withdrawal requested with exact intent/revision approval and mocked successful executor | availability becomes withdrawn; immutable started attempt plus successful typed operational receipt appended |
| C4 | sanitization or rights receipt revoked | every registered derivative invalidated or reported as a blocking propagation gap |

Record the pre-change baseline from fixture replay. Do not query or copy the seven production payloads; use synthetic records with the same counts and states.

## Tests and evaluations

Run from `apps/backend-rag` with its virtual environment:

```bash
source .venv/bin/activate
PYTHONPATH=. pytest \
  backend/tests/services/publishing/test_contracts.py \
  backend/tests/services/publishing/test_policy.py \
  backend/tests/services/publishing/test_state_machine.py \
  backend/tests/services/publishing/test_repository.py \
  backend/tests/app/routers/test_intel_publication_truth.py -q
PYTHONPATH=. pytest \
  backend/tests/security/test_mutating_routes_are_gated.py -q
```

Run the existing affected Intel and Telegram router suites discovered with:

```bash
rg -l "intel_scraper|publish_staging_item_internal|telegram_webhook" backend/tests tests
```

Then run each returned focused test file. Do not substitute the whole repository suite for targeted failures.

Run frontend tests from `apps/mouth`:

```bash
npm test -- --runInBand \
  src/lib/api/intelligence.api.test.ts \
  'src/app/(workspace)/intelligence/news-room/page.test.tsx'
npm run lint
```

Add a static forbidden-vocabulary evaluation that fails if the changed UI/API path treats `auto_publish`, `auto_approved`, or `published_articles.json` as proof of `deployed`.

## Shadow and canary plan

### Shadow

- Keep `PUBLISHING_SIDE_EFFECTS=disabled`.
- Classify and record synthetic/replayed candidates only.
- Compare policy output with existing human decisions for at least 100 candidates or 14 consecutive daily runs, whichever is longer.
- Report disagreement by reason code; do not tune thresholds from anecdotes.
- The canonical ledger may run in a non-production test database. Do not apply migration 271 to production in this packet.

### Canary

No canary publication is authorized here. A later owner-approved change may propose one green blog item after:

- Packet 02 independent review passes;
- Packet 09 read-only deployment/indexing verification passes;
- zero forbidden transitions occur in shadow;
- the owner explicitly authorizes the exact item, URL, and time.

Amber and red remain outside any future automatic canary. Magazine requires a separate canary decision.

## Metrics and exit criteria

Packet 02 is complete only when all are true:

- 100% of golden-set cases return the frozen canonical risk class and ordered reason codes.
- 100% of attempted skipped/backward/cross-revision transitions are rejected.
- 100% of green and amber content approvals require a valid canonical `content_revision` approval receipt.
- 100% of red direct-approval attempts are rejected.
- 100% of lower-risk successors require a valid exact `RiskReclassificationReceipt`; sanitization alone never lowers risk, and a two-axis decrease requires both receipt families.
- 100% of publication attempts require a separate exact, unexpired publication `ActionIntent` approval plus a canonical started `ExecutionAttempt`; a content approval alone never suffices.
- 100% of approval receipts bind the exact object/revision hashes and contain no raw actor identifier.
- 100% of correction/withdrawal cases preserve publication history and require exact intent/revision approval before mocked removal.
- 100% of revocation fixtures either confirm every registered propagation target or fail closed with a blocking gap.
- The seven-item baseline replay yields seven staged and zero public items.
- Every transition has one append-only event and one idempotency key.
- No changed API/UI path labels a staged item as live, deployed, indexed, or published.
- No external network publish, Git mutation, PR creation, deployment, scheduler activation, or Telegram send occurs.
- All focused tests, lint, migration checks, and security tests pass.
- Independent reviewer returns PASS on policy fidelity, state integrity, no-side-effect enforcement, and privacy.

## Rollback

- Before production adoption, rollback is simply branch deletion; no live state is changed.
- Migration 271 must be additive and include the repository-required rollback marker.
- After a future production migration, disable reads/writes through `PUBLICATION_TRUTH_ENABLED=false` and fall back to the unchanged legacy paths while preserving ledger tables for audit.
- Never delete publication event history as an operational rollback.
- UI must tolerate the canonical field being absent while the feature flag is off.
- If a transition bug is found, stop new transitions, preserve the ledger, repair code, and replay from append-only events; do not edit events in place.

## Security and privacy

- Treat the publication ledger as an audit surface, not a content warehouse.
- Persist URLs, hashes, reason codes, aggregate source counts, timestamps, and purpose-bound HMAC actor references only.
- Never persist source credentials, Telegram identifiers, names, raw private messages, client records, or raw OSINT.
- Test fixtures must use `example.com`, synthetic canonical content-object refs, synthetic artifact hashes, and synthetic purpose-bound actor refs.
- Use environment/Keychain-backed secrets only. A live SEO wrapper was observed to contain a hardcoded database connection string; do not reproduce or quote it. Secret removal and rotation belong to Packet 09's operational hardening and a separately authorized rotation.
- Logs must be safe to copy into a reviewer report.

## Independent reviewer handoff

Hand the reviewer:

1. exact commit hashes and changed-file list;
2. the frozen contract and policy version;
3. golden-set results;
4. state-transition matrix coverage;
5. migration forward/rollback review;
6. evidence that content approval binds the exact content-object and artifact revision;
7. evidence that a separately approved exact publication action is required and that green/amber/red cannot bypass their handling;
8. forbidden-side-effect spy output;
9. vocabulary scan output;
10. explicit confirmation that nothing was deployed or published.

The reviewer must be a fresh session that did not author the implementation. It must inspect code and rerun the focused tests. A self-review is insufficient. Merge and production migration remain owner/conductor decisions.
