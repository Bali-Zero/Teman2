---
panel: beyond-sota-xfamily
lane: 04-implementation-craft
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T18:33:34Z
finished: 2026-08-28T18:43:57Z
duration_s: 623
exit: 0
words: 5538
prompt_sha256_16: 8fc7f20c4259d888
prompt_chars: 17790
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 4/13 — Implementation craft (BUILD)
model: OpenAI GPT-5.6 sol, reasoning effort ultra (pinned lane)
sources: 12
repo_files_verified: 20
status: complete
---

## 0. TL;DR

Nuzantara is **AHEAD of SOTA in implementation doctrine and multi-agent worktree design, but BEHIND in making ownership, capacity, environment identity, and routing transactional and measurable**.
The largest gap is between “the rule exists” and “every builder necessarily passed through it”: leases remain manual/fail-open, routing policies conflict, and worktree admission is not atomic across machines.
Top move 1: combine fleet placement, resource reservation, worktree creation, heartbeat, and reaping into one transactional BUILD admission.
Top move 2: replace lane-count parallelism with a bottleneck-aware WIP governor based on machine/test-suite capacity and useful-work yield.
Top move 3: require a deterministic build receipt carrying base SHA, claim, environment, route, touched resources, test progression, and final commit.
Do not scale the H24 army further until business commits per agent-hour and accepted changes per million output tokens improve.
The requested PR-size distribution could not be retrieved because this snapshot’s Git origin is local and GitHub API access failed; no value is fabricated.

## 1. How Nuzantara does it today

This assessment uses only the read-only repository snapshot. No `$MEM`, external memory directory, live HOME hook, secret, or other panel output was opened. The four named memory briefs were therefore unavailable; their repository-owned substitutes were the cicatrix corpus, `PENDING-ARMS.md`, `AMENDMENTS.md`, broker comments, and runbooks. No test suite was run. Per the lane instruction, this report is returned in the final response rather than written to disk, so the protocol’s output-file `ls`/`wc` probe is inapplicable.

| BUILD layer | Current practice | What is actually enforced |
|---|---|---|
| Workspace isolation | Every agent is supposed to enter a dedicated `.worktrees/<lane>-<task-id>` created by `scripts/agent_start.py`; branches use `agent/{host}/{lane}/{task_id}`. The main checkout is reserved for the operator and cicatrix work (`scripts/agent_start.py:1-30,517`; `CLAUDE.md:23-27`). | The broker validates identifiers, refuses detectable nesting, creates metadata, wires expected branch/task variables, and provisions Husky plus dependency symlinks. It also has RAM/load admission and conservative cleanup. However, failed `origin/main` fetch falls back to the potentially stale local base, several probes fail open, and the isolation hook is not the admission authority. |
| Fleet placement | `scripts/fleet_dispatch.py`, documented by `docs/runbooks/fleet-lane-dispatch.md`, places work from declared files and refuses known collisions, partial inventory, opaque agents, saturated machines, and dark peers. | Placement and worktree creation are separate operations. The runbook explicitly identifies a cross-machine TOCTOU window in which two dispatches can both pass before either declares ownership. |
| Hot-zone ownership | Redis leases use `SET NX EX`, heartbeat, and Lua-guarded release for migrations, workflows, launch wrappers, auth, billing, pricing, and other shared resources (`docs/runbooks/redis-lease-registry.md`). | Acquisition is manual rather than intrinsic to edit/build admission. A missing Redis client or unavailable Redis produces a warning and permits the commit. Incorrect `REDIS_HOST` configuration can create split registries. The inspected broker cleanup path did not establish the three-way modus promise of “no process, no lease, content on main.” |
| Implementer routing | Sonnet 5 is described as the BUILD workhorse; Codex GPT-5.6, Kimi, Antigravity/Gemini, GLM/Qwen and other flat-plan seats are task-shaped alternatives (`MODEL_ROSTER.md:7-10,34,45-59,89-97`; `.claude/skills/modus/SKILL.md:114+`). Codex must be sandboxed; headless commands close stdin. Antigravity receives a scoped task in a fresh worktree and cannot merge or deploy (`CLAUDE.md:159-166`). | Policy has conflicting precedence. `MODEL_ROSTER.md:226-244` calls Sonnet the sane default while `MODEL_ROSTER.md:249-258` says Alibaba TP1 and Gemini precede Anthropic for throughput. The telemetry shows behavior remains concentrated: `docs/factory/SEAT-MIX.md` records 148 Agent dispatches across 118 sessions—127 Sonnet (85.8%), 18 inherited, two Haiku and one Opus—plus 112 non-Anthropic calls, but only one identifiable Kimi coding use and 35 unmapped sessions. External calls are not equivalent to effective implementer assignments. |
| Coding method | Modus requires reuse-first for non-trivial work, tests written to fail and then pass, and a narrowly scoped implementation. Karpathy discipline emphasizes reasoning before editing, simplicity, surgical changes, and verifiable success (`.claude/skills/modus/SKILL.md`; `.claude/skills/karpathy-discipline/SKILL.md`; `.claude/skills/reuse-first/SKILL.md`). | These are strong instructions, not universal execution proofs. The repository has no inspected BUILD receipt proving that a failing test preceded production code or that reuse research occurred. The reuse skill’s case study is useful but anecdotal rather than a repeatable benchmark. |
| PR construction | The Agent PR Contract requires one concern, a target of roughly 400 net lines when practicable, a dedicated worktree, and a first claim commit (`CLAUDE.md:29-63`). | The branch expectation is checked, but neither semantic single-concern scope, the approximate size target, nor “claim was the first commit” was shown to be mechanically enforced by the inspected broker/hook surfaces. |
| Code-shaping gates | `.pre-commit-config.yaml` defines secret checks, Ruff, formatting, ESLint, print/console rejection, protected-file checks, import-chain checks, and a narrow mypy gate. `.husky/pre-commit:143-188,192-229,232-269,380-441` adds Redis conflict checks, migration invariants, anti-reward-hacking checks, fail-closed Ruff availability, branch identity, and import checks. | Agent worktrees depend on `.husky/_` being correctly provisioned. Comments in `scripts/agent_start.py` record that three probe pushes silently skipped the gate without it. Some frontend type failures are non-blocking, and Redis outage is explicitly fail-open. There are multiple overlapping gate definitions, increasing drift risk. |
| Hook backstop | `infra/claude-hooks/worktree_isolation.py` blocks many writes and Git mutations in main and allows worktree/external/read-only operations. | `infra/claude-hooks/README.md` says the tracked files are reference copies while runtime HOME copies are executable; it also records a historical Pro configuration with enforcement disabled. That is not proof of current live state. The reference hook permits paths structurally under `.worktrees` even when registration is unproven and contains classification/probe fail-open edges. |
| H24 grunt lanes | Nonempty `infra/army/chore-queue/`, `infra/army/jules-queue/`, and `infra/army/spark-queue/` directories provide a standing backlog. | Queue presence proves supplied work, not successful autonomous completion. The inspected telemetry lacks a closed-loop accepted-yield, repair-rate, or queue-age objective for these lanes. `.claude/agents/README.md` currently documents four project-tracked aggregation/verification roles rather than the broad grunt/conductor split suggested by the lane brief. |

