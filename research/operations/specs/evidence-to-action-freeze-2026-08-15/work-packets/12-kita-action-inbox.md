---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 12 — Kita Action Inbox and Action Routing

**Wave:** 2
**Depends on:** Packets 04, 05, 06, and 07
**Feeds:** Packets 13–16
**Risk:** high operational-routing risk; no autonomous consequential action

## Session prompt

You own the one persistent decision queue through which evidence becomes accountable work. Consolidate semantics and adapters; do not build another cockpit beside Kita.

You are not alone in the codebase. Use a dedicated worktree, declare the backend/frontend/routes you own, preserve concurrent changes, and do not delete existing queues or dashboards. Migration `275` is reserved for this packet. Refresh the authoritative Pro head; if the central reservation is stale or occupied, stop and request a versioned ledger revision. Never expose raw NEXUS data or client PII in a general inbox. Do not send messages, alter CRM records, publish, or trigger client-facing actions without the specific approval receipt required by the action.

## Mission

Give the operator and team one queue where every candidate says why it matters now, what evidence supports it, what is uncertain, what action is recommended, who owns it, when it is due, what approval is required, and what happened downstream.

## Baseline to establish

Inventory all current decision/review surfaces and queues: Intel staging/News Room, WR2 Control, Damar/publish queues, WR3 supervisor states, regulatory alerts, compliance queues, WhatsApp operator action inbox, CRM opportunity/renewal queues, Telegram votes, and relevant Kita workspace views. Map duplicate objects, state names, owners, and actions. Measure queue age, orphan rate, duplicate rate, acknowledgement rate, and untraceable side effects.

## File ownership

Preferred ownership boundary:

- a new or existing backend Action Inbox service, repository, router, and additive migration;
- focused Kita/mouth workspace components and client API for the inbox;
- adapters from existing queues that produce validated `DecisionPacket` views;
- action/approval/operational-receipt and downstream-status adapters;
- focused tests and a migration/runbook.

Do not refactor each producer's internal implementation. Do not delete old UIs or queues. Packet 16 owns retirement after parity.

## Inputs and frozen contracts

- `DecisionPacket`, `RequestedActionSpec`, `ActionItem`, `ActionIntent`, `ApprovalReceipt`, immutable started `ExecutionAttempt`, typed `OperationalReceipt`, `WorkflowRun`, and `OutcomeEvent` from Packet 04.
- Intel candidates from Packet 05; claims/evidence from Packet 06.
- NEXUS supplies only sanitized, reviewed packets from Packet 07.
- Strongest risk/sensitivity propagation and scoped authority.

## Deliverables

1. Packet 04 immutable `ActionItem` queue snapshots plus separate `ActionIntent`, `ApprovalReceipt`, immutable started `ExecutionAttempt`, and typed `OperationalReceipt` records. The current inbox row is only a rebuildable projection; no composite “canonical action” status may collapse these axes.
2. Queue state machine exactly: `new`, `triaged`, `assigned`, `awaiting_decision`, `ready`, `closed`. Approval decisions and execution states remain on their own immutable contracts.
3. One inbox with filtered specialized views—not separate truth stores—for editorial, compliance, client service, revenue, product, NEXUS, and platform operations.
4. Queue-only decisions: triage, reject/close, snooze, assign, split, merge-duplicate, and request evidence. Each atomically appends an immutable `ActionItem` successor, its edge, and a registered typed `OperationalReceipt`; none is an `ApprovalReceipt` or execution authority. A substantive decision on the underlying `DecisionPacket` uses its own compatible `ApprovalReceipt`. Consequential effects become exact, separately approved `ActionIntent` objects.
5. Before/after hashes, purpose-bound actor references, and immutable intent/approval/started-attempt/operational-result receipts.
6. SLA/aging/escalation logic that never interprets silence as approval.
7. Adapter status for every legacy queue, including mapping losses and source links.
8. Sanitized notification summaries; links resolve to authorized detail views.
9. Full downstream status and outcome timeline derived from exact typed `OperationalReceipt` and `OutcomeEvent` references, never a mutable attempt status.
10. One idempotent Packet 12 general runtime service around Packet 04's canonical repository primitive. It turns an exact `RequestedActionSpec` into one `ActionItem` plus one `ActionIntent` atomically, preserves the spec reference and fields losslessly, and performs no execution. It must not fork or reimplement that primitive.
11. A Packet 04-governed operational-receipt type registry and Packet 12 adapters for at least `execution.result`, `routing.assignment`, `queue.triage`, `queue.rejected`, `queue.snoozed`, `queue.split`, `queue.merge_duplicate`, `queue.evidence_requested`, `team.acknowledgment`, `team.completion`, `team.blocked`, `team.cancelled`, and `team.superseded`; Packet 12 owns projections and validation hooks, not a parallel receipt envelope.

