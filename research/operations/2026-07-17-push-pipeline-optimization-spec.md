# SPEC v2 — Push-pipeline optimization without safety reduction (Nuzantara monorepo)

Date: 2026-07-17 · Author: orchestrator session (Fable) · Status: **PANEL-REVIEWED**
Panel (adversarial, independent): **GPT-5.6 Sol (ultra)** · **GLM 5.2** · **Gemini 3.1 Pro** — raw verdicts in the Appendix (see below), synthesized below by the orchestrator (final gate).
v1 → v2 changes: P1 inverted to allowlist; P3 redesigned per Sol; P4 DROPPED; P6 hardened; P2 gated behind a step-equivalence canary protocol; sequencing revised; 3 new items adopted from panel "MISSING" lists.

## 0. Problem (measured 2026-07-17, unchanged from v1)

- Local pre-push (`.husky/pre-push` state 4) runs the full backend suite — 17,384 tests, 11–32 min — on every push regardless of diff. A log-rotation PR paid it 4× today.
- ~45 required CI checks per PR (~18 min backend job) — the merge-time safety net; NOT a target of this spec.
- Derived-docs treadmill: committed generated artifacts (docs_sync outputs, docs-guardian inventory) + fast-moving main (merge every ~15–20 min) → rebase loops; the inventory gate additionally rots on wall-clock (90-day thresholds), 3 innocent-PR victims documented.
- Push serialization via `pgrep` quiet-window polling.
- Net: 3 small infra PRs ≈ 4–5h wall clock, >90% gate overhead.

## 1. Invariants (unchanged, plus one correction)

