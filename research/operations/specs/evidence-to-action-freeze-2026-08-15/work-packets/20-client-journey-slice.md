---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 20 — Client Journey Adoption Slice

**Architecture:** `research-os/v1.0.0`
**Wave:** 3 — measurement, learning, and business adoption
**Depends on:** Packets 12, 13, 14, and 18
**Integrates with:** Packet 19 compliance handoffs
**Unlocks:** one evidence-to-action lane for onboarding, active service, renewal, and escalation with protected local context and measurable handoffs; reviewed legacy-retirement candidates for Packet 16
**Risk:** critical client-PII, service-quality, authorization, and communication risk; no autonomous outreach or CRM mutation

## Session prompt

You own the adoption slice that projects the client journey into Packet 12's one Action Inbox. Reconcile existing onboarding checklists, practice/service states, document-intake handoffs, owner queues, renewal signals, escalations, portal events, and support workflows through canonical Research OS contracts. Do not replace the CRM, copy its protected data into a general ledger, or build a second client portal.

You are not alone in the codebase. Use a dedicated worktree. Before editing, identify the machine and commit, inspect authoritative Pro state read-only, declare the exact files, data objects, routes, jobs, components, and flags you will own, and check for sibling work. Preserve concurrent changes. If a migration is needed, obtain its number serially from the Conductor migration ledger; never allocate or renumber it yourself.

This packet is implementation preparation and bounded shadow/canary work only. Do not deploy, publish, send a welcome or reminder, mutate CRM or portal state, upload client documents, start a government process, change a practice, accept payment, or mark a service step complete on behalf of a human. Drafts remain internal and local. Any future effect requires a current, action-specific human `ApprovalReceipt` and a separately enabled adapter.

## Mission

Turn fragmented client-journey state into a truthful, privacy-preserving chain from evidence to accountable work:

- one current journey identity linked by opaque reference to protected CRM/local records;
- one evidence-backed `DecisionPacket` per distinct decision or blocker;
- one narrowly scoped action candidate that an explicit Packet 18 operator–AI deliberation may revise and select into a `RequestedActionSpec` inside an operator-confirmed `ConductorHandoff`, then Packet 12 may materialize into the canonical action pair;
- explicit human approval where an action changes client-facing or operational state;
- one immutable started `ExecutionAttempt` per specifically approved adapter invocation, followed by a separate typed `execution.result` `OperationalReceipt` carrying terminal outcome and reconciliation;
- one `OutcomeEvent` representing what was actually observed, not what the workflow hoped would happen.

The system should help the team see what is blocked, what is next, who owns it, and whether the client received the intended service, without exposing the client's protected context to cloud models or general-purpose stores.

## Baseline discovery — complete before editing

1. Inventory current onboarding, practice/service, document-intake, quote/payment confirmation, portal, CRM task, support, renewal, escalation, and client-status paths. Include scheduled agents, local checklist files, API services, dashboard views, event topics, and manual spreadsheets only where authorized.
2. Verify which paths are live, which are code-only, and which currently own state. Do not infer runtime use from a filename, stale documentation, or a launch definition.
3. Map service lines actually represented in current schemas and workflows. At minimum examine visa/immigration, company setup, tax service, and property, but do not assume identical stages.
4. Map each producer state to a canonical journey phase and Packet 12 action state. Record ambiguous transitions, duplicate tasks, stale checklists, missing owners, missing SLA, undocumented completion, and irreversible side effects.
5. Trace a de-identified sample from conversion or accepted engagement through onboarding, active service, completion, renewal, escalation, and closure. Identify where stable IDs disappear and where outcome truth is inferred from a mutable status.
6. Record current stage agreement, blocker accuracy, orphan actions, duplicate actions, handoff latency, stale-work rate, outcome closure, and privacy boundary failures using the definitions below.
7. Establish existing feature flags, authoritative read paths, rollback point, and retention/deletion rules for protected client data.

The baseline may contain only opaque client, engagement, practice, and document references outside the protected local store. Never copy names, contact data, passport/KTP/NPWP/NIB values, document text, credentials, message bodies, financial records, or case narratives into committed research artifacts, stdout, cloud prompts, or the general Research OS ledger.

