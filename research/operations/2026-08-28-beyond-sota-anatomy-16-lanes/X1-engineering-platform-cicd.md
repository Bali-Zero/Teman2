---
date: 2026-08-28
domain: operations
part: X1 engineering-platform-cicd
scope: CI/CD workflows, merge queue + Merge-OS, agent PR contract, evidence packs, required checks, pre-push gate, lint/scar gates, worktree broker, deploy paths, scripts sprawl
sources:
  - https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report
  - https://dora.dev/insights/dora-2025-year-in-review/
  - https://github.blog/engineering/engineering-principles/how-github-uses-merge-queue-to-ship-hundreds-of-changes-every-day/
  - https://dl.acm.org/doi/pdf/10.1145/3302424.3303970
  - https://www.uber.com/ca/en/blog/slashing-ci-costs-at-uber/
  - https://engineering.fb.com/2020/12/10/developer-tools/probabilistic-flakiness/
  - https://develocity.ai/blog/a-pragmatists-guide-to-flaky-test-management/
  - https://mergify.com/blog/when-to-outgrow-github-merge-queue
  - https://www.aviator.co/blog/merge-queues-for-large-monorepos/
  - https://github.blog/security/supply-chain-security/slsa-3-compliance-with-github-actions/
  - https://argo-rollouts.readthedocs.io/en/stable/features/analysis/
  - https://launchdarkly.com/blog/elite-performance-with-trunk-based-development/
  - https://grafana.com/blog/ci-cd-observability-a-rich-new-opportunity-for-opentelemetry/
  - https://buildkite.com/docs/pipelines/best-practices/monitoring-and-observability
status: DONE
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# X1 — Engineering Platform / CI/CD

## Anatomy (as measured)

All paths relative to the pinned worktree at `origin/main` `11a3c89a2e`. Every count below was measured with Glob/Grep/Read in this session.

### Workflow inventory

`.github/workflows/` holds **104 `.yml` workflows** (106 directory entries: plus `catE-paid-anthropic-baseline.txt`, a data file, and `ai-pr-review.yml.disabled-2026-08-20-zero-value-ci-trust-gate`, a deliberately disabled workflow). By purpose:

- **Test executors** (~20): `tests.yml` (2,413 lines — backend/frontend/E2E), plus per-organ suites (`wr2-queue-tests.yml`, `s7-yield-dispatch-tests.yml`, `vercel-autopromote-tests.yml`, `worker-plane-review-tests.yml`, `intel-router-tests.yml`, `contract-tests.yml`, `p3-sandbox-gates.yml`, …).
- **Meta-gates / gate-integrity** (~10): `verify-the-verifiers.yml` (152 lines, isolated-runner meta-verifier with sha256 integrity of the gate files themselves), `immune-enforcement.yml` (1,131 lines), `merge-gate-integrity-watch.yml`, `harness-floor.yml` (1,017 lines), `guard-conformance.yml`, `organ-conformance.yml`, `hook-innocence-gate.yml`, `main-red-breaker.yml`, `main-push-failure-watch.yml`, `watcher-coverage.yml`.
- **Scar-class regression pins** (6): `catA-channel-count-pin.yml` … `catF-wa-bridge-drift.yml` — each pins a cured incident class permanently red-on-regression.
- **Cron/observability** (14): `cron-*.yml` — cert monitor, Fly watcher/restart-detector/cost-alert, LLM credit sentinel, Sentry quota, notifier suites.
- **Lint gates** (~12): `actionlint.yml` (required), `lint-migration-*.yml`, `lint-cross-import.yml`, `token-lint.yml`, `prettier-changed-files.yml`, `asyncpg-lint.yml`, etc.
- **Security/supply-chain** (5): `security.yml` (CodeQL js+py, both required), `semgrep.yml` (the filename lies — its `name:` is "SAST — Bandit + ESLint Security"; Semgrep itself is not run), `sbom.yml` (SPDX/CycloneDX on push to main), `fly-secrets-check.yml`, Detect Secrets.
- **Deploy** (2 paths): `fly-deploy.yml` (backend), Vercel auto-deploy + `mini.vercel_autopromote` organ (below).
- **Adversarial-review enforcement**: `adversarial-review-gate.yml` (required R1 gate).

