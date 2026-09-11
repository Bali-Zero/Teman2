---
panel: beyond-sota-xfamily
lane: 06-ci-merge-queue-ship-pipeline
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T18:43:57Z
finished: 2026-08-28T18:53:57Z
duration_s: 600
exit: 0
words: 5369
prompt_sha256_16: 57620ab545d12b25
prompt_chars: 17867
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 6/13 — CI, merge queue & ship pipeline
model: OpenAI GPT-5.6 sol, reasoning effort ULTRA (pinned lane)
sources: 14
repo_files_verified: 29
status: complete
---

## 0. TL;DR

Nuzantara is **AHEAD of SOTA in queue-failure doctrine and scar-driven diagnosis, but BEHIND SOTA in executable policy coherence, CI efficiency, and automatic recovery**.

The largest gap is not missing machinery; it is contradictory machinery. The runbook and pipeline skill require bare `gh pr merge --auto`, while the whitelist workflow, its tests, and another doctrine passage encode `--auto --squash`. The workflow can then exit green without arming anything.

The top three moves are:

1. Compile one executable landing contract across required checks, triggers, CODEOWNERS, arm semantics, and queue actions.
2. Replace schedule-dependent queue watching with an event-sourced, head-SHA-bound merge admission controller.
3. Introduce an exact-tree CI proof graph that measures check yield and eliminates redundant PR/merge-group executions without weakening main.

The current 106-entry workflow directory contains 104 active YAML workflows, but only 11 required contexts. The system is over-instrumented yet under-coherent.

## 1. How Nuzantara does it today

### The landing lifecycle

The intended lifecycle is unusually explicit:

1. A change is built in a dedicated worktree.
2. Local pre-push guards classify the change and may run a machine-wide serialized suite.
3. A single-concern PR is opened, normally under approximately 400 net lines.
4. CODEOWNERS and hot-zone checks protect high-risk surfaces.
5. CI validates the PR.
6. `mq arm` freezes the branch and records its head SHA.
7. GitHub’s merge queue retests the synthetic merge-group commit.
8. After merge, `mq handoff` retires the branch and starts successors from fresh `origin/main`.

The lifecycle, same-cause three-round suspension rule, Dependabot serialization rule, freeze-after-arm rule, rerun diagnosis, and handoff requirement are defined in `CLAUDE.md:29-63` and `docs/runbooks/merge-queue-discipline.md`. That is stronger process doctrine than most repositories possess.

### The first critical contradiction: “arm” has multiple definitions

`docs/runbooks/merge-queue-discipline.md:253-338` and `.claude/skills/pipeline-ship/SKILL.md` require the native-queue gesture to be bare:

```text
gh pr merge <PR> --auto
```

They explicitly warn that `--auto --squash` can be rejected by the native merge queue and arm nothing. Yet:

- `.github/workflows/auto-merge-whitelist.yml` invokes `gh pr merge ... --auto --squash --delete-branch`.
- Its arm failure is downgraded to a warning and successful workflow exit.
- `scripts/tests/test_auto_merge_whitelist.py:200-231` expects `--auto --squash`, so the test preserves the defect.
- A separate operational passage in `CLAUDE.md` also presents the squash form.

This is a concrete family-#2 failure: the automation can be green while the intended state—armed—is absent.

The whitelist workflow otherwise has good defensive properties: `pull_request_target`, author/branch/path allowlists, paginated file enumeration, fail-closed file API behavior, and head-SHA pinning. The problem is at its final state transition, where correctness matters most.

### Required checks and policy surfaces

The checked-in snapshot `infra/required.d/contexts.json` records 11 required contexts, generated from the API on 2026-08-27. The runbook documents the recent reduction from 27 to nine, followed by reinstatement of two checks with demonstrated catches—actionlint and guard conformance—yielding 11.

The file is explicitly advisory, however. It records external branch-protection state; it does not itself enforce that state. Consequently, drift can arise among:

- GitHub branch protection or rulesets;
- `infra/required.d/contexts.json`;
- workflow job names;
- `merge_group` triggers;
- runbook prose;
- tests that assert expected contexts.

`.github/CODEOWNERS` protects workflows, ownership policy, pre-push trust bundles, impact maps, deploy configuration, migrations, authentication, pricing, embeddings, RAG invariants, and top-level doctrine under the Tier-1 owner. Its default `*` entry has no owner, so safety depends on the explicit hot-zone list remaining exhaustive.

`.github/workflows/hot-zone-pr-gate.yml` calls itself partial enforcement and runs on `pull_request`, but the inspected trigger does not include `merge_group`. It therefore does not independently attest the synthetic queue tree. It is also absent from the 11-context snapshot, so it is a PR-stage side gate rather than a current queue proof.

### CI inventory and cost

The workflow directory contains:

| Inventory signal | Verified count | Interpretation |
|---|---:|---|
| Directory entries | 106 | Includes non-active artifacts |
| Active `*.yml` files | 104 | Actual workflow-scale surface |
| Filename contains `cron` | 17 | Scheduled-work signal |
| Filename contains watcher/breaker/sentinel/reaper terms | 13 | Operational surveillance signal |
| Filename contains gate/test/lint/security/audit terms | 43 | Quality-control signal |

The last three categories overlap and are not a disjoint census. The key point is the control-plane surface: 104 active YAML workflows for 11 required contexts.

`.github/workflows/tests.yml` is comparatively mature. It supports `pull_request` and `merge_group`, prevents merge-group cancellation, uses a trusted-base change classifier, preserves stable fan-in context names, shards backend tests, and reserves broader coverage for merge groups and schedules.

The dated audits show the economic problem before the 27-to-11 reduction:

- Sixty sampled PRs used approximately 60–68 checks and 121–138 runner-minutes each; median open-to-merge was 61 minutes. `research/operations/2026-08-21-token-ceremony-ci-system-audit.md`
- One representative PR spent about 30 minutes in PR CI and another 33 minutes in queue CI.
- The system averaged about 1.5 merge-group entries and roughly 2.5 backend-suite executions per merged change.
- A ledger-only PR still launched 53 checks and consumed about 84 runner-minutes.
- Setup represented approximately 33% of measured step time.
- Of 258 merges in seven days, 33% were docs and 11% changed only `PENDING-ARMS.md`.

The later runner audit measured 21,054 runs in one day: 53.5% from PRs and 26.4% from merge groups. Tests and Security represented about 94% of the top-five estimated slot consumption. Sharding reduced backend wall time from approximately 1,068 seconds to 338 seconds, but increased concurrent slot demand. The documented plan limit was 60 slots, while the sampled lower-bound peak was only 15; queue-to-start latency was not measured. `research/operations/2026-08-23-runner-slot-audit.md`

Those measurements predate the final 11-context ruling. The new regime therefore needs a fresh baseline rather than assuming the reduction delivered its intended effect.

### Pre-push and the suite lock

`.husky/pre-push` still verifies its trusted-root bundle and runs classification and tip-drift logic, but the full backend suite has been default-off since 2026-08-13. It runs only under explicit `PREPUSH_FULL=1` or equivalent override.

That decision was evidence-based: among 88 push logs, only two contained genuine failures, while 26 produced no verdict—nine lock timeouts and 17 terminations. The local suite was also a strict subset of CI.

`scripts/prepush_suite_lock.sh` is nevertheless a strong single-flight implementation: atomic acquisition, FIFO tickets, stale-PID detection, heartbeat, a 75-minute timeout, and propagation of the child result. It directly addresses the prior case where nine suites shared one database and produced false red/livelock. The weakness is naming and doctrine drift: `.claude/skills/pipeline-ship/SKILL.md` still reads as if the expensive suite were the ordinary pre-push path.

### Queue watching, red main, and cleanup

`merge-queue-watch.yml` is scheduled every ten minutes, but its own header records only four executions in 6 hours 11 minutes—an average gap of 124 minutes—while its query looked back only 15 minutes. It therefore had a structural missed-event window.

`merge-gate-integrity-watch.yml` correctly distinguishes a verified policy violation from “cannot verify,” but it is a signaler rather than a gate.

`main-red-breaker.yml` triggers from `workflow_run` and alerts when the same job is red in consecutive queue or schedule runs. That is a useful noise filter, but the inspected workflow sends a P0 notification/spool entry; it does not mechanically freeze admission. It is currently a red-main detector, despite the stronger name.

`scripts/branch_graveyard_cleanup.sh` is safe by default: dry-run, ancestry checks, per-file blob equality after squash merges, age classes, and GitHub PR lookup. Its GitHub lookup is report-only and capped at 500 results. The dated quarantine index contains 613 lines, including its header, demonstrating substantial historical branch/worktree residue. `research/operations/2026-08-20-fleet-quarantine-index.tsv`

The 2026-08-26 fleet retro measured 170 merged PRs, median lead time 29.6 minutes, p90 377 minutes, 16 retraction chains, 24 open non-Dependabot PRs—17 at least 48 hours old—and 13 open Dependabot PRs. It also recorded 45 queue-unstick pages, with one PR paged 12 times and still blocked. `research/operations/2026-08-26-retro-fleet-sessions-25-26.md`

Live `gh pr list` and `gh run list` measurements could not be refreshed: the snapshot has no configured remote, and explicit GitHub API access failed from the isolated environment. No current open-count, DIRTY-count, median age, or last-100 workflow failure rate is inferred.

## 2. Scars & ledger evidence in this area

