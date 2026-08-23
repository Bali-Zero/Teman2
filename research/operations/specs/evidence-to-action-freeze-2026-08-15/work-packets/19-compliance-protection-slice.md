---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 19 — Compliance Protection Adoption Slice

**Architecture:** `research-os/v1.0.0`
**Wave:** 3 — measurement, learning, and business adoption
**Depends on:** Packets 06, 12, 13, 14, 17, and 18
**Unlocks:** one evidence-to-action compliance lane with accountable owners, SLAs, receipts, and measurable closure; a reviewed legacy-retirement candidate for Packet 16
**Risk:** critical client-protection, legal, temporal, and privacy risk; no automatic consequential action

## Session prompt

You own the adoption slice that turns verified regulatory deltas and protected client deadline signals into accountable compliance work in the Kita Action Inbox. Extend and reconcile the existing regulatory watcher, compliance-deadline sentinel, CRM expiry views, LKPM/tax/immigration obligation logic, and inbox adapters. Do not create another compliance queue, claim ledger, or outbound notifier.

You are not alone in the codebase. Work in a dedicated worktree. Before editing, identify the current machine and commit, refresh the live baseline from the authoritative Pro services using read-only access, declare every file and runtime boundary you intend to own, and check for active sibling work. Preserve concurrent edits. If persistence requires a migration, do not choose a number: request a serial reservation from the Conductor migration ledger and stop if the reservation is stale or collides.

This packet does not authorize deployment, publication, email, WhatsApp, Telegram, CRM mutation, government filing, deadline acknowledgment, payment, or any other client-facing or legally consequential effect. It may build adapters, validators, shadow projections, internal UI, separately approved dry-run commands, and test receipts. Every future effect must require a valid, effect-specific human `ApprovalReceipt` and a separately enabled adapter.

## Mission

Ensure that a credible regulatory change or client obligation becomes one traceable, deduplicated compliance decision with:

- the governing claim and exact evidence;
- valid time, observed time, and the rule version used;
- a precise client or portfolio scope held inside the authorized local boundary;
- exactly one accountable owner or an explicit unassigned escalation;
- an SLA, deadline, urgency, escalation path, and unresolved questions;
- an effect-specific approval boundary;
- an execution and outcome trail that never pretends a proposed action was performed.

The lane protects clients first. It is not a sales funnel and cannot be ranked by expected revenue.

## Baseline discovery — complete before editing

Establish current truth rather than trusting old agent descriptions or migration filenames.

1. Inventory the live and code-level producers of regulatory deltas, immigration/passport expiry, LKPM obligations, tax filing obligations, NIB/permit validity, claim expiry, and compliance escalations.
2. Locate the actual `compliance-deadline-sentinel`, regulatory-watcher, CRM expiry views, compliance services, event topics, Action Inbox adapters, launch/wrapper jobs, dashboards, and local staging paths. Distinguish code present from jobs installed, enabled, healthy, and recently productive.
3. Verify actual database tables and columns read-only. Do not assume a migration filename proves a live table or that a historical agent prompt matches the current schema.
4. Map every present queue and state name to Packet 12. Record duplicate items, missing owners, ambiguous due dates, stale acknowledgments, silent failures, and effects whose receipts cannot be reconstructed.
5. Sample recent regulatory deltas and deadline rows. For every sample, determine whether a NAGA `Claim` and `Evidence` span exist, whether the rule was effective on the relevant date, and whether a specialist or human review is mandatory.
6. Measure the pre-change metrics defined below over a fixed, timestamped observation window. Record denominators and missing-data caveats.
7. Establish the rollback point, all relevant feature flags, and which legacy surface remains authoritative during shadow mode.

Do not place client names, passport numbers, NPWP/NIK, document contents, contact data, case narratives, or raw CRM rows in the baseline report, stdout, committed fixtures, cloud prompts, or the general Research OS ledger.

## Ownership discovery and declaration — required before any edit

Produce a session-local ownership manifest before changing code. It must name exact files, tests, migrations if reserved, database objects, API routes, event topics, UI components, jobs, and feature flags. Determine them through search and live inspection; do not copy this packet's examples as fact.

The intended boundary is:

- compliance-domain adapters that read existing regulatory and obligation sources;
- canonical mapping to `DecisionPacket`; an explicit Packet 18 operator–AI deliberation may select or revise its downstream candidate and place a `RequestedActionSpec` inside an operator-confirmed `ConductorHandoff`, after which Packet 12 may materialize `ActionItem`/`ActionIntent`;
- a specialized compliance view inside Packet 12's one Action Inbox;
- owner/SLA/escalation policy and deterministic deadline calculations;
- focused repositories, validators, permissions, redaction, reconciliation, tests, fixtures, and runbooks.

Explicitly outside this packet:

- Intel Lake ingestion, NAGA claim semantics, and NotebookLM domain verification;
- direct modification of protected CRM client records or source documents;
- client messaging, government submissions, payments, permit changes, or acknowledgment of completed work;
- a new standalone compliance cockpit;
- deletion or retirement of legacy queues;
- commercial scoring of a compliance obligation.

If the exact files overlap an active packet, stop and coordinate through the Conductor. Do not widen ownership to resolve the collision yourself.

## Inputs and contract chain

Consume only validated `research-os/v1.0.0` objects and authorized local references:

1. `IntelEvent` identifies the regulatory delta, document change, protected CRM observation, or upstream invalidation.
2. `Evidence` and `Claim` provide the source span, source independence, effective dates, jurisdiction, status, confidence method, and review state.
3. `DecisionPacket` explains why action may be needed now, evidence, uncertainty, risk, proposed owner, SLA, alternatives, and permitted downstream candidates.
4. The compliance adapter stops at `DecisionPacket`. During an explicit Packet 18 operator–AI deliberation, the operator may select or revise one downstream candidate; Packet 18 then creates the narrow `RequestedActionSpec` inside an operator-confirmed `ConductorHandoff`. Packet 12 accepts only that exact handoff/spec pair and materializes it atomically into `ActionItem`/`ActionIntent`. None of these steps is approval or execution.
5. `ApprovalReceipt` records the human actor, authority, exact proposal/input hashes, permitted effect, expiry, and decision. Silence is never approval.
6. `ExecutionAttempt` records only the immutable start of a specifically approved dry-run/no-op or later approved adapter invocation, with exact `ActionIntent` and `ApprovalReceipt` references, idempotency key, executor version, and `started_at`. A separate typed `execution.result` `OperationalReceipt` records terminal outcome, effects, evidence/artifacts, error code, and reconciliation state. A rejection or other non-`approve` decision creates no attempt; an attempt alone is never proof that an effect succeeded.
7. `OutcomeEvent` records what was subsequently observed, its measurement window, attribution strength, completeness, and caveats.

Packet 17 supplies an independent `VerificationReceipt` over the exact evidence and object revisions required by the compliance gate. Packet 18 is the sole producer of the selected `RequestedActionSpec` and its `ConductorHandoff`; it preserves hashed operator inputs, selected and rejected options, unresolved questions, and verification-receipt references without storing private reasoning. Conversational text, a domain recommendation, or an unconfirmed handoff cannot create an Action Inbox item.

Never fabricate approval or success receipts. A shadow or dry-run item must say so explicitly. If any upstream claim expires, is contradicted, or materially changes, invalidate pending intents and approvals before execution.

## Privacy and sovereignty boundary

- Protected client attributes remain in CRM or another approved Pro-local store. The general event, claim, action, and outcome ledgers carry opaque subject references, policy-safe categories, and aggregates only.
- Client-specific deadline computation and drafting run locally. No cloud model receives client PII, raw CRM rows, protected documents, or reconstructable combinations of attributes.
- Notifications and logs use opaque references. Authorized users follow a permission-checked link to the protected detail view.
- General-ledger CRM projections suppress or aggregate cohorts smaller than 10, and every aggregate must pass re-identification review before leaving the protected boundary. Missing, incomplete, or too-small samples emit `insufficient_evidence`; suppressed cells never become zero.
- NEXUS-derived material follows the red boundary and is not required for this slice.
- A sanitization receipt cannot legalize an unnecessary data copy; minimize first, then sanitize the narrow projection.

## Deliverables

1. A versioned compliance-obligation taxonomy mapping each supported obligation or regulatory delta to domain, jurisdiction, trigger, valid-time rule, evidence requirements, owner-routing policy, SLA policy, escalation policy, and allowed action types.
2. Deterministic adapters from existing producers into validated `DecisionPacket` objects, with stable identities and duplicate suppression across watcher, CRM, and claim-invalidation sources.
3. A protected subject-reference resolver that can display authorized client context without copying protected fields into the general ledger.
4. Owner assignment rules with exactly one accountable owner, explicit fallback/unassigned state, working-calendar semantics, acknowledgement state, and escalation that never treats silence as completion.
5. SLA logic separating statutory deadline, recommended internal action date, acknowledgement deadline, execution due date, and escalation time. The original timezone and derivation rule must be retained.
6. Typed downstream-candidate templates for narrowly named actions such as `review_obligation`, `request_missing_evidence`, `prepare_filing_checklist`, `draft_internal_reminder`, or `escalate_to_owner`. They are side-effect-free fields in the `DecisionPacket`; only Packet 18 may turn an operator selection into a `RequestedActionSpec`, and only Packet 12 may materialize the canonical action pair. No broad `handle_compliance` action is allowed.
7. Approval guards that bind actor authority, current claim/evidence hashes, client scope, action, channel, deadline, and expiry. Material input changes invalidate the receipt.
8. Disabled-by-default execution adapters that may execute only a separately approved dry-run/no-op intent and emit an immutable started `ExecutionAttempt` plus a separate truthful `execution.result` `OperationalReceipt`, without performing an external or consequential effect.
9. `OutcomeEvent` adapters for acknowledged, assigned, evidence-requested, resolved, missed, false-positive, superseded, and unable-to-verify outcomes. Never infer resolution from queue disappearance.
10. A compliance-specialized filtered view in the existing Action Inbox, with evidence, uncertainty, owner, SLA clock, escalation, allowed actions, and protected-detail link.
11. A mapping and reconciliation report for every legacy compliance queue, alert, and status, including information loss and current authority.
12. Privacy field map, threat model, permission matrix, runbook, feature flags, rollback procedure, and independent-review bundle.