### Snapshot measurements

- `git log --since=14.days --format=%s | wc -l` returned **859 commits**.
- A case-sensitive subject-prefix heuristic, `grep -c '^fix'`, returned **261/859 = 30.4%**. This is not a defect rate: it includes intentional fixes and excludes rework labeled differently.
- `git worktree list | wc -l` returned **1**, but this is the isolated snapshot’s Git registry, not evidence that the live fleet has only one worktree.
- The requested last-100 merged-PR size query could not run against the local snapshot origin; an explicit GitHub query then failed at the API boundary. Median and p90 size are therefore **unknown**, which itself means the 400-line contract cannot be shown empirically effective from this lane.

## 2. Scars & ledger evidence in this area

The scars show that implementation craft fails primarily at lifecycle boundaries, not at code generation.

| Evidence | What happened | BUILD implication |
|---|---|---|
| W59 | `.claude/rules/cicatrix-scars.md:1228` says no independent record was available. | Do not turn a label into evidence. Unknown incidents must remain unknown. |
| W62 | `.claude/rules/cicatrix-scars-archive.md:2596` records six abandoned fan-out worktrees and 34 TTL violations. | TTL alone is not ownership or liveness. Parallelism created unmanaged inventory. |
| W63 | `.claude/rules/cicatrix-scars-archive.md:2197` records a nested-worktree failure. | Structural admission must be canonical and fail closed; “current directory looks plausible” is insufficient. |
| W79 | The worktree-isolation backstop was introduced after main-checkout mutation risk; `infra/claude-hooks/worktree_isolation.py` carries subsequent scar-derived exceptions and classifiers. | The backstop is sophisticated, but runtime HOME drift and structural allowances mean it cannot substitute for transactional admission. |
| W80, original | `.claude/rules/cicatrix-scars.md:296` records cleanup reaping a clean but active worktree; the initial cure was associated with PR #1401. | “Git clean” is not “abandoned.” |
| W80, recurrence | `.claude/rules/cicatrix-scars.md:565` records a three-implementer campaign in which a live worktree, branch and registration disappeared before its first commit, leaving no reflog, stash or dangling commit. | The first cure was incomplete. Ownership must exist before the first editable byte, and reaping must consult that ownership. |
| W88 | `.claude/rules/cicatrix-scars.md:1104` concerns content-equivalence/cherry-pick cleanup. `.claude/skills/modus/PENDING-ARMS.md:263` records a later Jules pilot cure. | Content-on-main is stronger than merge-ancestry alone, but remains only one of the necessary cleanup predicates. |