## Ownership discovery and declaration — required before any edit

Create a session-local ownership manifest naming the exact files and runtime surfaces you will change. Discover current paths first. Likely domains to inspect include the existing client-onboarding orchestrator, journey/workflow services, practices and portal projections, document-intake handoffs, renewal/escalation producers, Packet 12 adapters, local protected staging, and focused tests, but none is claimed until verified.

The intended ownership boundary is:

- read-only adapters from authoritative CRM, portal, checklist, and workflow sources;
- canonical client-journey projection and phase/state mapping;
- creation of `DecisionPacket` objects and downstream candidates; Packet 18 owns operator-confirmed `RequestedActionSpec`/`ConductorHandoff` creation, and Packet 12 owns materialization into `ActionItem`/`ActionIntent` before downstream receipts;
- protected-reference resolution, permissions, redaction, idempotency, reconciliation, tests, and a journey-filtered view inside the existing Action Inbox;
- adapters for onboarding, active-service, renewal, and escalation decisions.

Explicitly outside this packet:

- CRM/client/practice/document source-of-truth schemas unless a separately owned additive adapter field is approved;
- OCR or document classification, legal eligibility decisions, deadline calculations, quote composition, payments, or pricing logic;
- sending email, WhatsApp, portal messages, or notifications;
- modifying client records, checklist completion, practice state, quote/payment state, or government submission state;
- employee onboarding;
- a new standalone journey dashboard, CRM, or task queue;
- retirement of legacy sources.

If ownership overlaps another active session, stop and coordinate. Do not edit shared registries, routers, migrations, or contracts without a declared serial handoff.

## Inputs and contract chain

Use `research-os/v1.0.0` and the canonical action-runtime objects supplied by Packets 04 and 12:

1. `IntelEvent` describes a validated journey observation, such as an authorized status change, missing-input signal, returned specialist result, renewal window, or escalation.
2. `Evidence` and `Claim` are mandatory for consequential legal, eligibility, deadline, and numeric assertions. Ordinary operational facts use authoritative source references and hashes rather than invented claims.
3. `DecisionPacket` proposes a decision or next action with `why_now`, protected subject reference, evidence summary, uncertainty, owner, due time, and alternatives.
4. The journey adapter stops at `DecisionPacket`. Packet 18 may turn one operator-selected or revised candidate into a `RequestedActionSpec` inside an operator-confirmed `ConductorHandoff`; only Packet 12 accepts that exact pair and materializes it into `ActionItem`/`ActionIntent`.
5. `ApprovalReceipt` binds a human decision to exact inputs and one effect. Editing a draft or target creates a new proposal hash.
6. `ExecutionAttempt` records only the immutable start of a specifically approved dry-run/no-op or later approved adapter invocation, including exact `ActionIntent` and `ApprovalReceipt` references, idempotency key, executor, and `started_at`. A separate typed `execution.result` `OperationalReceipt` records terminal outcome, effects, evidence/artifacts, error code, and reconciliation. A rejection or other non-`approve` decision creates no attempt, and neither object copies payload PII into the general ledger.
7. `OutcomeEvent` records observed progress, client/service outcome, blocker resolution, response, correction, or failure with attribution and completeness.

Packet 18 is the sole producer of the selected `RequestedActionSpec` and `ConductorHandoff`; it preserves the operator's hashed inputs, selected and rejected options, unresolved questions, and verification-receipt references without storing private reasoning or protected client context. Conversational text, a journey recommendation, or an unconfirmed handoff cannot create an Action Inbox item.

No object may collapse proposal, approval, attempt, and success into one status. A journey phase is a projection of source truth, not a new CRM truth store.

## Privacy and data-placement contract

