---
date: 2026-07-19
domain: operations
client_case: none
sources: [tests.yml + pytest.ini + workflow audit (Sol read-only sandbox), current GitHub docs (Kimi web-verified), round-1 capture research/operations/2026-07-19-pr-queue-acceleration-research.md]
---

Round 2 of [round-1 capture](./2026-07-19-pr-queue-acceleration-research.md) — owner rejected the paid lever;
this round finds $0 levers and falsifies three round-1/round-2 premises.

# ROUND 2 — $0 speed levers: 3-seat synthesis (Sol ultra · Kimi K3 · Fable), arbitrated

Date: 2026-07-19 · Mandate: Zero ("salta i larger-runners; deep research per altre soluzioni, mantenendo le buone già trovate")
Seats independent as in round 1 (Fable's analysis on disk pre-panel). Gemini seat DEAD fleet-wide (agy OAuth expired M5+Pro, probed live) — declared 2-external-seat degraded; re-arm = operator login. Sol had read-only repo access and audited the ACTUAL workflow files; Kimi had web search and verified current GitHub docs; both were needed — several premises survived one seat and died under the other.

## 1. Falsifications first (what round 2 KILLED — this is the value of the panel)

| Premise (whose) | Verdict (whose evidence) |
|---|---|
| "ARM = 2→4 core upgrade" (Kimi + Fable) | **DEAD.** Current GitHub docs list public-repo x64 `ubuntu-latest` AND `ubuntu-24.04-arm` BOTH at 4 vCPU/16GB (ARM GA for public repos Aug 2025). There is no core doubling to harvest — the 4 cores are ALREADY under every job. ARM prior gain = 0 (±); only an off-peak A/B if ever. Day-0 probe: print `nproc`/`uname -m`/runner-image in a job and settle real allocation. (Sol, docs-grounded) |
| "Draft-PR gating saves 25-50% CI" (Fable #1 lever) | **DEAD as designed.** `tests.yml` triggers on `types: [opened, synchronize, reopened]` — `ready_for_review` NOT included → un-drafting would not re-trigger; and a `!draft` condition on required jobs can report skip-as-Success and never re-run. Exactly the silent-green family. (Sol, file-grounded; Kimi had already downgraded it to defer) |
| "Squash-before-push" (Kimi #1 event lever) | **Mechanism corrected.** One push of 8 commits and one push of 1 commit are the SAME single `synchronize` event — squashing is irrelevant; the lever is PUSH-COUNT: local SHIP-gate, one push, PR opened ready, at most one repair push. Keep atomic commits. Target 1.25-1.5 runsets/PR (from ~2). (Sol) |
| "Drop -v from the CLI" (all three) | **Insufficient as stated**: `--verbose` is re-introduced by `pytest.ini:21` AND duplicated in TOML — must be removed from all 3 surfaces or it's a no-op. Keep `-ra --tb=short --durations=10` + JUnit. (Sol) |
| "fsync=off on test PG, zero risk" (Kimi + Fable) | **Downgraded to gated pilot**: no `fsync=off` until a probe proves no test exercises restart/WAL/durability; tmpfs pilot OK. (Sol) |
| "Alembic snapshot restore" (all three, wording) | **Wrong premise**: the workflow runs `SQLModel.metadata.create_all()` + the PROPRIETARY SQL-v2 runner (`backend.db.migrate apply-all`), not Alembic. Any snapshot key must cover migrations bytes + models feeding create_all + bootstrap + runner code + PG digest/extensions; AND `migration_manager.py:286` has warn/skip paths that must become fail-closed BEFORE any cache trusts it. Only worth it if a probe shows bootstrap+migrations p90 ≥ ~45s. (Sol) |
| "Split mypy+pip-audit into parallel jobs" (Kimi L3) | **Arbitrated to Sol's in-job supervisor**: separate jobs add ~20 job-starts per 10-PR wave against the same slot pool; instead run pip-audit+mypy as supervised parallel processes INSIDE the job, overlapped with bootstrap/migrations, explicit PIDs + fan-in, failure-injection tested (fail-open is the risk). Job-split only later, with telemetry, via add-then-remove. |
| Same-content dedupe (Q2) | **KILLED 3/3, permanently.** Sharpest argument (Sol): pip-audit MUST be able to turn red with zero tree change (new advisory) — a tree-keyed green voids that by construction. Reuse INPUTS (wheels, snapshots-with-grader), never verdicts. |

## 2. The arbitrated $0 plan (keeps everything round-1 adopted)

**Day 0 — probes (no mutations):** in-job `nproc`/arch/runner-image print · per-step timing of tests.yml (setup vs pytest vs coverage vs uploads) · log-bytes · bootstrap+migrations duration · Redis socket-deny trial run · queue-wait telemetry baseline (`created_at→started_at`).

**Day 1 — reversible speed + HONESTY fixes (one PR, guardrail-class, session-merged):**
1. Quiet pytest across ALL THREE config surfaces (`-q -ra --no-header`, keep JUnit + durations).
2. Remove the duplicate coverage terminal report (keep XML + the independent `coverage report --fail-under=55` as grader).
3. **Fail-open cures found by Sol'a audit (correctness, I2):** `Test Summary` job prints "Passed" without reading `needs.*.result` and claims 80% vs the real 55% gate (tests.yml:454) → fail-closed or delete; E2E readiness loop exits 0 after 30 tries even when backend never came up (tests.yml:397) → final `curl -f` gate; MCP install `pip install … || true` (tests.yml:232) → drop `|| true`.
4. pip-audit audits the LOCK (hash-pinned, no re-resolution; first-party editable excluded) + pin the CI tools (mypy/pip-audit/pytest plugins) in a CI lock.
5. Push-count agent protocol (SHIP-gate → one push → ready PR → ≤1 repair push) + census of non-main `push`-triggered workflows.
6. Health-interval 10s→2s on service containers; macOS plist-lint → Linux `plistlib` (frees the 5-slot macOS pool); `timeout-minutes` ceilings on every job (hung job = 360 min slot hold today).

**Days 2-7 — the core lever: in-job xdist on the 4 cores we ALREADY have.** Sol's hardened protocol: fix the 2 known bugs + census DSN-hardcoded/DDL fixtures (e.g. partners/conftest.py:334 does DROP TABLE on the shared DB); bootstrap+migrate ONCE into `template_ci`; per-worker `CREATE DATABASE … TEMPLATE template_ci`; DSNs set before collection/import; `-n 2 --dist=loadfile` → n3 → n4 only if PG/Redis headroom; parity = exact multiset of nodeids + outcomes + coverage numerator/denominator/missing-lines (never just "passed count"); 300-run soak before it becomes the gate. Local M5 pilot first (same artifacts, 10 cores, target gate 7-11→~3-4 min).

**Later, measurement-gated:** schema snapshot (only if bootstrap+migrations ≥45s, fail-closed runner first, restore-A + cold-replay-B + independent schema grader) · Node workspace-scoped install A/B on the 3 Node jobs · checkout-history audit (21 of 55 workflows use fetch-depth:0 — keep only justified ones) · DAG-edge audit (drop data-free `needs`) · Python 3.12 + sysmon coverage as an isolated runtime lane · ARM A/B off-peak (prior 0).

**Projection (Sol's conservative math, adopted):** backend runner-load 1,030 → 358-558 min/day (−46-65%); ship-critical-path −5-8 min once xdist lands; plus round-1's queue-hygiene effects. Kimi's 18→7 min projection is NOT adopted (it assumed the dead 2×-core premise); realistic xdist-first target: 18 → 10-13 min, then re-measure.

## 3. Metrics (add to S24/T90/A_CI)
`T_backend_p50/p90` · `Q_wait p50/p90` (created→started) · `runs_per_PR` (target ≤1.5) · `context_starts_per_merge` · `log_MB` · coverage numerator/denominator · `flake_rerun_rate` (5% rerun ≈ 51 runner-min/day — fixing flakes beats caches).

## 4. §Solo-operatore
Nothing new requires Zero: every adopted lever is $0 and reversible. (agy re-login remains open for future councils — operator[consent].) The Day-1 PR touches required-workflow files → guardrail-class: no auto-merge, session red-teams (generator≠grader) then merges, per standing rules.

## 5. Panel meta-record (round 2)
- Sol uniquely: the x64-already-4vCPU falsification · the 3 fail-open findings · push-count≠squash mechanism · SQL-v2-not-Alembic · in-job supervisor over job-split · flake-tax quantification · draft-PR types gap.
- Kimi uniquely: ARM-GA/public-4vCPU web verification (true but incomplete without Sol's x64 fact — the two seats' halves only make the whole together) · macOS-pool starvation find · timeout-minutes find · Codecov tail.
- Fable uniquely: live anatomy grounding (tests.yml single-process/-v/serial mypy) that seeded the round; draft-PR lever proposed AND killed by the panel — recorded as the round's example of why the conductor's ideas face the same refutation bar (W100-family, second instance this day after the R1 misquote catch).


## Appendix P — shared research prompt

(raw seat output — leads, not conclusions; arbitration in the synthesis)

<details>
<summary>Shared research prompt (verbatim)</summary>

# DEEP RESEARCH ROUND 2 — ZERO-COST speed levers for CI + ship-loop (paid options rejected by owner)

You are one of three independent researchers. Round 1 produced an arbitrated plan (summary below) that the owner ACCEPTED — do NOT re-propose or re-litigate it. The owner then REJECTED the only paid lever (GitHub larger runners, per-minute billing). Your mandate: find ADDITIONAL levers to make the pipeline faster, **strictly $0 recurring cost**, keeping everything already adopted. Concrete, mechanism-level, ranked.

## Facts (measured on the repo, 2026-07-19 — trust these)

- Repo `Balizero1987/Teman2` is **PUBLIC** (this matters: GitHub gives public repos free Actions minutes on standard hosted runners; verify what runner types/concurrency are free for public repos in CURRENT GitHub docs, including ARM runners `ubuntu-24.04-arm` which GitHub made free for public repos in 2025 — 4 vCPU. If still true in 2026, this is a 2×-core upgrade at $0).
- All 91 CI jobs run on `runs-on: ubuntu-latest` (2 vCPU standard). 2 jobs on macos-latest (plist lint).
- The critical-path job "Backend Tests (Python)" (~18 min, required): postgres:15 + redis:7 service containers; Python 3.11; deps via **uv already** with `actions/cache` on `~/.cache/uv` (lock-pinned requirements.lock.txt); then pip-audit; **mypy inside the same job (serial)**; import-chain gate; a fast gate (`-x` on one test file); SQLModel bootstrap; **alembic migrations applied from scratch every run**; stability gate; then **`pytest backend/tests/ -v` — 17,561 tests, SINGLE-PROCESS (no xdist), VERBOSE flag on**, with pytest-cov + coverage threshold + Codecov upload.
- Burst pattern: 10-PR overnight waves × 25 required contexts; observed 33 runs queued/pending at once (concurrency-capped).
- Local (M5 Mac, 10-core): same suite takes 7-11 min under low load. A pytest-xdist investigation (prior work) says: per-worker DB isolation is the prerequisite; 2 known bugs to fix first (a frozenset-parametrize test, a DSN-bypass in 2 intake tests); verdict was GO-TO-HARDENED-PILOT for LOCAL. CI-side sharding was deferred because more jobs per PR worsens queue depth under the concurrency cap — BUT in-job parallelism (xdist -n on the SAME runner) adds zero jobs.
- Round-1 plan already adopted (kept, do not repeat): bot-PR steward arm-on-green (minor/patch only) · census gate + straggler dashboard · pure-report crons → artifacts/data-branch · real different-family bot-lane R1 for regen PRs · diagnosis-based red-bot triage + dependabot weekly grouping (majors isolated, security separate) · cancel-in-progress on superseded PR runs · derived docs OUT of feature PRs (single-writer regen lane on main) · fast-gates workflow consolidation tranche · lane budgets N=3 + cron stagger · TTL w/ receipts · conflict-only rebase lane · merge queue DEFERRED · self-hosted runners on the owner's Macs REJECTED (public repo, fork-PR code execution, production machines) · larger runners REJECTED by owner (no recurring spend).

## Invariants (unchanged — violating any = rejection)

I1 required checks never weakened/removed/path-filtered/conditional (coverage identical or stronger; renames only via add-then-remove migration). I2 fail-closed. I3 loud skips. I4 guilt+innocence tests for new guards. I5 PR-only merges. I6 no time-keyed state. Generator≠grader survives. $0 recurring is a NEW hard constraint (one-time engineering time is fine; owner-machine compute for LOCAL tooling is fine; anything billed per-minute/per-seat is out).

## Questions

1. **CI wall-clock, $0**: rank concrete levers to cut the 18-min backend job and the other 24 contexts. Evaluate at minimum, with mechanism and expected minutes saved: (a) free ARM 4-core runners for public repos (`ubuntu-24.04-arm`) — verify current docs/limits, migration risks (arch-specific wheels, postgres/redis container images on arm64); (b) in-job pytest-xdist `-n 2/-n 4` after the 2 prerequisite fixes (zero extra jobs — does it clear the CI DB-isolation bar the same way as local?); (c) drop `-v` (log I/O on 17.5k tests) and other pytest flags (`-q`, `--no-header`, `-p no:cacheprovider`, disable live-log); (d) split mypy + pip-audit out of the critical-path job into parallel jobs (contexts change! handle via add-then-remove or keep job names — analyze); (e) alembic-from-scratch → schema snapshot restore (pg_dump template DB cached by migrations-hash — I6-compliant since content-keyed; analyze staleness/safety); (f) coverage overhead: pytest-cov cost at 17.5k tests; options that keep the SAME threshold gate but cheaper (e.g. coverage core, Python 3.12 sys.monitoring — weigh the 3.11→3.12 bump as its own risk lane); (g) service-container startup (postgres/redis pull+boot) — image pinning/pre-warm/tmpfs (`PGDATA` on tmpfs, fsync=off for test DB); (h) checkout/setup overhead across 21 workflows (shallow fetch depth, sparse checkout for docs-only workflows).
2. **Same-content dedupe, CI-side**: round 1 killed a LOCAL green-stamp cache (non-hermetic). In CI the environment IS hermetic per run. Analyze honestly: a required check that reports success because "an identical TREE (not commit) already passed on main or another PR" — does any I1-compatible version exist (e.g. GitHub's own behavior per commit-SHA, marketplace skip-duplicate actions, merge-base tree equality)? If none survives I1, say so and kill it permanently.
3. **Event reduction**: fewer CI-triggering pushes per PR at the source — agent-side squash-before-push discipline, draft-PR semantics (do required checks run on drafts? should agent lanes open drafts until VERIFY passes?), `paths-ignore` traps (I1 forbids path-filtering REQUIRED checks — but non-required jobs?). Quantify: our agents push ~2-4 times per PR.
4. **Local ship-loop, $0**: the agent-side wall-clock (pre-push suite 7-11 min under low load, worse under contention). Given P1 (path-aware skip) is live and P6 (ticket lock) is designed: what else? (uv for local venv? pytest collection cache? `--lf`/`--sw` for iteration — NEVER as the push gate; mise task caching; worktree provisioning speed).
5. **Anything structurally missed** across the whole loop (open→checks→R1→arm→merge→regen) that is $0 and not in the adopted plan. Think mechanism, not vibes.
6. **Sequencing + self-red-team**: order your levers by minutes-saved per engineering-day, flag the top-3 risks of your own proposals, define how each is measured (the round-1 metrics S24/T90/A_CI stay; add per-lever probes).

## Output format

Markdown. Sections: (1) Ranked levers table (lever · mechanism · expected saving · risk · I-invariant check); (2) Deep dives only where the mechanism is non-obvious; (3) The dedupe verdict (Q2) argued properly; (4) Event-reduction verdict (Q3); (5) Local-loop levers (Q4); (6) Missed-structural (Q5); (7) Sequencing + self-red-team (Q6). Quantify in minutes/day saved where possible (25 contexts × 28.6 merges/day × ~2 runs/PR is the baseline volume). Do not pad. Disagree with round 1 only with evidence.

</details>

## Appendix A — GPT-5.6 Sol (ultra) verdict, verbatim

(raw seat output — leads, not conclusions; arbitration in the synthesis)

[Air-M5]

Verdetto: le tre leve migliori a costo ricorrente zero sono ridurre gli eventi PR alla fonte, sovrapporre `pip-audit`/mypy al resto dello stesso job e introdurre xdist con database per-worker. ARM è gratuito, ma non è il “2× core”: oggi sia x64 pubblico sia ARM pubblico risultano 4 vCPU.

Baseline usata: 57,2 runset/giorno, 1.430 context-start/giorno e 1.029,6 backend runner-minute/giorno. Sono minuti di capacità/queue, non spesa.

Audit: il checkout locale è 9 commit dietro al riferimento locale `origin/main`, ma i workflow/config analizzati sono identici a quel riferimento. Branch protection e piano GitHub effettivo non erano leggibili dal checkout.

## 1. Ranked levers table

Ordine per risparmio atteso per engineering-day, con priorità al critical path. I valori non sono additivi senza benchmark.

| # | Leva | Meccanismo | Risparmio atteso | Rischio | I-invariant check |
|---:|---|---|---|---|---|
| 1 | Coalescere gli eventi PR | Commit atomici locali, SHIP gate locale, un solo push/open PR; al massimo un repair push | Da 2 a 1,25–1,5 run/PR: **257–386 backend min/giorno** e **358–536 context-start/giorno** evitati. A 1 run/PR: 515 min e 715 context | Feedback remoto arriva più tardi | Suite richiesta completa sull’unico SHA candidato; nessuno skip |
| 2 | Quiet pytest + un solo report terminale coverage | Rimuovere `--verbose` da `pytest.ini`, TOML e CLI; usare `-q -ra --no-header`; generare XML e lasciare il report/threshold al grader separato | **0,15–0,8 min/backend**, 9–46 min/giorno | Perdita diagnostica se JUnit/`-ra` non restano completi | Stessi nodeid, exit code, coverage e threshold; skip e failure ancora visibili |
| 3 | Lock audit + fan-out interno | Audit del lock hash-pinned, tool CI pinning; avviare pip-audit e mypy in parallelo nello stesso processo supervisore e sovrapporli a bootstrap/import gate | **0,8–2,5 min/backend**, 46–143 min/giorno | `wait`/processo background implementato male può diventare fail-open | PID espliciti, exit code di entrambi, log obbligatori, failure injection |
| 4 | xdist hardened `-n 2` | DB dedicato per worker creato da template, entrambi i DSN impostati prima degli import; poi `--dist=loadfile` | **3–6 min/backend**, 172–343 min/giorno. `n3/n4` può arrivare a 5–9 min, non assunto | Collisioni DB, fixture DDL, test order, coverage incompleta | Parità esatta seriale/parallelo su nodeid, esiti, skip/xfail e righe coverage |
| 5 | Install Node workspace-scoped | A/B `npm ci`/workspace install, cache download npm anziché indiscriminatamente `node_modules`; cache Playwright content-addressed | **0–1,5 min/job Node**; sui 3 job di `tests.yml`, 0–257 min/giorno | Dipendenze root implicite o cache più lenta dell’install | Stesso package inventory e stessi test; guilt test su dipendenza root nascosta |
| 6 | Checkout mirato | Togliere `fetch-depth: 0` solo dove la history non serve; `filter: blob:none`; sparse solo su job con input closure provata | **5–20 s/job**; su 10 context eleggibili, 48–191 min/giorno aggregati | File letto dinamicamente o idratazione lazy dell’intero repo | Nessun path-filter sui required; audit accessi full-vs-optimized |
| 7 | Redis/service tuning | Prima provare che Redis non riceve connessioni; se innocente, rimuovere il service. Altrimenti health interval 2s con retry equivalenti e Postgres tmpfs | **0,1–1 min/backend**, 6–57 min/giorno, più E2E | Redis usato indirettamente; tmpfs altera test di durabilità | Socket-deny guilt/innocence; nessun `fsync=off` senza prova |
| 8 | Snapshot schema con replay parallelo | Restore da dump keyed sul contenuto; cold bootstrap/replay su DB B in parallelo; schema grader indipendente prima del green | Ipotesi **0,5–2 min/backend**, 29–114 min/giorno; ceiling = tempo bootstrap+migrazioni misurato | Snapshot stale o migration runner fail-open | Hash completo, replay ogni run, `pg_dump --schema-only` normalizzato, cache corrotta deve fallire |
| 9 | ARM pubblico | Pilot manuale x64 vs `ubuntu-24.04-arm`; adottare solo dove p90 è realmente migliore | Prior **0**; range realistico **–2…+3,5 min/job** | Wheel mancanti/source build, arch fidelity, queue ARM | Cache include `runner.arch`; stesso test/coverage; niente sostituzione x64 cieca |
| 10 | Python 3.12 + coverage `sys.monitoring` | Ridurre il costo del tracer coverage su suite line-only | Gross hypothesis **0,5–3 min/backend**; netto sconosciuto, quindi zero nel piano base | Lock/runtime/mypy drift; 3.12 potrebbe essere più lento altrove | Lane runtime separata, exact coverage-line parity, produzione non deve restare 3.11 senza sentinel |

## 2. Deep dives

### ARM: gratuito, ma nessun raddoppio

Le documentazioni correnti elencano per repository pubblici sia `ubuntu-latest` x64 sia `ubuntu-24.04-arm` con **4 vCPU, 16 GB RAM e 14 GB SSD**. L’uso dei runner standard è gratuito sui repository pubblici; la concurrency resta invece legata al piano, indicativamente 20/40/60/500 job standard per Free/Pro/Team/Enterprise, con sotto-limiti macOS. Pubblico gratuito non significa concurrency illimitata. [GitHub-hosted runners](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [usage limits](https://docs.github.com/en/actions/reference/limits), [billing](https://docs.github.com/en/actions/concepts/billing-and-usage).

ARM standard è GA per i repository pubblici dall’agosto 2025, quindi non è più preview. [Annuncio GA ARM64](https://github.blog/changelog/2025-08-07-arm64-hosted-runners-for-public-repositories-are-now-generally-available/).

Conclusione pratica:

- Il presupposto “x64 2 core → ARM 4 core” non è più supportato dalle docs. Inserire nel job `uname -m`, `nproc`, `lscpu` e runner-image version per verificare l’allocazione reale.
- `postgres:15` e `redis:7` hanno manifest ARM64 ufficiali; il rischio vero è lo stack Python nativo: `torch`, `pyarrow`, `scipy`, `numpy`, `grpcio`, `cryptography`, `asyncpg`, `uvloop`, `orjson`.
- La chiave uv attuale usa solo `runner.os`; su ARM deve includere almeno `runner.arch`, Python esatto e lock hash. Vedi [tests.yml](/Users/balizero/nuzantara/.github/workflows/tests.yml:58).
- Pilot off-peak su 40–60 SHA equivalenti. Promuovere ARM solo con install 100% wheel, parità totale e miglioramento p50/p90 ≥10%. Non aggiungere un job shadow a ogni PR.

ARM può avere senso per lint/static analysis architecture-neutral o se la coda ARM è empiricamente più corta. Non lo considero oggi una leva backend positiva.

### xdist: la barriera CI non è ancora superata

Il requisito è lo stesso del pilot locale, ma CI ha un Postgres condiviso fisso e fixture che eseguono `DROP TABLE` sulla stessa base, per esempio [partners/conftest.py](/Users/balizero/nuzantara/apps/backend-rag/backend/tests/services/crm/partners/conftest.py:334). `--dist=loadfile` da solo non isola quel DDL.

Pilot corretto:

1. Correggere i due bug già noti e censire DSN hardcoded/fixture DDL.
2. Eseguire una sola volta bootstrap e migrazioni su `template_ci`.
3. Per ogni `worker_id`, creare `nuz_test_<worker>` con `CREATE DATABASE ... TEMPLATE template_ci`.
4. Impostare `DATABASE_URL` e `TEST_DATABASE_URL` prima della collection/import.
5. Partire con `-n 2 --dist=loadfile`; poi provare `n3`; `n4` solo se lascia capacità a Postgres/Redis.
6. Confrontare la multiset dei nodeid e gli esiti JUnit, non solo il numero “passed”.
7. Confrontare percentuale, numeratore, denominatore e insieme delle righe mancanti coverage.

`pytest-cov` supporta xdist, ma la correttezza dipende comunque dall’avvio corretto dei worker e dalla combinazione dati. [pytest-cov xdist](https://pytest-cov.readthedocs.io/en/latest/xdist.html), [pytest-xdist worker identification](https://pytest-xdist.readthedocs.io/en/stable/how-to.html).

### pip-audit/mypy: parallelizzare dentro il job, non creare job

Oggi pip-audit filtra e audita `requirements.txt`, quindi rifà resolution nonostante l’installazione principale provenga da `requirements.lock.txt`; mypy e pip-audit vengono inoltre installati senza pin e girano serialmente. Vedi [tests.yml](/Users/balizero/nuzantara/.github/workflows/tests.yml:78).

Correzione:

- Creare un lock CI separato per `pip-audit`, mypy e plugin pytest.
- Derivare l’input audit dal lock completo, eliminando soltanto l’editable first-party `cell-core`.
- Usare la modalità hash-pinned/no-resolution supportata dalla versione di pip-audit scelta.
- Grader aggiuntivo: insieme `name==version` installato deve coincidere con quello auditato, al netto della allowlist first-party.
- Lanciare audit e mypy nello stesso script supervisore; sovrapporli a import-chain/bootstrap/migrazioni; fare fan-in esplicito prima del green.

Separarli in due job aggiunge 20 job durante una wave da 10 PR e può trasformare 2 minuti di serialità in più queue. Se in futuro la telemetria mostra slot liberi, migrazione obbligatoria:

1. Aggiungere due context con nomi univoci mantenendo i gate nel backend.
2. Renderli required.
3. Soak verde.
4. Solo allora rimuovere le copie dal backend.

Non usare nomi di check duplicati: rendono ambigua la branch protection.

### Schema snapshot: non è Alembic

Il workflow fa `SQLModel.metadata.create_all()` e poi `python -m backend.db.migrate apply-all`; è il migration runner SQL v2 proprietario, non Alembic. Vedi [tests.yml](/Users/balizero/nuzantara/.github/workflows/tests.yml:139).

La chiave minima deve includere:

- byte ordinati di tutte le migrazioni;
- modelli/import che alimentano `create_all`;
- script bootstrap;
- migration runner;
- digest Postgres, configurazione ed estensioni.

Un semplice hash delle migrazioni sarebbe stale. Inoltre il runner attuale contiene percorsi warning/skip per filename non parsabili, orphan e lock occupato; va reso fail-closed prima di affidargli una cache. Vedi [migration_manager.py](/Users/balizero/nuzantara/apps/backend-rag/backend/db/migration_manager.py:286).

Design accettabile: snapshot prodotto su main trusted; PR restore su DB A; replay cold su DB B contemporaneo ai test; grader indipendente confronta schema, ledger e checksum. Il required context aspetta entrambi. Nessuna data/TTL: solo chiavi di contenuto. Non implementarlo se il probe mostra bootstrap+migrazioni p90 sotto circa 45 secondi.

### Pytest, coverage e service startup

Il solo drop di `-v` non serve: [pytest.ini](/Users/balizero/nuzantara/apps/backend-rag/pytest.ini:21) reintroduce `--verbose`; anche il TOML lo duplica. Va rimosso da tutte e tre le superfici. Conservare `-ra`, `--tb=short`, `--durations=10` e JUnit. `-p no:cacheprovider` ha beneficio trascurabile e danneggia `--lf`; live logging non è attivo.

Coverage oggi genera `term-missing` durante pytest e poi ristampa tutto con `coverage report --fail-under=55`. Togliere il primo report terminale, non il secondo: XML/data restano il generatore e il comando `coverage report` resta il grader indipendente. La configurazione attuale è line-only, quindi `sys.monitoring` è tecnicamente promettente, ma solo dentro una vera lane Python 3.12. [.coveragerc](/Users/balizero/nuzantara/apps/backend-rag/.coveragerc:1), [coverage measurement cores](https://coverage.readthedocs.io/en/7.14.0/howitworks.html).

Sui service container, una VM hosted è fresca: “pre-warm” e pin digest migliorano soprattutto la riproducibilità, non garantiscono velocità. Cambiare health interval da 10s a 2s mantenendo la stessa finestra massima può recuperare secondi. Postgres tmpfs va pilotato; `fsync=off` no, finché non è provato che nessun test eserciti restart/WAL/durabilità.

Checkout: il backend è già shallow per default, quindi aggiungere `fetch-depth: 1` è un no-op. Nell’intero repo ho trovato 55 workflow con checkout, 21 con `fetch-depth: 0` e zero sparse checkout. Il lavoro è eliminare solo i full-history ingiustificati; i backend test leggono anche root, `packages/core`, `apps/mouth` e corpus, quindi uno sparse globale sarebbe fragile.

## 3. The dedupe verdict

Verdetto: **nessun green-cache cross-SHA basato sul TREE è compatibile con I1 in questo repository. Va chiuso definitivamente.**

Motivi:

1. GitHub associa i required check allo SHA, e per `pull_request` il test usa normalmente lo SHA del merge sintetico, non un generico tree hash. [Pull request events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request).
2. Tree identico non implica input identici: workflow/action ref, runner image, tag service, tool unpinned, secrets/variables, event payload e database advisory possono cambiare.
3. In particolare pip-audit deve poter diventare rosso senza alcun cambiamento al tree quando emerge una nuova vulnerabilità.
4. Un’azione marketplace “skip duplicate” che trova un vecchio green ed esce zero produce un required success senza eseguire il gate sullo SHA corrente: è esattamente l’indebolimento vietato.
5. Anche con ambiente completamente content-addressed resterebbero nondeterminismo e flake detection; costruire una supply-chain di attestazioni firmate costerebbe più della suite e non risolverebbe i check temporali.

L’unica forma lecita di reuse è riusare **input** verificabili — wheel, npm download, schema snapshot con grader — mai il verdetto. GitHub non documenta un meccanismo nativo di riuso cross-tree dei required result. [Workflow runs](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows), [dependency caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching).

## 4. Event-reduction verdict

Il target realistico è 1,25–1,5 runset per PR. Un push con otto commit e un push con un commit producono entrambi un solo evento `synchronize`: **squashare non è la leva**. Conservare commit atomici locali e ridurre i push.

Protocollo agente:

1. Branch/worktree locale.
2. Iterazioni locali parziali.
3. SHIP gate completo.
4. Push remoto una volta.
5. Aprire direttamente la PR ready-for-review.
6. Accumulare eventuali fix e fare un solo repair push.

Nel workflow principale il `push` è limitato a `main`/`develop`, quindi un backup push della feature branch prima di aprire la PR non avvia `Tests & Coverage`; vanno comunque censiti gli altri workflow con trigger `push` generico.

Le draft PR non fanno risparmiare CI. Il workflow esplicita `opened`, `synchronize`, `reopened`, quindi apertura draft e push successivi avviano i check; `ready_for_review` non è incluso. Condizionare il required job a `!draft` sarebbe peggio: lo skip può apparire Success e il passaggio a ready potrebbe non rilanciare il workflow. [Draft pull requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests).

`paths-ignore` resta vietato sui required. GitHub avverte che un required workflow saltato da branch/path filter può rimanere Pending; un job saltato via `if` può invece risultare Success. [Troubleshooting required status checks](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks).

Per job non-required: classifier sempre attivo, receipt esplicita nel summary, input closure completa e guilt/innocence. Non usare un silent workflow-level skip, perché viola I3.

## 5. Local-loop levers

| Leva locale | Risparmio plausibile | Guardrail |
|---|---:|---|
| Due modalità `ITERATE`/`SHIP` | Targeted/no-coverage 0,5–3 min contro 7–11 full: **4–10 min per iterazione**; 20–100 min/giorno con 5–10 iterazioni | Banner `PARTIAL — NOT SHIP`; pre-push usa sempre P1 completo |
| xdist M5 `n4`, poi `n6` solo se libero | **2–5 min per full gate** ipotetici | Stesso isolamento DB del CI; niente `-n auto`; P6 governa CPU |
| uv per-worktree | **0,5–3 min per nuovo worktree**, soprattutto provisioning | `.venv` separata, cache download uv globale, `uv pip sync` frozen; niente venv writable condivisa |
| Postgres/Redis persistenti locali | **0,3–2 min per gate** | DB per worktree/worker derivato da hash stabile; reset deterministico |
| mypy incremental per worktree | **0,2–1 min per run** | Cache keyed da Python, mypy, config e source; non riusare verdetti test |
| Overlap gate su M5 | Nasconde audit/mypy dietro test/DB setup | Budget CPU esplicito; fan-in fail-closed |

`--lf` e `--sw` sono ottimi per ITERATE e categoricamente non validi per SHIP. Pytest non possiede una vera collection cache: `.pytest_cache` supporta last-failed e metadati, non rende sicuro saltare la collection. Testmon o manifest selettivi restano locali/parziali.

`mise` può evitare codegen/build deterministici tramite source/output hash, ma non deve mai memorizzare “suite green”. I worktree devono condividere Git object store e cache download, non database o venv mutabili.

## 6. Missed-structural

- **DAG-edge audit:** rimuovere `needs` senza dipendenza dati permette agli stessi check di partire prima senza cambiare context o copertura. Misura: somma del wait eliminato, non runtime del job.
- **`Test Summary` statico:** aspetta tutti i job e stampa “Passed” senza leggere `needs.*.result`; dichiara inoltre target 80% mentre il gate backend è 55%. Se è required, va reso fail-closed con migrazione add-then-remove; se non è required, eliminarlo risparmia 57,2 tail-job/giorno. [tests.yml](/Users/balizero/nuzantara/.github/workflows/tests.yml:454).
- **E2E readiness fail-open:** dopo 30 tentativi il loop termina con exit zero anche se il backend non è pronto, poi installa Node/Playwright e avvia test destinati a fallire. Aggiungere una verifica finale `curl -f`/flag ready. Non accelera i green, ma tronca presto i red. [tests.yml](/Users/balizero/nuzantara/.github/workflows/tests.yml:397).
- **MCP install fail-open:** `pip install -e ".[test]" ... || true` viola I2. Va corretto prima di qualsiasi ottimizzazione del job. [tests.yml](/Users/balizero/nuzantara/.github/workflows/tests.yml:232).
- **Overlap test offline/DB bootstrap:** solo dopo un manifest provato, i test realmente DB-free possono girare mentre si prepara lo schema. Il grader deve dimostrare che unione e intersezione dei nodeid corrispondano esattamente alla collection completa.
- **Redis shadow proof:** il grep mostra molto `fakeredis`/fake client, ma non prova assenza di connessioni indirette. Un run socket-deny può trasformare il sospetto in evidenza.
- **macOS plist-only:** il plist lint puramente statico può essere portato a Linux con `plistlib` e fixture valida/invalida; il job che compila Swift deve restare macOS.
- **Flake tax:** anche solo il 5% di rerun backend costa circa **51,5 runner-minute/giorno**. Correggere la causa ha ROI maggiore di cache sofisticate; retry permissivi no.

## 7. Sequencing + self-red-team

Sequenza proposta:

1. **Giorno 0 — probe:** arch/CPU/runner image, queue time, durata di ogni step, log byte, collection, coverage numerator/denominator/missing-lines.
2. **Giorno 1 — leve reversibili:** protocollo push, quiet output, rimozione report coverage duplicato, tool CI lock, fix E2E/MCP fail-open.
3. **Giorni 1–2 — fan-out interno:** pip-audit/mypy supervisionati nello stesso job; nessun nuovo context.
4. **Giorni 2–4 — setup jobs:** Node install/cache A/B, checkout history audit, health interval, Redis socket-deny.
5. **Giorni 3–7 — xdist:** fix isolamento, `n2`, poi `n3`; `n4` solo se p90 migliora.
6. **Solo dopo misure:** snapshot schema se setup p90 ≥45s; ARM manual A/B; Python 3.12 come runtime lane indipendente.

Probe e acceptance:

| Leva | Probe | Acceptance |
|---|---|---|
| Eventi | `synchronize`/PR, runset/merge, first-open→merge | ≤1,5 run/PR senza aumento T90/red rate |
| Quiet | log byte, upload time, JUnit/skip summary | ≥15s oppure forte riduzione log; diagnostica identica |
| Audit/mypy | resolution, mypy, overlap e fan-in time | ≥0,8 min p50; failure injection sempre rossa |
| xdist | n1/n2/n3/n4, CPU/RSS, PG lock, nodeid/coverage diff | ≥20% p90; parità esatta; 300 run soak senza collisioni |
| Snapshot | restore/replay time, hit rate, schema fingerprint | ≥20% critical-path gain; corrupt/mutated key sempre rosso |
| ARM | queue/install/test p50/p90, wheel build, parity | ≥10% netto; zero source-build inatteso |
| Node/checkout | restore/save/install/checkout time e cache size | Risparmio netto incluso cache upload; inventory invariato |

Conservare S24, T90 e A_CI. Aggiungere `T_backend_p50/p90`, `Q_backend_p50/p90`, `runs_per_PR`, `context_starts_per_merge`, `log_MB`, `coverage_lines_total/covered` e `flake_rerun_rate`.

Self-red-team, top 3 rischi:

1. **xdist produce false green/flaky green** attraverso DSN bypass o fixture DDL. Mitigazione: collision sentinel, DSN poison test, exact nodeid/coverage grader e soak lungo. Cinquanta run non bastano; 300 green danno circa un upper bound 95% sotto l’1%.
2. **background fan-in o snapshot diventa fail-open.** Mitigazione: missing PID/log = failure, process kill guilt test, snapshot corrotta, hash mutato e schema divergent devono fallire.
3. **drift di arch/runtime:** ARM o Python 3.12 risultano veloci ma non rappresentano produzione. Mitigazione: runner fingerprint, wheel-only probe, runtime sentinel e nessuna sostituzione x64 finché la production architecture non è allineata.

Target combinato realistico, se xdist arriva a 10–13 minuti e gli eventi scendono a 1,25–1,5 per PR: **358–558 backend runner-minute/giorno**, contro 1.030 attuali, cioè **472–672 minuti evitati, 46–65%**. Il beneficio sullo ship time sarà circa 5–8 minuti solo finché il backend resta il critical path; per questo queue e DAG devono essere misurati insieme al runtime.



## Appendix B — Kimi K3 verdict, verbatim

(raw seat output — leads, not conclusions; arbitration in the synthesis)

# DEEP RESEARCH ROUND 2 — $0 speed levers for CI + ship-loop

**Verified facts (2026-07-19):**
- Free ARM runners for public repos are live and current: `ubuntu-24.04-arm` / `ubuntu-22.04-arm`, **4 vCPU in public repos**, announced Jan 2025 and confirmed still current — in Jan 2026 GitHub extended arm64 standard runners to *private* repos at 2 vCPU while public repos keep 4 vCPU free ([GitHub changelog via community #148648](https://github.com/orgs/community/discussions/148648), [community #185840, Jan 2026](https://github.com/orgs/community/discussions/185840)). `actionlint` recognizes the labels since Jan 2025.
- Concurrency caps **apply to public repos too** (minutes are unlimited, slots are not): Free plan = **20 total concurrent jobs, 5 macOS** ([GitHub Docs usage limits](https://docs.github.com/en/actions/reference/limits)). The observed 33-queued-runs burst is a 20-slot problem — anything that adds jobs per PR must be weighed against this.
- `COVERAGE_CORE=sysmon` (Python ≥3.12) roughly halved test-execution time in a real large-suite case ([PyPI suite writeup via Simon Willison](https://simonwillison.net/2025/May/1/making-pypis-test-suite-81-faster/)).
- Required checks are evaluated **against the latest commit SHA** of the PR ([GitHub Docs](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks)) — central to the Q2 verdict.
- `postgres:15` and `redis:7` official images are multi-arch (arm64v8 included); `actions/setup-python` works on the ARM runners (PyPy being the known exception, irrelevant here).

---

## 1. Ranked levers table

Baseline volume: 25 contexts × 28.6 merges/day × ~2 runs/PR ≈ **1,430 job-runs/day**, all competing for 20 slots.

| # | Lever | Mechanism | Expected saving | Risk | I-check |
|---|-------|-----------|-----------------|------|---------|
| L1 | **ARM 4-core runners** (`ubuntu-24.04-arm`) on all Linux jobs | 2× cores + ~40% newer-gen perf at $0; one-line `runs-on` change per workflow | Backend 18 → ~11–13 min single-process; ~30–40% off every other Linux job. Fleet-wide: ~2,500–3,500 runner-min/day off the 20-slot queue | Arch-specific wheel gaps (low: uv cache is per-arch, mainstream deps ship aarch64 manylinux); subtle arch-dependent test behavior | I1: context names unchanged → no migration needed. Clean |
| L2 | **In-job pytest-xdist `-n 4`** (after the 2 known bug fixes + per-worker DB isolation) | Same runner, same job, 4 workers against per-worker databases (`gwN` → `test_db_gwN`) on the existing postgres service. Zero new jobs → zero queue-depth cost. Multiplies L1's 4 cores | Pytest phase (~10–12 min) → ~3–4 min; backend job → **~7–8 min** combined with L1 | Unknown cross-test pollution beyond the 2 known bugs; false greens worse than reds | I4: guilt+innocence tests for the isolation guard; 1-week serial-vs-xdist dual-run soak comparing outcomes |
| L3 | **mypy + pip-audit split out of the backend job** into 2 parallel short jobs | Removes ~3–5 serial min from the critical path; mypy/pip-audit need no postgres/redis, finish in ~2–4 min, well inside the backend job's remaining runtime | Critical path −3–5 min. Cost: +2 jobs/PR (~+57 job-runs/day, but short → high slot turnover) | During 33-run bursts the new short jobs queue; still parallel-net-positive because they're 4× shorter than what they displace | I1 add-then-remove: add `Backend Typecheck (mypy)` + `Backend Deps Audit` as required, soak, then strip from the old job. Old context name untouched until removal |
| L4 | **Pytest output + plugin diet** | Drop `-v` (17.5k log lines → runner log I/O + GitHub log ingestion), add `-q --no-header`, `-p no:cacheprovider` (CI-only), ensure `log_cli = false` | 0.5–1.5 min on the backend job; near-zero elsewhere | Loses per-test PASSED lines in logs (failures still fully reported) — acceptable, keep `-v` locally | I-checks unaffected |
| L5 | **Test-DB durability off** (`POSTGRES_INITDB_ARGS: "-c fsync=off -c full_page_writes=off -c synchronous_commit=off"` + tmpfs `PGDATA` via service `options: --mount type=tmpfs,destination=/var/lib/postgresql/data`) | Test DB is ephemeral per run; crash-consistency is pure overhead. 1.3–2× on write-heavy DB tests | 1–2 min on pytest phase | None real — container dies with the job anyway. Must NOT leak into any non-test DB config | I2 fail-closed unaffected |
| L6 | **Python 3.11 → 3.12 + `COVERAGE_CORE=sysmon`** (own risk lane) | pytest-cov's C tracer costs ~30–40% at 17.5k tests; sys.monitoring cuts that to near-zero (measured 2× end-to-end in the PyPI case; expect 20–35% here). Same threshold gate, same tests, newer interpreter | 2–3 min on backend job; also speeds mypy/runtime steps ~5% | Interpreter bump = behavior-change surface (deprecations, C-ext wheels). NOT bundled with anything else | I1-compatible (coverage identical or stronger — same threshold, same tests). Requires its own soak PR |
| L7 | **Alembic from-scratch → content-keyed snapshot restore** | Cache key = hash(migrations dir + postgres image digest). On hit: `pg_restore` a template DB (~seconds) instead of replaying all migrations; on miss/error: loud fallback to full replay (I3). I6-clean: content-keyed, no time state | 1–3 min depending on migration count | **Real coverage loss**: per-run proof that migrations apply cleanly from scratch disappears. Mitigation is mandatory (see deep dive) | I1 only survives if full-replay remains in *some* required context — see §2.3 |
| L8 | **macOS plist-lint → Linux** (2 jobs) | plist linting is `plistlib` (stdlib, pure Python) — runs anywhere. Frees the scarce 5-slot macOS pool and macOS's slow provisioning | 1–3 min provisioning per PR + removes macOS-pool head-of-line blocking | If any lint genuinely shells out to `plutil`, needs a plistlib port (hours) | Context names unchanged if job names kept; otherwise add-then-remove |
| L9 | **Checkout/setup hygiene across 21 workflows** | `fetch-depth: 1` is default since checkout v2 (verify, likely no-op); sparse checkout for docs-only workflows; consolidate micro-lint jobs into one job (fewer checkouts, fewer queue slots) | Seconds per job, but −N queue slots per PR from consolidation | None | Non-required jobs only; required contexts untouched |

**Combined backend-job projection: 18 → ~6–8 min** (L1+L2+L3+L4+L5), with L6/L7 as follow-ons. At ~57 backend runs/day that's **~550–650 critical-path minutes/day** returned, and every other context drops ~30–40%.

---

## 2. Deep dives (non-obvious mechanisms)

### 2.1 L1+L2 interaction — why order matters
xdist on the current 2-vCPU x86 runner tops out around `-n 2` → ~1.3–1.5× (postgres I/O wait dominates). On the 4-core ARM runner, `-n 4` actually has cores to use. So: **ARM first (one-line, low risk), xdist second (hardened pilot, high value)**. Reversing the order burns the xdist debugging budget on a 2-core box where the payoff is smallest.

DB isolation bar in CI is *identical* to local, with one CI-specific advantage: the postgres service is fresh per job, so worker DBs (`test_db_gw0..3`) can be created by a session fixture with zero legacy-state handling. Coverage under xdist: pytest-cov combines per-worker data automatically (`--cov` + xdist is supported); verify the threshold gate still reads the combined total — add an innocence test asserting the gate fails when coverage is artificially dropped under xdist.

### 2.2 L3 — the queue math
Round 1 deferred CI sharding because more jobs worsen queue depth. That argument is correct for *splitting the 18-min job into shards* (each shard is long; slots held long). L3 is the opposite trade: it moves **short** work into **short** jobs. A 3-min job occupying a slot for 3 min during a burst costs the queue less than the 3–5 min it removes from every backend job's slot-hold. Net slot-minutes roughly neutral; critical-path wall-clock strictly better. This is the only sharding-shaped change that survives the 20-slot constraint.

### 2.3 L7 — honest I1 analysis
"Alembic applies cleanly from scratch" is itself test coverage the required check currently provides. Restoring a snapshot instead **weakens the check** unless the full replay survives elsewhere. Two I1-compatible designs:
- **(a)** Keep full replay in the required backend job, snapshot only for *worker DB provisioning* in xdist (L2 needs 4 DBs; snapshot-restore 3 of them, full-replay 1). Savings smaller (~1 min) but zero coverage change. **Recommended.**
- **(b)** Move full-replay to a separate required context (`Migrations From-Scratch`), snapshot-restore in the backend job. Costs a queue slot; needs add-then-remove. Only worth it if migrations are genuinely slow (measure first: if replay < 90s, do (a) or skip L7 entirely).

Staleness is impossible by construction (key = content of migrations + image digest); fail-closed fallback on any restore error (I2), loud on fallback (I3).

### 2.4 L4 note
`-p no:cacheprovider` must be CI-only — locally it kills `--lf`/`--sw` (Q4). Put it in the workflow's pytest invocation, not in `pytest.ini`.

---

## 3. Q2 — Same-content dedupe verdict: **killed, permanently**

The candidate mechanisms, honestly examined:

1. **Marketplace skip-duplicate actions** (fkirc/skip-duplicate-actions et al.): they skip on *same commit / same PR branch* duplicates (push+PR double-fires), not cross-PR tree equality. For required contexts they make the check report `skipped` — and **GitHub counts skipped required checks as satisfied**. That means the check's semantics silently change from "tests ran and passed" to "tests may not have run". That is a conditional required check — **I1 violation**, and generator≠grader collapses (the pipeline grades its own skip decision).

2. **Merge-base tree equality** ("this exact merge-ref tree passed on main/another PR"): the strongest variant and it *still* fails. A green on an identical tree is a green from a **different point in time** — tests are not pure functions of the tree (postgres/redis image drift, dependency-advisory data, time bombs, flakes, and the runner image itself change between runs). Reporting success without executing means the required check no longer executes — coverage is not "identical or stronger", it is strictly weaker. **I1 violation, no repair.**

3. **GitHub's own per-SHA behavior**: checks already attach to a SHA; re-pushing an unchanged SHA does not create redundant work, and the adopted cancel-in-progress handles superseded SHAs. Nothing further to extract here.

**What survives (and is worth doing):** skip-duplicate logic for **non-required** jobs only, where skipping frees queue slots without touching merge gating — e.g. suppressing `on: push` double-runs for branches that already have an open PR (pure event hygiene, required contexts fire from `pull_request` events regardless). Verdict on the required-check version: **no I1-compatible form exists. Closed.**

---

## 4. Q3 — Event reduction verdict

Agents push 2–4×/PR. Each push = 25 contexts = 25 slot-claims against the 20-slot cap. Ranked:

1. **Squash-before-push discipline (agent-side, zero CI change) — DO.** Agents iterate locally against the local gate (P1/P6 machinery), amend/squash, force-push once when VERIFY is green. 3 pushes → ~1.3 avg. At 28.6 PRs/day: **~1,200 fewer job-runs/day (~40% of total queue load)** — the single biggest queue-relief lever in this report, and it costs one paragraph in the agent contract plus a linter for PR push-count.
2. **paths-ignore on non-required jobs only — DO (already implied by I3 design).** Docs-only paths skipping heavy non-required jobs, with loud skip reporting. I1 forbids this for required contexts; nothing forbids it for the rest.
3. **Draft-PR CI gating (`if: github.event.pull_request.draft == false`) — DEFER to owner.** Facts: required checks *do* run on drafts today (events fire normally), so agent lanes could open as drafts and skip CI until `ready_for_review` (which re-triggers). Merge-time protection is untouched — a non-draft PR's latest SHA must still pass everything. I judge this I1-compatible (the merge gate is bit-identical; only pre-mergeable pushes skip), but it is optically close to "conditional required check" and the savings overlap heavily with (1). Do (1) first; adopt drafts only if push-count stays >2.
4. **`on: push` branch filters** so CI fires on PR events only for agent lanes (push runs reserved for main). Same effect as skip-duplicate but declarative. Zero cost, do with (1).

---

## 5. Q4 — Local ship-loop levers ($0, owner-machine compute allowed)

Current: 7–11 min pre-push suite, worse under contention. Ranked:

1. **Local xdist hardened pilot (round-1 GO) is the biggest lever — finish it.** Fix the frozenset-parametrize + DSN-bypass bugs, per-worker DBs, then `-n auto` on the 10-core M5: **7–11 min → ~2.5–4 min**. Same artifacts as L2 — do the local pilot first, it *is* the CI pilot's evidence.
2. **Local postgres on RAM disk** (`hdiutil attach -nomount ram://…` → tmpfs-style PGDATA, or docker volume on the ramdisk) + `fsync=off`: 20–40% off DB-heavy tests even single-process. Stacks with (1).
3. **`--lf` / `--sw` for the iteration loop** (never the push gate — gate stays full suite). Typical fix-iterate cycle: full suite once, then `--lf` loops at seconds each. Saves 5–10 min per red iteration.
4. **uv for local venv provisioning** (already the CI tool — align local): `uv venv && uv pip install -r requirements.lock.txt` ≈ seconds vs minutes; shared `~/.cache/uv` across worktrees makes new-worktree provisioning near-instant.
5. **Worktree provisioning script**: worktree + venv + pre-warmed uv cache + `.env` symlink in one mise task; target < 60s so agents stop nursing long-lived dirty checkouts (which is what causes the multi-push pattern in §4).
6. **pytest collection diet locally**: `testpaths` set, keep cacheprovider ON locally (opposite of CI, L4).
7. **mise task caching**: content-key the "fast gates" task (hash of touched paths vs merge-base) for re-runs within one iteration — local-only tooling, explicitly *not* a push gate, so the round-1 non-hermetic-cache objection doesn't apply.

Combined realistic local outcome: pre-push gate **~3–4 min**, iteration cycles in seconds.

---

## 6. Q5 — Structurally missed ($0, not in adopted plan)

1. **macOS pool starvation (L8)** — the 5-slot macOS cap is the fleet's scarcest resource; the 2 plist jobs sit in the wrong pool entirely. Biggest "free" find of this round.
2. **`timeout-minutes` tightening on every job.** A hung job holds a 20-slot slot for the default 360 min. Setting realistic ceilings (backend 25, lints 5–10) fails hung runs fast (I2-aligned: hang = failure, loudly) and returns slots to the queue. Zero engineering, pure queue hygiene.
3. **Codecov upload off the critical tail**: `fail_ci_if_error: false` + move upload to a non-required follow-up job consuming the coverage artifact. The required check currently completes only *after* upload (~30–60s tail). Gate semantics unchanged (threshold enforced by pytest-cov locally in-job; Codecov stays informational).
4. **Job-level consolidation of micro-lints** (21 workflows → fewer, broader jobs for non-required checks): every job has ~30–60s fixed overhead (runner alloc, checkout, setup) plus a queue slot. Round-1's consolidation tranche started this; extend it to the tail of tiny workflows.
5. **Regen-lane timing**: schedule the main-branch regen lane into the queue trough (the adopted cron stagger covers crons; the regen *trigger* on merge can land mid-burst — defer regen by a short jittered delay when A_CI queue depth > threshold, using queue depth not wall-clock as the key — I6-clean).

---

## 7. Q6 — Sequencing + self-red-team

### Order (minutes-saved per engineering-day)

| Seq | Lever | Eng-days | Payoff |
|-----|-------|----------|--------|
| 1 | L9 verify + L4 (pytest diet) + L5 (pg durability) | 0.5 | 1.5–3 min/run, trivial risk |
| 2 | **L1 ARM migration** (all Linux jobs) | 0.5–1 | ~30–40% fleet-wide |
| 3 | L8 macOS→Linux plist + timeout-minutes + Codecov tail (Q5) | 0.5 | queue relief |
| 4 | §4.1 squash-before-push agent contract | 0.5 | ~40% queue-load cut |
| 5 | Local xdist pilot (Q4.1) | 1–2 | local gate → 3–4 min; generates L2 evidence |
| 6 | **L2 CI xdist `-n 4`** (with L7(a) worker-DB provisioning if replay is slow) | 1–2 | backend → ~7–8 min total |
| 7 | L3 mypy/pip-audit split (add-then-remove) | 0.5–1 | −3–5 min critical path |
| 8 | L6 Python 3.12 + sysmon (isolated lane, soak) | 2–4 | −2–3 min + runtime gains |
| 9 | L7(b) only if measured replay > 90s after all above | 1–2 | −1–3 min |

### Top-3 risks of my own proposals

1. **L2 false greens from unknown test pollution.** The 2 known bugs were found by looking; the ones that matter are the ones not yet found. *Mitigation:* I4 guilt+innocence tests for DB isolation; 1-week dual-run where serial and xdist both execute and outcomes are diffed (xdist advisory, serial authoritative) before xdist becomes the gate. Metric: outcome-diff count, must be 0 for 7 days.
2. **L1 arch-dependent behavior** (aarch64 wheel silently substituted, float/ordering-sensitive test passing on x86 only). *Mitigation:* add-then-remove anyway — run ARM as the required context for a soak week while an x86 job (non-required) dual-runs; diff results. Metric: per-label p50 duration + outcome diff.
3. **L7 coverage erosion by convenience.** Once the snapshot path exists, pressure will grow to use it everywhere and let from-scratch replay quietly rot. *Mitigation:* full replay pinned in a required context as a hard design precondition (§2.3), plus a receipt in the regen lane proving replay ran. If that precondition is ever dropped, L7 is reverted.

### Measurement (S24 / T90 / A_CI stay)

New per-lever probes, all derivable from the GitHub API at $0:
- **Per-job p50/p95 duration by runner label** (validates L1, L2, L6; alert on regression).
- **Queue-wait time** (`run_created_at` → `job_started_at`) per PR — the metric §4.1 and L3 must move; this is the real burst-pain number.
- **Pushes-per-PR distribution** (validates §4.1; target ≤1.5 avg).
- **Serial-vs-xdist / x86-vs-ARM outcome-diff counters** (the L2/L1 soak gates above).
- **Cache hit rate + fallback count** for L7 (fallback must be loud per I3; >5% fallback = investigate).
- **macOS pool occupancy** (validates L8; should drop to ~0).

**Bottom line:** keeping everything round 1 adopted, the $0 path to roughly a 2.5× faster backend gate (18 → ~7 min) and ~40% less queue load is: **ARM runners + in-job xdist on those 4 cores + serial-work eviction (mypy/pip-audit/output/durability diet) + push-count discipline.** The dedupe question is settled permanently: no I1-compatible same-content skip exists for required checks — speed must come from running the same checks faster and less often, never from not running them.

## Appendix C — Fable pre-panel analysis, verbatim

(raw seat output — leads, not conclusions; arbitration in the synthesis)

# Round 2 — Seat Fable (pre-panel, grounded on tests.yml anatomy read live)

Constraint: $0 recurring (larger runners REJECTED by owner 2026-07-19). Adopted round-1 plan stays.

## Ranked levers (mine)

1. **Draft-until-VERIFY discipline + skip-on-draft** — agent lanes open PRs as DRAFT; required workflows add `types: [..., ready_for_review]` and `if: !github.event.pull_request.draft` at job level. A draft cannot merge, so draft-time checks are NOT the merge safety net — the full set runs at ready_for_review on the final SHA; I1 substance intact (needs the argument made explicitly + guilt/innocence: un-drafted PR with no fresh run must show pending contexts, not green). Our agents push 2-4×/PR → saves 1-3 full 25-context sets per PR ≈ **25-50% of ALL CI volume**. Steward sweeps forgotten drafts. Auto-merge arms at ready. THE sleeper. Risk: event-type coverage bugs (ready_for_review not in types → wedge) → canary first.
2. **Free ARM 4-core runners for public repos** (`ubuntu-24.04-arm`) + **in-job xdist -n 4** — 2→4 vCPU at $0 (VERIFY current docs), zero extra jobs (in-job parallelism honors the queue-depth constraint). Prereqs: the 2 xdist bugs + per-worker DB (CREATE DATABASE per worker in bootstrap; postgres service is one container, N databases). Watch: arm64 wheels (lockfile mentions cuda-toolkit transitive — may need lock split per arch or exclusion), multi-arch postgres:15/redis:7 images exist. Expected: 18 min → **6-9 min** critical path.
3. **PG service tuning: tmpfs PGDATA + fsync=off + synchronous_commit=off + full_page_writes=off** — test DB only, pure I/O waste removal, zero coverage change. Est. 10-25% of DB-bound test time.
4. **Drop `-v`** → `-q --no-header` on 17.5k tests — log streaming overhead in Actions is real. Est. 1-3 min. One-line change, do first.
5. **mypy incremental cache** (`.mypy_cache` in actions/cache keyed by lock+config) + **cache the mypy/pip-audit installs** (currently `pip install mypy` uncached mid-job). Est. 1-3 min off critical path without touching context names.
6. **Migrations from-scratch → schema snapshot restore** keyed by hash(migrations tree) (I6-safe: content-keyed). ONLY IF migration-apply coverage exists elsewhere in the required set (Squawk lints; verify a full-chain apply gate exists — else keep a weekly/scheduled from-scratch job and this becomes add-then-verify). Needs coverage-map first.
7. **Redis service probe**: fakeredis is installed for tests — if the suite doesn't hit the real redis service, drop the container (boot time + resources). 5-min probe.
8. **Codecov upload non-blocking** (continue-on-error + `fail_ci_if_error:false`, or move after threshold gate) IF Codecov is not itself a required context — external-service flake removal.
9. **fetch-depth:1 + no-LFS sweep** across the 91 ubuntu jobs where history isn't needed (docs_sync needs history! per-file git log walk — exclude those).
10. **Q2 CI-side tree-dedupe: KILL permanently.** Post-plan (derived-docs out of PRs) the identical-tree re-run volume collapses; remaining value low; plumbing (conditional required job) violates I1's letter. Not worth the constitutional fight.

## Local loop (Q4)
- Worktree provisioning speed = task #6 (venv symlink + node_modules) — fixes double as speed.
- Local xdist after same 2 bug fixes (GO-TO-HARDENED-PILOT stands): 7-11 min → 2-4 min on 10 cores; biggest local win.
- pytest collection cache + `--co -q` sanity probes for agents pre-push (NOT as gate).

## Self-red-team
1. Draft-skip: if the I1 argument is rejected (checks conditional on draft state), the lever dies — needs the constitutional ruling BEFORE build; also ready_for_review wedge risk (canary + guilt/innocence).
2. ARM: cuda-toolkit transitive on arm64 may not resolve → lock strategy per-arch or dependency exclusion; A/B on a branch first, keep x86 as fallback label.
3. Snapshot migrations: silently removes de-facto migration-apply testing from the PR path if my coverage-map assumption is wrong → verify FIRST, ship SECOND.