I1. CI required checks never weakened/removed/path-filtered/conditional. All optimizations target local gates and queue mechanics.
I2. Fail-closed on ERRORS everywhere (any classifier/lock/refresh failure → full current behavior). **Panel correction (Sol, verified against `.husky/pre-push`): fail-closed does NOT mitigate incomplete-list under-match (silent skip, W82), and the CURRENT hook's states 1–3 already convert infra absence into silent SKIP — pre-existing contiguous debt, tracked separately.** Structural mitigation for lists = allowlist inversion (P1): unknown → full.
I3. Every skip is loud (file list + allowlist version + reason).
I4. New guards ship with guilt+innocence tests, CI-armed (W81).
I5. Merge remains PR-only with required checks.
I6. No time-keyed caches; content/SHA-keyed state only. (P4's tree-hash cache was killed under this + hermeticity — see P4.)

## 2. Proposals — post-panel status

### P1 — Path-aware pre-push · **APPROVED WITH CHANGES (3/3) — IN FLIGHT (lane 5, revised mid-build)**
Final design (revisions bold):
- **ALLOWLIST of harmless paths** (docs/**, research/**, root *.md, .claude/** non-hook, memory/**, non-backend plist/wrappers) — skip backend suite ONLY if every changed file matches; **any unknown path → full suite** (incomplete list ⇒ over-testing, never under-testing — inverts the failure mode into the safe direction).
- **`git fetch origin main` before classification** (stale local ref = family-#9 proxy) ; classify the union of ALL stdin refs incl. force-push, new/deleted refs, **renames and deletions**, submodules.
- Explicitly NEVER allowlisted (panel's likely-omissions): packages/** and shared packages, root scripts/**, conftest.py/pytest plugins at any level, test fixtures/data (JSON/YAML/CSV), alembic/migrations, Dockerfile/compose, .env templates, pyproject/setup.cfg/pytest.ini/tox.ini anywhere, evaluator corpora, reusable Actions, the hook + classifier themselves.
- Kill-switches `PREPUSH_FULL=1` / `PREPUSH_PATHAWARE=0`; loud skip log (files + allowlist version); guilt+innocence corpus; guardrail-class merge (no auto-merge, session merges post-red-team).
- Known residual (GLM): cross-branch classifier staleness window until other checkouts pull — CI backstop covers; noted in hook header.

### P2 — GitHub merge queue · **APPROVED WITH CHANGES (3/3) — LAST IN SEQUENCE, CANARY-GATED**
The one real merge-time safety hole found by all three reviewers independently: **a job/step conditioned on `pull_request` silently skips on `merge_group` yet reports SUCCESS → weaker green at merge** (family #2); conversely path-filtered workflows stay PENDING and wedge the queue.
Preconditions before flipping branch protection:
1. **Manifest mapping all ~45 required CONTEXTS (not 21 workflows) → their `merge_group` execution**, auditing PR-only `if:` conditions, refs, checkout logic, caches, concurrency keys, external checks (Vercel/Socket), matrix-job context names.
2. **Step-level equivalence canary** (not "check fired"): two cumulative canary PRs + one injected failure + queue rebuild + bot churn, diffing the executed step graph PR-run vs merge-group-run.
3. **Ejection watcher**: bots must detect queue ejection (webhook/poll) and re-queue or alert — silent starvation otherwise (Gemini).
4. Start with queue concurrency 1, no jumping; accept that speculative bisection can cost MORE CI than today on failures (GLM) — measure before/after.

### P3 — Deterministic derived-docs · **REDESIGNED per Sol (his REJECT of as_of pinning is upheld by the final gate)**
v1's `as_of` pin loses to a concrete failure: refresh cron dies Friday → Thursday's `as_of` stays valid → gate certifies freshness indefinitely (W81+W82: frozen proxy, exactly the disease being cured). GLM's too-old guard patches it; Sol's redesign removes the class:
- The committed artifact stores **deterministic per-doc facts**: `last_touched_date`, `orphan_eligible_on` (pure functions of tree history — no "today" anywhere in the merge gate). `inventory-check` verifies THOSE facts against the tree: deterministic per-tree, PRs can never rot by aging.
- **Date-crossing detection moves to the scheduled refresh organ** (lane 4's workflow): it computes which docs crossed eligibility, raises the idempotent flip PR, and carries its own **liveness guard** (heartbeat + overdue alert if last successful run > 2× interval — GLM's guard, applied to the scheduler where it belongs, not to the merge gate).
- Refresh PR logs "advanced N flips, eligibility recomputed".

### P4 — Green-stamp tree-hash cache · **DROPPED (Gemini REJECT + Sol REJECT; GLM conditional)**
Kill arguments upheld: local env is non-hermetic (untracked files, .env drift, site-packages, parallel agents), and one flaky green becomes a durable local oracle that suppresses all future independent detection. Salvaged fragment (Sol): **exact-SHA single-flight coalescing** — if two concurrent pushes carry the identical outgoing SHA, dedupe to one suite run; no persistence, no green authority stored.

### P5 — Impacted-test selection · **STAYS REJECTED (3/3 concur)** — import graphs lie (dynamic imports, fixtures, data files); may serve as fast-FIRST feedback someday, never as authoritative completion.

### P6 — Push lock · **APPROVED WITH CHANGES (3/3) — PROMOTED to first follow-up**
- Portable mutex/ticket queue (macOS `flock` neither guaranteed present nor FIFO — Sol); explicit FIFO tickets.
- Lock taken AFTER classification (skip verdicts don't queue), held synchronously across the whole suite incl. pytest children (no backgrounding while held — GLM), scope includes any shared-test-resource mutation (and any future cache writes).
- **Bounded wait; on timeout the push FAILS loudly — never bypasses** (3/3). No force-acquire.

### P7 — Lint-only pre-push · **STAYS REJECTED (3/3 concur)** — unattended agents need the earliest semantic signal precisely where P1 keeps it.

## 3. Adopted from panel "MISSING" lists (new work items)

M1. **Suite sharding/parallelization (pytest-xdist) with isolated per-worker DB/resources** (Gemini + Sol): attacks the 30-min constant itself; if the local suite drops to ~5 min, every remaining full run cheapens. Investigation lane: worker-DB isolation vs the per-push clone design of the current hook.
M2. **W86 × squash × merge-queue interaction analysis** (GLM): `check-docs-sync` re-runs on the queue's merge commit; the same-commit regen rule must be re-derived for queue semantics BEFORE P2 flips. Folded into P2 preconditions.
M3. **Exact-SHA discipline** (Sol): the local gate should test the outgoing SHA (detached/clean worktree), not the dirty working tree — folded into P1 implementation notes.
Deferred (noted, not scheduled): remote pre-push dispatch to a runner (Gemini); bot gating profiles (WIP pushes lighter, `ready_for_review` full) — revisit after M1 lands.

## 4. Rollout (revised: Sol's ordering, GLM-consistent)

1. **P1 hardened** (in flight — lane 5, allowlist revision sent mid-build).
2. **P6** ticket-queue lock (small, pure-local, immediate flake relief).
3. **P3′** deterministic facts + scheduler liveness (pairs with lane-4 organ already building).
4. **M1** sharding investigation (potentially the biggest constant-factor win).
5. **P2** merge queue — only after its manifest + step-equivalence canary + ejection watcher (M2 folded in).
P4 dropped. P5/P7 remain rejected.

Measurement per PR (unchanged): pushes count, minutes in local gates, minutes in CI, rebase count. Baseline 2026-07-17: 3 infra PRs ≈ 4–5h wall. Target: ≤ 40 min for the same class with identical merge-time CI coverage.

## 5. Panel meta-record

- Convergent (high confidence): P2 silent-green step-skip hole (3/3 independently); P1 allowlist-class hardening (3/3); P6 timeout-fails-not-skips (3/3); P4 unsafety (2 reject + 1 heavy conditions); P5/P7 rejections (3/3).
- Divergent, arbitrated by final gate: P3 (Gemini approve / GLM guard / Sol reject-redesign → Sol's design adopted); sequencing (Gemini P2-first vs GLM/Sol local-first → local-first adopted; rationale: P2 without P3′ keeps the docs treadmill alive INSIDE the queue, and P2 carries the only merge-time risk class found).
- Reviewer depth note: Sol read the live hook and falsified one spec premise (I2 wording) — recorded in I2 above.

## Appendix — raw panel verdicts (verbatim)

### GPT-5.6 Sol (ultra)

### Verdicts

- **P1 — APPROVE-WITH-CHANGES.** Replace the backend-path denylist with an explicit harmless-path allowlist; unknown paths force full testing. Classify the union of every stdin ref update, including force-pushes, new/deleted refs, renames, submodules, and root files. Test the exact outgoing SHA in a detached clean worktree. Likely omissions: `packages/cell-core/**`, root `scripts/**`, shared packages, evaluator fixtures, frontend files imported by backend tests, Docker/env/schema files, and reusable Actions.

- **P2 — APPROVE-WITH-CHANGES.** Require a manifest mapping all ~45 required contexts—not merely 21 workflows—to their `merge_group` execution. Audit PR-only conditions, refs, checkout logic, caches, external checks, and concurrency keys. A conditionally skipped job can report Success, creating a silent-green synthetic commit; path-filtered workflows instead remain Pending. [GitHub documents both behaviours](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks). Canary two cumulative PRs, injected failure, queue rebuild, and bot churn before enabling protection.

- **P3 — REJECT.** Concrete failure: cron credentials expire Friday; Thursday’s `as_of` remains valid and CI stays green indefinitely. That is proxy-state drift with bounded staleness only when automation works. Store deterministic facts such as `last_touched_date` and `orphan_eligible_on`; CI verifies them without “today.” A separately monitored scheduler detects crossed dates and raises an idempotent PR plus overdue alert.

- **P4 — REJECT.** One flaky green becomes a durable local oracle, eliminating subsequent independent detection opportunities. The proposed key also cannot reliably capture dirty files, test-runner code, Python/dependency state, services, DB fixtures, environment, or external resources. At most coalesce simultaneous runs of the same exact immutable SHA; do not persist green authority.

- **P5 — APPROVE** keeping it rejected. Impacted tests may provide fast-first feedback, never authoritative completion.

- **P6 — APPROVE-WITH-CHANGES.** `flock` is neither portable to this macOS host nor FIFO-guaranteed. Use a portable mutex or explicit ticket queue; timeout must fail the push, not bypass it. Lock after classification, test an immutable SHA, and include every process mutating shared test resources.

- **P7 — APPROVE** keeping it rejected. It removes semantic and nondeterministic local detection precisely where unattended agents need it.

### Q1–Q6

- **Q1:** PR CI plus `merge_group` CI means “CI once” is false. Head failure rebuilds descendants; queue jumping, cancellation keys, and bot re-enqueueing can cause starvation. Start build concurrency at one and prohibit jumping. [GitHub queue semantics](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
- **Q2:** `as_of` is another proxy. Absolute eligibility dates plus an independently monitored freshness process are safer.
- **Q3:** Persistent cache: no. Exact-SHA single-flight deduplication: acceptable.
- **Q4:** Shared packages, root scripts/config, test data/snapshots, migrations, Docker context, env templates, generated schemas, reusable Actions, submodules, evaluator corpora.
- **Q5:** Harden P1 → P6 → redesign P3 → fully canary P2. Omit P4.
- **Q6:** Yes. `merge_group` jobs skipped by PR-only conditions can satisfy required contexts without executing tests; P3 can certify stale inventory.

### Top three risks

1. Required context present, actual merge-group test absent.
2. Local classifier tests a different tree than the pushed SHA.
3. Freshness automation dies while deterministic CI remains green.

**Missing:** exact-SHA sandboxing throughout; safe full-suite sharding with isolated DB/resources; algorithmic optimization of `docs_audit` rather than generated-state caching. Also audit I2 independently: the inspected [current hook](/Users/balizero/nuzantara/.husky/pre-push:64) converts some infrastructure failures into `SKIP`, so “fallback to current behavior” is not fail-closed.


tokens used
139.525
[Air-M5]

### Verdicts

- **P1 — APPROVE-WITH-CHANGES.** Replace the backend-path denylist with an explicit harmless-path allowlist; unknown paths force full testing. Classify the union of every stdin ref update, including force-pushes, new/deleted refs, renames, submodules, and root files. Test the exact outgoing SHA in a detached clean worktree. Likely omissions: `packages/cell-core/**`, root `scripts/**`, shared packages, evaluator fixtures, frontend files imported by backend tests, Docker/env/schema files, and reusable Actions.

- **P2 — APPROVE-WITH-CHANGES.** Require a manifest mapping all ~45 required contexts—not merely 21 workflows—to their `merge_group` execution. Audit PR-only conditions, refs, checkout logic, caches, external checks, and concurrency keys. A conditionally skipped job can report Success, creating a silent-green synthetic commit; path-filtered workflows instead remain Pending. [GitHub documents both behaviours](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks). Canary two cumulative PRs, injected failure, queue rebuild, and bot churn before enabling protection.

- **P3 — REJECT.** Concrete failure: cron credentials expire Friday; Thursday’s `as_of` remains valid and CI stays green indefinitely. That is proxy-state drift with bounded staleness only when automation works. Store deterministic facts such as `last_touched_date` and `orphan_eligible_on`; CI verifies them without “today.” A separately monitored scheduler detects crossed dates and raises an idempotent PR plus overdue alert.

- **P4 — REJECT.** One flaky green becomes a durable local oracle, eliminating subsequent independent detection opportunities. The proposed key also cannot reliably capture dirty files, test-runner code, Python/dependency state, services, DB fixtures, environment, or external resources. At most coalesce simultaneous runs of the same exact immutable SHA; do not persist green authority.

- **P5 — APPROVE** keeping it rejected. Impacted tests may provide fast-first feedback, never authoritative completion.

- **P6 — APPROVE-WITH-CHANGES.** `flock` is neither portable to this macOS host nor FIFO-guaranteed. Use a portable mutex or explicit ticket queue; timeout must fail the push, not bypass it. Lock after classification, test an immutable SHA, and include every process mutating shared test resources.

- **P7 — APPROVE** keeping it rejected. It removes semantic and nondeterministic local detection precisely where unattended agents need it.

### Q1–Q6

- **Q1:** PR CI plus `merge_group` CI means “CI once” is false. Head failure rebuilds descendants; queue jumping, cancellation keys, and bot re-enqueueing can cause starvation. Start build concurrency at one and prohibit jumping. [GitHub queue semantics](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue).
- **Q2:** `as_of` is another proxy. Absolute eligibility dates plus an independently monitored freshness process are safer.
- **Q3:** Persistent cache: no. Exact-SHA single-flight deduplication: acceptable.
- **Q4:** Shared packages, root scripts/config, test data/snapshots, migrations, Docker context, env templates, generated schemas, reusable Actions, submodules, evaluator corpora.
- **Q5:** Harden P1 → P6 → redesign P3 → fully canary P2. Omit P4.
- **Q6:** Yes. `merge_group` jobs skipped by PR-only conditions can satisfy required contexts without executing tests; P3 can certify stale inventory.

### Top three risks

1. Required context present, actual merge-group test absent.
2. Local classifier tests a different tree than the pushed SHA.
3. Freshness automation dies while deterministic CI remains green.

**Missing:** exact-SHA sandboxing throughout; safe full-suite sharding with isolated DB/resources; algorithmic optimization of `docs_audit` rather than generated-state caching. Also audit I2 independently: the inspected [current hook](/Users/balizero/nuzantara/.husky/pre-push:64) converts some infrastructure failures into `SKIP`, so “fallback to current behavior” is not fail-closed.



### GLM 5.2

**Verdicts**

**P1 — APPROVE-WITH-CHANGES.** The claim "fail-closed mitigates under-match" is false: fail-closed fires on *exceptions*, not on an *incomplete path list*. An under-match skips silently with no error — exactly W82/W99. Real mitigation is only I1 (CI backstop) + corpus, not fail-closed; stop claiming otherwise. Second hole: merge-base vs `origin/main` uses the **local ref**, which may be stale (concurrent agents, infrequent fetch) → wrong diff → under-count → wrong skip (family #9 proxy-state). Require `git fetch` immediately before classification, or pin to a fetched SHA verified current.

**P2 — APPROVE-WITH-CHANGES.** Staged rollout is sound, but "fires on merge_group" ≠ "runs the SAME check." A workflow with `if: github.event_name == 'pull_request'` gating a step will SKIP that step on `merge_group` yet report green → **silent-green weaker check at merge time** (family #2). Canary must diff the *step graph* between triggers, not just confirm the check name appears. Add cost model: GitHub does speculative batch bisection; under 21 required checks a failing PR can trigger re-runs that **exceed** today's CI cost.

**P3 — APPROVE-WITH-CHANGES.** Creates a new family-#9 proxy-state scar: `as_of` can **freeze** if the refresh cron silently stops (W81), making the freshness gate report fresh indefinitely (W82 under-match by another name). Spec fails-closed only on missing/future/unparseable — NOT on *too-old*. Add: gate fails if `as_of < now − 2×cron-interval*. Cron itself needs a liveness guard (green≠ran).

**P4 — APPROVE-WITH-CHANGES.** Poisoning acceptable under I2/I3 *only if* the store records **clean greens only** (no retried/flaky tests) and the cache is **evicted when CI later fails on a cached hash** (spec omits this feedback loop — without it an agent loops: same hash, local skip, CI flake-fails, repeat). Per-machine, never shared.

**P5 — APPROVE (rejection correct).** Import graphs lie on dynamic imports/fixtures/data — under-match trap.

**P6 — APPROVE-WITH-CHANGES.** Lock MUST wrap the suite **synchronously** — no backgrounding; the lock fd must be inherited by pytest children or held until all exit. If the hook exits while pytest lives, lock releases → concurrent suites → the race P6 meant to kill. Timeout → **fail the push**, not skip (never force-acquire).

**P7 — APPROVE (rejection correct).** P1+P4 narrow full runs to genuinely-changed backend code — exactly where earliest signal matters for unattended agents. Dropping loses signal where it pays.

**Q1.** Partial-batch speculative re-runs (cost, see P2); queue starvation if one PR fails repeatedly (needs max-retries + auto-dequeue + alert); required-check identity is name+path — a matrix job under `merge_group` may not match branch-protection's required name → stuck at queue level.

**Q2.** Yes, proxy-state scar (family #9). Fix: as_above guard + derive `as_of` from the artifact's own commit date (can't lag without a commit, and the commit IS the cron PR). Still needs the too-old guard.

**Q3.** Acceptable if clean-greens-only + eviction-on-CI-failure (above). Without eviction, agent-loop stall.

**Q4.** conftest.py/pytest plugins *anywhere* (pytest walks up); shared/ test fixtures + data files (JSON/YAML/CSV); alembic/ + env.py; Dockerfile/compose test context; pyproject/setup.cfg/pytest.ini/tox.ini at any level; .env.example templates; **renames/deletions** of backend files, not just modifications; root lockfiles if tests consume built JS assets.

**Q5.** Keep P3 before P2: P2 alone doesn't fix the docs treadmill (queue re-runs `check-docs-sync` on the merge commit, still stale). Minor: I'd promote P6 to first (smallest, pure local mechanics, immediate flake relief, zero interaction).

**Q6.** Yes — **P2 merge_group step-equivalence** (see P2): a conditionally-skipped step yields a weaker green check at merge time. That is a silent merge-time safety reduction. The canary must verify step-level equivalence, not just "check fires."

**Top-3 risks**
1. P2 silent-green via `merge_group` step-skips — weaker check at merge than at PR (family #2, the one real merge-time regression).
2. P3 `as_of` freezes on cron failure → freshness gate reports fresh indefinitely (W81+W82).
3. P1 conflates fail-closed (errors) with under-match mitigation (incomplete list skips silently) + stale local `origin/main` merge-base.

**MISSING**
- **P4 cache write concurrency**: concurrent agents finishing suites write the store simultaneously — need temp+rename atomic writes, or P6's lock must cover cache writes too; torn write corrupts the store.
- **P4↔CI eviction loop** (above) — unmentioned.
- **P2 cost model for speculative bisection** — unmentioned, could exceed today.
- **W86 + squash + merge-queue interaction**: `check-docs-sync` required in the queue re-runs on the merge commit; if `docs_sync.py` regen must be in the *same commit* as the feature, the squash/merge-commit semantics need explicit analysis — spec never addresses it.
- **Cross-branch classifier staleness**: agent A lands a classifier change; agent B on another branch runs the OLD classifier until pull — transient under-match window (CI backstop covers it, but should be noted).

### Gemini 3.1 Pro

**P1 — Path-aware pre-push**
**APPROVE-WITH-CHANGES**: Add all root-level build/config files to the backend-relevant list (`pyproject.toml`, `tox.ini`, `Makefile`, `.env.*`, `docker-compose.yml`). Skipping the suite when a root config changes is a critical under-match risk.

**P2 — GitHub merge queue**
**APPROVE-WITH-CHANGES**: Add an external queue-monitor alert. When a PR fails in `merge_group`, GitHub ejects it. Bots relying on `gh pr merge --auto` do not automatically re-queue. This creates silent starvation where PRs sit indefinitely. 

**P3 — Deterministic derived-docs**
**APPROVE**: Sound decoupling of wall-clock from CI validation. Tying `as_of` directly to the committed artifact successfully binds the state to the git tree, eliminating the proxy-state scar.

**P4 — Green-stamp tree-hash cache**
**REJECT**: Disqualifying poisoning risk. A git tree-hash only captures committed files. Untracked files, local `.env` drift, global python packages, and parallel agent mutations on the same machine make local state un-hermetic. Recording a flaky pass here creates a persistent false-negative scar.

**P5 — Impacted-test selection**
**APPROVE** (Rejection). Dependency graphs are too brittle in Python for safety-critical gating.

**P6 — Push-queue lock instead of pgrep**
**APPROVE-WITH-CHANGES**: Add a strict maximum wait timeout (e.g., `timeout 60m flock ...`). Unbounded FIFO waiting means an agent pushing behind 3 other 30-minute suites hangs for 1.5 hours, likely triggering the agent's own internal session timeouts and causing cascade failures.

**P7 — Radical alternative**
**APPROVE** (Rejection). Agents need fast local failure to iterate autonomously; shifting all feedback to CI breaks the unattended agent loop.

***

**Open Questions**

**Q1. P2 missing failure modes?**
Queue ejection. If `merge_group` CI flakes, the PR drops out of the queue. If bots aren't programmed to detect the `MERGE_QUEUE_EJECTED` webhook and re-arm auto-merge, the PR stalls silently forever.

**Q2. P3 proxy-state scar?**
No scar. Pinning `as_of` in the artifact makes the artifact itself the SSOT. The gate becomes a pure function of the file content, which is the correct invariant.

**Q3. P4 cache poisoning?**
Yes, disqualifying. Unless you use a hermetic build system (Bazel) that controls all inputs (env vars, untracked files, system dependencies), tree-hash caching locally is dangerous and will yield false greens.

**Q4. P1 classifier misses?**
Root configs (`pyproject.toml`, `setup.py`), infrastructure definitions (Dockerfiles, compose files), shared utility scripts, global environment variables (`.env.example`), and database seed/fixture data residing outside the specified `apps/` paths.

**Q5. Re-sequencing?**
Move P2 (Merge Queue) to step 1. It structurally destroys the rebase treadmill, immediately resolving the highest-pain issue (O(N) CI runs per PR). Local optimizations (P1) matter less once the treadmill stops.

**Q6. Silently reducing safety?**
Branch protection override risk. If P1 skips the local suite, and a bot merges the PR using an admin token that bypasses CI required checks (a common anti-pattern for agent automation), zero backend tests run. I1 assumes GitHub branch protection is perfectly airtight against all actors.

***

**Top-3 Overall Risks**
1. **Queue Ejection Starvation (P2)**: Autonomous agents push and forget. If a queue batch fails due to a flake, the PR is silently dropped from the queue and orphaned.
2. **Under-matching Root Configs (P1)**: Missing changes to dependencies or build scripts will result in broken code bypassing local checks and wasting CI time.
3. **Unbounded Local Queuing (P6)**: A FIFO lock without TTLs will cause agent sessions to time out while waiting for previous 30-minute suites to finish, paralyzing concurrency.

**MISSING (Omissions from the spec)**
- **Test parallelization (`pytest-xdist`)**: The spec accepts a 30-minute test suite as a law of physics. Sharding or parallelizing the local suite could reduce this to 5 minutes, mitigating the need for complex caching or locking.
- **Remote dispatch for pre-push**: Instead of blocking the agent's local process for 30 minutes, the pre-push hook should immediately zip the diff and dispatch it to an ephemeral, fast cloud runner, freeing the agent to do other work while polling for the result.
- **Bot-specific gating profiles**: The spec treats human and agent pushes identically. Agents can often batch multiple commits and only run the heavy suite on the final `ready_for_review` state, skipping pre-push entirely for intermediate WIP commits.
