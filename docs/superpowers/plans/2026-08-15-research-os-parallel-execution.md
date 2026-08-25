# Research OS v1.0.0 Parallel Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Use `agent-session-discipline` for every mutation session and `sota-architecture-loop` at G1–G4. A builder never grades, merges, deploys, publishes, sends, or performs an unlisted live effect.

**Goal:** Execute the frozen 23-packet Research OS program with the maximum safe parallelism, one immutable campaign base, independent review, serial shared integration, measured shadow/canary windows, and reversible one-target retirement.

**Architecture:** One persistent operator–AI Conductor owns a Pro-authoritative run registry and dispatches bounded workers from the frozen packet DAG. Up to two builders work in parallel on non-overlapping artifacts (Amendment A2, 2026-08-23 — reduced from four; see `research/operations/execution/research-os-v1.0.0/README.md`). Each result is independently reviewed and then queued to one serial integrator. Live effects remain separate owner-authorized actions. Retirement starts only after the replacement, outcomes, and evaluation gate are proven.

**Tech Stack:** Git worktrees, Python 3, JSON/JSONL receipts, Redis leases, PostgreSQL migration train, FastAPI, Next.js/TypeScript, Qdrant, NotebookLM adapters, Intel Lake, MATA GARUDA, NAGA, NEXUS, WR2, WR3/FlowKit, pytest, Ruff, MyPy, Jest/Vitest as present, deterministic replay and on-disk empirical review.

**Frozen inputs:**

- [`README.md`](../../../research/operations/specs/evidence-to-action-freeze-2026-08-15/README.md)
- [`CONTRACTS.md`](../../../research/operations/specs/evidence-to-action-freeze-2026-08-15/CONTRACTS.md)
- [`DEPENDENCY-DAG.md`](../../../research/operations/specs/evidence-to-action-freeze-2026-08-15/DEPENDENCY-DAG.md)
- [`DISPATCH-MANIFEST.md`](../../../research/operations/specs/evidence-to-action-freeze-2026-08-15/DISPATCH-MANIFEST.md)
- [`SESSION-BOARD.md`](../../../research/operations/execution/research-os-v1.0.0/SESSION-BOARD.md)
- [`WAVE-0-DISPATCH.md`](../../../research/operations/execution/research-os-v1.0.0/WAVE-0-DISPATCH.md)
- [`RETIREMENT-REGISTER.md`](../../../research/operations/execution/research-os-v1.0.0/RETIREMENT-REGISTER.md)

---

## Program invariants

1. The frozen architecture is read-only. Evidence that contradicts it creates a versioned change proposal; it is never silently reinterpreted by a worker.
2. `max_concurrent_builders = 2` across all machines (Amendment A2, 2026-08-23 — reduced from four). A reviewer that only reads may overlap if it does not contend for a saturated host. A reviewer repair consumes a builder slot.
3. One Conductor places lanes sequentially. Execution fans out only after reservations, worktrees, exact heads, scopes, and leases are verified.
4. One packet or explicitly split sub-packet per builder. One writer per path/registry/resource.
5. The migration integration order is exactly `research_os_contract_core → 271 → 272 → 273 → 274 → 275 → 276`. The first link is a symbolic name, not a fixed integer — the original `270` was found entirely void on 2026-08-23; see `research/operations/execution/research-os-v1.0.0/SESSION-BOARD.md` §0 (Migration-ledger decision 001).
6. The serial integrator is different from the builder and reviewer. It integrates one approved SHA at a time.
7. A technical PASS grants eligibility only. It never grants production migration, deploy, publish, message, scheduler, service, flag, secret, CRM, OSINT, or paid-render authority.
8. Raw client PII and restricted OSINT stay on their authorized Pro boundary. Commit artifacts contain only synthetic/public/redacted/aggregate/hash-addressed evidence.
9. `insufficient_evidence` is not PASS. A fixture-only PASS is not live readiness.
10. Retirement disables one target reversibly, observes it, and removes it only through a later separately approved action.

## Critical path and event-driven release