- Client names, contact details, citizenship, identity/document numbers, documents, credentials, message bodies, financial data, signed agreements, and case narratives remain in CRM or another approved Pro-local protected store.
- General Postgres/Intel Lake/NAGA/Action Inbox records carry opaque references, coarse service category, policy-safe state, risk, owner/team reference, timestamps, evidence IDs, and non-identifying aggregates only.
- A protected resolver performs authorization at read time and returns only fields needed for the user's role and action. Do not cache the resolved view in a general store or browser telemetry.
- Cloud models may process public regulatory evidence and non-PII aggregate workflow patterns. Client-specific classification and drafts run locally with no cloud fallback.
- Logs, traces, errors, analytics, fixtures, screenshots, exports, and notifications must be PII-safe. Opaque references must not embed names, phone fragments, or document numbers.
- General-ledger CRM projections suppress or aggregate cohorts smaller than 10. Missing, incomplete, or too-small samples emit `insufficient_evidence`; suppressed cohorts never become zero.
- Deletion, correction, consent withdrawal, and access revocation in the protected source must invalidate derived displays and pending intents; the audit ledger retains only the minimum lawful opaque trace.

## Journey domains

Implement adapters as distinct domain mappings, not one universal checklist:

1. **Onboarding:** engagement accepted, prerequisites, document categories received/missing/review-needed, specialist handoffs, service setup, compliance-clock request, owner, blocker, and readiness.
2. **Active service:** agreed deliverable, current stage, verified prerequisite, next action, owner, expected time, exception, evidence request, and handoff receipt.
3. **Renewal:** evidence-backed eligibility/window signal, service continuity risk, client-consent requirement, PricingTool reference if a priced proposal is later prepared, and separation from statutory compliance protection.
4. **Escalation:** missed internal SLA, unresolved blocker, contradictory specialist result, complaint, failed execution, safety/legal/privacy risk, reassignment, and explicit escalation authority.

The adapter must preserve each domain's vocabulary and source authority while presenting a consistent action contract.

## Deliverables

1. A versioned client-journey phase model and compatibility matrix across each authoritative source, with explicit `unknown`, `not_applicable`, `blocked`, `needs_review`, `superseded`, and `source_conflict` states.
2. Stable journey, engagement, practice, and step identities that remain opaque outside protected storage and support duplicate detection without leaking PII.
3. Read-only adapters that generate canonical `DecisionPacket` objects for missing input, specialist handoff, next step, renewal review, service exception, escalation, and closure review.
4. Narrow downstream-candidate templates such as `review_missing_input`, `assign_owner`, `request_specialist_review`, `prepare_local_draft`, `review_renewal`, `escalate_blocker`, and `verify_completion`. Packet 18 alone turns a confirmed selection into a `RequestedActionSpec`; Packet 12 is the sole materializer. Avoid generic `advance_client` or `contact_client` actions.
5. Per-action prerequisite, owner, SLA, risk, approval, and channel policy. Absence of a response or elapsed time never implies consent, approval, completion, or abandonment.
6. Approval and execution guards binding source-state hashes, protected target reference, exact draft or action, actor authority, channel, expiry, and idempotency.
7. Disabled-by-default effect adapters that emit immutable started `ExecutionAttempt` objects and separate truthful `execution.result` `OperationalReceipt` objects only for separately approved dry-run/no-op intents. No client-facing or source-of-truth effect is enabled by this packet.
8. Outcome adapters for assigned, specialist-accepted, blocker-confirmed, blocker-resolved, draft-reviewed, client-response-observed, step-source-confirmed, renewal-accepted/declined, escalated, corrected, and unable-to-verify.
9. A journey-specialized view in the one Kita Action Inbox, with protected-detail resolution only for authorized roles.
10. A read-only journey timeline that distinguishes source events, proposals, approvals, attempts, observed outcomes, and corrections.
11. Reconciliation reports against existing checklists, CRM/practice states, portal state, and team queues; mismatches remain visible rather than being overwritten.
12. Field-level privacy map, role/authority matrix, threat model, migration/adapter plan if needed, runbook, feature flags, rollback drill, and reviewer bundle.

## Non-goals

- Do not create or update a client, practice, checklist step, document, quote, invoice, payment, portal account, filing, or communication.
- Do not infer a missing document's content or a client's consent from behavior.
- Do not let an LLM decide legal eligibility, compliance, completion, or urgency without the required evidence and deterministic rules.
- Do not send welcome, document request, status, renewal, escalation, or sales messages.
- Do not place protected client context in cloud prompts, general ledgers, committed fixtures, telemetry, or alerts.
- Do not duplicate specialist work owned by document intake, compliance, PricingTool, tax, immigration, company, or property systems.
- Do not make one service line's stage model authoritative for another.
- Do not deploy, publish, enable a job, or retire a legacy path.

