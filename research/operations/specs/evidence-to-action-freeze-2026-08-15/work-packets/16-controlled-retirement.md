---
adversarial_review: exempt-frozen-spec-landed-verbatim-from-10d500e1c
---

# Work Packet 16 — Controlled Retirement and Simplification

**Wave:** 4, last packet
**Depends on:** Packets 01–15 and 17–23, plus Gate G4
**Risk:** high operational/destructive risk; deletion requires separate approval
**Purpose:** remove duplicate paths only after the replacement is proven

## Session prompt

You own simplification. Your task is not to delete old code because a new architecture exists. You must prove consumer parity, replay safety, rollback, and owner acceptance before disabling one path at a time.

You are not alone in the codebase. Work in a dedicated worktree, preserve concurrent changes, and begin with inventory and deprecation instrumentation. Never delete databases, queues, artifacts, LaunchAgents, or protected data without explicit target-level authorization and a recoverable backup/rollback. Never merge, deploy, or unload a live job on your own authority.

The first session is inventory-only: it may refresh topology, populate the deprecation registry, and nominate exactly one named lowest-risk candidate, but it may not disable or remove anything. Every later retirement is its own dispatched child session, worktree, branch, diff, independent review, exact owner approval, rollback drill, and atomic commit. This packet is a program contract, not permission for one giant cleanup session.

## Mission

Leave Nuzantara with one evidence spine, one claim ledger, one restricted institutional graph, one decision queue, one canonical NotebookLM feed, truthful publication states, and WR2/WR3 as production foundries—while preserving history and a tested return path.

## Candidate retirement inventory to reverify

Candidates—not automatic decisions—include:

- the MATA GARUDA WR2 bridge that emits an unsupported `intel.research_dossier` type;
- duplicate MATA/Intel Lake NotebookLM feeds;
- parallel/raw queues whose consumers have moved to canonical Intel events;
- misleading internal fields/files such as `auto_publish`, `auto_approved`, and `published_articles.json` once compatible state adapters are complete;
- standalone review queues and cockpits whose objects/actions are fully represented in the Kita Action Inbox;
- stale or split-brain graph readers such as a non-authoritative Mini snapshot;
- no-op routes, fixture-only jobs, dormant public-channel paths, and stale launch definitions;
- old WR2/WR3 contract fields replaced by lossless canonical adapters.

Refresh the full live inventory. A candidate may be retained if it serves a distinct verified purpose.

## File ownership

This packet owns:

- deprecation registry and runtime-use instrumentation;
- feature flags and cutover/reconciliation tooling;
- focused removal patches after approval;
- operator runbooks, archival manifests, and rollback drills;
- tests proving no active consumer depends on the retired path.

It does not own new features or redesign. Changes span domains only through small, separately reviewable commits, one retirement per commit.

## Inputs and frozen gates

For each candidate require:

- replacement owner and canonical contract;
- producer and consumer inventory;
- two complete parity windows or a stricter domain-specific requirement;
- zero unexplained stranded/dead-letter messages;
- successful replay and duplicate-side-effect checks;
- live-use telemetry showing no unknown consumer;
- tested rollback;
- data retention/archive decision;
- independent reviewer and a target-specific `ActionIntent` plus unexpired effect-specific owner `ApprovalReceipt`.

## Deliverables

1. Machine-readable deprecation registry with owner, path, reason, replacement, consumers, data, flag, planned date, evidence, rollback, and status.
2. Runtime-use counters and unknown-consumer alerts before any disablement.
3. Per-candidate parity and dependency report.
4. Feature-flagged disablement before code/data removal.
5. Dead-letter/stranded-message drain and audit receipts.
6. Archive manifest for code/config/data that must remain recoverable.
7. One small atomic retirement change at a time, with tests and rollback drill.
8. Updated architecture/runbooks/observability with stale references removed.
9. Final complexity report: active producers, consumers, queues, feeds, cockpits, jobs, and failure paths before versus after.

## Non-goals

- Do not combine cleanup with feature development.
- Do not delete historical evidence, claims, approvals, outcomes, or provenance.
- Do not remove a path based only on code search; prove live non-use.
- Do not retire fallback during the same window as replacement canary.
- Do not normalize away distinct security boundaries, especially NEXUS.
- Do not optimize for line-count reduction over operational clarity.

## Implementation sequence

1. Inventory code, runtime jobs, streams, tables, endpoints, UIs, docs, and external consumers.
2. Classify each as `retain`, `consolidate`, `deprecate`, `archive`, or `unknown`.
3. Add use instrumentation and deprecation warnings.
4. End the inventory session by nominating exactly one lowest-risk candidate and emitting a separate dispatch packet for it.
5. In the candidate's dedicated child session, collect parity/replay/rollback evidence, obtain independent review, and materialize the exact disable proposal through Packet 18 and Packet 12.
6. Disable that one candidate behind a flag only after an unexpired effect-specific owner `ApprovalReceipt` binds the exact `ActionIntent`; create an immutable `ExecutionAttempt` only when the disable starts, then record its terminal `OperationalReceipt` and `OutcomeEvent`. Monitor unknown consumers and missed outcomes for one complete window.
7. If clean, propose removal as a new, separately hashed `ActionIntent` with a new approval, started attempt, terminal receipt, and outcome; remove only that candidate's code/config in a later atomic change while preserving archive/data.
8. Close the child session only after all expected operational receipts and outcomes reconcile, before dispatching another candidate; never batch unrelated retirements.
9. After all approved child retirements, run the final topology and failure-injection audit.

## Adversarial cases

- an undocumented cron calls the endpoint;
- a consumer appears only weekly/monthly;
- queue lag is zero because unknown messages are ACKed and dropped;
- replacement succeeds but loses a field;
- rollback relies on already-deleted data;
- two feeds differ only during a source outage;
- UI is unused but API remains externally consumed;
- stale docs cause an operator to re-enable an old path;
- a protected NEXUS boundary is mistakenly “consolidated” into a general service.

## Tests and exit criteria per retirement

- dependency and runtime-use scan;
- parity of counts, hashes, state, fields, and side effects;
- bounded replay and duplicate-effect test;
- dead-letter/unknown-message test;
- failure injection with replacement unavailable;
- rollback drill from the disabled state;
- runbook/operator validation.

A retirement exits only when live use is zero or all consumers are migrated, two complete windows reconcile, no message is stranded, rollback succeeds, protected/history data is retained, observability points to the replacement, independent review passes, and each exact disable/remove effect has its own valid intent, approval, immutable started attempt, terminal operational receipt, and outcome.

## Program rollback

Every retirement starts with a reversible flag. If any unknown consumer, missing outcome, security regression, or unexplained divergence appears, stop further retirements and propose re-enable as an emergency action through the same exact approval/attempt/receipt chain; a narrowly defined pre-approved rollback intent may be used only while its bindings and expiry remain valid. Replay from retained data where safe and open an incident. Destructive data cleanup is outside this packet unless separately authorized.

## Reviewer handoff

For every candidate provide the registry entry, live-use evidence, dependency map, parity windows, replay result, dead letters, field-loss report, rollback drill, archive manifest, approval, and before/after topology.
