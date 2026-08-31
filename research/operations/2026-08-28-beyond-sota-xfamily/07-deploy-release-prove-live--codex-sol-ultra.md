---
panel: beyond-sota-xfamily
lane: 07-deploy-release-prove-live
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T18:51:54Z
finished: 2026-08-28T19:00:16Z
duration_s: 502
exit: 0
words: 5220
prompt_sha256_16: 2a7b676ff7344c1a
prompt_chars: 18233
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 7/13 — Deploy, release & prove-live
model: OpenAI GPT-5.6 sol, reasoning effort ULTRA (pinned lane)
sources: 12
repo_files_verified: 21
status: complete
---

## 0. TL;DR

Nuzantara is **AHEAD in release doctrine but BEHIND in mechanically proving delivery**: “merged ≠ live” and content-level PROVE-LIVE are explicit laws, yet critical releases can still terminate at HTTP 200, a deployment status, or one platform’s flag state.

The largest gap is the absence of one executable release contract binding commit, Fly image, every Fly process group, migrations, Vercel production content, both flag copies, and the user/business journey.

Top move 1: create a consumer-map-driven Release Evidence Graph that refuses “done” until every declared consumer returns content evidence.

Top move 2: replace generic `/health` gating with same-image process-group proofs plus cache-busted browser and transaction probes.

Top move 3: make Fly/Vercel flag activation a two-phase, owner-authorized release transaction with automatic paired rollback.

The documented deploy procedure still contains nine operator actions; `PENDING-ARMS.md` has 123 lines containing “deploy,” and the monthly restore drill covers PostgreSQL restoration but not a complete service cutover.

Against five repository-visible public defect classes, an ordinary browser synthetic would have caught 4/5; adding explicit visual/contract assertions raises this to 5/5.

## 1. How Nuzantara does it today

### 1.1 The doctrine is unusually explicit

A session owns the lifecycle through REVIEW → MERGE → ARM → DEPLOY → PROVE-LIVE on every consumer surface. It must construct the consumer map before declaring completion; producer success alone is insufficient (`CLAUDE.md:70-72`). The master operating loop repeats that SHIP+ARM occurs only from merged `main`, while PROVE-LIVE must inspect the actual public domain or downstream state, read returned content rather than an exit code, and stop or roll back on failure (`.claude/skills/modus/SKILL.md:80-81`).

The factory doctrine goes further:

- “Done” means a customer journey works in production and produces its business outcome.
- Release should proceed dark, then internally, then to 5%, then 100%.
- Database changes must be backward-compatible during rollout.
- Five-percent exposure requires real-user evidence.
- A synthetic sandbox purchase and refund should run every 10–15 minutes.
- Missing the business invariant for 15 minutes should turn the feature off and notify the owner.

These are enforceable acceptance concepts, not generic aspirations (`docs/factory/ASSEMBLY-LINE.md`).

The GARUDA mandate applies that model concretely: code is to be deployed with `GARUDA_PUBLIC_ENABLED` off, then separately armed; it calls for five real buyers at 5%, a daily or 15-minute synthetic journey, 48 hours green before completion, and owner approval for the business decisions (`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`).

### 1.2 Backend release mechanics

The main Fly workflow is substantially stronger than a basic “deploy on push” script:

- Changes on `main` affecting backend surfaces trigger `.github/workflows/fly-deploy.yml`.
- Deployment concurrency is serialized rather than canceling an in-flight release.
- Pre-deploy validation runs before a rolling Fly deployment.
- The build uses the repository root as Docker context, consistent with the verified presence of `apps/backend-rag/Dockerfile`.
- Migrations are not assumed to run from an arbitrary machine. The workflow first uses the existing runtime image, then after deployment pins a machine in the `api` process group carrying the newly deployed image and executes the SQL-v2 migration runner there.
- That explicit `api` selection exists because the `rag` image/process lacks a required database dependency.
- Several legacy Python migrations are subsequently invoked explicitly.
- A failed post-deploy health gate causes the previous image to be redeployed.

This is valuable provenance and runtime-parity work (`.github/workflows/fly-deploy.yml`).

However, the ordering contains a release hazard: the new image is rolled out before fresh-image migrations and their ledger/schema proof complete. A post-deploy migration can therefore fail after new application code is already serving. The workflow comments correctly acknowledge that image rollback does not roll back the database and may leave old code against a new or partially changed schema (`.github/workflows/fly-deploy.yml`).

