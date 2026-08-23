---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 17 — NotebookLM Specialist Verification Adapter

**Architecture:** `research-os/v1.0.0`
**Wave:** 1
**Depends on:** Packets 04 and 06
**Unlocks:** Packet 18 and grounded canaries in Packets 08, 10, 11, 12, and 14
**Risk:** high epistemic and privacy risk; fail closed for consequential claims

## Session prompt

You own the thin, versioned adapter that makes NotebookLM a specialist verification arm of Research OS. Implement the bipolar-verifier pattern: one research or generation arm proposes a claim and its evidence, while a separately invoked NotebookLM arm checks that claim against the correct specialist notebook and returns a structured receipt. NotebookLM is neither the event store nor a substitute for primary evidence.

You are not alone in the codebase. Work in a dedicated worktree, declare every file you will own before editing, preserve concurrent changes, and do not consolidate unrelated NotebookLM pipelines opportunistically. On Air-M5, use only lightweight clients and route live daemon, database, or long-running verification checks to Pro; never install heavy infrastructure locally. Do not publish, send, deploy, enable a daemon, modify notebook membership, or mutate a live claim merely because verification succeeds.

The only permitted NotebookLM account profile is `default`. Do not probe, recreate, or fall back to a `zero` profile. Resolve notebook identities through one reviewed registry; never copy UUIDs into prompts, callers, or tests. If profile identity, notebook routing, source version, freshness, privacy classification, or authentication cannot be established, return a typed unavailable or inconclusive receipt and stop the consequential path.

## Mission

Turn a NotebookLM check into a reproducible, privacy-safe, independently reviewable fact about the verification attempt: which claim was checked, which notebook and source snapshot were used, how fresh they were, which query template and canonical query hash were used, whether the two arms agreed, and what must happen next.

The successful outcome is not “NotebookLM answered.” It is “a downstream consumer can prove what was checked and can distinguish support, contradiction, uncertainty, staleness, routing error, and verifier unavailability without reading raw model prose.”

## Baseline to establish

Measure the current number of NotebookLM call sites, duplicated notebook maps/UUID literals, selectable profiles, freshness mechanisms, source-version coverage, output stores, discrepancy formats, fail-open paths, timeouts, and untraceable verifier results. On a redacted fixed sample, record route accuracy, completion state, latency, contradiction detection, inconclusive handling, raw-text persistence, and the downstream behavior when NotebookLM is unavailable. Treat current documentation as a hypothesis until verified against live Pro configuration and code.

## Frozen semantic boundary

- Intel Lake owns immutable `IntelEvent` records. This packet does not create a second event store.
- NAGA owns `Claim`, `Evidence`, contradiction, validity, expiry, supersession, and review state.
- NotebookLM is a specialist verifier over an approved source corpus. Its synthesized answer is not primary evidence.
- A NotebookLM citation becomes canonical `Evidence` only after a separate adapter can reproduce the source locator and verify the permitted source hash/version.
- Agreement cannot manufacture confidence, erase a contradiction, extend a claim's valid time, or authorize publication.
- A disagreement blocks consequential approval until adjudicated; it is never averaged away.
- `restricted_osint` and `client_pii` never enter a NotebookLM query. A lower-sensitivity projection requires a valid sanitization receipt and purpose binding.
- Only public claim facts may be serialized into the external query. An `internal` request must prove that its minimized query projection is composed solely of public facts; `confidential`, `restricted_osint`, and `client_pii` inputs are rejected unless a reviewed transformation has already produced a distinct public projection.
- Raw queries, raw NotebookLM answers, and raw sensitive excerpts do not enter the general claim, event, receipt, or analytics ledger.

## Exact scope and ownership discovery

Before changing code, trace the current live path on the authoritative Pro checkout and record file-and-line evidence for each hop. At minimum inspect:

- `apps/backend-rag/backend/services/oracle/nlm_notebook_registry.py` for domain routing, UUID ownership, and freshness behavior;
- `apps/backend-rag/backend/services/rag/nlm_verifier.py` for the legacy fire-and-forget verifier, duplicated notebook mapping, failure semantics, and discrepancy logging;
- `apps/evaluator/nlm_deep_research/nlm_bridge.py`, `freshness_monitor.py`, `source_snapshot.py`, and `registry.py` for query transport, freshness evidence, source-set snapshots, and registry semantics;
- `apps/nlm-bridge/main.py`, `hmac_verify.py`, and `test_nlm_bridge.py` for the Pro bridge boundary, authentication, rate limiting, and health states;
- `scripts/wr3_nlm_subprocess.py` and all WR2/WR3 NotebookLM call sites for contract-specific authority boundaries;
- the Packet 04 canonical model/validator location and the Packet 06 NAGA receipt/claim integration actually landed on the implementation branch;
- NotebookLM profile configuration and launch wrappers, confirming empirically that `default` is the sole configured profile without printing tokens or account-private data.

Use exact-string search for notebook UUIDs, `DOMAIN_NOTEBOOK_MAP`, `NLM_NOTEBOOKS`, `nlm_query`, `notebook_query`, freshness state, and discrepancy tables. Produce a call-site matrix with producer, profile, registry source, notebook class, input sensitivity, failure mode, output store, and consumer.

After discovery, declare a narrow ownership list. The preferred boundary is:

1. one canonical NotebookLM routing/profile adapter;
2. one strict NotebookLM namespaced extension for the canonical Packet 04 `VerificationReceipt` model;
3. one reconciliation service adjacent to Packet 06 claim review;
4. focused compatibility adapters for callers selected for the canary;
5. focused tests, fixtures, and an operator runbook.

Do not rewrite notebook ingestion, source curation, WR2/WR3 orchestration, the bridge daemon, or legacy pipelines unless a failing contract test proves that a minimal compatibility change is required. Shared registries and migrations are serialized integration points. This packet has no migration number. If persistence requires one, obtain the number from the Conductor migration ledger after refreshing the Pro migration head; a stale or absent allocation is a stop condition.

## Input and receipt contract

The adapter accepts only a validated request containing:

```yaml
verification_request_id: uuid
contract_version: research-os/v1.0.0
target_claim: {claim_id: uuid, object_hash: sha256, valid_from: utc-timestamp | null, valid_to: utc-timestamp | null}
evidence_refs: [{evidence_id: uuid, object_hash: sha256, source_version_id: string, content_hash: sha256}]
domain: canonical-domain-enum
risk_class: green | amber | red
sensitivity: public | internal | confidential | restricted_osint | client_pii
purpose: verification-purpose-enum
sanitization_receipt_ref: {sanitization_receipt_id: uuid, object_hash: sha256} | null
query_facts: structured-minimized-fields
requester: {service, version, workflow_run_ref: {workflow_run_id, object_hash}}
```

The general ledger stores the canonical Packet 04 `VerificationReceipt`, never a locally redefined receipt or free-form verifier prose. The receipt's `target_objects` contains the exact `claim_id` and claim `object_hash`; `source_versions` contains both an immutable version ID and content hash; `temporal_scope` binds the claim-validity interval, source cutoff, and check time. Notebook-specific detail is allowed only in this namespaced extension:

```yaml
extensions:
  com.balizero.notebooklm.verification:
    extension_version: 1.0.0
    payload:
      verification_request_id: uuid
      notebook: {profile: default, registry_key, notebook_id, registry_version}
      source_snapshot:
        snapshot_id: string
        source_set_hash: sha256
        sources: [{source_id, version_id, content_hash, ingested_at}]
      freshness:
        policy_version: string
        maximum_age_seconds: integer
        latest_source_at: utc-timestamp | null
        status: fresh | stale | unverifiable
      query: {canonicalization_version, template_version, hmac_sha256, hmac_key_version}
      specialist_finding: supports | contradicts | contextualizes | inconclusive | unavailable | rejected_sensitive
      disagreement: {present: boolean, codes: [stable-enum], affected_claim_fields: [field-path], comparison_hash: sha256 | null}
      protected_detail_ref: restricted-purpose-bound-reference | null
      lineage: {workflow_run_ref: {workflow_run_id, object_hash}, adapter_version, tool_version, input_receipt_refs: [{receipt_id, object_hash}]}
```

