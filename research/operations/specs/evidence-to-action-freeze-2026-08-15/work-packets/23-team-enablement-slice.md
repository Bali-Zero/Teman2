---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 23 — Team Enablement and Accountable Knowledge Routing

**Architecture:** `research-os/v1.0.0`
**Wave:** 3 — measurement, learning, and business adoption
**Depends on:** Packets 12, 13, 14, and 18; Packet 12 owns canonical action ownership, SLA, state, authorization, and receipts
**Integrates with:** Packet 13 for acknowledged/completed/blocked `OutcomeEvent` telemetry and Packet 14 for the team-enablement release gate
**Unlocks:** one accountable internal enablement lane with reusable briefs, checklists, knowledge references, routing, acknowledgment, and completion receipts; later Packet 15 learning only after Packet 14 passes
**Risk:** high operational and privacy risk; internal enablement only, with no autonomous client message, client-record mutation, filing, submission, payment, or other client consequence

## Session prompt

You own the team-enablement projection of the Research OS. Convert validated evidence and approved action proposals into concise briefs, versioned checklists, authorized knowledge references, and accountable team routing with one owner, an SLA, an acknowledgment receipt, and a completion or blocked receipt.

You are not alone in the codebase. Work in a dedicated worktree, declare every file before editing, preserve concurrent changes, and use Packet 12 and Kita as the only canonical action queue. Do not create another dashboard, task database, or lifecycle. Do not send any client-facing message or trigger any client action autonomously. Do not let an acknowledgment authorize execution, let silence count as acknowledgment, or let a completion self-attestation masquerade as a verified client outcome. Client PII and restricted OSINT stay in their authorized systems and never enter general briefs, learning artifacts, cloud prompts, logs, or fixtures. Do not self-allocate a migration: central ledger slots `270`–`276` are reserved. Refresh the authoritative Pro head and obtain a new serial reservation from the Conductor migration ledger before creating any migration.

## Mission

Ensure that a verified signal becomes useful team work without losing evidence, ownership, or accountability:

- the responsible person sees what changed, why it matters, what is known, what remains uncertain, and what not to do;
- the work arrives through an existing authorized surface with an explicit owner, backup role, SLA, and escalation path;
- the recipient acknowledges the exact revision received;
- execution follows a versioned checklist and any required approval boundary;
- completion, partial completion, blockage, supersession, and downstream outcomes are distinguishable and traceable.

Success is less hunting, fewer orphaned obligations, faster acknowledgment, and better evidence-to-completion traceability—not more alerts and not employee surveillance.

## Baseline discovery

Before implementation, record the current commit, machine, live/read-only status, canonical owner, permission boundary, and event semantics for:

- the Packet 12 Action Inbox implementation and existing Kita specialized views;
- team identity and role sources in `apps/backend-rag/backend/app/routers/team.py`, `team_members.py`, `team_activity.py`, and `admin_team_activity.py`;
- knowledge access/activity in `apps/backend-rag/backend/app/routers/knowledge_activity.py`, `apps/backend-rag/backend/app/modules/knowledge/**`, and `apps/nuzantara-mcp/nuzantara_mcp/tools/knowledge.py`;
- existing routing/SLA components in `apps/backend-rag/backend/services/review/sla_worker.py`, `services/communication/routing_engine.py`, `services/routing/**`, and `services/crm/assignment.py`;
- MATA setup-team feeders and promotion gates under `apps/mata-garuda/mata_garuda/domains/setup_team/**`;
- current team-agent and workflow adapters under `apps/team-agent/**` and `apps/nuzantara-mcp/nuzantara_mcp/workflows/**`;
- existing internal team surfaces under `apps/mouth/src/app/(workspace)/**` and any authorized internal notification adapters;
- Packet 13 outcome collectors and Packet 14 evaluator extension points present on disk.

Inventory current briefs, alerts, checklists, assignments, promises, reminders, and completion signals. For each, map the source of truth, object ID, owner, backup, risk, SLA clock, acknowledgment semantics, completion semantics, evidence/knowledge references, channel, duplicate path, escalation, privacy class, and whether a client side effect can occur.