```text
P04
 → max(P01-final, P05, P06)
 → P07
 → P12
 → P18
 → max(P09-runtime, P10, P11)
 → P13
 → P14
 → max(P15, P19, P20, P21, P22, P23)
 → P16
```

P02 and P17 must join before P18. P03 must join before P11. P08 must join before P14 and before any P12 grounded canary. Packets release as soon as their exact predecessor receipts are valid; a fast branch never waits for an unrelated lane in the same thematic wave.

---

### Task 1: Independently review and freeze the execution control room

**Files:**

- Review: `research/operations/execution/research-os-v1.0.0/README.md`
- Review: `research/operations/execution/research-os-v1.0.0/SESSION-BOARD.md`
- Review: `research/operations/execution/research-os-v1.0.0/WAVE-0-DISPATCH.md`
- Review: `research/operations/execution/research-os-v1.0.0/RETIREMENT-REGISTER.md`
- Review: `docs/superpowers/plans/2026-08-15-research-os-parallel-execution.md`

**Step 1: Verify mechanics**

Run from the isolated execution-plan worktree:

```bash
git diff --check
git status --short
```

Run a local-link resolver over every changed Markdown file and verify all relative targets exist. Check balanced code fences, one H1 per file, no placeholder tokens, and no credential-shaped strings.

**Step 2: Create the candidate control-room commit**

```bash
git add research/operations/execution/research-os-v1.0.0 \
  docs/superpowers/plans/2026-08-15-research-os-parallel-execution.md
git commit -m "docs(research-os): organize parallel execution and retirement"
```

This commit creates the first reviewable identity. Do not push, open a PR, merge, or launch a packet.

**Step 3: Dispatch two independent read-only reviews against that exact commit**

- Reviewer A: dependency/collision/migration/base-ref correctness.
- Reviewer B: retirement safety/live-use/rollback/authority correctness.

Both reviewers inspect the exact candidate commit and recorded document hashes, then return only `PASS`, `PASS_WITH_LIMITS`, `FAIL`, or `insufficient_evidence`, with file-and-line findings.

**Step 4: Repair P0/P1 findings through a successor commit**

Use a separate bounded repair session. Any repair creates a new commit SHA, invalidates the applicable previous review, and requires the mechanical checks plus both applicable reviewers again against the successor SHA.

**Step 5: Record the final reviewed revision**

```bash
git show --stat --oneline HEAD
git status --short
```

Expected result: one final locally reviewed feature-branch revision, possibly preceded by superseded candidate commits. Record its exact SHA and document hashes in the control-room review receipt. Do not push, open a PR, merge, or launch a packet as part of this task.

---

### Task 2: Build the thin campaign-control adapter (Session S00)

**Not exercised — superseded by the 2026-08-23 execution amendment in `research/operations/execution/research-os-v1.0.0/README.md`.** Amendment A1 rules that this campaign runs on the existing agent-worktree broker, Redis lease registry, and GitHub merge queue instead of building S00; this task is left below as the record of the bootstrap design that was not carried out, not as live work to perform.

This is execution infrastructure, not a twenty-fourth semantic packet.

**S00-only bootstrap gate:** this is the sole bounded exception to the normal packet-session protocol, because S00 creates that protocol's registry and sidecars. Make the exact independently reviewed Task 1 commit available to Pro through an immutable feature ref as `control_room_sha`; reverify its relationship to current Pro source and critical tooling hashes. If it is not a safe direct source base, an interactive operator-controlled integrator creates one conflict-free bootstrap-composition commit from an operator-approved immutable Pro source ref plus the exact reviewed control-room change, and an independent reviewer approves that exact composed SHA. Record the final reviewed immutable commit as `s00_base_sha`, create one dedicated Pro S00 worktree from it, acquire the existing Pro path/repository leases through a non-fail-open operation, verify `HEAD == s00_base_sha`, and write an immutable branch-bound bootstrap scope receipt before editing. Recheck collisions after creation. No packet session or live effect may run concurrently. This exception terminates after S00's final reviewed commit creates the normal controls and becomes the 23-packet `campaign_root_sha`; it is never reusable.

**Files:**

