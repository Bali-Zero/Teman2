---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 22 — Product and Self-Service Evidence Slice

**Architecture:** `research-os/v1.0.0`
**Wave:** 3 — measurement, learning, and business adoption
**Depends on:** Packets 08, 12, 13, 14, and 18; Packet 12 owns canonical action materialization, routing, and state
**Integrates with:** Packet 13 for `OutcomeEvent` collection and Packet 14 for the product-slice release gate
**Unlocks:** one privacy-safe product evidence lane for Kita, KBLI Navigator, calculators, and portals; later Packet 15 learning only after Packet 14 passes
**Risk:** medium-high privacy and product-direction risk; observation and recommendation only, with no automatic code, configuration, content, or prompt mutation

## Session prompt

You own the evidence-to-decision slice for Nuzantara products and self-service surfaces. Turn aggregated, privacy-safe query, search, friction, and support-gap signals into traceable `DecisionPacket` objects with scoped downstream candidates for Kita, KBLI Navigator, calculators, and portals. Packet 18 alone may turn an operator-selected or revised candidate into a `RequestedActionSpec` inside an operator-confirmed `ConductorHandoff`; Packet 12 alone materializes that exact pair.

You are not alone in the codebase. Work in a dedicated worktree, declare every file before editing, preserve concurrent changes, and confine implementation to the ownership boundary below. Reuse the Packet 12 Action Inbox; do not build another dashboard or state machine. Treat all product changes as proposals. Never edit production code, prompts, routing policy, KBLI data, calculator rules, or portal behavior automatically. Never copy raw client queries, support messages, documents, CRM rows, credentials, or other PII into research-OS objects, fixtures, logs, model prompts, or general analytics. Do not self-allocate a migration: no fixed integer block is reserved for this program (the original `270`–`276` reservation was found entirely void on 2026-08-23 — see `research-os-v1.0.0/SESSION-BOARD.md` §0, Migration-ledger decision 001). Refresh the authoritative Pro head and obtain a new serial reservation from the Conductor migration ledger before creating any migration.

## Mission

Give the operator and product owners a reliable answer to four questions:

1. Where are users failing, abandoning, searching without a useful result, or repeatedly asking for help?
2. How large, recent, and persistent is the problem, and what uncertainty or missing coverage affects that conclusion?
3. Which product surface and owner should investigate it next?
4. What bounded, reviewable action is proposed, and what downstream outcome would prove improvement without harming safety, accuracy, or privacy?

Success is a ranked, evidence-linked product action stream inside the existing Kita Action Inbox—not an autonomous product manager and not another analytics cockpit.

## Baseline discovery

Before implementation, record the current commit, machine, source freshness, available history, access boundary, and authoritative owner for every signal source. At minimum, inspect and classify:

- query/search analytics in `apps/backend-rag/backend/app/routers/query_analytics.py` and `apps/backend-rag/backend/db/repositories/query_analytics_repository.py`;
- explicit feedback in `apps/backend-rag/backend/app/routers/feedback.py`, its schemas/models, and the corresponding focused tests;
- search and self-service behavior in `apps/mouth/src/app/kbli/**`, `apps/mouth/src/app/kbli-explorer/**`, `apps/mouth/src/app/visa/**`, `apps/mouth/src/app/taxes/**`, and `apps/mouth/src/app/portal/**`;
- the separate `apps/kbli-navigator/**` surface and its search implementation;
- portal support and workflow signals in `apps/backend-rag/backend/app/routers/portal*.py` and `apps/backend-rag/backend/services/portal/**`;
- aggregate web/product telemetry already exposed through GA4, the existing analytics adapters, or Packet 13 collectors;
- the Packet 12 Action Inbox contracts, repository, permissions, and specialized-view adapter actually present on disk when the session starts.

For each source, distinguish a real user outcome from a proxy. A page view is not success; a search submission is not a useful answer; a support contact is not automatically product failure; absence of an event may mean broken instrumentation. Record event definitions, denominators, retention, sampling, bot/internal-traffic policy, consent/purpose, small-cell risk, and gaps in ID propagation.

Establish a labeled baseline before proposing thresholds. Use at least 120 public, synthetic, or irreversibly aggregated candidate windows spanning all four target surface families, with at least 20 eligible examples per family. If the available corpus cannot meet that floor, report `insufficient_evidence`; do not shrink the denominator or claim a pass.

## Exact ownership