Measure at least two representative operating windows where history permits: eligible-item count, duplicate rate, orphan/unassigned rate, time-to-owner, time-to-acknowledge, SLA breach rate, reassignment rate, completion-receipt coverage, blocked-without-escalation rate, stale-knowledge rate, and untraceable side effects. Do not infer success from the absence of records. If fewer than 30 eligible internal work items across at least three team functions are available for canary evaluation, report `insufficient_evidence`.

## Exact ownership

This packet owns only:

- a team-enablement adapter/projection under `apps/backend-rag/backend/services/research_os/team_enablement/**` or the equivalent Packet 04 namespace present at execution time;
- deterministic brief/checklist assembly from validated evidence and approved templates;
- a versioned role-capability-routing map and manual-override adapter, without owning the authoritative team directory;
- typed acknowledgment, routing, and completion/blocked adapters over the Packet 04 canonical `OperationalReceipt` registry exposed through Packet 12, with observations emitted through Packet 13;
- one specialized team-enablement view inside the existing Kita Action Inbox, using Packet 12 truth;
- focused public/synthetic fixtures, tests, runbook, privacy map, and the Packet 14 team-enablement evaluation profile.

Packet 12 owns action identity, state, permissions, assignment, SLA, approval, and action-runtime adapters. Packet 04 owns the canonical `OperationalReceipt` and `OutcomeEvent` contracts and repositories; Packet 12 exposes the registered receipt adapters, and Packet 13 owns collectors, domain mappings, attribution policy, cursors, and materialized aggregates that use those repositories. Packet 14 owns release gates. Existing HR/team directories own identity, role, availability, and employment data. Domain teams own the substantive checklist and knowledge content. Client systems own client records and communication. Any shared schema export, router mount, registry, notification adapter, or migration is integrated serially by the Conductor and is not claimed casually by this packet.

## Inputs and contract rules

- Consume validated `DecisionPacket`, exact Packet 12 `ActionIntent` and `ExecutionAttempt` references, `ApprovalReceipt`, `WorkflowRun`, claims/evidence, sanitization receipts, and the Packet 04 `OperationalReceipt` and `OutcomeEvent` contracts through their canonical repositories and Packet 13 collectors. Do not redefine their lifecycle locally.
- The team view is a projection of one canonical Packet 12 action. It may cache presentation data but cannot become another writable action store.
- Each brief is bound to an exact `ActionIntent` reference `{object_id, object_hash}`, exact evidence/claim references with hashes, brief template version, checklist version, risk/sensitivity, owner role, SLA policy, required authority, and expiry.
- Each checklist step declares instruction, required/optional status, evidence or artifact expected, authority boundary, and whether it could affect a client. A client-affecting step is locked until the exact approval receipt exists; this packet never executes it.
- Acknowledgment means only that a named authorized recipient received and accepted responsibility for an exact revision. It is not approval to contact a client or execute an effect.
- Completion means the internal checklist requirements were satisfied with declared evidence. `team.partial` is a non-terminal progress receipt with completed and pending step IDs and no terminal outcome; `blocked`, `cancelled`, and `superseded` are terminal outcomes. None can be relabeled as completed.
- Client outcome is separate from work completion. Any claimed filing, submission, delivery, approval, payment, or client response requires a downstream system receipt and Packet 13 outcome, not team self-attestation.
- Knowledge references carry source, claim/version, valid-time or freshness, access class, and expiry. Superseded or contradicted knowledge invalidates the affected brief/checklist and returns the action to review.
- Silence, a link click, notification delivery, or elapsed time never counts as acknowledgment, approval, completion, or client outcome.

## Deliverables