- Modify: `scripts/fleet_dispatch.py`
- Modify: `scripts/agent_start.py`
- Create: `scripts/research_os_campaign.py`
- Create: `scripts/tests/test_research_os_campaign.py`
- Modify/create focused tests for `fleet_dispatch.py` and `agent_start.py`
- Create: `research/operations/execution/research-os-v1.0.0/INTEGRATION-MANIFEST.schema.json`
- Create: `docs/runbooks/research-os-campaign-control.md`

**Ownership/lease:** `session-tooling`, `research-os-campaign-control`, and exact script paths. Do not combine this with a packet implementation.

**Step 1: Write failing tests**

Cover:

- the S00 bootstrap accepts only the exact reviewed `s00_base_sha`, branch-bound scope receipt, Pro leases and authority fingerprint, and terminates before any packet dispatch; an absent/moving/mismatched source or concurrent session fails closed (superseded by the 2026-08-23 execution amendment in `research/operations/execution/research-os-v1.0.0/README.md` — this test spec describes the unbuilt S00 bootstrap);
- each dispatch carries `campaign_root_sha`, monorepo `dispatch_base_sha`, `source_repository`, and immutable `source_base_sha` through reservation, placement and handoff;
- monorepo lanes require `source_base_sha == dispatch_base_sha`; external P01/P07 lanes require an independently approved immutable OSINT-Nexus source ref and fail closed without it;
- the worktree refuses to start when repository identity differs or `HEAD != source_base_sha`;
- `.agent-task.json` records base SHA, packet ID/hash, contract hash, owned paths, dependencies, and run ID;
- `max_concurrent_builders=2` queues the third builder (Amendment A2, 2026-08-23 — reduced from four);
- Redis unavailable refuses reservation;
- check/create is wrapped by a campaign/path reservation and post-create collision recheck;
- stale heartbeat becomes `needs_reconcile`;
- a review receipt for commit A is invalid for commit B;
- run-manifest writes use lock + temporary file + atomic rename;
- every receipt binds `authority_host=Pro`, absolute registry root, Redis host/port/database/keyspace identity, and backend fingerprint;
- Air/Mini-local Redis, wrong-backend fingerprints, fail-open lease behavior, and sidecar-write failure all stop dispatch;
- the reviewed topology policy binds `authority_host=Pro`, `control_surface=Air-M5`, and `excluded_nodes=[Mini-Pro2]`; Mini-Pro2 unreachability does not block S00, no Mini probe is required, and any campaign placement/ref/worktree/lease request targeting Mini-Pro2 is rejected;
- the S00 bootstrap uses direct Pro-authoritative worktree, path, registry and lease inventory; a pre-S00 generic fleet failure caused solely by probing excluded Mini-Pro2 records `excluded_node_ignored`, while any unknown or failed participating Pro/Air authority input remains fail closed;
- builder, Gear-2 reviewer, Gear-3 judge, and I1 integrator session IDs/families are recorded; self-review and same-family Gear-2 review are rejected;
- completed receipt replays idempotently, while unknown/in-progress/failed state stops automatic continuation;
- the frozen packet Dispatch Manifest remains merge-forbidden, while a separately instantiated integration manifest binds one integrator, reviewed source/review receipt, source/destination repository, control and repository checkpoints, worktree/branch, leases, expected merge-tree/result hashes, tests and expiry;
- absent, stale, mismatched or over-broad integration manifests refuse integration, and only one exact conflict-free isolated-branch merge is representable; rewriting, conflict repair, `main`, deploy, production migration, scheduler/service/flag/publication/paid effects remain forbidden;
- no command merges, deploys, publishes, starts a scheduler, restarts a service, or executes a packet.

**Step 2: Implement the smallest adapter**

The adapter should:

- create/validate `~/.organism/frozen-packet-runs/<run-id>/` on Pro;
- encode the closed campaign topology and filter excluded nodes before capacity or collision admission, without treating excluded-node reachability as an authority dependency;
- hash frozen packet/contract/DAG inputs;
- maintain a single-writer run manifest and append-only event/receipt indexes;
- reserve packet/path/shared resources before sequential placement;
- pass and verify all four lineage fields and require worktree `HEAD == source_base_sha`;
- expose `plan`, `reserve`, `place`, `record-handoff`, `record-review`, `create-integration-manifest`, `queue-integration`, `record-integration`, and `status` commands;
- produce and validate the dedicated hash-bound integration-manifest schema without weakening the merge prohibition in the ordinary packet manifest;
- never launch an LLM, merge, deploy, or perform a live effect;
- make side effects explicit and default to none.

Air-M5 is a remote control surface only: every mutation of the run registry or campaign lease executes through and is attested by the Pro authority.

Do not turn this into a daemon, new database, generic workflow engine, or alternate Action Inbox.

**Step 3: Run focused tests**

```bash
apps/backend-rag/.venv/bin/python -m pytest scripts/tests/test_research_os_campaign.py -q
apps/backend-rag/.venv/bin/python -m pytest scripts/tests -k 'fleet_dispatch or agent_start' -q
```

**Step 4: Create the S00 candidate commit**

```bash
git add scripts/fleet_dispatch.py scripts/agent_start.py \
  scripts/research_os_campaign.py scripts/tests \
  research/operations/execution/research-os-v1.0.0/INTEGRATION-MANIFEST.schema.json \
  docs/runbooks/research-os-campaign-control.md
git commit -m "feat(ops): add frozen research campaign control"
```

**Step 5: Independently review the exact candidate SHA**

The reviewer binds the exact commit SHA and artifact hashes, then reproduces bootstrap mismatch, repository/base mismatch, Redis failure, fifth-builder queueing, stale-review invalidation, collision refusal, and absent/stale/over-broad integration-manifest refusal. The implementation cannot be used by Wave 0 until this review passes.

**Step 6: Repair only through a successor commit**

Any change after review creates a new commit and invalidates that verdict. Run the focused checks again and obtain a fresh independent review of the successor SHA; never rebase or amend the reviewed candidate.

**Step 7: Freeze the campaign root**

Only the final independently reviewed S00 SHA becomes `campaign_root_sha`. Record the exact SHA, hashes, bootstrap receipt and review receipt; then terminate the S00-only exception and require the normal packet protocol for every later session.

---

### Task 3: Create the Pro-authoritative campaign run (Wave −1)

**External runtime state:**

- Create: `~/.organism/frozen-packet-runs/<run-id>/run-manifest.json` on Pro
- Append: `events.jsonl`, `integration-queue.jsonl`
- Create immutable receipt paths under `receipts/<packet-id>/` and `reviews/<packet-id>/`

**Step 1: Reverify Pro truth**

Read current Pro `HEAD`, `origin/main`, worktrees, dirty paths, fleet topology, capacity, Redis lease backend, migration ledger, and exact frozen input hashes. Never edit the dirty main checkout.

**Step 2: Select the campaign base**

Use the reviewed S00 commit as immutable `campaign_root_sha`. Create an immutable feature ref on Pro; Air-M5 may consume a read-only mirror as the operator control surface, while Mini-Pro2 must not fetch, check out, synchronize, or execute that ref. Initialize the first monorepo integration checkpoint to the same SHA and record ref and hashes. Later control-plane checkpoints are append-only successors; the campaign root never moves. Every dispatch also binds `source_repository` and `source_base_sha`; for monorepo lanes the source base equals the selected `dispatch_base_sha`, while external P01/P07 lanes require their own operator-approved immutable OSINT-Nexus ref. This is not a main merge or deployment.

**Step 3: Initialize the registry**

Record all 23 packets, split identities `P01-prep/P01-final` and `P09-schema/P09-runtime`, DAG predecessors, exact owned paths, serial groups, migration numbers, model roles, and default side-effect ceilings.

**Step 4: Reserve and validate**

Acquire the campaign lease; calculate pairwise path intersections; place collisions into a serial group; validate DAG acyclicity and migration order; verify all packet paths/hashes.

**Step 5: Emit readiness receipt**

Expected status: Wave 0 entries registered, zero workers running, zero live effects, exact base/head equality proven. An independent reviewer checks the registry before any placement.

