---
date: 2026-07-17
seat: A
reviewer: Fable 5
model: claude-fable-5
role: architecture-judge
invocation_result: success
model_proof: "modelUsage contained only claude-fable-5; contextWindow 1000000"
client_data: none
repository_access: read-only
---

All verification is complete. Here is my Seat A review.

---

# Verdict

**GO-WITH-CHANGES — confidence 82.**

The decision is proportionate: it rejects every large option (Kafka, microservices, repo split) and generalizes a pattern the repository has already proven (`drive` as an isolated same-image process). The reversibility story is genuinely good at the phase level. However, the fencing model — the single mechanism the whole dual-ownership promise rests on — has two concrete holes as specified: it does not bind the legacy claim paths that exist in the code today, and the rollback procedure as written fences out the very owner it reactivates. Both are fixable with amendments, not redesign.

# Blocking findings

**B1. Fencing does not bind the legacy claim path; dual ownership survives Phase 3 as specified.** (Spec §7.2, §13, G2 §15; repo `apps/backend-rag/backend/services/workflow/queue.py:72`.)
_Verified fact:_ the workflow queue — the designated first pilot — claims work via `FOR UPDATE SKIP LOCKED` with no lease-owner, lease-expiry, or generation column. The fencing generation exists only in the proposed new protocol. _Inference:_ §7.2 says a stale owner "fails its next claim or side-effect checkpoint," but a machine running pre-cutover code (a Fly rolling deploy that leaves an old machine up, or an operator restart onto a cached release — both scar classes the spec itself lists in §1.5) resumes the lifespan loop and claims jobs _without ever reading the ownership row_. The generation advance is invisible to code that predates it. With the new worker also active, one job executes twice — precisely the failure I1 and G2 promise to prevent. G2 as written ("start an old process with stale configuration") can pass green while exercising only the new runner. _Falsifiable correction:_ the migration sequence must deploy the fencing checkpoint into the **existing** claim paths (workflow queue, legal ingestion, notification scheduler, WA outbox) fleet-wide at least one release before any cutover; G2 must run its stale-owner probe against the pre-cutover release's actual code path, not the new runner.

**B2. Rollback as written fences out the reactivated old owner, producing a zero-owner outage.** (Spec §13, G12 §15.)
_Verified fact (spec text):_ cutover "atomically advance[s] the workload fencing generation"; rollback says only "reactivate the old owner" and never mentions the generation. _Inference:_ once B1 is fixed and the legacy path enforces fencing, the reactivated old owner holds a stale generation and fails every claim. Rollback then yields **no** working owner at exactly the moment rollback is invoked because the new owner is broken — the workload is fully down instead of degraded. _Falsifiable correction:_ define rollback as a cutover in the reverse direction — an atomic generation advance that assigns ownership back to the old owner — and extend G12 to assert that the old owner successfully claims and completes at least one job after rollback.

# Important findings

**F1. The G7 ratchet baseline is not reproducible.** (Spec §1.2, §5.2, G7; repo `apps/backend-rag/backend/app/routers/`.) _Verified:_ `^\s*(import|from) asyncpg` matches **67** router files; top-level `^import asyncpg` matches **57**. Neither pattern yields the spec's 61. A ratchet whose measurement command is unpinned either starts red or gets quietly rewritten until it passes — the spec's own risk "direct SQL ratchet is gamed" (§16). Commit the exact check command as the repository check, re-derive the baseline from its own output, and cite the command inside G7.

**F2. The table-ownership inventory has no gate.** (§5.3, §12 Phase 0.) Phase 0's exit criterion covers durable loops only; nothing falsifies whether every mutable table actually received an owner or whether the assignment is honored. This is the one piece of kernel work with real cost and no proof mechanism — the spec's risk #1 ("catalogs become documentation only") applies to it directly. Either attach a check (e.g., migration lint requiring an owning-context annotation, tested like Squawk) or defer the inventory to Phase 5. The five bounded contexts themselves are conceptual-only and cheap; they pass the proportionality test.

