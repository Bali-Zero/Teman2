---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 18 — Operator–AI Conductor Session Bridge

**Architecture:** `research-os/v1.0.0`
**Wave:** 2
**Depends on:** Packets 02, 04, 06, 12, and 17
**Unlocks:** operator-led canaries in Packets 09–11 and traceable outcomes in Packet 13
**Risk:** high authorization and intent-integrity risk; no autonomous outward side effect

## Session prompt

You own the thin bridge that preserves the best part of an operator–interactive-AI session: human judgment turns an evidence-backed `DecisionPacket` into an explicit topic, creative direction, or action intent, and the system captures that decision without confusing conversation with authorization.

The Conductor is a role, not a new autonomous agent, scheduler, cockpit, or truth store. The operator remains the source of taste, priorities, exceptions, and final intent. The interactive AI may research already-authorized public context, explain evidence, expose uncertainty, propose alternatives, and structure decisions. It may not silently infer approval, grade its own generated output, publish, send, deploy, spend media credits, mutate CRM/client state, or execute another outward effect.

You are not alone in the codebase. Use a dedicated worktree, declare the exact files and interfaces you own before editing, preserve concurrent changes, and do not refactor WR2, WR3, Kita, NAGA, or publication internals. All outward effects remain behind the Packet 02 policy and a separately scoped `ApprovalReceipt`. If new persistence requires a v2 migration, do not choose a number: refresh the authoritative Pro head and receive an allocation from the Conductor migration ledger. Missing allocation is a stop condition.

## Mission

Implement this traceable transformation:

```text
DecisionPacket
  -> operator + interactive AI deliberation
  -> exact TopicLock / CreativeLock proposals when content is intended
  -> ConductorHandoff with approved lock references and/or RequestedActionSpec
       -> content path: ContentObject.generated only
       -> action path: Packet 12 atomically creates ActionItem + ActionIntent
  -> operator sees the exact next decision
  -> effect-specific ApprovalReceipt
  -> immutable started ExecutionAttempt -> typed OperationalReceipt -> OutcomeEvent
```

The bridge succeeds when a future session can begin with a small number of operator inputs while retaining evidence lineage, uncertainty, judgment, creative specificity, risk, and authorization scope. Speed and token economy are useful outcomes; they never outrank fidelity or human control.

## Baseline to establish

For at least 20 recent, redacted operator-led decisions, record the originating candidate and evidence, number of operator inputs, elapsed time, manual copy/paste hops, fields lost or reinterpreted, AI proposal-to-final edit distance, approval artifacts, downstream queue/object identity, critic result, and any external side effect. Inventory every surface that currently uses “approve,” “lock,” “handoff,” or equivalent language and map the actual authority each control grants. Establish separate baselines for content and operational actions; do not average them into one convenience metric.

## Frozen semantic boundary

- `DecisionPacket` is the evidence-backed proposal and `why_now` carrier.
- NAGA remains authoritative for claims, evidence, time, contradiction, and expiry.
- Packet 17 supplies specialist verification receipts; agreement does not replace evidence.
- Packet 04 owns canonical `TopicLock`, `CreativeLock`, `RequestedActionSpec`, and `ConductorHandoff`; `ContentObject` carries exact lock references.
- Packet 12 owns Action Inbox persistence, action state, assignment, SLA, and execution adapters.
- `ApprovalReceipt` records an explicit action over an exact before/after hash and authorizes only named effects.
- Publication state reflects public reality. Topic Lock selection, Creative Lock selection, handoff confirmation, content approval, and publication approval are distinct acts. Handoff confirmation is recorded by an immutable `ConductorHandoff(state=operator_confirmed)` successor; it is not an `ApprovalReceipt` subject.
- A chat transcript, model summary, thumbs-up, silence, prior habit, or ambiguous “yes” is not durable authorization.
- The AI that generates a brief, content candidate, or action proposal cannot be its consequential independent grader or approver.
- Strongest risk and sensitivity propagate. A reviewed `SanitizationReceipt` is required for a lower-sensitivity projection; a separate evidence-bound `RiskReclassificationReceipt` is required for a lower-risk corrected/remediated successor.

## Exact scope and ownership discovery

Before mutation, inspect the implementation outputs actually landed by Packets 02, 04, 06, 12, and 17. Record exact file-and-line evidence for:

1. the canonical `DecisionPacket`, `ContentObject`, `WorkflowRun`, `ApprovalReceipt`, and Notebook verification receipt models and validators;
2. the Action Inbox service, repository, state machine, permissions, and command adapter;
3. WR2 and WR3 intake boundaries and the exact point where topic/creative intent currently loses fidelity;
4. Blog/Magazine staging intake and publication-policy checks;
5. Kita surfaces that currently show candidate work, review actions, or structured briefs;
6. current operator-session artifacts, handoff files, queue messages, Telegram votes, WR2 Control records, and any code using `topic_lock`, `creative_lock`, “conductor,” “approve,” or “handoff” semantics;
7. PII/redaction, actor identity, authentication, idempotency, and audit-log utilities already available.

Search exact identifiers and field names rather than assuming a service exists. Trace one representative DecisionPacket through every current manual copy/paste or queue hop and record where exact claim, evidence, and source-document revision references, risk, why-now, operator edits, and approval scope are lost.

After discovery, publish an exact file-ownership declaration before editing. The preferred narrow boundary is:

- one bridge/domain service adjacent to the Packet 04 canonical contracts;
- imports and compatibility tests for canonical `ConductorHandoff`, `TopicLock`, `CreativeLock`, and `RequestedActionSpec`; this packet does not redefine them;
- one adapter to create a validated `ContentObject`;
- one adapter to create a side-effect-free Action Inbox proposal under Packet 12;
- a minimal Kita interaction surface only if no existing surface can capture the required explicit choices;
- focused tests, redacted fixtures, telemetry, and a runbook.

Do not edit WR2/WR3 generation or rendering internals, publication workers, channel senders, CRM mutators, NAGA truth logic, or legacy queue files by hand. Those remain owned by their packets. Shared contract exports, router registries, migrations, and frontend route registries are serial integration points.

## Canonical contract imports and bridge specialization

Import `ConductorHandoff`, `TopicLock`, `CreativeLock`, `RequestedActionSpec`, `ActionItem`, `ActionIntent`, and `ApprovalReceipt` unchanged from `CONTRACTS.md`. The bridge owns orchestration and adapters, not a parallel schema family. If implementation evidence requires a meaning change, stop and raise a freeze-change proposal.

The canonical handoff binds a purpose-scoped pseudonymous `operator_actor_ref`, the assistant producer/version, exact DecisionPacket and VerificationReceipt IDs plus hashes, optional exact Topic/Creative Lock references, zero or more RequestedActionSpec IDs plus hashes, risk/sensitivity, workflow run, supersession, expiry, and retention. When a lower-sensitivity handoff exists, a separate canonical `SanitizationReceipt` is indexed by that exact handoff object hash; the handoff never embeds its receipt. Its session reference is opaque and purpose-bound. A raw transcript, raw user ID, email, account ID, or reusable cross-dataset session ID is forbidden in the general ledger; an exceptional protected transcript reference has separate access control and expiry.

The bridge may create a `RequestedActionSpec`, but only Packet 12 may atomically materialize it into one `ActionItem` plus one `ActionIntent`. The bridge never writes `ActionIntent` status, approval state, execution state, or an execution receipt. The operator sees that materialized pair before any exact effect can be approved.

A Topic or Creative Lock is first hashed as an immutable proposal. A separate `ApprovalReceipt` then binds that proposal hash and authorizes only selection of the named lock. The lock never embeds a receipt ID, avoiding circular identity. Content approval and publication/action approval remain separate receipts over their canonical subjects. `generated → staged` is a deterministic Packet 02 transition based on persisted review payload, policy decision, and provenance summary; it is not an approval. Handoff confirmation is recorded in the immutable `ConductorHandoff` successor chain, not in an invented receipt subject.

## Contract invariants