---

### Task 4: Dispatch Wave 0 with two active builders maximum (Amendment A2, 2026-08-23 — reduced from four; see `research/operations/execution/research-os-v1.0.0/README.md`)

Follow [`WAVE-0-DISPATCH.md`](../../../research/operations/execution/research-os-v1.0.0/WAVE-0-DISPATCH.md) exactly.

**Initial active set:**

- P04 canonical contracts on Pro;
- P01 Tasks 1–6 on a separately preserved OSINT-Nexus Pro worktree;
- P03 WR3/FlowKit zero-spend readiness on Pro;
- P05 Intel/MATA preparation on the fourth available Pro builder slot.

**Queued next:** P06 NAGA preparation. It enters when one of the four Pro slots clears and no other preparation lane is active. If Pro capacity makes three hot-path lanes unsafe, queue the lower-priority lane; do not move protected work to Air-M5 or any work to Mini-Pro2.

**Step 1: Place sequentially**

For each lane: immutable manifest → leases → capacity/collision dry run → worktree from exact base → HEAD/metadata/scope/lease verification → worker acceptance.

**Step 2: Run builders in parallel**

Each builder edits only its declared paths, commits atomically, writes a worker handoff receipt, and stops at `review_ready`.

**Step 3: Review as branches finish**

Dispatch independent reviewers without waiting for the entire wave. A repair receives a successor manifest and consumes a builder slot.

**Step 4: Integrate only P04/P03 candidates**

- Integrate P04 first through I1 after its semantic PASS; its `research_os_contract_core` migration (integer bound at integration time, not 270 — see invariant 5 above) is test-only in this program branch until separately authorized for any real environment.
- P03 may integrate only after a P04 compatibility review and only with zero-spend behavior.
- P01 remains a shadow candidate; its five production effects are not part of Wave 0.
- P05/P06 preparation bundles are evidence inputs, not runtime branches.

**Wave 0 exit:** reviewed P04, P01 shadow, P03 zero-spend readiness, P05/P06 prep bundles; no external effect.

---

### Task 5: Open G1 and run contract-adoption Cohort B

**Parallel builders, maximum four:**

- P01-final authority/cutover preparation;
- P02 publication truth and migration 271;
- P05 Intel Lake v2/MATA and migration 272;
- P06 NAGA claim ledger and migration 273.

**Step 1: Create successor implementation lanes from the reviewed P04 checkpoint**

Preparation branches are immutable evidence, not implementation branches. Open fresh worktrees and successor manifests from the exact integrated P04 checkpoint, reference the preparation receipts, and revalidate adapter loss maps. Never rebase or reuse the preparation branch, and never merge preparation-generated schemas blindly.

**Step 2: Implement packet-owned code**

Follow each frozen packet's file ownership, golden/adversarial sets, tests, metrics, flags, rollback, and reviewer handoff. Keep all flags off and all migrations unapplied outside isolated tests.

**Step 3: Serialize migration integration**

I1 integrates and tests:

```text
271 P02
272 P05
273 P06
```

No branch renumbers or skips a migration. A conflict stops the queue for a versioned ledger decision.

**Step 4: Keep P01 effects separate**

The source candidate may become eligible, but credential rotation, template installation, Neo4j binding mutation, UI restart, and H24 restart each require a separate exact authority chain. If those actions are not approved, P01 remains `owner_gate`; other code work can continue where the DAG permits.

**Cohort exit:** P02/P05/P06 independently reviewed and integrated, G0/G1 evidence current, P01 containment either verified live through five authorized effects or explicitly held at `owner_gate` with no false completion claim.

---

### Task 6: Build the evidence spine and integrate migration 274

**Parallel builders, maximum four:**

- P07 NEXUS entity resolution on a disposable synthetic clone;
- P08 hybrid retrieval baseline/challenger;
- P17 NotebookLM verification adapter;
- P09-schema only, migration 274 and disabled projections/cursors.

**Step 1: Enforce exact prerequisites**