This packet owns only:

- a new product-intelligence slice under `apps/backend-rag/backend/services/research_os/product_intelligence/**` or the equivalent Packet 04 namespace that exists at execution time;
- read-only, typed adapters over approved aggregate sources;
- deterministic redaction, aggregation, gap-feature extraction, clustering, and proposal-building logic;
- product-slice fixtures and focused unit/integration tests under the matching backend test namespace;
- a producer/adapter that emits validated `DecisionPacket` objects and side-effect-free downstream candidates for Packet 18 deliberation, without producing `RequestedActionSpec` or owning Packet 12 persistence or lifecycle;
- a Packet 13 outcome adapter and a Packet 14 evaluation profile for this slice, integrated through their public extension points;
- an internal runbook, source/data dictionary, privacy field map, and rollback procedure.

Packet 12 owns canonical action state, authorization, owner/SLA state, receipts, and Kita presentation. Packet 04 owns the canonical `OutcomeEvent` contract and repository; Packet 13 owns collectors, domain mappings, attribution policy, cursors, and materialized aggregates that use that repository. Packet 14 owns release-gate execution and grader calibration. Product teams retain ownership of Kita, KBLI Navigator, calculators, portal UX, prompts, rules, and code. Any shared registry, router mount, contract export, or migration is a serial Conductor integration step and is not edited opportunistically by this packet.

## Inputs and contract rules

- Consume only validated `research-os/v1.0.0` contracts. Emit `DecisionPacket` only. Packet 18 is the sole producer of `RequestedActionSpec` inside an operator-confirmed `ConductorHandoff`; Packet 12 may materialize only that exact handoff/spec pair into the canonical `ActionItem` and `ActionIntent`. Do not redefine any contract locally.
- Every emitted proposal carries stable source-window IDs, surface, locale where safe, observation period, freshness, denominator, aggregate count/rate, baseline comparison, uncertainty, suppression reason if applicable, algorithm/rule version, and lineage to sanitized evidence.
- Raw query or support text remains in its authorized source system. The general research-OS store may contain only approved taxonomies, redacted features, aggregate counts, and opaque access-controlled references.
- Small cohorts are suppressed under a threshold approved by the privacy field review. Synthetic tests use a default minimum cell size of ten; production adoption may change that value only through a documented privacy decision, never an inline constant change.
- One issue may generate several downstream candidates inside a `DecisionPacket`. During explicit deliberation Packet 18 may select or revise one; the resulting `RequestedActionSpec` names exactly one target surface, one bounded change class, one owner role, one approval requirement, one expiry, and measurable acceptance/guardrail criteria.
- A Packet 18 `RequestedActionSpec`, and the `ActionIntent` later materialized from it by Packet 12, contains no executable patch, prompt replacement, database command, feature-flag mutation, or client-contact payload. Approval means “investigate or prepare this scoped change,” not “deploy it.”
- Strongest risk and sensitivity propagate. Missing instrumentation, stale sources, suppressed cells, or contradictory signals lower confidence and remain visible.

## Deliverables

1. A versioned source/data dictionary covering event meaning, authoritative store, privacy class, retention, window, denominator, freshness, and known blind spots.
2. Deterministic privacy transformation with PII detection, small-cell suppression, and query/support text minimization. Its canonical `SanitizationReceipt` binds both the exact source-window object ID/hash and the exact sanitized output object ID/hash, plus reviewer, transformations, purpose, destination/consumer, expiry, and propagation scope; lookup is indexed by sanitized output hash so no downstream object can claim sanitization by carrying only a source hash.
3. A product-gap taxonomy including at least: zero-result search, reformulation loop, abandoned flow, repeated error, contradictory answer, missing content, unsupported intent, calculator/input confusion, portal workflow blockage, accessibility friction, and repeated support escalation.
4. A gap-clustering record that preserves distinct surface, intent, locale, time window, and evidence. It must expose merge/split reasons and never use an LLM-only merge as canonical truth.
5. A validated `DecisionPacket` producer describing impact, recency, persistence, confidence, counterevidence, unknowns, and the safest useful next step.
6. Validated downstream-candidate templates with target surface, problem hypothesis, owner role, SLA class, investigation/change class, evidence references, expected outcome, guardrails, expiry, and approval scope. Packet 18 alone creates a `RequestedActionSpec` after operator confirmation; Packet 12 alone materializes it.
7. Product-specific filtered views inside the existing Kita Action Inbox. These are projections over Packet 12 truth, not a new queue or dashboard.
8. Packet 13 `OutcomeEvent` mappings for accepted, rejected, duplicate, investigated, instrumented, implemented-by-a-separate-product-change, corrected, rolled back, and no-measurable-effect outcomes.
9. A Packet 14 product-slice dataset card, deterministic graders, human labeling guide, baseline-versus-candidate report, and release-gate profile.
10. A source-health and coverage report that makes missing or stale telemetry explicit instead of interpreting it as zero friction.