Its hard production gate remains a content check on the global `/health` response for `"healthy"`. The RAG smoke is informational rather than a blocking consumer proof. This permits the exact split-brain class already recorded: the web/API surface can return 200 while a required worker process group is stopped (`.github/workflows/fly-deploy.yml`; `.claude/rules/cicatrix-superscar.md`).

Credential checking is present but narrower than release proof. A weekly workflow verifies that Fly authentication succeeds; it does not establish that the credential addresses the intended application, process group, deployment, or runtime behavior (`.github/workflows/fly-secrets-check.yml`).

### 1.3 Frontend delivery

The frontend is configured as a Next.js Vercel application, with build/install commands in `apps/mouth/vercel.json`. No progressive-delivery or proof policy is declared there.

The repository has already reacted to a severe failure mode: `.github/workflows/frontend-live-sentinel.yml` records that commits accumulated while production continued serving old code, and later that a Vercel deployment could be `READY` while custom domains were stale. The sentinel now:

1. identifies the latest frontend-deploy-relevant commit;
2. queries a public health surface for its commit;
3. accepts production when the returned commit is the target or a descendant;
4. runs both after relevant pushes and on a schedule.

This is materially better than trusting the Vercel dashboard. It proves public-domain provenance, but not that a feature’s content or journey works. It also does not implement the memory-referenced cache-busting `?dpl=` probe. Consequently, this snapshot cannot confirm enforcement of the rule about a frontend change skipped between unrelated backend commits. A cache-busted feature signature remains necessary even when the returned production SHA is acceptable (`.github/workflows/frontend-live-sentinel.yml`).

`.github/workflows/vercel-autopromote-tests.yml` tests the autopromotion tooling itself; it is not proof that a particular production journey was delivered.

### 1.4 Split-brain recovery

The release organism has scar-driven defenses for Fly process groups:

- `.github/workflows/cron-fly-watcher.yml` records a prior period when workflow runs were red or ineffective while a RAG worker remained stopped and a consumer returned 503.
- `.github/workflows/cron-fly-restart-detector.yml` checks group-level state, not merely individual-machine restart events, and can force-start when a required group has no started member.

That is useful operational recovery, but it belongs after release. The deployment workflow itself still does not fail closed unless all required process groups run the intended image and complete a consumer-specific task. Release-time proof and after-release healing are therefore inconsistent.

### 1.5 Flags span two control planes

`.github/workflows/garuda-arm.yml` explicitly states that it arms only the backend Fly environment. The same logical flag must separately be configured on Vercel, and frontend/backend parsing historically accepted different literal forms. `.github/workflows/lint-garuda-environment-values.yml` now checks legal values and cross-language parity, which removes one class of drift.

The remaining problem is atomicity. The backend workflow can finish successfully while the frontend remains off, stale, or points to a build without the intended code. Its final probe checks generic service health, not flag behavior or the whole public journey (`.github/workflows/garuda-arm.yml`).

### 1.6 Manual burden and recovery coverage

The canonical deployment procedure in `CLAUDE.md:226-250` contains nine distinct operator actions before final reporting:

1. inspect backend changes;
2. enter and activate the backend environment;
3. probe the critical import chain;
4. run the core test set;
5. launch the rolling deployment from repository root;
6. wait for and query the public endpoint;
7. capture browser evidence;
8. visually check branding and broken elements;
9. fix and redeploy if the QA gate fails.

The final written report is a tenth procedural step but not a deployment action.

Database restoration is exercised monthly through `.github/workflows/restore-drill.yml`: it selects a recent backup, restores it into an isolated PostgreSQL target, and runs validation queries. This is a real drill rather than a prose-only runbook. It does not exercise Fly image rollback, Vercel alias rollback, feature-flag convergence, application startup against the restored schema, or traffic cutover.

`docs/runbooks/synthetic-probe-cleanup.md` shows good discipline for tagging, identifying, and idempotently removing synthetic residue. It does not demonstrate that the mandated public purchase/refund probe exists for GARUDA.

The two external deploy skills named in the lane brief were outside the authorized snapshot and were not read. All conclusions above derive from repository-local doctrine, workflows, scars, plans, and history. No memory file or external dotfile was accessed.

## 2. Scars & ledger evidence in this area

### 2.1 Green control plane, dead consumer

Superscar family #2, **“Esiste != Armato,”** is the dominant release scar. Its `503-RAG` member states the failure directly: health returned 200 while the worker was stopped. The prescribed antidote is a real result, database heartbeat, or equivalent consumer evidence—not process existence (`.claude/rules/cicatrix-superscar.md`).

