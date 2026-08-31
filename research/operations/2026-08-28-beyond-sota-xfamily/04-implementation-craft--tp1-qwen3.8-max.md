---
panel: beyond-sota-xfamily
lane: 04-implementation-craft
seat: tp1-qwen3.8-max
model: "qwen3.8-max · enable_thinking · TP1 API, no tools, ground pack"
started: 2026-08-28T16:47:58Z
finished: 2026-08-28T16:58:02Z
duration_s: 604
exit: 0
words: 5223
prompt_sha256_16: c6ff42fca45e2d22
prompt_chars: 136688
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 4/13 — Implementation craft (BUILD)
model: Qwen3.8 Max (pinned lane)
sources: 18
repo_files_verified: 13
---

**Evidence base (access note).** This lane ran with NO file, shell or web tools. Every repository claim below is grounded in the redacted GROUND PACK appended to the lane prompt (13 files; `scripts/agent_start.py`, `MODEL_ROSTER.md`, `.claude/skills/modus/SKILL.md` and `CLAUDE.md` were truncated at ~12,000 chars each — claims beyond the visible range are marked **ASSUMED**). All four requested MEM bodies were **NOT FOUND in snapshot** — `MEM:` references are unavailable to this lane. All MEASURE items are **UNMEASURED** with the exact command stated. External sources are cited from model knowledge (no live fetch possible in this lane); uncertain URLs are marked `(unverified)`. Intended output path, had writes been available: `research/operations/2026-08-28-beyond-sota-implementation-craft.md`. The post-write `ls -la` / `wc -w` probe could not be run; this message is the deliverable.

## 0. TL;DR

**Position:** the BUILD isolation/coordination fabric (worktree broker, Redis leases, fail-closed fleet placement) is **AHEAD** of every surveyed system; BUILD *economics and outcome measurement* are **BEHIND** — the organism measures what it *dispatched* (seat-mix) but not what it *shipped*.
**Biggest gap:** contracts live as prose, not armed checks — the ~400-line PR contract, the claim-commit rule and lease acquisition have no enforcement point and no standing metric (fix-of-fix commits already measured at 27/200 = 13.5% of main landings, `CLAUDE.md` §1 rule 8).
**Top-3 moves:**
1. **Ship-time contract gate**: `lane_ship.sh` refuses >400-net-line PRs without a declared `oversize:` reason (the one chokepoint every lane already traverses).
2. **BUILD outcome ledger**: `build_outcome_report.py` computing PR size/rework/cycle metrics daily — Law 7 numbers for everything else.
3. **Close the two declared holes**: PreToolUse lease auto-acquire (coverage manual→~100%) + atomic `fleet_dispatch.py place` via the lease registry (closes the residual race the runbook itself declares).

## 1. How Nuzantara does it today