## Non-goals

- Do not calculate a deadline from an unverified or inapplicable legal rule.
- Do not let an LLM decide that a client is legally obliged, compliant, noncompliant, or safe without deterministic rules and required review.
- Do not automatically file, renew, pay, contact, update CRM, acknowledge, or close an obligation.
- Do not convert a protection item into a revenue opportunity in this packet.
- Do not expose raw client or NEXUS material in Kita, telemetry, logs, alerts, or cloud prompts.
- Do not replace NAGA, NotebookLM, CRM, Intel Lake, or Packet 12.
- Do not deploy, enable a scheduled job, send a message, publish content, or retire a legacy path.
- Do not claim statutory penalty amounts or dates unless the governing claim is current, scoped, and evidence-backed.

## Implementation sequence

1. Freeze the baseline, ownership manifest, obligation taxonomy, privacy map, and metric denominators.
2. Build synthetic and de-identified fixtures before touching live adapters.
3. Add strict read-side adapters and canonical identity/dedup rules.
4. Bind every consequential field to current NAGA evidence and temporal validity; abstain when the rule or client applicability is unresolved.
5. Generate shadow `DecisionPacket` objects without changing existing queue or notification behavior. Test action flow only with a synthetic or operator-confirmed Packet 18 `ConductorHandoff`; then exercise Packet 12 materialization through its test/shadow adapter. The compliance producer never emits a `RequestedActionSpec` directly.
6. Reconcile shadow output against legacy queues and independent human labels. Classify every mismatch.
7. Add the read-only compliance view to the Action Inbox behind an off-by-default feature flag.
8. Add effect-specific approval validation and no-op/dry-run execution adapters. Every dry-run/no-op execution itself requires an unexpired `approve` receipt binding the exact `arguments_hash` and `input_revision_hash`; prove stale, replayed, unauthorized, non-approve, and overbroad receipts fail closed.
9. Emit immutable started `ExecutionAttempt` objects only for those separately approved internal dry-run/no-op intents, then append exact typed `execution.result` `OperationalReceipt` objects for their terminal observations. Retries create new attempts; neither attempts nor receipts are mutated. Record other shadow validation observations through `VerificationReceipt` or `OutcomeEvent`, as applicable; do not manufacture attempts or successful outcomes.
10. Run a bounded internal canary with existing workflows still authoritative. No external action is enabled.
11. Complete independent legal/temporal, privacy, security, and operational review.
12. Hand off a deployment proposal separately. This packet ends before deploy or activation.

## Golden set and adversarial cases

Create an independently labeled golden set across immigration, passport, LKPM, tax, NIB/permit, claim-expiry, and regulatory-delta cases. Include supported, contradicted, superseded, expired, ambiguous, inapplicable, duplicate, and no-answer examples.

At minimum include:

- publication date differing from effective date;
- a rule amended after the client event but discovered later;
- a national rule with a local or entity-type exception;
- a syndicated news story mistaken for multiple legal sources;
- a deadline with an uncertain applicability prerequisite;
- a recurring obligation crossing year, month, leap-day, holiday, and WITA/UTC boundaries;
- a missing passport or company-type attribute that requires abstention;
- duplicate watcher and CRM alerts for one obligation;
- two candidate owners, no owner, and an inactive owner;
- an acknowledgment without evidence of completion;
- a stale approval after claim, deadline, owner, or action text changes;
- a replay after the first attempt timed out but may have reached the target;
- a protected subject whose display authorization is revoked;
- a malicious note or source text attempting prompt or action injection;
- a red/NEXUS-derived signal attempting to enter the client action lane;
- a compliance item incorrectly prioritized below an associated commercial opportunity.

## Tests and metric definitions

Materialize every metric below as a canonical `MetricProfile` before evaluation. Pre-register its exact numerator, denominator, window, timezone, late-arrival policy, exclusions, minimum sample, estimator and confidence method, subgroups, guardrails, and decision rule. If a sample floor is unmet, the result is `insufficient_evidence`, and that metric cannot satisfy an exit gate.