W87 supplies the same lesson at a different boundary: a PostgreSQL integration reported “Connected,” but the first identity-sensitive query failed. Connectivity and authentication UI state were not usability proof (`.claude/rules/cicatrix-scars.md`, W87).

This has recurred across at least four release boundaries:

- merged commit versus running public artifact;
- Vercel `READY` versus custom-domain content;
- Fly `/health` versus a live worker process group;
- successful flag mutation versus matching frontend/backend behavior.

### 2.2 The ledger remains deployment-heavy

A case-insensitive repository grep found **123 lines containing `deploy`** in `.claude/skills/modus/PENDING-ARMS.md`. This is a line count, not 123 unique open entries, because entries can span multiple lines. A broader release vocabulary matched 289 lines, confirming that deployment is not a marginal source of unfinished arming work.

Material ledger examples include:

- a Vercel integration gap that left shared frontend production stale for roughly 13 hours;
- a production deployment reaching `READY` without the intended custom-domain artifact;
- false stale detections when docs-only commits were treated as frontend deployment targets;
- an asynchronous consumer whose code SHA was live but whose scheduler execution could not be proven by `/health`;
- schema changes blocked because the runtime migration role did not own the required DDL capability;
- source-map upload failure that did not fail the enclosing build.

These are different symptoms of the same missing object: a release receipt composed from every consumer’s state (`.claude/skills/modus/PENDING-ARMS.md`).

### 2.3 The learning loop knows that exit zero lies

The amendments log records:

- an actual runtime binary invocation revealing a `KeyError` missed by unit tests, CI, and adversarial reviews;
- a probe needing exact entity matching rather than approximate success;
- producer logs being insufficient unless the downstream state changes;
- deployment/shared-resource operations needing serialization.

The repository has therefore learned the right epistemology; it has not yet embodied it as one release gate (`.claude/skills/modus/AMENDMENTS.md`).

### 2.4 Joint defects and synthetic coverage

`research/operations/2026-08-24-garuda-voa-the-defects-were-in-the-joint.md` found defects at the Python/TypeScript boundary despite 202 Python tests and 130 local TypeScript tests being green. Its conclusion is especially relevant to deployment: local correctness on both sides did not prove the assembled public surface.

The canonical memory document naming the “five measured public-surface defects” was unavailable by explicit access rule. I therefore do not present its contents as observed fact. Repository history exposes five representative public defect classes:

1. anonymous users forced into an expired-session path;
2. authenticated requests producing 401/network and error-reporting noise;
3. missing or broken public image assets;
4. CORS or dead third-party resources;
5. visible header/content contract drift.

A standard Playwright journey asserting navigation, network failures, console failures, and asset responses would catch classes 1–4: **4/5**. Adding a screenshot or DOM contract assertion catches class 5: **5/5**. A status-only probe catches at most the redirect, and may catch none if redirects are followed without asserting the destination.

### 2.5 Recovery is documented more broadly than it is exercised

| Recovery path | Documented or encoded | Exercised automatically |
|---|---:|---:|
| Redeploy previous Fly image | Yes | Only on workflow health failure |
| Database rollback | Explicitly not provided by image rollback | No general automatic reversal |
| PostgreSQL backup restore | Yes | Monthly |
| Restart absent Fly process group | Yes | Scheduled detector |
| Vercel production rollback/promotion | Platform-supported; no verified repo release drill | No |
| Paired Fly + Vercel flag-off | Backend action exists; frontend separate | No atomic drill |
| Full restored-service journey | Doctrine requires it | No verified drill |

The backend has one exercised data recovery path and one image recovery path, but no end-to-end recovery proof spanning data, both deployment platforms, flags, and the customer journey.

## 3. World SOTA survey