## Implementation sequence

1. Freeze the baseline, privacy map, ownership manifest, domain vocabularies, source-authority matrix, and metric denominators.
2. Build synthetic and fully de-identified journey fixtures for every domain and edge state.
3. Add strict identities, contract validators, and read-only adapters one source at a time.
4. Implement protected reference resolution with deny-by-default authorization and non-cacheable sensitive responses.
5. Generate shadow `DecisionPacket` objects while current sources and team processes remain authoritative. Test action flow only with a synthetic or operator-confirmed Packet 18 handoff, then exercise Packet 12 through its test/shadow adapter. The journey producer never emits a `RequestedActionSpec` directly.
6. Reconcile phases, blockers, owners, SLAs, and duplicates against independent human labels. Classify every mismatch by source, mapping, freshness, or ambiguity.
7. Add the journey-filtered Action Inbox view behind an off-by-default flag.
8. Add effect-specific approval validation and disabled/no-op execution adapters. A rejection creates an `ApprovalReceipt` but no `ExecutionAttempt`; an approved invocation creates one immutable started attempt and a separate typed terminal `OperationalReceipt`, while every retry creates a new attempt. Separately exercise changed-input, replay, timeout, and reconciliation paths. Every execution requires an unexpired `approve` receipt binding the exact `arguments_hash` and `input_revision_hash`.
9. Emit `OutcomeEvent` objects only from observed source truth or explicit human review; never manufacture a completed journey.
10. Run a bounded internal shadow and canary with protected access audited and legacy workflows unchanged.
11. Complete independent privacy/security, service-operations, and contract review.
12. Prepare a separate rollout proposal. End this packet before deployment, sending, source mutation, or publication.

## Golden set and adversarial cases

Use an independently labeled, privacy-safe golden set covering onboarding, active service, renewal, escalation, and closure across at least the supported visa, company, tax, and property domains. Synthetic cases must reflect real state shapes without containing real client values.

Include:

- one person with multiple engagements and service lines;
- two source records referring to one engagement and two similar records that must remain separate;
- missing, expired, revoked, unreadable, and wrong-category documents;
- a specialist result that contradicts a checklist assumption;
- payment/quote evidence absent even though a manual checklist says complete;
- a client reply arriving before the action intent was created;
- a stage update arriving out of order or being corrected later;
- a renewal signal that is simultaneously a compliance risk and a commercial possibility, requiring separate linked decisions;
- a stalled case with no owner, two owners, or an inactive owner;
- an approved draft changed after approval;
- retry after timeout where the downstream system may have accepted the request;
- a client who withdraws consent or loses portal authorization;
- role escalation attempting to expose a protected document or message;
- prompt injection inside a document, message, or free-text note;
- a service marked complete without an authoritative completion receipt;
- an aggregate slice small enough to identify a client;
- a cloud/local failover attempt that would route PII to a cloud model.

## Tests and metric definitions

Materialize every metric below as a canonical `MetricProfile` before evaluation. Pre-register its exact numerator, denominator, window, timezone, late-arrival policy, exclusions, minimum sample, estimator and confidence method, subgroups, guardrails, and decision rule. If a sample floor is unmet, the result is `insufficient_evidence`, and that metric cannot satisfy an exit gate.

Required tests:

- contract, identity, deduplication, replay, ordering, correction, and supersession tests;
- source-to-phase compatibility and `unknown`/`source_conflict` property tests;
- blocker derivation, prerequisite, owner, SLA, and escalation tests;
- cross-service isolation and linked-but-separate compliance/commercial decision tests;
- approval scope, changed-input invalidation, authority, expiry, and no-silence-as-consent tests;
- dry-run execution, idempotency, timeout-after-effect, reconciliation, and truthful-state tests;
- protected resolver, role, consent, deletion, cache, log, trace, export, screenshot, and cloud-egress privacy tests;
- Action Inbox parity, accessibility, stale-view, and authorization tests.