The external `MEM:` files named in the lane brief are outside the permitted snapshot and were not opened. In particular, the claimed “19 merge-queue traps” could not be independently recounted from `MEMORY_MERGE_QUEUE_TRAPS.md`. Repository-native evidence still establishes at least eleven named incidents.

| Evidence | What failed | Recurrence implication |
|---|---|---|
| W69, W123 | Required checks or workflows existed but were not mechanically armed | Family #2: configuration presence was mistaken for enforcement |
| W101 | A fail-closed pre-push branch was unreachable under shell behavior | A guard’s intended semantics were not mutation-proven |
| W118 | Queue proxies appeared healthy while the queue stopped progressing for 11 hours | Multiple observable proxies did not prove the actual state |
| W124 | DIRTY/check-suite state was inferred from an incomplete subset | Partial state was treated as authoritative |
| W126 | Draft status did not cause the expected queue ejection | A GitHub state transition was assumed rather than observed |
| W86 | Auto-merge landed before a later correction, leaving doctrine stale | Arm/freeze boundaries were violated |
| W102 | Two-dot diffing blamed an innocent PR for changes already on main | The wrong comparison tree contaminated gate attribution |
| W109b | Independent PRs updating one monotonic central register blocked each other without meaningful semantic conflict | Central generated/ledger files create structural contention |
| W111 | Rerunning replayed a stale merge ref; `autoMergeRequest` and queue membership were individually ambiguous | A rerun was mistaken for revalidation of current code |
| W125 | A clean fusion lacked the state marker consumers depended upon | Content success did not imply protocol completion |

Sources: `.claude/rules/cicatrix-superscar.md` and the corresponding blocks in `.claude/rules/cicatrix-scars.md`.

`.claude/skills/modus/AMENDMENTS.md` records repeated manifestations:

- Review after arm allowed a defective change to race into the queue.
- Nine concurrent suites sharing one database created false red and livelock.
- PR #3507 was armed before the refuter completed.
- An auto-merge request silently disappeared after a required check went red.
- Long pre-push suites had to be detached and serialized.

The ledger also demonstrates how advisory CI can become invisible. `.claude/skills/modus/PENDING-ARMS.md:19` records an advisory full-stack smoke that had never been green: 13 failures, 17 skips, zero successes across 30 inspected runs. The parent workflow still reported success because the job used `continue-on-error`.

The 2026-08-26 retro found `scripts/tests/test_auto_merge_whitelist.py` at 24 failures out of 73 tests on clean main and reported that no workflow then ran it. This is a particularly severe recurrence pattern: a test existed, encoded the wrong queue command, and was itself outside effective CI reach.

The evidence supports two dominant superscars:

- **Family #2 — Exists ≠ Armed:** files, workflow runs, schedules, and auto-merge requests are repeatedly treated as proof of live enforcement.
- **Family #9 — State-schema mutation drift:** PR head, merge-group SHA, base tree, check suite, queue membership, and central-register state are conflated even though each changes independently.

## 3. World SOTA survey