1. Every handoff binds the exact `DecisionPacket` hash. A material packet, claim, evidence, verification, risk, or sanitization change marks dependent proposed/locked objects stale.
2. The operator performs an explicit, authenticated action to select topic or creative direction, confirm a handoff, or authorize an effect. Lock/content/action approvals use separate exact `ApprovalReceipt` objects over canonical subjects; handoff confirmation uses an exact immutable `ConductorHandoff(state=operator_confirmed)` successor. One screen may present several acts, but a bulk “approve all” control is forbidden.
3. An operator's Topic/Creative Lock receipt authorizes only creation of the named internal object. It never authorizes publication or another external effect.
4. A `RequestedActionSpec` is pre-queue only. Packet 12 creates the queue item and intent atomically; an `ActionIntent` remains a proposal until an unexpired `approve` receipt binds its exact hash, arguments, input revision, authority, and effect.
5. `ContentObject.origin_decision_packet_ref`, lock refs/hashes, exact claim/evidence refs, exact source-document revisions, and complete `{risk_class, sensitivity}` classification bind the exact inputs selected by the handoff. The classification is component-wise at least the maximum of the exact `DecisionPacket`, Topic/Creative Locks, claims/evidence, source revisions, referenced assets, and operator inputs. `lineage.input_hashes` cannot replace the ID-to-hash mapping. Receipt ledgers bind exact object hashes separately. Adapters reject omissions, stale revisions, substitutions, or weaker classification.
6. Red material may produce an internal handoff but never a public `ContentObject`. A lower-sensitivity projection is a distinct version bound to a reviewed `SanitizationReceipt`; a lower-risk corrected/remediated successor is separately bound to a `RiskReclassificationReceipt`. If both dimensions decrease, both exact receipts are required.
7. The raw conversation is not canonical truth. Persist the smallest structured decision record; protected transcript references, when necessary, have explicit purpose, access control, retention, and hashes.
8. The assistant may propose fields and iteratively self-critique creative work with the operator, but cannot set `operator_confirmed`, select a lock, set `human_approved`, issue an independent release critic/verifier, or approve execution on behalf of the operator.
9. A generator identity cannot satisfy an independent factual verifier, release critic, or approver field. The bridge must reject self-gating attempts even if provider/model names differ but the same workflow actor generated both artifacts.
10. Replay, reconnect, or retry may create attempts, never duplicate locks, content objects, inbox actions, approvals, or external effects.

## Deliverables

1. Compatibility adapters and strict validation against the Packet 04 canonical contracts, including supersession and retention rules; no local core schema.
2. A Conductor bridge state machine: `packet_opened`, `deliberating`, `awaiting_operator`, `operator_confirmed`, `materializing`, `handed_off`, `stale`, `rejected`, `failed`, `superseded`.
3. A compact operator interaction that exposes why-now, evidence strength, contradictions, verification state, risk, unresolved questions, alternatives, and the exact next effect before confirmation.
4. Explicit commands for select topic, edit angle/audience, set creative promise/constraints, request evidence, defer, reject, propose content, and propose action. No natural-language-only approval path.
5. A deterministic adapter from confirmed locks to a valid `ContentObject` in `generated` state only. Packet 02 alone may later perform `generated → staged` from persisted review payload, policy decision, and provenance summary; that transition is not an approval. This bridge never sets `staged`, `human_approved`, `publishing`, or `deployed`.
6. A deterministic adapter from `RequestedActionSpec` to Packet 12's atomic, side-effect-free `ActionItem` + `ActionIntent` creation, never an executed command.
7. Immutable before/after hashes and successor `ConductorHandoff` revisions for operator edits, confirmations, rejections, and handoffs; narrowly scoped `ApprovalReceipt` objects only for the canonical subject kinds they actually approve.
8. Stale-input detection and invalidation fan-out when claims, evidence, verification receipts, risk, sanitization, or the DecisionPacket change.
9. Session resume from canonical structured state without relying on a model's memory or the full raw chat transcript.
10. Preregistered `MetricProfile` objects for operator turns, time-to-lock, edit distance, rejection, defer/request-evidence, stale invalidation, handoff validity, downstream acceptance, and unauthorized-effect attempts, with sample floors, windows, confidence method, guardrails, and `insufficient_evidence`.
11. A runbook explaining authority scopes, lock semantics, generator-versus-grader separation, failure recovery, audit lookup, feature flags, and rollback.

## Non-goals

