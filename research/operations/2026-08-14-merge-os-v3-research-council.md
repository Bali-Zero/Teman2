---
date: 2026-08-14
domain: operations
client_case: internal — Merge-OS v3 direction: research council over the PR/CI/merge system
discovered_by: "Fable 5 (M5 orchestrator) — 3-seat cross-family council convoked at dispatch, own SOTA sweep, all repo facts re-verified live this session"
sources:
  - "council seats (transcripts in research/operations/refutations/2026-08-14-mergeos-v3-*.txt): Codex gpt-5.6 default-model effort=xhigh (red-team, re-grounded itself on the repo) · Gemini via agy (constructive+width) · Kimi K3 kimi-code/k3 (refuter, re-verified every repo claim on main d5f34fe53)"
  - "own SOTA sweep 2026-08-14: Mergify State of Merge Queues 2026 (https://mergify.com/reports/state-of-merge-queues-2026) · TianPan 2026-07-02 merge-queue-is-the-new-bottleneck · Tenki GitHub MQ 2026 guide (https://tenki.cloud/blog/github-merge-queue-setup) · Mergify when-to-outgrow-github-merge-queue · GitHub changelog 2026-07-30 stacked PRs public preview · GitHub docs (managing-a-merge-queue, troubleshooting-required-status-checks)"
  - "repo ground (re-executed this session): origin/main migration-lint.yml / docs-sync.yml / tests.yml / security.yml / pytest.ini:72 · gh run list tests.yml main 6 runs · Pro ~/.nuzantara-mq/baseline/*.json (4 records) · PENDING-ARMS.md:901-907 · #4142 · #4101"
  - research/operations/2026-08-10-merge-os-v2-submission-system.md
  - research/operations/2026-08-10-queue-acceleration-round3-system-wide.md
adversarial_review: codex
---

# Merge-OS v3 — the research council (2026-08-14)

> **Mandate (Zero, 2026-08-14): analysis and research only, no PRs — "chiedi ai grandi LLM di
> supportarti nel ricercare la soluzione migliore studiando sia il nostro sistema e sia i migliori
> sistemi al mondo."** This document is the disposition groundwork §8.6 of the v2 spec demanded
> ("a v3 that disposes of F1–F7 / F1–F4 finding-by-finding"), produced by a 3-family council plus
> an independent SOTA sweep. It authorizes nothing to arm; it tells the next implementing session
> exactly what to build, in what order, and why.

## 0. One sentence

All three external families converge, independently, on the same inversion of the v2 plan:
**govern the suite's growth first, delete the derived-state exactness invariant instead of
building an organ to heal it, keep the full proof where attribution lives (PR-side) until
post-R0-off data says otherwise, and add agent volume (cloud offload) last** — ring-gating,
the wave v2 called "capacity", drops from first lever to a gated, shadow-proven, maybe-later.

## 1. Radiography — what moved since the BLOCK verdict (all re-measured this session)

The 2026-08-10 BLOCK is partially stale; a v3 that disposes the original finding list without
this section would re-litigate cures that already landed (W111: a rejection can describe text
that no longer exists).

**Already cured on main (2026-08-10/11):**
- The converged P0 (false-green migration gate) — #4026: top-level `paths:` removed from
  migration-lint.yml AND docs-sync.yml, `merge_group:` added, job-level relevance via
  `github.event.merge_group.base_sha || pull_request.base.sha`, sentinel skip=success.