## Non-goals

- Do not modify Kita, KBLI Navigator, calculator, portal, prompt, routing, pricing, regulatory, or KBLI behavior in this packet.
- Do not generate or apply code patches, prompt edits, feature-flag changes, deployments, content changes, or database mutations from observed behavior.
- Do not create a new product dashboard, backlog, task store, or competing priority score.
- Do not ingest raw support conversations, free-text client queries, CRM records, document contents, IP addresses, device identifiers, account identifiers, or protected NEXUS data into the general research OS.
- Do not infer user identity, nationality, immigration status, financial position, legal status, or protected attributes from product behavior.
- Do not equate traffic, clicks, completion, low support volume, or a model-generated relevance score with user success.
- Do not rank employees, punish owners for unresolved items, or optimize for closing volume.
- Do not let the generator grade its own proposals or let product telemetry authorize deployment.

## Implementation sequence

1. Freeze the source inventory, event semantics, privacy field map, baseline windows, and source-health report.
2. Create public/synthetic/adversarial fixtures before implementation, including PII-like text that must be suppressed.
3. Implement read-only source adapters and deterministic normalization with no Action Inbox writes.
4. Add privacy transformation and prove that raw text and small cells cannot cross the boundary.
5. Build transparent gap features and deterministic exact/near grouping; send ambiguous semantic grouping to review.
6. Emit shadow `DecisionPacket` objects to a sink isolated from Packet 12 production state. Test action flow only with a synthetic or operator-confirmed Packet 18 `ConductorHandoff`, then exercise Packet 12 materialization against its test/shadow adapter. The product producer never emits a `RequestedActionSpec` directly.
7. Reconcile every candidate window against source aggregates and independently labeled examples.
8. Connect one existing Packet 12 product-filtered projection, still read-only and side-effect-free.
9. Register Packet 13 outcome mappings and the Packet 14 evaluation profile through their declared extension points.
10. Canary one operator-selected product surface after Packet 14 passes; expand only after two complete operating windows and explicit owner approval.

## Golden set and adversarial cases

The held-out and adversarial sets must include:

- the same intent phrased in different languages; different intents sharing the same words;
- one user repeatedly retrying versus many users encountering the same failure;
- bot, staff, QA, and synthetic traffic mixed with real aggregate traffic;
- a tracking outage that looks like sudden success;
- a product launch or campaign that changes the denominator;
- support contacts caused by service policy rather than product UX;
- a query containing a passport number, phone, email, company identifier, name, or document excerpt;
- a small cohort whose details would enable re-identification;
- a KBLI zero result caused by spelling, a genuinely missing code, and a question outside KBLI scope;
- contradictory signals between search, support, feedback, and completion data;
- stale and duplicated events, delayed events, timezone/window boundaries, and replay;
- two separate friction points that an embedding would falsely collapse;
- a high-volume low-harm issue and a low-volume safety-critical issue;
- an approved proposal whose underlying evidence changes before investigation begins.

## Tests and metric definitions

Required tests:

- schema and contract-version tests for every `DecisionPacket`, `ActionIntent`, receipt, and `OutcomeEvent`;
- source-adapter, window-boundary, idempotency, delayed-arrival, duplicate, and replay tests;
- PII redaction, small-cell suppression, authorization, log-scrubbing, and prompt-boundary tests, including forged, stale, cross-purpose, source-only, and output-hash-mismatched `SanitizationReceipt` cases;
- grouping precision/recall and critical false-collapse tests;
- missing-source, stale-source, contradictory-signal, and abstention tests;
- Packet 12 projection parity and no-second-state-store tests;
- mutation guards proving product code, prompts, data, configuration, flags, and client channels cannot be changed;
- Packet 13 ID propagation and Packet 14 known-bad-candidate tests.