- Do not replace the operator with an autonomous strategist, taste model, approval agent, or scheduled Conductor daemon.
- Do not build a separate cockpit when Kita can host the interaction.
- Do not use chat completion, message sentiment, silence, emoji, or a generic “yes” as publication or execution approval.
- Do not let the interactive AI fabricate, edit, expire, or approve NAGA claims.
- Do not let the bridge discover topics independently of a DecisionPacket except to request more evidence.
- Do not let WR2 or WR3 silently reinterpret a locked topic, promise, audience, must-keep, or must-avoid field.
- Do not publish to Blog, Magazine, Instagram, YouTube, TikTok, Facebook, email, WhatsApp, or any other outward surface.
- Do not deploy, mutate CRM/client records, submit forms, spend FlowKit credits, or send notifications.
- Do not store raw PII, restricted NEXUS detail, credentials, or complete unredacted transcripts in general logs or contract rows.
- Do not optimize the system solely for fewer operator turns, lower token use, or higher throughput.
- Do not allow the generator to issue the final critic or approval receipt.

## Implementation sequence

1. Freeze the current operator journey for at least 20 recent representative decisions: inputs, copy/paste hops, lost fields, operator turns, edit distance, receipts, downstream state, and side effects.
2. Trace exact implementation boundaries landed by dependency packets and declare owned files, shared integration points, feature flags, and rollback point.
3. Create a redacted, human-labeled golden set before selecting prompts, defaults, or UI controls.
4. Add canonical-contract imports, compatibility adapters, state transitions, hashes, receipt scope, and stale-input rules with no downstream adapters enabled.
5. Implement a side-effect-free interaction over recorded/synthetic packets; require explicit UI or structured command confirmation.
6. Add ContentObject materialization and validate lossless transfer into WR2/WR3-compatible fixtures without invoking either foundry.
7. Add atomic `RequestedActionSpec` → `ActionItem` + `ActionIntent` materialization in Packet 12 and validate permissions/idempotency without executing an action.
8. Add structured resume, concurrency control, retries, and partial-write reconciliation.
9. Shadow real operator sessions for the operating window declared in `DISPATCH-MANIFEST.md`, compare the structured handoff with the existing manual outcome, and capture operator corrections.
10. Canary a small number of operator-selected internal handoffs to staging-only consumers; keep every outward adapter disabled.
11. Run an independent adversarial review and an operator usability review before any broader adoption.

## Golden set and adversarial cases

Build at least 90 redacted cases across the nine Research OS outcome families: regulatory radar, editorial/SEO, WR2 carousel, WR3 video, client/compliance action, revenue opportunity, product knowledge, NEXUS internal intelligence, and operational/platform action. Include green, amber, and red risk; accepted, edited, rejected, deferred, request-evidence, content, and action outcomes.

Include at least these adversarial cases:

- a DecisionPacket changes after the operator opens the session;
- a claim expires or becomes contradicted after Topic Lock;
- a NotebookLM receipt is stale, unavailable, or contradictory;
- the operator approves a topic but not the creative promise;
- the operator approves a Creative Lock but not publication;
- an ambiguous “yes,” emoji, silence, or quoted approval from another message;
- a malicious packet or source instructs the AI to bypass the operator;
- the assistant adds an unsupported fact or drops an exception while summarizing;
- two browser tabs or sessions confirm different edits concurrently;
- reconnect/replay after receipt creation but before downstream acknowledgment;
- a ContentObject adapter drops claim IDs, why-now, risk, or a must-avoid constraint;
- a RequestedActionSpec or materialized ActionIntent has broad parameters, missing owner, excessive authority, or a mutable target;
- a red NEXUS-derived packet requests a public object without valid sanitization;
- the same agent generates and attempts to grade the result;
- an expired or purpose-mismatched approval receipt;
- a transcript containing client PII or credentials;
- a FlowKit/video intent that tries to spend credits during planning;
- downstream timeout after an Action Inbox proposal was durably accepted.

## Tests and metrics

Required tests:

- strict schemas, unknown-field rejection, enum/state-machine, and property tests;
- DecisionPacket hash binding and material-change invalidation tests;
- strongest risk/sensitivity propagation and sanitization-receipt tests;
- explicit operator-action, authentication, authority-scope, and ambiguous-language rejection tests;
- Topic/Creative Lock sequencing and separate publication-approval tests;
- lossless DecisionPacket-to-handoff-to-ContentObject field-lineage tests;
- lossless RequestedActionSpec-to-atomic-ActionItem-plus-ActionIntent tests with execution disabled;
- approval before/after hash, expiry, revocation, replay, idempotency, and concurrency tests;
- generator-versus-grader/approver identity tests;
- crash, reconnect, partial-write, duplicate-delivery, stale-session, and downstream-timeout tests;
- log, trace, database, fixture, and analytics scans for raw transcripts, client PII, restricted NEXUS detail, and credentials;
- accessibility and operator comprehension tests for the confirmation surface;
- integration assertions proving publication, send, CRM mutation, deploy, FlowKit spend, and every other outward adapter remain disabled.

