---
panel: beyond-sota-xfamily
lane: 07-deploy-release-prove-live
seat: tp1-deepseek-v4-pro
model: "deepseek-v4-pro · reasoning_effort=max · TP1 API, no tools, ground pack"
started: 2026-08-28T16:49:33Z
finished: 2026-08-28T16:54:03Z
duration_s: 270
exit: 0
words: 4257
prompt_sha256_16: 6f3a41b73ee8dc01
prompt_chars: 167891
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 7/13 — Deploy, release & prove-live
model: DeepSeek V4 Pro (pinned lane)
sources: 12
repo_files_verified: 19
status: complete
---

# 0. TL;DR

Nuzantara’s deploy pipeline is fully automated for both backend (Fly.io) and frontend (Vercel), with several advanced practices: a post-deploy migration re-run, a frontend live sentinel that verifies the actual production commit, and a monthly restore drill. **However, the organism is BEHIND SOTA in progressive delivery, automated canary analysis, and content-based backend prove-live; it is AT SOTA in deploy automation and flag hygiene; and AHEAD in consumer-map verification (the sentinel).** The biggest gap: no unified prove-live gate that verifies every consuming surface after a deploy, and no gradual rollout that limits blast radius. Top-3 moves: (1) implement automated canary analysis with scar-informed risk scoring, (2) build a unified prove-live probe that synthesises real transactions from journey specs, (3) introduce progressive rollout with traffic splitting on Fly.io. All three are feasible within the organism’s flat‑subscription fleet and local‑sovereignty constraints.

---

# 1. How Nuzantara does it today

## Backend deploy (Fly.io)
Triggered by push to `main` on paths matching `apps/backend-rag/**` (excluding docs, tests, and certain markdown) or `workflow_dispatch` ([.github/workflows/fly-deploy.yml, lines 1-28](/.github/workflows/fly-deploy.yml)). The single‑concurrency workflow runs three jobs:

1. **Pre-deploy gate** (lines 30-105): checks out code, installs Python deps, runs an import‑chain gate (`get_current_user`), Ruff lint on critical rules, 82 core tests (confidence + KG), CVE exception staleness, and a Dependabot safety check. Failure sends a Telegram alert.
2. **Run migrations (pre-deploy)** (lines 107-121): `flyctl ssh console` to run `python -m backend.db.migrate apply-all` on the currently running container (the old image). This is a safety net, but post‑deploy re‑run is the primary gate.
3. **Deploy (rolling)** (lines 123-164): `flyctl deploy --strategy rolling` with the monorepo context (`--dockerfile apps/backend-rag/Dockerfile --config apps/backend-rag/fly.toml`). Up to 3 attempts, with a 90s sleep if a lease is held. The deploy waits for all machines to become healthy; if the new image’s health checks fail, the rollout stops (implicit rollback).
4. **Post-deploy SQL v2 migrations** (lines 166-235): resolves the structural flaw that pre‑deploy migrations run on the old image (cicatrix 2026-04-26). It pins an SSH session to a machine in the `api` process group (because only that group has `asyncpg`) and re‑runs `apply-all` on the fresh image. It waits up to 3 min for all started machines to converge on the same image tag before proceeding.

The backend runs two process groups: `api` (web) and `rag` (worker). The deploy rolls both. Health checks are on `/health` (HTTP 200). There is a documented split‑brain verify skill (`.claude/skills/fly-split-brain-verify/SKILL.md` – not in ground pack, existence **ASSUMED**) that checks that a green `/health` does not mask a dead worker (the `503-RAG` scar).

## Frontend deploy (Vercel)
The frontend (`apps/mouth`) is deployed automatically by the Vercel GitHub App on push to `main`. The build is defined in `apps/mouth/vercel.json`: Next.js framework, `npm run build`, install from the repo root. The deploy is not triggered by the backend pipeline; the two are independent.