### 1.1 The isolation fabric (worktree broker)
`scripts/agent_start.py` (header: "SOTA L1 2026-05-24 — Agent Worktree Broker") gives every agent session a dedicated git worktree under `<REPO_ROOT>/.worktrees/<LANE>-<TASK_ID>/`, closing the 2026-04-29 sibling-collision incidents (#1+#2: untracked-file loss when a sibling switches branches) and 17 stash orphans (2026-05-23). The invariant was ratified 4/4 by a 4-LLM panel: `∀ w₁,w₂ : session(w₁) ∧ session(w₂) ⇒ working_tree(w₁) ∩ working_tree(w₂) = ∅`. Mechanics verified in pack:

- Branch namespace `agent/<hostname>/<lane>/<task-id>`; metadata in `.agent-task.json` (task_id/lane/branch/host/created_at/ttl_minutes/pid/base_branch/worktree_path); env-safe symlinks for `apps/backend-rag/.venv`, `.env`, `node_modules/` pointing at main checkout (`docs/runbooks/agent-worktree-broker.md`).
- Lifecycle: `--list` (with `ORPHAN` flag at age >2× TTL), `--cleanup` (WIP-safe + skip-recent W62: filesystem activity <10 min = live session), `--release` (branch deleted only if merged), kill switch `AGENT_BROKER_ENABLED=false` (lesson W33), log `~/logs/agent-broker.log`.
- Root derivation was hardened after W105/W63: `_derive_repo_root()` asks `git rev-parse --git-common-dir` (answers "main checkout" even from inside a worktree), signature-checks every candidate (`scripts/agent_start.py` presence), normalises worktree paths to their owning main checkout, and **raises** when nothing carries the signature — the docstring names the failure it prevents: "a guessed root reports an EMPTY worktree inventory, which reads as 'nothing to clean up'" (W84 calm-liar).
- Hygiene is 3-level: explicit `--release` → daily cron reaper (`com.nuzantara.agent-worktree-cleanup.daily`, 08:15 WITA) → CI gate `tests/integration/test_no_stale_worktrees.py` in `broker-hygiene.yml` (fails on any worktree >24h old).
- Known lanes: `wr2, wr3, infra, docs, db, cicatrix-fix, mouth, intel, cell, organism, mata-garuda, backend-rag, frontend, ops` (`docs/runbooks/agent-worktree-broker.md`).

### 1.2 Enforcement at the tool-call layer
`infra/claude-hooks/README.md` documents PreToolUse hooks (executable copies live in `~/.claude/hooks/`, repo copies are audit trail — W50/W51/W52 drift mitigation): `worktree_isolation.py` blocks mutating git ops (`checkout|switch|stash|reset|merge|rebase|pull`, `commit -a/-am/--all`, `add -A/...`) targeted at the main checkout; `worktree_file_write_check.py` blocks Edit/Write into the main checkout outside registered worktrees. **Honest state:** on Pro the enforcement kill switch is `false` (single-operator interactive); on M5 it is armed. So on the primary interactive machine isolation is doctrine + main-checkout-read-only convention, on M5 it is mechanically enforced.

### 1.3 Concurrent-write coordination (leases)
`docs/runbooks/redis-lease-registry.md`: `scripts/agent_lease.py` + pre-commit `lease-check` close family W40/W50/W51/W52. Keys `agent_lock:<resource>`, atomic `SET NX EX`, Lua-scripted release/heartbeat, audit trail `~/.agent/leases.jsonl`. Hot-zone regexes cover launchagent scripts, `migrations_v2/*.sql`, escalations jsonl, sentinel/dlq/pg-bridge scripts, all `.github/workflows/`, and `auth|billing|pricing` services. Doctrine: Redis outage → commits pass with WARN ("MAI block commit per Redis outage"); kill switch `AGENT_LEASE_ENFORCEMENT=false`. Acquisition is **manual** (`acquire` → edit → `release`); the runbook's own Future Work lists auto-acquire-on-Edit as deferred.

### 1.4 Fleet placement (where a lane may build)
`docs/runbooks/fleet-lane-dispatch.md`: `scripts/fleet_dispatch.py` answers *where can a lane go* and *may it go there*. `capacity` reports per-node verdicts (READY <0.60 load/core, ≥2048 MB, no suite lock; BUSY; SATURATED; DARK; unreadable ⇒ SATURATED; exit 4 = BLIND when no node answered). `place --files ...` records declared scope in a sidecar (`~/.organism/fleet_dispatch/lanes/<worktree>.scope`), and treats collision as **refusal, not warning** — grounded in the Google parallelism result the repo cites (arXiv 2512.08296): coders on the same artifact degrade ~70%. `empty` scope is a completed measurement (advisory only); `opaque`/`partial`/unreachable-node are refusals. The runbook **declares a known residual race**: check and create are not atomic across machines. Lanes placed via `place` get the broker's pre-push hook; bare `git worktree add` gets none — "the `--no-verify` the fleet forbids, with extra steps."

### 1.5 Implementer routing
`MODEL_ROSTER.md` (Zero ruling 2026-08-14): implementer routing is a **per-task choice across the full cross-family roster**, not Sonnet-by-law. Verified rows: `claude-opus-5` = conductor + final gate; **`claude-sonnet-5` = implementer workhorse / BUILD-stage default** ("Opus 5 designs, Sonnet builds, Opus 5 verifies"; note the ~+30% tokenizer cost warning); `claude-haiku-4-5` = grunt door with 7 pinned `.claude/agents/` defs (`ledger-writer, lint-fixer, i18n-sync, fixture-gen, log-triage, catalog-meta, docs-sync`); Codex via `codex exec --sandbox` with versioned models `-m gpt-5.6-sol/terra/luna` live through `seat_build.sh` (PR #5044), bare slugs dead since 2026-07-21; Fable 5 has **no automated role** (RULED 2026-08-20). Kimi/GLM/Antigravity rows exist per `CLAUDE.md` §5/modus headers but sit beyond the pack's truncation (**ASSUMED** in detail). `docs/factory/SEAT-MIX.md` gives the telemetry organ (`scripts/seat_mix_report.py`): day-0 baseline (Pro, 48h): 148 Agent dispatches — sonnet 85.8%, inherit 12.2%, haiku 1.4%, opus 0.7%; 112 non-Anthropic seat calls (0.76/dispatch); `workflow_runs: 1`; 35 unmapped sessions. The earlier one-off fleet-wide parse: 882 dispatches/48h, ~512 cross-family calls, Workflow tool at 0 genuine runs, **only 5/20 evidence packs carried a cross-family reviewer**.

### 1.6 Build disciplines and the PR contract
- `.claude/skills/karpathy-discipline/SKILL.md`: Think Before Coding / Simplicity First / Surgical Changes / Goal-Driven Execution; every changed line must trace to the request.
- `.claude/skills/reuse-first/SKILL.md`: 7-step search-before-write with a load-bearing license gate (MIT/Apache/BSD vendor-with-attribution; GPL/AGPL = study-pattern-rewrite; no-LICENSE = no-copy) and provenance tracking; founding measurement: ~70% of a document-intake system already existed elsewhere.
- `CLAUDE.md` §1 Agent PR Contract: one PR one concern (~400 net lines), arm-means-freeze, never-rerun-red-without-cause (W111), no commit while push in flight, serialize Dependabot lockfiles, dedicated worktree + claim commit in `agent/<host>/<lane>/...`, `mq handoff` after merge, and **rule 8: three rounds then suspend** (fix-of-fix depth cap 1).
- Lane report contract (2026-08-21, `docs/runbooks/agent-worktree-broker.md`): every lane ends with a report (PR number, worktree path, checks with pass/fail lines, what's undone); shipping goes through `scripts/lane_ship.sh`, which refuses dirty/main-checkout worktrees, captures the push exit code, arms auto-merge, and **GraphQL-verifies the arm before printing `LANE_SHIP_OK`** — "the orchestrator reads the worktree/PR state as truth, the report as a lead."
- `.claude/skills/modus/SKILL.md` (visible portion): gear triage with anti-sperpero rules — fan-out only ≥3 independent items, reads fan out / writes funnel in, "prefer one agent + more budget over N agents (coding barely parallelizes — Anthropic/Cognition)", gear **floor** (`harness-floor.yml`) and **ceiling** (`compute_ceiling()` in `scripts/evidence_pack_lint.py`, PR #4474: a ≤2-file/≤60-net-line diff outside hot zones is Gear-1-shaped by construction). The BUILD-stage row body itself is past the pack truncation (**ASSUMED** beyond the stage-table header).

### 1.7 Pre-commit gates that shape code
`.pre-commit-config.yaml`: ruff lint+format **scoped to `^apps/backend-rag/`**, eslint **scoped to `^apps/mouth/`**, mypy `--strict` on exactly one file (`backend/app/dependencies.py`, the Rogue-AI-Import-Removal SPOF guard), no-print/no-console/TODO checks, root-guard, organs-registry checksum HALT, anti-rogue-AI gates (`check_import_chain.sh`, `check_protected_files.sh`), and three shape-based secret guards born from real leaks: Telegram bot token (2026-08-13), any-role Postgres DSN password (2026-08-21), Google OAuth triples (2026-08-21).

**Unverified in this lane** (no tools): `ls infra/army/*` (H24 chore/jules/spark lanes — **ASSUMED** from brief), `.github/workflows` lint/autofix listing, husky pre-push internals beyond runbook description.

## 2. Scars & ledger evidence in this area

Grounded in pack text only; superscar file, PENDING-ARMS and AMENDMENTS were not excerpted, so family-level claims are limited to what the pack's files themselves state.

| Evidence | What bit | Recurrence/size |
|---|---|---|
| `scripts/agent_start.py` header | Sibling sessions sharing a working tree: untracked-file loss when sibling switches branches (2026-04-29 #1+#2); 17 stash orphans | Systemic → broker born (superscar #5 sibling-race) |
| W40 (`redis-lease-registry.md`) | Two sessions both picked migration number 194; deploy would hard-fail at `_assert_unique_migration_numbers` | Race class → lease registry |
| W50/W51/W52 (same runbook) | Stale HOME-forks executed for 4+ days (dlq_autopilot) and 24 days (sentinel: **60% more escalations, 75% slower for 3+ weeks**); survey found **84/167 plists (50%)** on HOME-forks | Superscar #1 HOME-fork |
| W62 | Cron reaper deleted/reaped live worktrees → skip-recent (10-min activity) antibody | Guard-vs-live-session |
| W63 + W105 | Broker run from a worktree nested `.worktrees` inside a worktree; `/tmp` copy fell back to `/` and printed an empty inventory "as cleanliness" (W84 calm liar) | Recurred across machines (m5, 2026-08-08) |
| `agent_start.py` comment | `node_modules`/`.husky/_` broker symlinks tripped the WIP guard: **3 worktrees sat 5–14h past a 60-min TTL**, silently WARN-skipped every cron run | Empirically reproduced before fix |
| Broker runbook §7 | Direct `git worktree add` bypasses symlinks → pre-push dies with **zero output**; observed **twice in one day** (2026-07-12) | Recurred same day |
| Lane report contract origin | Two implementer lanes finished with only an idle notification (no PR, no path, no test result); a third hard-blocked by `orchestrate_gate.py` as subagent | 2026-08-21, same day fix |
| `CLAUDE.md` rule 8 | PR #4547 (1-file hook fix): **14 commits, 11 adversarial rounds, ~6h**; the 44h session burned **3.9M output tokens**; **27 of 200 commits (13.5%)** landing 2026-08-20..22 existed only to correct a previous claim | The rework tax, measured |
| `SEAT-MIX.md` | The seat-mix PR's own mandatory Kimi K3 refuter caught a secret/PII leak path in free-captured flags + a systematic over-counting bug pre-merge; but only 5/20 evidence packs had any cross-family reviewer | Refuter works; coverage is 25% |
| Pre-commit comments | Live Telegram token reached the public default branch (unrevocable); a prod Postgres password hit origin/main **twice** then copy-pasted into **24** more places (live 2026-05-23..08-21); one OAuth triple sat green for months in **9** scripts | Guards born post-leak |

**UNMEASURED** (no shell in this lane) — exact commands:
- PR size distribution vs the 400-line contract: `gh pr list --state merged --limit 100 --json number,additions,deletions,changedFiles` → median/p90 of `additions+deletions`.
- 14-day main commit volume + fix share: `git -C /Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828 log --since=14.days --oneline | wc -l` and `... log --since=14.days --pretty=%s | grep -c '^fix'` divided by total. Heuristic: subject begins with literal `fix` (captures `fix:`/`fix(scope):`).
- Live worktrees: `git -C /Users/nuzantara/nuzantara/.worktrees/research-beyond-sota-0828 worktree list | wc -l`.
- Scar blocks W59/W62/W63/W79/W80/W88: `grep -n '^## ' .claude/rules/cicatrix-scars.md .claude/rules/cicatrix-scars-archive.md | grep -E 'W59|W62|W63|W79|W80|W88'` then `sed -n` each block. (W79 is referenced only by the lane brief's hook note; its scar text is unverified here.)
- Superscar families #1/#5 full text: `grep -n '^## ' .claude/rules/cicatrix-superscar.md`.
- MEM grep: `grep -il "antigravity\|implementer\|worktree" /Users/nuzantara/.claude/projects/-Users-nuzantara-nuzantara/memory/*.md | head -20`. The four named MEM lessons (`lesson_headless_cli_implementers_die_when_they_pause_2026_08_09`, `decision_workhorse_first_routing_doctrine_2026_08_15`, `discovery_a_mouth_worktree_can_fail_60_tests_that_ci_passes_2026_08_28`, `discovery_the_backend_rag_venv_is_live_infrastructure_not_a_dev_sandbox_2026_08_26`) are **NOT FOUND in snapshot** — titles only; contents unavailable.

## 3. World SOTA survey

No web access in this lane; sources are from model knowledge as of 2026-08-28.

| # | System/practice | Source | Mechanism that makes it best-in-class | Measured effect (published) | Transferability here |
|---|---|---|---|---|---|
| 1 | Google small-CL / eng practices | google.github.io/eng-practices | Tiny, self-contained changes make review fast and correct; size discipline is *prose enforced by reviewers* | Review latency scales with CL size (internal, qualitative) | Direct — organism's 400-line contract is the same idea, currently unenforced |
| 2 | Trunk-based development | trunkbaseddevelopment.com | Branches <1–2 days, flags decouple deploy from release | Industry baseline for elite DORA clusters | High — matches per-lane `agent/...` branches + session-owned merge |
| 3 | Anthropic "Building effective agents" (2024-12) | anthropic.com/engineering/building-effective-agents | Simplest composable pattern wins; orchestrator-worker; don't framework | Qualitative; adopted industry-wide | Already reflected in modus anti-sperpero rules |
| 4 | Anthropic Claude Code best practices (2025) | anthropic.com/engineering/claude-code-best-practices | CLAUDE.md as context, explore→plan→code→commit, TDD, git-worktree parallelism for independent tasks | Qualitative | Organism already exceeds (broker + hooks); TDD enforcement gap matches mine |
| 5 | Anthropic context engineering (2025) | anthropic.com/engineering/effective-context-engineering-for-ai-agents | Context as the scarce resource; compaction, subagent context isolation | Qualitative | Lane 2 territory; BUILD implication: claim-commit + scope sidecars are context anchors |
| 6 | Cognition "Don't Build Multi-Agents" (2025-06) | cognition.ai/blog/dont-build-multi-agents | Actions carry implicit decisions; parallel writers conflict; one action-thread per decision domain | Qualitative | Repo already ratified the sibling result (arXiv 2512.08296); residual race in `place` is the remaining exposure |
| 7 | SWE-agent (arXiv 2405.15793, 2024) | arxiv.org/abs/2405.15793 | Agent-computer interface design > raw model: guarded editor, search tools, lint feedback in-loop | +14pp over baseline scaffolds on SWE-bench-lite (paper) | High — the lease/pre-commit feedback at commit time is exactly ACI thinking |
| 8 | Agentless (arXiv 2407.01489, 2024) | arxiv.org/abs/2407.01489 | Localize→repair→validate pipeline beats open-ended agent loops at ~1/10 cost | ~32% SWE-bench at ~$0.50/issue (paper) | Supports gear-ceiling: most diffs are Gear-1-shaped; don't run loops on them |
| 9 | SWE-bench Verified leaderboard | swebench.com | Standing benchmark; top scaffolds >70% solve (late-2025) | Leaderboard numbers | Only as a regression-shape reference; organism's tasks are ops-shaped, not issue-shaped |
| 10 | METR RCT on AI dev productivity (2025-07) | metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study | Randomized controlled trial on mature, complex codebases | Devs believed +24% faster; **measured −19% slower** | Central warning: BUILD speed claims need measured cycle-time, hence R2 |
| 11 | DORA State of DevOps 2024/25 (AI chapters) | dora.dev/research | Org-level AI adoption correlates with throughput/stability shifts | 2024: ~+25% AI adoption ↔ ~−7% throughput, ~−15% stability (reported) | Same moral at fleet scale; organism needs its own DORA-equivalent (R2) |
| 12 | OpenHands | github.com/All-Hands-AI/OpenHands | Event-stream architecture, sandboxed runtime, CodeAct action space | SWE-bench entries | Sandbox-per-task pattern = what broker gives locally |
| 13 | OpenAI Codex cloud agent (2025-05) | openai.com/index/introducing-codex | Isolation by construction: each task in a fresh cloud sandbox, parallel tasks | Qualitative | Contrast: free isolation but cloud/tenant-bound; organism is local-first by Law |
| 14 | Google Jules async agent | developers.googleblog.com/en/start-building-with-jules (unverified) | Async task queue over repo sandbox, PR-shaped output | Qualitative | Already integrated (`jules_dispatch.py` appears in seat-mix vocabulary) |
| 15 | GitHub Copilot coding agent (2025-05) | github.blog Copilot coding agent announcement (unverified) | Issue→agent→PR in Actions sandbox; merge stays human-gated | Qualitative | Weaker than organism's session-owns-merge model |
| 16 | Hypothesis property-based testing | hypothesis.readthedocs.io | Spec-shaped tests find edge cases example tests miss | Widely evidenced in OSS | Cheap add for hot-zone services; complements red-first (R6) |
| 17 | Meta Sapling / stacked diffs | sapling-scm.com/docs (unverified) | Stacked-commit workflow for many small reviewable units | Internal at Meta | Conceptually matches one-PR-one-concern; tooling not needed on GitHub flow |
| 18 | ast-grep / OpenRewrite codemods | ast-grep.github.io | Structural, deterministic mass edits with zero LLM tokens | Industry codemod practice | Direct: grunt-door codemod lane (R7) |

**The five that matter most here.** (1) **arXiv 2512.08296** (via `fleet-lane-dispatch.md`): the repo already converted the "same-artifact parallelism is negative" result into refusal semantics — ahead of every public system I surveyed, which either document the problem (Cognition) or sidestep it with single-tenant cloud sandboxes (Codex, Devin-class). (2) **METR RCT**: the only rigorous causal evidence that felt speed ≠ real speed on mature codebases; it indicts any BUILD practice without measured cycle-time — the organism's exact gap. (3) **SWE-agent**: validates the organism's deepest instinct — that the *interface* around the implementer (guarded ops, commit-time feedback, leases) is the lever, not the model. (4) **Agentless**: pipeline-over-loop economics justify the gear ceiling and cheap-seat routing. (5) **DORA 2024**: adoption without stability instrumentation regresses delivery; seat-mix is adoption telemetry — the stability half is missing.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Per-session workspace isolation | **AHEAD** | Formal 4-LLM-ratified invariant, brokered lifecycle (TTL/WIP/skip-recent/orphan/CI-24h-cap), branch namespace, metadata file — `scripts/agent_start.py`, broker runbook. Cloud agents get isolation free but container-bound and single-machine; nothing surveyed brokers local multi-machine worktrees with this lifecycle |
| Concurrent-write coordination | **AHEAD (with declared hole)** | Redis leases + hot-zone regex + audit jsonl + fail-open doctrine (redis runbook); collision-as-refusal in `place` (fleet runbook). Residual race explicitly declared; acquisition manual |
| Fleet placement/load routing | **AHEAD** | Fail-closed capacity verdicts, declared-scope sidecars, exit-4 BLIND, locale/rename/normalization gotchas paid for — no surveyed local-first equivalent exists |
| Implementer routing economics | **AT** | Full task-shaped roster + doors (`MODEL_ROSTER.md`), telemetry exists (`SEAT-MIX.md`); but haiku share 1.4%, Workflow runs 1/48h, 35 unmapped sessions — the cheap/parallel primitives are provisioned, not used |
| PR size/contract discipline | **AT doctrine / BEHIND enforcement** | Contract mirrors Google small-CL and goes beyond (three-rounds-suspend, claim commit, arm-means-freeze); but no enforcement point and **no measurement** (size distribution UNMEASURED); 13.5% correction-commit share shows the cost of unenforced claims |
| TDD / reuse-first / karpathy discipline | **AT** | Codified, vendored skills with real provenance (karpathy, reuse-first); red-first is mandated for product work (ASSEMBLY-LINE, per CLAUDE.md §2) but no machine-checked red-first artifact for general BUILD visible in pack |
| Commit-time code-shaping gates | **AHEAD on secrets/safety, BEHIND on coverage** | Shape-based secret guards born from real leaks, anti-rogue-AI import-chain gate, mypy SPOF guard; but ruff covers only `apps/backend-rag`, eslint only `apps/mouth`, mypy one file |
| BUILD outcome measurement | **BEHIND** | seat-mix measures *inputs* (dispatches, seat calls); nothing in pack measures PR size, rework ratio, first-pass-green, or cycle time. Law 7 (no metric = not an improvement) is cited in doctrine and absent in BUILD practice |
| Enforcement-hook arming | **BEHIND doctrine** | `AGENT_WORKTREE_ENFORCEMENT=false` on Pro (hooks README) — on the primary interactive machine the isolation law is convention, while W79-class main-checkout protection is the brief's stated intent (scar text itself UNMEASURED) |

## 5. Beyond-SOTA recommendations

Each satisfies §2.D: novelty/composition, an organism asymmetry, a before/after number path, hard-rule compliance (OAuth/CLI-only, no paid API, PII boundary respected, Fable untouched). Ranked by (impact × confidence)/cost. Scar-family numbers beyond #1/#2/#5/#7 are not grounded in the pack and are marked as such.

### R1 — Ship-time PR contract gate (size · namespace · claim commit)
- **What:** `scripts/lane_ship.sh` refuses to arm when net diff (`additions+deletions`) >400 unless PR body carries `oversize: <reason>`; verifies branch matches `agent/<host>/<lane>/...` and a claim commit exists. Codifies contract rules 1+6 at the one chokepoint every shipping lane already traverses.
- **Why it beats SOTA:** Google's small-CL rule is reviewer-enforced prose; Copilot/Codex/Jules have no size gate at all. This composes a size lint with the arm-then-GraphQL-verify pattern the organism already proved in `lane_ship.sh`.
- **Cost:** ~3–4 h, flat-sub tokens negligible. **Gear 1.**
- **Risk:** nuisance blocks on legit large migrations → explicit override; if override becomes routine the gate is family-#2 (exists ≠ armed) again — measure override rate.
- **Metric:** before: UNMEASURED (run the §2 `gh` command for baseline); after: p90 net lines ≤400, override rate <10%. Method: `lane_ship` emits `LANE_SHIP_FAIL reason=oversize`; R2 aggregates.
- **Kill:** override rate >15% for 2 consecutive weeks, or evidence of artificial PR-splitting (dodge detection: same-lane same-day PR pairs touching adjacent files).
- **First PR:** `scripts/lane_ship.sh` + `scripts/tests/test_lane_ship.sh` additions, ≤400 net lines.

### R2 — BUILD outcome ledger (`build_outcome_report.py`)
- **What:** daily report in the seat-mix family: pulls last N merged PRs via `gh` API — net lines, changedFiles, commits/PR, time-to-merge, fix-share of commit subjects — emits JSON+MD to `~/logs/build-outcome/`, reusing seat-mix's sanitizer + `assert_all_strings_safe` PII pattern. Descriptive first (no thresholds), same ruling seat-mix got.
- **Why it beats SOTA:** DORA is survey-scale and org-level; no surveyed system continuously computes per-PR contract conformance for a solo multi-agent organism. It converts Law 7 from slogan to instrument and supplies the before/after for R1/R5/R6.
- **Cost:** ~6 h. **Gear 2.**
- **Risk:** W84 calm-liar if the gh join silently drops PRs — emit explicit `unmapped`/`skipped` counts exactly as seat-mix does; family #2 if produced-but-unread — wire a cron line into the existing daily digest.
- **Metric:** baseline (today UNMEASURED) → weekly median/p90 net lines, fix-share, commits/PR. Target direction set after baseline; first win = number exists.
- **Kill:** gh API breakage >7 days unfixed, or zero downstream references in 60 days.
- **First PR:** `scripts/build_outcome_report.py` + `scripts/tests/test_build_outcome_report.py`.

### R3 — Lease auto-acquire on Edit/Write (PreToolUse hook)
- **What:** close the redis runbook's own deferred item: PreToolUse hook on hot-zone regex auto-acquires with `task_id` from the worktree's `.agent-task.json`, PostToolUse heartbeat, release at `lane_ship`/Stop. Reference copy in `infra/claude-hooks/` with drift-check discipline (W50/51/52). Hook errors fail OPEN with loud logging (consistent with commit doctrine), Redis-down fails open per standing doctrine.
- **Why it beats SOTA:** surveyed systems isolate per-task (containers) or don't coordinate files at all; in-tool-call file reservation on a shared local fleet is a composition none has.
- **Cost:** ~4–6 h. **Gear 2.**
- **Risk:** stale lease after crash blocks a lane (bounded by TTL 300s + documented emergency DEL); family #5 if two sessions race between hook and write — window strictly smaller than today's fully-manual gap.
- **Metric:** before: manual-only (lease-event count today UNMEASURED — `wc -l ~/.agent/leases.jsonl`); after: ≥95% of hot-zone commits preceded by a matching acquire event (pre-commit cross-check).
- **Kill:** false-blocks >1/week after TTL tuning, or +1s p95 commit latency.
- **First PR:** `infra/claude-hooks/lease_autoacquire.py` + regex/corpus tests + runbook delta.

### R4 — Atomic fleet placement via the lease registry
- **What:** `place` acquires short-TTL fleet leases on every declared `--files` path before worktree creation, converts them to the lane's task lease after sidecar write, rolls back on any failure — closing the residual race the runbook declares rather than hides.
- **Why it beats SOTA:** arXiv 2512.08296 measures the ~70% same-artifact degradation but offers no coordination primitive; cloud agents dodge it by single-tenancy. Cross-machine reservation on a flat-subscription local fleet is unclaimed territory.
- **Cost:** ~1–2 days. **Gear 2.**
- **Risk:** Redis outage behavior touches a Zero-dictated doctrine ("MAI block commit per Redis outage") on a new surface → see Needs-ruling; lease TTL expiry mid-lane → sidecar-owner heartbeat.
- **Metric:** before: unbounded race window (collisions uncountable today); after: 0 post-placement collisions on declared scope (leases.jsonl `release-denied` + dispatch logs), `place` p95 <5s, false-refusal <5%.
- **Kill:** false-refusal >5% or p95 >10s sustained 2 weeks.
- **First PR:** `scripts/fleet_dispatch.py` + `scripts/tests/test_fleet_dispatch.py`.

### R5 — Gear-model routing lint (cheap-seat ceiling)
- **What:** extend `scripts/evidence_pack_lint.py`: a diff already declared Gear-1-shaped by `compute_ceiling()` (≤2 files/≤60 net lines, non-hot-zone) implemented via opus/sonnet dispatches emits NOTICE unless `gear_override:`; grunt-eligible subagent types dispatched above haiku are counted. Seat-mix stays descriptive (its ruling stands); the lint enforces gear *shape*, which is already law.
- **Why it beats SOTA:** no surveyed system lints model choice against diff shape; exploits the CI-recomputed gear-floor asymmetry nobody else has.
- **Cost:** ~4 h. **Gear 2.**
- **Risk:** under-gearing — modus names under-gearing the systematic failure mode; ceiling fires only where ceiling law already applies; watch for reward-hacking (lane 5's territory) via fabricated overrides.
- **Metric:** `cheap_seat_share_pct` 1.4% → ≥15% in 60 days with rework ratio (R2) flat (±2pp).
- **Kill:** rework ratio +2pp, or override rate >20%.
- **First PR:** `scripts/evidence_pack_lint.py` + tests.

### R6 — Red-first evidence requirement for logic diffs
- **What:** evidence-pack lint requires a captured failing-test run (test id + exit-code artifact) predating the fix commit for PRs touching `apps/**` logic; Gear-1 declared exemption. Generalizes ASSEMBLY-LINE's journey-tests-red-first beyond product work.
- **Why it beats SOTA:** Anthropic's TDD guidance is advice; SWE-bench scaffolds validate post-hoc. Machine-verified red-first as a standing CI-recomputed requirement is not something any surveyed system ships.
- **Cost:** ~1 day. **Gear 2.**
- **Risk:** forged red runs (reward hacking — flag for lane 5 mutation-style audits); overhead on trivial fixes (exemption).
- **Metric:** logic PRs carrying red-run artifact: baseline ASSUMED ~0% (no such requirement visible in pack) → 100%; later: regression-escape rate (UNMEASURED today).
- **Kill:** >2 detected forgeries, or Gear-2 cycle time +25%.
- **First PR:** red-first rule in `scripts/evidence_pack_lint.py` + tests.

### R7 — Codemod grunt lane (zero-LLM mechanical diffs)
- **What:** `.claude/agents/codemod-runner.md` on the haiku grunt door + runbook: renames/import moves/lint migrations run as ast-grep/ruff `--fix` codemods inside a brokered worktree with the standard PR contract; lease required when touching hot zones.
- **Why it beats SOTA:** OpenRewrite/ast-grep are human-driven; composing codemods with grunt doors + broker + `lane_ship` yields an autonomous mechanical lane spending zero implementation tokens.
- **Cost:** ~4 h. **Gear 1/2.**
- **Risk:** over-broad rewrites (blast radius) — constrain rules per-PR; sibling-race (#5) if run leaseless on hot zones — lease is a precondition.
- **Metric:** mechanical-diff share via codemod lane 0 → ≥10% of mechanical diffs in 90 days; sonnet tokens saved via the existing `seat_usage_collector` join.
- **Kill:** codemod PRs failing first-pass >30%.
- **First PR:** `.claude/agents/codemod-runner.md` + `docs/runbooks/codemod-lane.md`.

## 6. 90-day roadmap + first PRs

**Wave 1 (days 1–30) — measure and gate the contract.** Run the §2 baseline commands (PR size, fix-share, worktree count); ship R2 (ledger) and R1 (ship-time gate); draft R3 hook. Exit: every number in §2 UNMEASURED exists; no lane can arm an oversize PR silently.
**Wave 2 (days 31–60) — coordination atomicity.** Ship R3 (auto-lease) then R4 (atomic place); ship R5 (routing lint). Exit: lease coverage ≥95% of hot-zone commits; 0 placement collisions on declared scope; cheap-seat share moving.
**Wave 3 (days 61–90) — quality and economics.** Ship R6 (red-first) and R7 (codemod lane); first metric review against Wave-1 baseline; retro written into AMENDMENTS (the loop's own misfire ledger) so the meta-pattern gets its scar entry if any gate misfires.

| First PR | Title | Files | Net | Gear | Acceptance test |
|---|---|---|---|---|---|
| 1 | `lane_ship: enforce PR size + namespace + claim-commit contract` | `scripts/lane_ship.sh`, `scripts/tests/test_lane_ship.sh` | ≤250 | 1 | fixture oversize PR refused with `LANE_SHIP_FAIL reason=oversize`; `oversize:` body passes |
| 2 | `build_outcome_report: daily BUILD outcome ledger` | `scripts/build_outcome_report.py`, `scripts/tests/test_build_outcome_report.py` | ≤400 | 2 | emits median/p90 net lines + fix-share over fixture PRs; PII fixture never leaks (seat-mix pattern) |
| 3 | `lease_autoacquire: PreToolUse hot-zone lease hook` | `infra/claude-hooks/lease_autoacquire.py`, tests, runbook delta | ≤350 | 2 | hot-zone Edit auto-acquires (leases.jsonl event); kill switch + fail-open honored |
| 4 | `fleet_dispatch: atomic place via lease registry` | `scripts/fleet_dispatch.py`, `scripts/tests/test_fleet_dispatch.py` | ≤400 | 2 | concurrent-place fixture yields exactly one success + rollback; BLIND/exit-4 semantics unchanged |
| 5 | `evidence_pack_lint: cheap-seat ceiling notice` | `scripts/evidence_pack_lint.py`, tests | ≤200 | 2 | Gear-1-shaped diff + opus dispatch ⇒ NOTICE; override converts to pass |
| 6 | `evidence_pack_lint: red-first artifact requirement` | `scripts/evidence_pack_lint.py`, tests | ≤300 | 2 | logic PR without red-run artifact fails; Gear-1 declaration passes |
| 7 | `codemod-runner: grunt-door codemod lane` | `.claude/agents/codemod-runner.md`, `docs/runbooks/codemod-lane.md` | ≤200 | 1 | agent def resolves project-level; runbook requires lease for hot zones |

## 7. Needs-ruling

1. **Fail-closed placement on Redis outage.** R4 makes `place` refuse when the lease registry is unreachable. This extends Zero-dictated doctrine ("MAI block commit per Redis outage" — commit surface) to the placement surface; I recommend fail-closed (unreadable ⇒ withhold work, per `fleet_dispatch`'s existing SATURATED-degradation philosophy), but the source doctrine is operator-dictated → needs-ruling.
2. **Re-arm worktree enforcement on Pro.** `AGENT_WORKTREE_ENFORCEMENT=false` on the primary interactive machine (`infra/claude-hooks/README.md`); BUILD isolation there is convention. Re-arming changes live behavior on Zero's interactive machine → needs-ruling (with the M5 experience as evidence it is livable).
3. **Publish BUILD outcome metrics in the public repo.** R2's forcing-function option (metrics in-tree, public repo as discipline) vs local-only is a business/public-exposure decision → needs-ruling. Default until ruled: local `~/logs/build-outcome/`, repo-internal weekly digest only.

*(No recommendation in this lane requires new credentials, consents, GUI or physical actions. On-machine dedup of `~/.claude/agents/` HOME copies remains a session-executable PENDING-ARMS item, not a ruling.)*

## 8. §Meta-pattern

**What repeats:** every recurring scar in this lane is the gap between a *declared* contract and an *armed* check. The lease exists — acquisition is manual. The 400-line contract exists — nothing enforces or measures it. Lanes must report — two still finished with idle notifications until the report contract was written. Agents are defined — "esiste ≠ armato" is literally cicatrix family #2. Isolation is law — the hook is disarmed on Pro. Guards exist — but only after the token, the DSN password and the OAuth triple had already lived on origin/main.

**The single defective belief generating them:** *"a rule written down is a rule followed"* — doctrine treated as a runtime control. The organism's own most reliable fixes are the negation of that belief, and they are already in the corpus as a reusable antibody pattern: `lane_ship` GraphQL-verifies the arm before printing OK; `fleet_dispatch` treats `empty` as a completed measurement and silence as DARK; `.claude/agents` pairs every whitelist with an explicit denylist ("declaration is not enforcement"). The craft upgrade is mechanical: **no contract enters doctrine without naming, in the same PR, the check that fires when it is broken** — and the check's output must be a number (Law 7), because the calm liar's favorite disguise is an empty inventory read as clean (W84).

## 9. Sources

No live web access in this lane; all external items from model knowledge, accessed 2026-08-28 unless marked.

1. Google Engineering Practices — developer guide (small CLs). https://google.github.io/eng-practices/review/developer/ — canonical statement of size discipline in review.
2. Trunk-based development. https://trunkbaseddevelopment.com/ — reference model for short-lived branches the organism already runs.
3. Anthropic, "Building effective agents" (2024-12). https://www.anthropic.com/engineering/building-effective-agents — simplest-pattern doctrine mirrored by modus anti-sperpero.
4. Anthropic, "Claude Code: best practices for agentic coding" (2025). https://www.anthropic.com/engineering/claude-code-best-practices — worktree-parallelism + TDD guidance; baseline the organism exceeds.
5. Anthropic, "Effective context engineering for AI agents" (2025). https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — context-scarcity framing for BUILD-stage anchors.
6. Cognition, "Don't Build Multi-Agents" (2025-06). https://cognition.ai/blog/dont-build-multi-agents — implicit-decisions conflict theory behind collision-as-refusal.
7. Yang et al., "SWE-agent" (2024-05). https://arxiv.org/abs/2405.15793 — ACI design beats raw model; validates commit-time feedback layers.
8. Xia et al., "Agentless" (2024-07). https://arxiv.org/abs/2407.01489 — pipeline-over-loop economics; grounds gear ceiling and cheap seats.
9. SWE-bench (leaderboard, Verified). https://www.swebench.com/ — standing scaffold benchmark (shape reference only).
10. METR, "Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity" (2025-07-10). https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/ — the RCT behind "measure cycle time, not felt speed".
11. DORA research program (2024/2025 AI findings). https://dora.dev/research/ — adoption-vs-stability instrumentation at org scale.
12. OpenHands. https://github.com/All-Hands-AI/OpenHands — sandbox-per-task agent runtime pattern.
13. OpenAI, "Introducing Codex" (2025-05). https://openai.com/index/introducing-codex/ — isolation-by-construction contrast to local-first broker.
14. Google, Jules coding agent docs (2025). https://developers.googleblog.com/en/start-building-with-jules/ (unverified) — async PR-shaped agent; already integrated via `jules_dispatch.py`.
15. GitHub, Copilot coding agent announcement (2025-05). https://github.blog/news-insights/product-news/github-copilot-meet-the-new-coding-agent/ (unverified) — human-gated merge model the organism deliberately supersedes.
16. Hypothesis documentation. https://hypothesis.readthedocs.io/ — property-based testing for hot-zone services.
17. Meta Sapling documentation (stacked commits). https://sapling-scm.com/docs/ (unverified) — many-small-units workflow precedent.
18. ast-grep. https://ast-grep.github.io/ — structural codemod engine for R7.

*(Repo-internal "source" of record for the parallelism taxonomy: arXiv 2512.08296 as cited by `docs/runbooks/fleet-lane-dispatch.md`; URL https://arxiv.org/abs/2512.08296 (unverified).)*

`status: complete` · `sections_done: 0-9` · Word-probe note: no shell access — `wc -w` could not be run; estimated ~4,900 words.