`.claude/rules/cicatrix-superscar.md` classifies W62, W63 and W80 under family **#5 sibling-race**, while runtime/repository-copy drift belongs to **#1 HOME-fork** and an installed-but-ineffective guard belongs to **#2 exists ≠ armed**. These are the relevant risk families for BUILD improvements.

The ledgers show recurrent throughput mistakes:

- `.claude/skills/modus/AMENDMENTS.md` records a nine-lane BUILD fan-out where every lane launched the full pre-push suite against the same database, creating **7–18 concurrent suites** and repeated flakiness/livelock. Serialization arrived only after the third storm.
- A plain `git worktree add` produced a worktree without `.venv`; four pushes were misjudged because `git push | tee` masked the real return code.
- Five or more lanes silently idled, a final response was never delivered, and redispatch created two implementers on the same branch.
- A 14-lane spawn burst produced **13/14 fork failures**; sequential groups of two or three succeeded.
- Two “speed coding” sessions ran for 44 and 31 hours, generated 180 PRs and about 8.6 million output tokens, but yielded roughly ten business commits. Median lead time for PRs of at least 100 lines moved from 1.5 to 1.6 hours and p75 worsened from **4.3 to 6.0 hours**, despite test time improving from 23.9 to 12.9 minutes.
- `.claude/skills/modus/PENDING-ARMS.md:35` says the routing-gate repository canon existed while live copies on all three machines were stale; until refresh proof, alignment remained pending.
- `PENDING-ARMS.md:225` captures the headless Codex remedy—workspace-write sandbox, repository-check handling, and stdin from `/dev/null`—while noting that real network proof still remained.

The repeated pattern is clear: Nuzantara frequently invents the right local cure, but parallel admission, runtime propagation and outcome telemetry lag behind the doctrine.

## 3. World SOTA survey