1. A versioned team-enablement projection over Packet 12 actions, with no independent lifecycle or source of truth.
2. A concise brief format containing: objective, why now, verified facts, uncertainty, risk, prohibited actions, owner, backup role, SLA, escalation, knowledge references, checklist, required approvals, expected artifact, and outcome definition.
3. Versioned checklist templates by action/domain with stable step IDs, evidence requirements, authority boundaries, and change history.
4. A deterministic role-capability-routing matrix with explicit manual override, workload/availability inputs only when authorized, fallback owner, and a registered `routing.assignment` `OperationalReceipt` bound to the exact action and owner revisions.
5. A registered `team.acknowledgment` `OperationalReceipt` bound to recipient, role, exact `ActionIntent` reference, exact brief/checklist revisions and hashes, timestamp, authority scope, and SLA clock. It records acknowledgment only—not approval or completion.
6. Registered `team.partial`, `team.completion`, `team.blocked`, `team.cancelled`, and `team.superseded` `OperationalReceipt` variants bound to actor, exact action/attempt where applicable, completed and pending step IDs, artifact/evidence references, exceptions, and timestamp. `team.partial` is explicitly non-terminal; the other four carry their truthful terminal outcome. They must not contain raw client content.
7. Invalidation and supersession behavior for changed evidence, expired knowledge, reassignment, changed authority, changed checklist, or changed input hash.
8. One existing-Kita specialized view that supports read, acknowledge, assign/reassign, request clarification/evidence, report blocked, attach an authorized artifact reference, and record internal completion.
9. Internal reminder/escalation behavior that is explicit, idempotent, rate-limited, role-authorized, privacy-safe, and link-based. Every live reminder/escalation is a named notification effect with an exact `ActionIntent`, unexpired effect-specific `ApprovalReceipt`, immutable started `ExecutionAttempt`, terminal `OperationalReceipt`, and `OutcomeEvent`; a bounded recurring approval may cover only the exact template, audience class, rate limit, operating window, and expiry it binds. Secondary internal notifications are not truth and never contain client PII.
10. Packet 13 outcome mappings for delivered, acknowledged, reassigned, clarification_requested, partial_progress, blocked, escalated, internally_completed, downstream_verified, corrected, cancelled, and superseded.
11. A Packet 14 dataset card, deterministic receipt/state/permission graders, human comprehension/routing rubric, baseline-versus-candidate report, and release-gate profile.

## Non-goals

- Do not create a new dashboard, team cockpit, kanban, inbox, task database, or notification truth store.
- Do not send client email, WhatsApp, Telegram, portal messages, filings, submissions, invoices, payments, or CRM updates autonomously.
- Do not draft a client message as an executable payload or treat team acknowledgment as authorization to send one.
- Do not rank, score, surveil, discipline, or compare employees. Team-level workflow metrics are for system quality, not performance evaluation.
- Do not expose raw client records, documents, messages, contact details, precise private locations, or protected NEXUS material in briefs, general queues, notifications, analytics, fixtures, or cloud prompts.
- Do not let an LLM invent an owner, SLA, legal deadline, checklist requirement, policy, or knowledge citation.
- Do not clone or rewrite the team directory, knowledge base, Action Inbox, CRM, or domain workflows.
- Do not interpret a delivered notification, checked box, or closed action as proof of a real client or regulatory outcome.
- Do not retire existing team workflows; Packet 16 owns retirement after parity and owner approval.

## Implementation sequence

1. Freeze the surface/workflow inventory, authority matrix, team-role source map, privacy field map, baseline metrics, and a collision map with Packet 12.
2. Define the projection and receipt adapters against the Packet 04 canonical `OperationalReceipt` registry and the Packet 12 adapter surface actually present on disk. If the required registered receipt types or adapter hooks are absent or ambiguous, stop integration and return a contract gap rather than inventing local semantics.
3. Build public/synthetic fixtures and adversarial cases before implementation.
4. Implement deterministic brief/checklist assembly and knowledge-freshness validation in isolation.
5. Implement routing as an explainable proposal with manual override; do not send notifications or mutate assignments in shadow mode.
6. Add registered `routing.assignment`, `team.acknowledgment`, `team.partial`, `team.completion`, `team.blocked`, `team.cancelled`, and `team.superseded` `OperationalReceipt` adapters with exact subject hashes, idempotency, permission, replay protection, and correction through a successor receipt rather than mutation.
7. Run an isolated shadow projection and reconcile every item with its source action, owner/SLA policy, knowledge versions, and expected receipt transitions.
8. Connect the existing Kita specialized view for a small internal cohort; keep all secondary notifications disabled.
9. Register Packet 13 outcomes and the Packet 14 team-enablement release gate.
10. Canary one low-risk, internal-only workflow with explicit owner approval. Add bounded internal reminders only after the view canary passes, their own side-effect tests pass, and the canonical intent/approval/started-attempt/terminal-receipt/outcome chain is implemented end to end.

