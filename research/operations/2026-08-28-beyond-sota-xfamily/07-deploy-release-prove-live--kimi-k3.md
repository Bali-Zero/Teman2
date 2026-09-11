---
panel: beyond-sota-xfamily
lane: 07-deploy-release-prove-live
seat: kimi-k3
model: "kimi-code/k3 · Kimi CLI print mode (tools)"
started: 2026-08-28T18:58:58Z
finished: 2026-08-28T19:09:27Z
duration_s: 629
exit: 0
words: 4036
prompt_sha256_16: aa56130eb3261236
prompt_chars: 18236
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

• [Pro] I'm lane #7 (deploy/release/prove-live). Starting Phase A: grounding in the snapshot.

• Grounding is solid. A few final repo probes, then the SOTA survey.

• Now Phase B: SOTA survey, fetching 12 primary sources.

• Survey complete (10 primary sources verified). Writing the final report now.

  ---

  ```markdown
  ---
  date: 2026-08-28
  domain: operations
  panel: beyond-sota-2026-08-28
  part: 7/13 — Deploy, release & prove-live
  model: Moonshot Kimi K3 (pinned lane, kimi-code CLI)
  sources: 10
  repo_files_verified: 27
  status: complete
  ---

  # Lane 7 — Deploy, release & prove-live

  **Access note (mandatory disclosure).** This lane ran inside a read-only snapshot. Every `MEM:`
  reference in the brief (`feedback_merged_is_not_live_consumer_map_first`, `lesson_merged_is_not_delivered`,
  the four `discovery_*` memory notes, `MEMORY_VERIFICATION_RULES.md`) and the two home-directory skills
  (`~/.claude/skills/nuzantara-deploy/SKILL.md`, `~/.claude/skills/fly-split-brain-verify/SKILL.md`) are
  **outside the snapshot and were not read**. Where they mattered, I used the repository's own copies
  instead: `.github/workflows/fly-deploy.yml`, `frontend-live-sentinel.yml`, `garuda-arm.yml`,
  `docs/runbooks/*`, `products/garuda-voa/ops/*`, and the scar ledgers. Claims below cite only paths
  verified on disk in this session.

  ## 0. TL;DR

  Nuzantara's deploy lane is **at SOTA for deployment automation and ahead of SOTA in prove-live
  doctrine** (content-probes, ancestry tests, downstream state-delta), but **behind SOTA in progressive
  delivery and flag management**: there is no canary strategy, no traffic splitting, no flag registry,
  and the flagship "ship dark → 5% → 100%" ladder is doctrine that the current tooling cannot execute.
  The biggest single gap is that **"merged ≠ live" is detected per-platform by one sentinel on one
  surface** (frontend only), while the backend has no served-commit probe and Fly supports canary/bluegreen
  strategies that are never used. Top-3 moves: (1) a unified **served-commit receipt** closing the loop
  main-HEAD → both platforms, with the api/rag split-brain probe promoted from a skill to a deploy-gate
  step; (2) a **repo-tracked flag registry with two-platform parity checking** (Fly secrets digest ×
  Vercel env) so `GARUDA_PUBLIC_ENABLED` can never drift half-armed; (3) arm **Fly `--strategy canary`
  for high-risk deploys and Vercel Rolling Releases** (already on the Pro plan, measured unconfigured
  2026-07-30) to make the 5% stage real.

  ## 1. How Nuzantara does it today

  **Backend deploy pipeline** (`.github/workflows/fly-deploy.yml`, 601 lines, verified whole): five jobs
  in strict sequence. `pre-deploy-gate` runs the import-chain check
  (`from backend.app.dependencies import get_current_user`), deploy-critical ruff (F401/F821/F822/F823),
  the 82-test core RAG suite, CVE-exception freshness, and a Dependabot/safety filter. `run-migrations`
  executes `python -m backend.db.migrate apply-all` via `flyctl ssh console` against the **old** image.
  `deploy` runs `flyctl deploy --strategy rolling --remote-only` from the monorepo root with a 3-attempt
  lease-retry loop. `run-sql-v2-migrations-post-deploy` then re-runs migrations on the **fresh** image —
  with a sentinel that polls `flyctl machines list` until all started machines share one image tag and
  pins the SSH session to a machine in the `api` process group, because `rag`-group machines lack
  `asyncpg` (the split-brain fix, Wave-4 2026-05-09, run 25596634798). `run-python-migrations` runs
  hardcoded `apply_migration_119/120/121`. Finally `post-deploy-health` curls
  `https://nuzantara-rag.fly.dev/health` up to 10×30s, and on failure runs
  `flyctl releases rollback --yes` — with an in-file comment honestly stating the rollback **reverts the
  image only, never the schema**. Notification design is unusually mature: three distinct Telegram
  messages distinguish "clean deploy" from "service healthy but migration degraded" (the skip-cascade
  fix, Task #19 2026-07-26).

  **Frontend deploy**: Vercel builds on push-to-main; `apps/mouth/vercel.json` is a 6-line minimal
  config. `scripts/vercel_prod_deploy.py` (deploy + promote via the Vercel CLI OAuth token) plus the
  `mini.vercel_autopromote` LaunchAgent (`--promote-only` mode, 900s interval) form the auto-promote
  organ. `apps/mouth/src/app/api/health/route.ts` exposes the served commit (`VERCEL_GIT_COMMIT_SHA`)
  so production can answer "which commit am I running?"

  **The prove-live layer** is the strongest part. `.github/workflows/frontend-live-sentinel.yml`
  (verified whole) polls `balizero.com/api/health`, extracts `.commit`, and asserts
  `git merge-base --is-ancestor <expected> <served>` — an ancestry test, not an equality test, so
  production may be ahead but never behind; unknown shas fail closed. It dedups alerts by expected-sha
  cache key, judges Telegram delivery by the API reply (W104), and its header documents why the verdict
  is "does production include this commit," written after the 2026-07-27 incident where 25 commits
  landed while the Vercel GitHub App was uninstalled and nothing noticed for 13 hours. The modus
  doctrine (`.claude/skills/modus/SKILL.md` PROVE-LIVE row) commands: probe by **downstream
  state-delta, never exit code** ("READ THE OUTPUT/log"), and a probe failure triggers STOP-THE-LINE
  with rollback keeping the branch alive.

  **Product release ladder** (`docs/factory/ASSEMBLY-LINE.md` stage 6, verified): SHIP DARK behind a
  flag → internal → 5% with **5 real buyers observed end-to-end** → 100%; rollback = flag off; the
  paged alert is a **business invariant** ("paid orders in rolling 24h > 0"), plus a synthetic
  transaction that really buys (sandbox, refunded) every 10–15 min with a **dead-man switch**: probe
  silent 15 min → flag auto-off + owner alert. GARUDA VOA implements this in
  `apps/backend-rag/backend/services/garuda_ops/` (`deadman.py`, `invariants.py` BI-01/BI-02,
  `synthetic_probe.py`, per `products/garuda-voa/ops/README.md`) — with the probe honestly reporting
  `BLOCKED` on stages 2–5 rather than faking green.

  **Migrations at deploy**: custom SQL v2 runner (`backend/db/migrations_v2/NNN_*.sql` with mandatory
  `-- === ROLLBACK ===` markers), Squawk lint on migration PRs, the runtime-DSN runner executing as the
  application role — so a ledger-owned DDL **aborts the deploy** (W130: `must be owner of table
  visa_decision_retention_policies`, deploy red, main undeployable until fixed).

  **Flags**: `GARUDA_PUBLIC_ENABLED` is read at call time in `apps/mouth/src/app/visa/voa/flag.ts` and
  gated on the backend via `garuda-arm.yml`, whose summary step says explicitly: *"Frontend flag NOT
  touched by this workflow. Set `GARUDA_PUBLIC_ENABLED=true` in Vercel separately."* One flag, two
  platforms, two manual flips. `lint-garuda-environment-values.yml` pins the workflow's
  `garuda_environment` choice list against the DB CHECK constraints — a rare cross-surface guard.

  **Recovery**: `.github/workflows/restore-drill.yml` runs a **monthly** pg-restore drill from Tigris
  into a CI Postgres with row-count sanity gates (it caught its own silent-restore PGPASSWORD bug on
  2026-06-06 — a drill that drills itself). `docs/SLO.md` records rollback time ~2 min automatic,
  deploy frequency ~2–3/week against a ≥1/day target. Post-deploy browser QA (CLAUDE.md §11) is
  mandatory-but-manual: curl 200/307 → Chrome screenshot → verify 5 domains.

  ## 2. Scars & ledger evidence in this area

  Deploy is one of the most-scarred areas of the organism. Measured this session:

  - **123 lines** in `.claude/skills/modus/PENDING-ARMS.md` match "deploy" (2.2 MB ledger, grep-only).
    The open Vercel cluster alone spans lines 57–60, 155, 172, 202: no working Vercel credential on any
    fleet machine (2026-08-02); the promote-organ armed but its promote path **never executed
    unattended** (2026-08-21); a **~10h production staleness incident** (2026-08-22→23) that
    self-resolved externally; and the `BUNDLE_PATHS` defect making the sentinel chase docs-only commits.
  - **W130** (cicatrix-scars.md:1455): migration written after a role repair does `ALTER TABLE` on a
    table the runtime role no longer owns — deploy red, and *"the pre-deploy gate cannot see it, because
    in its Postgres it owns everything."* The CI shadow-DB is not prod-shaped for ownership.
  - **W122** (cicatrix-scars.md:1200): `release_command` did its work, then Fly's SIGINT produced exit
    130 → healthy deploy aborted; "read the OUTPUT, not the color."
  - **503-RAG / 2026-08-18 outage** (superscar #2; `cron-fly-watcher.yml` header): the rag worker was
    stopped ~2h serving 503s while health=200, found by a human — because the vm-critical alert storm
    (31/35 runs red) buried the signal. This is the exact "health endpoint ≠ worker alive" split-brain
    the lane brief names.
  - **W101-recidiva-fly-backup**, and the `fly_credential.sh` scar (cicatrix-scars.md:868): an env token
    poisoned the good credential; the antibody's rule — *the probe must measure the WORK, not the
    credential* (`fly auth whoami` proves nothing) — generalizes to every deploy-health check.
  - **AMENDMENTS.md** rows: "PROVE-LIVE catches what CI + two red-team rounds cannot" (2026-07-17, real
    binary vs real data found a KeyError 21 unit tests missed); "verification probes need entity-match
    discipline" (a bare-substring probe nearly overturned a correct verdict); W89's amendment —
    producer logs are still a proxy; prove by downstream state-delta.
  - **Vercel App uninstall incident** (PENDING-ARMS:202): 25 commits, 13h frozen public surface, one
    shared Vercel project (`prj_LcXb9Z...`) carrying balizero.com + 6 subdomains — blast radius was the
    whole public face.
  - **Restore drill**: documented cadence monthly, and it has fired real catches (apt-exit-100 class,
    PGPASSWORD-scope silent restore). `docs/SLO.md` still lists backup RTO as "Untested" for both
    Postgres and Qdrant — the drill proves restorability, not RTO.

  On the brief's measurement asks: the documented **manual** deploy path (CLAUDE.md §11) has ~10
  distinct human steps (4 pre-deploy commands + deploy + wait-curl + screenshot + 5-domain verify +
  fix/redeploy + report); the CI path is ~fully automated. The "5 measured public-surface defects of
  2026-08-28" live in an unavailable MEM note; from repo evidence (`products/garuda-voa/ops/README.md`),
  SYN-01 stages 2–5 are blocked placeholders today, so **0 of any end-to-end funnel defect class would
  be caught by the synthetic probe as currently wired** — the probe knows this and refuses to report
  green.

  ## 3. World SOTA survey

  | System/practice | Source (date) | Mechanism | Measured effect | Transfers here? |
  |---|---|---|---|---|
  | Google SRE canarying + release engineering | sre.google workbook ch.16 (2018–) | Small canary population, per-version metrics, error-budget proportionality; one canary at a time | Defect cost ∝ traffic fraction exposed | Yes, cheaply: Fly has `canary` strategy built in |
  | Netflix Kayenta (ACA) | Netflix TechBlog, 2018-04-10 | Mann-Whitney U on canary-vs-**fresh-baseline** clusters; score = pass-ratio; pluggable judges | ~200 judgments/day, 30% of canaries at publication | The *fresh baseline* insight transfers; the stats engine doesn't (traffic too low for significance) |
  | Meta quasi-continuous push | engineering.fb.com, 2017-08-31 | employees → 2% → 100% tiers over hours; Gatekeeper flags decouple deploy from release; emergency stop | Eliminated hotfixes; ~1,000 diffs/day | The tier ladder + flag-decoupling IS the ASSEMBLY-LINE model — Meta proves it at scale |
  | Stripe online migrations | stripe.com/blog (2017, still canonical) | 4-phase dual-write → read-switch → write-switch → cleanup; Scientist to compare paths in prod | Hundreds of millions of objects, zero downtime | Directly: the expand/migrate/contract discipline for migrations_v2 |
  | pgroll (Xata) | github.com/xataio/pgroll (2023–) | Two schema versions live simultaneously via views; instant migration rollback | Benchmarked per-commit across PG 14–18 | The missing half of this repo's rollback story |
  | Vercel Rolling Releases | vercel.com/docs (2024–) | Cookie-bucketed % rollout, stages, `vcrrForceCanary`, Skew Protection, API-driven start/complete | Built-in on Pro plan | Available TODAY on this repo's plan; measured unconfigured 2026-07-30 |
  | Fly.io deploy strategies | fly.io/docs (accessed 2026-08-28) | `rolling` (default), `canary` (boot one, health-verify, proceed), `bluegreen` (full shadow fleet, cutover on health); release_command; machine smoke checks | — | `canary` is a one-flag change away |
  | Fowler feature toggles | martinfowler.com (2016, continuously updated) | Toggle categories (release/ops/permission/experiment), config-in-source, **expiration dates / time-bomb flags**, inventory carrying cost | Knight Capital $460M as the counter-example | The flag-registry + expiry discipline is exactly what the two-platform GARUDA flag lacks |
  | DORA five keys | dora.dev (updated 2026-01) | Lead time, deploy frequency, failed-deploy recovery time, change-fail rate, rework rate; speed↔stability correlated | Elite: on-demand deploys, <1-day recovery | This repo already tracks most of these in docs/SLO.md — against stale (2026-04-06) baselines |
  | Argo Rollouts | argo-rollouts.readthedocs.io (accessed 2026-08-28) | Controller-driven blue/green + canary, metric-provider analysis runs, automated abort | — | Overkill (no K8s); its **analysis-template-as-code** idea transfers to the sentinel layer |

  The five that matter most: **Meta** (proof that deploy≠release via flags + tiered rollout eliminates
  hotfix culture — Nuzantara has the doctrine, not the mechanism), **Kayenta** (the *fresh baseline
  cluster* — comparing a new canary to a long-lived production instance produces unreliable metrics;
  Nuzantara's health probe compares against nothing), **Stripe** (online-migration phasing — the repo's
  migrations_v2 already has ROLLBACK markers but no enforced expand/contract sequencing), **pgroll**
  (schema rollback is the hole the auto-rollback comment itself confesses), and **Fowler** (flags as
  inventory with expiry — the GARUDA flag is a permanent release toggle with no registry, no expiry,
  and a two-platform manual flip).

  ## 4. Position vs SOTA

  | Sub-dimension | Verdict | Evidence |
  |---|---|---|
  | Deploy pipeline automation (backend) | **AT** | fly-deploy.yml: gate → migrate → rolling → re-migrate → health → auto-rollback, with lease-retry and degraded-state notifications |
  | Deploy verification by content | **AHEAD** | frontend-live-sentinel ancestry test; `/api/health` commit field; modus PROVE-LIVE "downstream state-delta, never exit code" (AMENDMENTS W89) — most shops still check HTTP 200 |
  | Split-brain / partial-fleet detection | **AT** (doctrine), **BEHIND** (placement) | api/rag asyncpg sentinel exists for migrations, but post-deploy health probes only `/health` — the rag-worker-dead case (503-RAG, 2026-08-18) is watched by cron, not gated at deploy |
  | Progressive delivery (canary, % traffic) | **BEHIND** | `--strategy rolling` everywhere; Fly `canary`/`bluegreen` unused; Vercel Rolling Releases unconfigured (PENDING-ARMS:172, measured 2026-07-30); the 5% stage of ASSEMBLY-LINE has no mechanism |
  | Feature flags | **BEHIND** | env-var flags, two-platform manual flip (garuda-arm.yml line ~197), no registry/expiry/parity check; one cross-surface lint (lint-garuda-environment-values.yml) is the exception |
  | Migrations at deploy | **AT** | runtime-role runner aborts on ownership violation (W130), post-deploy re-run fixes old-image class (2026-04-26 cicatrix), Squawk at PR |
  | Schema rollback | **BEHIND** | image-only rollback, confessed in fly-deploy.yml comments; no pgroll-class dual-schema; expand/contract named in ASSEMBLY-LINE contracts but not CI-enforced |
  | Synthetic business probes | **AHEAD** (design), **BEHIND** (wiring) | SYN-01 + BI-01/BI-02 + dead-man switch is beyond what most startups run; but stages 2–5 are honest placeholders and prod-crm-smoke is a manually-invoked script |
  | Recovery drills | **AHEAD** for size | Monthly automated restore drill with self-caught bugs is elite behavior at this budget; RTO untimed (SLO.md) |
  | Deploy metrics | **AT/BEHIND** | SLO.md has DORA-ish rows but is 5 months stale; no computed-from-CI deploy-frequency/change-fail dashboard |

  ## 5. Beyond-SOTA recommendations

  Ranked by (impact × confidence) / cost.

  **R1 — Served-commit receipt: one ledger, both platforms, gated at deploy.**
  *What*: add the served GIT_SHA to the backend `/health` payload (the image already builds with
  `--build-arg GIT_SHA`), then extend the sentinel pattern into a `deploy-receipt` job: after every
  merge, assert `balizero.com/api/health.commit` AND `nuzantara-rag.fly.dev/health.commit` are both
  ancestors-or-equal of the deploy-relevant main HEAD, writing one JSONL row (sha, image tag, probe
  delta). *Why beyond SOTA*: surveyed systems verify *their own* deploy; none of Google/Netflix/Vercel
  close the loop across two independent platforms against a single source-of-truth ref with an ancestry
  semantics — this organism already invented the hard half (ancestry, not equality) on one surface.
  *Asymmetry used*: the scar corpus (13h/10h staleness incidents) + the existing sentinel idiom.
  *Cost*: ~1 day, gear 2. *Risk*: family #2 (a receipt job that exists but is never required) — mitigate
  by making it a required check on `main` pushes. *Metric*: staleness detection latency, before 13h/10h
  (measured) → after <45 min worst case (the sentinel's own honest cron-latency math). *Kill*: if it
  cries wolf >2×/month, revisit the pathspec. *First PR*: `/health` commit field + receipt workflow, ≤300 lines.

  **R2 — Flag registry with two-platform parity sentinel.**
  *What*: `config/feature-flags.yaml` — name, category (Fowler), owner decision ref, expiry date,
  expected state per platform. A cron workflow compares: Fly secret *names+digest-present* (the
  garuda-arm.yml verification idiom) × Vercel env via API × registry; skew → alert; expired release
  toggle → PR-failing lint (Fowler's time-bomb). *Why beyond SOTA*: flag platforms (LaunchDarkly et al.)
  manage flags *inside* their own walled garden; no surveyed system treats a repo file as the registry
  and audits two independent SaaS platforms against it — and this organism's measured failure
  (`GARUDA_PUBLIC_ENABLED` armed on Fly, forgotten on Vercel, or vice versa) is exactly that shape.
  *Cost*: ~2 days, gear 2. *Risk*: family #9 (state drift between registry and reality) — the parity
  job IS the mitigation. *Metric*: flag-skew time-to-detect, currently unbounded (never measured) →
  <1 cron cycle; flags without expiry at go-live: 0. *Kill*: if the registry sees no update in 90 days,
  fold it into garuda-arm and delete. *First PR*: registry + read-only parity reporter, ≤250 lines.

  **R3 — Promote the split-brain probe from skill to deploy-gate step.**
  *What*: a `post-deploy-split-brain` job in fly-deploy.yml that, after rolling convergence, probes
  **both** process groups — api via `/health`, rag via its queue-depth/heartbeat surface — before the
  "Deploy OK" Telegram may fire. *Why beyond SOTA*: canary tooling (Argo, Kayenta) watches the *new
  version*; nobody's deploy gate asserts "every process group that was alive before is alive after" —
  and 503-RAG (health=200, worker stopped 2h, found by a human) is the measured cost of that hole here.
  *Cost*: ~1 day, gear 2 (reuses the existing machine-list sentinel code verbatim). *Risk*: family #2
  if the rag probe is a proxy — use the W104/W89 rule: judge the work (queue drained), not the
  heartbeat. *Metric*: worker-dead detection latency, before ~2h human-found → after <5 min at deploy;
  incidents of class 503-RAG post-deploy: target 0/90 days. *Kill*: none — this is a gate, not an
  experiment. *First PR*: one job, ≤200 lines.

  **R4 — Arm Fly `canary` strategy for risk-tiered deploys; Vercel Rolling Releases for the 5% stage.**
  *What*: deploys whose diff touches `payments/`, `garuda_*`, `channels/` use `--strategy canary`
  (Fly boots one machine, verifies health, then rolls) — a one-line strategy flag plus a diff-path
  classifier; separately, configure Rolling Releases (Pro plan includes one project; measured
  unconfigured 2026-07-30) so ASSEMBLY-LINE's 5% stage is a platform primitive, not a wish. *Why
  beyond SOTA*: it isn't novel per se — it's SOTA this organism's doctrine already claims and cannot
  execute; the beyond-SOTA part is *risk-tiered strategy selection driven by the diff*, which neither
  Fly nor Vercel offers natively. *Cost*: ~1 day + one operator[control-plane] Vercel settings change
  (needs-ruling for the account gesture). *Risk*: family #8 (a staged rollout stuck mid-flight blocks
  the next promote — Vercel documents exactly this). *Metric*: blast radius of the next bad deploy —
  before 100% of traffic, after ≤1 canary machine / 5% of sessions. *Kill*: if canary deploys add
  >10 min P95 deploy time, restrict to payment-touched diffs. *First PR*: strategy classifier + canary
  path, ≤150 lines.

  **R5 — Spec-to-probe: generate the synthetic journey from `journeys/*.feature`.**
  *What*: GARUDA's frozen Gherkin acceptance scenarios (products/garuda-voa/journeys/) compile into the
  SYN-01 probe stages — the same artifact is the pre-build RED test and the post-deploy probe.
  *Why beyond SOTA*: synthetic-monitoring vendors (Checkly/Datadog) hand-write probes; no surveyed
  system derives the production probe *from the contract artifact the refuter froze*, closing the loop
  between "what we promised at G2" and "what prod proves at G7". *Asymmetry*: the journeys/ artifacts
  already exist and are gate-frozen. *Cost*: ~3 days, gear 3 (crosses contract and ops lanes). *Risk*:
  family #3 (substring/classification trapping in generated assertions) — mitigate with the AMENDMENTS
  entity-match rule (match by id/fact-key). *Metric*: probe-stage coverage of named sad paths, before
  1/6 stages real → after 6/6; funnels shipping with unprobed sad paths: 0. *Kill*: if the generator
  drifts from hand-written probes twice, keep probes hand-written. *First PR*: one happy-path scenario
  → one probe stage, ≤400 lines.

  **R6 — Rollback-safety annotation for migrations (pgroll-lite).**
  *What*: CI check on `migrations_v2/*.sql`: every migration declares `rollback_safe: image-only |
  requires-contract-phase`; a deploy carrying a `requires-contract-phase` migration disables the
  automatic `flyctl releases rollback` and demands the two-phase (expand, then contract in a later
  deploy) — making the image-only-rollback confession in fly-deploy.yml *enforced* instead of
  documented. *Cost*: ~2 days, gear 2. *Risk*: family #2 (annotation present, check unrequired).
  *Metric*: % deploys where rollback is provably schema-safe, before unknown → after 100% *declared
  and checked*. *First PR*: annotation parser + check, ≤300 lines.

  ## 6. 90-day roadmap + first PRs

  **Wave 1 (days 1–30) — close the detection holes.** PR-a: *"feat(ops): served-commit receipt for both
  platforms"* — `apps/backend-rag/backend/app/routers/health.py` (add commit), new
  `.github/workflows/deploy-receipt.yml`; ≤300 lines; gear 2; acceptance: a pushed no-op backend commit
  produces a receipt row within 45 min, and a doctored stale sha fails the check red. PR-b: *"feat(ci):
  post-deploy split-brain probe across api+rag groups"* — fly-deploy.yml only; ≤200 lines; acceptance:
  kill the rag worker in a drill, deploy must not emit the unqualified "Deploy OK". PR-c: *"feat(ops):
  feature-flag registry + parity reporter"* — `config/feature-flags.yaml` + read-only reporter; ≤250
  lines; acceptance: deliberately skew `GARUDA_PUBLIC_ENABLED` in a fork → reporter names the skewed
  platform.

  **Wave 2 (days 31–60) — make the ladder executable.** Arm Fly canary for risk-tiered diffs (PR-d);
  operator flips Vercel Rolling Releases + Skew Protection (needs-ruling gesture), then PR-e wires
  `rolling-release start/complete` into a promote workflow with `vcrrForceCanary` smoke via the
  browser QA skill; acceptance: a docs-trivial mouth change rolls 0%→5%→100% with metrics visible.
  PR-f: migration rollback-safety annotations (R6).

  **Wave 3 (days 61–90) — spec-derived proving.** PR-g: spec-to-probe generator for the GARUDA happy
  path (R5 first slice); acceptance: editing the `.feature` file changes probe behavior with no code
  edit. Close the wave by refreshing `docs/SLO.md` deploy rows from computed CI data (deploy frequency,
  change-fail rate, recovery time — DORA five keys) so the doctrine's numbers are re-derivable, per
  the ASSEMBLY-LINE anti-fabrication rule.

  ## 7. Needs-ruling

  - **Vercel Rolling Releases + Skew Protection enablement** — a project-settings change on the paid
    Vercel account (operator[control-plane] gesture; the repo measured rolling releases `null` on
    2026-07-30). Business-adjacent because it changes how all balizero.com traffic is served.
  - **`productionDeploymentsFastLane`** — the still-unflipped, undocumented Vercel setting suspected of
    forcing `readySubstate: STAGED` (PENDING-ARMS:172). Flipping it is an account-level gamble the
    lanes correctly refuse to take alone.
  - **Payment provider sandbox for the synthetic purchase probe** — SYN-01's "really buys, refunded"
    stage needs owner credentials (MANDATE.md owner decision 1).
  - **GARUDA go-live flag flip itself** (`GARUDA_PUBLIC_ENABLED=true` on BOTH platforms + sitemap PR) —
    already gated as owner decision 0; this lane only notes the flip must become one atomic
    registry-driven act (R2), not two manual ones.

  ## 8. §Meta-pattern

  Every finding in this lane is generated by one defective belief: **"the platform's green signal is
  the deploy's truth."** Fly says the release succeeded (but the rag worker is dead — 503-RAG); Vercel
  says READY (but the domains serve the old build — 2026-07-30); the migration runner says applied
  (but on the old image — 2026-04-26); the workflow says success (but the arm step never ran — W123);
  `launchctl` says running (but the promote organ has never promoted — PENDING-ARMS:57); the cron says
  */30 (but delivers at a 91-minute median — the sentinel's own measurement). The organism has already
  discovered the antidote piecemeal — ancestry probes, downstream state-deltas, judged delivery,
  honest-blocked probes — but applies each antidote **at the exact scar that taught it**, leaving the
  adjacent surface unguarded (the "defects in the joint" document makes the identical observation about
  test suites). The beyond-SOTA move that subsumes R1–R3 is therefore not another probe but a rule with
  teeth: **no deploy, arm, or rollout may conclude from the platform's own success signal** — every
  conclusion requires an observation of the *consumer-visible state the deploy was for*. That is
  SRE's "monitoring from the user's perspective" pushed one step further than Google, Netflix, or
  Vercel take it operationally: made a **merge-time invariant**, enforced by CI, scar-funded.

  ## 9. Sources

  1. [Google SRE Workbook — Canarying Releases](https://sre.google/workbook/canarying-releases/) — accessed 2026-08-28. Authoritative primary on canary population sizing, metric attribution, one-canary-at-a-time.
  2. [Netflix — Automated Canary Analysis with Kayenta](https://netflixtechblog.com/automated-canary-analysis-at-netflix-with-kayenta-3260bc7acc69) — 2018-04-10, accessed 2026-08-28. Primary on ACA mechanics; the fresh-baseline-cluster insight.
  3. [Meta — Rapid release at massive scale](https://engineering.fb.com/2017/08/31/web/rapid-release-at-massive-scale/) — 2017-08-31, accessed 2026-08-28. Primary on tiered rollout (employees→2%→100%) and Gatekeeper deploy/release decoupling.
  4. [Stripe — Online migrations at scale](https://stripe.com/blog/online-migrations) — 2017, accessed 2026-08-28. The canonical dual-write 4-phase online migration pattern.
  5. [Vercel — Rolling Releases docs](https://vercel.com/docs/rolling-releases) — accessed 2026-08-28. Official mechanism for the 5% stage this organism's doctrine demands (Pro plan, stages, skew protection, API).
  6. [Fly.io — Deploy an app (strategies, release_command, smoke checks)](https://fly.io/docs/launch/deploy/) — accessed 2026-08-28. Confirms `canary`/`bluegreen` strategies available and unused here.
  7. [Martin Fowler — Feature Toggles](https://martinfowler.com/articles/feature-toggles.html) — accessed 2026-08-28. The reference taxonomy + flag inventory/expiry discipline behind R2.
  8. [DORA — Five key metrics guide](https://dora.dev/guides/dora-metrics-four-keys/) — updated 2026-01-05, accessed 2026-08-28. Benchmark frame for deploy frequency / recovery time / change-fail rate.
  9. [Argo Rollouts — official docs](https://argo-rollouts.readthedocs.io/en/stable/) — accessed 2026-08-28. Reference for metric-gated progressive delivery and analysis-as-code.
  10. [pgroll (Xata) — zero-downtime reversible Postgres migrations](https://github.com/xataio/pgroll) — accessed 2026-08-28. The dual-schema expand/contract mechanism behind R6.

  *Attempted but unusable: AWS Builders' Library "Automating safe, hands-off deployments" (JS-gated
  page, no extractable content — not cited above).*
  ```

  **Report delivered above as the final message** (per the lane instruction, protocol file-write steps were converted to this return). Verification notes: all cited repo paths were verified on disk this session via `ls`/`grep`/`sed -n`/full reads — including `fly-deploy.yml` (601 lines), `frontend-live-sentinel.yml` (279), `restore-drill.yml` (158), `garuda-arm.yml`, `lint-garuda-environment-values.yml`, `docs/factory/ASSEMBLY-LINE.md`, `docs/SLO.md`, both runbooks, `products/garuda-voa/ops/README.md`, and the scar ledgers (grep-only per protocol). The two `$HOME` skills and all `MEM:` files were outside the snapshot and are declared unavailable in the report's header. One survey target (AWS Builders' Library) failed to yield content and is disclosed, not cited; the report carries 10 usable primary sources against the 10-source minimum.