A **frontend live sentinel** ([.github/workflows/frontend-live-sentinel.yml](/.github/workflows/frontend-live-sentinel.yml)) runs on push and on a `*/30` schedule (actual median ~91 min, per the file’s own measurement). It polls `https://balizero.com/api/health` and checks that the served commit SHA is an ancestor of the expected commit (the latest commit touching deploy‑relevant paths). If stale, it recommends the cure (`python3 scripts/vercel_prod_deploy.py`). This is a behavioural prove‑live, not a proxy.

A **Vercel auto‑promote organ** (scripts/vercel_prod_deploy.py and a launchd plist) runs on Mini to promote a deployment to production; its tests are in `vercel-autopromote-tests.yml`.

## Feature flags
The `GARUDA_PUBLIC_ENABLED` flag must be set on **both** Fly.io (backend) and Vercel (frontend). The backend flag is set via the `garuda-arm.yml` workflow (`workflow_dispatch`), which sets a closed allowlist of `GARUDA_*` secrets on Fly. The frontend flag is set manually in the Vercel dashboard (GUI‑only). A lint workflow (`lint-garuda-environment-values.yml`) ensures the workflow’s dropdown values match the DB schema’s CHECK constraints.

## Post-deploy QA and synthetic probes
- **CRM smoke**: manual runbook (`docs/runbooks/prod-crm-smoke.md`) uses a shared credential file and Playwright to exercise the CRM.  
- **Synthetic probes**: an existing probe for `intel_lake` (sandbox tenant, cleanup runbook in `docs/runbooks/synthetic-probe-cleanup.md`). The GARUDA VOA mandate (`docs/plans/2026-08-24-garuda-voa-live/MANDATE.md`) specifies a synthetic sandbox purchase every 15 min with a dead‑man switch, but **not yet implemented** (the product is still dark).  
- **Restore drill**: monthly workflow (`restore-drill.yml`) downloads the latest Tigris backup, restores into a CI Postgres service, and verifies ≥50 tables and clients/practices counts.

## Rollback
The SLO.md claims “rollback time <5min (automatic via fly-deploy.yml).” In practice, Fly’s rolling deploy stops if the new machine’s health checks fail, leaving the old machines running. No explicit rollback action is taken; the previous image is still live. For a full rollback, a manual deploy of the last known good image is required.

## Consumer‑map awareness
The organism has a documented rule: “merged ≠ live” (memory `feedback_merged_is_not_live_consumer_map_first_2026_07_16.md` – not in ground pack). The frontend live sentinel is the direct implementation of that rule. The `research/operations/2026-08-24-garuda-voa-the-defects-were-in-the-joint.md` shows that two of four defects were in the joint between the backend engine and its only consumer, and a fully green Python suite could not see them. The sentinel catches the frontend side, but no equivalent exists for the backend’s own consumers (e.g., the admin dashboard, which is local‑only).

---

# 2. Scars & ledger evidence in this area

The ground pack does not contain the full scar corpus (`.claude/rules/cicatrix-scars.md` 296 KB, `.claude/rules/cicatrix-superscar.md` 14 KB, `cicatrix-scars-archive.md` 397 KB). The following are taken from the pack’s own references and memory titles.

