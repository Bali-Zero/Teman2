---
date: 2026-08-21
domain: operations
client_case: none
sources:
  - transcript 09277ba9 (sibling session 2026-08-20, "perché la quota brucia"), config/prompts/2026-08-20-fable5-quota-burn-investigation.md
  - gh API (pr list/checks/run list/rulesets/branch protection/code-scanning) probed 2026-08-21 00:00-01:30 WITA
  - M5 transcripts ~/.claude/projects/-Users-balizero-nuzantara/*.jsonl (7-day window), Pro ~/.claude/projects (session counts by hour)
  - origin/main at 2f7e485e3 via `git show origin/main:<path>` (the M5 checkout d5f34fe53 is 250 commits behind — every YAML/number re-derived upstream)
  - reader reports R-CI / R-CTX / R-SEATS / R-SUITE (Sonnet 5, read-only, 2026-08-21) — each re-verified on the load-bearing lines by the author
  - council: Codex GPT-5.6 (O2 seat, red-team) + Kimi K3 (refuter) — see §Adversarial review
adversarial_review: codex
---

# Token waste · coding throughput · PR velocity · test-suite size — system audit after the 2026-08-20 quota-burn session

> One-line answer: **the quota does not burn in the cron any more — it burns in the ship ceremony.** After the sibling
> session stopped the WR2 metronome (≈99% of the automation host's cache-write mass), the dominant remaining costs are
> (1) a 61-65-minute PR critical path that is ONE 30-minute test job run twice serially, (2) the 54% of every
> PR-session's output spent babysitting that path, (3) a 42K-token doctrine prefix paid by every session and every
> subagent, and (4) a model mix in which Fable 5 produces 63% of interactive output tokens — **of which ~86% is
> invisible reasoning** (visible text + tool calls are ~14% of the 32.3M output tokens/7d). None of these is "a cron
> running Opus". The single largest lever is therefore the **reasoning budget per turn (effort), tied to the gear**,
> followed by the CI double-run and the docs-lane. The only real-dollar lever (Gemini metered pool, 12% cache hit — see the 2026-08-21 amendment under L8: the bot leaves Gemini, so the cache half of this lever is suspended and only the spend cap survives) is
> still untouched.

Labels: **[measured]** = probed by the author this session with the command named; **[reported]** = from a reader
report or the sibling transcript, load-bearing lines re-verified; **[estimated]** = method stated; **[unknown]**.

---

## 0. Scope and method

Mandate (Zero, 2026-08-21 00:00): study the parallel session that was "optimizing the system to cut useless token
waste, speed up coding with quality, speed up PRs, and cut the suites drastically without losing safety — for every
LLM, not only Claude"; analyse the system; convene the LLMs as adversaries.

Budget declared at TRIAGE: 4 Sonnet read-only readers + 1 external council (planned 4 seats, **2 alive**) + Fable final
gate. Actual: 4 readers, 2 council seats (Codex O2 red-team, Kimi K3 refuter), ~20 orchestrator probes.

Twin-Fable lane discipline: the sibling session owns code PRs (token cuts, CRM/S7); this session owns **analysis +
council + this document**. No file overlap by construction.

---

## 1. What the sibling session (09277ba9) established — audit of its work

| Claim | Her evidence | My re-probe | Verdict |
|---|---|---|---|
| WR2 slide-critic loop was ~99% of Pro automation cache-write mass (686M/690M per 7d), 1,054 boots/day, 16/30 sessions with 0 API tokens, terminal consumer (IG publish) fired 0× ever | transcript parsing on Pro | — (not re-derived; unit caveat below) | [reported], plausible; **unit is cache-write tokens, not quota** (her refuters' point, accepted by her) |
| WR2 stopped (html-apply, supervisor, plist-watchdog `disabled`) and the stop is durable | same-hour comparison 17-19/8 vs 20/8 | Pro deploy-checkout sessions/hour 20/8: 18h **80**, 19h **42**, 20h **22**, 21h-00h **0** [measured] | **CONFIRMED** |
| `wr2.oracle` still enabled and reaches an LLM; 6 other WR2 jobs enabled | launchctl + payload read | not re-probed | [reported] — residual risk, ledger line below |
| `security.yml` path-aware → −22-32% of that workflow's runner-min | two lanes, 120 + 20 PRs | #4444 MERGED 15:01 [measured] | CONFIRMED merged; effect size [reported] |
| `ai-pr-review.yml` ran ~100× green, delivered 0 reviews | 8 merged PRs, 0 comments | #4435 MERGED [measured] | CONFIRMED |
| `agy` ignores stdin → paid calls with no prompt delivered | live probe | #4436/#4439 MERGED [measured]; agy itself now AUTH-DEAD on M5 (§5) | CONFIRMED |
| Codex O1 usage-limited until 22/8 08:30, burned by the 19/8 interactive swarm | codex stderr | O1 probe: timeout/no answer; O2 PONG [measured]; 120 `codex exec` calls from M5 interactive sessions in 7d, 0 codex cron on M5 [measured] | CONFIRMED, and the burner is the ceremony (§3) |
| Gemini metered: $19.18/$21.33 in 3 days on `rag.gateway.chat`, cache 12%, ~16K in-tokens/msg — "the only real-$ lever, not touched" | `llm_cost_events` | R-SEATS: no `cachedContents`, RAG context appended in the LAST user turn, no proactive cap on this pool [reported, file-level grep] | CONFIRMED untouched |
| Self-assessment: 3 duplicate dispatches, 4 broken probes, 12 PRs and **zero deliverable document** | her own words 14:37 | `ls research/operations/2026-08-2*` → empty [measured] | CONFIRMED — this document is that deliverable |

Her external panels: 11:03 five-family panel → Codex-sol ERR, Qwen 401, agy/Codex-o2/Kimi answered; 22:52 refuter
round → Codex usage-limited, Kimi + Gemini **WEAKENED** the "75% of quota" claim (cache-write ≠ quota unit; "stopped"
and "produced nothing" overstated). She accepted all three. Nothing in her work contradicts what follows; what follows
is the axis she never measured.

---

## 2. PR velocity — the critical path, proven with timestamps [measured]

- Every PR: **60-68 checks, 121-138 runner-minutes**; 92 workflows (~66 on `pull_request`, ~30 on `merge_group`);
  **27 required contexts** (classic branch protection).
- Open→merge, 60 PRs merged 2026-08-20: **median 61 min, p25 57, p75 66**. Ten newest: median 65.4.
- **Critical chain, PR #4450**: opened 14:39:42 → `Backend Tests (Python)` on the pull_request run 14:40:58→15:11:07
  (**30.1 min**) → queue entry 15:11:33 (17 s later) → `Backend Tests` again in merge_group 15:11:33→15:44:46
  (**33.2 min**) → merged 15:45:12. Identical shape on #4448 and #4444. **The median PR is one 30-minute job run
  twice, back to back.**
- The path-aware classifier (`scripts/ci/change_map.py`, enforcing since #4181 2026-08-14) IS wired on merge_group,
  but Backend Tests is skipped in only ~13% of queue runs (2/15 sampled) — fail-open by design.
- Merge-queue rule (ruleset `merge-queue-main`): `min_entries_to_merge: 1`, `max_entries_to_merge: 4`,
  `min_entries_to_merge_wait_minutes: 2`, `grouping_strategy: ALLGREEN` → **the queue never batches**: one full CI run
  per PR (verified on #4448/#4449/#4450, each its own `gh-readonly-queue/main/pr-N-…` run).
- **Queue re-entry amplification** [measured, Kimi D class]: since 2026-08-14, tests.yml merge_group runs = **388**
  for **258** merged PRs → **ratio 1.5**: the average PR runs the queue suite 1.5× (evictions when main moves,
  queue failures, requeues) — invisible in open→merge medians. Summed with the pull_request run, **Backend Tests
  executes ~2.5× per merged PR.** `min_entries_to_merge: 1` + ~37 main pushes/day is the thundering-herd setting.
- Does the second run earn its keep? Last 100 merge_group runs: tests.yml **9 failures**, security.yml **18**.
  Sampled causes: `test_deleted_at_guard_registry_matches_disk` (a committed registry moved by a sibling PR — cross-PR
  coupling on a generated file, W109b class; failed #4414/#4421/#4423 in one morning), Playwright killed by Docker Hub
  `toomanyrequests`, CodeQL/Snyk infra. In this sample the queue run catches **cross-PR coupling and infra flakes, not
  logic regressions** — real value, but against a disease curable upstream (derive registries in CI instead of
  committing them; pull base images from GHCR/cached).
- Per-PR runner-minute anatomy (ledger-only PR #4434, a single `.md` diff): 53 checks, 84 runner-min: **Detect Secrets
  19 min** (full working-tree scan of **18,967 tracked files** against `.secrets.baseline`, deliberately not
  domain-gated), **CodeQL Analysis (python) 13 min** (custom job in security.yml, required) **+ Analyze (python) 11 min
  + Analyze (javascript-typescript) 3 min** — the latter pair comes from GitHub's **Code Quality** feature, **not**
  CodeQL default setup as first written here (**corrected 2026-08-21, see §13.1**): the runs are named `Code Quality:
  CodeQL Setup` (main pushes) / `Code Quality: PR #N` (PRs), event `dynamic`, 2 jobs per run, **713 runs in the 7 days
  to 2026-08-20** [reported, orchestrating session] — while the actual CodeQL default-setup API
  (`repos/{owner}/{repo}/code-scanning/default-setup`) reports `state: not-configured` and org security
  configuration 17 ("GitHub recommended") has **zero attached repositories** [measured:
  `gh api orgs/Bali-Zero/code-security/configurations/17/repositories` → `[]`]. Code Quality lives at repo Settings →
  **Code quality** (separate from Advanced Security / code scanning) and has no REST surface of its own
  (`repos/{owner}/{repo}/code-quality` → `404` [measured]) — the shared `dynamic` event name is what caused the
  original misattribution. It still duplicates the custom job's coverage regardless of mechanism:
  **~13.7 runner-min/PR, not required** (Codex objection C4's underlying point — a redundant analysis pair — holds;
  its *attribution* to org-level default setup did not, see §13.1 and the corrected Adversarial-review rows below).
- PR mix, 258 merged in 7d: docs **84 (33%)**, fix 74, feat 73, chore 17. **29 PRs (11%) touch ONLY
  `.claude/skills/modus/PENDING-ARMS.md`**; 72 (28%) are markdown/json-only. Docs PRs: median 55 min open→merge, p25 37.

## 3. The ceremony axis — measured for the first time [measured, M5, 7 days, 140 sessions]

| Signal | Value |
|---|---|
| Assistant turns / output tokens | 31,111 / 31.9M |
| Model mix of assistant messages (token-weighted output) | **Fable 5 56.0% (63% of output tokens)** · Sonnet 5 28.8% (21%) · Opus 5 13.9% (15%) · rest 1.3% |
| **Output-token composition** (32.3M/7d) | visible text ≈ 0.7M tok + tool-call payloads ≈ 3.7M tok = **14%**; the remaining **~86% is thinking** (transcripts store redacted thinking blocks; 33% of turns carry one). Tool-less turns: 18.0M out, 0.69M visible → **96% thinking** |
| Post-PR output by dominant activity (13.77M) | **tool-less turns 62%** (reasoning + prose) · other bash 13% · code edits 8% · CI babysitting **4%** · subagent dispatch 4% · ledger/memory 3% · prove-live 2% · tests 2% |
| Declared gears | GEAR 3 ×11 · GEAR 2 ×2 · GEAR 1 ×4 (65% heaviest) |
| `Agent` dispatches | 415 — **289 (70%) grader/verifier/refuter-type**, 126 build/read |
| External-seat shell calls | codex **120** · kimi 101 · agy 26 · glm 18 · bare claude 26 (≈38/day) |
| Sessions creating PRs / PRs created | 52 / 107 |
| Output tokens before first `gh pr create` vs after | 11.66M vs **13.77M → 54% post-PR** — a *location*, not a cause (Codex C1): the post-PR mass is reasoning, not `gh pr checks` |
| CI-babysitting Bash calls in PR sessions | 1,078 of 7,542 (**14%** of calls, **4%** of post-PR output tokens) |
| Median output tokens per PR | **178K** (mean 253K) |
| Rework: correction/retraction PRs · closed unmerged (of 284 created) | 6 · 13 — **quality is not the cost; process is** |
| Token shape | cache_read 9.10B · cache_creation 258M · output 31.9M; median cache_creation/turn 1,148, mean 8,306 (7.2× skew) |
| `isSidechain:true` | **0** in all 264 transcripts ever on M5 (subagent work is re-read inline by the parent) |

**Boot tax — paid by every session and every subagent spawn** (R-CTX, confirmed on the reader's own system prompt):

| Component | Bytes (local / origin/main) | ~tokens | Note |
|---|---|---|---|
| `~/.claude/CLAUDE.md` | 25,067 | 7.2K | duplicates the ship-lifecycle section of the project file |
| `CLAUDE.md` (project) | 37,644 / **40,707** | 10.8K | SSOT, growing |
| `.claude/rules/cicatrix-superscar.md` | 66,943 / **70,970** | **19.1K** | self-described "bridge, not the encyclopedia"; W95-W119 carry full narratives inline; still accreting |
| `MEMORY.md` | 18,236 | 5.2K | at its own cap |
| **Static total** | **147,890 / ~155,000** | **~42-44K** | + skill/agent/MCP catalogs est. 20-35 KB (~90 skill entries, ~40 agent types) |
| SessionStart hooks | 867 B, 2.4 s | — | negligible |
| PreToolUse hooks | 9 per Bash, 9 per Edit | — | latency unmeasurable today (load avg 281 on M5) |

Arithmetic [estimated]: ~45K static tokens × 31,111 turns ≈ **1.4B of the 9.1B cache-read tokens/7d (≈15%)** is the
doctrine prefix being re-read on every turn; every one of the 415 subagent spawns re-writes it (~45K × 415 ≈ 19M of
the 258M cache-creation). Cache reads are discounted in the quota weighting (exact weights opaque — Kimi/Gemini
objection, accepted; Codex C6: "bytes removed ≠ quota recovered, the prefix is already cached" — accepted). The boot
tax is therefore primarily a **context-room and quality** lever (45K of every window spent before the first user
token; 290K average context = the documented context-rot zone) and a subagent-boot lever, not a quota lever.

**CI setup overhead** [measured, PR #4450, all pull_request runs]: 574 steps, 104 step-minutes, of which **33 min
(32%) are checkout / setup-python / install / cache-restore / image-pull** — the per-job fixed cost of having 60-68
jobs (Codex D, confirmed).

## 4. Test suite anatomy [reported R-SUITE, load-bearing lines re-verified on origin/main]

- `apps/backend-rag/backend/tests/`: 1,392 files, ~21,430 `def test_`; single pytest process on a 4-vCPU runner;
  **no xdist**; `--cov=backend --cov-branch` on every PR and queue run + `--fail-under=55` gate; job
  `timeout-minutes: 40` (raised from 30 on 2026-08-14 because p95 was 28.6 min).
- Last merge_group job: 25m07s total; setup 3m51s; **"Run unit tests" 20m46s (83%)**. Slowest test 12-15 s; top-50
  slowest sum to ~200-250 s of 1,246 s → **~58 ms/test average: death by a thousand cuts, no whale to quarantine**.
- Tiering baseline: **2 of 21,430 tests** carry `@pytest.mark.slow`; `unit`+`integration` < 2%; no testmon/`--lf`.
- Orphan tree `apps/backend-rag/tests/` (276 files / ~3,376 tests, the ONLY session-scoped DB fixtures in the repo) is
  outside `testpaths`; CI cherry-picks 3 files. Collected by nothing else.
- `pyproject.toml [tool.pytest.ini_options]` is dead config (pytest.ini wins).
- Scar on parallelism: 2026-07-14, 9 lanes against ONE shared Postgres → spurious `migration_112` LISTEN/NOTIFY
  failures. xdist without per-worker DB isolation would re-create that inside one CI job.
- Pre-push backend suite is DEFAULT-OFF since 2026-08-13 → duplication is 2× (PR + queue), not 3×.
- Meta-layer tests (guards/lints/hooks proving guilt+innocence) mostly live in **28 separate workflows**, not in the
  25-min job; the META required gates fire for real (30-day failures: R1 gate 104, antidotes 78, organ-conformance 42,
  root-guard 14; only hook-innocence-gate 0/~200). Failure count measures friction, **not** true-positive rate — the
  R1 gate is known to have failed 3 PRs in one day for narrative frontmatter (memory
  `lesson_r1_frontmatter_is_vocabulary_not_narrative_2026_08_18`).

## 5. Non-Claude seats [reported R-SEATS + author probes]

| Seat | Scheduled callers | Measured use | Waste class | Cure in flight |
|---|---|---|---|---|
| Codex O1 `~/.codex` | 0 on M5; 6 plists on Pro (~39 triggers/day ≈ 207 sessions/7d) | M5 206 sessions/7d, **100% interactive**, 37 from bare main checkout | window burned by refuter/red-team calls (120/7d) | rotation #4446 merged; O1 dead until 22/8 |
| Codex O2 | — | PONG, **8,289 tokens for a one-word reply** (Codex skills-context budget exceeded warning) | per-call prefix tax on the OpenAI side | none |
| Gemini metered (`gemini_service.py`, gemini-3.5-flash) | 0 synthetic; pure inbound WA/web/TG/IG | ~2,238 calls/day, $11.11 one day; 12% cache hit, ~16K in/msg | **cache-miss by construction** (no `cachedContents`; RAG context in last user turn) + no proactive cap | **none** — the only real-$ lever |
| agy (Gemini CLI, flat) | 0 | 165/8d (after telemetry fix #4450) | telemetry lied (fixed); stdin bug (fixed) | **AUTH DEAD on M5 since ~00:14 21/8** ("not logged into Antigravity") → `operator[gui]` |
| Kimi K3 | 0 | 129/8d (after #4450) | none found | — |
| GLM (`claude-glm`) | 0 | 18 calls/7d interactive | **dead with exit 0**: Claude Code 2.1.237 answers `unrecognized_model glm-5.2` (W104 class green-that-lies) | none → ledger line |
| Qwen | 0 | — | 401 credential expired | `operator[business]` |
| Ollama | cron | Pro 3/7 declared models present | no live consumer of the missing 4; PII consumers fail closed | #4443 open (hardening) |

## 6. §Meta-pattern — the disease behind the findings

Every large number above is the same shape: **a safety mechanism whose cost is paid per-unit while its value is paid
per-incident, with nobody owning the product.** The second suite run, the 27 required contexts, the full-tree secrets
scan, the 9 hooks per Bash call, the 70% grader dispatches, the 42K-token doctrine prefix, the Fable-by-default
session — each is individually defensible, each was born from a real scar, and **no organ measures their sum**. The
sibling session's own prompt said it: "the gates add up, and nobody is responsible for the sum". The W-family that
generates this is the same one that generates the 29 ledger-only PRs: the organism records every lesson at the cost
of the next task. A doctrine that grows by accretion (superscar +4 KB/week, CLAUDE.md +3 KB/week) and a CI that grows
by accretion (92 workflows) have the same fix: **a budget per unit of work, enforced by a script, not a rule in prose.**

Corollary (measured on ourselves, twice): the sibling session and this one both paid the ceremony they were
auditing — 120 interactive codex calls burned the refuter seat the council needed; this session's readers each booted
with the full 42K prefix to run a read-only census; and 86% of everything the fleet's most expensive model emitted
this week was reasoning nobody reads, at a budget nobody chose per task.

## 7. Levers — ranked by (time or window recovered) ÷ (risk × effort)

| # | Lever | Recovers (per PR unless noted) | Risk | Effort | Enforced where | 7-day proof |
|---|---|---|---|---|---|---|
| **L0** | **Reasoning budget tied to the gear**: interactive sessions default to `effort=medium` (Opus 5) for Gear 1-2 turns, `xhigh` for Gear 3 design/verify turns, `max` reserved for the final on-disk gate; routine ship-tail turns (status, ledger, recap) never at `xhigh`/`max`. Implementation: `/effort` per session + a modus §STAGE 0 line; a weekly census of output-token composition as the receptor | the largest single number: ~86% of 32.3M output tok/7d is thinking; at 63% Fable share. Even a 30% cut in thinking on Gear 1-2 turns ≈ 8M output tok/week | LOW-MED: under-thinking a Gear-3 decision is the failure mode → gear-gated, never blanket; the final gate untouched | `/effort` + doctrine line (operator-gated) | output tokens/PR ↓ ≥25% with correction-PR rate flat |
| L13 | **Take `npm audit` out of the required merge-queue gate** (advisory/nightly job instead of a `merge_group`/`pull_request` blocker) — new lever, see §13.3 | kills the class of failure that made 2026-08-17 a lost day: 19 failures across 4 PRs, 9-17 re-entries each, 29-33 h open→merge (#4264 never merged) | LOW-MED: a genuinely new advisory on a used package is still caught, just nightly instead of same-day-blocking | 1 PR | tests.yml / new nightly workflow | 0 queue-required failures on `npm audit` over 7 days; nightly run still reports advisories |
| L14 | **Cache `~/.cache/ms-playwright` keyed on the playwright version** — new lever, see §13.3 | the 2026-08-19 tail (8 failures on `Install Playwright browsers`), network-bound install time on every job | LOW (standard `actions/cache` pattern) | 1 PR | tests.yml | `Install Playwright browsers` ≤ 1 min on cache hit; cache hit-rate ≥ 90% over 7 days |
| L15 | **Main-red circuit breaker**: same required job failing on ≥2 consecutive queue groups → pause the queue + alert instead of rebuilding 30 min × N — new lever, see §13.3 | the wasted rebuild cost of every PR that churns behind a broken main (2026-08-17/19 tail) | MED: needs a safe pause that releases itself once the job is green again, never blocks a legitimately cured main | 1-2 PRs | tests.yml / merge-queue tooling | no group rebuilt >1× against a main-red window; alert fires ≤5 min after the 2nd consecutive same-job failure |
| L1 | **DOWNGRADED by measurement, 2026-08-21 — see §13.2.** ~~Queue batching: `min_entries_to_merge` 1→3, wait 2→4 min~~ — re-entry rises steeply with group size (24%→85% at size 3), so batching would move most merges into the worst bucket; do not flip until the conditional failure rate is understood. Superseded as the top lever by L13-L15 (the tail, not the batching) | merge_group runner-min ÷ ~2-3 at today's cadence (10 PRs/80 min) AND fewer evictions (re-entry ratio 1.5 → ~1.1); 0 wall-clock — **claim not actioned, see §13.2** | LOW, config-only, reversible (`gh api` ruleset PATCH) | minutes | ruleset | merge_group runs ÷ merged PRs ≤ 1.15 over 7 days (today 1.5) — retained as the metric to watch, not a target to hit by flipping this lever |
| L2 | **DONE 2026-08-21 (Code Quality disabled).** Not CodeQL default setup as first identified (corrected, §13.1) — the duplicate was GitHub's separate **Code Quality** feature; disabled at repo Settings → Code quality | ~13.7 runner-min | LOW (one of two identical analyses) | session, via GUI (corrected from `operator[gui]` — the session executed it directly) | GitHub setting | `Code Quality`-named `dynamic`-event runs = 0 since 2026-08-20T18:40Z [measured 2026-08-20T18:51:39Z] |
| L3 | **Diff-scope Detect Secrets on PRs** (scan `hotzone_changed_files.sh` output only) + keep the full-tree scan on `push: main` and nightly | ~15-17 min runner; ~15 min wall-clock on docs-only PRs | MED: a secret in an UNCHANGED file is caught by the nightly, not the PR (acceptable: it is already on main) | 1 PR | security.yml | Detect Secrets ≤ 2 min on PRs; nightly full scan green; baseline unchanged |
| L4 | **Stop the serial double-run** — option A: make `pull_request` Backend Tests "impacted domains + smoke" and keep the queue run as THE gate; option B: skip the queue run when the queue merge-commit **tree hash** equals the tree the PR run tested (only true when main did not move) | option A ≈ 25-28 min wall-clock per PR; option B rarely fires at 37 merges/day | **MED-HIGH**: A moves failure discovery to the queue (ejection = +60 min for that PR; cross-PR coupling still caught); B is safe but low-yield | spike + 1 PR | tests.yml | median open→merge ≤ 40 min; queue failure rate not above today's 9% |
| L5 | **DONE 2026-08-21 (discovered stale, not built — §13.5).** ~~Docs lane: a PR whose diff is 100% in `DOC_PREFIXES/SUFFIXES` (already defined in `change_map.py`) runs actionlint + diff-scoped secrets + doc lints only~~ — the mechanism landed via #4181 (2026-08-14, tests.yml's six heavy jobs) and #4444 (2026-08-20, security.yml's CodeQL/Bandit/Snyk + diff-scoped Detect Secrets), both gated on the identical `change_map.py` domain model this row proposed building. All 27 required contexts measured green on two real single-file docs-only PRs in ≤1m53s each (§13.5) | **compute-cost target MET**: 28-33% of PRs already pay <2 min of required-check compute (was ~80 runner-min pre-#4181/#4444); the **wall-clock target (≤8 min median) is NOT yet met** — measured 25-38 min median on the same two PRs, of which ~72% is post-green merge-queue wait, not gate compute (§13.5). That residual is L1/L4's remit, not this row's | LOW-MED (realized): no new guard was added by this row's own PR — it only added one literal guilt+innocence test pinning the mandate's 50:1 docs:code ratio (`scripts/ci/test_change_map.py`) on top of the already-thorough corpus #4181/#4444 shipped with | 1 PR (`agent/air-m5/ops/l5-docs-lane`) | change_map + required-check `if:` (already on origin/main) | **met**: docs-only required-check compute ≤2 min (was ≤8 min target) — **not yet met**: docs-only PR median open→merge ≤8 min (blocked on L1/L4, tracked separately) |
| L6 | **Give the floor a ceiling.** The deterministic gear floor ALREADY EXISTS and is CI-enforced (`scripts/evidence_pack_lint.py::compute_floor()` via `harness-floor.yml`, fail-closed, floor 1 = non-hot-zone / floor 3 = hot-zone; "the model may only raise the gear, never lower it below the floor") and the 2026-08-19 ruling already splits the FINAL GATE by floor (floor-1 → Opus 5, floor-3 → Fable). What is missing is the **ceiling**: a floor-1 diff still pays council, cross-family refuters, Evidence Pack prose and `xhigh` thinking. Amendment (operator-gated): floor 1 ⇒ no council, no external refuter unless the author requests one, `effort=medium`, targeted test + required CI + `--auto` + PROVE-LIVE on the one consumer; any CI red, second file, or hot-zone touch re-floors | the 70%-grader share on trivial diffs; the 120 codex calls/7d that killed O1 | MED: under-match is the dangerous direction → the floor stays the single source of truth (`compute_floor`, not a second predicate — Kimi B1); shadow refuter on a 20% random sample of floor-1 PRs; any shadow-only defect revokes the ceiling | modus §STAGE 0 amendment + 1 receipt line in the Evidence Pack | harness-floor (exists) + modus | ≥20 floor-1 PRs with revert/CI-red rate ≤ baseline; external-seat calls per floor-1 PR ≤ 0.2 (Codex C5 metric) |
| L7 | **Prefix diet**: `cicatrix-superscar.md` declares itself "~2k tokens" in its own header and is 70,970 B (~19K tokens) on origin/main — a 10× drift (Kimi C6). Trim target = the scar-level inline narratives (W95-W119 verbatim bodies in the MEMBRI paragraphs), **keeping the per-family MALATTIA/segnale/antidoto skeleton** (that IS the design; a careless trim re-creates the W77 flat blob). Dedupe global vs project CLAUDE.md (−3-5 KB). Add a CI byte budget on the auto-loaded set (fail on growth) | ~25-30% of the 42K boot tokens, every session and every subagent — a context-room/quality lever, not a quota lever (Codex C6) | LOW for content (bodies stay in `cicatrix-scars.md`, `scar query` still finds them); the cap is a new guard → guilt+innocence tests | 1-2 PRs | CI lint | `wc -c` of the auto-loaded set ≤ 100 KB on main; median cache_creation/turn below today's 1,148 |
| L8 | **Gemini metered**: static-first/volatile-last prompt order + explicit `cachedContents` for system prompt + RAG scaffold; proactive daily USD cap on THIS pool (not the cascade breaker) | $/msg — A/B needed; denominator known (16K in/msg, 12% hit) | MED: prompt reorder can change answer quality → shadow A/B on 50 msgs first; PII stays in the same pool it already uses | 1-2 PRs + Fly deploy | `gemini_service.py` + breaker | cache-hit ≥ 60% on `llm_cost_events`; $/day ↓ with msgs/day flat |

> **AMENDED 2026-08-21 — L8's premise is expiring (Zero, Legge 5).** Ruling given while approving
> the world-practice levers: *"Gemini non sara piu il bot ma chatgpt"* — the conversational bot lane
> moves off Gemini to ChatGPT (subscription path per the 2026-08-15 owner ruling;
> `OPENAI_WA_PROVIDER_API_KEY` remains barred). L8 is metered **only because `rag.gateway.chat` is
> the bot path**, so its "the only real-$ lever" framing dies with the cutover. Split L8 accordingly:
> - **cache half** (`cachedContents` for the static prefix, prompt reorder, shadow A/B) — **SUSPENDED**:
>   do not build it against a pool being retired. Re-derive the target after cutover; the Anthropic-side
>   prefix work is a separate lever and is unaffected.
> - **cap half** (proactive USD/day breaker on this pool, degrading — never silent, per C8) — **STAYS
>   LIVE and rises in priority**: a destination is not a switch, WA runs on Gemini until the OpenAI path
>   is armed, and a pool nobody is optimising any more is exactly the one that needs a brake. The
>   4th prepay depletion (2026-08-11) already left WA mute once.
> This amendment retracts the *ranking rationale*, not the observation: the 12% cache hit and
> ~16K in-tokens/msg measured on `llm_cost_events` remain true of the pool as it runs today.

| L9 | **Suite**: (i) drop `--cov-branch` from PR runs, keep full coverage on the 2-hourly main run; (ii) xdist **spike** with per-worker DB (`nuzantara_test_gw{n}`); (iii) fold or delete the orphan tree; (iv) delete dead pyproject pytest block | (i) 2-6 min [estimated]; (ii) 2-3× on the 21-min step if the spike holds; (iii) 0 min, −3,376 phantom tests | (i) LOW; (ii) **MED-HIGH** (2026-07-14 scar); (iii) LOW | (i) 1 PR; (ii) spike; (iii) owner call | tests.yml / conftest | step time; coverage % unchanged on main |
| L10 | **Model mix**: two standing rulings on origin/main — interactive default = Opus 5 (2026-07-25, CLAUDE.md §104) and **"Fable 5 non fa review di piccoli interventi. Usiamo Opus 5 per quelle"** (2026-08-19, §112, gate split by the deterministic floor). The measured 56% message / 63% output-token Fable share is non-compliance with both until a newer dated ruling exists (Kimi C7, Codex C7 — the "owner's choice for the week" inference is withdrawn; this session runs Fable by an explicit `/model`, nothing more) | Fable share 63% of output → ~10% | business (Legge 5): ratify or restore | `/model` | doctrine | model mix in transcripts |
| L12 | **CI setup consolidation**: fewer, fatter jobs (shared checkout/setup/cache per workflow), pinned base images from GHCR (kills the Docker Hub `toomanyrequests` queue failures), `actions/cache` hit-rate audit | up to ~33 runner-min/PR (32% of step-minutes) | LOW-MED (workflow refactor, actionlint-gated) | 2-3 PRs | workflows | setup-class step-min/PR ≤ 15 |
| L11 | **Seat arming**: agy re-login (`operator[gui]`); GLM shim: map to a model name the CLI accepts or pin Claude Code < 2.1.237 for that config dir; Codex O1 waits for 22/8 | restores 2 council families | LOW | minutes | arsenal_probe | PONG from each |

**Order of attack** (highest yield per risk): **L0 → L13 → L14 → L15 → L2 → L3 → L5 → L12 → L7 → L9(i) → L6 → L8 →
L4(A) → L9(ii)**. **Corrected 2026-08-21 (see §13.2/§13.3):** L1 dropped out of this ranking — do not flip
`min_entries_to_merge` until the conditional failure rate (24%→85% re-entry by group size) is understood; L13-L15
(the tail, not the batching) take its place as the next lever after L0. L2 is DONE (Code Quality disabled, §13.1).
L5 is DONE on the compute metric (§13.5) — its residual wall-clock gap is L1/L4, not further docs-lane work.
L10/L11 are owner/operator actions and gate everything else's denominator. Codex's risk-adjusted order
(C4 → C3 → C2 → C6 → C5 → C8) agrees on the CI head of the list and ranks the Gemini lever last because it buys
dollars, not windows — accepted.

## 8. Ship-path Gear 1 — the spec the sibling session left in prose (to be armed as code)

- **Entry predicate = the existing floor, not a second classifier** (Kimi C5/B1): `compute_floor()` on the final
  merge-base diff returns 1 (non-hot-zone) — that is the ONLY eligibility test, so the hot-zone list stays the single
  source of truth. Additional *ceiling* conditions the session checks in 30 s and records in the pack: ≤ 60 net lines,
  no new `import`, no registry/prompt/workflow path, a named cause in the PR body. Unknown → Gear 2.
- **What Gear 1 skips:** council, cross-family refuter seats, Evidence Pack prose, research capture, AMENDMENTS line.
- **What Gear 1 keeps:** worktree, targeted test, required CI (docs lane if docs-only), `--auto` merge, PROVE-LIVE
  on the one consuming surface, a 1-line ledger entry only if something is left un-armed.
- **Exit condition (forces re-gearing):** a second file appears, an unexpected CI red, behaviour expansion, live
  rollout needed, or the predicate script itself changed in the diff.
- **Falsifier (pre-registered):** shadow for 20 candidates; then enforce; revoke the whole class on the first Gear-1 PR
  that is reverted or needs a corrective follow-up within 48 h; weekly metric = Gear-1 revert rate vs the 284-PR
  baseline (currently 6 corrections + 13 closed / 284).

## 9. Probes to delegate (copyable)

```bash
# L1 — batch the queue (reversible; record the old JSON first)
gh api repos/{owner}/{repo}/rulesets/19779175 > /tmp/ruleset-19779175.before.json
# PATCH min_entries_to_merge=3, min_entries_to_merge_wait_minutes=4 (rules[].parameters) — session, not operator
# proof: gh run list --workflow tests.yml --event merge_group --created ">=$(date -v+1d +%F)" | wc -l  vs merged PRs

# L2 — DONE 2026-08-21: who ran 'Analyze (python)' was GitHub's Code Quality feature, not org-level CodeQL default
# setup (corrected, §13.1) — code-scanning/default-setup genuinely reports not-configured, it just wasn't the source
gh api repos/{owner}/{repo}/code-scanning/default-setup          # state: not-configured (true, but not the answer)
gh api orgs/{org}/code-security/configurations/17/repositories   # [] — zero attached repos, confirms no org default setup
gh api "repos/{owner}/{repo}/actions/runs?event=dynamic&created=>=<disable-ts>" \
  --jq '[.workflow_runs[]|select(.name|startswith("Code Quality"))]|length'   # proof: 0 after disablement

# L3 — detect-secrets on changed files only (prove equivalence on the last 20 PRs before switching)
for n in $(gh pr list --state merged --limit 20 --json number --jq '.[].number'); do
  gh pr view $n --json files --jq '.files[].path' | xargs detect-secrets scan --baseline .secrets.baseline; done

# L7 — boot-tax cap
wc -c ~/.claude/CLAUDE.md CLAUDE.md .claude/rules/*.md ~/.claude/projects/-Users-balizero-nuzantara/memory/MEMORY.md

# L8 — Gemini cache hit, by hour (postgres read-only MCP)
# SELECT date_trunc('hour',created_at), count(*), sum(cost_usd), avg(cache_read_tokens::float/nullif(input_tokens,0))
#   FROM llm_cost_events WHERE endpoint='rag.gateway.chat' AND created_at>now()-interval '3 days' GROUP BY 1 ORDER BY 1;

# §3 — ceremony metric to re-run weekly (M5)
# python3 scripts/usage/ceremony_census.py  (to be written: gears, grader/builder dispatch ratio, pre/post-PR token split)
```

## 10. PENDING-ARMS lines proposed

- opened 2026-08-21 (m5, audit session), **CLOSED 2026-08-21** | **CodeQL ran twice per PR — the custom `codeql` job in security.yml (required) and, mischaracterized at open as CodeQL's org-level default setup, actually GitHub's separate Code Quality feature (`Code Quality: CodeQL Setup` / `Code Quality: PR #N`, event `dynamic`) — ~13.7 runner-min/PR with zero marginal value (see §13.1)** | arming step taken: disabled at repo Settings → Code quality by the session (GUI action, not `operator[gui]` after all) | owner: session | proof: `Code Quality`-named `dynamic`-event runs = 0 since 2026-08-20T18:40Z, checked 2026-08-20T18:51:39Z.
- opened 2026-08-21 (m5) | **merge queue never batches (`min_entries_to_merge: 1`)** | arming step: ruleset PATCH to 3 / wait 4 min, record before/after | owner: session | proof: merge_group runs/day ÷ merged PRs/day ≤ 0.5 after 7 days.
- opened 2026-08-21 (m5) | **`claude-glm` shim dead with exit 0 on Claude Code 2.1.237 (`unrecognized_model glm-5.2`)** — the first-call refuter seat is un-armed and `arsenal_probe.py` would read RC 0 as alive | arming step: probe must judge the REPLY (`PONG`), not RC; shim: acceptable model alias or pinned CLI for that config dir | owner: session | proof: `claude-glm -p PONG` prints PONG.
- opened 2026-08-21 (m5) | **agy AUTH DEAD on M5** ("You are not logged into Antigravity") since 2026-08-21 00:14 | arming step: interactive re-login | owner: `operator[gui]` | proof: `agy -p PONG`.
- opened 2026-08-21 (m5) | **`wr2.oracle` still enabled and LLM-reaching after the WR2 stop** (sibling finding) | arming step: disable or prove a consumer | owner: session (Pro) | proof: `launchctl print gui/$(id -u)/com.balizero.wr2.oracle` → disabled, or a named reader of its output.
- opened 2026-08-21 (m5) | **Gemini metered pool has no proactive spend cap** (L8, cap half — the cache half is SUSPENDED by the 2026-08-21 ruling that moves the bot to ChatGPT; see the amendment under the L8 row) | arming step: breaker on `rag.gateway.chat` USD/day, degrading not silent (C8). Do NOT build `cachedContents` against this pool | owner: session | proof: `llm_cost_events` cache-hit ≥ 60%, $/day ↓ with msgs flat.
- opened 2026-08-21 (m5) | **The deterministic gear floor (`compute_floor`, harness-floor.yml) has no ceiling: a floor-1 diff still pays council + cross-family refuters + Evidence Pack + `xhigh` thinking** (this doc §8, L0/L6) | arming step: modus §STAGE 0 amendment "floor 1 ⇒ effort medium, no council, no external refuter unless requested" + shadow refuter on a 20% sample | owner: `operator[business]` for the doctrine line, session for the receipt | proof: 20 floor-1 PRs logged with external-seat calls ≤ 0.2/PR and revert rate ≤ baseline.
- opened 2026-08-21 (m5) | **Merge-queue re-entry amplification: 388 merge_group runs for 258 merged PRs since 2026-08-14 (ratio 1.5)** — `min_entries_to_merge: 1` + ~37 main pushes/day evicts and re-runs | arming step **corrected 2026-08-21 (§13.2)**: NOT the L1 ruleset PATCH — re-measurement (392 runs / 264 PRs / 303 groups, re-entry 24%→85% by group size) shows batching would move most merges into the worst re-entry bucket; arm L13-L15 (the tail levers) instead, then re-measure | owner: session | proof: ratio ≤ 1.15 over 7 days (metric retained; batching is not the path to it).
- opened 2026-08-21 (m5) | **Interactive model mix is non-compliant with two standing rulings** (2026-07-25 Opus default; 2026-08-19 "Fable never on small diffs"): Fable = 56% of messages / 63% of output tokens on M5 in 7d, ~86% of which is thinking | arming step: owner ratifies or restores; session default `/model opus` + `/effort` per gear | owner: `operator[business]` | proof: weekly model-mix census from transcripts.
- opened 2026-08-21 (m5) | **auto-loaded doctrine has no size budget** (148 KB local / 155 KB origin/main, growing ~7 KB/week) | arming step: pointer-format restore of superscar W95-W119 + CI cap lint with guilt+innocence tests | owner: session | proof: `wc -c` of the auto-loaded set ≤ 100 KB on main.

## 11. §Solo-operatore

- L10 model mix (Fable 56% of interactive turns vs §5 Opus-5 default) — business decision, Legge 5.
- agy re-login, Qwen credential, Codex O1 window (22/8 08:30) — credentials only the owner holds.
- ~~Org-level CodeQL default setup toggle — GitHub GUI.~~ **RESOLVED 2026-08-21 (§13.1):** not org-level CodeQL
  default setup after all (org security configuration 17 has zero attached repositories) — it was the repo-level
  **Code Quality** feature, and the session disabled it directly at repo Settings → Code quality; no operator
  action was needed.
- Whether the WR2 pipeline (now stopped) is retired or re-designed with a real publisher — business.

## 12. Checklist pre-arming for any NEW automation or gate (machine-checkable)

A lint reads the PR and fails unless the new plist/workflow/hook/required-check declares: `model` (or `none`),
`interval`, `consumer` (who reads the output), `cost_per_run` (runner-min or tokens, measured on one real run),
`skip_predicate` (when it may not run), `sunset` (the metric that would retire it). The organism already has the
shape (`automation_catalog.json` has `produces`/`consumes`, `change_map.py` has domains) — what is missing is the
field and the lint, not the idea.

## 13. Post-merge corrections (2026-08-21)

PR #4454 (which shipped this document) froze on arm — Agent PR Contract rule 2 ("arm means freeze"; every follow-up
goes in a new PR from a fresh `origin/main`). This section is that follow-up. The CodeQL correction (13.1) is applied
in place above (§2, §7 L2/L1/Order-of-attack, §9, §10, §11, and both C4 rows in the Adversarial review); 13.1 here
only records the proof metric. 13.2-13.4 are new findings from a fresh measurement pass after the document shipped.

### 13.1 CodeQL duplicate — proof metric

`repos/{owner}/{repo}/code-scanning/default-setup` genuinely reports `state: not-configured`; org security
configuration 17 ("GitHub recommended") has **zero attached repositories**
[measured: `gh api orgs/Bali-Zero/code-security/configurations/17/repositories` → `[]`]; `repos/{owner}/{repo}/code-quality`
has no REST surface (`404` [measured]). The duplicate pair (`Analyze (python)` / `Analyze (javascript-typescript)`,
~13.7 runner-min/PR, 713 runs/7d [reported]) is GitHub's separate **Code Quality** feature (repo Settings → Code
quality), not CodeQL default setup — both happen to fire under the Actions `dynamic` event, which is what caused
the original misattribution throughout this document and in both council seats' C4 rows (a second-order W65
instance: the refuter's own refutation was also wrong on attribution). **Status: DISABLED 2026-08-21 ~02:35 WITA
(2026-08-20T18:35Z)** by the session, through the repo settings page (operator-GUI class action executed by the
session). Proof metric, run now:
`gh api "repos/Bali-Zero/Teman2/actions/runs?event=dynamic&created=>=2026-08-20T18:40:00Z" --jq '[.workflow_runs[]|select(.name|startswith("Code Quality"))]|length'`
→ **0**, checked 2026-08-20T18:51:39Z.

### 13.2 L1 (merge-queue batching) — DOWNGRADED by measurement

Objection raised by the peer session (nuzantara-75); measured here. Method: 392 `merge_group` runs of `tests.yml`
since 2026-08-14; queue branch `gh-readonly-queue/main/pr-<N>-<base_sha>`; a run is chained to the run whose
`head_sha` equals its `<base_sha>` AND was created within 120 s (entries of one speculative group are built
together; without the time bound the chain crosses merges via the main tip and collapses to one group — measured).
**PROXY, declared**: group = maximal time-bounded chain. Link-gap histogram: ≤30s 63, ≤120s 26, ≤10m 99, ≤1h 152, >1h 51.

`runs=392 · prs=264 · groups=303 · runs/PR 1.48 · 23% of PRs re-enter at least once`

| Group size | Groups | Later re-entry | Rate | Any non-success | Runs |
|---|---|---|---|---|---|
| 1 | 243 | 59 | 24% | 30 | 243 |
| 2 | 40 | 14 | 35% | 6 | 80 |
| 3 | 13 | 11 | **85%** | 10 | 39 |
| 4 | 5 | 4 | 80% | 2 | 20 |
| 5 | 2 | 1 | 50% | 1 | 10 |

Attempts per PR: `1:203 2:35 3:10 4:4 5:4 6:4 7:3 8:1` → 26 PRs (10%) with ≥3 attempts consume 119 runs (30%).
`merge_group` conclusions: success 329 · failure 57 · cancelled 3 · pending 3 → **15% queue-red on PR-green code**
(57 failure + 3 cancelled of 392).

**Verdict**: re-entry rises steeply with group size (`ALLGREEN`: one red re-queues the whole group). Flipping
`min_entries_to_merge` 1→3 would move most merges into the 85% bucket — the gross ×2.5→×1.8 saving is eaten by
fatter re-entries. **L1 is downgraded** to "do not flip until the conditional failure rate is understood." The
sharper lever is the tail (13.3): why 26 PRs needed 3-8 attempts, and why 15% of queue runs go red on code that was
green on the PR run.

### 13.3 Tail anatomy + three replacement levers (L13-L15)

Failed `merge_group` runs of `tests.yml`, 60 runs, by day × failing step (`Test Summary` aggregator excluded):

| Day | PRs | Failing step (count) |
|---|---|---|
| 2026-08-14 | 7 | Run tests (with coverage) 12 · Initialize containers 1 · Run E2E 1 |
| 2026-08-15 | 1 | Initialize containers 1 |
| 2026-08-17 | 4 | **npm audit 19** |
| 2026-08-18 | 10 | Run unit tests 8 · Install Playwright browsers 1 |
| 2026-08-19 | 6 | **Install Playwright browsers 8** · Run E2E 1 · Initialize containers 1 |
| 2026-08-20 | 7 | Run unit tests 5 · Initialize containers 2 · Run E2E 1 |

2026-08-17: one upstream advisory turned the queue red for a day — PRs #4243/#4244/#4247/#4264 re-entered 9-17× each
(29-33 h open→merge, #4264 never merged).

**Reading**: the re-entry tail is NOT per-PR flakiness — it is **main-red windows** in which every queued PR churns
(30 min × N) until main is cured. Three levers, none of them batching (added to §7 as L13-L15, ranked right after L0):

- **L13** — `npm audit` is a non-hermetic required gate (an external advisory feed can flip green code red with zero
  repo change); move it to an advisory or nightly job, never a queue gate.
- **L14** — Playwright browser install is network-bound; cache `~/.cache/ms-playwright` keyed on the playwright
  version.
- **L15** — when the same required job fails for ≥2 consecutive queue groups, the queue should PAUSE and alert
  rather than rebuild — a "main-red circuit breaker".

### 13.4 Consumer-map lesson (W107 form)

The orphan-tree deletion (PR #4459, open as of 2026-08-21) had two consumers invisible to a
`git grep apps/backend-rag/tests/` census: `.github/workflows/sonarqube.yml` (paths written as `tests/...` after
`cd apps/backend-rag` — confirmed on `origin/main` at lines 136-139: `backend/tests/`, `tests/test_sentry_lazy_import.py`,
`tests/test_sentry_pii_redaction.py`, `tests/kb/test_politics_hierarchical.py`; fix lives in PR #4461, open as of
2026-08-21) and `apps/backend-rag/scripts/backend_stability_gate.py` (a pytest argument list inside a Python script
— confirmed on `origin/main`: `"tests/test_migrations.py"` in the migration-suite invocation; fixed inside #4459
itself, after the required check `Backend Tests (Python)` went red first).

**Rule**: enumerate consumers by **basename** across the whole tree, never by the path prefix you expect to find
them under — a census anchored on the wrong token is the W107 shape (23 counted where 9 were): grepping
`apps/backend-rag/tests/` as a path prefix misses every consumer that references the tree by its cwd-relative
`tests/...` form instead.

### 13.5 L5 (docs lane) — discovered already-shipped, and the wall-clock gap decomposed

Same shape as 13.3's L13-L15 close: this row was dispatched as new work ("implement L5") and turned out to be
**stale, not built** — two other PRs had already shipped its mechanism before this lane started reading. Verified
this lane, not assumed, against `origin/main` and two live PR samples.

**Mechanism, verified on-disk.** `.github/workflows/tests.yml`'s `changes` job (#4181, merged 2026-08-14) gates all
six heavy test jobs on `scripts/ci/change_map.py`'s `suggested_jobs` — for a diff whose only domain is
`docs_content_data` (every path under `DOC_PREFIXES`/`DOC_SUFFIXES`), `suggested_jobs` is `[]` by construction
(`docs_content_data` is not in `PRODUCT_DOMAINS`, so `_suggested_jobs()` never appends a job for it). Frontend Tests
is a matrix job and — per that PR's own CRITICAL fix, cited in `security.yml`'s CodeQL job comment as the reason
CodeQL never carries a job-level `if:` either — its legs are always instantiated, gated at the STEP level, so the
required context still posts (fast, not absent). `.github/workflows/security.yml`'s `changes` job (#4444, merged
2026-08-20T15:01:48Z, i.e. **before** this document's own commit) reuses the identical `change_map.py` classifier
plus a new `scripts/ci/security_gate_flags.py` to gate CodeQL (python + javascript, same always-instantiate/
step-skip pattern, with the job's own comment recording a live incident — PR #4452 — where an earlier job-level
`if:` left both matrix legs' required contexts permanently absent) and Bandit off for docs-only diffs; Detect
Secrets is deliberately never domain-gated (a secret can land in any file) but IS diff-scoped to the changed-file
list (that job's own header cites this exact document as the L3 rationale) — full-tree scan measured 19m34s
(run 31312661093), diff-scoped is seconds. Both `test_change_map.py` and `test_security_gate_flags.py` already
carried a docs-only innocence test before this lane touched anything
(`test_innocence_docs_only_skips_product_test_jobs`, `test_innocence_docs_content_data_only_skips_every_scanner`).

**Empirical proof — all 27 required contexts, two real docs-only PRs, post-#4444.** `gh pr checks 4499` (single file
`.claude/skills/workflow/SKILL.md`, opened 2026-08-21T04:39:32Z): every one of the 27 branch-protection-required
contexts (`gh api repos/Bali-Zero/Teman2/branches/main/protection/required_status_checks --jq '.contexts[]'`) is
either `skipping` in 0s (Backend/MCP/Frontend/E2E Tests, Bandit) or `pass` in ≤1m53s (slowest: `antidotes`;
CodeQL python/js 25-29s; Detect Secrets 33s diff-scoped). The 19 "sentinel"/immune workflows this row never touches
(root-guard, verify-the-verifiers, hot-zone-enforcement, R1 gate, guard-conformance, hook-innocence-gate,
prepush-guards, harness-floor, organ-conformance, the canary/P3/P6/P7/P8/P9 gates, npm-lock-sync, actionlint) were
**already** fast before any of this (29-59s each, confirmed both by this sample and by 3-run `gh run list` medians
on `merge_group` across each workflow) — they were never part of the ~55 min/80 runner-min ceremony this row's
mechanism was scoped to cut, so nothing further needed gating.

**A second, pre-#4444 sample (#4407, created 2026-08-20T06:11, 4h55m BEFORE #4444 merged) shows the counterfactual**:
its `Security Scanning` run took 17m25s wall-clock, with `CodeQL Analysis (python)` alone running 10m9s (full
scan, ungated) and `Detect Secrets` 17m11s (full-tree, pre-diff-scoping) — the exact cost this row's mechanism
removes. Comparing the two samples is what pins #4444's merge timestamp as the actual cutover, not a guess.

**Wall-clock decomposition — where the acceptance bar (≤8 min median) actually fails.** #4499 opened 04:39:32Z,
merged 05:04:42Z = 25m10s. Breakdown by trigger event (`gh api .../actions/runs?head_sha=...` for the PR branch SHA,
then `?event=merge_group` filtered on `head_branch` containing `pr-4499`):
- `pull_request`-triggered checks: all 29 runs complete by 04:41:49Z — **2m17s**.
- `merge_group` queue entry created 04:41:52Z (3s after pull_request checks went green) — this is the serial
  double-run L4 targets (PR #4505, open). Slowest `merge_group` run (`Immune enforcement`) completes 04:46:31Z —
  **4m39s** of re-verification.
- Merge itself lands 05:04:42Z — **18m11s** after every `merge_group` check was already green, with zero required
  work running in that window.

**18m11s of 25m10s (72%) is pure post-green queue wait — not gate compute, and not this row's mechanism.** It
matches §13.2's still-open L1 finding (`min_entries_to_merge: 1`, 388 merge_group runs / 258 merged PRs since
2026-08-14, ratio 1.5) and #4505's still-open L4 fix for the 4m39s double-run. **Conclusion**: this row's own
acceptance bar as originally written ("docs-only PR median ≤8 min") conflated two different quantities — required-
check *compute* cost (now ≤2 min, met, and was the entire mechanism this row described) and PR-open-to-*merge*
wall clock (still 25-38 min median on n=2, blocked on L1/L4/L13-15, none of which this row's mechanism can move).
Closing this row on the compute metric and handing the wall-clock metric to L1/L4 — rather than re-implementing
already-shipped gating a third time — is the correct scope boundary, not a partial close.

**What this PR actually shipped**, since the guard itself needed nothing new: one guilt test pinning the mandate's
own literal 50-docs-files:1-code-file ratio in `scripts/ci/test_change_map.py`
(`test_guilt_one_code_file_among_fifty_docs_still_forces_its_suite`) — mutation-verified against the real
`_suggested_jobs()` (killing a mutant that short-circuits the `backend_python` branch, alongside 14 other tests in
the existing corpus, confirming it is not decorative) — and this section + the corrected L5 row above.

## Adversarial review

Planned: 4 external seats (Codex O2 red-team · Kimi K3 refuter · Gemini agy costruttivo · GLM refuter-2). **Alive at
council time: 2** — agy AUTH-DEAD ("not logged into Antigravity"), GLM dead with exit 0 (`unrecognized_model glm-5.2`
on Claude Code 2.1.237), Codex O1 usage-limited. Two families ≠ Claude → quorum met, **declared degraded**. Dossier:
`council_dossier.md` (this session's scratchpad; reproduced by the §1-§5 data above). Seats ran in read-only sandbox
with the stale-checkout warning; no env/process/credential access. Verdicts are LEADS; every accepted objection below
was re-probed on disk by the author before being folded in.

### Codex GPT-5.6 (O2, `model_reasoning_effort=high`, red-team — "default to defective")

| # | Objection | Disposition | Evidence |
|---|---|---|---|
| C1 | "54% post-PR" is a location, not a cause; 14% Bash share can't explain it | **ACCEPTED, reframed** | decomposition: post-PR output = tool-less turns 62%, CI babysitting 4% → the cause is reasoning budget, not babysitting (§3) |
| C2 | cheap PR run may push logic failures into the queue (9% fail rate already); batching needs arrival-rate check | **ACCEPTED** | L4(A) kept MED-HIGH and late; L1 yield conditional on burstiness (10 PRs/80 min bursts observed) |
| C3 | markdown/json ≠ non-executable; META-gate true-positive rate unmeasured; ledger batching timing unmeasured | **ACCEPTED, narrowed** | docs lane = `DOC_PREFIXES/SUFFIXES` of `change_map.py` minus registries/workflows/prompts; META gates keep running (fast) |
| C4 | `codeql-analysis.yml` is absent → can't be the cure; "0 value" unproven without query-suite comparison | **ACCEPTED, then closed with data** | source = default setup (`dynamic/github-code-scanning/codeql`); custom = `security-extended,security-and-quality` ⊃ default suite → default is redundant (§2). **Corrected 2026-08-21**: the "source" identification here was itself wrong — the duplicate is GitHub's Code Quality feature, not CodeQL default setup (`code-scanning/default-setup` genuinely reports `not-configured`; org config 17 has 0 attached repos). The redundancy finding (two analyses of the same code) stands; the mechanism named for it did not (§13.1) |
| C5 | file/line/path predicates are weak semantic proxies; revert-rate can't falsify silent regressions | **ACCEPTED** | §8: Gear 1 skips LLM seats only, never a machine gate; shadow refuter on a 20% random sample; any shadow-only defect revokes the class |
| C6 | bytes removed ≠ quota recovered (prefix already cached); minimal-context subagents can't drop safety rules | **ACCEPTED** | L7 reframed as context-room + subagent-boot lever; cut = catalogs + superscar narratives, never PII/worktree/merge rules |
| C7 | no datum supports "owner's choice for the week"; 56% is message share not token share | **ACCEPTED, withdrawn** | token-weighted share measured: Fable 63% of output; L10 = owner decision, no inference |
| C8 | dynamic RAG can't be a cached prefix; hard daily cap may silently deny 24h service | **ACCEPTED** | L8 caches only the static scaffold; cap must degrade (local/abstain + alert), never silent |
| C9 | deleting the orphan tree saves 0; folding adds runtime; coverage removal unmeasured | **ACCEPTED** | L9 labels unchanged ([estimated]/owner call) |
| B | top risks: minimal-context subagents (PII/outward actions) · Gear-1 under-gearing · diff-scoped secrets missing renames/baseline drift | **ACCEPTED as tripwires** | policy-canary suite 0 forbidden attempts; shadow gates on every Gear-1 PR 7 days; fake-secret canaries in .md/.json/renamed paths must fail pre-merge 100% |
| D | missing class: CI environment setup across 60-68 jobs | **CONFIRMED by measurement** | 33 of 104 step-min (32%) on PR #4450 → L12 |

### Kimi K3 (refuter — "falsify C1-C9"; it re-read origin/main and the live GitHub API on its own)

| # | Objection | Disposition | Evidence |
|---|---|---|---|
| C5 | partially refuted: a deterministic gear floor already exists (`compute_floor()` + `harness-floor.yml`, fail-closed) and C5 ignored it | **ACCEPTED — load-bearing** | verified on origin/main (`evidence_pack_lint.py:61-96`, `harness-floor.yml:21-32`); L6 rewritten as "give the floor a ceiling", single source of truth kept |
| C7 | refuted pending evidence: two standing rulings (2026-07-25 Opus default; 2026-08-19 "Fable never on small diffs") | **ACCEPTED** | CLAUDE.md §104 and §112 on origin/main, verbatim quote confirmed; L10 reframed as non-compliance until a newer ruling |
| C6 | weakened: the superscar design is per-family narratives, not 1-line per scar; the drift is 10× vs its own "~2k token" header | **ACCEPTED** | L7 trim target = scar-level inline bodies, family skeleton kept |
| C2 | weakened: smoke-only PR run concentrates detection in the queue; ejection = +60 min; gain holds only if queue failure rate stays flat | **ACCEPTED** (same as Codex) | L4(A) gated on the B3 tripwire (7d queue failure rate ≤ 2× baseline) |
| C4 | "confirmed": `codeql-analysis.yml` active + absent → delete it, cleanest win | **REFUTED on attribution** (W65: the refuter also hallucinates) | that workflow's last run is 2026-02-14; the live duplicate is `dynamic/github-code-scanning/codeql` (default setup, `default` suite ⊂ custom `security-extended`); cure = disable default setup at org level. **Corrected 2026-08-21**: Kimi's own attribution here was *also* wrong — the live duplicate is GitHub's Code Quality feature (`Code Quality: CodeQL Setup` / `Code Quality: PR #N`), not CodeQL default setup; org security configuration 17 has zero attached repositories, so no default setup runs above this repo. A second-order W65 instance: the refuter's refutation was wrong on the same axis it refuted. Cure executed anyway (right action, wrong mechanism named): disabled at repo Settings → Code quality (§13.1) |
| C9 | orphan tree is 310 files, not 276 | **REFUTED** | `git ls-tree -r origin/main apps/backend-rag/tests \| grep -c test_*.py` = 276 |
| C8 | only the static system prompt is cacheable; if it is ~2K of 16K the gain caps near today's 12% | **ACCEPTED as probe-first** | L8 step 0 = log static vs volatile token split per call for 24 h before building |
| C1 | agreement with caveat: part of post-PR output is doctrine-mandated queue-watch | **ACCEPTED** | and now measured: babysitting is 4% of post-PR output; reasoning is the mass |
| B | risks: (1) floor/hot-zone drift under-gears a migration/workflow → weekly diff of floor-1 paths vs `hotzone_changed_files.sh` changelog; (2) diff-scoped secrets scanning 0 files and passing green (the GLM-shim class) → echo scanned-file count, fail on 0, nightly full scan alerts within 24 h; (3) cheap PR run → 7-day rolling queue failure rate, auto-rollback at 2× baseline | **ACCEPTED as tripwires** | folded into L3/L4/L6 |
| D | missing class: merge-queue re-entry amplification (`min_entries_to_merge: 1` + every main push evicts) — probe runs ÷ merged PRs | **CONFIRMED by measurement, large** | 388 runs / 258 merged PRs since 2026-08-14 = **1.5** (§2); L1's proof metric now uses this ratio |

**Council summary**: 2 of 4 planned seats alive (degraded, declared). 19 objections; 16 accepted (6 of them changed
a lever's shape: C1→L0/§3, C4→L2 source, C5→L6 ceiling, C6→L7 target, C7→L10, D→L1 metric + L12), 2 refuted with
on-disk evidence (Kimi C4 attribution, Kimi C9 count), 1 confirmed by a new measurement (Codex D, 32% setup).
Nothing in either review touches the invariants; no seat proposed disabling a security control.
