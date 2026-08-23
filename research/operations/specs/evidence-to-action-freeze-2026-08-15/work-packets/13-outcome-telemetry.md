---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 13 — Outcome Telemetry and Attribution

**Wave:** 3
**Depends on:** Packets 04 and 09–12, including the canonical `MetricProfile`, correction-aware `MetricResult`, typed `OperationalReceipt`, and exact-reference `OutcomeEvent` contracts
**Unlocks:** Packet 15
**Risk:** medium privacy/interpretation risk; observation does not authorize optimization

## Session prompt

You own the return path from actions and published objects into the evidence spine. Measure what happened at content-object, decision, claim, campaign, and workflow level without overstating attribution or exposing client PII.

You are not alone in the codebase. Work in a dedicated worktree, declare the telemetry collectors, adapters, and materialized projections you own, and preserve concurrent changes. Migration `276` is reserved for collector cursors and aggregates. Refresh the authoritative Pro head; if the central reservation is stale or occupied, stop and request a versioned ledger revision. Packet 04 owns the only canonical `OutcomeEvent` repository; do not create a second outcome event store. Do not alter rankings, prompts, routes, or live business decisions in this packet. Do not send or publish anything.

## Mission

Make every important downstream action observable through a canonical `MetricResult` and bound `OutcomeEvent`, with explicit attribution strength, data window, completeness, privacy class, and links back to the object and evidence that caused it.

## Baseline to establish

Inventory current GSC, GA4, CRM attribution, social metrics, WR2/WR3 telemetry, workflow analytics, alert outcomes, human-review logs, publication receipts, and SEO-cell memory. Establish which systems measure submission versus real outcome, which IDs survive downstream, and where metrics are aggregate-only or stale.

Primary ownership should center on:

- existing SEO/analytics sensors under `apps/evaluator/seo_cell/**`;
- outcome/alert services, collectors, cursors, and materialized projections in `apps/backend-rag/`;
- WR2/WR3 telemetry adapters;
- Packet 04 canonical outcome repository plus new domain collectors and read projections; migration `276` stores only collector cursors, reconciliation state, and materialized aggregates;
- sanitized dashboards/scorecards and focused tests.

Do not own content composition, SEO ranking policy, CRM client records, or publication state machines.

## Inputs and frozen contracts

- `MetricProfile`, `MetricResult`, `OutcomeEvent`, `DecisionPacket`, `ContentObject`, `MediaManifest`, `WorkflowRun`, exact `ExecutionAttempt`, `OperationalReceipt`, and approval/publication receipts.
- Stable IDs must be propagated by Packets 09–12.
- GSC submission is distinct from verified indexing, impressions, clicks, and ranking.
- Engagement is diagnostic; qualified lead, conversion, retention, accuracy, and correction are higher-value outcomes.

## Deliverables

1. Versioned outcome taxonomy spanning factual quality, workflow, publication, search, site, social, CRM, compliance, client service, product usage, and human review.
2. Canonical collectors/adapters writing validated `MetricResult` objects and bound `OutcomeEvent` objects through Packet 04 repositories, with exact profile/result, subject-revision, source-observation, action, attempt, operational-receipt, and measurement-window hashes; no parallel contract or event table.
3. Identity propagation map from exact DecisionPacket revisions through ContentObject/MediaManifest/action/attempt/operational receipt to channel IDs, URL, campaign, and outcome.
4. The exact canonical attribution enum: `direct`, `deterministic`, `modeled`, `correlational`, `unattributed`. No local synonyms or silent mapping.
5. Registered namespaced events for submitted, crawled/inspected where available, indexed_verified, impression, click, engaged session, qualified lead, conversion, correction, withdrawal, and complaint.
6. Privacy-preserving CRM aggregation; general research telemetry stores IDs/aggregates, not raw client messages or documents, suppresses cohorts smaller than 10, and propagates consent, retention, rights-expiry, and revocation into projections, caches, vectors, and reports.
7. Data-quality fields, missingness, freshness, duplicates, delayed-arrival handling, idempotency identities, metric-result families, explicit supersession edges, and deterministic current-result selection.
8. Scorecards by outcome family and surface, with drill-through to receipts rather than raw sensitive data and every conclusion backed by an exact preregistered `MetricProfile` plus immutable `MetricResult`.
9. Backfill plan for a bounded historical cohort, clearly marked as lower-confidence attribution.

## Non-goals

- Do not claim causality from correlation.
- Do not optimize content automatically.
- Do not rank team members or clients.
- Do not copy CRM PII into Intel Lake, logs, or external analytics.
- Do not equate likes, URL submissions, or process completion with business success.
- Do not rebuild GA4, GSC, CRM, or social platforms.

## Implementation sequence

1. Freeze the taxonomy, exact ID/receipt propagation map, dataset/split-bound `MetricProfile` objects, exclusions, owner, expiry, sample floors or power targets, and the operating window declared in `DISPATCH-MANIFEST.md`; candidate results are written later as separate `MetricResult` objects.
2. Build positive, delayed, duplicate, corrected, and unattributable fixtures.
3. Add canonical collectors with source-observation identity, idempotency, data-quality metadata, correction families, and fail-closed fork detection.
4. Start with deterministic internal workflow/publication outcomes.
5. Add GSC/GA4 and social aggregates.
6. Add privacy-preserving CRM/compliance/client outcomes after a field-level privacy review, with cohort suppression below 10 and revocation propagation tests.
7. Backfill one bounded cohort and reconcile against source systems.
8. Run dashboards in shadow beside current reporting.

## Golden set and adversarial cases

Include at least 100 outcome chains with multiple channels, delayed conversions, duplicate webhooks, changed canonical URL, shared campaign, correction, withdrawn content, unattributable direct traffic, index submission without indexing, and a lead whose PII must remain in CRM.

## Tests and exit criteria

- schema/idempotency/dedup tests over exact subject and source-observation hashes;
- delayed-arrival, successor-edge, correction-order, current-result selection, and fork-quarantine tests;
- ID propagation and orphan detection;
- source reconciliation with declared tolerances;
- attribution-strength rules;
- closed-enum rejection and registered namespaced outcome-type tests;
- PII minimization and log-redaction tests;
- cohort suppression below 10 plus consent, retention, and revocation fan-out tests;
- permission tests for sensitive drill-through.

Exit only when at least 95% of canary actions/publications carry exact subject revision/hash references into available typed operational and outcome receipts, deterministic outcomes reconcile at least 99.5%, every metric has a preregistered dataset/split, numerator, denominator, sample floor or power target, window, exclusions, owner, expiry, confidence method, guardrails, decision rule, and attribution strength, and every result has a deterministic gate disposition and current-family identity. Submission/indexing are never conflated, protected client fields do not leave their authorized store, freshness is visible, and an independent reviewer validates a sample end to end. An unmet sample floor, expired profile, incomplete operating window, suppressed cohort, failed guardrail, or result-family fork produces `insufficient_evidence`, never zero or a directional claim.

## Shadow, canary, and rollback

All new telemetry is observation-only. Shadow existing dashboards for two complete reporting windows as declared in `DISPATCH-MANIFEST.md`. Rollback disables domain collectors, cursors, projections, and dashboards without affecting source systems or the Packet 04 repository; canonical events remain append-only for audit and can be corrected by later events.

## Reviewer handoff

Provide taxonomy, ID map, reconciliation tables, privacy field map, sample chains, missing/orphan report, delayed/correction tests, and a list of metrics that remain aggregate-only or unattributable.