Freeze metric definitions and denominators before canary:

- **Phase agreement** = journey projections matching independent source-based labels / all labeled projections.
- **Blocker precision** = proposed blockers independently confirmed present / all proposed blockers.
- **Blocker recall** = independently confirmed blockers represented by a packet / all independently confirmed blockers.
- **Handoff completeness** = required handoffs with source, receiving owner/system, SLA, and traceable receipt or explicit pending state / all required handoffs.
- **Owner/SLA coverage** = actionable journey packets with exactly one valid owner or explicit unassigned escalation and a defined SLA / all actionable journey packets.
- **Duplicate-action rate** = extra active intents representing an already active equivalent intent for the same journey step / all active intents.
- **Stale-work rate** = active intents whose source hash, prerequisite, consent, or journey phase is no longer current / all active intents.
- **Outcome closure rate** = actions with a source-backed OutcomeEvent or explicit unresolved/unknown result after their observation window / actions whose observation window ended.
- **Median handoff latency** = median time from verified ready state to receiving owner/system acknowledgement, reported by service domain.
- **Unauthorized-effect count** = client-facing or source-of-truth effects without a current, exact ApprovalReceipt. Acceptable value: zero.
- **PII leakage count** = protected or re-identifying client data outside authorized local stores. Acceptable value: zero.

## Shadow and canary

Shadow each source adapter for two complete operating cycles before exposing write-like controls. Existing CRM, checklist, portal, and team workflows remain authoritative. Display shadow provenance and mismatch state to the operator; do not silently reconcile source conflicts.

Canary only an operator-selected internal cohort with the minimum protected access needed. The canary may enable read-only journey views and internal triage, assignment, snooze, request-review, and approval-denial receipts. All client communication and source mutation adapters remain disabled. Do not use real PII in screenshots or reviewer artifacts.

Expand service domains independently. Passing onboarding does not prove renewal or escalation safety, and passing visa does not prove tax, company, or property mappings.

## Exit criteria

Exit only when:

- phase agreement is at least 98% on the frozen golden set;
- blocker precision and blocker recall are each at least 95%;
- handoff completeness and owner/SLA coverage are 100% for canary items;
- duplicate-action rate and stale-work rate are each below 1% after reconciliation;
- every displayed completion is backed by an authoritative source event or explicit human receipt;
- unauthorized-effect count and PII leakage count are zero;
- all changed-input, revoked-consent, role, replay, and timeout cases fail closed or reconcile truthfully;
- every unresolved source conflict remains visible and cannot produce an executable intent;
- the rollback drill restores legacy-only views without source-data loss;
- independent privacy/security, service-operations, and contract reviewers return `PASS` or explicitly bounded `PASS_WITH_LIMITS`;
- the owner separately approves any deployment proposal. Finishing this packet does not authorize deployment, outreach, mutation, or publication.

## Rollback

Disable the journey adapter and view flags, revoke pending action capabilities, and return users to the current authoritative CRM/checklist/portal/team surfaces. Retain append-only audit, denial, and mismatch records with opaque references; correct projections through supersession rather than destructive edits. Purge any unauthorized cached sensitive projection according to the protected-store incident runbook. Rollback must not alter CRM, documents, practices, client communication state, payment state, or government process state.

## Independent reviewer handoff

The generator cannot approve its own work. Provide the reviewer with the baseline, ownership manifest, source-authority and phase matrices, privacy field map, protected-resolver design, golden-set provenance, before/after metrics with denominators, mismatch ledger, contract-chain samples, permission and cloud-egress tests, dry-run/replay/timeout evidence, feature flags, rollback drill, and a list of every legacy source still authoritative.

The reviewer must independently trace at least one case in each supported service domain, attempt unauthorized protected-detail access, test a changed draft and a reordered event, and verify that all client-facing and source-mutating adapters are disabled. The verdict is `PASS`, `PASS_WITH_LIMITS`, or `FAIL`; it authorizes no deployment, send, CRM mutation, document handling, payment, filing, or publication.