Measure evidence-to-topic-lock time, operator turns, clarification rate, request-evidence rate, edit distance between AI proposal and locked result, lock invalidation rate, lossless-field rate, duplicate-object rate, unauthorized-effect attempts blocked, operator comprehension, downstream acceptance, critic rejection, and operator preference against the current manual baseline. Each conclusion must use a preregistered `MetricProfile`; unmet sample floors, incomplete operating windows, or failed guardrails produce `insufficient_evidence`, not an improvement claim.

## Exit criteria

- 100% of handoffs bind a current DecisionPacket hash, purpose-bound operator actor, assistant producer/version, verification receipt hashes, risk/sensitivity, lineage, retention, and structured operator confirmation; every selected lock is bound by its own exact approval receipt;
- 100% field retention for why-now, topic, angle, audience, claims, sources, risk, unresolved questions, promise, must-keep, and must-avoid across the relevant path;
- zero locks or approvals created from ambiguous natural language, silence, prior habit, or assistant inference;
- zero stale, expired, revoked, wrong-scope, or self-issued approvals accepted;
- zero duplicate ContentObjects, Action Inbox proposals, receipts, or effects under replay and concurrency tests;
- zero outward side effects and zero FlowKit credit spend throughout shadow and canary;
- zero raw PII, restricted NEXUS detail, credentials, or unredacted transcripts in general persistence, logs, traces, or analytics;
- the canary improves median DecisionPacket-to-locked-handoff time by at least 30% without increasing critical field loss, unsupported claims, or operator correction severity;
- at least 90% operator comprehension on blinded “what will happen next?” checks;
- an independent reviewer and the operator both return `PASS` or explicitly bounded `PASS_WITH_LIMITS`.

## Shadow, canary, and rollback

Shadow first on recorded or synthetic DecisionPackets. Produce handoffs and candidate objects in an isolated store; compare them with the operator's real manual decisions. Do not enqueue, render, publish, notify, spend credits, or execute actions.

Canary only operator-selected sessions. The first canary may create `generated` ContentObjects or side-effect-free Action Inbox proposals after explicit confirmation, while staging, publication, channel, CRM, deploy, and media-spend adapters remain disabled. Keep the current manual workflow available and show the operator the exact object and each next decision before handoff; one interface may group them visually but cannot collapse their receipts.

Rollback turns off bridge intake and downstream materialization independently. Return the operator to the existing manual session and legacy queue path; never reinterpret missing bridge output as approval. Mark unfinished handoffs stale, preserve immutable receipts and audit evidence, release leases, reconcile partially accepted proposals, and prove no external effect escaped. Do not delete schemas or history. Retirement of old paths belongs to Packet 16.

## Independent reviewer handoff

The reviewer must not be the AI/agent that generated the contracts, bridge, handoff, ContentObject, or ActionIntent being assessed. Provide:

- the before/after journey map and exact owned-file list;
- contract schemas, state-transition table, authority matrix, and feature-flag defaults;
- golden-set results, field-lineage proof, stale-input tests, and concurrency/replay evidence;
- examples of content, action, request-evidence, defer, reject, and superseded handoffs;
- proof that Topic Lock, Creative Lock, content approval, publication approval, and execution approval remain separate canonical `ApprovalReceipt` objects, while an Action Inbox queue disposition remains a separate `ActionItem` successor plus registered typed `OperationalReceipt` and cannot be interpreted as approval;
- generator-versus-grader tests and reviewer identity evidence;
- privacy scans and protected-transcript retention/access policy;
- shadow comparison, operator edit deltas, comprehension results, and canary metrics;
- rollback drill, partial-write reconciliation, and proof of zero outward side effects and zero media-credit spend;
- all assumptions, limitations, deferred integrations, and unresolved operator decisions.

The reviewer issues `PASS`, `PASS_WITH_LIMITS`, or `FAIL`. Any autonomous outward effect, inferred approval, stale approval acceptance, self-grading, loss of claim/risk/creative-lock fields, or sensitive-data leak is an automatic `FAIL`.