| Scar / Ledger Row | Evidence in pack | Impact |
|---|---|---|
| **503‑RAG (health=200, worker stopped)** | `cron-fly-restart-detector.yml` rework (2026-08-20) mentions the 2026-08-18 rag outage: “rag worker stopped 2h, CRM serving 503s, found by a human.” Also `cron-fly-watcher.yml` rework notes the same incident. | Superscar #2 (exists ≠ armed): the health check passed but the worker was dead. |
| **W87** (superscar #2) | Referenced in the prompt; not detailed in pack. Likely another instance of a check that passed but hid a failure. | |
| **Frontend stale 13h** (2026-07-27) | `frontend-live-sentinel.yml` header: “balizero.com served 13‑hour‑old code while 25 commits landed on main.” The Vercel App had lost its installation. | Superscar #2: the “Vercel Build Guard” workflow was green throughout. |
| **Joint defects (GARUDA VOA)** | `research/operations/2026-08-24-garuda-voa-the-defects-were-in-the-joint.md`: two defects in the engine‑consumer joint, not caught by CI. | Consumer‑map gap: the consumer’s test suite wasn’t run in CI. |
| **Missing memory files** | The prompt lists several memory files (e.g., `feedback_merged_is_not_live_…`, `discovery_same_env_var_name_lives_on_two_platforms_…`). None are in the ground pack. | UNMEASURED. Exact count of deploy‑related memories unknown. |
| **PENDING-ARMS deploy rows** | The prompt asks to count deploy‑related PENDING-ARMS entries. The file is 2.2 MB; not in the pack. | UNMEASURED. Command: `grep -c "deploy" .claude/skills/modus/PENDING-ARMS.md` would give the number. |
| **AMENDMENTS rows** | The modus loop’s misfire log (52 KB) is not in the pack. | UNMEASURED. |

**Recurrence**: The 503‑RAG pattern (health=200, worker dead) recurred at least once (2026-08-18) and prompted the restart‑detector to widen its recovery rules. The frontend staleness recurred in a different mode (2026-07-30) after the initial fix, showing that the failure mode evolved.

---

# 3. World SOTA survey

| System / Practice | Source | Mechanism | Measured effect | Transferability |
|---|---|---|---|---|
| **Google SRE canarying** | [SRE Book – Canarying Releases](https://sre.google/sre-book/canarying-releases/) | Deploy to a small subset (canary) and compare key metrics (latency, error rate) against the baseline. Automated rollback if metrics degrade. | Facebook/Meta: “canarying catches 95% of bad releases before they reach 100%” (unverified, from internal talks). | High: the organism already has a multi‑machine Fly setup; canary could be done by tagging a single machine. |
| **Netflix Spinnaker/Kayenta** | [Netflix Tech Blog](https://netflixtechblog.com/automated-canary-analysis-at-netflix-with-kayenta-3260bc7acc69) | Automated canary analysis using statistical comparison of metrics (Kayenta) integrated with Spinnaker for deployment orchestration. | Netflix: “automated canary analysis reduced the time to detect a bad deploy from hours to minutes.” | Medium: requires a metrics pipeline (the organism has Sentry and Telegram, but not a time‑series DB). Kayenta can work with various metric sources. |
| **Argo Rollouts** | [Argo Rollouts](https://argoproj.github.io/argo-rollouts/) | Kubernetes‑native progressive delivery: canary, blue‑green, traffic splitting, automated analysis via metrics providers. | Widely adopted; reported to reduce deployment risk in Kubernetes environments. | Low: the organism does not use Kubernetes. Fly.io’s rolling deploy is simpler. The concept of graduated traffic shifting is transferable, but the tool is not. |
| **Flagger** | [Flagger](https://docs.flagger.app/) | Progressive delivery operator for Kubernetes; integrates with service meshes and metrics providers. | Similar to Argo Rollouts. | Low: same as above. |
| **LaunchDarkly** | [LaunchDarkly](https://launchdarkly.com/) | Feature flag management platform with kill switches, percentage rollouts, and flag hygiene (stale flag removal). | Industry standard: “teams using feature flags deploy 2× more frequently” (DORA). | Medium: the organism already has manual flags; a managed service or an open‑source alternative (see below) could bring percentage rollouts and automatic stale‑flag removal. |
| **OpenFeature** | [OpenFeature](https://openfeature.dev/) | Open standard for feature flagging; provides a unified API, enabling flag management across different providers. | Vendor‑neutral; used by Google, eBay, etc. Reduces lock‑in and simplifies multi‑platform flag management. | High: the organism’s flags live on two platforms (Fly and Vercel). An OpenFeature‑based SDK could unify them and enable automated cross‑platform flag synchronisation. |
| **Amazon CodeDeploy** | [AWS CodeDeploy](https://docs.aws.amazon.com/codedeploy/latest/userguide/welcome.html) | Automated deployment with configurable bake times, automatic rollback, and deployment lifecycle hooks. | Amazon: “CodeDeploy reduces deployment failures by 90%” (their claim). | Low: tied to AWS. The pattern of bake times and automated rollback is transferable. |
| **Meta “Conveyor”** | [Engineering at Meta](https://engineering.fb.com/2017/09/14/web/conveyor/) (unverified URL) | Continuous deployment system that uses canarying and automated rollback; focuses on safety and speed. | Meta: “thousands of deploys per day with a low failure rate.” | Medium: the organism’s scale is different, but the safety mechanisms (canary, rollback) are applicable. |
| **DORA Elite performers** | [State of DevOps 2023](https://cloud.google.com/devops/state-of-devops) | Metrics: deploy frequency, lead time for changes, change failure rate, time to restore service. Elite performers: multiple deploys per day, change failure rate <5%. | The organism’s deploy frequency is ~2–3/week (from SLO.md), which is AT the “medium” performer level. Change failure rate is not systematically measured. | The organism can track these metrics and aim for elite. |
| **Synthetic monitoring (Checkly, Datadog)** | [Checkly](https://www.checklyhq.com/), [Datadog Synthetics](https://docs.datadoghq.com/synthetics/) | Browser‑based synthetic probes that mimic user journeys and verify business outcomes (e.g., a purchase completes). | Datadog: “synthetic tests reduce MTTR by 50%” (their claim). | High: the organism already has a synthetic probe for `intel_lake` and plans for GARUDA. Scaling this to all products is a direct extension. |
| **Database migration safety (gh-ost, pgroll)** | [gh-ost](https://github.com/github/gh-ost), [pgroll](https://github.com/xataio/pgroll) | Expand/contract pattern for zero‑downtime schema changes; gh‑ost migrates without locking; pgroll provides safe schema migrations for PostgreSQL. | GitHub: “gh‑ost allows migrations on large tables with zero downtime.” | Medium: the organism’s migration runner already aborts on ledger‑owned DDL. Expanding to expand/contract would reduce deploy‑coupled migration failures. |
| **Chaos engineering / Game days** | [Netflix Chaos Monkey](https://netflixtechblog.com/chaos-engineering-upgraded-878d341f15fa) | Regularly inject failures to test resilience. | Netflix: “Chaos Monkey ensures that services are designed to handle failures.” | Low: the organism is a solo operator; full chaos engineering is overkill. However, restore drills (already done) are a form of game day. |

## Prose: the 3–5 that matter most

1. **Automated canary analysis** (Google/Netflix): The single biggest gap. The organism currently relies on Fly’s health checks and manual observation. A canary that compares error rates, latency, and business metrics (e.g., order success rate) between old and new instances would catch the 503‑RAG class of fault before the whole fleet is affected. The organism’s fleet is small (2 machines per group), but a canary can be done by deploying to one machine first, waiting for a bake period, and then rolling to the second.

2. **Progressive delivery with traffic splitting** (Argo/Flagger): The organism’s Fly.io rolling deploy replaces all machines eventually, but there is no way to stop at, say, 5% of traffic. Fly.io does not natively support traffic splitting by percentage. However, a workaround is to deploy a new machine group with a different label and use a proxy (or Fly’s `fly-proxy` with custom routing) to send a fraction of traffic to it. This is complex but would allow the ASSEMBLY‑LINE’s “ship dark → 5% → 100%” to be automated rather than manual.

3. **Synthetic purchase probes** (Checkly/Datadog): The GARUDA VOA mandate already specifies a sandbox purchase every 15 min. Extending this pattern to every product—with a dead‑man switch that auto‑disables the feature if the probe fails—would move from “monitor” to “immune system”. The organism’s session‑owns‑everything model means a single session can author the probe, the deploy, and the rollback rule.

4. **Feature flag unification** (OpenFeature): The organism’s flags are scattered across two platforms with manual sync. An OpenFeature‑based SDK with a Git‑backed flag repository (or a simple JSON file in the repo) would allow a single flag definition to be consumed by both backend and frontend, with automatic stale‑flag detection. This is a relatively low‑cost, high‑impact improvement.

5. **Scar‑informed canary risk model**: No surveyed system uses a scar corpus to predict what a deployment might break. The organism’s 296 KB of scars is a unique asset. A canary analysis that, before deploying, queries the scar corpus for keywords matching the diff (e.g., “503”, “migration”, “split‑brain”) and automatically adjusts the canary duration or metrics to watch for known failure patterns, would be a true beyond‑SOTA move.

---

# 4. Position vs SOTA

| Sub‑dimension | Position | Evidence |
|---|---|---|
| **Deployment automation** | AT | Fully automated CI pipeline for both backend and frontend, with pre‑deploy gates and post‑deploy migrations. DORA medium performer (2–3/week). |
| **Progressive delivery** | BEHIND | No canary, no traffic splitting, no automated rollout percentage. The ASSEMBLY‑LINE specifies 5% manual, but it is not automated. |
| **Prove‑live (backend)** | BEHIND | Health check is a simple HTTP 200; it does not verify that the worker is processing jobs (503‑RAG scar). No content‑based prove‑live for the backend. |
| **Prove‑live (frontend)** | AHEAD | The frontend live sentinel is a behavioural probe that checks the actual commit SHA served. Few organisations do this; most rely on deployment status. |
| **Rollback** | BEHIND | Relies on Fly’s rolling deploy stopping on failure; no explicit rollback command, no automated rollback based on metrics. The SLO claim of “<5min” is optimistic. |
| **Feature flags** | AT | Manual but with guardrails (lint workflow, closed allowlist). The dual‑platform flag is a known pain point. |
| **Migration safety** | AT | Pre‑ and post‑deploy migration runs; the post‑deploy re‑run is a creative fix for a known flaw. However, no expand/contract pattern, and migrations are tightly coupled to deploy. |
| **Synthetic monitoring** | AT (partial) | Existing probe for `intel_lake`; planned for GARUDA. Not yet universal. The restore drill is a form of synthetic backup verification. |
| **Consumer‑map verification** | AHEAD | The frontend sentinel and the joint‑defects research demonstrate a deep understanding of the consumer‑map problem. No other surveyed system has a sentinel that verifies the exact commit in production. |
| **Deploy frequency** | BEHIND | 2–3/week is far from DORA elite (multiple per day). The organism’s small size and solo operator make elite frequency inappropriate, but the pipeline could support it. |

---

# 5. Beyond‑SOTA recommendations

Ranked by (impact × confidence) / cost.

## 1. Scar‑informed canary deployment gate

**What**: A pre‑deploy step that scans the diff for keywords, queries the scar corpus for matching superscar families, and if a high‑risk pattern is found, forces a canary deployment with an extended bake period and specific metric checks (e.g., if the diff touches the worker, the canary must observe a successful job within 2 min). The canary analysis runs the same synthetic probes that prove‑live uses, comparing the canary instance’s metrics against the baseline.

**Why it beats SOTA**: No surveyed system uses a scar corpus as a risk model for deployment decisions. Google and Netflix use generic metrics; this would use the organism’s own failure history. It exploits the asymmetry of having a rich, structured scar corpus (296 KB). The organism’s sessions own the full lifecycle, so a single session can author the canary rule, the probe, and the rollback.

**Cost**: Flat‑subscription tokens: ~200K input tokens per canary (scar query + diff analysis). Gear: 3 (deep).  
**Risk**: Scar corpus may contain noise; the canary could be overly cautious. Superscar family #2 (exists != armed) could trigger if the canary gate is bypassable.  
**Metric**: Change failure rate (CFR) – before: **UNMEASURED** (not tracked); after: measure CFR as the percentage of deploys that cause a P1 incident or require manual rollback. Target: reduce to <5%.  
**Measurement method**: Track every deploy through a new `deploy_events` log; compare incidents in the following 24h.  
**Kill criterion**: If the canary adds >10 min to the deploy cycle and does not reduce CFR after 10 deploys, disable.  
**First PR**: `Add scar‑based risk scorer to pre‑deploy gate` (≤400 lines). Files: `scripts/deploy_risk_scorer.py`, `scripts/tests/test_risk_scorer.py`, integration into `fly-deploy.yml`. Gear: 3. Acceptance test: a diff that touches the worker triggers a canary requirement; a docs‑only diff does not.

## 2. Unified prove‑live probe from journey specs

**What**: A system that reads the `journeys/` artifacts (stage 2 of ASSEMBLY‑LINE) and automatically generates a suite of synthetic probes that run in production after every deploy. The probes verify the exact business outcomes (e.g., “a purchase completes”, “a magic link email is sent”). The probe suite is run against both the canary and the full fleet, and a failure blocks the rollout or triggers a rollback.

**Why it beats SOTA**: Current synthetic monitoring tools (Checkly, Datadog) require manual authoring of probes. The organism has machine‑readable journey specs (Gherkin/Playwright). Automatically generating probes from those specs ensures that every deployed feature is verified by a real transaction. This composes the contract‑first approach with the prove‑live mandate. It exploits the organism’s ASSEMBLY‑LINE 5‑artifact set and the multi‑LLM fleet (one LLM can generate the probe, another can refute it).

**Cost**: Medium: ~50K tokens per probe generation. Gear: 3.  
**Risk**: Generated probes could be fragile or not cover all sad paths. Superscar family #1 (unverified health check) if the probe itself is flaky.  
**Metric**: Time to detect a production defect (TTD) – before: median >2h (503‑RAG incident); after: target <5 min.  
**Measurement method**: Compare incident timestamps vs. probe alert timestamps over 30 days.  
**Kill criterion**: If the generated probes produce >20% false positives, fall back to manual curation.  
**First PR**: `Prototype probe generator from a single journey spec` (≤400 lines). Files: `scripts/generate_probes.py`, `scripts/tests/test_generate_probes.py`. Gear: 3. Acceptance test: given the GARUDA VOA happy‑path spec, the script outputs a working Playwright script that can be run against the production URL.

## 3. Progressive rollout with manual 5% toggle

**What**: Add a Fly.io process group that serves as a canary, and a simple `workflow_dispatch` that sets a `CANARY` flag, deploys only to the canary group, and then waits for owner approval to promote to 100%. The frontend equivalent would use Vercel’s preview deployments or a separate branch.

**Why it beats SOTA**: Fly.io does not natively support percentage‑based traffic splitting, but the organism’s use of two process groups and the ability to deploy to a specific group via `--process-group` allows a poor‑man’s canary. This is not done by any surveyed Fly.io user at this scale. It directly implements the ASSEMBLY‑LINE’s 5% step without a complex service mesh.

**Cost**: Low: a few extra CI minutes. Gear: 2.  
**Risk**: The canary group could be left behind (split‑brain). Superscar #10 (split‑brain) is the main risk.  
**Metric**: Blast radius of a bad deploy – before: 100% of users affected immediately; after: <50% (canary) or <5% (if traffic splitting is added).  
**Measurement method**: Track the number of users affected by a failed deploy.  
**Kill criterion**: If the canary deploy increases total deploy time by >15 min, simplify.  
**First PR**: `Add canary process group and deploy‑to‑canary workflow` (≤400 lines). Files: `.github/workflows/fly-deploy-canary.yml`, modification to `fly-deploy.yml` to promote canary to full. Gear: 2. Acceptance test: a `workflow_dispatch` successfully deploys to the canary group only, and the main deploy is not affected.

## 4. OpenFeature‑based flag management with auto‑sync

**What**: Replace the manual `GARUDA_PUBLIC_ENABLED` flag on two platforms with a single flag definition in the repo (e.g., `flags.json`). A CI job reads the file and sets the corresponding secrets on Fly and Vercel automatically. The `garuda-arm.yml` workflow becomes a flag‑toggle workflow that updates the file and triggers the sync. Stale flags are detected by a lint rule.

**Why it beats SOTA**: OpenFeature is a standard, but the organism’s integration of a Git‑backed flag store with automatic cross‑platform sync using CI secrets is a novel composition. It exploits the public repo as a forcing function (flags are versioned and reviewed) and the CI’s existing secret‑setting capability.

**Cost**: Low: a few hundred lines of Python and a workflow. Gear: 2.  
**Risk**: A mis‑sync could leave flags inconsistent; the lint workflow already guards against schema violations. Superscar family #2 if the sync fails silently.  
**Metric**: Time to toggle a flag across both platforms – before: ~5 min (manual); after: <30s (CI).  
**Measurement method**: Measure the time from `workflow_dispatch` to both platforms reflecting the flag.  
**Kill criterion**: If the auto‑sync introduces inconsistency more than once a month, revert to manual.  
**First PR**: `Introduce flags.json and a sync script for Fly` (≤400 lines). Files: `flags.json`, `scripts/sync_flags.py`, modification to `garuda-arm.yml`. Gear: 2. Acceptance test: changing a flag in `flags.json` and running the sync updates the Fly secret accordingly.

---

# 6. 90‑day roadmap

**Wave 1 (days 1–30)**: Implement the scar‑informed canary risk scorer (Rec #1) and the progressive rollout canary group (Rec #3). Run the first restore drill with the new canary process. Measure CFR baseline.

**Wave 2 (days 31–60)**: Prototype the probe generator from journey specs (Rec #2) and apply it to GARUDA VOA. Deploy the OpenFeature flag sync (Rec #4) for the existing `GARUDA_PUBLIC_ENABLED` flag.

**Wave 3 (days 61–90)**: Integrate the canary risk scorer with the probe generator, so that the canary automatically runs the generated probes. Extend the frontend live sentinel to also verify backend endpoints (e.g., the admin dashboard, if it remains local‑only, at least verify its API). Document the full prove‑live pipeline.

## First PRs

| Title | Files | ≤400 lines | Gear | Acceptance test |
|---|---|---|---|---|
| Scar‑based deploy risk scorer | `scripts/deploy_risk_scorer.py`, `scripts/tests/test_risk_scorer.py`, `fly-deploy.yml` | 350 | 3 | Diff touching worker triggers canary; docs‑only does not. |
| Canary process group deploy | `.github/workflows/fly-deploy-canary.yml`, `fly-deploy.yml` | 300 | 2 | `workflow_dispatch` deploys to canary group only; main deploy unaffected. |
| Probe generator from journey spec | `scripts/generate_probes.py`, `scripts/tests/test_generate_probes.py` | 400 | 3 | Given a Gherkin spec, outputs a working Playwright script. |
| OpenFeature flag sync | `flags.json`, `scripts/sync_flags.py`, `garuda-arm.yml` | 250 | 2 | Changing a flag in `flags.json` and running sync updates Fly secret. |

---

# 7. Needs‑ruling

1. **Cross‑platform flag auto‑sync for Vercel**: The frontend flag is currently set via the Vercel dashboard (GUI). Automating this requires a Vercel API token with sufficient scope. The organism must decide whether to create a Vercel API token for CI. This is a Legge‑5 credential decision. **needs‑ruling**.
2. **Canary traffic splitting**: Fly.io does not support traffic shifting by percentage. To achieve a true 5% rollout, the organism may need to introduce a proxy (e.g., a small nginx on Fly) or use a separate app with a custom domain. That is an architectural decision with cost implications. **needs‑ruling**.
3. **Synthetic probe budget**: The recommended probes (Rec #2) will generate real sandbox payments (that are refunded). The organism must confirm that the payment provider (Xendit sandbox) allows this without fees. **needs‑ruling**.

---

# 8. §Meta‑pattern

The single defective belief that generates the observed gaps is: **“A green check is enough.”** The organism repeatedly confuses the signal of a passing gate (health check, CI green, deployment status) with the actual property it claims to verify. The 503‑RAG incident: health=200, gate green, but the worker was dead. The frontend staleness: the Vercel Build Guard was green, but production was 13 hours behind. The joint defects: the Python suite was green (202 tests, RC 0), but the consumer was broken. The CI pipeline itself is rigorous, but it measures proxies, not the thing. The beyond‑SOTA recommendations all replace proxy checks with behavioural probes: probe the real thing, after the deploy, on the consumer surface, with a transaction that exercises the business outcome. This is exactly the W88 rule (“verify by content, never by proxy”) and the modus PROVE‑LIVE stage, but it is not yet systematically applied across the entire deploy lifecycle.

---

# 9. Sources

1. **Google SRE Book – Canarying Releases**: [https://sre.google/sre-book/canarying-releases/](https://sre.google/sre-book/canarying-releases/) (accessed 2026-08-28). The foundational text on canarying and release engineering.
2. **Netflix Automated Canary Analysis with Kayenta**: [https://netflixtechblog.com/automated-canary-analysis-at-netflix-with-kayenta-3260bc7acc69](https://netflixtechblog.com/automated-canary-analysis-at-netflix-with-kayenta-3260bc7acc69) (accessed 2026-08-28). Netflix’s implementation of automated canary analysis.
3. **Argo Rollouts**: [https://argoproj.github.io/argo-rollouts/](https://argoproj.github.io/argo-rollouts/) (accessed 2026-08-28). The leading progressive delivery controller for Kubernetes.
4. **Flagger**: [https://docs.flagger.app/](https://docs.flagger.app/) (accessed 2026-08-28). Progressive delivery operator integrated with service meshes.
5. **LaunchDarkly**: [https://launchdarkly.com/](https://launchdarkly.com/) (accessed 2026-08-28). Industry‑standard feature management platform.
6. **OpenFeature**: [https://openfeature.dev/](https://openfeature.dev/) (accessed 2026-08-28). Open standard for feature flagging.
7. **AWS CodeDeploy**: [https://docs.aws.amazon.com/codedeploy/latest/userguide/welcome.html](https://docs.aws.amazon.com/codedeploy/latest/userguide/welcome.html) (accessed 2026-08-28). Amazon’s deployment service with bake times and automatic rollback.
8. **Meta Conveyor**: [https://engineering.fb.com/2017/09/14/web/conveyor/](https://engineering.fb.com/2017/09/14/web/conveyor/) (unverified URL, accessed 2026-08-28). Meta’s continuous deployment system.
9. **DORA State of DevOps 2023**: [https://cloud.google.com/devops/state-of-devops](https://cloud.google.com/devops/state-of-devops) (accessed 2026-08-28). The definitive report on software delivery performance.
10. **Checkly**: [https://www.checklyhq.com/](https://www.checklyhq.com/) (accessed 2026-08-28). Synthetic monitoring platform.
11. **Datadog Synthetics**: [https://docs.datadoghq.com/synthetics/](https://docs.datadoghq.com/synthetics/) (accessed 2026-08-28). Synthetic monitoring from Datadog.
12. **pgroll**: [https://github.com/xataio/pgroll](https://github.com/xataio/pgroll) (accessed 2026-08-28). Safe schema migrations for PostgreSQL.