| System/practice | Primary source | Mechanism | Published effect | Transferability |
|---|---|---|---|---|
| GitHub native merge queue | [GitHub merge-queue documentation](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue) | Synthetic merge groups, configurable build concurrency, queue-selected merge method, mandatory `merge_group` CI events | No performance result published | Already the substrate; Nuzantara must follow its state model exactly |
| GitHub rulesets | [GitHub rulesets documentation](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository) | Composable policy, bypass controls, evaluation mode, rule insights, importable JSON | No performance result published | Stronger external policy SSOT than classic protection; requires admin ruling |
| Graphite merge queue | [Graphite queue optimizations](https://graphite.com/docs/merge-queue-optimizations) | Stack-aware fast-forwarding, speculative parallel CI, batching | Vendor reports 1.5× faster merges; up to 2.5× for stack-heavy users | Mechanisms transfer; paid external service does not fit by default |
| Mergify batching | [Mergify batch documentation](https://docs.mergify.com/merge-queue/batches/) | Batch validation, binary failure isolation, result reuse, anti-flake intermediate-result policy | Vendor claims throughput/cost gains without public methodology on this page | Scope-aware batching is useful only after Nuzantara measures failure correlation |
| Uber SubmitQueue | [CI at Scale: Lean, Green, and Fast](https://arxiv.org/abs/2501.03440) | Speculative execution, build prioritization, queue/resource optimization | About 53% less CI resource use, 44% less CPU, 37% lower p95 waiting time | Most relevant economic benchmark; can be implemented incrementally on native queue |
| Chromium CQ | [Chromium CQ documentation](https://chromium.googlesource.com/chromium/src/+/119.0.6045.105/docs/infra/cq.md) | Impact-selected try jobs, OWNERS/presubmit checks, mirrored sheriffed builders, explicit admission criteria | New CQ builders should have median cycle under 40 minutes, p90 around one hour, and sufficient catch yield | Its “earn your place in CQ” rule maps directly to Nuzantara’s 104 workflows |
| Google TAP speculative cycles | [Speculative Testing at Google with Transition Prediction](https://research.google/pubs/speculative-testing-at-google-with-transition-prediction/) | Failure-likelihood scheduling from change and test history | About 70 minutes lower median time to detect novel breakages; evaluated on 120B test-cycle pairs | Full ML scale is unnecessary; historical yield prioritization transfers |
| Google flake-aware culprit finding | [Flake Aware Culprit Finding](https://research.google/pubs/flake-aware-culprit-finding/) | Bayesian noisy search using prior flake probability | Evaluated across more than 13,000 breakages | Better model than blind rerun; queue shepherd should use historical reliability |
| Nx affected graph | [Nx affected documentation](https://nx.dev/docs/features/ci-features/affected) | Computes changed projects plus transitive dependents; understands lockfile effects | No independent effect published on the reference page | Nuzantara already has impact-map foundations; extend them across Python and workflow policy |
| Bazel remote cache | [Bazel remote caching](https://bazel.build/remote/caching) | Content-addressed action keys over declared inputs, commands, environment, and outputs | No universal result; reuse is exact-input based | The proof model transfers even if Bazel itself does not |
| Meta Sapling | [Meta Sapling engineering report](https://engineering.fb.com/2022/11/15/open-source/sapling-source-control-scalable/) | First-class stacks, mutation history, automatic restacking, clear commit topology | Demonstrated at tens of millions of files, commits, and branches | Stack UX transfers; wholesale source-control replacement would be disproportionate |
| Rust Bors | [Rust Forge Bors documentation](https://forge.rust-lang.org/infra/docs/bors.html) | Simple explicit approval-to-queue state machine managed as infrastructure | No published performance delta | Valuable counterexample: small, legible landing state can beat workflow proliferation |
| Semantic-conflict testing | [Detecting semantic conflicts with unit tests](https://www.sciencedirect.com/science/article/pii/S0164121224001158) | Generated tests detect conflicts that textual and structured merge miss | Evaluated on 85 merge scenarios | Supports test-backed resolution, not autonomous LLM conflict merging |
| DORA | [2025 DORA report announcement](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report) | Measures delivery throughput and stability together rather than optimizing speed alone | Multi-year industry dataset; report emphasizes combined product and delivery outcomes | Use lead time and change-failure outcomes, supplemented by queue-specific cost/yield metrics |

The most transferable systems are Uber SubmitQueue, Chromium CQ, Google TAP, and GitHub’s native queue.

Uber demonstrates that queue policy and scheduling—not merely faster tests—can halve CI resource demand. Chromium supplies the missing admission principle: a check belongs in the landing path only if it has an owner, reproducible configuration, acceptable latency, and demonstrated catch value. Google shows that historical evidence can prioritize work, but its own research warns that simple recent-history selectors do not perform as well as expected; Nuzantara should begin with deterministic dependency and exact-tree evidence rather than speculative ML.

GitHub’s state model is non-negotiable. A merge-group SHA is a different tested object from the PR head. A workflow required on the queue must receive `merge_group`. The queue’s configured merge method should not be reasserted incompatibly by the arm command.

Graphite and Mergify show the throughput ceiling available from speculation and batching, but buying either would surrender local control and add a paid dependency. Their algorithms should be copied selectively into the existing native-queue/local-machine organism.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Queue doctrine and failure taxonomy | **AHEAD** | `mq arm/requeue/handoff`, freeze semantics, cause-specific rerun guidance, three-round suspension, and W111’s stale-ref model exceed typical repository doctrine |
| Executable landing-policy coherence | **BEHIND** | Bare-auto doctrine conflicts with workflow, test, and CLAUDE passage; arm failure can exit green |
| Required-check policy as code | **BEHIND** | `infra/required.d/contexts.json` is an advisory snapshot, not the generator or enforcer of live rules |
| CODEOWNERS/hot-zone segmentation | **AT** | Extensive Tier-1 paths are protected, but default ownership is open and the hot-zone gate does not run on `merge_group` |
| Queue throughput | **BEHIND** | Dated baseline shows approximately 2.5 backend executions per merge, 121–138 runner-minutes per PR, and no measured speculative/batch optimization |
| Change-impact selection | **AT** | `tests.yml` has a trusted-base classifier and shards; docs/ledger changes were still historically overtested |
| CI cache/proof reuse | **BEHIND** | No inspected mechanism reuses an attestation solely by the complete action/tree digest in the Bazel sense |
| Flake and infra-failure handling | **AT in diagnosis; BEHIND in control** | Queue Shepherd doctrine distinguishes INFRA/CODE/CONFLICT, but advisory tests can remain never-green and schedule watches miss events |
| Red-main breaker | **BEHIND its name** | `main-red-breaker.yml` detects and alerts consecutive failures but does not mechanically close admission |
| Pre-push resource coordination | **AHEAD in mechanism; BEHIND in reach** | `prepush_suite_lock.sh` is robust, but the expensive suite is default-off and doctrine still implies otherwise |
| DIRTY/conflict handling | **AHEAD in understanding; BEHIND in automation** | W109b and runbook §6quinquies identify structural register conflicts; the retro still recorded 45 unstick pages |
| Dependabot serialization | **BEHIND** | “One lockfile at a time” is doctrine, while the inspected control surfaces do not prove a lockfile-cohort admission scheduler |
| Branch hygiene | **AT** | Safe graveyard tooling and a reaper exist; the quarantine index still contains 612 historical records |
| CI observability | **BEHIND** | Exceptional audits are excellent, but queue-to-start latency and post-11-context economics are not continuously measured |
| Solo-owner autonomy | **AHEAD conceptually** | Freeze, handoff, suspension, and generator≠grader suit an owner who cannot manually review code; contradictions prevent full autonomous trust |

## 5. Beyond-SOTA recommendations

Ranking uses `(impact × confidence) / cost`, with impact and cost scored 1–5. “Beyond SOTA” is scoped to the 14 surveyed primary sources: none combines these mechanisms with Nuzantara’s scar corpus, cross-family review, exact agent lifecycle, and always-on local machines.

### 5.1. Executable Landing Contract Compiler — score 4.75

**What:** Introduce one machine-readable landing contract describing:

- required context names and producers;
- valid event triggers;
- arm command shape;
- freeze and requeue transitions;
- CODEOWNERS/hot-zone coverage;
- check severity;
- allowed automated actions;
- exact head/base/merge-group identity requirements.

A deterministic checker compares it against workflow YAML, `infra/required.d/contexts.json`, CODEOWNERS, tests, and selected doctrine assertions.

**Why it beats surveyed SOTA:** GitHub rulesets centralize server policy, but none of the surveyed systems checks semantic agreement among local runbooks, shell commands, tests, workflow triggers, and live protection snapshots. Nuzantara can exploit its scar corpus to encode mutations that previously caused real failures.

**Before → after:** Four conflicting arm surfaces → zero; unknown `merge_group` coverage → 100% of required producers; policy drift discovered after queue failure → discovered in the introducing PR.

**Cost:** 12–18 engineering hours plus one flat-subscription cross-family review; deterministic runtime, no paid API. **Gear:** 3.

**Risk/scars:** Family #2 if the compiler exists but is not required; family #9 if its schema changes without regenerating consumers.

**Metric:** Contract contradictions, orphan required contexts, required producers lacking `merge_group`, and policy-age drift. Measure on every PR and daily against the API snapshot.

**Kill criterion:** Kill or redesign if it produces more than 10% false positives over 30 PRs or requires duplicating workflow logic rather than deriving it.

**First PR:** `fix(ci): make native queue arming bare and fail-closed`; modify `.github/workflows/auto-merge-whitelist.yml` and `scripts/tests/test_auto_merge_whitelist.py`; under 120 net lines. Acceptance: mutation adding `--squash` fails; simulated arm failure makes the job red.

### 5.2. Event-sourced Merge Admission Controller — score 2.13

**What:** Represent each transition as an append-only fact keyed by:

```text
{pr_number, head_sha, base_sha, merge_group_sha, check_suite_id}
```

A pure reducer derives `OPEN`, `REVIEWED`, `ARMED`, `QUEUED`, `EJECTED_INFRA`, `EJECTED_CODE`, `DIRTY`, `MERGED`, or `SUSPENDED`. Actions are idempotent and level-triggered. Only proven INFRA failures may be rearmed, at most three times per PR/head/24h; CODE, CONFLICT, MANUAL, and UNKNOWN remain fail-closed.

**Why it beats surveyed SOTA:** Existing queues automate landing, but the surveyed systems do not combine replayable queue state with a scar-derived causal taxonomy, agent freeze/handoff, and local-sovereignty failover. It turns W111/W118/W123 into state invariants.

**Before → after:** Ten-minute nominal watch with observed 124-minute gaps → transition detection under 60 seconds; ambiguous queue proxies → one reducer with replayable evidence; repeated pages → one deduplicated incident per exact state.

**Cost:** 30–45 hours, local Pro/Mini runtime, flat-sub tokens only for design/review. **Gear:** 3.

**Risk/scars:** Family #2 if the event receiver is not armed; family #9 if head and merge-group identities are collapsed.

**Metric:** Missed ejections, transition latency, duplicate actions, stale-ref reruns, manual queue pages. Replay the ledger against GitHub terminal outcomes.

**Kill criterion:** Immediate rollback if any CODE/UNKNOWN failure is automatically rearmed, or if duplicate state-changing actions exceed 0.1%.

**First PR:** `feat(merge-os): add pure queue-event reducer in shadow mode`; proposed `scripts/merge_event_reduce.py` and `scripts/tests/test_merge_event_reduce.py`; under 400 lines. Acceptance: replayed fixtures are deterministic, out-of-order events converge, and a stale SHA cannot authorize an action.

### 5.3. Exact-tree CI Proof Graph — score 1.60

**What:** Separate:

- PR feedback proofs;
- merge-group collision proofs;
- scheduled broad health proofs.

Each action emits an attestation over the complete tree SHA, dependency closure, toolchain, command, environment class, and input hashes. A result may be reused only when that digest is identical. PRs run the minimal dependency proof; merge groups run collision-sensitive checks not already proven for the exact tree.

**Why it beats surveyed SOTA:** Google/Nx provide test selection and Bazel provides content-addressed reuse. None of the surveyed sources combines those with risk gear, queue-state identity, scar recurrence, and required-context generation for an agent-run organism.

**Before → after:** Approximately 2.5 backend executions per merge → at most 1.25; 121–138 runner-minutes per PR → under 70; median 29.6-minute lead time → under 15 without higher main-red incidence.

**Cost:** 45–70 hours in incremental slices; no new paid service. **Gear:** 3.

**Risk/scars:** Family #9 through incomplete digests; family #2 if GitHub accepts a fan-in context without all required attestations.

**Metric:** Runner-minutes per merged PR, cache/proof hit rate, unique failures caught at PR versus merge-group stage, and escaped-main failures.

**Kill criterion:** Any missed deterministic failure attributable to proof reuse disables reuse for that proof class. Kill the program if 30-day savings remain below 20%.

**First PR:** `feat(ci): report backend proof-graph decisions without skipping tests`; modify the trusted change-map path in `.github/workflows/tests.yml` plus one focused test module; under 350 lines. Acceptance: shadow selection includes every test that actually failed during replay of the previous 30 days.

### 5.4. CI Value Ledger and SLO Governor — score 1.20

**What:** Give every workflow/context an owner, severity, p50/p95 queue delay, execution time, setup share, flake rate, unique-catch count, rerun cost, and runner-minutes per useful catch. Chromium-style admission rules determine whether a check deserves required, advisory, scheduled, or retired status. Enforcement changes remain proposals until ruled.

**Why it beats surveyed SOTA:** DORA measures delivery outcomes and Chromium evaluates CQ builders. Nuzantara can add per-check scar prevention and PENDING-ARMS debt, linking cost directly to failures the organism has actually suffered.

**Before → after:** Queue-to-start unknown → 100% measured; 33% setup share → below 15%; never-green advisory jobs → zero unresolved beyond 24 hours; 104 workflows with diffuse ownership → 100% classified.

**Cost:** 20–30 hours. **Gear:** 2 for telemetry, 3 for enforcement.

**Risk/scars:** Family #2 if metrics exist but nobody consumes them; family #9 if renamed jobs split history.

**Metric:** The ledger itself, checked daily and summarized weekly.

**Kill criterion:** Telemetry consuming more than 1% of total runner-minutes or producing recommendations contradicted by three consecutive human audits.

**First PR:** `feat(ci): measure queue-to-start and setup ratio`; modify `scripts/queue_baseline_probe.py`, its tests, and the existing merge-queue baseline workflow; under 300 lines.

### 5.5. Lockfile-cohort Dependabot admission — score 1.19

**What:** Compute the lockfiles affected by every dependency PR. Permit only one armed PR per overlapping lockfile cohort; automatically consider the next only after the previous PR reaches a terminal state on fresh main. GitHub concurrency alone is insufficient because it retains at most one pending member and can silently displace older work.

**Why it beats surveyed SOTA:** Mergify scopes by path and Graphite by stacks; neither surveyed source describes a bot-specific lockfile cohort with terminal-state admission and exact-main refresh.

**Before → after:** Doctrine-only serialization and 13 open dependency PRs in the dated retro → zero overlapping lockfile PRs simultaneously armed; dependency PR p90 age below 48 hours.

**Cost:** 10–16 hours. **Gear:** 2 in report mode, 3 when arming.

**Risk/scars:** Family #2 if the scheduler reports serialized while native auto-merge remains armed elsewhere; family #9 if lockfile renames or generated locks are missed.

**Metric:** Cohort overlap violations, dependency PR age, conflict/ejection count, and updates merged per week.

**Kill criterion:** Any incorrect cohort permits two conflicting dependency PRs to queue, or throughput drops below the current 30-day baseline for two weeks.

**First PR:** `feat(ci): report Dependabot lockfile cohorts`; proposed `scripts/dependabot_lockfile_cohorts.py` and tests; under 300 lines, no state changes.

### 5.6. Typed structural-conflict lanes — score 0.75

**What:** Stop treating all DIRTY states alike:

- Append-only evidence such as `evidence/2026-08/**/{brief,pack}.yml` remains independently owned.
- Central registries such as `apps/organism/organism/organs_registry.yaml` move toward per-owner fragments plus deterministic canonical generation.
- MDX bodies such as `apps/mouth/src/content/**/*.mdx` remain human/agent-owned documents; they are rebased or reauthored, never semantically auto-merged.
- Generated aggregates are written by one canonical writer and excluded from ordinary PR ownership.

**Why it beats surveyed SOTA:** Structured-merge research improves syntax, while queues scope changes. This recommendation selects a different conflict protocol from the artifact’s semantics and provenance, using W109b as training data.

**Before → after:** 45 queue-unstick pages in the dated retro → fewer than five per 14 days; central-register DIRTY recurrence reduced by at least 80%.

**Cost:** 40–60 hours across multiple one-concern PRs. **Gear:** 3.

**Risk/scars:** Family #9 through fragment-schema drift; family #2 if both canonical and legacy writers remain active.

**Metric:** DIRTY incidents by file family, manual resolutions, regeneration determinism, and lost/reordered entry count.

**Kill criterion:** Any lost registry entry, nondeterministic output, or inability to explain at least 80% of current hotspot conflicts.

**First PR:** `feat(merge-os): classify DIRTY hotspots by artifact semantics`; proposed `scripts/classify_dirty_hotspots.py` and tests; under 350 lines, report-only.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: restore one truth

| PR | Files | Limit | Gear | Acceptance test |
|---|---|---:|---:|---|
| `fix(ci): make native queue arming bare and fail-closed` | `.github/workflows/auto-merge-whitelist.yml`; `scripts/tests/test_auto_merge_whitelist.py` | 120 | 3 | `--squash` mutation fails; arm failure cannot exit green |
| `fix(ci): validate hot zones on merge groups` | `.github/workflows/hot-zone-pr-gate.yml`; focused trigger test | 150 | 3 | Removing `merge_group` makes the test fail; PR and queue diff bases are separately verified |
| `feat(merge-os): introduce executable landing contract` | proposed `infra/merge-os/landing-contract.yml`; `scripts/check_landing_contract.py`; tests | 400 | 3 | Orphan context, wrong arm verb, or missing queue trigger each produces a deterministic red |
| `feat(ci): add queue-to-start SLO telemetry` | `scripts/queue_baseline_probe.py`; existing baseline workflow; tests | 300 | 2 | Fixture timestamps reproduce queue, execution, and setup percentiles exactly |

Wave-1 exit criteria: zero arm-command contradictions, 100% required-context producer mapping, current post-11-context runner baseline, and no required producer missing `merge_group`.

### Wave 2 — Days 31–60: observe state before acting

| PR | Files | Limit | Gear | Acceptance test |
|---|---|---:|---:|---|
| `feat(merge-os): reduce queue events in shadow mode` | proposed `scripts/merge_event_reduce.py`; tests | 400 | 3 | Out-of-order replay converges; stale head cannot authorize rearm |
| `feat(ci): inventory check yield and flake tax` | proposed `scripts/ci_value_ledger.py`; tests; report artifact | 400 | 2 | Every active YAML receives owner/severity/cost classification; rename continuity is tested |
| `feat(ci): report Dependabot lockfile cohorts` | proposed cohort script and tests | 300 | 2 | Two PRs sharing any lockfile are placed in the same cohort |
| `chore(branches): make graveyard truncation explicit` | `scripts/branch_graveyard_cleanup.sh`; tests | 180 | 2 | More than 500 fixture PRs produces pagination or an explicit incomplete verdict, never a complete-looking partial report |

Wave-2 exit criteria: seven days of shadow state with zero unexplained transitions; every advisory failure older than 24 hours has an owner or deliberate retirement proposal.

### Wave 3 — Days 61–90: enforce measured reductions

| PR | Files | Limit | Gear | Acceptance test |
|---|---|---:|---:|---|
| `feat(ci): shadow backend affected-proof selection` | `.github/workflows/tests.yml`; trusted impact-map code; tests | 350 | 3 | Thirty-day replay covers every historical deterministic failure |
| `feat(merge-os): rearm proven infra ejections only` | queue reducer/action adapter; tests | 350 | 3 | CODE, CONFLICT, MANUAL, UNKNOWN, and stale-SHA fixtures are impossible to rearm |
| `feat(organism): compile one registry from owned fragments` | `apps/organism/organism/organs_registry.yaml`; proposed fragment/compiler paths; tests | 400 | 3 | Random fragment order produces byte-identical registry; duplicate IDs fail closed |

Wave-3 targets:

- Median PR lead time below 15 minutes.
- Runner-minutes per merged PR below 70.
- Backend suite executions per merge at or below 1.25.
- Queue-event detection below 60 seconds.
- Fewer than five DIRTY unstick pages per 14 days.
- Zero increase in escaped-main failures.

## 7. Needs-ruling

1. **GitHub rulesets migration:** Zero must approve replacing or layering classic branch protection, including bypass principals and administrative GUI changes.
2. **Autonomous queue authority:** Zero must rule whether the controller may rearm proven INFRA failures, cancel stale runs, or freeze admission when main is repeatedly red.
3. **CI risk budget:** Reducing PR-stage execution requires an explicit acceptable change-failure ceiling and rollback threshold.
4. **Webhook credentials:** A local event receiver requires GitHub App/webhook installation and credential provisioning.
5. **Paid external queue or runner capacity:** Graphite, Mergify, or additional runner spend requires a business decision. None is necessary for Waves 1–2.

No ruling is required for report-only telemetry, the bare-auto correction, contract linting, or shadow reducers.

## 8. §Meta-pattern

The single defective belief is:

> **A named or documented state is equivalent to a current, mechanically enforced, hash-bound fact.**

That belief explains the entire lane:

- A workflow named “auto merge” can finish green without arming.
- A “main red breaker” can alert without breaking admission.
- A ten-minute schedule can run every 124 minutes.
- An advisory test can be never-green while its workflow reports success.
- A required-context snapshot can drift from live protection.
- A pre-push “gate” can have its expensive suite default-off.
- A rerun can validate an obsolete merge ref.
- Two logically independent changes can collide through one monotonic register.

The cure is not more prose or more workflows. Every landing transition must carry proof of the exact PR head, base, merge-group tree, policy version, and successful action. One executable contract defines legal transitions; one replayable reducer observes them; every CI result earns its cost through measured catch value.

## 9. Sources

1. [GitHub — Managing a merge queue](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue). Accessed 2026-08-29. Authoritative definition of native queue events, concurrency, merge groups, and merge methods.
2. [GitHub — Creating rulesets for a repository](https://docs.github.com/en/enterprise-cloud@latest/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository). Accessed 2026-08-29. Authoritative server-side policy and evaluation mechanism.
3. [Graphite — Merge Queue Optimizations](https://graphite.com/docs/merge-queue-optimizations). Accessed 2026-08-29. Official description and vendor-reported measurements for stack-aware speculative CI.
4. [Mergify — Merge Queue Batches](https://docs.mergify.com/merge-queue/batches/). Accessed 2026-08-29. Official batching, failure isolation, and anti-flake mechanics.
5. [Uber — CI at Scale: Lean, Green, and Fast](https://arxiv.org/abs/2501.03440). 2025; accessed 2026-08-29. Primary report of SubmitQueue’s deployed resource and latency improvements.
6. [Chromium — Commit Queue](https://chromium.googlesource.com/chromium/src/+/119.0.6045.105/docs/infra/cq.md). Accessed 2026-08-29. Project-owned CQ admission requirements and latency targets.
7. [Google Research — Speculative Testing at Google with Transition Prediction](https://research.google/pubs/speculative-testing-at-google-with-transition-prediction/). 2025; accessed 2026-08-29. Primary production study over 120 billion test-cycle pairs.
8. [Google Research — Flake Aware Culprit Finding](https://research.google/pubs/flake-aware-culprit-finding/). 2023; accessed 2026-08-29. Primary large-scale study of probabilistic culprit identification under flaky tests.
9. [Nx — Run Only Tasks Affected by a PR](https://nx.dev/docs/features/ci-features/affected). Accessed 2026-08-29. Official dependency-graph and lockfile-aware test-selection mechanism.
10. [Bazel — Remote Caching](https://bazel.build/remote/caching). Accessed 2026-08-29. Authoritative content-addressed action-cache model.
11. [Meta Engineering — Sapling](https://engineering.fb.com/2022/11/15/open-source/sapling-source-control-scalable/). 2022-11-15; accessed 2026-08-29. Primary description of mutation-aware stacks at Meta scale.
12. [Rust Forge — Bors](https://forge.rust-lang.org/infra/docs/bors.html). Accessed 2026-08-29. Official infrastructure documentation for Rust’s landing bot.
13. [Journal of Systems and Software — Detecting semantic conflicts with unit tests](https://www.sciencedirect.com/science/article/pii/S0164121224001158). 2024; accessed 2026-08-29. Peer-reviewed evaluation of test-backed semantic-conflict detection.
14. [Google Cloud — Announcing the 2025 DORA Report](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report). 2025; accessed 2026-08-29. Official delivery-performance research framing throughput and stability together.