- P07 waits for P01/P04/P05/P06 receipts and never mutates production NEXUS.
- P08 waits for P05/P06; P17 must pass before grounded canary.
- P17 waits for P04/P06 and reuses canonical repositories; new persistence stops the lane.
- P09-schema waits for P02/P04 contract review and contains no Action Inbox, Conductor, publisher, or outward runtime activation.

**Step 2: Run independent evaluations**

Preregister every incumbent/challenger metric before examining candidate results. Record `REJECTED_CANDIDATE` when advanced retrieval/entity techniques fail to produce material lift without privacy/latency/safety regression.

**Step 3: Integrate migration 274**

I1 integrates 274 only if it is independently valid without P12/P18 runtime. If not, stop and revise the migration ledger; never apply 275 first.

**Step 4: Hold evidence windows**

Complete the packet-specific windows. P17 requires two complete reconciliation windows; P07 requires its declared cycles/sample floor. Parallel code cannot substitute for missing observations.

**Exit:** G2 evidence receipt, P08 baseline, P17 verifier, P07 synthetic-clone evidence, P09 schema disabled.

---

### Task 7: Implement P12 Action Inbox and migration 275

**Files:** exact packet-owned backend, frontend, state-machine, receipt and focused-test paths from Work Packet 12.

**Step 1: Refresh entry gate**

Require P04/P05/P06/P07 PASS. P12 core may build according to the frozen DAG, but no grounded canary opens before P08/P17/G2 are valid.

**Step 2: Implement one action runtime**

Use P04's canonical `RequestedActionSpec → ActionItem + ActionIntent` primitive. Implement permissions, state transitions, queue-only operational receipts, exact approval separation, projections and UI. Do not create a second action/approval ledger.

**Step 3: Test adversarial authority cases**

Assignment, triage, snooze, merge, split, evidence request, acknowledgment and closure must not authorize an execution attempt. Only an exact unexpired `action_intent + approve` receipt may do so.

**Step 4: Integrate 275 serially**

After independent review, I1 confirms 270–274 already exist and integrates 275. No production application or external action occurs.

---

### Task 8: Implement P18 Conductor session bridge

**Entry:** P02/P04/P06/P12/P17 PASS on the integrated base.

**Step 1: Reconcile canonical contracts**

Reuse P12 persistence. If P18 discovers a need for a new table/migration, stop for a ledger revision; do not allocate 277 privately.

**Step 2: Implement hash-bound handoffs**

Implement the interaction/lock/handoff bridge so it can create a reviewed decision/action request but cannot execute, send, publish, deploy or mutate a service autonomously.

**Step 3: Test stale and replayed sessions**

Reject stale locks, mismatched hashes, superseded packet revisions, replayed approvals, missing receipts and session identity leakage.

**Step 4: Review and integrate**

Require a different family reviewer. I1 confirms no alternate action store, approval path, or hidden outward endpoint.

---

### Task 9: Run the three production-foundry surfaces in parallel

**Parallel builders:**

- P09-runtime Blog/Magazine/SEO;
- P10 WR2 carousel foundry;
- P11 WR3 video foundry.

**Entry:** P18 plus each packet's additional dependencies. P11 also requires P03 compatibility and exclusive `wr3-runtime` ownership.

**Step 1: Freeze exact content/media IDs**

Verify `IntelEvent`, `Claim`, `DecisionPacket`, `ContentObject`, media manifest, workflow, verification, approval and outcome references remain lossless across each surface.

**Step 2: Keep outward stops**

- P09 remains human-gated for publication.
- P10 produces reviewed drafts/assets; final Instagram action is manual and separately authorized.
- P11 starts with zero-spend fixtures. Any Flow/Veo pilot is a separate cost-bounded owner-authorized action with current extension/credit truth.

**Step 3: Run surface-specific tests and critics**

WR2 must prove multiple hero slides survive the typed contract and its independent constitutional critic sees rendered output. WR3 must prove typed route, identity/audio/manifest/critic paths and exact credit math. Blog/SEO must distinguish generated, staged, approved, publishing, deployed and indexed-verified states.

**Step 4: Complete observation windows**