| System/practice | Primary source | Mechanism | Measured effect | Transferability |
|---|---|---|---|---|
| Google release engineering | [Google SRE Book](https://sre.google/sre-book/release-engineering/) | Reproducible artifacts, automated builds/deploys, unique build IDs, logged rollout steps | Publishes operating principles and release metrics, not one universal defect-reduction number | Directly applicable: immutable IDs and a release receipt should bind every Nuzantara consumer |
| Google canarying | [Google SRE Workbook](https://sre.google/workbook/canarying-releases/) | Control/canary comparison, limited population, time-bound evaluation, automatic integration into release | Notes that most incidents arise from binary/config pushes; no single percentage effect | Strong transfer: dark → internal → 5% → 100% already exists in doctrine |
| Amazon safe deployment | [AWS Builders’ Library announcement](https://aws.amazon.com/about-aws/whats-new/2020/06/new-abl-article-automating-safe-hands-off-deployments/) | Small waves, bake periods, automated alarms, rollback, hands-off release captain | AWS reports over 150 million deployments annually across its automated estate | Transfer mechanisms, not scale; Nuzantara needs deterministic gates because one owner cannot inspect every release |
| Netflix Kayenta | [Netflix TechBlog](https://netflixtechblog.com/automated-canary-analysis-at-netflix-with-kayenta-3260bc7acc69) | Compare canary/control metrics, score degradation, abort and route back to stable | Netflix reports higher deployment trust and developer productivity; no public universal rate | Use simple absolute and differential signals; full Kayenta infrastructure would be disproportionate |
| Argo Rollouts | [Official canary documentation](https://argo-rollouts.readthedocs.io/en/stable/features/canary/) | Declarative weights, pauses, analysis runs, header routing, automatic abort | No project-wide effect published | Do not import Kubernetes; copy its explicit state machine and abort semantics |
| Flagger | [Official project documentation](https://flagger.app/) | Progressive traffic shifting plus success-rate, latency, webhooks, automated promotion/rollback | No universal measured effect published | Its custom acceptance-test webhook maps directly to business-invariant and browser probes |
| OpenFeature | [Official evaluation API](https://openfeature.dev/docs/reference/concepts/evaluation-api/) | Vendor-neutral typed evaluation, provider abstraction, context, detailed result, fail-safe defaults | Standardization benefit; no quantified delivery effect | Useful semantic contract across Python and TypeScript; avoid adopting a paid flag control plane |
| Fly.io rolling deployment and rollback | [Official rollback guide](https://fly.io/docs/blueprints/rollback-guide/) | Redeploy a known image, rolling or immediate strategy, validate after rollback | No aggregate effect published | Directly applicable; crucial warning: image rollback does not reverse database state |
| Vercel promotion and rollback | [Official promotion documentation](https://vercel.com/docs/deployments/promoting-a-deployment) | Reassign production domains to an existing build for fast rollback; staged promotion available | No aggregate effect published | Suitable for frontend recovery, but environment changes require a rebuilt artifact |
| DORA delivery performance | [2024 report](https://dora.dev/research/2024/dora-report/2024-dora-accelerate-state-of-devops-report.pdf) | Measure lead time, deployment frequency, change failure, rework, failed-deployment recovery | 2024 elite cluster: on-demand deployment, <1-day lead time, 5% change-failure rate, <1-hour recovery | Establish Nuzantara’s missing release baseline before claiming improvement |
| Checkly synthetic monitoring | [Official synthetic overview](https://www.checklyhq.com/docs/detect/synthetic-monitoring/overview/) | API, multistep, and browser checks validating complete user workflows | No universal effect; mechanism targets MTTD and transaction correctness | Use local/CI Playwright rather than a new paid service; retain console/network/visual evidence |
| pgroll expand/contract | [Official repository](https://github.com/xataio/pgroll) | Concurrent old/new schema views, backfill, reversible expand/contract rollout | No universal effect; promises zero-downtime and instant schema rollback | Adopt the compatibility contract and verification ideas, not necessarily the tool—especially given RLS and ownership constraints |

### The most relevant lessons

**Google and Argo make rollout state explicit.** A release is not one command; it is a state machine with population, evaluation, pause, promotion, and abort. Nuzantara’s doctrine names these states but its two hosting platforms do not share one machine-readable rollout state.

**Netflix and Flagger compare behavior, not deployment metadata.** Nuzantara does not need a statistically elaborate Kayenta installation. A control/candidate comparison over error rate, latency, process-group task completion, and one business invariant would capture most value at solo-owner scale.

**AWS demonstrates the importance of unattended safety.** The owner does not review code and cannot manually validate nine steps repeatedly. The correct transfer is not more checklists but defaults that stop automatically and preserve a small blast radius.

**Fly and Vercel both provide fast artifact rollback, but neither coordinates the database or the other platform.** Their local success models create the exact joint defect Nuzantara experiences. Cross-platform correctness is an application responsibility.

**DORA supplies the missing outcome baseline.** Nuzantara counts scars and unfinished arms but does not yet compute release lead time, change-failure rate, rework rate, and failed-deployment recovery time from its own evidence.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Immutable backend provenance | **AT** | Root build context, image-aware post-deploy migration machine selection, serialized Fly deployment in `.github/workflows/fly-deploy.yml` |
| Consumer-map doctrine | **AHEAD** | Explicit “every consuming surface” and content-not-exit rules in `CLAUDE.md` and `.claude/skills/modus/SKILL.md`; surveyed platforms generally stop at service/application rollout |
| Consumer-map enforcement | **BEHIND** | No single manifest or receipt binds Fly, Vercel, database, flags, workers, and journey |
| Progressive exposure | **AHEAD in specification; BEHIND in execution** | Dark → internal → 5% → 100% plus business invariant in `docs/factory/ASSEMBLY-LINE.md`; no verified automated traffic/flag state machine |
| Fly rolling deployment | **AT** | Rolling releases and previous-image recovery are implemented |
| Fly process-group proof | **BEHIND** | `/health` can be 200 while a required worker is stopped; release workflow does not block on same-image group/task proof |
| Vercel public provenance | **AT** | Public commit sentinel is better than trusting build status; content-level feature and cache-busted proofs remain absent |
| Cross-platform feature flags | **BEHIND** | Backend and frontend copies are changed independently; lint checks values but not transaction convergence |
| Migration execution parity | **AHEAD** | Fresh image, runtime DSN, and explicit `api` process targeting avoid arbitrary runner assumptions |
| Migration release safety | **BEHIND** | Public image rollout precedes definitive fresh-image migration success; image rollback cannot reverse schema |
| Synthetic business probes | **AHEAD in doctrine; BEHIND in implementation** | Purchase/refund cadence and dead-man behavior are specified, but no verified GARUDA synthetic implementation exists |
| Rollback and restore | **AT for components; BEHIND end-to-end** | Fly image recovery and monthly PostgreSQL restore exist; full Vercel/Fly/DB/flag/journey recovery is unexercised |
| Release metrics | **BEHIND** | No evidence-derived DORA baseline or consumer-proof coverage rate |
| Public-surface QA | **AT manually; BEHIND automatically** | Browser QA is mandatory but remains part of the nine-action operator procedure |

## 5. Beyond-SOTA recommendations

### 1. Release Evidence Graph — impact 10 × confidence 9 / cost 5

**What:** Introduce a versioned consumer-map manifest. For each release it declares required nodes and proof predicates: Git SHA, Fly image, `api`/`rag`/other required process groups, migration-ledger head, Vercel production SHA, cache-busted feature signature, backend and frontend flag values, browser journey, and business-state delta. A release receipt is complete only when all mandatory nodes prove the same intended release.

**Why beyond SOTA:** None of the twelve surveyed systems composes deployment provenance, database ledger, two independent flag planes, asynchronous consumers, browser evidence, and business outcome into one release graph. Nuzantara can because full-lifecycle sessions, the scar corpus, hooks, and the consumer-map doctrine already span these domains.

**Before → after:** no unified receipt and nine manual actions → ≥95% of declared consumers automatically proved within ten minutes; zero release completion claims with an unproved mandatory node; manual actions ≤3.

**Cost:** 32–48 engineering hours; flat-subscription LLM review only. **Gear:** 3.

**Risk/scar:** stale or overbroad manifests could create cron-theater or false blocking—families #2 and #9.

**Measurement:** emit node timestamps and results into one JSON receipt; compute proof coverage, commit-to-proven-live p50/p95, false-block rate, and escaped defect rate.

**Kill criterion:** abandon the graph abstraction if, after 20 releases, maintaining manifests consumes over 15 minutes per release or false-blocks exceed 5%; retain the underlying probes.

**First PR:** `feat(release): validate consumer-map manifests`; proposed `config/release-consumers.yaml`, `scripts/release_consumer_map.py`, focused tests; ≤400 net lines.

### 2. Same-image process-group and functional canary gate — impact 10 × confidence 10 / cost 3

**What:** Before promotion is accepted, enumerate required Fly process groups, prove at least one started machine in each runs the candidate image, then execute one process-specific function. The RAG proof must return a grounded sentinel result or durable downstream delta—not merely `/health`.

**Why beyond SOTA:** Argo and Flagger gate pods and metrics, but the surveyed material does not express “global health can be green while another process group is absent” as a first-class release graph condition. Nuzantara’s `503-RAG` scar supplies the exact invariant.

**Before → after:** one blocking generic health response and a nonblocking RAG smoke → 100% of required groups prove candidate image plus consumer function; recurrence of health=200/worker-stopped becomes a release failure.

**Cost:** 12–20 hours. **Gear:** 2.

**Risk/scar:** an unstable external dependency could block safe releases—families #2 and #5. Use a deterministic internal sentinel and bounded retries.

**Measurement:** per-release group/image matrix, functional proof duration, false-negative rate, and count of post-release missing-group incidents.

**Kill criterion:** replace a functional probe if it false-blocks over 2% of twenty releases; never fall back to global health alone.

**First PR:** `fix(deploy): block on required Fly process groups`; `.github/workflows/fly-deploy.yml`, one read-only probe script, tests; ≤300 net lines.

### 3. Two-phase cross-platform flag transaction — impact 9 × confidence 9 / cost 4

**What:** Treat one logical flag as a release transaction:

1. **Prepare:** confirm both production artifacts contain the feature, read both current flag states, validate legal values, and run dark probes.
2. **Commit:** after owner authorization, change both platforms.
3. **Verify:** query backend behavior and cache-busted frontend content.
4. **Abort:** if either proof fails, return both to the recorded safe state.

The receipt stores redacted state and artifact IDs, never credentials.

**Why beyond SOTA:** OpenFeature standardizes evaluation inside applications but not atomic activation across Fly and Vercel. The composition of owner consent, two control planes, artifact provenance, paired behavioral verification, and paired rollback is absent from the surveyed systems.

**Before → after:** two independent operations with possible split state → 100% convergent paired transitions or automatic paired abort within two minutes.

**Cost:** 20–32 hours. **Gear:** 3.

**Risk/scar:** partial rollback or credentials addressing the wrong project—families #2, #9, and #10.

**Measurement:** flag convergence latency, partial-state seconds, behavioral proof rate, and rollback success.

**Kill criterion:** do not arm automatically if the platform APIs cannot supply unambiguous project and deployment identity; retain a dry-run verifier and require owner GUI action.

**First PR:** `feat(release): add dual-platform flag preflight`; read-only state verifier plus schema tests, no mutation; ≤400 net lines.

### 4. Schema-before-exposure choreography — impact 9 × confidence 9 / cost 5

**What:** Preserve the strong runtime-image migration rule but change release order: deploy the candidate dark/nonpublic, execute expand-phase migrations from its `api` runtime, prove migration ledger and schema invariants, run candidate probes, then admit traffic. Contract-phase/destructive migrations occur only after old code is absent and require a separate release.

**Why beyond SOTA:** Expand/contract is known SOTA. The beyond-SOTA composition is binding it to Nuzantara’s runtime-role identity, ledger ownership, candidate image, consumer graph, and automatic refusal to expose traffic before schema proof.

**Before → after:** candidate code can serve before post-deploy migration completion → zero releases expose candidate traffic before ledger/schema proof; 100% of migrations classified expand or contract; zero image rollbacks incompatible with current schema.

**Cost:** 32–50 hours. **Gear:** 3.

**Risk/scar:** prolonged dual-schema state or an incorrectly classified DDL operation—families #3 and #9.

**Measurement:** exposure-before-schema violations, lock duration, migration failure point, old/new image compatibility tests, and rollback drill outcomes.

**Kill criterion:** if Fly cannot isolate candidate traffic without operational fragility, retain global dark flags and require additive migrations before image deployment rather than inventing an unsafe pseudo-canary.

**First PR:** `feat(migrations): classify expand versus contract`; migration metadata validator and tests only; ≤350 net lines.

### 5. Four-channel synthetic journey — impact 9 × confidence 10 / cost 3

**What:** Run one production-safe journey with four assertion channels: HTTP/DOM outcome, console errors, failed network/assets, and visual/contract snapshot. For transactional flows, use a tagged sandbox purchase and compensating refund/cleanup. Bind every run to its release receipt.

**Why beyond SOTA:** Checkly provides these test types, but the novel composition is release-bound proof plus business-state delta, residue cleanup, two-platform flag confirmation, and scar-derived assertions maintained by the same lifecycle session.

**Before → after:** status/commit probes catch at most 0–1 of five reconstructed defect classes → standard journey 4/5; four-channel journey 5/5; release-time detection under ten minutes.

**Cost:** 16–24 hours per critical journey; no paid monitoring API required. **Gear:** 2.

**Risk/scar:** synthetic residue, accidental real transaction, brittle visual snapshots—families #3 and #5.

**Measurement:** seeded-defect catch rate, run duration, false alarms, cleanup completeness, and escaped public defects.

**Kill criterion:** remove or redesign an assertion if its false-positive rate exceeds 3% over 30 runs; disable any monetary probe until owner-approved isolation and refund limits exist.

**First PR:** `test(live): add cache-busted anonymous funnel probe`; Playwright test and redacted artifact schema; ≤350 net lines.

### 6. Full recovery game day — impact 8 × confidence 9 / cost 4

**What:** Quarterly, exercise one coherent recovery: previous Fly image, Vercel production reassignment, paired flags off, restored database compatibility, required process groups, and final journey. Run in an isolated recovery target until the owner authorizes any public cutover.

**Why beyond SOTA:** Game days are established practice; the novel component is deriving scenarios and assertions directly from superscar recurrence and the Release Evidence Graph, then retiring a scenario only when its scar is mechanically impossible.

**Before → after:** monthly database restore but zero verified full-stack drills → all six recovery components exercised at least quarterly; technical RTO under 30 minutes; proof coverage 100%.

**Cost:** 24 hours to automate, then 2–4 hours quarterly. **Gear:** 3.

**Risk/scar:** test recovery impacting production or restoring sensitive data to an unsafe target—families #3 and #7.

**Measurement:** RTO by component, manual interventions, failed proof nodes, rollback compatibility, and residual synthetic data.

**Kill criterion:** stop any drill immediately if isolation identity is ambiguous or a target could receive public traffic; redesign before retrying.

**First PR:** `test(recovery): verify rollback-plan identities`; dry-run planner checking artifact and target identities; ≤300 net lines.

## 6. 90-day roadmap + first PRs

| Wave | Outcome | First PR | Files | Size/gear | Acceptance test |
|---|---|---|---|---|---|
| Days 0–30 | Make current releases falsifiable | `feat(release): validate consumer-map manifests` | New `config/release-consumers.yaml`, `scripts/release_consumer_map.py`, focused tests | ≤400 lines, Gear 3 | Fixture missing one mandatory consumer fails; complete fixture emits deterministic receipt |
| Days 0–30 | Close `503-RAG` release hole | `fix(deploy): block on required Fly process groups` | `.github/workflows/fly-deploy.yml`, read-only probe script, tests | ≤300 lines, Gear 2 | Simulated API-green/RAG-stopped state fails deployment proof |
| Days 0–30 | Establish numbers | `feat(release): compute delivery baselines` | Receipt summarizer and tests | ≤350 lines, Gear 2 | Computes lead time, proof coverage, failure, rework, and recovery from fixtures |
| Days 31–60 | Prove public content | `test(live): add cache-busted anonymous funnel probe` | Playwright probe and artifact schema | ≤350 lines, Gear 2 | Seeded redirect, 404 asset, console error, and CORS failure all fail; clean fixture passes |
| Days 31–60 | Prevent flag split state | `feat(release): add dual-platform flag preflight` | Read-only verifier, contract schema, tests | ≤400 lines, Gear 3 | Mismatched flags or artifact identities fail without mutation |
| Days 31–60 | Prevent schema-after-traffic failure | `feat(migrations): classify expand versus contract` | Migration metadata linter and tests | ≤350 lines, Gear 3 | Destructive operation without contract-phase metadata fails |
| Days 61–90 | Automate controlled exposure | `feat(release): record dark-internal-5-100 states` | Release state machine and tests | ≤400 lines, Gear 3 | Illegal transition, missing proof, or missing owner approval cannot promote |
| Days 61–90 | Exercise recovery | `test(recovery): verify rollback-plan identities` | Dry-run recovery plan and fixtures | ≤300 lines, Gear 3 | Wrong Fly app, Vercel project, image, or database target causes hard refusal |

Wave-one success target: consumer proof coverage ≥80%, manual deploy actions from nine to five, and every Fly release proves required process groups.

Wave-two target: ≥95% proof coverage, cache-busted browser evidence for critical public routes, and zero seconds of undetected two-platform flag disagreement beyond the verifier interval.

Wave-three target: automated dark/internal transitions, owner-gated 5% exposure, 100% exposure only after business-invariant proof, and one complete isolated recovery drill under 30 minutes.

## 7. Needs-ruling

Only the following require owner or external authority:

1. **Five-percent real-user exposure:** approve which users may enter the cohort, the minimum five-user evidence requirement, the bake duration, and the business abort threshold.
2. **Synthetic transaction consent:** approve whether a production synthetic may create a purchase, the maximum monetary exposure, refund behavior, retention, and isolation markers.
3. **Business invariant:** select the authoritative outcome for promotion—for example, successful eligibility result, completed checkout, or another owner-defined event—and its acceptable failure budget.
4. **Vercel/Fly credentials or GUI integration:** if the required project identity, Git integration, or environment state cannot be proved through existing sanctioned credentials, an owner must reconnect or confirm it.
5. **Public rollback/cutover game day:** authorize any exercise that changes a production domain, public traffic, or customer-visible flag. Isolated dry runs do not require this ruling.
6. **Schema risk acceptance:** approve any exceptional migration that cannot follow expand/contract or remain compatible with the previous image. The technical default should be refusal.

## 8. §Meta-pattern

The single defective belief is:

> **A green control-plane statement can stand in for the consumer’s experienced state.**

It generates nearly every finding:

- merge success stands in for public delivery;
- Vercel `READY` stands in for the custom domain;
- Fly `/health` stands in for every process group;
- authentication success stands in for correct target and usable authorization;
- migration command completion stands in for compatible runtime schema;
- one platform’s flag stands in for the logical feature;
- an exit code stands in for returned content;
- restored rows stand in for a recoverable service;
- a producer log stands in for a downstream business delta.

Nuzantara’s doctrine already rejects this belief. The next evolution is not another instruction: it is one executable Release Evidence Graph whose edges terminate only in consumer-observed facts. The organism becomes beyond-SOTA when its unusual advantages—the scar corpus, full-lifecycle ownership, two always-on local machines, cross-family review, consumer-map rule, and business-invariant doctrine—are used to generate those proofs automatically.

## 9. Sources

1. [Google SRE, “Release Engineering”](https://sre.google/sre-book/release-engineering/) — 2016; accessed 2026-08-29. Primary description of Google’s reproducible, automated, measurable release practice.
2. [Google SRE Workbook, “Canarying Releases”](https://sre.google/workbook/canarying-releases/) — 2018; accessed 2026-08-29. Primary guidance on partial exposure, control comparison, evaluation, and rollback.
3. [AWS, “Automating safe, hands-off deployments” announcement](https://aws.amazon.com/about-aws/whats-new/2020/06/new-abl-article-automating-safe-hands-off-deployments/) — 2020-06-18; accessed 2026-08-29. Authoritative summary of Amazon’s automated deployment-safety model and scale.
4. [Netflix Technology Blog, “Automated Canary Analysis at Netflix with Kayenta”](https://netflixtechblog.com/automated-canary-analysis-at-netflix-with-kayenta-3260bc7acc69) — 2018-04-10; accessed 2026-08-29. Primary account of control/canary metric scoring and automatic abort.
5. [Argo Rollouts, “Canary Deployment Strategy”](https://argo-rollouts.readthedocs.io/en/stable/features/canary/) — current documentation; accessed 2026-08-29. Authoritative specification of declarative weights, pauses, analysis, and abort.
6. [Flagger official documentation](https://flagger.app/) — current documentation; accessed 2026-08-29. Primary description of automated progressive traffic, acceptance checks, promotion, and rollback.
7. [OpenFeature, “Evaluation API”](https://openfeature.dev/docs/reference/concepts/evaluation-api/) — current documentation; accessed 2026-08-29. Authoritative vendor-neutral feature-evaluation contract and safe-default semantics.
8. [Fly.io, “Rollback Guide”](https://fly.io/docs/blueprints/rollback-guide/) — 2025; accessed 2026-08-29. Primary platform guidance confirming image redeploy semantics and the database rollback boundary.
9. [Vercel, “Promoting Deployments”](https://vercel.com/docs/deployments/promoting-a-deployment) — updated 2025-09-24; accessed 2026-08-29. Primary source for production reassignment, staged promotion, and instant rollback behavior.
10. [DORA, “2024 Accelerate State of DevOps Report”](https://dora.dev/research/2024/dora-report/2024-dora-accelerate-state-of-devops-report.pdf) — 2024; accessed 2026-08-29. Primary empirical benchmark for delivery throughput, failure, rework, and recovery.
11. [Checkly, “Synthetic Monitoring Overview”](https://www.checklyhq.com/docs/detect/synthetic-monitoring/overview/) — current documentation; accessed 2026-08-29. Primary description of API, multistep, and browser journey monitoring.
12. [pgroll official repository](https://github.com/xataio/pgroll) — current repository; accessed 2026-08-29. Primary implementation reference for reversible expand/contract PostgreSQL migrations.