### Required-check topology

`infra/required.d/contexts.json` (regenerated 2026-08-27 via `scripts/ci/snapshot_required_contexts.py`) declares **11 required contexts** on main: Backend Tests, CodeQL ×2, E2E Playwright, guard-conformance, organ-conformance, Frontend Tests, Harness floor recompute, R1 adversarial gate, actionlint, immune-enforcement `antidotes`. This reflects the 2026-08-26 owner ruling that cut required contexts 27→11. An internal contradiction was left behind: `infra/required.d/integration-branch-minimum-contexts.json` (same `generated_at: 2026-08-27`) still says "27 contexts total; full list mirrored in infra/required.d/contexts.json" — the mirror now holds 11. That file also documents a verified structural quirk: main's required checks live in **classic branch protection**, while ruleset 19779175 carries only the `merge_queue` rule — an integration branch cannot "inherit" required checks and needs its own ruleset.

Required checks deliberately avoid `paths:` filters (`adversarial-review-gate.yml:12`: "A path-filtered required check never reports on PRs outside its paths, which leaves them stuck at 'Expected — waiting for status' forever") — the skip→success sentinel pattern is applied repo-wide (e.g. `verify-the-verifiers.yml:9-17`).

### Merge-queue mechanics

Three cooperating layers:

1. **GitHub merge queue** (ruleset `merge-queue-main`) + classic branch protection.
2. **`scripts/mq.sh`** (363 lines) — arm/watch/requeue/dequeue/handoff verbs. Its header codifies blood-bought rules: every `gh` rc captured errexit-immune (W101), `gh` output judged by content never exit code (W104 — "`gh pr checks` returns 0/1/8 inconsistently … 0 was returned with pending checks present"), never pipe an rc-bearing command through `tail` (W97). `mq arm` records head SHA; `mq watch` enforces no-push-after-arm.
3. **`scripts/merge_train.py`** — LaunchAgent-driven coordinator (~180s tick) with progress-semantics state file and zombie self-repair. Note: it hardcodes `REPO = "Balizero1987/Teman2"` (line 35) while `mq.sh:40` and `scripts/ci/queue_rearm.sh:34` default to `Bali-Zero/Teman2` — one of the two slugs is stale (unverified live which; the org migration left a split-brain pin).

`merge-queue-watch.yml` polls GraphQL for queue ejections because the `merge_group` `destroyed` webhook action is not delivered to Actions workflows (verified against GitHub docs per its own header) — so ejection detection is poll-based with two alert classes (EJECTED-WITHOUT-MERGE, ARMED-BUT-STUCK >30min).

### Evidence packs + gear floor

`scripts/evidence_pack_lint.py` (122KB) enforces the Evidence Pack contract: receipts `{claim, cmd, exit, ts, seat}` (non-empty on Gear 3), mandatory `dissent` (non-empty on Gear 3, entries validated with `status∈{CONFIRMED,PLAUSIBLE,RETRACTED}`), `pii_scan == "clean"`, ≤30k approx-tokens on raw bytes pre-parse, repo-relative `brief_ref`, and **gear ≥ deterministic floor** computed from the changed-file set (hot-zone paths → floor 3; the S1 size term via `--numstat-file` → floor 2; everything else floors at 1). The floor consumes `scripts/ci/hotzone_changed_files.sh` output — one source of truth for "what did this PR touch", never a two-dot diff (W102).

**Verified live defect**: `harness-floor.yml` stages exactly two files into the synthetic CI tree — line 909 `git show "$HEAD_SHA:${PACK_PATH}" > /tmp/evidence-check/evidence/pack.yml`, line 910 `cp /tmp/brief.yml /tmp/evidence-check/evidence/brief.yml`. But R9 (`check_council_run_gear3`, `evidence_pack_lint.py:1550`) resolves `council_run:` relative to the pack's directory (`:1519`) and returns an empty seat-set when the journal is absent (`:1522`). The journal is never staged, so in CI the quorum check can never pass. Today that is a NOTICE; the enforcement date is **2026-09-02** (`:151`, `:1375`), after which **every Gear-3 PR fails the required "Harness floor recompute" context by construction**. Confirmed on disk.