| System/practice | Primary source | Best-in-class mechanism | Published effect | Transfer to Nuzantara |
|---|---|---|---|---|
| Google small change lists | [Google Engineering Practices](https://google.github.io/eng-practices/review/developer/small-cls.html) | One self-contained concern, tests in the same change, separate refactors, vertical/horizontal decomposition. Rough guidance calls 100 lines reasonable and 1,000 usually too large. | No controlled trial; Google reports faster, deeper review, fewer bugs/conflicts and simpler rollback. | High. The 400-line target is directionally sound but needs measured distribution and exceptions by change type. |
| Simple composable agents | [Anthropic, Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) | Prefer transparent workflows and small composable patterns; use routing, parallelization or orchestrator-workers only when the task warrants them; ground every loop in environment feedback and stopping conditions. | Experience across dozens of teams; no controlled effect size. | High, using sanctioned CLI paths only. It argues against multiplying orchestration layers without measured gain. |
| Claude Code operating practice | [Anthropic Claude Code best practices](https://code.claude.com/docs/en/best-practices) | Persistent repository instructions, deliberate context/session management, common workflow primitives and subtask separation. | No published causal metric. | High as harness guidance; not permission to use paid APIs. |
| Experienced-developer RCT | [METR productivity study](https://arxiv.org/abs/2507.09089) | Randomized real issues in mature repositories, using experienced maintainers rather than toy tasks. | 16 developers, 246 tasks; AI use made completion **19% slower** even though developers expected a speedup. | Critical. Optimize useful accepted work, not PR count, tokens, or model activity. |
| DORA AI-assisted development | [DORA 2025 report](https://dora.dev/research/2025/dora-report/) | Treat AI as an amplifier of platform quality, feedback speed, workflow clarity and product alignment rather than an isolated coding tool. | Survey of nearly 5,000 professionals; no universal speed multiplier. | Very high. Nuzantara’s environment and admission weaknesses will be amplified by more seats. |
| Agent-first harness engineering | [OpenAI, Harness engineering](https://openai.com/index/harness-engineering/) | One bootable application and ephemeral observability stack per worktree; repository-embedded skills; agents operate standard tools and can run for hours. | Reports six-hour unattended runs; no controlled causal estimate. | High. Local worktrees are already strong, but dependency/test state must become isolated and legible too. |
| Fresh machine baselines | [Devin golden snapshots](https://docs.devin.ai/product-guides/snapshots) | Every session starts from a fresh copy of a managed machine baseline; current blueprints propagate shared configuration. | No public performance number. | Medium-high. Reproduce locally with content-addressed capsules rather than cloud VMs or mutable shared symlinks. |
| Agent-computer interface engineering | [SWE-agent paper](https://arxiv.org/abs/2405.15793) | Purpose-built search, viewer, editor and test interface; tool ergonomics are treated as a major performance variable. | 12.5% SWE-bench and 87.7% HumanEvalFix pass@1 in the reported evaluation. | High. Nuzantara’s broker, absolute paths, closed stdin and return-code discipline are ACI work, not incidental scripting. |
| Sandboxed, model-agnostic agents | [OpenHands paper](https://arxiv.org/abs/2407.16741) | Safe execution environments, CLI/browser interaction, multi-agent coordination and benchmark integration in an open platform. | Evaluated across 15 task families; no single comparable aggregate. | Medium. Borrow lifecycle/sandbox contracts without adopting another heavy platform or violating local sovereignty. |
| Hermetic builds | [Bazel hermeticity](https://bazel.build/concepts/hermeticity) | Declared inputs/tools, source identity, sandboxed actions and content-based caching isolate builds from host variation. | Official docs emphasize reproducibility/cacheability; sandbox setup is generally a small overhead, not a productivity result. | High at the principle level. A wholesale Bazel migration is unjustified; dependency and test capsules are transferable. |
| Agent-written property tests | [Hypothesis `/hypothesis` command](https://hypothesis.works/articles/claude-code-plugin/) | Agent explores callers and invariants, writes generated tests, runs them, then distinguishes incorrect properties from real failures. | Found confirmed bugs in NumPy, pandas and other projects; a NumPy correction shipped in 2.3.4. | High for Python invariants and broker state machines, with local execution and no PII. |
| Deterministic semantic autofix | [Semgrep AST autofix](https://semgrep.dev/blog/2022/autofixing-code-with-semgrep/) | AST-aware transforms preserve syntax better than textual replacement and can be tested against expected fixed files. | Reported valid synthesis on 96.4% of Python and 100% of JavaScript test cases in its then-current corpus. | High for H24 grunt work using OSS deterministic rules; paid AI autofix is unnecessary. |

The most transferable lessons are:

1. **The harness is part of the implementation.** SWE-agent, OpenAI and Devin all make environment/interface design a first-class product. Nuzantara already understands this better than most repositories, but its isolation stops at the working tree while dependencies, databases, hooks and reservations remain partially shared or ambient.

2. **More agents are not automatically more throughput.** Anthropic conditions parallelization on genuine independence. METR shows even capable tools can slow experts, while DORA says AI amplifies the surrounding system. Nuzantara’s 7–18 concurrent suites, 13/14 fork failures and worse p75 lead time are a textbook local confirmation.

3. **Small changes need an outcome loop.** Google’s practice is conceptual, not merely a line count. Nuzantara has the correct “one concern” language but lacks distribution measurement and a machine-readable claim connecting task, change, test progression and final commit.

4. **Hermeticity is the missing complement to worktrees.** A worktree isolates source mutations; Bazel-style declared inputs isolate execution. Shared mutable `.venv`, `node_modules`, database state or runtime hooks can still make two isolated builders affect one another.

5. **Grunt automation should be semantic and falsifiable.** Hypothesis and Semgrep show productive autonomous chores: infer/test invariants or perform tested AST transforms. A generic “find TODOs and fix things” queue has much weaker safety and yield economics.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence and judgment |
|---|---|---|
| Per-task source isolation | **AHEAD** | The broker has namespaced branches, metadata, nested-worktree defenses, dependency/Husky provisioning, machine admission, conservative content-aware cleanup and scar-derived commentary (`scripts/agent_start.py`; `docs/runbooks/agent-worktree-broker.md`). This exceeds ordinary “one worktree per agent” guidance. |
| Atomic ownership | **BEHIND** | Fleet placement has a documented TOCTOU gap; Redis acquisition is manual and fail-open; cleanup was not shown to consume lease state. Leading isolated-agent platforms make environment creation one admission event. |
| Change decomposition | **AT in doctrine; BEHIND in proof** | “One concern” and roughly 400 lines track Google’s practice, but the last-100-PR distribution is unavailable and no inspected gate measures semantic scope or claim-first compliance. |
| TDD and reuse-first | **AT in guidance; BEHIND in evidence** | The skills are strong and specific. There is no universal receipt proving red→green order, reuse search, or provenance for each builder. Hypothesis demonstrates a more executable test-generation loop. |
| ACI/headless craft | **AHEAD** | Closed stdin, explicit sandbox, worktree-root discipline, branch assertions, return-code lessons, and tool-specific routing reflect mature ACI design. Silent-idle and masked-exit recurrences show the completion protocol remains incomplete. |
| Environment reproducibility | **BEHIND** | Broker symlinks repair missing dependencies but preserve dependence on mutable host state. The recorded 5/37 `node_modules` coverage before repair and missing-`.venv` incident are far from hermetic capsules or fresh blueprints. |
| Cross-family implementer breadth | **AHEAD in arsenal; BEHIND in control** | The roster and flat subscriptions create unusual optionality. Actual routing is Sonnet-heavy, 35/118 sessions are unmapped, and policy precedence conflicts. Breadth without outcome-calibrated selection is inventory, not routing. |
| Code-shaping local gates | **AT** | The pre-commit/Husky checks are broad and scar-aware. Runtime/reference drift, Redis fail-open behavior and overlapping configurations prevent an AHEAD rating. |
| Parallel BUILD economics | **BEHIND** | 180 PRs and 8.6M output tokens produced about ten business commits; p75 lead time worsened. Capacity was allocated by possible lanes rather than the downstream bottleneck. |
| H24 grunt system | **AHEAD in ambition; BEHIND in yield measurement** | Three fed queues and multiple coding families are rare for a solo-owner organism. Accepted-without-repair rate, cost per retained change, recurrence reduction and queue age were not established. |

## 5. Beyond-SOTA recommendations

The ranking applies `(impact × confidence) / relative cost`; scores are prioritization estimates, not performance claims.

| Rank | Recommendation | Impact | Confidence | Relative cost | Score |
|---:|---|---:|---:|---:|---:|
| 1 | Transactional BUILD admission | 5 | 0.95 | 1.5 | 3.17 |
| 2 | Bottleneck-aware WIP governor | 5 | 0.90 | 2 | 2.25 |
| 3 | Content-addressed build receipt | 4 | 0.90 | 2 | 1.80 |
| 4 | Hermetic worktree capsules | 4 | 0.80 | 3 | 1.07 |
| 5 | Outcome-calibrated family router | 4 | 0.75 | 4 | 0.75 |

### 1. Transactional BUILD admission

**What.** Replace the current placement→manual lease→worktree sequence with one reservation transaction:

1. Normalize declared files into resource keys.
2. Atomically reserve the task, resources, machine and branch namespace.
3. Create the worktree against the reserved base SHA.
4. Store the reservation ID in broker metadata and `.env.worktree`.
5. Heartbeat from the running implementer.
6. Release only after content-on-main or explicit abandonment.
7. Permit reaping only when there is no process, no active reservation and content is recoverable/on main.

Hot-zone reservation failure must not silently degrade to “unprotected.” Non-hot-zone local work may degrade only with an explicit `UNPROTECTED` receipt and no cross-host overlap.

**Why beyond SOTA.** Codex and Devin isolate environments; Bazel isolates actions; Nuzantara already has multi-host placement, scar history and content-aware cleanup. None of the surveyed systems combines those with a scar-aware distributed ownership transaction spanning placement, branch, worktree, heartbeat and reaping.

**Cost.** Two to three engineering days; deterministic Redis/local code; no LLM API and negligible flat-sub token cost.

**Gear.** 3, because it changes the shared worker plane and failure semantics.

**Risk/scar family.** A bad rollout could trigger **#2 exists ≠ armed** or **#5 sibling-race**; runtime-copy drift could trigger **#1 HOME-fork**.

**Before/after metric.** Before: two recorded W80 lost-work events and six W62 abandoned fan-out worktrees. After: **0 lost-work events and 0 overlapping hot-zone reservations for 90 days**, ≥99% reservation heartbeat continuity, p95 admission under two seconds, false refusal below 2%. Measure from reservation events joined to broker cleanup outcomes; no client data.

**Kill criterion.** Disable mandatory reservation if false refusal exceeds 5% for seven days or reservation availability falls below 99% without reducing near-collisions; retain telemetry and repair the protocol before re-arming.

**First PR.** `feat(agent-broker): add atomic resource reservation command`; existing `scripts/agent_lease.py`, `scripts/fleet_dispatch.py`, plus one new focused unit-test file; ≤380 net lines. Acceptance: two simultaneous requests for an overlapping set produce exactly one owner, and rollback leaves no partial keys.

### 2. Bottleneck-aware WIP governor

**What.** Admit BUILD work by scarce downstream tokens, not theoretical model seats:

- one full-suite token per machine by default;
- separate lightweight-edit, frontend-build, backend-test and hot-zone tokens;
- RAM/load as supporting signals, not the primary concurrency definition;
- queued rather than failed admission;
- oldest-ready/fair scheduling with task priority;
- an agent-heartbeat timeout that suspends rather than redispatches onto the same branch.

**Why beyond SOTA.** DORA advocates platform feedback and agent systems support parallel work, but the composition here is distinctive: local machine telemetry, flat-sub seat inventory, scars, serialized suites and useful-business-commit economics become one closed-loop controller. It exploits the always-on Pro/Mini asymmetry without confusing available LLM seats with available integration capacity.

**Cost.** Two to four engineering days, then a 30-day observation period; no additional paid service or API.

**Gear.** 3.

**Risk/scar family.** Over-admission triggers **#5 sibling-race**; an installed but bypassable semaphore triggers **#2 exists ≠ armed**.

**Before/after metric.** Before: 7–18 concurrent suites, 13/14 failed processes in one burst, p75 lead time 6.0 hours, and about **1.16 business commits per million output tokens**. After: at most one full suite per machine, 0/14 spawn failures in a repeated synthetic admission scenario, p75 ≤4.3 hours, and ≥2.0 retained business commits per million output tokens. Also target ≥25% more retained business commits per agent-hour.

**Kill criterion.** Roll back the scheduling policy if median queue wait exceeds saved execution time for two weeks or retained throughput improves by less than 10% after 30 comparable tasks.

**First PR.** `feat(agent-broker): add machine build-slot admission`; `scripts/agent_start.py` plus a new deterministic admission test file; ≤350 net lines. Acceptance: fourteen simulated requests produce bounded `READY/QUEUED` outcomes without process spawning or duplicate tokens.

### 3. Content-addressed build receipt

**What.** Every implementer emits a deterministic receipt, updated by scripts rather than prose:

- mandate/task ID, route and exact profile;
- base SHA, reserved resource set and worktree identity;
- claim commit SHA and proof that it was first after the base;
- environment/capsule fingerprint;
- reuse decision and referenced internal component, without copied PII;
- test command identities and red→green timestamps;
- final commit/diff statistics;
- terminal state: completed, suspended, abandoned or superseded.

Hash the canonical JSON. Store the active record in broker metadata and export a redacted summary for downstream review. No chain-of-thought, prompt body, secret or client datum belongs in it.

**Why beyond SOTA.** Agent platforms expose sessions and traces, and build systems hash inputs. No surveyed source joins implementation provenance, distributed claim, test progression, model-family route, PR scope and scar-compatible terminal state into a local-sovereign receipt. Nuzantara’s many seats and solo non-code-reviewing owner make this more valuable than another dashboard.

**Cost.** One to two engineering days; deterministic local I/O; zero extra LLM calls.

**Gear.** 2 for schema/producer, Gear 3 only when made mandatory.

**Risk/scar family.** A receipt written but not consumed is **#2 exists ≠ armed**; divergent runtime schemas are **#1 HOME-fork**.

**Before/after metric.** Before: 35/118 sessions unmapped (29.7%) and at least one documented silent-idle redispatch onto the same branch. After: ≥98% BUILD sessions mapped to an exact route, ≥95% complete receipts, 100% hot-zone receipts, and zero duplicate-branch redispatches for 90 days. Receipt generation p95 must remain below one second.

**Kill criterion.** Remove any field whose completion rate remains below 80% after two schema revisions or whose median capture overhead exceeds three minutes; keep the minimal identity/claim/test fields.

**First PR.** `feat(build): emit canonical local build receipts`; new `scripts/build_receipt.py` and focused tests; ≤360 net lines. Acceptance: repeated serialization is byte-identical, secret-like fields are rejected, and an invalid first-claim relationship fails deterministically.

### 4. Hermetic worktree capsules

**What.** Evolve dependency symlinks into content-addressed, read-only capsules keyed by lockfiles, interpreter/runtime version and relevant configuration. Each worktree receives:

- an immutable dependency base;
- a writable per-task cache overlay;
- an explicit environment manifest;
- a task-specific test database/schema namespace;
- a preflight that compares capsule identity across Pro/Mini;
- no dependency installation into the shared live backend environment.

This is incremental hermeticity, not a monorepo-wide Bazel migration.

**Why beyond SOTA.** Devin blueprints provide fresh baselines and Bazel declares every action input, but neither is composed with Nuzantara’s local two-node worktree broker, no-cloud-sovereignty constraint and multi-family implementation receipts. The capsule lets a task move between machines without turning shared `.venv`, `node_modules`, database state or HOME hooks into invisible inputs.

**Cost.** Five to eight engineering days over multiple PRs; additional local disk/cache space; no paid API.

**Gear.** 3.

**Risk/scar family.** Incorrect capsule selection creates **#1 HOME-fork**; a manifest that is generated but not enforced creates **#2 exists ≠ armed**.

**Before/after metric.** Before: broker comments record only 5/37 worktrees with required app `node_modules` before provisioning repair, plus a missing-`.venv` incident. After: 100% worktrees pass capsule preflight, selected deterministic tests agree across Pro/Mini ≥99%, and environment-origin false reds fall to zero for 90 days. Track cold-start p50/p95 and disk consumption.

**Kill criterion.** Stop expansion if cold start worsens by more than 20% after caching or if cross-machine agreement fails to exceed the symlink baseline after 30 tasks. Retain the manifest checker even if full capsules are rejected.

**First PR.** `feat(worktrees): verify dependency capsule fingerprints`; new `scripts/worktree_capsule.py`, focused tests, and a small call site in `scripts/agent_start.py`; ≤390 net lines. Acceptance: changed lockfile/runtime invalidates the fingerprint; identical inputs match across fixture hosts; the first PR only diagnoses and does not provision.

### 5. Outcome-calibrated family router

**What.** Resolve the roster contradiction with one executable router. Input features should include task class, language, expected change size, hot-zone membership, required tools, context size, current subscription health and local-only/PII constraints. Output must name exact family, profile and effort plus a confidence/reason. Begin with deterministic rules. After at least 30 receipt-backed tasks, evaluate an offline contextual policy against the incumbent; do not let it self-modify live.

Hard constraints remain outside optimization: Fable is never auto-routed; all LLM use is sanctioned CLI-only; no client/OSINT cleartext enters routing logs; paid Anthropic API remains forbidden.

**Why beyond SOTA.** Commercial agents usually choose within one provider. OpenHands is model-agnostic, but the surveyed systems do not combine six subscription seats, cross-family roles, scar-derived task risk, local machines, quota state and end-to-end retained-change outcomes. That is Nuzantara’s genuine asymmetry.

**Cost.** Five to seven engineering days plus a 30–60 task controlled evaluation; initially up to 1.25× flat-sub token use for matched comparisons.

**Gear.** 3.

**Risk/scar family.** Stale deployed copies are **#1 HOME-fork**; a telemetry-only “gate” is **#2 exists ≠ armed**. Poor routing can amplify **#5 sibling-race** by choosing more workers instead of better workers.

**Before/after metric.** Before: Sonnet handles 127/148 Agent dispatches (85.8%), 35/118 sessions are unmapped, and only one Kimi coding call is identifiable. After: unmapped routes <2%; eligible non-hot-zone BUILD work uses a non-Sonnet family in 20–40% of tasks; first-pass retained-change rate improves ≥15%; median lead time falls ≥15%; output tokens per retained business commit fall ≥25%. Diversity alone is not success.

**Kill criterion.** Retain deterministic safety routing but reject adaptive selection if 30 matched tasks show no improvement in retained-change rate or if median wall time increases by more than 25%.

**First PR.** `fix(routing): establish one executable BUILD precedence`; existing `scripts/model_routing_gate.py`, `MODEL_ROSTER.md`, and focused fixture tests; ≤300 net lines. Acceptance: the same task manifest produces one exact route; prohibited Fable/API/PII cases refuse; every documented default agrees with executable precedence.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: establish identity, ownership and baseline

Arm no new fleet scale. Implement atomic reservation, build receipts and BUILD metrics first. For two weeks, run reservations in shadow mode except on one non-production hot zone; compare intended owners with actual worktrees. Start collecting PR-size distribution in a fixture-testable script once GitHub access is available, separating generated, deletion-heavy and hand-written changes rather than enforcing a blind 400-line ceiling.

| First PR | Files | Cap | Gear | Acceptance test |
|---|---|---:|---:|---|
| Atomic resource reservation | `scripts/agent_lease.py`, `scripts/fleet_dispatch.py`, new focused tests | ≤380 | 3 | Two overlapping batch claims yield one owner and no partial state. |
| Canonical build receipt | new `scripts/build_receipt.py`, new tests | ≤360 | 2 | Stable hash, PII/secret-field rejection, valid terminal-state transitions. |
| BUILD craft metrics | new `scripts/build_craft_metrics.py`, fixture data/tests | ≤300 | 2 | Fixture produces median/p90 change size, route coverage and retained-work yield without network access. |

Wave exit: ≥95% shadow reservations match actual ownership, ≥90% BUILD receipts complete, and a trustworthy PR-size baseline exists. Otherwise remain in Wave 1.

### Wave 2 — Days 31–60: control capacity and environment

Make hot-zone reservations mandatory only after the Wave 1 threshold and Zero’s outage ruling. Add machine build-slot tokens, queue rather than fork at saturation, and ship diagnostic capsule fingerprints. Do not yet replace dependency provisioning.

| First PR | Files | Cap | Gear | Acceptance test |
|---|---|---:|---:|---|
| Machine build-slot controller | `scripts/agent_start.py`, new admission tests | ≤350 | 3 | Fourteen requests remain within declared per-machine limits; none silently disappears. |
| Capsule fingerprint preflight | new `scripts/worktree_capsule.py`, `scripts/agent_start.py`, tests | ≤390 | 3 | Lockfile/runtime changes invalidate identity; identical fixtures match. |
| Lease-aware cleanup predicate | `scripts/agent_start.py`, focused cleanup tests | ≤300 | 3 | Active reservation always blocks reap; content-on-main alone is insufficient. |

Wave exit: zero duplicate claims, zero reaped active work, spawn-failure reproduction reduced from 13/14 to 0/14, and capsule identity captured for ≥95% of new worktrees.

### Wave 3 — Days 61–90: calibrate routes and feed disciplined grunts

Resolve the model precedence ruling, then run matched task-shaped comparisons. H24 chore/Jules/Spark tasks must claim through the same broker and emit the same receipt. Restrict autonomous grunt work to deterministic transforms, property-test generation, documentation-local fixes and other reversible one-concern changes. Semantic codemods require a detector fixture and expected fixed output, following Semgrep’s tested-transform model.

| First PR | Files | Cap | Gear | Acceptance test |
|---|---|---:|---:|---|
| Executable BUILD router | `scripts/model_routing_gate.py`, `MODEL_ROSTER.md`, tests | ≤300 | 3 | Exact route for every fixture; hard rules cannot be optimized away. |
| Army receipt adapter | new `scripts/army_build_adapter.py`, queue-local fixture/tests | ≤350 | 2 | A grunt cannot start without claim/reservation and cannot finish without a valid receipt. |
| One tested semantic grunt transform | one new local rule plus before/fixed fixtures | ≤250 | 2 | Detection and autofix tests pass; second application is a no-op. |

Day-90 success: ≥25% more retained business commits per agent-hour, p75 lead time at or below 4.3 hours, unmapped routes below 2%, zero BUILD lost-work events, and ≥70% of sampled grunt changes accepted without human repair. If those numbers do not move, reduce concurrency rather than adding seats.

## 7. Needs-ruling

Only three structural choices require Zero:

1. **Canonical routing precedence:** choose whether BUILD is task-shaped with Sonnet as fallback, or workhorse-first with TP1/Gemini before Anthropic. Both currently appear in `MODEL_ROSTER.md`; code cannot faithfully enforce both.
2. **Hot-zone outage policy:** approve fail-closed reservation when Redis/ownership is unavailable, or explicitly accept unprotected availability. The recommendation is fail-closed for hot zones and explicit degradation elsewhere.
3. **Autonomous WIP budget:** approve the maximum simultaneous BUILD lanes/full suites and the maximum H24 grunt token budget per 24 hours. The recommendation is one full-suite token per machine until retained-work metrics justify more.

No credential, GUI action, production deployment or outward publication is required for this report.

## 8. §Meta-pattern

The single defective belief is:

> **If a rule, seat, hook, lease, queue or worktree exists, it governs the bytes.**

That belief generates nearly every finding. A documented lease becomes optional acquisition; a checked-in hook becomes assumed runtime enforcement; a worktree becomes assumed environment isolation; a model roster becomes assumed routing; a queue becomes assumed completed work; many available seats become assumed throughput; a “fixed” scar becomes assumed non-recurrence.

The Gear-3 correction is to move BUILD policy to the admission and completion boundaries: one transaction before any edit, one content-addressed receipt before completion, and one outcome metric before scaling. Doctrine then explains the mechanism instead of impersonating it.

## 9. Sources

1. [Google Engineering Practices — Small CLs](https://google.github.io/eng-practices/review/developer/small-cls.html) — living primary engineering guidance; accessed 2026-08-29; authoritative for small, self-contained changes and test inclusion.
2. [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) — 2024-12-19; primary account of composable agent patterns, routing, parallelism and ACI design.
3. [Anthropic — Claude Code best practices](https://code.claude.com/docs/en/best-practices) — living official documentation, originally published 2025-04-18; authoritative for Claude Code operating practice.
4. [METR — Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity](https://arxiv.org/abs/2507.09089) — 2025-07; primary randomized study of experienced maintainers doing real repository work.
5. [DORA — State of AI-assisted Software Development 2025](https://dora.dev/research/2025/dora-report/) — 2025; primary large-sample research on AI as an amplifier of engineering systems.
6. [OpenAI — Harness engineering: leveraging Codex in an agent-first world](https://openai.com/index/harness-engineering/) — 2026; primary description of worktree-local applications, ephemeral observability and long-running agents.
7. [Cognition — Devin golden snapshots](https://docs.devin.ai/product-guides/snapshots) — living official documentation; accessed 2026-08-29; primary source for fresh session baselines and environment blueprints.
8. [SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering](https://arxiv.org/abs/2405.15793) — 2024-05-06, revised 2024-11-11; primary paper connecting ACI design to benchmark performance.
9. [OpenHands: An Open Platform for AI Software Developers as Generalist Agents](https://arxiv.org/abs/2407.16741) — 2024-07-23, revised 2025-04-18; primary ICLR 2025 system paper on sandboxed, model-agnostic agents.
10. [Bazel — Hermeticity](https://bazel.build/concepts/hermeticity) — living official documentation; accessed 2026-08-29; authoritative for declared-input, reproducible build design.
11. [Hypothesis — A Claude Code command for Hypothesis](https://hypothesis.works/articles/claude-code-plugin/) — 2025-11-01; primary account of agent-generated property tests finding confirmed production-library bugs.
12. [Semgrep — Powerfully autofixing code with an AST-based approach](https://semgrep.dev/blog/2022/autofixing-code-with-semgrep/) — 2022-11-03; primary implementation report with measured Python and JavaScript autofix validity.