- Codex F4 — #4003: docs-sync gate fails closed when judge/corpus deleted, self-tests its corpus.
- Wave 0's other items: `mq.sh` v1 + post-arm watcher (#4029), required.d snapshot (#4026),
  agent PR contract in CLAUDE.md (#4044).
- agy-F4 *literal* case (pure-CSS PR): cured by the sentinel relevance detection. The *general*
  case (a relevant-but-innocent PR killed by pre-existing main drift) is still open — observed
  live in #4101 and #4066.

**Wave 1 is armed and flowing, with one real defect:**
- `com.nuzantara.queue-baseline` runs nightly 03:51 on Pro; 4 consecutive daily records
  (2026-08-09..12). Acceptance (7 records) ≈ 2026-08-17.
- DEFECT: pagination shortfall (`fetched=1000 reported_total=10269; record is partial`) —
  billed/PR was computed for only 4 of 48 merged PRs (those 4 measured **62-70 min/PR**), and
  the slot-utilization figure (4.16%) is unusable. The record honestly self-declares partial
  (fail-visible worked), but **Wave-1 acceptance is meaningless until the probe paginates fully.**
  Also: the plist's log paths (`~/logs/queue-baseline*.log`) do not exist on disk.

**The world the plan does not know (post-2026-08-10 changes):**
- **R0 backend suite DEFAULT-OFF since 2026-08-13 (#4142)**: measured 2.3% real catches, 30%
  no-verdict under one-Mac multi-session contention; CI is a verified strict superset and now
  the ONLY test boundary. v2's ring-gating safety argument ("code-red caught by R0 pre-push")
  is structurally weaker than written.
- Suite growth CONTINUES: main runs today 26.2–53.6 min wall, median ~29 (25.7 on 08-10;
  18 five weeks ago). Kimi's file count: backend test files 1,280 (07-10) → 1,531 (today),
  +20% in 5 weeks. The only "budget" is `timeout-minutes: 30` — a kill-switch the median is
  now walking toward, and a **cancelled required check ejects the queue entry and never turns
  green by itself** (the repo's own docs-sync.yml comment documents this failure mode).
- Still undone: tests.yml still fires on `push: main`; security.yml still weekly (Sunday) +
  push; `critical` marker still used by zero tests (F6 confirmed live); `change_map.py` still
  shadow-only, still in neither CODEOWNERS nor hot-zone (F3 confirmed live).
- Kimi seat ALIVE again on M5 (billing cycle reset — the 08-10 seat-availability record is stale).

## 2. External SOTA (2025-2026, own sweep — what the v2 classics don't cover)

1. **Mergify State of Merge Queues 2026**: batching is the most underused lever (94% of merges
   still 1-PR-per-CI-cycle; batch users average 4/batch); **AI-assisted PRs break main LESS
   than human PRs (1.9% vs 4.4%)**, holding within repos; broken-main scales ~16× with team
   size; median queue 8 min, p90 63-68 min.
2. **TianPan (2026-07)**: agents are a *flake amplifier* — exposure multiplication × agent
   retry loops ("get it merged" → re-trigger storms = self-inflicted DoS) × higher issue rate;
   remedies: admission control, pre/post-merge test split, batching. Uber pre-flake-regime:
   main green only 52%, ~1k flaky of 600k tests.
3. **Tenki GitHub-MQ 2026 guide**: lean required set (fast deterministic only; E2E/visual/perf
   informational); quarantine via markers/BuildPulse; check timeout ≈ 2× CI runtime; group
   size 5 to start; the top failure modes are exactly ours (cascading restarts,
   pull_request-only triggers, matrix check-name mismatch).
4. **Native-queue ceiling (Aug 2026, re-verified)**: still no bisection, no priority lanes,
   no per-path queues; jump-to-front exists. v1's three answers stand. Codex adds precision:
   GraphQL exposes `MergeQueueEntry.solo` and a "Request a solo merge" custom-role permission,
   but **solo-merge ≠ exclusive admission** — no queue-wide freeze/lease primitive exists, so
   §2.2's isolation gate cannot be built on native GitHub at all.
5. **NEW primitive: stacked PRs** (public preview 2026-07-30, merge-queue support rolling
   out): land a whole stack into the queue in one operation; unmerged layers auto-rebase.
   Relevant to the agent contract: today rule 7 forces serial fresh-main handoff per merge; a
   stack lets an agent lane keep building while layers land. Watch maturity; not load-bearing yet.
6. **Test governance practice**: instrument durations and ENFORCE budgets (hard budgets prevent
   regression); flaky ≈ 20%-of-CI-time claims; ~30 min human cost per flake investigation
   (Microsoft). Bazel: size/timeout classes per test. Flutter: ownership + statistical
   observation + green-streak restoration + deletion only for unstabilizable tests.
7. **Public-repo capacity note**: Bali-Zero/Teman2 is public → Actions minutes free; the
   binding resource is CONCURRENCY (20 slots), as every prior measurement assumed. Self-hosted
   runners on the idle fleet are NOT a safe lever on a public repo (fork-PR code execution —
   GitHub's own warning); parked unless restricted org-wide someday.

## 3. The council — seats, provenance, method

| seat | family | mandate | grounding behavior |
|---|---|---|---|
| Codex `gpt-5.6` (default model), effort xhigh, `--sandbox read-only` | OpenAI | red-team: dispose residual findings, attack ratified doctrine, GitHub-primitive precision, risk-ranked build order | re-read repo files itself (tests.yml:89, CODEOWNERS, mq.sh:294, pytest.ini:72, hot-zone-pr-gate.yml:68); cited official GitHub/Bazel/Meta/Flutter docs; declared Pro unreachable → ruleset/entitlement claims marked ASSUMPTION |
| Gemini via `agy` | Google | constructive + width: what the best do, best concrete v3 shape | industry patterns (TAP/Meta/Stripe tiers, budgets, PTS); full artifact archived |
| Kimi K3 `kimi-code/k3` | Moonshot | refuter: falsify 4 core claims with cases | re-verified EVERY repo claim on main `d5f34fe53` (#4142 content, triggers, file counts, #4101 commit message, docs-inventory-refresh liveness organ); marked pack aggregates it could not re-measure as ASSUMPTION |

All were handed the same self-contained grounding pack (state + residual findings + 6 research
questions), written from facts re-verified this session — no seat was asked to trust the v2
document's own citations (W65). Seat provenance caveat (W100): the Gemini seat is the same
family that produced agy-F1..F4 in the 08-10 BLOCK round; its convergence with Codex/Kimi on
NEW questions is cross-family, its agreement with its own prior findings is not counted as
independent confirmation. Codex's `-m` slugs remain dead post-rotation, so the seat is named by
account default model, not flag (the 08-10 provenance rule).

## 4. The four convergences (each reached independently by ≥2 families, most by 3)

### C1 — Suite-growth governance BEFORE any test selection (3/3 seats)
Kimi's arithmetic is the sharpest form: ring-gating touches ~1 of ~3.6 runs/PR (the classifier
is PR-only by design), so its ceiling is a **one-time** cut to a minority of slot-minutes,
while the suite compounds ~10%/week across ALL FOUR triggers (PR, queue, push:main, 2-hourly
cron) — the growth term erases the entire saving in ~2 weeks. Nothing in the tree pushes back
on d(cost)/dt. Concrete predicted incident (Kimi): at median ~29 min against
`timeout-minutes: 30`, growth converts the job timeout into cancelled-required-check queue
ejections — a systemic hard-block, already documented as a failure mode by the repo itself.
Codex frames it as risk-adjusted return: budgets/dedupe don't weaken the correctness boundary,
selection does. Gemini brings the industry floor: Google/Meta layer selection ON TOP of
size/flakiness governance, never instead of it.

### C2 — Delete the derived-state exactness invariant; do not build the healing organ (3/3)
The strongest structural result of the round: **verify-don't-store** (Codex, Gemini) /
**diff-local check** (Kimi's sharper transitional form) dissolves THREE findings at once —
F5 (no isolation primitive needed because no heal actor exists), agy-F2 (no stale-tree loop
because nothing chases moving main), agy-F4-general (no innocent PR inherits global drift).
Kimi's evidence that the current invariant is self-defeating: #4101's own commit message —
"regen in the same commit is necessary but not sufficient on a moving main… the queue outran
it" — plus the fact that heal-as-PR **already exists** in this repo (docs-inventory-refresh.yml
opens flip-PRs through the queue) and **already needs a stuck-PR >48h liveness alarm**: stuck
heal PRs are a monitored, expected failure mode today. And the defended value is ~zero: the
derived state is counts in prose with no programmatic consumer (grep: writer, auditor, tests
only), while AGENTS.md and README.md sit committed with contradictory counts and nothing breaks.
Codex adds the primitive-level proof that the alternative is unbuildable: solo-merge exists,
queue-wide freeze does not — so §2.2's fail-closed isolation gate can never open.
The Go/DotSlash exception pattern (tracked generated files as true runtime/client inputs, with
declared `input_source_sha` provenance) does not apply to editorial counts.

### C3 — Full proof stays where attribution lives; the third payment goes first (3/3, two routes)
Kimi refutes ratified doctrine #2 head-on: "full proof paid once **in the queue**" is backwards
for THIS repo's author class — post-#4142, PR-side CI is the FIRST execution of agent code
anywhere; the queue batches ≤5, attributes to `github-actions[bot]`, has no bisection, and F7's
retry counter resets per entry: **attribution is the scarcest resource in an agent-authored
repo, and the PR-side run is the only point where failure maps 1:1 to an author and a diff.**
The 4-reverts-in-12-weeks record was achieved UNDER redundancy — the duplicate payments are
insurance premiums, not waste. Codex reaches the same operational conclusion from the other
side: queue-full-proof remains sound for *correctness*, defective for *admission economics*;
Google/Meta pay at the land queue but have local verification + culprit-finding — importing
their allocation without their machinery is cargo-cult. Operational resolution both accept:
**keep PR-side full proof AND queue full proof for now; remove only the third payment
(`push: main`) — the 2-hourly scheduled run is the backstop, verified live** — and revisit the
allocation only with post-R0-off shadow data (Codex: 2 weeks or 100-200 PRs, whichever later).

### C4 — Cloud/agent volume LAST (3/3)
Kimi: UNSOUND-harms-first — #4142's 30% no-verdict rate under one-Mac contention is the
observed signature of saturating a fixed-capacity gate (verdicts don't slow, they DISAPPEAR);
at 48% utilization with μ falling ~10%/wk, the system crosses the Kingman regime within weeks
with λ held flat. The batching steelman (deeper queue → fuller batches → amortized proof) is
confiscated by ejections of never-tested code (batch of 5 at p=5% per-PR ⇒ 23% batch ejection)
plus F7's unbounded rearm plus no bisection. Codex and Gemini: identical sequencing verdict.
Reverses to SOUND after: attributed PR-side proof retained + capacity work landed + transit
p95 in SLO. **This answers the session's opening question (offload sessions to cloud): yes in
architecture, last in sequence.**

## 5. Finding-by-finding disposition (what §8.6 demanded)

| finding | v3 disposition | mechanism | seat(s) |
|---|---|---|---|
| converged P0 (migration gate) | **CURED 08-11** (#4026) — verify residually in Wave-0 conformance guard | sentinel + merge_group SHAs | conductor (this session) |
| Codex F1 (needs:-skip on merge_group) | OPEN, P0-at-activation — classifier job materializes on ALL events (emits run_all=true on merge_group/error/empty/kill-switch≠'on'); NO required job may be top-level skipped (`if: always()` + step-level gating); no-op is an explicit sentinel annotation (`intentional_noop=true`), never bare `skipped`; guilt corpus parses the WORKFLOW YAML shape, not just the Python | Codex §2 | Codex, (GLM r2 converged) |
| Codex F3 (self-modifiable judge) | OPEN, elevate to P0-at-activation — root of trust, not ownership: judge+corpus execute from a SHA-pinned required workflow (org ruleset "require workflows to pass", fields repository_id/path/ref/sha), PR tree treated as data only; **ASSUMPTION: needs Enterprise-tier rulesets — entitlement unverified (operator check)**; fallback package if unavailable: CODEOWNERS + code-owner review + dismiss-stale + hot-zone base-pinned (pattern already exists at hot-zone-pr-gate.yml:68) + required shape-corpus — and ring-gating stays OFF until the package is whole | Codex §3; Gemini's ref:main checkout is the weaker cousin (main moves on every merge) |
| Codex F5 (no isolation primitive) | **DISSOLVES** via C2 — no heal actor, nothing to isolate; F5's precise form recorded: solo-merge ≠ queue-wide freeze | C2 | all 3 |
| Codex F6 (vacuous critical marker) | OPEN — invert the polarity: quarantine is a protected ALLOWLIST manifest (owner, issue, failure fingerprint, expiry ≤14d, sample size), default-deny; critical floor is a POSITIVE protected manifest (auth, migrations, startup/import, pricing, security boundaries, RAG abstention, embeddings, verifiers, deploy health), never the complement of an unused marker; manifest CODEOWNERS-protected + hot-zone + unmodifiable by the benefiting PR | Codex §6; Tenki/Flutter practice |
| Codex F7 (retry counter resets) | OPEN — durable budget keyed `(repo, PR, head SHA)`, never queue entry; CODE=0 auto-requeue, INFRA≤3/24h, CONFLICT/HEAD_MOVED=none until new head passes smoke, UNKNOWN=fail-closed; **no atomic cross-run store exists in Actions → if no organic durable store, the conservative choice is NO autonomous rearm** (launchd organ on Pro can own the counter file) | Codex §7 |
| agy-F2 (heal stale-loop) | **DISSOLVES** via C2 | C2 | all 3 |
| agy-F3 (author-class unmeasurable) | **DISSOLVED — wrong observation point**: attribute from the PR timeline, not merge_group.actor; GraphQL `RemovedFromMergeQueueEvent` carries pullRequest/actor/enqueuer/beforeCommit/reason; episodes keyed (PR, head SHA, enqueue ts); even-split stays for COST attribution only, declared as estimate | Codex §8 — feeds the baseline organ |
| agy-F4 (innocent PR vs main drift) | literal case cured; general case **DISSOLVES** via C2; transitional rule while files stay tracked: gate blocks only hand-edits in generated blocks / invalid generator / provenance mismatch vs declared input SHA — guilt by DELTA, never by proximity | Codex §9, Kimi (b) |
| round-2 cures (kill-switch `!= 'on'`, wired-shape corpus, billing formula) | stand as Wave-2 preconditions; billing formula already implemented in baseline organ (#4031) — now needs the pagination fix to produce a real denominator | r2 + this session |
| NEW: baseline pagination shortfall | OPEN, blocks Wave-1 acceptance — paginate `list_workflow_runs` fully (10,269 ≠ 1,000); until then every capacity number is partial | this session |

## 6. The v3 build order (merged council verdict, risk-adjusted)

0. **Freeze** (free): ring-gating stays un-armed; heal-as-PR is never built; classifier stays
   shadow. (Both P0-at-activation findings are inert while frozen.)
1. **Fix the baseline probe's pagination + finish 7 records.** Add timeline-based ejection
   attribution (agy-F3 disposition) while in there. Every later target gets its denominator here.
2. **Trigger dedupe, in the risk order Codex specified**: audit ruleset (no bypass actors, no
   direct pushes, 26 contexts actually materialize) → remove `push: main` from tests.yml (2-hourly
   schedule is the verified backstop) → observe one full cycle → add security.yml daily schedule
   (`cron: '17 19 * * *'` = 03:17 WITA) → one green scheduled run → remove security push.
   Accepts brief extra duplication on security rather than a window with no confirmed backstop.
3. **Suite-growth governance** (the dominant lever, C1): hard per-job timeout from p95 not
   median; rolling p50/p95 + slot-minutes + top-N-by-duration telemetry per lane with weekly
   delta and owner; **test-cost regression gate** that blocks only the regression a PR
   introduces (hard on PRs touching test infra/fixtures/timeouts, telemetry-only elsewhere);
   ownership SLA on top slow tests; suite diet from the `--durations=50` data (round-3 L3 —
   both 08-10 refuters' first pick, still undone). NO auto-deletion on slowness/flake alone
   (Codex: deletion requires proof of redundancy or documented unstabilizability).
4. **Derived-state deletion** (C2): remove volatile counts/inventories from tracked docs (link
   to `docs_sync.py --json` / CI artifact instead); transitional diff-local gate while any file
   stays tracked; docs-sync check becomes generator-correctness + no-hand-edits. Dissolves
   F5/agy-F2/agy-F4 and today's false-red class (#4101/#4066). Requires the ASSUMPTION check:
   grep-verified no programmatic consumer — one dependency sweep before deletion (cheap).
5. **Judge root-of-trust** (F3 package): entitlement check first (operator); pinned required
   workflow if available, else the full fallback package. Prerequisite to ANY future ring-gating.
6. **Flake + retry regime** (F6/F7 dispositions): exact-test same-SHA in-attempt retry with
   fail→pass = flake-candidate-but-STILL-BLOCKING unless in valid quarantine manifest;
   protected quarantine allowlist + positive critical floor; durable (PR, head-SHA) retry
   budget or no autonomous rearm.
7. **Shadow re-observation under R0-off conditions** (2 weeks or 100-200 PRs, whichever later):
   classifier recall vs full runs, red-catch PR-vs-queue split, intentional-noop vs
   accidental-skip counts. The pre-#4142 shadow data does not carry over.
8. **Ring-gating, maybe, progressively**: only after 1-7, `vars.MERGEOS_RING_GATING == 'on'`
   opt-in, one low-risk lane first, auto-rollback on recall or transit regression.
9. **Cloud agent scale-out** (the question that opened this session): after capacity headroom
   + transit p95 in SLO. Architecture yes; sequence last.

Steps 1-4 are individually safe, individually valuable, and none changes gate semantics — the
same "stopping after any step leaves the repo healthier" property v2 claimed for its waves,
this time without a P0 hidden in the easy part.

## 7. Divergences and how they were resolved

- **Ring-gating's eventual worth**: Gemini would build it (with budgets + 4.5-min presubmit
  target); Kimi calls it UNSOUND-as-sequenced; Codex gates it behind 8 preconditions. Resolution:
  it is not killed, it is RE-SEQUENCED (step 8) and must re-prove itself on post-R0-off shadow
  data. The Fable-side note: Gemini's 4.5-min presubmit target assumes selection precision this
  repo has not yet demonstrated — treat as aspiration, not acceptance.
- **Doctrine #2 wording**: Kimi demands the doctrine be rewritten ("paid at the point of
  attribution, then once more amortized at the serializer"); Codex keeps the queue as the
  correctness boundary and adds an economics clause. Resolution for the v3 spec: keep the queue
  as the NRSR authority (doctrine #1 survives untouched); replace "paid once" with "paid at
  attribution + amortized at the serializer; the only deletable payment is post-merge
  duplication" — matching what the system's own 12-week safety record actually validates.
- **Judge protection mechanism**: Gemini's `ref: main` checkout vs Codex's SHA-pinned required
  workflow. Codex's critique stands (main moves per merge; ref-pinning ≠ review-gated policy
  change), but its mechanism carries an unverified Enterprise entitlement ASSUMPTION.
  Resolution: entitlement check is an operator item; the fallback package is fully buildable
  today and is the default path.

## 8. §Meta-pattern (the malattia-delle-malattie)

Kimi's closing line is the second-order finding, and both other families circled the same
object from different sides: **the system was about to trade attributed, redundant, pre-queue
proof for unattributed, batched, post-hoc proof at exactly the moment its authors stopped
testing locally (#4142) and its suite started compounding ungoverned.** Every open P0 in the
v2 plan is a shadow of that one trade: F1 (the skip that removes the queue's authority), F3
(the judge that would decide what not to prove, modifiable by the judged), F5/agy-F2 (an organ
racing the very serializer it must pass through), F7/agy-F3 (retries and ejections that cannot
be attributed to anyone).

One level deeper: **every optimization on the table attacked the LEVEL of the cost curve;
the disease is its DERIVATIVE.** No organ owns d(suite-cost)/dt — the suite grew +60% in five
weeks through the exact weeks the organism spent optimizing run counts. The same shape as W106
(a cure anchored to a frozen measurement of the world): a capacity plan tuned to an 18-minute
suite is wrong by construction against a suite that re-measures itself upward every week.
The v3's first structural organ is therefore a GOVERNOR (budget + owner + alarm on the
derivative), not another optimizer of the level.

And a loop-hygiene observation for CAPTURE: the 08-10 BLOCK verdict was correct on the day it
was issued and materially stale four days later — three of its findings were already cured, one
seat it declared dead is alive, and the plan's own safety premise (R0) had been inverted by an
unrelated PR. **A refutation is a snapshot, not a standing fact**; any future disposition doc
must re-date every finding against origin/main before disposing it (this document's §1 exists
for that reason).

## 9. §Solo-operatore

- **TELEGRAM_BOT_TOKEN rotation in Actions secrets** — `operator[secret]`, already ledgered
  (W102): still the prerequisite for every alarm this system will emit.
- **Ruleset entitlement check** — `operator[gui]`: does org Bali-Zero's plan expose "require
  workflows to pass" rulesets (Enterprise-tier per docs)? Decides F3's mechanism (pinned
  workflow vs fallback package).
- **Removing counts from README/INDEX/AI_ONBOARDING** — touches the public face of the repo
  and the AI-onboarding contract: doctrine sign-off (Legge 5) before step 4 deletes them.
- **Cloud agent scale-out GO** — `operator[business]`: sequenced last (step 9); when its
  preconditions are green, the go/no-go and budget are Zero's.
- **Kimi seat status in CLAUDE.md §5** — the "dead on both machines" record is stale (alive on
  M5 today); the standing PENDING-ARMS item (retire explicitly or fix the doc) can now resolve
  in the "alive" direction.

## 10. References

Transcripts: `research/operations/refutations/2026-08-14-mergeos-v3-{codex,kimi-k3,agy-gemini}.txt`.
Predecessors: v2 spec + §8 verdict (2026-08-10), round-3 system-wide (2026-08-10), v1 draft
(refuted). Ledger: PENDING-ARMS.md:901-907. Scars carried: W65 (refuter hallucinates → every
seat re-grounded), W100 (seat parentage declared), W111 (stale rejection → §1), W106 (frozen
measurement → §8), W86/W88/W102/W104 (inherited via v2). Cicatrix family for this session's
near-miss: none opened — no wave was armed, nothing broke.