P09 requires at least its frozen 14-day window. A branch may integrate earlier with flags off, but P13 cannot claim full return-path evidence until the window completes.

---

### Task 10: Implement P13 outcome telemetry and migration 276

**Entry:** P04 and P09–P12 PASS with exact IDs/receipts actually propagated.

**Step 1: Implement namespaced adapters**

Write into P04's one canonical `OutcomeEvent` repository. Do not create a parallel outcome store. Preserve late-arrival/correction lineage and bind exact `MetricProfile`/`MetricResult` hashes.

**Step 2: Test idempotency and reconciliation**

Cover duplicate events, delayed indexing, corrected analytics, withdrawn claims, failed execution, missing platform metrics and privacy-safe aggregation.

**Step 3: Integrate 276**

I1 confirms the complete 270–276 train applies/rolls back in an isolated database, then integrates 276.

**Step 4: Observe two reporting windows**

No fixture-only telemetry unlocks P14.

---

### Task 11: Run P14 as the independent cross-system gate

**Entry:** P05–P13, P17 and P18 reviewed; P13 measurements runnable and reconciled.

**Step 1: Freeze the evaluation revision**

Bind datasets, splits, thresholds, denominators, exclusions, subgroup slices, confidence treatment, costs, latency/privacy guardrails, and operating windows before results.

**Step 2: Run deterministic and adversarial suites**

Evaluate ingestion, evidence, entity/retrieval, action authority, publication truth, WR2, WR3, outcomes, privacy, replay and rollback. Run on actual integrated code and receipts.

**Step 3: Use an independent empirical judge**

Follow the current Pro fleet topology. Gear 2/refuter uses a different session and family from the main builder. Gear 3 is a separate Fable-first session regardless of builder family; only the topology-defined Opus/max degraded fallback is permitted when every Fable account is unavailable. The roster comes from Pro, not a stale Air copy.

**Step 4: Emit the gate verdict**

Only exact `PASS` or explicitly bounded `PASS_WITH_LIMITS` can open named adoption canaries. `insufficient_evidence` and fixture-only results do not.

---

### Task 12: Run adoption Cohort H in a rolling 4+2 schedule

Six packets are topologically parallel but the builder cap is four.

**First admitted set:** P15, P19, P20, P21.
**Rolling queued set:** P22, P23 enter as soon as any slot releases.
**Adjustment:** the Conductor may reorder by current business priority/capacity if all exact dependencies remain satisfied.

Shared-resource integration remains serial:

- Action Inbox schema/runtime registry;
- backend router mounts;
- Kita route/navigation registry;
- outcome adapter registry;
- evaluator profile registry;
- any newly approved migration reservation.

Domain builders own namespaced adapters, UI modules, fixtures and evaluators only. P19 keeps compliance risk explicit; P20 protects client PII; P21 uses PricingTool and sends no outreach; P22 uses retrieval and measures self-service friction; P23 creates team actions/templates but sends nothing.

Each packet completes its frozen two-cycle/window requirement and receives a separate reviewer. Outcome/action/PII leaks must be zero.

---

### Task 13: Execute Packet 16 as a serial retirement program

Follow [`RETIREMENT-REGISTER.md`](../../../research/operations/execution/research-os-v1.0.0/RETIREMENT-REGISTER.md).

**Inherited entry gate:** Packet 16 starts only after every Packet `P01–P15` and `P17–P23` is complete and G4 is valid. Candidate rows may add stricter prerequisites; they never weaken this global gate. Earlier read-only topology work is preparation evidence, not a Packet 16 nomination or state transition.

**Step 1: Inventory only**

Refresh every candidate, classify `RETAIN|CONSOLIDATE|DEPRECATE|ARCHIVE|UNKNOWN`, and add instrumentation designs. The inventory session must end with exactly one atomic, evidence-qualified nomination, acquisition of the exclusive `active_candidate_id` lease, and no disable. If no target qualifies, the session remains open/blocked and produces no effect; it does not close with zero nominations or manufacture a candidate.

**Step 2: Prove replacement and non-use**