Materialize every metric below as a canonical `MetricProfile` before evaluation. Pre-register its exact numerator, denominator, window, timezone, late-arrival policy, exclusions, minimum sample, estimator and confidence method, subgroups, guardrails, and decision rule. Metric definitions are fixed before the canary:

- **Eligible-window coverage** = eligible source windows that emit a proposal or an explicit typed suppression/abstention reason divided by all windows meeting the predeclared volume, freshness, and consent rules. Missing telemetry stays in the denominator as unavailable, not as success.
- **Gap precision** = independently labeled actionable gap clusters divided by all surfaced gap clusters. Report the numerator, denominator, 95% confidence interval, surface/locale subgroups, and reviewer agreement.
- **Gap recall** = independently labeled actionable gaps surfaced by the candidate divided by all actionable gaps in the held-out set. Reject-all cannot pass.
- **Critical false-collapse rate** = clusters joining two materially different problems divided by all reviewed joins; critical safety or regulatory false collapses must be zero.
- **Lineage completeness** = emitted objects with surface, exact source-window ID/hash, exact sanitized-output ID/hash, denominator, freshness, transformation version, a valid purpose/destination-bound sanitization receipt indexed by the output hash, and exact evidence references divided by all emitted objects.
- **Product auto-mutation count** = any code, prompt, configuration, content, data, flag, deployment, or customer-channel change caused by this slice. The required value is zero.
- **PII leak count** = direct identifiers or reconstructable raw text observed outside the authorized source boundary across fixtures, logs, objects, prompts, exports, and UI projections. The required value is zero.
- **Evidence-to-owned-action time** = elapsed time from source-window close to the first valid Packet 12 assignment receipt. Report p50/p90 and compare with the frozen baseline; do not exclude abstentions or failures.
- **Outcome traceability** = canary actions with a stable ID reaching a Packet 13 outcome or an explicit still-pending state divided by all canary actions whose measurement window has closed.

The Packet 14 gate must predeclare target thresholds after baseline capture. It may not pass unless the lower bound of the gap-precision confidence interval is at least 0.80, gap recall is at least 0.75, lineage completeness is at least 0.99, critical false collapses are zero, PII leaks are zero, auto-mutations are zero, and no protected subgroup or surface regresses beyond its declared tolerance. If sample floors are unmet, the result is `insufficient_evidence`, never `pass`.

## Shadow, canary, and expansion

Run in observation-only shadow mode for two complete, predeclared operating windows. Shadow output goes to an isolated comparison sink and cannot create product tasks or notifications. Reconcile source counts, suppression, lineage, and labels before connecting the Packet 12 projection.

The first canary covers one owner-selected surface and only creates reviewable internal proposals in the existing Kita Action Inbox. It does not execute a change. Every proposal expires when its source window or relevant evidence becomes stale. Expansion to another surface requires the Packet 14 gate, an operator usability check, and owner approval based on the same metric definitions.

## Exit criteria

Exit only when:

- the source/data dictionary and privacy field map are signed by an independent privacy-aware reviewer;
- every canary object validates against `research-os/v1.0.0` and Packet 12 contracts;
- gap precision, recall, lineage, safety, subgroup, and sample-floor requirements pass the Packet 14 gate;
- every visible proposal has one accountable owner or an explicit unassigned state, an SLA, expiry, evidence, uncertainty, allowed next action, and outcome measurement plan;
- no raw client text or PII crosses the authorized boundary;
- no product or customer-facing side effect is possible from the slice;
- two complete operating windows reconcile within the predeclared tolerance;
- a fresh reviewer who did not author the implementation reruns the deterministic/adversarial suite and issues `PASS`.

## Rollback

Disable the product-intelligence producer and Packet 12 projection with default-off feature flags. Stop new shadow/canary proposals while retaining immutable receipts and Packet 13 correction events. No product surface needs rollback because this packet never changes product behavior. Do not delete source data, canonical action history, or audit artifacts. A rollback drill must prove the legacy analytics and product surfaces remain unchanged and available.

## Independent reviewer handoff

Provide the source inventory, event/data dictionary, privacy map, aggregation and suppression policy, exact owned-file list, golden/adversarial dataset cards, label guide, baseline/candidate reports with raw numerators and denominators, source reconciliation, lineage samples, Packet 12 projection proof, Packet 13 outcome chains, Packet 14 gate result, mutation-guard proof, canary notes, and rollback drill. The author cannot be the final grader, and a fixture-only pass is not evidence of live readiness.