Required deterministic, property, integration, privacy, and adversarial tests:

- contract validation, stable identity, duplicate suppression, replay, and out-of-order delivery;
- temporal rule, calendar, timezone, amendment, supersession, and invalidation tests;
- evidence sufficiency, source-span, jurisdiction, and abstention tests;
- owner routing, role change, SLA, acknowledgement, escalation, and orphan tests;
- approval scope, authority, expiry, input-hash invalidation, and fail-closed tests;
- dry-run execution, timeout-after-effect, idempotency, reconciliation, and truthful-state tests;
- field-level PII leakage, logs/stdout, cloud-bound prompt, aggregate re-identification, and permission tests;
- Action Inbox adapter parity, accessibility, and authorized-detail-link tests.

Freeze these metric definitions before measuring the canary:

- **Obligation recall** = independently labeled applicable obligations represented by one canonical DecisionPacket / all independently labeled applicable obligations.
- **Critical false-negative count** = independently labeled lapsed or due-within-critical-window obligations with no canonical packet.
- **Actionable precision** = packets independently confirmed applicable and actionable / all packets proposed as actionable.
- **Evidence coverage** = consequential packets with current supported Claim, reproducible Evidence span, jurisdiction, and valid time / all consequential packets.
- **Owner coverage** = actionable packets with exactly one valid owner or explicit unassigned escalation / all actionable packets.
- **SLA completeness** = applicable packets containing statutory deadline when known, internal due time, acknowledgement SLA, escalation time, timezone, and rule version / all applicable packets.
- **Detection latency** = `DecisionPacket.created_at - max(relevant IntelEvent.observed_at, Claim.time.recorded_at)`; report p50, p95, and maximum by domain.
- **Duplicate rate** = extra active canonical packets representing an already represented obligation / all active canonical packets.
- **Unauthorized-effect count** = consequential side effects without a current effect-specific ApprovalReceipt. The acceptable value is zero.
- **PII leakage count** = protected fields or reconstructable client context found outside authorized local stores. The acceptable value is zero.
- **Outcome closure rate** = packets with a later, source-backed OutcomeEvent or explicit unresolved state / packets whose observation window has ended.

## Shadow and canary

Run shadow mode for at least two complete compliance operating cycles relevant to the canary domains. Existing queues, owners, and notification behavior remain authoritative. Shadow objects are visibly labeled and cannot call effect adapters.

The canary is an operator-selected, bounded internal cohort. It may expose the new read-only view and allow triage, assign, snooze, request-evidence, and approval-denial receipts, but it must keep all external and consequential execution disabled. Do not page owners twice; reconcile against legacy acknowledgments before showing a proposed escalation.

Expansion between domains requires the same evidence and privacy review; success on visa expiry does not authorize tax, LKPM, or permit logic.

## Exit criteria

Exit only when:

- critical false-negative count is zero on the frozen golden set;
- obligation recall is at least 99% and actionable precision is at least 98% on the labeled set;
- evidence coverage, owner coverage, and SLA completeness are 100% for critical canary items;
- every uncertain applicability case abstains or routes to review rather than asserting a deadline;
- duplicate rate is below 1% after reconciliation;
- unauthorized-effect count and PII leakage count are zero;
- replay and timeout tests create no duplicate external effect and never fabricate success;
- all shadow/canary mismatches are classified and no unexplained critical mismatch remains;
- the legacy path can be restored without data loss and the rollback drill passes;
- independent legal/temporal, privacy/security, and operational reviewers issue `PASS` or explicitly bounded `PASS_WITH_LIMITS`;
- the owner approves only a later deployment proposal. Completion of this packet itself authorizes no deployment or effect.

## Rollback

Rollback disables the compliance adapter flags and hides its Action Inbox view while retaining append-only audit objects and mismatch evidence. The pre-existing queues remain authoritative. Do not delete canonical records; emit correction, supersession, or invalidation events. Revoke pending intents and approvals when their evidence, owner, deadline, or subject authorization changes. A failed canary must not alter CRM, client communication state, filing state, or statutory truth.

## Independent reviewer handoff

The generator cannot be the final grader. Provide the reviewer with the commit and machine baseline, ownership manifest, schema/adapter map, obligation taxonomy, golden-set provenance, temporal-rule tests, before/after metric table with denominators, mismatch ledger, privacy field map, prompt-egress evidence, permission matrix, sample contract chain, dry-run/replay/timeout evidence, feature flags, rollback drill, and a list of every legacy path still authoritative.

The reviewer must sample source evidence and effective dates independently, test at least one false deadline and one privacy attack, verify that no consequential adapter is enabled, and return `PASS`, `PASS_WITH_LIMITS`, or `FAIL`. A pass permits only the separately proposed bounded rollout; it does not authorize deployment, client contact, filing, payment, publication, or queue retirement.