## Golden set and adversarial cases

Use at least 100 public or synthetic work-item chains spanning compliance, client service, product, editorial, revenue, and platform operations, while the live canary floor remains 30 items across at least three team functions. Include:

- missing owner, unavailable owner, conflicting roles, wrong team, reassignment, and backup-owner fallback;
- duplicate briefs from two producers and one action split into two genuinely distinct responsibilities;
- an item acknowledged after its evidence changed;
- a checklist updated after acknowledgment;
- expired, superseded, contradictory, inaccessible, or fabricated knowledge references;
- an urgent low-volume safety item and a high-volume low-risk item;
- notification delivery without acknowledgment and acknowledgment without approval;
- completion with no artifact, partial completion, blocked work, cancellation, and supersession;
- retry after timeout where the receipt was persisted but the response was lost;
- two recipients racing to acknowledge or complete the same revision;
- a client-facing step with no approval, an expired approval, and approval for a different effect;
- PII embedded in a title, excerpt, artifact name, notification, or completion note;
- malicious prompt/instruction text in a source brief;
- timezone/DST/SLA boundary, planned leave, and an unconfigured operating window;
- a completed internal action whose downstream client outcome later fails.

## Tests and metric definitions

Required tests:

- Packet 12 contract, projection parity, single-source-of-truth, and forbidden-transition tests;
- role/permission, owner/backup, SLA-clock, operating-window, and escalation tests;
- acknowledgment/completion hash binding, stale-revision invalidation, idempotency, replay, race, and timeout tests;
- checklist version, required-step, artifact-reference, partial/blocked, and downstream-outcome separation tests;
- knowledge source/freshness/access, contradiction, expiry, and revocation tests;
- PII minimization, redaction, access-control, log, notification, and prompt-injection tests;
- no-client-side-effect guards across email, WhatsApp, Telegram, portal, CRM, filing, submission, payment, and deployment adapters, plus forbidden reminder/escalation execution without an exact unexpired approval and immutable started attempt;
- accessibility and operator/team comprehension tests for the existing Kita projection;
- Packet 13 ID/outcome propagation and Packet 14 known-bad implementation tests.

Materialize every metric below as a canonical `MetricProfile` before evaluation. Pre-register its exact numerator, denominator, window, timezone, late-arrival policy, exclusions, minimum sample, estimator and confidence method, subgroups, guardrails, and decision rule. Metric definitions are frozen before canary:

- **Eligible-item coverage** = eligible Packet 12 actions projected or explicitly rejected with a typed reason divided by all actions meeting the predeclared domain/risk/sensitivity rules. Missing owners and failed projections remain in the denominator.
- **Owner completeness** = visible items with one valid owner or explicit unassigned state plus a valid fallback/escalation path divided by all visible items.
- **Misroute rate** = independently reviewed delivered items requiring reassignment because the original role/team was wrong divided by all reviewed delivered items. Reassignment caused only by availability changes is reported separately.
- **Acknowledgment rate within SLA** = items with a valid acknowledgment receipt before the acknowledgment deadline divided by all delivered items whose acknowledgment deadline elapsed, excluding only items cancelled or superseded before that deadline.
- **Time to acknowledgment** = elapsed time from authorized delivery receipt to valid acknowledgment receipt; report p50/p90 by risk and team function, including breached items at their observed or censored duration.
- **Completion-receipt coverage** = terminal internal-work items with a valid completed, blocked, cancelled, or superseded receipt divided by all items entering a terminal internal-work state. `team.partial` never satisfies this metric and does not enter its denominator until the item reaches a terminal state; `blocked` is not counted as completed.
- **Stale-knowledge exposure** = items delivered while any required claim/reference was already expired, superseded, contradicted, or inaccessible divided by all delivered items.
- **Receipt lineage completeness** = receipts carrying action ID, revision/input hash, actor/role, brief version, checklist version, timestamp, authority scope, and evidence/artifact references divided by all receipts.
- **Client-side-effect count** = client message, client-record mutation, filing, submission, payment, publication, deployment, or other client consequence caused autonomously by this slice. The required value is zero.
- **PII leak count** = raw/reconstructable client PII observed in unauthorized briefs, general views, notifications, fixtures, logs, prompts, exports, or telemetry. The required value is zero.
- **Downstream truth separation** = internally completed items whose client/regulatory outcome is represented only by a separate downstream receipt or explicit `unknown/pending` state divided by all internally completed items.