## Non-goals

- Do not create a new standalone dashboard or duplicate every producer's data.
- Do not surface raw NEXUS graph rows, private locations, credentials, or client PII.
- Do not allow a broad “approve” to authorize unspecified external effects.
- Do not auto-execute amber/red actions.
- Do not auto-execute green or “internal” actions either. Every execution requires a specific, unexpired approval binding the exact `ActionIntent` ID/hash, `arguments_hash`, and `input_revision_hash`.
- Do not compress semantically distinct choices into an “Approve all” receipt. One screen may present a batch, but each intent retains its own receipt and authority scope.
- Do not retire legacy queues in this packet.
- Do not use a ranking model without explainable features and evaluation.

## Implementation sequence

1. Freeze the queue/surface inventory and a state/action compatibility matrix.
2. Import the Packet 04 canonical records and atomic requested-action materialization primitive, add Packet 12 projections/adapters in migration 275, and implement the general runtime permission/idempotency boundary without local contract or primitive redefinition.
3. Build read-only adapters for legacy queues.
4. Present a unified shadow inbox and reconcile counts/states.
5. Enable queue-only triage/reject/snooze/assign/split/merge/evidence-request decisions by atomically appending the exact `ActionItem` successor, `ObjectSuccessorEdge`, and registered typed `OperationalReceipt`. These use role permission, not `ApprovalReceipt`, and authorize no downstream effect.
6. Add one mocked low-risk internal adapter that creates an immutable started `ExecutionAttempt` only after an exact approval receipt, then appends a separate typed result `OperationalReceipt`; the packet performs no live execution.
7. Canary a small operator/team cohort; keep old surfaces readable.
8. Measure duplicate reduction across the reconciled union of old and new queues, action time, and operator comprehension through preregistered `MetricProfile`s.

## Golden set and adversarial cases

Use at least 100 items across all nine outcome families and all risk classes. Include duplicates from two queues, stale claims, missing owner, expired SLA, changed inputs after approval, restricted NEXUS packet, two actions requiring different authority, generic/batch approval, action replay, and a downstream timeout after the mocked effect succeeded.

## Tests and exit criteria

- state-machine and permission property tests;
- approval-scope and input-hash invalidation tests;
- idempotent downstream-command/reconciliation tests proving attempts are never updated and typed result receipts bind their exact attempt hashes;
- operational-receipt registry tests for acknowledgment, completion, blocked, cancellation, supersession, assignment, every queue-only decision, and execution-result required fields;
- queue transaction tests proving exact successor/edge/receipt atomicity, rollback on partial write, and zero `ApprovalReceipt` or `ExecutionAttempt` creation;
- NEXUS sanitization and PII redaction tests;
- adapter parity/count/state tests;
- accessibility and role-based UI tests;
- injected timeout/retry/duplicate tests.
- axis-separation property tests proving queue state cannot fabricate approval or execution truth;
- `RequestedActionSpec` materialization, lossless-field, transaction-rollback, race, and replay tests proving one stable ActionItem/ActionIntent pair and zero effects;
- `MetricProfile` validation with fixed numerator, denominator, sample floor, confidence method, subgroups, guardrails, and `insufficient_evidence` behavior.

Exit only when every canary item has one canonical identity, owner or explicit unassigned state, SLA, risk, strongest inherited sensitivity, evidence link, allowed actions, and separate queue/approval/execution truth; unauthorized or stale approvals fail closed; the preregistered duplicate and latency metrics satisfy their thresholds across the union of all old and new sources without hiding any source; unmet sample floors return `insufficient_evidence`; no restricted field leaks; and an independent reviewer plus operator usability review passes.

## Shadow, canary, and rollback

Begin as a read-only projection. Canonical actions remain side-effect-free until each action adapter is separately approved. Rollback hides the unified write controls and returns users to legacy surfaces; canonical receipts remain for audit. No old queue is removed before Packet 16.

## Reviewer handoff

Provide the surface inventory, mapping matrix, queue reconciliation, permissions model, redaction tests, action/approval receipts, timeout/replay evidence, usability notes, and list of legacy queues still authoritative.