The extension's `specialist_finding` does not redefine the canonical `verification_verdict`. A fully grounded and temporally aligned support finding may map to `pass`; bounded contextual support maps to `pass_with_limits`; contradiction or a failed mandatory check maps to `fail`; unavailability, inconclusive evidence, stale or unverifiable sources, and privacy rejection map to `insufficient_evidence` unless the registered criteria specify a stricter fail. The mapping is versioned in `criteria_version` and tested against the golden set.

Contract rules:

1. Canonicalize the minimized structured query, then compute a keyed HMAC-SHA-256. Never persist the raw query in the general ledger. Load the HMAC key from the approved runtime secret boundary; if unavailable, fail closed.
2. Every source must carry both `version_id` and `content_hash` from the reviewed ingest/source registry, not a model assertion. If NotebookLM cannot expose a usable revision, the adapter must resolve both through an externally recorded snapshot or return `insufficient_evidence`.
3. Missing or unverifiable source versions/hashes force `freshness.status=unverifiable`; a consequential claim cannot receive a canonical `pass` or `pass_with_limits`.
4. Detailed model output, if operationally required for adjudication, stays in a protected local store with a restricted reference, short retention, access log, and no PII. The receipt carries only codes, IDs, field paths, and hashes.
5. A material claim, evidence, notebook source set, query template, or freshness-policy change creates a new receipt. Receipts are immutable and may be superseded, never overwritten.
6. The same workflow component may request and reconcile verification, but the generating model or agent cannot be the independent human or critic approver. Any human reviewer identity is a purpose-bound HMAC `actor_ref`, never a raw ID.
7. Source publication and validity must align with the claim's frozen valid-time scope. A correct statement supported only by material outside the permitted temporal window is not a pass.
8. An idempotent replay returns the already persisted receipt. A genuinely new verification attempt receives a new receipt ID and hash even when its versioned inputs are identical.

## Deliverables

1. A versioned NotebookLM extension validator, canonical `VerificationReceipt` construction adapter, JSON fixtures, and compatibility policy under the Packet 04 contract family.
2. One canonical domain-to-notebook registry adapter locked to profile `default`, with no duplicated UUID maps in migrated callers.
3. A privacy preflight that permits only public query facts, validates any public projection and its sanitization receipt, rejects `confidential`, `restricted_osint`, and `client_pii`, minimizes query fields, and emits no raw rejected content.
4. A source-snapshot and freshness resolver that records notebook, source identities, source versions/hashes, source-set hash, policy version, and checked time.
5. A deterministic reconciliation engine comparing the requesting arm's claim to the specialist result and returning stable disagreement codes rather than prose-only judgments.
6. Fail-closed handling for missing authentication, wrong profile, unroutable domain, missing notebook, stale or unverifiable sources, timeout, rate limit, malformed response, citation mismatch, and receipt-write failure.
7. A compatibility adapter for the first selected NAGA/WR2/WR3 consumer that can dual-record legacy output and the new receipt without changing live decisions.
8. Receipt lookup by claim ID, workflow run, notebook snapshot, and supersession chain, subject to sensitivity controls.
9. Preregistered `MetricProfile` objects for request count, completion state, routing failures, freshness failures, disagreement rate, adjudication accuracy, latency, and leakage checks, including sample floors, windows, exclusions, confidence method, and `insufficient_evidence`; never label failure as agreement.
10. An operator runbook covering profile preflight, registry verification, source freshness, degraded mode, adjudication, rollback, and incident evidence.