### Guard/scar-gate lints

- `infra/guard-conformance/registry.json`: **14 registered guard surfaces**; each guard entry carries scar refs plus named guilt AND innocence tests (e.g. `_guard_property_zoning_reply` → scars W68/W68b, 1 guilt + 4 innocence tests). `check_guard_conformance.py` fails CI for a censused guard missing either.
- `infra/scar-gates/`: MANIFEST + 2 executable scar tests (W82, home-fork live-vs-tracked).
- `scripts/lint_home_fork.py` (34KB): sha256-compares live HOME-executed copies against tracked versions. `infra/home-fork/declared-pairs.json` holds **167 declared pairs** (the injected `cicatrix-superscar.md` still says 97 — the doctrine file is behind the registry it describes); `--discover` parses `~/Library/LaunchAgents/*.plist` for undeclared payloads; exit codes 1|2|4.
- `scripts/docs_sync.py` (22KB): DOCSYNC pointer blocks in README/INDEX; `--check --changed-files-from` gives diff-local CI mode (the W86 cure: a stale global count no longer rejects an innocent PR).
- `infra/merge-os/critical-floor.d/`: 9 YAML invariant declarations (auth, deploy-health, embedding dims, gate-verifiers, migrations, pricing, RAG abstention, security boundaries, startup import chain). `infra/merge-os/quarantine.d/` exists with a SCHEMA.md and **zero entries** — a flaky-quarantine mechanism designed but never used.

### Test sharding + selective testing

- **Sharding** (`tests.yml:502-800`, S11 2026-08-23): the single backend job measured 797s of a 1,068s run (74.6%) in its unit-test step; cure is a 3-shard matrix (`shard: [1, 2, 3]`, `fail-fast: false` deliberately) with `scripts/ci/shard_tests.py` as single source of both partition and coverage proof: the fan-in re-derives the corpus and refuses unless consumed chunks are pairwise disjoint AND cover it exactly, compared against uploaded artifacts, "never against a recomputation of itself — a guard that only checks its own arithmetic is a tautology".
- **Selective testing** (`scripts/ci/impact_map.py`): static Python import-graph selection, backend tree only, **PR lane only** — the `merge_group` lane deliberately always runs the full suite, so a wrong impact map costs a slow PR run, never a missed regression. `conftest.py` changes select the whole subtree. Both classifiers are extracted from BASE_SHA by a trusted step so a malicious PR cannot under-select its own regression's tests.
- **Mutation testing** (`p1s2-mutation-incremental.yml`): incremental AST-diff mutation with hidden canary mutants — a surviving frozen canary means the suite is too weak or gamed. Runs on PR and push-to-main.

### Pre-push / pre-commit (husky)

`.husky/pre-push` resolves its classifier, suite lock, and tip-drift verifier from a **trust root** (`NUZ_PREPUSH_TRUST_ROOT`, pinned bundle from reviewed main for the unattended autofix runner) so a broken branch cannot supply the guards governing its own push. `scripts/quickcheck.sh` runs advisory-only with `|| true` load-bearing under `sh -e` (W101 decapitation scar). `.husky/pre-commit` carries the cicatrix auto-archive and a PII gate whose enumeration is first-parent-aware (measured 2026-07-30: a 12-file merge enumerated 12, authored 0).

### Deploy pipeline

- **Fly** (`fly-deploy.yml`): push-to-main, path-filtered with doc-class exclusions that deliberately keep runtime-read markdown deployable; pre-deploy gate with a real Postgres service container; `concurrency: fly-deploy, cancel-in-progress: false`.
- **Vercel**: the `commandForIgnoringBuildStep` payload is tracked in-repo (`scripts/ci/vercel_ignore_build_step.sh`) after the 2026-07-29 incident — the dashboard field invoked a script not yet on main, bash exited 127, and since any exit ≠0/1 fails the deployment, 9 deployments went to ERROR in 30 minutes. The wrapper normalizes all failures to exit 1; a test asserts its ≤256-char length and behavior. Promotion to production is a cron organ (`mini.vercel_autopromote`) with its own CI suite.