Collect two complete windows or the stricter candidate window, live-use/unknown-consumer telemetry, field/hash/state parity, replay, failure injection, zero stranded/duplicate effects, archive and rollback drill.

**Step 3: Disable one target**

After independent review, G4-compatible outcomes and exact owner authority, verify that the nomination's global `active_candidate_id` lease is still exact and held, then change one reversible flag/selector. Record immutable attempt, operational receipt and outcome. Observe one full window. No other retirement proceeds while that lease is held.

**Step 4: Remove later and separately**

If the disabled window is clean, either close the candidate revision as `DisabledRetainedClosed`, or create a new removal intent and approval while retaining the same global candidate lease. Remove only code/config whose data/history is archived and whose rollback remains tested. Release the lease only at `ArchivedRetired`, `DisabledRetainedClosed`, or `ReenableReconciled`; partial/unknown effects must complete the rollback or restore/re-enable path first. Never delete historical evidence, claims, approvals, outcomes, provenance, protected graph data, or NotebookLM sources as part of generic cleanup.

After the inherited Packet 16 gate, the lowest-risk first nomination is the metadata-only R13a alias repair if its own windows are complete; it never touches the live job. The recommended first runtime disable is the narrowly scoped MATA WR2 dossier-writer R03 after its additional P05/P12/P18/P14 proof. Canonical NotebookLM consolidation follows in three serial steps. Publication-history retirement is four near-last effects: canonical read with dual write, fallback-off, legacy-writer-off, then physical archive. R12 NEXUS/Mini graph readers are terminally retained in this program; any future retirement proposal requires a new freeze and absolute-last placement.

---

### Task 14: Close the program with an empirical topology audit

**Step 1: Recompute topology**

Count active producers, consumers, queues, groups, dead letters, feeds, registries, cockpits, routes, jobs, failure paths and rollback controls. Compare with the preregistered baseline.

**Step 2: Reconcile all receipts**

Verify every packet's exact manifest, branch SHA, review SHA, integration receipt, migration state, flags, side effects, outcomes, unresolved gaps and next-authorized-step.

**Step 3: Run cross-system failure injection**

Exercise source outage, Redis/DB/retrieval unavailability, unknown message, duplicate delivery, stale approval, missing NotebookLM route, FlowKit disconnect, platform metric delay and replacement rollback without outward effects.

**Step 4: Final independent gate**

The final judge inspects current disk/runtime evidence, not summaries. Open gaps remain explicit. The program is not complete merely because every branch merged.

**Step 5: Produce the operator handoff**

Deliver:

- what is live, shadowed, owner-gated, retained, disabled-observing and retired;
- which surfaces now consume the daily research treasure;
- exact current controls and rollback paths;
- remaining observation windows and blockers;
- before/after complexity and outcome metrics;
- a zero-PII, zero-secret evidence index.

No final deployment, publication, message, scheduler activation, service control, secret rotation, production migration, paid render or destructive cleanup occurs without its own explicit authority.

---

## Session handoff template

Every builder and reviewer handoff must include:

```yaml
run_id: exact campaign run
packet_id: exact packet or split sub-packet
dispatch_manifest_ref: exact id and sha256
campaign_root_sha: exact immutable campaign root
dispatch_base_sha: exact monorepo control-plane checkpoint
source_repository: exact repository identity and path
source_base_sha: exact immutable source repository SHA
base_commit: compatibility alias equal to source_base_sha
branch: exact branch
head_commit: exact current SHA
owned_paths: exact list
files_changed: exact list
tests:
  - command: exact command
    exit_code: integer
    result: concise result
leases: exact held/released resources
integration_manifest_ref: null unless queued for one exact I1 operation
side_effects_observed: []
migration_state: not_created | created_not_applied | applied_test_only
flags_state: exact values
privacy_result: pass | fail
known_limits: exact list
reviewer_family: null until independent review
reviewed_commit_sha: null until independent review
verdict: null | pass | pass_with_limits | fail | insufficient_evidence
next_authorized_step: none unless separately dispatched
```

The Conductor verifies this against Git, disk, test output and runtime receipts. The handoff is a claim until independently reproduced.