The Packet 14 canary gate may pass only if eligible-item coverage and owner completeness are each at least 0.99, completion-receipt coverage and receipt lineage completeness are 1.00, stale-knowledge exposure is zero, client-side effects are zero, PII leaks are zero, every critical misroute is zero, and downstream truth separation is 1.00. The misroute-rate target and acknowledgment improvement target must be predeclared from the captured baseline, including raw numerators, denominators, confidence intervals, and subgroup results. A missed sample floor yields `insufficient_evidence`, never `pass`.

## Shadow, canary, and expansion

Run the projection in isolated shadow mode for two complete, predeclared operating windows. Do not assign, acknowledge, notify, escalate, or complete live actions during shadow. Compare proposed routing, briefs, checklists, SLAs, and knowledge versions with independent labels and existing team practice.

The first canary is one low-risk internal workflow, at least one named owner and backup role, and a bounded team cohort approved by the operator. It uses the existing Kita Action Inbox. Client-affecting steps remain locked and no client channel adapter is enabled. Internal reminders start disabled; if later enabled, they receive a separate exact action intent and approval, immutable started attempt, terminal receipt and outcome, rate limit, idempotency proof, privacy check, expiry, and kill switch. Expansion requires two reconciled windows, Packet 14 `PASS`, team usability review, and owner approval.

## Exit criteria

Exit only when:

- the authority, routing, privacy, and knowledge-source maps are reviewed and versioned;
- all Packet 12 projection/receipt adapters validate against `research-os/v1.0.0` and preserve one canonical action identity;
- every visible item has the required brief, owner/unassigned state, backup/escalation, SLA, risk, evidence, knowledge freshness, checklist version, approval boundary, and expected outcome;
- acknowledgment and terminal receipts are immutable, idempotent, revision-bound, permission-checked, and fully traceable;
- all Packet 14 sample, accuracy, safety, privacy, and receipt metrics pass;
- two complete operating windows reconcile within the predeclared tolerance;
- no autonomous client message or action is possible and no client PII crosses an unauthorized boundary;
- a fresh reviewer who did not author the implementation reruns the focused and adversarial suites, samples complete chains end to end, and issues `PASS`.

## Rollback

Disable the team-enablement projection, receipt adapters, and any separately approved internal reminder adapter with independent default-off feature flags. Return users to the unchanged Packet 12/legacy views and workflows. Preserve canonical action/receipt history and emit correction or cancellation outcomes through Packet 13; do not delete audit evidence. Rollback must not change client state, resend a notification, reopen completed work silently, or erase an SLA breach. A drill must prove the old path remains usable and no duplicate effect occurs.

## Independent reviewer handoff

Provide the baseline workflow/surface inventory, exact owned-file list, authority/routing matrix, privacy map, brief and checklist schemas/templates, knowledge freshness rules, receipt schemas and sample chains, Packet 12 parity proof, Packet 13 outcome mapping, golden/adversarial dataset cards, labeling guide, raw metric numerators/denominators/confidence intervals, Packet 14 gate result, no-client-effect proof, shadow/canary reconciliation, usability notes, and rollback drill. The generator cannot be the final grader, and internal completion cannot be accepted as proof of an external client outcome.