### Dead / theater / broken (measured)

1. **`test_auto_merge_whitelist.py` runs nowhere blocking.** `grep -rln auto_merge_whitelist .github/workflows/` returns nothing (rc=1). The only path that touches it is `scripts-tests-sweep.yml`, explicitly "report-only, non-blocking" (`continue-on-error: true`) over the 235 `test_*.py` files in `scripts/tests/`. The reported 24/73 red on main is consistent with this (count not re-run — test execution out of scope). The enforcement workflow `auto-merge-whitelist.yml` is live and CODEOWNERS-protected, but its test corpus is unenforced — branch-protection behavior is effectively unmeasured.
2. **Layer-2 AI PR review is dead**: `ai-pr-review.yml.disabled-…` — ~100 runs, every one failed a CI workspace-trust gate before reaching the model, zero comments posted. Honestly disabled with re-enable steps in its header (good hygiene; many orgs leave such theater running).
3. **The council_run staging defect** (above) is a time bomb dated 2026-09-02 for all Gear-3 PRs.
4. **Doctrine drift**: superscar says 97 home-fork pairs, the registry holds 167; the integration-contexts doc says 27 required, the snapshot holds 11; `merge_train.py` pins a repo slug that disagrees with `mq.sh`.
5. **No DORA-class delivery metrics exist** — no lead-time, deploy-frequency, MTTR, or change-failure-rate instrumentation anywhere in `scripts/` or workflows (grep: only false positives). The one delivery number that exists is anecdotal (PR #4547: 14 commits, 11 adversarial rounds, ~6h for a 1-file fix; 27 of 200 commits on main 2026-08-20..22 existed only to correct a prior PR's claim).

## Honest state vs. SOTA

**Genuinely ahead of industry practice** — the adversarial-gate culture is machine-enforced, not aspirational: generator≠grader is a required check (R1); a guard cannot exist without proving guilt AND innocence (registry-driven CI); the verifiers are themselves verified on an isolated runner with sha256 integrity; mutation canaries detect gamed suites; classifiers are extracted from BASE_SHA so a PR cannot weaken its own test selection; the queue is nursed by a poll-based ejection watcher that GitHub's own event model cannot provide. Most industry CI — including at large shops — trusts its own head checkout and its own test suite's honesty. This repo structurally does not, and that skepticism is its single most SOTA-exceeding trait.

**At rough parity with SOTA**: merge-queue discipline (GitHub merge queue + arm/watch tooling ≈ small-scale GitHub/Uber practice); two-lane test economics (selective PR lane, exhaustive merge-group lane — exactly the safe shape Mergify sells as "two-phase CI"); sharding with coverage proof; supply-chain basics (SBOM, CodeQL, actionlint, SHA-pinned actions, secret scanning).

**Below SOTA**: (1) **no delivery measurement at all** — the system measures gate integrity obsessively and delivery performance never; DORA's five keys (now including rework rate, the exact disease measured by hand as 27/200) are uninstrumented; (2) **no flaky-test system** — quarantine.d exists empty, no retry policy, no flake scoring, while a 3-shard suite at this scale mathematically guarantees flake pain; (3) **no build/dependency caching strategy** beyond pip cache — 269s of non-test setup is on every shard's critical path; (4) **no progressive delivery** — Fly deploy is rolling all-at-once, release=deploy, and the one feature-flag mechanism in use (env vars) produced its own scar (same flag name on two platforms, independently set); (5) **no provenance/attestation** — SBOM is generated but nothing signs or verifies what actually ships; (6) **CI observability is alert-only** — red-breaker names a failing job, but nobody can answer "what is p95 queue-to-merge time this month, and is it worse than last month".

The DORA 2025 finding is this repo in miniature: AI multiplies individual throughput (195 merged PRs in ~3 days) while the org-level constraint moves to review/verification — here the constraint became so dominant that a 1-file fix cost 11 adversarial rounds. The gates are world-class; the *cost of the gates* is unmeasured.

## Deep research: the world's best

**1. DORA 2025 — measure delivery, not activity.** The 2025 DORA report (Google Cloud) extends the four keys (deployment frequency, lead time, change failure rate, MTTR) with a fifth, **rework rate**, and its central AI-era finding: AI assistance lifts individual output (~21% more tasks, ~98% more PRs merged) while organizational delivery metrics stay flat, because review and integration become the bottleneck — "AI amplifies what's already there". The prescription is platform quality and workflow clarity, measured continuously. ([announcement](https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report), [year in review](https://dora.dev/insights/dora-2025-year-in-review/))

**2. Merge queues at scale — GitHub and Uber.** GitHub's own monorepo ships ~2,500 PRs/month from 500+ engineers through merge queue; groups of up to 30 PRs are built together, conflicting PRs are auto-ejected and groups re-form, and the rollout cut average wait-to-ship 33% ([github.blog](https://github.blog/engineering/engineering-principles/how-github-uses-merge-queue-to-ship-hundreds-of-changes-every-day/)). The theoretical ceiling is Uber's SubmitQueue ("Keeping Master Green at Scale", EuroSys'19): a **speculation tree** over pending changes with a **conflict analyzer** that prunes it so independent changes build concurrently, plus a probabilistic model choosing which speculative builds are worth running; later work bypasses full builds for provably independent large diffs ([paper](https://dl.acm.org/doi/pdf/10.1145/3302424.3303970), [Slashing CI Costs](https://www.uber.com/ca/en/blog/slashing-ci-costs-at-uber/)). Mergify and Aviator productize the middle ground: batching, scope-aware queues per monorepo area, and two-phase CI — light checks at PR, the expensive suite only in the queue ([Mergify](https://mergify.com/blog/when-to-outgrow-github-merge-queue), [Aviator](https://www.aviator.co/blog/merge-queues-for-large-monorepos/)).

**3. Trunk-based development.** DORA consistently identifies TBD — small batches, at-least-daily merges to a single trunk, no long-lived branches — as a top predictor of elite performance ([LaunchDarkly](https://launchdarkly.com/blog/elite-performance-with-trunk-based-development/)). Nuzantara already lives this (400-net-line PR contract, one-PR-one-concern, fresh-from-origin/main successor rule) — arguably more strictly than most elite teams.

**4. Selective testing + caching.** Nx's affected-graph and Bazel's content-addressed remote cache/execution are the reference: build/test only what the dependency graph says changed, share the cache between CI and every developer machine, and measured deployments skip ~80% of tasks. The key economics: cache keys derived from content hashes, not timestamps; cold CI becomes warm instantly. Google-style TAP presubmit selection is the same idea at planetary scale. Nuzantara's `impact_map.py` is the same family (static graph, fail-open to run-all), correctly scoped to the PR lane only.

**5. Flaky-test management.** Meta's **probabilistic flakiness score** reframes the question: all real tests are flaky to a degree; measure *how much*, per test, continuously, and alert when a test's reliability degrades ([engineering.fb.com](https://engineering.fb.com/2020/12/10/developer-tools/probabilistic-flakiness/)). Develocity's pragmatist playbook is the operational floor: exactly one retry (never chains), log every fail-then-pass event with timestamps to a database, quarantine tests that exceed a budget (target: flakes disrupt <1% of builds, from the formula flaky-failures/day = builds/day × flaky-count × p^(1+retries)), file ownership bugs before sprint planning, and require proof of cure before re-enablement ([develocity.ai](https://develocity.ai/blog/a-pragmatists-guide-to-flaky-test-management/)).

**6. Progressive delivery.** Argo Rollouts' canary + **AnalysisTemplate** pattern is the reference mechanism: shift traffic in steps, run metric queries (Prometheus etc.) as an automated verdict, auto-promote or auto-rollback — no human watching dashboards ([docs](https://argo-rollouts.readthedocs.io/en/stable/features/analysis/)). The companion principle: **decouple deploy from release** with feature flags, so exposure — not binaries — is what gets rolled back. Neither requires Kubernetes conceptually; the pattern is staged exposure + machine-readable health verdict + automatic reversal.

**7. CI observability.** The OpenTelemetry community is standardizing CI/CD semantic conventions — treat the pipeline as a production service with traces per run/job/step ([Grafana](https://grafana.com/blog/ci-cd-observability-a-rich-new-opportunity-for-opentelemetry/)); Buildkite exposes queue wait-time min/p50/p95/max as first-class metrics and treats "queue time high → add runners" as an operational signal ([Buildkite docs](https://buildkite.com/docs/pipelines/best-practices/monitoring-and-observability)). The pattern: per-run structured records, trend dashboards, and p95 (not mean) as the honest number.

**8. Supply-chain integrity.** SLSA defines build levels L0–L3; GitHub artifact attestations (built on sigstore keyless OIDC signing) give **SLSA Build L2 out of the box** — a signed provenance statement tying artifact → workflow run → commit; L3 requires the build definition to live in a reusable workflow outside the built repo; `slsa-verifier` closes the loop at deploy time ([github.blog SLSA-3 guide](https://github.blog/security/supply-chain-security/slsa-3-compliance-with-github-actions/)).

## Gap table

| Dimension | SOTA reference | Nuzantara today | Gap |
|---|---|---|---|
| Delivery metrics | DORA 5 keys, continuously computed | None; one hand-measured anecdote (27/200 rework) | **Large** |
| Merge queue | GitHub groups-of-30, Uber speculation+conflict-pruning | GitHub MQ + mq.sh/train/watcher; no batching insight | Small |
| Trunk-based dev | Small batches, daily merge | 400-line contract, arm-means-freeze | **None (ahead)** |
| Gate integrity | Rarely exists at all | verify-the-verifiers, guilt+innocence registry, mutation canaries, trusted classifier | **Ahead of SOTA** |
| Selective testing | Nx/Bazel affected graph, content-addressed | Static import graph, PR-lane only, fail-open | Small |
| Build caching | Bazel/Nx remote cache, CI+local shared | pip cache only; 269s setup on critical path | Medium |
| Flaky management | Meta PFS, Develocity retry+quarantine+budget | quarantine.d schema exists, empty; no retry policy, no flake log | **Large** |
| Progressive delivery | Argo canary+analysis, flags decouple release | Rolling deploy; env-var flags (two-platform scar) | **Large** |
| CI observability | OTel traces, p95 queue metrics | Alert-only (red-breaker, push-failure-watch); no trends | Medium |
| Supply chain | SLSA L2-L3 attestation + verify | SBOM + CodeQL + pinned actions; nothing signed/verified | Medium |
| Docs/doctrine drift | Registry-generated docs | DOCSYNC pointers good; superscar 97≠167, 27≠11 drift | Medium |

## Recommendations — reach SOTA

Each sized for a solo operator + agent fleet; no purchases required unless flagged in §Solo-operatore.

1. **P0 — Defuse the 2026-09-02 R9 bomb.** Stage the council journal into `/tmp/evidence-check/` (or resolve `council_run` against the real pack directory at HEAD) in `harness-floor.yml` before the NOTICE becomes FAIL. *Acceptance*: on/after 2026-09-02, a Gear-3 PR whose pack carries a valid ≥2-seat journal goes green on "Harness floor recompute" in CI, and one without quorum goes red — both proven by a fixture PR pair.
2. **P0 — Close the unenforced-test hole.** Either wire `scripts/tests/test_auto_merge_whitelist.py` (and the sweep's red set) into a blocking workflow, or move each red test into `infra/merge-os/quarantine.d/` with a schema-valid entry naming owner and cause. *Acceptance*: `grep -rln auto_merge_whitelist .github/workflows/` returns a blocking workflow; the sweep reports 0 unquarantined reds.
3. **P0 — Instrument DORA-5 for the agent fleet.** A nightly cron computing, from `gh api` + Fly/Vercel deploy history + git: deploy frequency, PR-open→live lead time, change failure rate (deploy rollbacks + main-red events), MTTR (red→green on main), and **rework rate** (commits whose subject/branch marks them as correcting a prior PR — the 27/200 measure, automated). Emit one JSON per week under `research/operations/metrics/`. *Acceptance*: 4 consecutive weekly JSONs exist and the weekly ledger cites their numbers.
4. **P1 — Arm the flaky-test system that already has a schema.** Adopt the Develocity floor: single pytest rerun (`--reruns 1` equivalent) in the PR lane only, log every fail-then-pass event to a JSONL artifact, populate `quarantine.d` when a test exceeds budget (flakes in >1% of runs), re-enable only with a green 20-run proof. *Acceptance*: quarantine.d non-empty or measured flake rate <1%; zero `gh run rerun` invocations on the queue without a named cause in the ledger.
5. **P1 — CI observability beyond alerts.** Per-run JSON (workflow, job, conclusion, queue-time, wall-time) appended by a `workflow_run`-triggered collector; weekly p50/p95 per required context. *Acceptance*: a month of data; the p95 of "Backend Tests" and of PR-open→merge is a number the ledger can quote and trend.
6. **P1 — SLSA L2 on the deploy artifact.** Add `actions/attest-build-provenance` to the Fly image build and verify the attestation in the deploy job before `fly deploy`. *Acceptance*: a deploy with a missing/invalid attestation fails closed; `gh attestation verify` passes on the shipped image digest.
7. **P2 — Cut the 269s setup tax.** Content-hash-keyed dependency cache (uv + `actions/cache` on the lockfile hash) shared across the 3 shards; consider a prebuilt test container. *Acceptance*: shard setup time halved from the measured 269s baseline, verified on 5 consecutive merge-group runs.
8. **P2 — One flag platform of record.** A single `infra/flags/` registry consumed by both Fly and Vercel surfaces (build-time injection), replacing per-platform env duplication (the `GARUDA_PUBLIC_ENABLED` scar). *Acceptance*: a lint fails any `os.environ`/`process.env` read of a flag name not present in the registry.

## Recommendations — beyond SOTA

1. **Claim-correction rate as a first-class metric (agent-native DORA).** Industry measures rework as code churn; this organism's real disease is *epistemic* rework — commits that exist only to correct a claim a previous session made (measured once by hand: 27/200). Automate its detection (fix-of chains, retracted-claims registry `infra/retracted-claims/` already exists as a surface) and publish it weekly next to DORA-5. No industry equivalent measures LLM-agent truthfulness decay; this repo is uniquely positioned to. *Acceptance*: weekly number, alert when >10%.
2. **Verification provenance (Evidence Packs as attestations).** Industry signs *build* provenance; nobody signs *review* provenance. Attach the Evidence Pack (receipts with cmd+exit+seat, dissent ledger) as a GitHub attestation on the merge commit via sigstore — making "who verified what, adversarially, with which seats" cryptographically bound to the artifact. *Acceptance*: `gh attestation verify` on a merge commit returns the pack digest; a PR merged without one is detectable by a single query.
3. **Immune-system health index (esiste≠armato as a number).** The #2 scar family keeps recurring because armedness is checked incident-by-incident. Generalize: a weekly job that cross-references every test file against the workflows that execute it, every registry count against the doctrine files that cite it (superscar 97-vs-167 class), every workflow against its last non-skipped run — and emits one scalar ("N gates exist, M are proven armed") plus the delta. *Acceptance*: the 5 dead/theater findings in this report's anatomy section would all have been auto-detected; re-running the index after cures shows the count fall.
4. **Scar-aware speculative queue.** The queue watcher already detects ejections; main-red-breaker already distinguishes consecutive same-job failure from one-off noise. Fuse them: on ejection, auto-classify flake-vs-real using the consecutive-failure signal and the flake log (rec. 4 above), auto-requeue on flake-classification with the cause written to the ledger — an Uber-style "keep master green" reflex at solo-operator scale. *Acceptance*: ≥80% of ejections get an auto-classification; zero blind requeues.

## §Meta-pattern

The system's structural disease is **asymmetric proprioception**: world-class at verifying *correctness* (gates, guards, meta-verifiers — it verifies the verifiers), absent at measuring *delivery* (no DORA, no flake rate, no queue p95, no cost-of-gate number). Every instance of the program-wide meta-malattia — "the written/armed/announced artifact IS the thing in force" — found here fits this frame: the sweep that reports but never blocks, the quarantine schema with zero entries, the superscar count frozen at 97 while the registry grew to 167, the "27 contexts" doc beside an 11-context snapshot, the enforcement date nobody's CI can survive. The repo already invented the antidote (registry + conformance lint + guilt/innocence proof); it has simply never pointed that antidote at its own delivery pipeline and doctrine numbers.

## §Solo-operatore

Decisions only Zero can take:

1. **The 2026-09-02 R9 enforcement date** — keep (forces the fix now), postpone, or drop the council-quorum requirement. Gate-strictness is a business risk call (Legge 5).
2. **Required-context set size** — the 27→11 cut was ruled without delivery data; once DORA-5 exists (rec. 3), re-ruling with change-failure-rate evidence is a Zero decision, not a session's.
3. **Spend**: everything recommended runs on free GitHub Actions + existing subscriptions. Paid options deliberately NOT recommended: Depot/Namespace runners (~$20-200/mo, would halve wall-times), Mergify/Aviator/Trunk.io (queue features GitHub already provides at this scale), Develocity (enterprise-priced). Any of these requires Zero's explicit spend authorization per the cost constraint.
4. **GitHub org GUI actions**: enabling artifact attestations, editing rulesets/branch protection, creating the integration-branch ruleset — all `operator[gui]`/`operator[control-plane]` per doctrine.
5. **Progressive-delivery posture for client-facing surfaces**: staged exposure means a brief window where two versions answer clients — acceptable for a visa-services business or not is a Legge-5 call.

## Sources

1. Google Cloud — Announcing the 2025 DORA Report: https://cloud.google.com/blog/products/ai-machine-learning/announcing-the-2025-dora-report
2. DORA — 2025 Year in Review: https://dora.dev/insights/dora-2025-year-in-review/
3. GitHub Engineering — How GitHub uses merge queue: https://github.blog/engineering/engineering-principles/how-github-uses-merge-queue-to-ship-hundreds-of-changes-every-day/
4. Ananthanarayanan et al. — Keeping Master Green at Scale (Uber SubmitQueue, EuroSys'19): https://dl.acm.org/doi/pdf/10.1145/3302424.3303970
5. Uber Engineering — Slashing CI Costs: https://www.uber.com/ca/en/blog/slashing-ci-costs-at-uber/
6. Meta Engineering — Probabilistic flakiness: How do you test your tests?: https://engineering.fb.com/2020/12/10/developer-tools/probabilistic-flakiness/
7. Develocity — A Pragmatist's Guide to Flaky Test Management: https://develocity.ai/blog/a-pragmatists-guide-to-flaky-test-management/
8. Mergify — When to Outgrow GitHub's Merge Queue: https://mergify.com/blog/when-to-outgrow-github-merge-queue
9. Aviator — Merge Queues for Large Monorepos: https://www.aviator.co/blog/merge-queues-for-large-monorepos/
10. GitHub Blog — Achieving SLSA 3 Compliance with GitHub Actions and Sigstore: https://github.blog/security/supply-chain-security/slsa-3-compliance-with-github-actions/
11. Argo Rollouts — Analysis & Progressive Delivery: https://argo-rollouts.readthedocs.io/en/stable/features/analysis/
12. LaunchDarkly — Elite Performance with Trunk-based Development: https://launchdarkly.com/blog/elite-performance-with-trunk-based-development/
13. Grafana Labs — CI/CD observability with OpenTelemetry: https://grafana.com/blog/ci-cd-observability-a-rich-new-opportunity-for-opentelemetry/
14. Buildkite — Monitoring and observability best practices: https://buildkite.com/docs/pipelines/best-practices/monitoring-and-observability