**F3. I1 needs one clarifying sentence on intra-owner concurrency.** _Verified:_ `main_api.py:34-37, 162-167` already spawns `WA_OUTBOX_WORKERS` (default 2) concurrent scheduler loops inside one process, coordinated by a per-thread advisory lock. I1's "exactly one active runtime owner" is coherent only if "owner" means the workload grant, with internal parallelism governed by the catalog's `concurrency` field. Without that sentence, G2's "zero dual-owner intervals" telemetry can false-positive on a legitimate multi-loop owner.

**F4. Phase 2 has no absolute budget for the worker itself.** G9 bounds API/RAG regression at 10% and reports worker resources "separately," and §16 mentions a "measured import budget" with no number. On a memory-constrained Fly app (3GB api / 2GB rag after two emergency upgrades recorded in `fly.toml`), "cheap enough" needs a figure: set explicit worker memory and DB-connection ceilings as part of the Phase 2 exit.

# What survives review

- **Verified ground is honest.** I independently confirmed: the three `fly.toml` process groups with the documented single-worker scar; the outbox's single global `consumed_at`/`consumer_id` with stale-skip acknowledgement (`services/events/outbox.py:261-264, 391`); zero occurrences of `XAUTOCLAIM`/`XCLAIM` under `infra/eventbus/`; 157 router files; the workflow queue's SKIP LOCKED claim. Section 1 states its lexical counts are indicators, not audits — correct framing (though see F1 for the one number that must be exact).
- **The decision is smaller than the problem, in the right way.** The worker plane generalizes the proven `drive` pattern with the same image and release; the extraction gate (§14) converts "microservices someday" into a measurable, deferrable decision; §8.4 blocks broker escalation by anticipation.
- **I3 (commands ≠ events) targets a real, verified defect** — the global-ack outbox genuinely cannot support durable fan-out, and the spec retains it only for declared single-consumer channels rather than forcing a migration.
- **Reversibility is structurally sound**: shadow/off/active per workload, additive-only schema during the rollback window, per-workload (never global) cutover, and the only true one-way door — deleting lifespan wiring in Phase 4 — is explicitly held behind the rollback window's close.
- **G1's mutation test attacks the documented 404 scar class correctly**: today registration is explicit `include_router` calls, parity-_checked_ by tests but not generated; deriving mounting and proxy selection from one catalog is the right minimal fix, and keeping the existing public functions preserves rollback.

# Required amendments

1. **§12 Phase 3 + §7.2:** add an explicit pre-cutover step — deploy the fencing/kill-switch checkpoint into each legacy claim path one release before its cutover; rewrite G2 to probe the pre-cutover code path (B1).
2. **§13:** define rollback as a reverse cutover with an atomic generation re-advance assigned to the old owner; extend G12 to assert a successful post-rollback claim by the old owner (B2).
3. **G7:** pin the exact measurement command in the repository check and re-baseline from its output (measured 67 by `^\s*(import|from) asyncpg`) (F1).
4. **§5.3/§12 Phase 0:** attach a falsifiable check to table ownership or defer the inventory to Phase 5 (F2).
5. **I1:** state that the owner is the workload grant and internal concurrency is governed by the catalog `concurrency` field (F3).
6. **§12 Phase 2 exit:** add absolute worker memory and DB-connection ceilings (F4).

# Falsification test

In staging, seed the workflow queue with N jobs carrying side-effect ledgers. Keep one machine running the **pre-cutover release** with its lifespan loop enabled. Execute the cutover (generation advance, worker `active`), let both processes run a full cycle, then execute the documented rollback. The design survives only if (a) zero jobs record two side-effect executions while the stale machine is alive, and (b) after rollback the old owner claims and completes a job within the workload SLO. As currently specified, this test fails at (a) — the stale release never consults the fencing row — and, once fencing is added to the legacy path, fails at (b) — the reactivated owner holds a stale generation. Passing both legs proves the two blocking findings are closed.
