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
> followed by the CI double-run and the docs-lane. The only real-dollar lever (Gemini metered pool, 12% cache hit) is
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
  + Analyze (javascript-typescript) 3 min** — the latter pair comes from GitHub's **CodeQL default setup**
  (`dynamic/github-code-scanning/codeql`, event `dynamic`; the repo API reports `state: not-configured`, i.e. it is
  enabled above the repo, org-level) and duplicates the custom job: **~13.7 runner-min/PR, not required**. Which of
  the two is redundant [measured on origin/main]: the custom job runs `queries: security-extended,security-and-quality`
  + `.github/codeql-config.yml` (one filter); default setup runs the `default` suite, a strict subset → **the default
  setup is the redundant one** (Codex objection C4 answered with data; the workflow `codeql-analysis.yml` listed as
  "active" last ran 2026-02-14 and is NOT the source — the source is `dynamic/github-code-scanning/codeql`).
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
| L1 | **Queue batching**: `min_entries_to_merge` 1→3, wait 2→4 min | merge_group runner-min ÷ ~2-3 at today's cadence (10 PRs/80 min) AND fewer evictions (re-entry ratio 1.5 → ~1.1); 0 wall-clock | LOW, config-only, reversible (`gh api` ruleset PATCH) | minutes | ruleset | merge_group runs ÷ merged PRs ≤ 1.15 over 7 days (today 1.5) |
| L2 | **Disable the duplicate CodeQL default setup** (org/repo Settings → Code security) OR drop the custom job and make `Analyze (*)` the required contexts | ~13.7 runner-min | LOW (one of two identical analyses) | `operator[gui]` (setting) or 1 PR + branch-protection PATCH | GitHub setting | `Analyze (python)` absent from PR checks; CodeQL alerts count unchanged |
| L3 | **Diff-scope Detect Secrets on PRs** (scan `hotzone_changed_files.sh` output only) + keep the full-tree scan on `push: main` and nightly | ~15-17 min runner; ~15 min wall-clock on docs-only PRs | MED: a secret in an UNCHANGED file is caught by the nightly, not the PR (acceptable: it is already on main) | 1 PR | security.yml | Detect Secrets ≤ 2 min on PRs; nightly full scan green; baseline unchanged |
| L4 | **Stop the serial double-run** — option A: make `pull_request` Backend Tests "impacted domains + smoke" and keep the queue run as THE gate; option B: skip the queue run when the queue merge-commit **tree hash** equals the tree the PR run tested (only true when main did not move) | option A ≈ 25-28 min wall-clock per PR; option B rarely fires at 37 merges/day | **MED-HIGH**: A moves failure discovery to the queue (ejection = +60 min for that PR; cross-PR coupling still caught); B is safe but low-yield | spike + 1 PR | tests.yml | median open→merge ≤ 40 min; queue failure rate not above today's 9% |
| L5 | **Docs lane**: a PR whose diff is 100% in `DOC_PREFIXES/SUFFIXES` (already defined in `change_map.py`) runs actionlint + diff-scoped secrets + doc lints only; ledger writes ride in the feature PR that caused them (already the modus rule W86 for docs_sync) | 28-33% of PRs drop from ~55 min/80 runner-min to <5 min/<10 runner-min | LOW-MED: required contexts must still be *satisfied* (skipped-with-success pattern already proven by #4181) | 1 PR | change_map + required-check `if:` | docs-only PR median ≤ 8 min; ledger-only PR count/week ↓ |
| L6 | **Give the floor a ceiling.** The deterministic gear floor ALREADY EXISTS and is CI-enforced (`scripts/evidence_pack_lint.py::compute_floor()` via `harness-floor.yml`, fail-closed, floor 1 = non-hot-zone / floor 3 = hot-zone; "the model may only raise the gear, never lower it below the floor") and the 2026-08-19 ruling already splits the FINAL GATE by floor (floor-1 → Opus 5, floor-3 → Fable). What is missing is the **ceiling**: a floor-1 diff still pays council, cross-family refuters, Evidence Pack prose and `xhigh` thinking. Amendment (operator-gated): floor 1 ⇒ no council, no external refuter unless the author requests one, `effort=medium`, targeted test + required CI + `--auto` + PROVE-LIVE on the one consumer; any CI red, second file, or hot-zone touch re-floors | the 70%-grader share on trivial diffs; the 120 codex calls/7d that killed O1 | MED: under-match is the dangerous direction → the floor stays the single source of truth (`compute_floor`, not a second predicate — Kimi B1); shadow refuter on a 20% random sample of floor-1 PRs; any shadow-only defect revokes the ceiling | modus §STAGE 0 amendment + 1 receipt line in the Evidence Pack | harness-floor (exists) + modus | ≥20 floor-1 PRs with revert/CI-red rate ≤ baseline; external-seat calls per floor-1 PR ≤ 0.2 (Codex C5 metric) |
| L7 | **Prefix diet**: `cicatrix-superscar.md` declares itself "~2k tokens" in its own header and is 70,970 B (~19K tokens) on origin/main — a 10× drift (Kimi C6). Trim target = the scar-level inline narratives (W95-W119 verbatim bodies in the MEMBRI paragraphs), **keeping the per-family MALATTIA/segnale/antidoto skeleton** (that IS the design; a careless trim re-creates the W77 flat blob). Dedupe global vs project CLAUDE.md (−3-5 KB). Add a CI byte budget on the auto-loaded set (fail on growth) | ~25-30% of the 42K boot tokens, every session and every subagent — a context-room/quality lever, not a quota lever (Codex C6) | LOW for content (bodies stay in `cicatrix-scars.md`, `scar query` still finds them); the cap is a new guard → guilt+innocence tests | 1-2 PRs | CI lint | `wc -c` of the auto-loaded set ≤ 100 KB on main; median cache_creation/turn below today's 1,148 |
| L8 | **Gemini metered**: static-first/volatile-last prompt order + explicit `cachedContents` for system prompt + RAG scaffold; proactive daily USD cap on THIS pool (not the cascade breaker) | $/msg — A/B needed; denominator known (16K in/msg, 12% hit) | MED: prompt reorder can change answer quality → shadow A/B on 50 msgs first; PII stays in the same pool it already uses | 1-2 PRs + Fly deploy | `gemini_service.py` + breaker | cache-hit ≥ 60% on `llm_cost_events`; $/day ↓ with msgs/day flat |
| L9 | **Suite**: (i) drop `--cov-branch` from PR runs, keep full coverage on the 2-hourly main run; (ii) xdist **spike** with per-worker DB (`nuzantara_test_gw{n}`); (iii) fold or delete the orphan tree; (iv) delete dead pyproject pytest block | (i) 2-6 min [estimated]; (ii) 2-3× on the 21-min step if the spike holds; (iii) 0 min, −3,376 phantom tests | (i) LOW; (ii) **MED-HIGH** (2026-07-14 scar); (iii) LOW | (i) 1 PR; (ii) spike; (iii) owner call | tests.yml / conftest | step time; coverage % unchanged on main |
| L10 | **Model mix**: two standing rulings on origin/main — interactive default = Opus 5 (2026-07-25, CLAUDE.md §104) and **"Fable 5 non fa review di piccoli interventi. Usiamo Opus 5 per quelle"** (2026-08-19, §112, gate split by the deterministic floor). The measured 56% message / 63% output-token Fable share is non-compliance with both until a newer dated ruling exists (Kimi C7, Codex C7 — the "owner's choice for the week" inference is withdrawn; this session runs Fable by an explicit `/model`, nothing more) | Fable share 63% of output → ~10% | business (Legge 5): ratify or restore | `/model` | doctrine | model mix in transcripts |
| L12 | **CI setup consolidation**: fewer, fatter jobs (shared checkout/setup/cache per workflow), pinned base images from GHCR (kills the Docker Hub `toomanyrequests` queue failures), `actions/cache` hit-rate audit | up to ~33 runner-min/PR (32% of step-minutes) | LOW-MED (workflow refactor, actionlint-gated) | 2-3 PRs | workflows | setup-class step-min/PR ≤ 15 |
| L11 | **Seat arming**: agy re-login (`operator[gui]`); GLM shim: map to a model name the CLI accepts or pin Claude Code < 2.1.237 for that config dir; Codex O1 waits for 22/8 | restores 2 council families | LOW | minutes | arsenal_probe | PONG from each |

**Order of attack** (highest yield per risk): **L0 → L1 → L2 → L3 → L5 → L12 → L7 → L9(i) → L6 → L8 → L4(A) →
L9(ii)**. L10/L11 are owner/operator actions and gate everything else's denominator. Codex's risk-adjusted order
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

# L2 — who runs 'Analyze (python)': default setup above the repo (org-level)
gh api repos/{owner}/{repo}/code-scanning/default-setup          # state: not-configured (repo) → check org Settings → Code security
gh run view 32381473497 --json workflowName,event                 # "CodeQL | dynamic"

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

- opened 2026-08-21 (m5, audit session) | **CodeQL runs twice per PR — the custom `codeql` job in security.yml (required) and GitHub's default setup (`dynamic/github-code-scanning/codeql`, enabled above the repo) — ~13.7 runner-min/PR with zero marginal value** | missing arming step: disable default setup at the org level OR make `Analyze (python|javascript-typescript)` the required contexts and delete the custom job | owner: `operator[gui]` for the setting, session for the PR variant | proof: `gh pr checks <next PR>` shows one CodeQL pair.
- opened 2026-08-21 (m5) | **merge queue never batches (`min_entries_to_merge: 1`)** | arming step: ruleset PATCH to 3 / wait 4 min, record before/after | owner: session | proof: merge_group runs/day ÷ merged PRs/day ≤ 0.5 after 7 days.
- opened 2026-08-21 (m5) | **`claude-glm` shim dead with exit 0 on Claude Code 2.1.237 (`unrecognized_model glm-5.2`)** — the first-call refuter seat is un-armed and `arsenal_probe.py` would read RC 0 as alive | arming step: probe must judge the REPLY (`PONG`), not RC; shim: acceptable model alias or pinned CLI for that config dir | owner: session | proof: `claude-glm -p PONG` prints PONG.
- opened 2026-08-21 (m5) | **agy AUTH DEAD on M5** ("You are not logged into Antigravity") since 2026-08-21 00:14 | arming step: interactive re-login | owner: `operator[gui]` | proof: `agy -p PONG`.
- opened 2026-08-21 (m5) | **`wr2.oracle` still enabled and LLM-reaching after the WR2 stop** (sibling finding) | arming step: disable or prove a consumer | owner: session (Pro) | proof: `launchctl print gui/$(id -u)/com.balizero.wr2.oracle` → disabled, or a named reader of its output.
- opened 2026-08-21 (m5) | **Gemini metered pool has no proactive spend cap and no explicit cache** (L8) | arming step: breaker on `rag.gateway.chat` USD/day + `cachedContents` for the static prefix, shadow A/B first | owner: session | proof: `llm_cost_events` cache-hit ≥ 60%, $/day ↓ with msgs flat.
- opened 2026-08-21 (m5) | **The deterministic gear floor (`compute_floor`, harness-floor.yml) has no ceiling: a floor-1 diff still pays council + cross-family refuters + Evidence Pack + `xhigh` thinking** (this doc §8, L0/L6) | arming step: modus §STAGE 0 amendment "floor 1 ⇒ effort medium, no council, no external refuter unless requested" + shadow refuter on a 20% sample | owner: `operator[business]` for the doctrine line, session for the receipt | proof: 20 floor-1 PRs logged with external-seat calls ≤ 0.2/PR and revert rate ≤ baseline.
- opened 2026-08-21 (m5) | **Merge-queue re-entry amplification: 388 merge_group runs for 258 merged PRs since 2026-08-14 (ratio 1.5)** — `min_entries_to_merge: 1` + ~37 main pushes/day evicts and re-runs | arming step: L1 ruleset PATCH (batch 3 / wait 4 min), then re-measure | owner: session | proof: ratio ≤ 1.15 over 7 days.
- opened 2026-08-21 (m5) | **Interactive model mix is non-compliant with two standing rulings** (2026-07-25 Opus default; 2026-08-19 "Fable never on small diffs"): Fable = 56% of messages / 63% of output tokens on M5 in 7d, ~86% of which is thinking | arming step: owner ratifies or restores; session default `/model opus` + `/effort` per gear | owner: `operator[business]` | proof: weekly model-mix census from transcripts.
- opened 2026-08-21 (m5) | **auto-loaded doctrine has no size budget** (148 KB local / 155 KB origin/main, growing ~7 KB/week) | arming step: pointer-format restore of superscar W95-W119 + CI cap lint with guilt+innocence tests | owner: session | proof: `wc -c` of the auto-loaded set ≤ 100 KB on main.

## 11. §Solo-operatore

- L10 model mix (Fable 56% of interactive turns vs §5 Opus-5 default) — business decision, Legge 5.
- agy re-login, Qwen credential, Codex O1 window (22/8 08:30) — credentials only the owner holds.
- Org-level CodeQL default setup toggle — GitHub GUI.
- Whether the WR2 pipeline (now stopped) is retired or re-designed with a real publisher — business.

## 12. Checklist pre-arming for any NEW automation or gate (machine-checkable)

A lint reads the PR and fails unless the new plist/workflow/hook/required-check declares: `model` (or `none`),
`interval`, `consumer` (who reads the output), `cost_per_run` (runner-min or tokens, measured on one real run),
`skip_predicate` (when it may not run), `sunset` (the metric that would retire it). The organism already has the
shape (`automation_catalog.json` has `produces`/`consumes`, `change_map.py` has domains) — what is missing is the
field and the lint, not the idea.

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
| C4 | `codeql-analysis.yml` is absent → can't be the cure; "0 value" unproven without query-suite comparison | **ACCEPTED, then closed with data** | source = default setup (`dynamic/github-code-scanning/codeql`); custom = `security-extended,security-and-quality` ⊃ default suite → default is redundant (§2) |
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
| C4 | "confirmed": `codeql-analysis.yml` active + absent → delete it, cleanest win | **REFUTED on attribution** (W65: the refuter also hallucinates) | that workflow's last run is 2026-02-14; the live duplicate is `dynamic/github-code-scanning/codeql` (default setup, `default` suite ⊂ custom `security-extended`); cure = disable default setup at org level |
| C9 | orphan tree is 310 files, not 276 | **REFUTED** | `git ls-tree -r origin/main apps/backend-rag/tests \| grep -c test_*.py` = 276 |
| C8 | only the static system prompt is cacheable; if it is ~2K of 16K the gain caps near today's 12% | **ACCEPTED as probe-first** | L8 step 0 = log static vs volatile token split per call for 24 h before building |
| C1 | agreement with caveat: part of post-PR output is doctrine-mandated queue-watch | **ACCEPTED** | and now measured: babysitting is 4% of post-PR output; reasoning is the mass |
| B | risks: (1) floor/hot-zone drift under-gears a migration/workflow → weekly diff of floor-1 paths vs `hotzone_changed_files.sh` changelog; (2) diff-scoped secrets scanning 0 files and passing green (the GLM-shim class) → echo scanned-file count, fail on 0, nightly full scan alerts within 24 h; (3) cheap PR run → 7-day rolling queue failure rate, auto-rollback at 2× baseline | **ACCEPTED as tripwires** | folded into L3/L4/L6 |
| D | missing class: merge-queue re-entry amplification (`min_entries_to_merge: 1` + every main push evicts) — probe runs ÷ merged PRs | **CONFIRMED by measurement, large** | 388 runs / 258 merged PRs since 2026-08-14 = **1.5** (§2); L1's proof metric now uses this ratio |

**Council summary**: 2 of 4 planned seats alive (degraded, declared). 19 objections; 16 accepted (6 of them changed
a lever's shape: C1→L0/§3, C4→L2 source, C5→L6 ceiling, C6→L7 target, C7→L10, D→L1 metric + L12), 2 refuted with
on-disk evidence (Kimi C4 attribution, Kimi C9 count), 1 confirmed by a new measurement (Codex D, 32% setup).
Nothing in either review touches the invariants; no seat proposed disabling a security control.
