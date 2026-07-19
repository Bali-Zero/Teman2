---
date: 2026-07-19
domain: operations
client_case: none
sources: [live GitHub API probes 2026-07-19, GPT-5.6 Sol ultra independent research, Kimi K3 independent research, Fable orchestrator analysis, prior captures 2026-07-17 push-pipeline-optimization-spec / merge-queue-readiness-manifest / backend-suite-sharding-investigation]
---

# PR-queue acceleration — 3-seat independent research, adversarial synthesis

Date: 2026-07-19 · Mandate: Zero ("troppa coda PR — accelerarla senza perdere qualità/sicurezza")
Seats (INDEPENDENT — none read the others before writing): **GPT-5.6 Sol (ultra, read-only sandbox)** · **Kimi K3 (Moonshot)** · **Fable (orchestrator, grounded live)**. Synthesis + arbitration: Fable (final gate). Raw verdicts: appendices A-C.

## 0. Measured ground (2026-07-19, live probes — not impressions)

- Median pipe is FAST: 200 PRs merged in 7d = 28.6/day; created→merged p50 0.5h, p75 0.9h, p90 3.3h, max 21.9h; 176/200 < 2h.
- 36 open PRs; ~10 fresh (<8h, healthy in-flight), ~26 aged 28-145h.
- Probed anatomy of the aged pool: **green-but-unarmed** (#2513: 45/45 checks green, auto-merge never armed, 75h; part of a ~10-PR dependabot batch) · **bot-vs-R1 deadlock** (#2484 nb-health cron PR, armed 85h, fails "R1 gate — adversarial review present" forever; class GROWS +1-2/day) · **red-failing dependabot** (#2383 145h DIRTY + 3 red; majors like prisma 6→7) · **derived-docs treadmill** (#2626, 41h, conflicts only on the 2 derived docs; spawns repair-PRs #2828/#2830) · legit WIP (~5-6).
- Burst saturation observed live: 17 queued + 16 pending Actions runs vs 7 completed (last 40) during a 10-PR overnight wave. 25 required contexts/PR.
- branch protection `strict=false` (branch need NOT be up to date to merge) — the treadmill is NOT strict-mode; it's the two committed derived artifacts + real conflicts.

## 1. The unifying diagnosis (3/3 convergent, Sol's formulation sharpest)

**Healthy WIP** at this throughput ≈ 1.19 merges/h × 3.3h p90 ≈ **4 PRs. We hold ~26 aged = 6.6× healthy WIP.**
The PR lifecycle is an **incomplete state machine: several states are ABSORBING and own-erless** — green-but-unarmed, R1-deadlocked, red-bot-rot, conflict-treadmill. No receptor owns them, so PRs fall in and never leave. Speeding up CI does not drain an absorbing state.

**§Meta-pattern (the malattia-delle-malattie):** this is cicatrix family #2 (Esiste≠Armato / W81) expressed at the PR-lifecycle level — *built-but-not-armed, armed-but-never-mergeable, red-but-unowned*. Every stuck class is an unowned terminal state. The cure class is always the same: give the state an owner (receptor/steward) + make the state visible (census/dashboard) + close the loop (arm/triage/convert). The same defect generated the queue pool, the cron zombie growth, and historically the ~20 dead cron jobs of W81.

## 2. Panel verdict matrix

| Lever | Sol | Kimi | Fable | ARBITRATION (final gate) |
|---|---|---|---|---|
| Bot-PR steward (arm-on-green + triage) | #1, event-driven App + reconciler, observe-first | #1, 20-min sweeper + arm-at-creation upstream | #1, drain + policy | **ADOPT** — sweeper/steward, observe-first 48h, then arm minor/patch-only; majors NEVER auto-armed (W98 class). Arm-at-creation fix in bot lanes. |
| Census/dashboard first | Decision GATE day 1-2 | dashboard in sweeper | receptor >48h in organismo feed | **ADOPT as gate**: day-1 census decides magnitudes before mutations; then live straggler dashboard (class breakdown) in the sweeper + organismo feed. |
| Cron reports → artifacts/data branch | #1 of missing levers | Track 1, "deletes the class" | preferred for pure reports | **ADOPT** — pure-report crons stop opening PRs (kills the only UNBOUNDED growth term). Consumer-map BEFORE migration (W82). |
| R1 for main-destined regen PRs | **REJECTS path-only waiver** ("keeps the check's name, kills its substance") → separate Grader identity, different LLM family, real verification | mechanical path-scoped waiver, denylist-wins; LLM review of deterministic regen = "theater" | two-track, artifacts-first | **Sol's substance wins, our mechanics**: no path-only waiver. Residual regen PRs get a real bot-lane R1: a different-family LLM lane re-runs the generator in a clean env, byte-compares, checks diff scope, posts the R1 review. Honest generator≠grader, cheap because the verification is deterministic. Deterministic validator = ADDITIONAL check, never the grader. |
| Dependabot config | grouping + majors isolated + security separate + circuit breaker | grouping (250→25-50 check-runs/cycle) + stagger | grouping + weekly | **ADOPT ALL**: weekly grouped minor/patch per ecosystem (staggered off-peak), majors individual, security individual + never auto-closed, per-ecosystem circuit breaker. |
| Red-bot triage | close-from-DIAGNOSIS (not age), issue for real regressions, receipts | close >72h red + recreate semantics | close majors w/ ledger | **ADOPT Sol's**: diagnosis-based, one rerun per SHA for allowlisted infra signatures, one rebase per real conflict, receipts always, security quarantined never closed. |
| Cancel-in-progress superseded runs | yes, per workflow+PR, never main/merge_group | yes, "ship today" | yes | **ADOPT day 1** (3/3, identical design). |
| Derived docs OUT of feature PRs | E: single-writer, content-addressed, dual-read transition | P-B: main-side regen, "treadmill is a CAPACITY problem" | refresh-organ owns all counters | **ADOPT** — post-P3′: feature PRs stop carrying INDEX/inventory/counters; single-writer regen lane on main (auto-armed PR through the bot R1 lane, NOT direct push — I5). Repair-PR class dies. |
| Merge queue (P2) | **NOT NOW**: ~5,000 extra required-context executions/week ≈ a second suite per PR; MQ does NOT kill the textual treadmill (ejection/rebuild instead); measure stale-base incompatibility rate `s` first; canary 50→200 entries, promotion thresholds defined | **AGAINST now, possibly never**: ≥715 extra check-runs/day; the hole it closes is unmeasured; cheap substitute = base-freshness advisory | DEFER; revisit at 2-week mark | **DEFER — unanimous.** Preconditions unchanged (manifest + step-equivalence canary + ejection watcher). Decision input = measured `s` (stale-green incidents/60d) + A_CI headroom. Cheap substitute meanwhile: base-freshness advisory (non-required). |
| Self-hosted runners on the Macs | only ephemeral/JIT VM, no secrets, synthetic fixtures, post-merge/non-required first | GO pilot week 2 — **on the false premise the repo is private** | **NO — repo is PUBLIC** | **REJECTED for required PR checks while the repo is public** (fork-PR arbitrary code on PII-holding production Macs; GitHub's own guidance). Revisit ONLY if repo goes private; then Sol's ephemeral-VM conditions are the bar. Kimi's premise error recorded (see §5). |
| Larger runners ($) | pilot 20 PRs, hard $10 budget, ARM 8-core ≈ $5 | separate concurrency pool from standard cap (saturation relief) | Legge-5 money decision | **PILOT under operator authorization** (Legge 5): backend job on 8-core ARM, 20-PR A/B, hard budget, measure speed-up ≥30% to adopt. |
| Admission control / lane budgets | ready-intent + admission broker K=floor(0.8×C/j95) + security slot, observe-first | PR budget N=3/lane + stagger crons | stagger + P6 lock adjacency | **ADOPT the light version now** (lane budget N=3 + cron stagger); Sol's full broker ONLY if waves persist in metrics after week 1 (over-engineering otherwise — his own observe-first gate concedes this). |
| Workflow consolidation | run-records ≠ runner-jobs; real 25→8 needs trusted check-publisher (bigger fault domain, shadow 100 SHAs, NOT week 1) | fast-gates job (lint family) add-then-remove | staged, REF-BREAKAGE care | **Fast-gates tranche only** (real job-count drop, low risk, add-then-remove migration); check-publisher DEFERRED. |
| TTL >7d idle | yes, receipts, non-security only, time decides hygiene never validity | yes, dry-run first, exclusions | yes | **ADOPT week 2** with Sol's exclusions. |
| Auto-update-branch bots | reactive-only (one rebase per real conflict) | anti-recommend blanket ("the treadmill generalized"); conflict-only rebase bot | — | **Conflict-only rebase lane** (serialized, oldest first). Blanket auto-update REJECTED 3/3. |
| Stacked PRs / trunk+flags / batch windows | deps-only / selective / no (concentrates arrivals) | reject / reject-I5 / poor-man's-MQ optional | reject | **REJECTED** for this repo (agent lanes at 3am fumble stacks; I5; windows concentrate bursts). |

## 3. The plan (sequenced, rollback per step)

**Phase 0 — census gate (day 1-2, zero mutation):** full census of the 36 (state, head SHA, author, R1, checks, conflict, auto-merge) → if hypothesized classes explain <30% of aged pool, re-rank before acting. Baseline the 3 metrics. Verify GitHub plan/concurrency cap + which token the cron PRs use (Sol's #2484 mechanism hypothesis: `GITHUB_TOKEN`-created PRs can sit approval-required — TO VERIFY, labeled hypothesis).
**Phase 1 — drain + stop the growth (day 2-4):** steward observe-only 48h → arm the verified-green minor/patch; triage reds (diagnosis-based, receipts); pause/convert the pure-report cron PR creation (artifacts/data branch, consumer-map first). Cancel-in-progress on all PR workflows. Dependabot config (grouping/majors/security/circuit-breaker). Lane budgets + stagger.
**Phase 2 — structural (day 5-10):** bot-lane R1 (different-family verification lane) for residual regen PRs; derived docs out of feature PRs (single-writer regen lane); fast-gates consolidation; caching timing measurement; larger-runner pilot (operator-gated $).
**Phase 3 — decide with data (day 10-14):** TTL live; measure `s` (stale-green incidence 60d); merge-queue go/no-go with A_CI headroom + Sol's promotion thresholds; full admission broker only if waves persist.

**Metrics (Sol's definitions adopted — subsume the others):**
1. **S24** = open non-draft PRs older than 24h, sampled daily 08:00, no label exclusions. Target: 26 → ≤6 by day 7, ≤3 by day 14.
2. **T90** = p90 of (mergedAt − readyIntentAt) rolling 7d — latency may never be "improved" by hiding waits outside GitHub. Target ≤2h by day 14. Guard: main-breakage rate (reverts/fix-forwards per week) must not rise.
3. **A_CI** = all runner-minutes (pull_request + merge_group incl. cancelled/rerun) ÷ merged PRs, rolling 7d. Target −25% pre-MQ; any MQ future must project ≤1.5× baseline.
Kill-condition (not a metric to average): any I1-I6 violation or false R1 attestation.

## 4. §Solo-operatore (Legge 5 — decisions only Zero can make)

1. **Larger-runner spend** (per-minute $; pilot ≈ $5-10, steady-state ≈ order of $100-250/month if adopted) — authorize or defer.
2. **Bot-lane R1 policy ratification** — extending the R1 gate's satisfiers (even honestly) touches the generator≠grader constitution; the design above preserves substance (real different-family verification), but the constitution change is Zero's to ratify.
3. **Auto-arm policy for dependency bumps** (minor/patch only, W98 tripwire required in the gate set) — supply-chain posture call.
4. **Repo visibility** — self-hosted runner economics only exist if the repo ever goes private; not recommended to change for this reason alone.
5. **Merge-queue go/no-go at day 14** — with the measured `s` and A_CI data in hand.

## 5. Panel meta-record (for the ledger)

- Independence held: Fable's analysis written to disk BEFORE reading either seat; Sol/Kimi never saw each other or Fable.
- Convergences 3/3: state-machine diagnosis · steward-first · reports→artifacts · derived-docs-out · MQ-defer · cancel-in-progress · grouping · TTL-with-receipts · census-first.
- Arbitrated divergences: R1 waiver (Sol's reject upheld — substance over mechanics); self-hosted (rejected — Kimi's GO stood on a false "private repo" premise; the conductor caught it from grounded memory: the repo is PUBLIC. W100 lesson live: cross-family seats + grounded conductor catch what any single seat misses); admission broker (Sol's design adopted only as contingency — anti-sperpero).
- Sol uniquely contributed: WIP math frame · check-source identity binding (anti-spoof) · GITHUB_TOKEN/approval-required hypothesis for #2484 · A_CI amplification metric with MQ kill-threshold · close-from-diagnosis triage.
- Kimi uniquely contributed: treadmill-as-capacity reframe with CI-burn estimate · larger-runners-separate-pool fact (TO VERIFY on our plan) · arm-at-creation upstream fix · base-freshness advisory substitute.
- Fable uniquely contributed: live probes (the anatomy itself) · strict=false discovery · R1-passes-dependabot-but-not-cron observation (mechanism TBV) · unbounded-growth-term prioritization · W98/W92/W100 scar wiring.

## Appendix P — shared research prompt

(shared prompt given verbatim to all three independent seats — context, not seat output)

<details>
<summary>Shared research prompt (verbatim)</summary>

# DEEP RESEARCH TASK — accelerate the PR queue of a high-throughput agent-driven monorepo WITHOUT losing quality or safety

You are one of three independent researchers (the others: a different frontier LLM and the repo's orchestrator). Do NOT hedge toward consensus — produce your own strongest analysis. Your output will be adversarially compared with the others.

## Context: the repo and its ship model

- Monorepo (`Balizero1987/Teman2`, GitHub), solo human owner, but ~5-15 CONCURRENT AI agent sessions across 3 Macs open PRs around the clock. The human never reviews/merges — sessions review each other (generator≠grader: every PR needs an adversarial review by a DIFFERENT LLM family, enforced by a required check called "R1 gate — adversarial review present").
- Merge policy: PR-only to main, 25 REQUIRED status contexts (backend suite ~18 min is the longest; also CodeQL python+js, docs gates, security scans, frontend tests, actionlint, etc). Branch protection strict mode = FALSE (branch does NOT need to be up-to-date with main to merge). Auto-merge (squash) is the standard arming mechanism.
- Two committed DERIVED artifacts (INDEX.md, docs/DOCS_INVENTORY.md + AI_ONBOARDING counters) are regenerated by gates; PRs touching overlapping surfaces conflict on them repeatedly (the "derived-docs treadmill").
- GitHub-hosted runners (paid plan), concurrency-capped. 21 workflows produce the 25 required contexts + extra non-required jobs.

## MEASURED STATE (2026-07-19, real data — trust these numbers)

Throughput is NOT the problem for the median PR:
- Merged last 7 days: 200 PRs = 28.6 merges/day.
- created→merged latency: p50=0.5h, p75=0.9h, p90=3.3h, max=21.9h. 176/200 merged in <2h.

The problem is a STANDING POOL of stragglers + burst saturation:
- 36 open PRs right now. Age distribution: ~10 fresh (<8h, actively merging), the rest 28h-145h old.
- Straggler anatomy (probed individually):
  - **Green-but-unarmed**: e.g. dependabot #2513 has 45/45 checks GREEN but auto-merge was never armed — sat 75h. A ~10-PR dependabot batch (74-145h old) is partly in this class. Nobody's job is to arm bot PRs.
  - **Bot-PR vs R1-gate deadlock**: cron-generated report PRs (e.g. nb-health #2484, armed, 85h) fail the required "R1 gate — adversarial review present" check FOREVER because the generating cron never produces an adversarial review. Armed + never mergeable = zombie.
  - **Red-failing dependabot**: e.g. #2383 (145h, DIRTY + 3 red: cross-import integrity, Snyk, frontend tests), #2698 (2 red). No triage lane owns them.
  - **Derived-docs treadmill victims**: e.g. #2626 (41h): only conflict surface is the 2 derived docs, re-conflicts every ~15-20 min as main moves. A repair-PR pattern also EXISTS (e.g. "regen DOCSYNC counters — repair stale left by #NNNN"): the treadmill spawns EXTRA PRs.
- Burst saturation measured NOW: GitHub Actions shows 17 queued + 16 pending runs vs 7 completed in the last 40 — a fresh 10-PR wave from overnight agent lanes saturates runner concurrency; wall-clock per PR balloons far beyond the nominal ~18 min critical path.

## PRIOR WORK (already done — do NOT re-derive; build on it or attack it)

A 3-LLM-reviewed spec (2026-07-17) already shipped these:
- **P1 path-aware pre-push (LIVE)**: local backend suite (17.5k tests, 7-30 min) skips for allowlisted-innocent diffs, fail-closed to full on anything unknown. Local push latency for docs/infra PRs: ~30min → ~1min. CI untouched.
- **P3′ deterministic docs gate (PR #2626, landing)**: the inventory gate becomes a pure function of the tree (no wall-clock rot); date-crossing moves to a scheduled refresh organ with liveness guard.
- **P6 push ticket-queue lock (designed, pending)**: replaces pgrep quiet-window polling for LOCAL suite serialization.
- **P2 GitHub merge queue (mapped, NOT enabled)**: a 25-context readiness manifest exists; known hazards mapped by a 3-LLM panel: (a) jobs conditioned on `pull_request` silently SKIP on `merge_group` yet report success → weaker green at merge; (b) path-filtered workflows stay PENDING and wedge the queue; (c) queue ejection is silent → bots must watch and re-queue; (d) speculative bisection can cost MORE CI than today. Preconditions: step-level equivalence canary, ejection watcher, REF-BREAKAGE fixes.
- **Sharding investigation (done)**: pytest-xdist local sharding = GO-TO-HARDENED-PILOT but modest gains; 2 prerequisite bugs identified.

## INVARIANTS (violating any = automatic rejection)

I1. CI required checks are never weakened, removed, path-filtered, or made conditional — the merge-time safety net stays identical or gets STRONGER.
I2. Fail-closed on errors everywhere.
I3. Every skip/fast-path is loud (logged with reason).
I4. New guards ship with guilt+innocence tests, CI-armed.
I5. Merge remains PR-only with required checks; no direct-to-main, no admin bypass.
I6. No time-keyed caches; content/SHA-keyed state only.
Also: generator≠grader must survive (a bot cannot rubber-stamp its own PR); the R1 adversarial-review requirement must survive IN SUBSTANCE (its mechanics may change).

## YOUR RESEARCH QUESTIONS

1. **Root-cause ranking**: given the measured anatomy (green-but-unarmed, bot-vs-R1 deadlock, red-bot rot, treadmill, burst saturation), rank the levers by expected reduction in queue size and PR age. Show your reasoning about magnitudes.
2. **Queue-hygiene policy design**: design the missing policies — (a) who/what arms green bot PRs (auto-arm-on-green? a sweeper cron? risks?); (b) how should the R1 gate treat AUTOMATED report/regen PRs without weakening generator≠grader for real code (options: bot-lane R1 waiver with path-scoped allowlist? a reviewer-bot that actually performs adversarial review? convert cron outputs from PRs to artifacts/branches?); (c) a triage lane for red bot PRs (auto-close stale dependabot? batch weekly?).
3. **Burst-capacity engineering**: 25 required contexts × 10-PR waves vs concurrency cap. Attack: workflow consolidation (fewer, fatter jobs — same coverage, fewer queued units), concurrency-group cancellation of superseded runs, caching, sharding IN CI, self-hosted runners on the idle Macs (they're 10-24-core Apple Silicon, mostly idle at night — safety analysis needed: secrets exposure, PII boundary, untrusted-PR code execution), scheduling (stagger agent lanes), GitHub larger runners ($). What's the highest-leverage, safest combination?
4. **Merge queue under THIS anatomy**: with strict=false and the burst pattern, does GitHub merge queue still pay? It serializes merges and re-runs checks on merge_group (MORE runner load), but kills the treadmill and closes the stale-green-merge hole (a PR green on an old base can merge today — logical conflicts slip through). Argue FOR or AGAINST flipping it now vs after capacity fixes, quantitatively if you can.
5. **What are we MISSING?** Structural alternatives: stacked PRs, batch/merge windows, trunk-based with feature flags, auto-update-branch bots, required-context consolidation (25→fewer contexts with identical coverage), PR budget/rate-limits per agent lane, TTL policies (auto-close PRs idle >7d with re-open receipt), replacing cron-report PRs with a data branch or artifact store. For each: safety analysis against the invariants.
6. **Sequencing**: a concrete 2-week rollout order with rollback points, and the 3 metrics to watch (define them precisely).

## OUTPUT FORMAT

Markdown. Sections: (1) Root-cause ranking with magnitudes; (2) Proposals — each with: design, safety-vs-invariants analysis, expected gain, failure modes, kill-switch; (3) Merge-queue verdict; (4) Missing levers; (5) 2-week sequencing; (6) Top-3 risks of YOUR OWN plan (self-red-team). Be concrete and quantitative. Do not pad. If you disagree with the prior work's conclusions, say so with reasons.

</details>

## Appendix A — GPT-5.6 Sol (ultra) verdict, verbatim

(raw seat output — leads, not conclusions; arbitration lives in the synthesis)

**Verdetto:** non ottimizzerei ulteriormente il PR mediano. Il problema principale è una macchina a stati incompleta: alcuni PR entrano in stati terminali senza proprietario. Per i burst, la prima cura è controllare l’ammissione e cancellare lavoro obsoleto; la merge queue va attivata solo dopo aver creato headroom CI e rimosso gli artifact derivati dalle feature PR.

## 1. Root-cause ranking with magnitudes

Con 200 merge/settimana, il flusso medio è 28,6/giorno = 1,19/ora. I circa 26 PR più vecchi di 24 ore equivalgono a **21,8 ore dell’intero throughput normale**.

Se il sistema sano avesse un WIP coerente col p90 di 3,3 ore, ci aspetteremmo circa:

`1,19 merge/ora × 3,3 ore = 3,9 PR`

Averne ~26 significa **6,6× il WIP sano**. Non è una coda lenta: sono PR finiti in stati assorbenti.

| Rank | Leva | Magnitudine sullo stock attuale | Ragionamento |
|---|---|---:|---|
| 1 | Lifecycle ownership per Dependabot: green-unarmed + red triage | Batch noto di ~10 PR = fino al 38% dei ~26 aged | Un solo steward può armare quelli realmente verdi e classificare/chiudere/quarantinare quelli terminalmente rossi. Planning range: 4–8 rimozioni immediate, da confermare col censimento Day 1. |
| 2 | Correggere il deadlock R1 per PR automatici | Minimo verificato: #2484; totale non misurato | Ogni PR in questa classe ha latenza infinita: aumentare capacità CI non cambia nulla. Inoltre consuma CI a ogni update senza possibilità di merge. |
| 3 | Rimuovere i derived artifacts dalle feature PR | Minimo: #2626 + repair PR indotti | P3′ elimina il wall-clock rot, ma non il conflitto testuale. Se main cambia ogni 15–20 minuti e CI dura ~18, inseguire main opera vicino o oltre il punto d’instabilità. |
| 4 | Admission control e capacità burst | Circa 10 PR freschi; 250 required-context instances per onda | È la prima leva sul p90 durante i burst, ma non fa sparire nessuno dei PR zombie vecchi. |
| 5 | Merge queue | Zero riduzione diretta prima della pulizia | Chiude il rischio stale-green, ma aggiunge una seconda suite e trasforma i conflitti derivati in ejection/rebuild. |

Le magnitudini non sono additive: il batch Dependabot contiene sia green sia red. Una stima ragionevole è che le policy di hygiene possano disporre **6–12 dei 26 aged** nella prima settimana; il numero va sostituito dal censimento esatto, non trattato come dato misurato.

Come corroborazione storica, non come fotografia corrente, casi di fine giugno mostrano sia major Dependabot deterministically incompatibili sia gate docs che diventavano rossi per inventory drift estraneo alla modifica.

## 2. Proposals

### A. Queue Steward: event-driven auto-arm più reconciler

**Design.** Un GitHub App indipendente mantiene questa macchina a stati:

`DISCOVERED → CLASSIFIED → R1_VALID → CI_GREEN → ARMED → MERGED`

con uscite esplicite verso `QUARANTINED`, `SUPERSEDED` e `CLOSED_WITH_RECEIPT`.

L’arming avviene quando:

- head SHA coincide esattamente;
- PR non è draft/hold;
- autore è l’App/bot atteso, verificato per App ID;
- classificazione path/semver è consentita;
- tutti i 25 required contexts sono success, provenienti dalle App attese;
- R1 è valido per lo stesso head SHA e canonical diff hash.

Primario: webhook su check/PR completion. Secondario: reconciler ogni 5–10 minuti per recuperare webhook persi. Lo sweeper non “decide” diversamente: riesegue la stessa funzione pura. GitHub auto-merge resta il solo meccanismo di merge e continua ad attendere le protezioni richieste.

**Safety vs invariants.**

- I1/I5: nessun check rimosso e nessun bypass.
- I2: stato sconosciuto, API error, check duplicato o SHA mismatch ⇒ non armare.
- I3: ogni decisione produce receipt con SHA, regola e motivazione.
- I4: fixture “innocence” green e “guilt” per stale SHA, actor spoof, missing R1, red check e unexpected path.
- I6: autorizzazione keyed da head SHA + diff hash + policy hash; mai da età o timestamp.
- Le label sono soltanto UI, mai fonte d’autorità.

**Expected gain.** Green-to-armed lag da ore/giorni a ≤10 minuti. #2513 diventerebbe impossibile come stato persistente. La riduzione corrente dipende dal numero verde dentro il batch: upper bound 10, planning range 4–8.

**Failure modes.** Webhook perso, status omonimo proveniente dall’App sbagliata, check riferito a SHA vecchio, loop di retry.

**Kill-switch.** `QUEUE_STEWARD_MODE=observe|arm|off`; credenziali senza admin/bypass; disabilitazione dell’App lascia semplicemente i PR non armati.

---

### B. R1 per automation: nessuna waiver path-only

La waiver “se tocca soltanto report/docs, R1 passa” va rifiutata: preserva il nome del controllo ma elimina generator≠grader in sostanza.

**Design, in ordine preferenziale.**

1. **Report osservazionali non destinati a main:** pubblicarli come artifact content-addressed o su un branch `reports` protetto e single-writer. Nessun PR, nessun merge in main, nessun R1 necessario.
2. **Dati runtime:** object store/data branch con manifest firmato e SHA; main contiene soltanto schema/consumer.
3. **Regen che deve realmente entrare in main:** R1 eseguito da un Grader App separato, con diversa famiglia LLM, credenziali separate e permessi `contents:read`, `checks:write`; nessuna capacità di push.
4. Il deterministic validator resta un controllo addizionale, non il grader.

L’evidenza R1 deve includere:

- head SHA e canonical patch digest;
- generator App ID;
- famiglia e versione del reviewer;
- rubric/policy hash;
- findings e verdict.

GitHub consente di vincolare i required checks alla sorgente attesa; inoltre la creazione di check runs è riservata alle GitHub Apps, adatta quindi a un grader con identità separata. [GitHub Checks API](https://docs.github.com/en/rest/checks/runs)

Va anche auditato come sono creati i cron PR: quelli creati con `GITHUB_TOKEN` possono lasciare i workflow in stato approval-required; GitHub indica App installation token o PAT come meccanismo per automation senza quell’approvazione. È un’ipotesi da verificare, non la causa già dimostrata di #2484. [GitHub `GITHUB_TOKEN`](https://docs.github.com/en/actions/concepts/security/github_token)

**Safety vs invariants.** R1 sopravvive per ogni modifica a main; il lane routing può essere path-scoped, il verdetto no. Reviewer indisponibile ⇒ R1 failure, non neutral/success.

**Expected gain.** Almeno #2484 viene sbloccato o eliminato come PR. Per ogni report spostato fuori da main si risparmiano `25 × R` required-context instances, dove `R` è il numero di report PR per periodo.

**Failure modes.** Falsa separazione tra generator e grader, output non più reperibile, consumer nascosto che dipende dal file in main.

**Kill-switch.** `R1_AUTOMATION=off`; dual-publish legacy+artifact durante la migrazione; in caso di errore il PR resta bloccato.

---

### C. Red-bot triage lane

**Design.**

- Un solo rerun per head SHA, esclusivamente per signature infrastrutturale allowlisted.
- Un solo rebase per conflitto reale; mai update periodico “per restare fresco”.
- Patch/minor verdi e R1-valid ⇒ arm.
- PR superseded, duplicate, package removed o resolver-proven-unsatisfiable ⇒ chiusura con receipt e comando di ricreazione.
- Red riproducibile non-security ⇒ issue di remediation; chiusura dopo 24–48 ore dalla diagnosi, non dalla sola età.
- Security update ⇒ mai auto-close per TTL; resta quarantinato con severity, owner-agent e remediation receipt.
- Major update sempre isolato.
- Routine update raggruppati settimanalmente per ecosystem compatibile; security giornalieri e separati. Dependabot supporta grouping, schedule e limiti agli open PR. [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)
- Circuit breaker per ecosystem: sospendere i nuovi non-security dopo 3 red terminali consecutivi oppure ≥50% red negli ultimi 10, con almeno 5 campioni.

**Safety vs invariants.** Nessun rosso viene trasformato in verde. Il close è reversibile e lascia prova durable; la security lane non viene occultata.

**Expected gain.** Disposizione della parte rossa del batch ~10; planning range 2–6 PR, ma il censimento deve separare incompatibilità reali da CI infra.

**Failure modes.** Raggruppare dipendenze incompatibili, classificare una regressione come infra, cosmeticamente ridurre la queue chiudendo lavoro ancora necessario.

**Kill-switch.** `DEPENDABOT_STEWARD=observe|triage|off`; circuit breaker non si applica alle security alerts.

---

### D. Burst-capacity stack

La combinazione più sicura, in ordine:

| Layer | Design | Gain atteso |
|---|---|---:|
| Admission broker | Ogni agent emette un `ready-intent` SHA-keyed. Ammessi simultaneamente `K = floor(0,8 × C / j95)`, con uno slot riservato alla security. | Con K=2, una wave di 10 passa da 250 a 50 context instances inizialmente attive: −80% fan-out istantaneo. |
| Cancel obsolete SHA | `concurrency.group = workflow + PR number`, `cancel-in-progress` solo su `pull_request`; mai su `main` o `merge_group`. | Recupera tutti i runner-minuti residui delle revisioni superseded. GitHub supporta esplicitamente questa cancellazione. [Concurrency groups](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) |
| Exact caching | Chiavi con OS, architettura, toolchain e lockfile hash; cache miss esegue il percorso completo. | Se setup/dependency install è 3–6 dei 18 minuti, saving teorico 17–33%; va prima misurato. |
| In-job xdist | Parallelismo dentro un runner 8+ core, dopo i due prerequisite fix già individuati; niente nuova matrix. | Riduce il critical path senza moltiplicare job concorrenti. |
| Larger runner pilot | Solo backend, 20 PR, budget hard di $10. | 20×18 min costerebbero $7,92 su Linux x64 8-core o $5,04 su ARM 8-core prima dello speed-up. Larger runners richiedono Team/Enterprise. [Pricing](https://docs.github.com/en/enterprise-cloud@latest/billing/reference/actions-runner-pricing) |
| Self-hosted | Inizialmente soltanto trusted post-merge/non-required work. Required CI solo dopo isolamento e shadow validation. | Pochi runner bare aggiungono soltanto pochi slot; il vantaggio vero sarebbe usare i core per in-job parallelism. |

Il limite corrente va letto live: la documentazione attuale indica 40 job per Pro e 60 per Team e consente di chiedere un aumento al Support, ma il piano/account effettivo non è stato verificato qui. [GitHub Actions limits](https://docs.github.com/en/actions/reference/limits)

**Workflow consolidation.** Ridurre 21 workflow files a 5 riduce i run records, non necessariamente i runner job. Per passare da 25 a, per esempio, 8 executor jobs mantenendo tutti i 25 required contexts, servirebbe un trusted check-publisher che riporti ogni componente separatamente; un crash deve segnare failure o lasciare pending, mai success. Questo ridurrebbe i job della wave da 250 a 80, ma aumenta il fault domain. Va shadowato per almeno 100 SHA, non spedito nella prima settimana.

**Self-hosted safety.** Nessun persistent runner direttamente sui Mac con Keychain, SSH, OAuth, PII o accesso LAN. Accettabile soltanto:

- VM effimera/JIT, un job e wipe;
- nessun host mount, Docker socket, Keychain o home directory;
- niente secrets/OIDC, `GITHUB_TOKEN` read-only;
- synthetic fixtures, pinned actions, egress allowlist;
- log esportati prima del wipe.

GitHub raccomanda self-hosted ephemeral, un job per runner, con cleanup e log esterni. [Self-hosted runners](https://docs.github.com/en/actions/reference/runners/self-hosted-runners) Anche le cache vanno trattate come input non fidato e non devono contenere segreti. [Cache security](https://docs.github.com/en/actions/concepts/workflows-and-actions/dependency-caching)

**Safety vs invariants.** Ogni SHA finale esegue comunque tutti i 25 controlli. Si cancella soltanto lavoro riferito a SHA ormai impossibile da mergiare. Ogni admission/cancellation viene registrata.

**Failure modes.** Starvation, cancellation group troppo ampia, cache poisoning, job fat che nasconde risultati, self-host compromise.

**Kill-switch.** Broker bypassabile soltanto disabilitandolo per tutti, non per un singolo PR; `cancel-in-progress:false`; cache disattivabile; runner group self-hosted rimosso dalle label.

---

### E. Eliminate the derived-docs treadmill structurally

**Design.**

- Human-authored source docs restano in main.
- `INDEX.md`, inventory e contatori puramente derivati non vengono modificati dalle feature PR.
- CI mantiene gli stessi required checks, rigenera in ambiente pulito e valida schema, determinismo e output digest.
- L’output viene pubblicato content-addressed per il main SHA.
- Se un consumer richiede un checkout con i file generati, usare un branch generated single-writer o un bundle di release, mai farli competere dentro ogni feature PR.
- Durante la transizione: dual-read/dual-publish e inventario di tutti i consumer.

**Safety vs invariants.** Il controllo resta required e può diventare più forte verificando riproducibilità. Nessuna cache temporale: artifact e manifest sono keyed dal tree SHA/content hash.

**Expected gain.** Elimina almeno il conflitto di #2626 e la classe di repair PR. Ogni repair PR evitato risparmia una suite da 25 contexts.

**Failure modes.** Consumer che assume il file in main, retention insufficiente, single writer fermo.

**Kill-switch.** `GENERATED_DOCS_MODE=legacy|dual|artifact`; rollback al formato committed usando lo stesso generatore deterministico.

## 3. Merge-queue verdict

**Non abilitarla ora. Abilitarla dopo capacity headroom + derived-artifact removal + canary.**

### Costo

Ogni PR già esegue la suite sulla head. La merge queue richiede nuovamente i controlli sul `merge_group` applicato all’ultima base. A 200 merge/settimana:

- circa **5.000 required-context executions aggiuntive/settimana**;
- approssimativamente una seconda suite `D` per ogni PR riuscito;
- retry/ejection aumentano ulteriormente il moltiplicatore.

Per una wave di 10 PR e critical path di 18 minuti, il lower bound nominale è:

- build concurrency 1: 180 minuti;
- concurrency 2: 90 minuti;
- concurrency 3: 60 minuti;

escludendo queue wait e rebuild.

GitHub consente build concurrency 1–100, rimuove dalla queue i PR con failure/conflitto e ricostruisce i gruppi downstream. Saltare in testa provoca un rebuild completo. [Merge queue mechanics](https://docs.github.com/en/repositories/configuring-branches-and-merges/in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)

### Beneficio

Con `strict=false`, oggi non esiste una validazione garantita contro l’ultima base. Se il tasso reale di incompatibilità stale-base è `s`, la queue protegge circa `200 × s` merge/settimana. È un beneficio importante, ma `s` non è stato misurato.

Soprattutto: **la merge queue non elimina il treadmill testuale**. Un artifact derivato ancora in conflitto causa ejection; poi i gruppi successivi vengono ricostruiti. P3′ è necessario, ma finché il file resta multi-writer il problema non scompare.

### Preconditions e canary

Canary su branch protetto identico:

- tutti i 25 check su `pull_request` e `merge_group`;
- prova step-level, non soltanto check verde: GitHub documenta che un workflow path-skipped resta pending mentre un job conditionally skipped può apparire success; entrambe le semantiche sono pericolose in una queue. [Required-check behavior](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks)
- 50 ingressi, inclusa una wave da 10;
- build concurrency 1;
- “only merge non-failing” abilitato;
- nessun queue jump;
- watcher per ejection e un solo retry per infra signature.

Promozione soltanto con:

- 100% dei 25 context presenti dalle App attese;
- zero silent skip/REF breakage;
- infra ejection <2%;
- p95 ready-intent→merge non peggiore di oltre il 20%;
- CI amplification dentro il budget definito sotto.

In produzione: concurrency 1, poi 2 soltanto dopo sette giorni stabili.

## 4. Missing levers

| Leva | Verdetto | Safety analysis |
|---|---|---|
| Cross-machine PR admission budget | **Alta priorità** | Riduce il burst senza saltare CI. Deve registrare l’attesa prima dell’ammissione per non “nascondere” latency. |
| Intent registry + conflict-surface leases | **Alta priorità** | Prima di aprire PR, registra goal, head e touched surfaces. PR duplicati o concorrenti sugli stessi global artifacts vengono serializzati. Nessun impatto sui check. |
| Cron reports → artifact/data branch | **Alta priorità** | Rimuove PR senza valore di code promotion. Data branch bot-only, nessun executable/workflow, manifest firmato. |
| Auto-update-branch bot | **Solo reattivo** | Un rebase per conflitto reale o ejection. Blanket updating ogni main merge creerebbe un CI self-DDoS. |
| PR TTL >7 giorni | **Sì, con receipt** | Solo non-security, non-release e non-hold; chiusura con SHA, diagnosi e recreation command. Il tempo decide hygiene, non validità o cache. |
| Stacked PRs | **Solo dipendenze vere** | Rendono esplicito l’ordine ma ogni layer paga CI e gli update cascata possono aumentare il carico. |
| Batch/merge windows globali | **No** | Concentrano gli arrivi e peggiorano i burst. Utili soltanto per release settimanale Dependabot, poi rilascio sequenziale. |
| Trunk + feature flags | **Selettivo** | Utile per feature multi-PR: default-off, owner, expiry e test di entrambi gli stati. Sempre PR-only. |
| Literal 25→fewer required contexts | **Respinto** | Viola I1. Ammessa soltanto execution consolidation mantenendo tutti i 25 risultati e la stessa copertura. |
| Coalescing agent work | **Sì, ma per goal coerente** | Riduce il costo fisso per PR; non deve creare mega-PR con superfici non correlate o indebolire generator≠grader. |

## 5. Two-week sequencing

| Giorni | Rollout | Exit/rollback point |
|---|---|---|
| 1–2 | Census dei 36 PR per stato, head SHA, App, R1, 25 checks, conflict e auto-merge; baseline delle tre metriche; verificare cap/piano GitHub e token usati dai cron. | Nessuna mutazione automatica. Se le classi ipotizzate non spiegano almeno il 30% degli aged, rifare il ranking. |
| 2–3 | Queue Steward in observe-only; agent triage dello stock: armare gli effettivamente verdi, chiudere solo incompatibili/superseded con receipt, quarantinare security/red. | Audit di tutte le decisioni; una classificazione falsa blocca il rollout. |
| 3–4 | Auto-arm per Dependabot patch/minor e bot allowlisted, webhook + reconciler. | `MODE=observe` in un’unica modifica; zero bypass permissions. |
| 4–6 | Grader App separato; migrare il primo report puro a artifact con dual-publish. | Reviewer outage deve produrre R1 failure. Ripristino immediato del legacy consumer. |
| 5–7 | Dependabot grouping, major isolation, open limit e circuit breaker. | Disabilitare ecosystem per ecosystem; security lane mai sospesa. |
| 6–8 | Admission broker: 24h observe, poi K=2 + security slot. Abilitare cancellation superseded su due workflow canary, poi estendere. | Spegnere broker/cancellation se starvation o wrong-SHA cancellation. |
| 8–10 | Timing dei setup; exact caches; xdist shadow dopo i prerequisite fix. Richiedere aumento cap; larger-runner pilot soltanto con autorizzazione di spesa. | Cache off; pilot stop se speed-up p90 <20% o regressioni. |
| 10–12 | Rimuovere derived global files dalle feature PR o introdurre single writer; dual mode per i consumer. | Tornare a legacy generation senza cambiare i required checks. |
| 11–14 | Merge-queue canary da 50 ingressi e wave da 10; validazione `merge_group` step-level. | Go/no-go Day 14. Se una soglia fallisce, main resta su auto-merge attuale. |

### Le tre metriche

1. **Aged stock `S24`**  
   `count(open PR con now-createdAt > 24h)`, senza esclusioni per label.  
   Target: ≤6 al Day 7, ≤3 al Day 14.

2. **True ship latency `T90`**  
   p90 di `mergedAt - readyIntentAt` per la final head SHA, rolling 7 giorni. Include attesa locale, admission, R1, CI, arming e merge queue.  
   Target: ≤2 ore al Day 14; mai migliorare il dato spostando l’attesa fuori da GitHub.

3. **CI amplification `A_CI`**  
   Tutti i runner-minuti `pull_request + merge_group`, inclusi canceled/rerun/abandoned SHA, divisi per i PR merged nello stesso rolling window.  
   Target pre-MQ: −25% rispetto alla baseline 7 giorni. Una produzione MQ è ammessa soltanto se l’amplificazione proiettata resta ≤1,5× la baseline originale.

Qualsiasi violazione di I1–I6 o falsa attestazione R1 è un kill condition immediato, non una metrica da mediare.

## 6. Top-3 risks of my own plan

1. **Queue Steward e Grader diventano un’autorità ad alto blast radius.**  
   Un errore su SHA/source identity potrebbe armare molti PR. Mitigazione: App separate, least privilege, observe-first, labels non authoritative, policy hash e test guilt/innocence.

2. **Il backpressure può soltanto spostare o nascondere la coda.**  
   K=2 potrebbe lasciare agent pronti ma invisibili su GitHub o affamare lane lente. Il `ready-intent` antecedente all’admission e lo slot security sono indispensabili; senza quella telemetria non spedirei il broker.

3. **La stima 6–12 PR eliminabili è costruita da esempi, non da un censimento completo.**  
   Se Day 1 mostra che gran parte dei 26 aged appartiene ad altre classi, il piano di hygiene è sovra-ottimizzato. Per questo il census è un decision gate e non semplice osservabilità. Analogamente, 50 merge-group canary non stimano bene failure rari: prima del flip definitivo estenderei lo shadow sample verso 200 ingressi se emergono anche pochi ejection non spiegati.

## Appendix B — Kimi K3 verdict, verbatim

(raw seat output — leads, not conclusions; arbitration lives in the synthesis)

# Accelerating the PR queue of Teman2 — independent research report

## 1. Root-cause ranking with magnitudes

First, decompose the standing pool and the CI burn. Of 36 open PRs: ~10 fresh (healthy), ~26 stale. From the probed anatomy, my estimate of the stale pool's composition:

| Class | Est. count | Terminal? | CI burn while alive |
|---|---|---|---|
| Green-but-unarmed (mostly dependabot batch) | ~8–10 | Sits until someone arms | ~zero (checks done) |
| Bot-vs-R1 deadlock (cron report PRs) | ~2–4 | **Permanent** — every cron run adds another | re-arm churn, repair PRs |
| Red-failing bot PRs | ~2–4 | Sits until triaged | occasional rebase re-runs |
| Treadmill victims + spawned repair PRs | ~3–6 | Self-perpetuating | **huge** — full 25-context suite per rebase |
| Misc stalled agent PRs | ~5–8 | mixed | mixed |

Ranking levers by **expected reduction in queue size and age**:

**#1 — Arm-on-green sweeper (clears class 1, the largest single class).** ~10 PRs, 74–145h old, become mergeable within one sweeper cycle. This is the only class where the work is *done* and only a 30-line automation is missing. Expected: −8–10 open PRs in week 1, and it permanently removes the class. Cost: near-zero. Risk: near-zero (see §2a).

**#2 — Kill the derived-docs treadmill at the source (class 4).** Undercounted in the brief as a *latency* problem; it's actually a **capacity** problem. A PR re-conflicting every 15–20 min over 41h, if rebased even a tenth of those times, burns 25 contexts × dozens of full suites — plausibly rivaling the CI cost of *all normal merges that day*. And it spawns repair PRs (queue inflation) and rebase storms exactly during bursts. P3′ (PR #2626) fixes the gate determinism but not the *committed derived artifacts*; the full fix is getting INDEX.md / DOCS_INVENTORY.md / counters **out of the merge path** (regenerate on main post-merge, or on a schedule; PRs carry no derived diffs). Expected: −3–6 queue slots, one entire PR class eliminated, and the single largest CI-waste reduction available.

**#3 — R1-lane resolution for automated PRs (class 2).** Small count today, but it's the only class that is *absorbing*: without a fix the pool grows by one zombie per cron cycle, forever, and each zombie sits armed, re-polling, clogging the queue view and the agents' attention. Expected: −2–4 now, unbounded prevented accumulation.

**#4 — Red-bot triage lane + dependabot grouping (class 3).** Small direct queue effect (−2–4), but grouping is a major *upstream* CI reducer: the current 10-PR dependabot batch costs 10×25 = 250 required check-runs; grouped to 1–2 PRs it costs 25–50. [Dependabot groups are GA and, since Feb 2026, can group across directories](https://github.blog/changelog/2026-02-24-dependabot-can-group-updates-by-dependency-name-across-multiple-directories/).

**#5 — Burst capacity engineering.** This ranks **last for queue size** but **first for tail latency** (p90 3.3h, max 21.9h). Median PR is fine; the 17-queued/16-pending saturation is what stretches the tail. It deserves heavy investment (§3) but it will not clear the straggler pool — don't confuse the two problems.

**Anti-ranking (explicit):** the local pre-push work (P1) and the local suite lock (P6) do nothing for this pool. They're agent-DX wins, not queue wins. Fine to finish, but don't let them displace #1–#3.

---

## 2. Proposals

### P-A. Arm-on-green sweeper (answers 2a)

**Design.** A scheduled workflow (every 20 min, jittered) + `workflow_dispatch`, running a small script:

1. List open, non-draft PRs whose author ∈ bot allowlist (`dependabot[bot]`, named cron bots) — v1 scope: **bots only**.
2. For each: fetch mergeable state + all 25 required contexts. Conditions to arm, ALL required, else skip with a logged reason: `mergeable == MERGEABLE` (no conflicts), every required context `SUCCESS`, zero `PENDING`/`FAILURE`, R1 context green where applicable, no `do-not-merge` label.
3. `gh pr merge --auto --squash <n>`. Log every arm and every skip-with-reason to a step summary (I3).
4. Fail-closed (I2): any API ambiguity, unknown check state, or unexpected author ⇒ skip.

Also fix it *upstream*: the PR-creation path for agent lanes should arm auto-merge at creation time (GitHub happily arms against pending checks). "Unarmed" is a missing default, not a process failure.

**Safety vs invariants.** I1 untouched (all 25 contexts must be green to arm). I5 untouched. Generator≠grader untouched — the sweeper arms, it doesn't review; the R1 context must already be green. The one real hazard: with strict=false, arming a dependabot PR green on a stale base merges untested-against-head code. This hole exists today for every armed PR; the sweeper widens its *frequency* for dependency bumps. Mitigation: backend suite runs on `push` to main (post-merge), so breakage is detected within ~18 min; dependabot bumps with green full CI are the lowest-risk content class in the repo. Accept, and measure via the guard metric in §5.

**Expected gain.** −8–10 queue slots immediately; class eliminated permanently. **Failure modes:** GraphQL `mergeable` returning `UNKNOWN` transiently (handled: retry-once-then-skip, fail-closed); arming during a burst adds merge commits that retrigger treadmill rebases (transient, dies with P-B). **Kill-switch:** repository variable `SWEEPER_DISABLED=true` checked at workflow start; one-line revert of the cron schedule.

### P-B. Derived artifacts out of the merge path (the real treadmill kill)

**Design.** Finish landing P3′, then go further than the spec: INDEX.md, DOCS_INVENTORY.md, and the AI_ONBOARDING counters become **main-side artifacts**. A scheduled (or `push`-to-main) workflow regenerates them and commits directly to main via the one allowed bot push exception — or, cleaner under I5, opens a *self-arming, R1-waived* regen PR (see P-C) that merges within minutes. The docs gate on PRs becomes P3′'s pure function of the tree and stops requiring the derived files to be in the PR diff at all.

**Safety vs invariants.** I1: the gate still runs, still required — stronger, since it's now deterministic (already established by the P3′ panel). I6: regeneration is content-keyed, not time-keyed; the scheduled organ has the liveness guard already designed. If a direct-to-main bot push is judged an I5 violation, use the waived-PR variant — the mechanics are P-C either way.

**Expected gain.** Eliminates the re-conflict loop (#2626-class), the repair-PR subclass, and the largest single source of redundant full-suite runs. **Failure modes:** regen organ silently dying → counters rot (mitigated by the liveness guard from P3′); two regen commits racing (serialize via concurrency group on main, `cancel-in-progress: false`). **Kill-switch:** revert gate to requiring committed artifacts (old behavior) with one config flag.

### P-C. R1 treatment for automated PRs (answers 2b)

My recommendation: **two-track, by destination.**

- **Track 1 — reports that don't need to be on main → stop making them PRs.** Cron outputs (nb-health-style reports) go to workflow artifacts + a `data/reports` branch (or an orphan `reports` branch), which is not protected and needs no checks. The dashboard/docs read from there. This deletes the zombie class rather than negotiating with it. No invariant is even engaged — nothing merges.
- **Track 2 — generated content that must land on main (regen PRs from P-B) → mechanical-grader waiver.** Extend the R1 gate with a second, independent satisfier: pass if (a) author ∈ named bot allowlist, AND (b) every changed file matches a *narrow, non-executable* path allowlist (e.g. `docs/reports/**`, the two derived docs), AND (c) a denylist of executable surfaces (`**/*.py`, `**/*.ts`, `.github/**`, `package.json`, lockfiles, workflows) is empty in the diff. The waiver decision and the full path list are logged on the check output (I3). The allowlist itself lives in a YAML that changes only through a normal, fully-reviewed PR — generator≠grader governs the waiver's own scope.

**Why not a reviewer-bot LLM reviewing bot PRs:** for a pure function-of-tree regen diff, an LLM "adversarial review" is theater that adds cost, latency, and a new failure mode (the reviewer bot hallucinating a block) while providing less assurance than the path-scope check. Generator≠grader survives *in substance* here because the grader is a deterministic, independently-maintained mechanical check over a trust domain (generated, non-executable content) where adversarial semantic review has no object. Real code never qualifies: any executable-path touch fails closed to the existing cross-family R1 requirement. I'd argue this to the other researchers explicitly: if your waiver allows *any* executable path, it has weakened generator≠grader; mine cannot.

**Expected gain.** −2–4 permanent zombies now; unbounded future accumulation prevented; enables P-B's regen-PR variant. **Failure modes:** allowlist creep (mitigated: changes need full R1 review; denylist evaluated *after* allowlist so denylist always wins); a bot account getting compromised and pushing within allowlisted paths (blast radius: docs only, fully revertible, and the same exposure exists today via the cron itself). **Kill-switch:** gate config flag `bot_waiver: false` → all bot PRs need classic R1 again.

### P-D. Red-bot triage lane + dependabot grouping (answers 2c)

**Design.**

1. `dependabot.yml`: add `groups` — one group per ecosystem for minor+patch (security updates stay individual and ungrouped, or a security-only group with `applies-to: security-updates`), weekly cadence staggered per ecosystem (e.g. pip Mon 03:17, npm Tue 03:47, github-actions Wed 04:07 — off-peak, off the :00/:30 herd marks).
2. Nightly triage job: bot PR red for >24h → comment with the failing contexts (loud, I3) and `@dependabot recreate` semantics where the failure looks environmental; red >72h with no green run → close with a receipt comment (`closed by triage lane; reason; reopen with: gh pr reopen` / dependabot will re-propose on next cycle). **Exception:** security-update PRs are never auto-closed — they're escalated (label + issue ping) instead, fail-closed toward keeping them alive.
3. Guilt+innocence tests (I4): fixture PR states → must-close / must-not-close (security label, recent green, human comments present) / must-skip-on-API-error.

**Safety vs invariants.** Closing a PR touches no required check; I1/I5 unaffected. Fail-closed on any state ambiguity (I2). **Expected gain:** −2–4 queue slots now; grouped dependabot cuts the recurring bot batch from ~250 required check-runs to ~25–50 per cycle — a recurring ~10% CI-load reduction. **Failure modes:** grouping couples updates — one bad bump fails the group (mitigation: keep groups minor/patch-only; majors individual). **Kill-switch:** delete the triage workflow; revert `dependabot.yml`.

### P-E. Burst-capacity program (answers 3), ordered by leverage-per-risk

**E1. Supersede-cancellation — ship today.** Add to every PR-triggered workflow:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true
```

Never on `push` to main or any future `merge_group` trigger. During treadmill rebase storms and agent force-push churn this is the single largest immediate capacity recovery — every stale in-progress run is pure waste, since only the head commit's checks can ever gate the merge. I1-safe: the merge-gating head always runs the full suite; cancelled runs are, by definition, superseded. Zero new failure modes beyond GitHub's own cancellation race (a cancelled run's context disappears with the run — the superseding run replaces it).

**E2. Larger runner for the backend suite — the bridge (days, $).** The 18-min backend suite is both the critical path and, multiplied by 25 contexts × 28.6 merges/day ≈ 715 required check-runs/day before re-runs, the load driver. Moving it to an 8-vCPU larger runner should cut it to ~8–12 min (test-bound, not I/O-bound — verify with one A/B run) and, crucially, **larger runners have their own concurrency pool (up to 1,000 concurrent) separate from the standard cap** ([Depot calculator / GitHub plan limits](https://depot.dev/github-actions-price-calculator), [GitHub larger runners docs](https://docs.github.com/actions/using-github-hosted-runners/about-larger-runners/running-jobs-on-larger-runners)) — this directly relieves the 17-queued saturation. Cost: per-minute billing, no included minutes; estimate actual $ from one week of minutes before rolling to all lanes. Zero workflow-logic change, zero invariant impact, trivially reversible.

**E3. Consolidate the small gates into one fast job.** actionlint, docs lint, shellcheck, YAML lint, misc metadata gates: each currently boots a runner (~30–60s overhead) for seconds of work. Merge into one `fast-gates` job with steps. **Context-name caveat:** I1 forbids *removing* required contexts, so the migration is: add consolidated job → add its context as required alongside → observe 1 week → remove old contexts. Identical coverage, ~5–8 queue slots freed per PR-wave. Do E1/E2 first; this is gravy.

**E4. Self-hosted runners on the idle Macs — the big lever, gated by safety.** Capacity math: 3 Apple Silicon Macs, 10–24 cores each, mostly idle overnight — that is plausibly 6–12 GitHub-runner-equivalents, i.e. a 2–5× capacity multiplier, free at the margin. Safety analysis:

- **Threat model.** Every CI job executes PR code. In this repo the PR authors are the owner's own agent sessions, not the public — no fork-PR attack surface (GitHub's standard self-hosted warning targets public repos). Residual risks: (a) a prompt-injected agent session shipping hostile workflow/code that runs on the runner; (b) job escape → lateral movement to the DB/daemons on **Mini (the H24 production server)** and Pro (workhorse DB); (c) secrets: any job with repo secrets on a self-hosted runner exposes them to PR code and to runner-disk residue; (d) PII boundary — AGENTS.md says PII never into cloud outputs; ironically self-hosting is *PII-friendly*, but jobs pulling prod-like data must stay off GitHub-hosted runners, not the reverse.
- **Design that makes it acceptable:** ephemeral VM runners only — [Tart](https://tart.run) on Apple Silicon, one fresh VM per job, destroyed after; dedicated unprivileged runner user on the host; **network segmentation** (VM NAT with no route to LAN services — non-negotiable on Mini; if Mini can't be segmented cleanly, exclude Mini and use Pro + Air only); runner group scoped to an explicit workflow allowlist; **secretless jobs only** (backend tests, frontend tests, lint) — CodeQL, Snyk, and anything needing tokens/secrets stays GitHub-hosted; concurrency group per Mac to cap load; watchdog that deregisters the runner on host sleep/reboot.
- **Verdict:** GO as a week-2 pilot with exactly one job type (backend suite shard) behind a `runs-on` label flag, on Pro first. The engineering is the highest of any lever here; that's why E2 is the bridge.

**E5. Stagger the agent lanes + PR budgets.** Free and immediate: offset each lane's cron by 15–40 min across the night window; cap each lane at N=3 open PRs (token-bucket; lane must merge or close before opening more — forces completion over creation, directly attacks the 10-PR overnight wave). Loud log when a lane is throttled (I3).

**Not recommended:** path-filtering required workflows (I1, and [the pending-skipped wedge is well documented](https://linqdev.com/how-to-reduce-ci-cd-pipeline-build-times-in-github-actions/)); CI sharding of the backend suite *before* capacity headroom exists (4 shards × 10-PR wave = 4× the queued units; revisit after E2/E4, and then only behind a single aggregator context).

---

## 3. Merge-queue verdict: AGAINST flipping now; CONDITIONAL GO later — and possibly never

**The case against now, quantitatively.** Merge queue re-runs all 25 contexts per `merge_group` at merge time. At 28.6 merges/day that's ≥715 *additional* required check-runs/day — before speculative-group checks and ejection re-runs — landing on a runner pool that *right now* shows 17 queued + 16 pending. With the 18-min backend critical path, a serialized queue at this merge rate needs 28.6 × ~20 min ≈ 9.5 runner-hours/day of *serialization-critical* capacity just for the queue, and every hiccup ejects and re-runs. You would be adding a second CI workload the size of the current one to a saturated pool. The predictable outcome: queue depth replaces PR staleness as the bottleneck, and the ejection churn (hazard c) becomes the new treadmill.

**The value case is also weaker than it looks here.** Merge queue buys two things: (i) kills the treadmill — but P-B kills it *at the source* for all PRs, not just queued ones, and without re-running CI; (ii) closes the stale-green-merge hole — real, but **unmeasured**. Before paying ~2× CI forever, measure the hole: count main breakages attributable to logical (non-textual) conflicts over the last 60 days. My prior from the data given (p50 latency 0.5h, 176/200 merged <2h): bases at merge are usually minutes-to-hours old, so the hole's incidence is likely low. If it's ~0, the honest conclusion is merge queue is a solution to a problem this repo doesn't measurably have, at a cost it measurably can't currently afford.

**Correct sequence if the measurement says GO:** (1) P-B landed (else derived-docs PRs eject-loop in the queue — same trap the kroxylicious project hit with their CHANGELOG, see [their adoption issue](https://github.com/kroxylicious/kroxylicious/issues/3666)); (2) E1+E2 capacity landed; (3) add `merge_group` triggers to all 21 workflows — [GitHub's docs are unambiguous: without them required checks simply never report and the merge fails](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks) — and fix every `github.event.pull_request.*` condition that would silently evaluate null (prior work's hazard (a) is real and would *violate I1 by weakening green at merge*); (4) shadow canary: dispatch `merge_group`-equivalent runs in parallel for 2 weeks, diff coverage per context; (5) ejection watcher bot; (6) flip with small group size.

**Cheaper substitute worth deploying regardless:** a *base-freshness advisory* — a non-required check that flags PRs whose base is >N commits behind main and touching high-blast-radius surfaces, surfaced to the sweeper as "prefer fresh-base PRs first." Captures much of the hole's value at ~0 CI cost without touching I1.

---

## 4. Missing levers (with invariant analysis)

- **Auto-update-branch bots (e.g. "update all open PRs on main push"):** **anti-recommend.** With strict=false, updating is optional; blanket auto-update turns every merge into a 25-context re-run × every open PR — it *is* the treadmill, generalized. The correct version is **conflict-only rebase**: a repair bot that rebases a PR only when `mergeable == CONFLICTING`, one at a time, oldest first, serialized. Safe, I1-neutral, and removes the manual/agent rebase loop. Recommend.
- **TTL policy:** auto-close PRs idle >7 days (no commits, no comments, not armed) with a reopen receipt (branch retained, `gh pr reopen` in the comment). Clears the 145h tail; dependabot re-proposes automatically. Exclusions: armed PRs, security-labeled PRs. I1/I5 untouched; fail-closed on ambiguity. Recommend, week 2, after 48h dry-run.
- **Required-context consolidation (25 → fewer, identical coverage):** legitimate under I1 *if* coverage is byte-identical and migration is add-then-remove with a canary overlap (E3 is the first tranche). The 25-context manifest from P2 is the diff baseline. Moderate gain; do after capacity work.
- **PR budgets per lane:** covered in E5 — cheap, effective against burst waves. Recommend.
- **Cron reports → data branch/artifacts:** covered in P-C Track 1 — the cleanest kill of the zombie class. Recommend.
- **Batch merge windows (clock-driven merge train):** a poor man's merge queue — e.g. bot PRs only arm/merge in a 02:00–06:00 window. Captures some burst-smoothing at a fraction of merge queue's cost. Optional; only if staggering (E5) underdelivers.
- **Stacked PRs:** reject for this repo. The conflict surface is overwhelmingly the derived docs (fixed by P-B), and stacking adds rebase-cascade complexity that LLM-agent lanes will reliably fumble at 3am. Negative expected value.
- **Trunk-based + feature flags:** violates I5 (PR-only) by design. Reject.
- **What nobody listed — a live straggler dashboard:** the taxonomy in this brief exists because someone probed PRs by hand. The sweeper cron should emit the class breakdown (green-unarmed / R1-zombie / red / conflicted / fresh) as a step summary + a pinned issue, every run. You cannot hold a gain you can't see. One hour of work; do it in P-A.

---

## 5. Two-week sequencing (with rollback points)

**Day 1–2 (all zero-risk, parallel):**
1. E1 supersede-cancellation on all PR workflows. *Rollback: revert YAML.*
2. P-A sweeper in **dry-run** (logs what it *would* arm) + straggler dashboard live. *Rollback: delete workflow.*
3. P-D dependabot `groups` + staggered schedule. *Rollback: revert dependabot.yml.*
4. E5 lane staggering + open-PR budget N=3 in the lane orchestrator. *Rollback: config flag.*
5. Start the measurement: stale-green-merge hole incidence over last 60 days; baseline the three metrics below.

**Day 3–5:**
6. P-A sweeper live (bot authors only) after 48h of clean dry-run agreement with manual judgment.
7. E2 backend suite on 8-vCPU larger runner, A/B vs standard for 2 days, then default if ≥30% faster. *Rollback: `runs-on` label.*
8. Land P3′ (#2626); begin P-B (derived artifacts to main-side regen).
9. P-C spec through the normal R1-reviewed PR process (it changes a required gate — it must eat its own dog food), with guilt+innocence fixtures: bot+docs-only diff → waived; bot+one `.py` in diff → R1 required; unknown author → R1 required; API error → required.

**Week 2:**
10. P-B live; verify treadmill PRs stop re-conflicting. *Rollback: gate config flag.*
11. P-C live (Track 1 reports→branch first, then Track 2 waiver). *Rollback: `bot_waiver: false`.*
12. P-D triage lane live after 48h dry-run.
13. TTL policy live (dry-run day 8–9, live day 10).
14. E4 self-hosted pilot: Tart ephemeral pool on Pro, backend-shard job only, secretless, network-segmented. *Rollback: label flip.*
15. Day 14: merge-queue decision review with the hole-incidence data.

**Three metrics (precise definitions):**
1. **Straggler count S** = number of open, non-draft PRs whose age > 24h, sampled daily at 08:00. Target: 26 → ≤5 by day 14.
2. **p90 merge latency** = 90th percentile of (merged_at − created_at) over rolling 7 days. Target: 3.3h → <2h. Guard metric beside it: **main-breakage rate** = reverts or fix-forward PRs per week attributed to a bad merge (must not rise — this is the guard on P-A's stale-base risk).
3. **CI queue pressure** = median minutes from job `queued` to `in_progress` for required jobs during the 00:00–08:00 window, plus total check-minutes/day. Target: queue minutes −50%, total check-minutes *down* (cancellations + grouping + treadmill kill) despite equal-or-higher throughput. If check-minutes rise, something in the plan is re-running work it shouldn't.

---

## 6. Top-3 risks of my own plan (self-red-team)

1. **P-A + strict=false normalizes stale-base merges of dependency bumps.** I've accepted this risk on the strength of full green CI + post-merge main suite, but "green on an old base" is exactly the class of failure that passes every individual check and breaks the combination. If the guard metric (main-breakage rate) ticks up even once, my plan says add base-freshness as an arming precondition for the sweeper — but I've made that a reaction, not a precondition, and a more conservative researcher will rightly flag it. Defense: dependency bumps are the lowest-semantic-coupling content class in any repo; the expected breakage rate is low and fully revertible.
2. **The P-C waiver is a permanent, machine-enforced hole in generator≠grader — its safety lives entirely in the path allowlist.** My defense is that the denylist-wins ordering and the executable-surface denylist make it impossible for code to pass through, and that allowlist changes need full R1 review. But the failure mode isn't today's config, it's *creep*: six months of "just add this one path" PRs, each individually reasonable. The mitigation is social/process, not technical, and I should be honest that that's weaker than the rest of the design. If the panel judges this unacceptable, Track 1 (reports→branch, no PRs) alone still kills the zombie class for everything except main-destined regen, which could instead be folded into the P-B scheduled organ as the single, solitary waived actor — a narrower hole.
3. **E4 (self-hosted runners) is under-scoped for the two-week window and carries the worst tail risk in the plan.** Mini is the H24 production server; Pro runs the workhorse DB. A misconfigured Tart network or a prompt-injected lane shipping hostile code to a runner is a lateral-movement path into production infrastructure — a categorically different blast radius than anything else proposed here. My sequencing already makes E4 last, smallest, and reversible, but the honest statement is: if the network-segmentation story isn't airtight by day 12, E4 should *slip*, not ship — and then the capacity story rests on E2's paid runners, which costs money forever. The plan survives that (E1+E2+E5+E3+P-B's CI savings likely suffice), but E4 is the item most likely to be quietly descoped by reality, and I've sized expectations accordingly.

**Where I disagree with prior work, explicitly:** the P2 panel treats merge queue as the next structural milestone; I think that's the wrong next milestone *for this measured anatomy* — it's a ~2× CI tax to buy treadmill-killing that P-B gets cheaper, plus a hole-fix whose incidence nobody has measured. Measure first; I predict the answer is "don't flip." And the sharding investigation's "modest gains" conclusion is right locally but should be extended: *CI* sharding before capacity headroom is actively harmful to queue depth — shard only after E2/E4, behind an aggregator context, or not at all.

## Appendix C — Fable pre-panel analysis, verbatim

(raw seat output — leads, not conclusions; arbitration lives in the synthesis)

# Seat 3 (Fable, orchestrator) — independent analysis, written BEFORE reading Sol/Kimi outputs

Timestamp: 2026-07-19 (pre-panel). Grounding: measured live this session (36 open PRs probed, 200 merged-7d stats, strict=false, 33 runs queued).

## 1. Root-cause ranking (by expected queue reduction)

The median pipe is HEALTHY (p50 0.5h, 28.6 merges/day). The "coda troppo lunga" is a STANDING POOL of ~24 stale PRs + burst latency. Anatomy with magnitudes:

| Class | Est. count | Growth | Cure class |
|---|---|---|---|
| R1-deadlocked cron PRs (nb-health daily, news-covers) | 3-4 | **+1-2/DAY, UNBOUNDED** | policy (the ONLY unbounded term → priority #1) |
| Green-but-unarmed bot PRs (#2513: 45/45 green, OFF, 75h) | ~6-8 | +batch/week | trivial drain + auto-arm policy |
| Red-failing dependabot (majors: prisma 7, huggingface-hub 1.x) | ~5-8 | +few/week | triage lane (fix minors, close majors w/ ledger) |
| Treadmill DIRTY (#2626) | 1-2 | steady-state | P3′ landing + refresh organ (in flight) |
| Legit WIP/draft | ~5-6 | — | not a problem |

Burst: 25 required contexts × 10-PR overnight wave ≈ 250-300 jobs vs concurrency cap → 33 queued observed; p90 3.3h is burst-driven, not check-driven.

KEY REFRAME: this is 80% an OWNERSHIP/POLICY gap (nobody's job to arm/triage/unblock bot PRs), 20% capacity. Speeding up CI without the policy fixes leaves the pool intact.

Noted nuance: R1 gate PASSES on dependabot (#2513 45/45 incl. R1) but FAILS on nb-health cron (#2484) — the gate already has author-aware handling; the cron lane simply isn't covered. Verify gate logic at synthesis.

## 2. Proposals

**A. Drain now (day 0):** arm the green-unarmed after eyeball; close red majors with ledger receipt (dependabot re-opens on schedule — reversible); adopt-or-fix R1-deadlocked. Queue 36→~20 in one day. No invariant touched.

**B. Kill the unbounded term:** cron report PRs must stop deadlocking. Three options:
  1. Reviewer-bot R1 lane: scheduled Sonnet session performs REAL adversarial review of bot PRs (verify report vs its data source), posts R1 comment. Honest generator≠grader. Cost: quota.
  2. Path-scoped R1 waiver for declared bot-output paths + known authors. Family-#3 under/over-match risk → guilt+innocence corpus mandatory. Smaller residual risk than it looks (bot paths are non-executable reports).
  3. **Reports→artifacts/branch (preferred for pure reports):** cron output stops being a PR at all. Kills the class + its CI cost. Weekly index PR (1 not 14). Loses per-report PR audit trail → artifacts retention + weekly index mitigates.
  Lean: 3 for pure reports, 1 for must-land-on-main regen PRs.

**C. Burst capacity (invariant-clean set):**
  1. `concurrency` cancel-in-progress per workflow×PR on PR events — superseded-run cancellation. Safe: auto-merge merges HEAD; old-SHA runs are moot. ~20-30% runner-minute saving during agent iteration.
  2. Workflow consolidation 21→fewer (shared setup amortized, fewer queue units). DANGER: renames required contexts → REF-BREAKAGE wedge (P2 manifest). Staged, one at a time, protection updated atomically, alias-job transition window.
  3. Non-required informational jobs → main-only/nightly.
  4. Self-hosted runners on the idle Macs: **NO — repo is PUBLIC** (fork-PR arbitrary code on our machines + PII-holding hosts; GitHub's own guidance forbids). Only revisit if repo goes private.
  5. Larger runners for the 18-min backend job: ⅓ latency at ~similar $/job — Legge-5 money decision, needs real minute data first.
  6. Stagger agent lanes (soft): flatten the 2am 10-PR wave via push-lock jitter (P6 adjacency).

**D. Ownership receptor:** organismo feed line "open PRs >48h: N (top-3 + reasons)" via scheduled probe → stragglers visible at day 2, not day 6. Closes the gap that CREATED the pool.

**E. Merge-skew repair-PR class (#2828/#2830):** post-merge reconciler owns ALL derived counters on main (auto-armed bot PR w/ B-mechanics) — repair-PRs obsolete.

## 3. Merge queue (P2) verdict: DEFER (not never)

- Its main sell (treadmill) is being cured by P3′+organ; strict=false → no update-branch storms today.
- merge_group ADDS ~6-10 full required-set runs/day on top of per-PR runs → worsens the ACTUAL bottleneck (burst saturation) before consolidation lands.
- The hole it closes (stale-green merge → logical conflicts, evidenced at low severity by the docs-counter repair-PRs) is real but low-frequency; E covers the observed instance class.
- Revisit at 2-week mark with post-fix burst profile + the canary preconditions already mapped.

## 4. Sequencing (2 weeks)

D0-1: A (drain) + stop cron-PR creation interim (or session adopts orphans at boundary).
D2-4: C1 (cancel-in-progress), D (receptor), dependabot config (weekly, stronger grouping, majors separated).
D5-9: B3 reports→artifacts (or B1 reviewer-bot) · C2 consolidation phase 1 · C3 non-required→main-only.
D10-14: measure, decide larger-runners ($, Legge 5), re-evaluate P2.

Metrics (precise): (1) open-PR count + p90 open-age, daily; (2) Actions queued→started wait p50/p90; (3) merges/day + created→merged p90. All gh-api, logged by the receptor.

## 5. Self-red-team (top-3 risks of MY plan)

1. Auto-arm sweeper arms a semantically-bad GREEN bump (W98 fastapi-malware class). Mitigate: minor/patch only, Snyk/Socket in required set, per-arm audit line, majors NEVER auto-armed.
2. Consolidation renames required contexts → "Expected—waiting" wedge on in-flight PRs (REF-BREAKAGE). Mitigate: staged + atomic protection update + alias window.
3. Reports→artifacts loses main-visibility of report history; if any consumer greps main for them, it breaks silently (W82 under-match). Mitigate: consumer-map BEFORE migration (feedback_merged_is_not_live rule applies to removals too).