## Non-goals

- Do not make NotebookLM a primary source, claim ledger, event bus, event store, long-term transcript store, or publication authority.
- Do not upload client records, NEXUS rows, LHKPN working data, private messages, credentials, raw OSINT, or any other PII to NotebookLM.
- Do not query NB-INTEL or another OSINT-oriented notebook through this general verifier.
- Do not treat multiple NotebookLM citations as independent corroboration without source-family analysis.
- Do not silently fall back from NotebookLM to a general LLM and call the result verified.
- Do not let a successful receipt mutate claim truth, extend validity, clear a contradiction, approve content, or trigger an outward effect by itself.
- Do not restore deprecated NotebookLM routing to the general RAG hot path.
- Do not create or select a second NotebookLM profile.
- Do not hardcode notebook UUIDs outside the canonical registry or fixtures designed to detect forbidden duplication.

## Implementation sequence

1. Freeze the current call-site, registry, profile, source-version, freshness, storage, and failure-semantics baseline.
2. Build a human-adjudicated golden set before choosing reconciliation rules.
3. Add the namespaced extension, canonical receipt adapter, enums, validators, and redacted fixtures with no live integration.
4. Implement registry/profile resolution and privacy preflight; make all ambiguous states typed failures.
5. Implement source snapshot, freshness binding, query canonicalization/HMAC, and immutable receipt construction.
6. Implement deterministic disagreement extraction and explicit inconclusive handling; keep free-form synthesis out of the contract.
7. Dual-record one existing verifier path in shadow mode while preserving its current behavior for the operating window declared in `DISPATCH-MANIFEST.md`.
8. Reconcile shadow receipts against human adjudication and investigate every false support or false contradiction.
9. Canary the receipt as a blocking gate only for a small, operator-selected set of consequential internal drafts; do not publish them.
10. Hand the exact diff, receipts, protected-output retention proof, metrics, and rollback drill to an independent reviewer.

## Golden set and adversarial cases

Create at least 120 versioned cases spanning immigration, company/KBLI, tax, property, operations, editorial, and Bali lifestyle. Include green, amber, and red-classified inputs; supported, contradicted, inconclusive, expired, and superseded claims; numeric thresholds; effective dates; translations; multiple jurisdictions; and sources updated after the first receipt.

The set must include at least these adversarial cases:

- the correct domain but an outdated specialist notebook source;
- a fresh notebook whose cited source lacks a reproducible version or locator;
- the wrong notebook returned by ambiguous routing;
- an unavailable `default` profile and a tempting legacy `zero` profile on disk;
- authentication failure, timeout, rate limit, malformed response, and empty answer;
- a NotebookLM answer that sounds confident but cites no supporting source;
- two syndicated sources presented as independent corroboration;
- a correct conclusion reached from a source that postdates the claim's valid time;
- disagreement on a percentage, currency, date, threshold, exception, or legal modality;
- a materially changed claim reusing an old query hash or receipt;
- prompt injection embedded in source text;
- `client_pii` and `restricted_osint` hidden in nested fields or Unicode-obfuscated text;
- a sanitization receipt that is expired, revoked, purpose-mismatched, or bound to different source hashes;
- receipt persistence failure after a successful NotebookLM response;
- the generating agent attempting to approve its own reconciliation.

## Tests and metrics

Required deterministic and adversarial tests:

- strict request/receipt schema validation and unknown-field rejection;
- property tests for strongest risk/sensitivity propagation;
- profile lock and forbidden-profile fallback tests;
- registry single-source-of-truth and duplicate-UUID-literal checks;
- query minimization, canonicalization, HMAC stability, key rotation, and raw-text non-persistence tests;
- sensitive-field, nested-field, encoding, and sanitization-receipt rejection tests;
- source snapshot, source-version, freshness boundary, clock-skew, and stale-state tests;
- claim-valid-time versus source-valid-time alignment and postdated-source tests;
- reconciliation tests for numbers, units, dates, modalities, exceptions, translations, and negation;
- unavailable/timeout/rate-limit/malformed/citation-mismatch fail-closed tests;
- replay, idempotency, supersession, material-input-change, and partial-write tests;
- generator-versus-reviewer identity tests;
- scans proving no raw query, raw answer, credential, client PII, or restricted OSINT reaches general logs, events, traces, receipts, or analytics.

Measure at least receipt completeness, route accuracy, source-version-and-hash coverage, freshness-verifiable rate, adjudicated verdict accuracy, false-support count, false-contradiction count, inconclusive rate, disagreement precision/recall, latency distribution, unavailable rate, raw-text leakage count, and operator adjudication time. Report a metric only through its preregistered `MetricProfile`; if its sample floor or operating window is unmet, report `insufficient_evidence` rather than a directional claim.

## Exit criteria

- 100% of receipts validate and bind the exact claim hash, `default` profile, registry version, notebook ID, source snapshot, freshness policy, query HMAC, verdict, and lineage;
- zero raw sensitive values or raw verifier prose in general ledgers, logs, traces, or analytics;
- zero false `supports` verdicts on consequential contradicted, expired, stale, unverifiable, or wrong-notebook golden cases;
- 100% fail-closed behavior for injected profile, auth, routing, freshness, privacy, timeout, malformed-response, and persistence failures;
- at least 95% macro-accuracy against the human-adjudicated verdict set, with disagreements reported separately from unavailable states;
- an idempotent replay returns the same persisted receipt ID/hash, while a new attempt produces a new ID/hash and any material input change invalidates the earlier receipt;
- no receipt directly changes a publication state or executes an external action;
- an independent reviewer returns `PASS` or an explicitly bounded `PASS_WITH_LIMITS`.

## Shadow, canary, and rollback

Start with receipt generation in shadow mode. Shadow receipts may be inspected and scored but cannot alter claim review state, ranking, rendering, queue routing, or publication. Reconcile two complete operating windows against current behavior and human adjudication.

Canary only an operator-selected subset of amber, public-source claims. The verifier only writes a receipt; it never mutates a claim, queue, rank, render, or publication state. A consuming gate may withhold its own pass when the receipt is contradictory, stale, unverifiable, unavailable, or privacy-rejected, but it may never auto-approve the draft. Red material remains outside the NotebookLM path unless it has already been reduced to an independently reviewed public projection with a valid sanitization receipt, and even then remains human-gated.

Rollback disables the new verifier consumer and returns affected claims to explicit manual verification. It must not interpret absence of a receipt as support. Preserve immutable receipts, supersession edges, metrics, and incident evidence. Restore the old read path behind a feature flag; do not delete schemas, source snapshots, or audit records. A rollback drill must demonstrate that queued requests stop cleanly, in-flight results cannot update decisions, and no outward effect occurs.

## Independent reviewer handoff

The reviewer must be independent of the generator and implementation agent. Provide:

- the before/after call-site and registry matrix;
- proof that `default` is the only selected profile and forbidden fallback tests pass;
- the schema, validator, fixtures, source snapshot, and freshness policy;
- a sample of each typed verdict and disagreement code with raw text removed;
- golden-set adjudication, confusion matrix, false-support investigation, and latency/error metrics;
- privacy, log, trace, and artifact scans;
- dual-record reconciliation across two operating windows;
- feature-flag state, canary scope, rollback transcript, and all unresolved limitations.

The reviewer issues `PASS`, `PASS_WITH_LIMITS`, or `FAIL`. Any false support on a consequential contradiction, any sensitive-text leak, any use of a non-`default` profile, or any fail-open unavailable state is an automatic `FAIL`.
