---
panel: beyond-sota-xfamily
lane: 09-multi-agent-orchestration-fleet-routing
seat: tp1-qwen3.8-max
model: "qwen3.8-max · enable_thinking · TP1 API, no tools, ground pack"
started: 2026-08-28T16:55:03Z
finished: 2026-08-28T17:05:14Z
duration_s: 611
exit: 0
words: 5787
prompt_sha256_16: ed94591fb57948f1
prompt_chars: 171453
snapshot: "n/a — API seat: no repository access, redacted ground pack only (no panel file embedded)"
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 9/13 — Multi-agent orchestration, fleet & cost/quota routing
model: Qwen3.8 Max (pinned lane)
sources: 15
repo_files_verified: 16
status: complete
sections_done: 0-9
---

**Method note (honesty, up front):** this lane had NO shell, file or web access. All repository claims are grounded in the redacted GROUND PACK appended to the lane prompt (16 files, several truncated at 12,000 chars). Files listed in the brief but absent/truncated from the pack (`research/operations/2026-08-21-token-ceremony-ci-system-audit.md`, `2026-08-21-universal-conductor-control-plane-design.md`, `2026-08-26-retro-fleet-sessions-25-26.md`, `CLAUDE.md`, `orchestrate_gate.py`, `dispatch_nudge.py`, `docs/runbooks/fleet-lane-dispatch.md`, and ALL listed `MEM:` bodies) are **unavailable to this lane**; claims that rest on them are labelled **ASSUMED**, and computable quantities I cannot compute are **UNMEASURED** with the exact command. `MEM:`/`$MEM` references are unavailable — stated wherever relevant. The SOTA survey cites training-knowledge sources (no live fetch); URLs I am not confident in are marked `(unverified)`. The report is returned as this final message per the lane instruction (the protocol’s write-then-`ls`/`wc` probe is therefore moot; estimated length ≈5,200 words). One disclosure: this lane itself appears to execute on the TP1/Qwen door the repo rosters (`MODEL_ROSTER.md`), i.e. the panel is a live data point of cross-family flat-sub routing.

## 0. TL;DR

Position: **AT-or-AHEAD on fleet architecture, liveness probing and cascade engineering; BEHIND on fan-out execution robustness and on consuming the telemetry it already builds** — the organism measures more than any surveyed system about its own seats, then dispatches as if it hadn’t.
Biggest gap: **no dispatch surface reads measured state** — quota, liveness and context-inheritance are discovered *post-hoc* from stderr, and it cost this panel 10 dead lanes in ~5 minutes (launch 1: 5 fork lanes × ~90K inherited tokens, dead in ~2 min; launch 2: 5 fresh pinned lanes, dead in ~3 min; third seat: 3% of 5h window but **91% of WEEKLY cap** — the 5h number lied).
Top-3 moves:
1. **Fleet-quota dispatch digest** — one fresh-timestamped JSON (seat-quota + TP1 burn + arsenal liveness + true-slack) that every dispatcher must read or DECLARE blindness.
2. **Fresh-first fan-out firewall** — inherited context becomes a budgeted, declared input; fork is opt-in; default = fresh context + grounding pack.
3. **Sunset-or-consume the conductor** — 81 endpoint profiles with zero live consumers get a consumer or the archive in 30 days; declared-only calibrations become measured or are deleted.

## 1. How Nuzantara does it today

*(Every claim below is grounded in the pack; pack-truncated or absent sources are flagged.)*

**1.1 Estate & topology (SSOT).** `FLEET_TOPOLOGY.json` (v1.4, updated 2026-08-20 by Zero ruling) is the SSOT for the cloud fleet: 6 Anthropic seats — A1–A5 (Claude Max 20x) + AZ (Claude Team seat Premium) — plus OpenAI O1/O2 (ChatGPT Pro, `CODEX_HOME` per account), Google G1 (AI Ultra: agy/Antigravity + NotebookLM), Moonshot K1 (Allegro flat → Kimi K3), Alibaba TP1 (Token Plan “Pro Plan”, one key, five families), and local Ollama for PII. Lanes are “HOME assignments, not fences”: each lane drains its home account first, then the ladder borrows from the least-loaded other account; cron/batch (A3) is the designated DONOR and pauses first — but the donor auto-pause is **UNARMED until the cron auto-pause hook lands (PENDING-ARMS)**; today donor rotation is manual. Hard invariants: final on-disk gate = Opus 5 xhigh, rotating AZ→A2→A3→A1, **never cascades to a weaker model; all accounts dead ⇒ task SUSPENDS/QUEUES**; Fable 5 is out of every automated role (manual-only); PII lanes = local models only, fail-closed; no external seat ever merges or deploys; per-token spend requires Zero’s explicit GO; spend order = flat subs → Token Plan credits → local; PROBATION seats are never load-bearing and never count toward refutation quorum. OAuth tokens carry **no identity**; the slot→account mapping written at setup-token time is the only registry (`FLEET_TOPOLOGY.json` `oauth_slot_note`, verified 2026-08-23).

**1.2 Roles & doctrine.** `MODEL_ROSTER.md` is the model×strength×effort×door catalogue, read by every conductor before choosing a seat (Zero ruling 2026-08-14). Categorical positions (`research/operations/2026-08-10-fleet-order-spec.md` §2): Opus 5 = Architect/Judge (all gates, post 2026-08-20 ruling); Sonnet 5 = First Builder/workhorse; Haiku 4.5 = Foot Soldier with 7 pinned grunt agent defs (`ledger-writer`, `lint-fixer`, `i18n-sync`, `fixture-gen`, `log-triage`, `catalog-meta`, `docs-sync`); Codex Sol = Prosecutor (refuter #1), Terra/Luna = second builders; Kimi K3 = Reviewer (refuter #2, 1M-context auditor); TP1 wing = Qwen 3.8 Max “Third Pole”, GLM 5.2 counter-builder, DeepSeek v4 second reasoner, all under hard NOs (no client PII, no client-facing outputs, no merge/deploy, no final gates, no Nuzantara credentials in env). OpenAI runs a single-role-per-account rule since bare slugs died 2026-07-21; versioned slugs (`-m gpt-5.6-sol/terra/luna` via `seat_build.sh --seat codex --tier …`) verified live 2026-08-27. The “workhorse-first” routing doctrine is named in the brief and consistent with the roster’s BUILD-stage default (“Opus 5 designs, Sonnet builds, Opus 5 verifies”), but its memo `decision_workhorse_first_routing_doctrine_2026_08_15.md` is NOT in the pack — exact content **ASSUMED**.

**1.3 Dispatch surfaces.** Four coexist:
- **Agent tool** (Claude-family fan-out): `model:` must be explicit — a HOME hook (`~/.claude/hooks/model_routing_gate.py`, PreToolUse on `Agent`) denies dispatches without an explicit model (`docs/mandates/2026-08-22-arsenal-routing-mandate.md` §1; hook source itself not in pack — structure **ASSUMED** from the mandate). Subagent chains cap at 5 levels (`.claude/skills/modus/SKILL.md`).
- **Workflow tool + `infra/workflows/*.js`**: durable templates (`verify-template.js` = gather→adversarial-verify→synthesize with `skeptics` parameter; `kbli-pilot-a1.js` = per-code D1→D5→D2 adjudication). Contract: pin `model:` on every `agent()`; generator≠grader; cross-family verifier; verdicts are leads; durable output on disk (`.claude/skills/workflow/SKILL.md`). Also hosts the **twin-session protocol** (disjoint lanes, durable artifacts on disk, handoff via ledger — skill frontmatter). Measured 2026-08-21: eight research lanes with no `model:` inherited Fable from the interactive session and died together on its limit 25 s in, having produced nothing — “a default that contradicts the rule is the rule that wins.”
- **Cross-family build door**: `scripts/seat_build.sh` (mandate D1, live by 2026-08-27 per `MODEL_ROSTER.md`), giving Codex/Kimi/Qwen/GLM the same one-call shape as `Agent`, worktree-only, JSON output contract `{seat, model, effort, rc, duration_s, diff_stat, tests, quota_exhausted}`, env stripped of foreign credentials.
- **Autonomous lane door**: `infra/launchagents/wrappers/claude-cascade.sh` — the quota-aware fallback cascade (below). Fleet-wide machine dispatch consumes `infra/fleet/nodes.json` (3 nodes: m5 interactive, pro dev+runtime, mini = H24 server “usually the freest”) via `scripts/fleet_dispatch.py` (script not in pack — **ASSUMED** current). “Army H24 lanes” beyond mini’s H24 role: **ASSUMED**, no pack evidence.

**1.4 The cascade.** `claude-cascade.sh` tries: (1) explicit Claude OAuth seats token_1…token_5, legacy token, then Keychain; (2) agy (Gemini 3.1 Pro); (3) Kimi K3; (4) `codex exec --sandbox read-only`; (5) `ollama run qwen3.5:9b`; (6) `fm respond` (Apple on-device FM, ~3B, grunt-only; benchmarked 2026-08-19: 12/15 vs Ollama 14/15). Failure detection is unusually rigorous: retryable classification on stderr is authoritative, but stdout is classified retryable **only when the whole payload is a known diagnostic envelope** (a successful answer may discuss “401”); reset-hint parsing; per-attempt timeout 900 s, total deadline 3600 s; W89 fix raises the print-mode background ceiling to 30 min because sonnet-5 in `--print` can silently background work and exit 0 with empty stdout; provider credentials are isolated per child (`build_isolated_provider_env`) and non-OAuth Anthropic credentials scrubbed. `--claude-only` mode keeps Claude-requiring jobs from crossing the provider boundary.

**1.5 Quota & cost plane.** `scripts/claude_seat_quota.py` (2026-08-23) reads the CLI’s own endpoint `GET /api/oauth/usage` — the only real source of 5h/weekly percentages. Two measured constraints: **(a)** long-lived cron tokens (`setup-token`) get HTTP 403 (`user:profile` scope missing) — quota is readable only per **interactively logged-in profile**; **(b)** the Keychain access token goes stale in ~1 h, so the tool WARMS profiles before reading (a cold read turns a saturated seat into a blank row). Pro measures and `--publish`es; other machines `--from-report` with a 90-minute `--max-age`; a stale report exits 2, never 0. Pacing 1.2 s between probes (without it, 3 of 9 entries came back rate-limited). Output includes `weekly_opus_pct`/`weekly_sonnet_pct` and `resets_at`. TP1 quota has **no API** (20 candidate paths probed, all 404) — ground truth is console-verified (2026-08-14: 7-day rolling quota 56.31% used; metered-equivalent ~$42/7d is reference-only; the rolling quota is the binding constraint; local `~/.qwen/usage` jsonl reconciled within ~2.5% over 1,330 calls / 211.7M tokens). Effort economics: **~86% of output tokens measured as thinking** (`research/operations/2026-08-21-token-ceremony-ci-system-audit.md`, cited via `.claude/skills/modus/SKILL.md`; file itself truncated in pack — per-gear cost **UNMEASURED**, command in §4). Gear↔effort mapping is doctrine: Gear 1 = `medium`; Gear 2 = `xhigh`; Gear 3 = `xhigh` with `max` opt-in only on declared adjudication; council only when divergent-priors ∧ error-cost>15×tokens ∧ parallel breadth; cache-aware polling ≤270 s or ≥1200 s, never ~300 s.

**1.6 Liveness plane.** `scripts/arsenal_probe.py` fires a real 1-shot probe per seat, classifies **output content, never exit code alone** (W84), taxonomy LIVE/AUTH_DEAD/CONTEXT_AUTH/QUOTA_DEAD/BALANCE_DEAD/MODEL_ERR/SHED/TIMEOUT/CRED_UNAVAILABLE/NOT_INSTALLED/UNKNOWN_ERR; blind-scan guard exits 2 on 0 seats probed; signaler-never-actuator; secret scrubbing on all evidence; per-machine `REQUIRED_SEATS`; 16 seats probed (9 named + 7 TP1 models); 15 s timeouts after the agy pipe-leak incident (detached grandchild holds stdout → probe now judges the REPLY in partial stdout before accepting TIMEOUT); TP1 probe uses `max_tokens=256` because at 8 the thinking models spent the whole budget on reasoning and three LIVE seats read dead (superscar #2 inverted; observed reasoning high-water mark 171 tokens on qwen3.7-max).

**1.7 Telemetry of the mix.** `scripts/seat_mix_report.py` (`docs/factory/SEAT-MIX.md`) stream-parses Claude transcripts and counts Agent dispatches by model/subagent_type, non-Anthropic seat calls by fixed vocabulary, and Workflow runs; PII-safe by construction (never reads `tool_result`/free text). Day-0 baseline (Pro, 48 h, 2026-08-27): 148 dispatches — sonnet 85.8%, inherit 12.2%, haiku 1.4%, opus 0.7%; subagent_type: general-purpose 113, Explore 14, backend-verifier 12, **fork 5**, unspecified 2; non-Anthropic calls 112 (0.76 per dispatch); workflow_runs: 1; unmapped sessions with activity: 35. Deliberately **descriptive, no thresholds** (retro A5 target-ratio proposal rejected). Cron daily 06:30 on Pro + Mini, not M5.

**1.8 Control plane (dormant).** `infra/conductor/`: `task_profiles.v1.json` defines 7 profiles (read_only, mechanical, standard_build, hard_build, architecture, review, pii_local) with minimum quality tiers, benchmark `conductor-priority-pilot`, context/output floors and PII policies — but **every evidence row is level `declared`**; `calibrations.v1.json` has **zero records**; `endpoint_profiles/` holds **ASSUMED** 81 cards (mandate §1 says 81) consumed by nothing live. The failed alternative they belonged to: Pro 21–22/8 `codex resume` fan-out, 281 rollouts/day — cards nobody reads (`docs/mandates/2026-08-22-arsenal-routing-mandate.md` §1; memory body unavailable — **MEM unavailable**).

**1.9 Client release governance.** `infra/fleet/llm-clients.json` locks versions for 14+ CLIs per machine (codex 0.147.0, claude 2.1.226, agy 1.1.11, kimi 0.34.0, nlm 0.9.8, grok, opencode, qwen, jules, pi, aider, cline, ollama, openclaw…), with `tracked` vs `canary_required` rollout rules and host_policy (ollama forbidden on m5, required pro/mini). Dispatch ergonomics: Claude Code agent-team panes require tmux or iTerm2 — bare Ghostty gives “No pane backend available” / iTerm2 split failures (observed 2026-08-18, `docs/runbooks/ghostty-fleet.md`); tmux now on all 3 nodes. “≤3 panes on Pro: pty ENXIO” dispatch discipline: the brief asserts it and the receptor-live ENXIO paragraph is NOT in the pack — **ASSUMED**. Fleet mailbox: `project_fleet_mailbox_cross_machine_session_messaging_2026_08_23.md` NOT in pack — **ASSUMED**/**MEM unavailable**.

**MEASURE block (requested):**
- *Seats×models×doors vs proven-live*: roster = 16 probe seats (`scripts/arsenal_probe.py::ALL_SEATS`), phantom-corrected (MiniMax M2.5 / kimi-k2.x NOT in TP1 plan — console 2026-08-14). Proven-live now: **UNMEASURED** — `python3 scripts/arsenal_probe.py --read-last --json` per machine (pack gives only dated point facts: kimi PONG-proven all machines 2026-07-19; A5 live 2026-08-19; tp1-glm-5.2 LIVE 2026-08-23; codex versioned slugs LIVE 2026-08-27; qwen3.8-max/qwen3.7-plus/dsv4-flash ARMED 2026-08-14).
- *Fork vs fresh share*: day-0 = fork 5/148 = **3.4%** of Agent dispatches (`docs/factory/SEAT-MIX.md`); context-inheritance mode itself is not recorded — **UNMEASURED**: `grep -o '"subagent_type":"[^"]*"' ~/.claude/projects/*/*.jsonl | sort | uniq -c`.
- *Quota-visibility gap*: visible = Anthropic seats with interactive Keychain logins on Pro (publisher); invisible = all cron-token seats (Mini/M5 hold tokens, report nothing), TP1 ceiling (console-only; burn locally computable), OpenAI/Kimi/Google windows (no mechanism in pack). ≈ **1 family, 1 machine, interactive-only**.

## 2. Scars & ledger evidence in this area

Direct grep of `cicatrix-scars.md`/`PENDING-ARMS.md`/`AMENDMENTS.md` was not possible in this lane (no shell; files not in pack) — **UNMEASURED**, commands: `grep -n "quota\|429\|cascade\|seat" .claude/rules/cicatrix-scars.md | head -30`; `grep -n "council\|fan-out\|agent" .claude/skills/modus/AMENDMENTS.md | head -30`. Evidence below is from scar references embedded in pack files:

| # | Event / scar | Evidence in pack | Recurrence? |
|---|---|---|---|
| S1 | **Superscar #2 “Esiste ≠ Armato”**: the multi-LLM cascade recommended 2026-05-24 was never armed; tier order assumed, not measured — Codex 401-silent, agy keychain-bound-under-ssh, DeepSeek 402 degraded cascades with no alarm | `scripts/arsenal_probe.py` header | Yes — the whole probe exists because it recurred; panel launch 1–2 repeat the shape (assumed-live capacity) |
| S2 | **Superscar #2 inverted**: TP1 probe at `max_tokens=8` let thinking models burn the budget on reasoning → 3 LIVE seats reported dead (“a board that marks live models dead is worse than no board”) | `scripts/arsenal_probe.py` TP1 comment, measured 2026-08-23 | Fixed in place (256), with explicit do-not-regress note |
| S3 | **W84 green-but-dead / exit-0-empty**: agy pipe-leak — detached grandchild holds stdout; every probe consumed full timeout; “0 bytes for 60 s” indistinguishable from hung | `scripts/arsenal_probe.py` 2026-08-07 incident note | Yes (agy -p RC 0 empty output again 2026-08-15, `.claude/skills/workflow/SKILL.md`) |
| S4 | **W89 print-mode silent backgrounding**: sonnet-5 `--print` backgrounds work, CLI kills it at the ceiling, exits 0 with nothing (regulatory-watcher-run.sh 2026-07-05) | `claude-cascade.sh` header | Class fix applied fleet-wide via the cascade ceiling |
| S5 | **W100 same-family agreement**: same-lane agreement certified 7 false-clean of 8 | `.claude/skills/workflow/SKILL.md` contract §3 | Motivated cross-family verifier rule |
| S6 | **W65 refuter hallucinates** — verdicts are leads, re-probe on disk | `.claude/skills/workflow/SKILL.md` contract §4 | Standing rule |
| S7 | **W107 cost-breaker coverage gap**: breaker threshold fine, but the spender (`genai_client.py`) never consults it | `research/operations/2026-08-10-fleet-order-spec.md` §1 | Open at PR #3914 time |
| S8 | **DEAD-GREEN quota watcher**: Playwright usage watcher ran hourly, exit 0, SESSION_EXPIRED for every account for months, knew only 3 accounts | `scripts/claude_seat_quota.py` header | Replaced 2026-08-23 by the OAuth-usage tool |
| S9 | **Inherited-model fan-out death**: 8 lanes without `model:` inherited Fable, died at 25 s, zero output | `.claude/skills/workflow/SKILL.md` §1 (2026-08-21) | Recurred as this panel’s launch 1 (fork × ~90K context, ~2 min) — same disease, new vector |
| S10 | **Conductor cards nobody reads**: 81 endpoint profiles + broker consumed by nothing live; 281 rollouts/day fan-out loop | `docs/mandates/2026-08-22-arsenal-routing-mandate.md` §1 | Dormant, unresolved |
| S11 | **Panel fresh evidence (measured 2026-08-28)**: launch 1 = 5 `fork` lanes on Fable inherited ~90K tokens each, died on the account session limit in ~2 min; launch 2 = 5 fresh-context pinned lanes died the same way on a second seat in ~3 min; third seat measured 3% of its 5h window but **91% of its WEEKLY cap**; panel moved to headless `claude -p` spread across seats | lane brief (measured, this panel) | First measured instance of weekly-cap surprise |
| S12 | **OAuth tokens carry no identity**; `setup-token` does not revoke predecessors (every superseded token valid ~1y, revocable only from console) | `FLEET_TOPOLOGY.json` `oauth_slot_note` (2026-08-23) | Standing registry discipline |
| S13 | **Quota strings burned silently**: piping into `agy -p` binds the flag as the prompt → RC 0, empty output, quota burned | `.claude/skills/workflow/SKILL.md` arsenal table (2026-08-15) | Same shape as S3 |
| S14 | **Pane-backend dispatch failure**: Agent-team panes fail outside tmux/iTerm2 (“Failed to create iTerm2 split pane” while in Ghostty) | `docs/runbooks/ghostty-fleet.md` (2026-08-18) | Fixed by tmux; ENXIO ≤3-pane limit on Pro **ASSUMED** |
| S15 | Seat-mix’s own PR: cross-family reviewer (Kimi K3) caught a secret-shape leak in free-captured flags + read/edit over-counting before merge | `docs/factory/SEAT-MIX.md` | Positive evidence the adversarial gate works on routing code itself |

Pattern: every scar in this lane is a case where **a channel-level signal (exit 0, card written, watcher green, tier listed, context inherited) was accepted as proof of work capacity**.

## 3. World SOTA survey

*(No web access in this lane; sources are from training knowledge, dated as published; accessed-noted 2026-08-28. Uncertain URLs marked `(unverified)`.)*

| System / practice | Source (date) | Mechanism that makes it best-in-class | Measured effect (published) | Transferability here |
|---|---|---|---|---|
| Anthropic multi-agent research system | anthropic.com/engineering/built-multi-agent-research-system (2025-06) | Lead-agent orchestrator spawns parallel subagents with explicit task briefs; honest token accounting | Multi-agent ≈15× chat tokens; wins on breadth tasks | Validates anti-sperpero “1 agent + budget”; briefs→grounding-packs pattern transfers directly |
| Anthropic “Building effective agents” | anthropic.com/engineering/building-effective-agents (2024-12) | Workflows≠agents taxonomy; orchestrator-workers; evaluator-optimizer loop | Qualitative; de-facto industry reference | `verify-template.js` already implements evaluator pattern; vocabulary aligns |
| Claude Code subagents / agent teams | docs.anthropic.com/en/docs/claude-code/sub-agents (2025); agent-teams docs `(unverified)` (2026) | Per-subagent model pinning, tool scoping, persistent defs | — | Already used (7 haiku defs); pinning rule matches |
| Cognition “Don’t Build Multi-Agents” | cognition.ai/blog/dont-build-multi-agents (2025-06) | Context-engineering argument: actions carry implicit decisions; parallel writers collide; share one full trace | Qualitative postmortems (Devin ops) | Strongest external validation of funnel-in-for-writes + fresh-context grounding packs |
| OpenAI Agents SDK / Swarm | openai.github.io/openai-agents-python (2025); github.com/openai/swarm (2024) | Handoffs as first-class transfer of control; guardrails; sessions/tracing | — | Handoff-as-ledger already exists (twin sessions); tracing gap is real (seat-mix is the homegrown analog) |
| LangGraph | langchain-ai.github.io/langgraph (2024–26) | Graph state machine, checkpointing = durable execution, interrupts | — | Durable-execution concept transfers; heavy framework does not (CLI-only, no paid infra) |
| MAST failure taxonomy | arxiv.org/abs/2503.13657 (Cemri et al., 2025-03) | 14 failure modes in 3 classes: specification, inter-agent misalignment, task verification | 150+ systems analyzed; verification failures dominant | Direct checklist for dispatch preflight + scar mapping |
| FrugalGPT | arxiv.org/abs/2305.05176 (Chen et al., 2023-05) | LLM cascade with confidence-based stopping; prompt adaptation | Up to 98% cost reduction or +4% quality | Cascade exists here on quota/auth; adding confidence-stop = transfer |
| RouteLLM | arxiv.org/abs/2406.18665 (Ong et al., 2024-06); github.com/lm-sys/RouteLLM | Learned/calibrated routers strong↔weak with quality constraint | ~85% cost reduction at ~95% quality retention (reported) | Router idea transfers, but currency is **quota not $**; could calibrate from evidence-pack verdicts |
| LiteLLM proxy | docs.litellm.ai; github.com/BerriAI/litellm (2023– ) | Unified gateway: fallbacks, cooldowns, per-key budgets, rate-limit-aware routing | — | Fallback/cooldown patterns match `claude-cascade.sh`; subscription windows are outside its model |
| Portkey Gateway | github.com/Portkey-AI/gateway (2023– ) | Conditional routing, fallback, load balancing as config | — | Same as LiteLLM; declarative route policies are the borrowable piece |
| Test-time compute scaling | arxiv.org/abs/2408.03314 (Snell et al., 2024-08) | Compute-optimal effort allocation by task difficulty beats blanket scaling | Gains over fixed-effort baselines | Backs gear↔effort table; argues for difficulty-conditioned effort, which task_profiles already model |
| Temporal durable execution | docs.temporal.io (2020– ); durable-execution-for-agents blog `(unverified)` (2024–25) | Workflow state survives crashes; retries/signals/durable timers | — | Artifact-anchored completion (§5-R6) is the infra-free analog |
| Google ADK / A2A | google.github.io/adk-docs (2025); github.com/a2aproject/A2A `(unverified)` (2025-04) | Inter-agent protocol (task lifecycle, artifacts) across vendors | — | Artifact+lifecycle message shape is borrowable for the fleet mailbox (MEM unavailable) |
| Borg / quota-aware scheduling | research.google Borg paper `(unverified)` (Verma et al., EuroSys 2015) | Priority bands, admission control, preemption, quota at fleet scale | Google-scale | Conceptual ancestor of quota-aware dispatch plane; donation = preemption with consent |

**The 3–5 that matter most.** (1) **Anthropic’s multi-agent research system** is the closest published cousin of this organism: orchestrator + parallel workers + explicit token economics; its key lesson — most tasks do NOT need multi-agent, and the ones that do need *excellent task briefs and explicit communication contracts* — is exactly the grounding-pack design this panel used. (2) **Cognition’s essay** is the strongest argument against naive fan-out and predicts launch-1’s failure mode precisely: forked lanes inherit implicit decisions (90K tokens of them) and then die or diverge; the counter-pattern (one context, or fresh workers given only what they need) is what “fresh-context pinned lanes” implement. (3) **MAST** gives the empirically-grounded failure checklist: specification failures (bad briefs), inter-agent misalignment (information withholding, ignored other-agent input), and weak verification — the organism’s scars S3/S5/S6/S9 map onto all three, and the taxonomy belongs in dispatch preflight. (4) **FrugalGPT/RouteLLM** define the routing-economic SOTA: cascades stop on *confidence*, routers choose on *measured quality under a budget*; Nuzantara’s cascade stops on *quota/auth* and its router chooses on *doctrine* — fusing the two (quota-aware + quality-calibrated) is unclaimed territory. (5) **LiteLLM/Portkey + Temporal** together show the two missing substrates: health-cooldown routing (they do it for APIs; nobody does it for subscription CLI seats) and durable completion signals (they need infra; here the artifact-on-disk can be the signal).

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Fleet estate & role architecture | **AHEAD** | 6-seat OAuth estate + 5 flat-sub families with categorical roles, PII fail-closed, spend order, rulings provenance (`FLEET_TOPOLOGY.json`, fleet-order-spec). No surveyed system documents seat roles at this rigor on subscriptions |
| Liveness probing | **AHEAD** | Content-classified probes, blind-scan guard, per-machine required seats, strict-fail taxonomy (`scripts/arsenal_probe.py`); gateways trust health endpoints/exit codes |
| Cascade engineering | **AHEAD** | Whole-envelope stdout classification, credential isolation, W89 ceiling, 6-tier ladder incl. on-device FM (`claude-cascade.sh`) — richer than LiteLLM/Portkey fallback config for this context |
| Quota observability | **AT** (recently) | `claude_seat_quota.py` is honest about its own limits (warm-up, pacing, freshness exits) — beyond SOTA in candor; but structural gap: interactive-profile-only, one publisher, other families invisible; weekly-vs-5h asymmetry still surprised the panel (S11) |
| Effort economics awareness | **AT/AHEAD** | 86%-thinking measurement, gear↔effort table, `max` opt-in ruling, cache-aware polling (modus SKILL). Cost-per-gear: **UNMEASURED** — `grep -n -i "gear\|cost\|token" research/operations/2026-08-21-token-ceremony-ci-system-audit.md \| head -60` |
| Routing compliance measurement | **BEHIND → AT (in flight)** | 2026-08-22: 62 build dispatches, all Sonnet; Codex workspace-write 7 vs read-only 63; Workflow tool ~0 genuine runs; 5/20 packs with cross-family reviewer (mandate §1). seat-mix day-0 exists; hook floor (D2) not yet verified in pack |
| Fan-out execution robustness | **BEHIND** | Launch 1–2 deaths (S11), fork inheritance, idle≠deliverable (measured twice, workflow SKILL §2bis), pane-backend constraints (ghostty runbook), ENXIO ≤3-pane limit (**ASSUMED**); no durable-execution substrate |
| Control-plane maturity | **BEHIND** | task profiles evidence=`declared` only; calibrations EMPTY; 81 endpoint profiles unconsumed (S10) |
| Client release governance | **AT** | `llm-clients.json` version locks + canary rules + host policy is rare for CLI fleets; two canaries blocked (aider, cline) show it is alive, not decorative |

## 5. Beyond-SOTA recommendations

Ranked by (impact × confidence) / cost. All respect hard rules (no paid Anthropic API, CLI-only, PII boundary, Fable never auto-routed, no per-token spend without GO).

### R1 — Fleet-quota dispatch digest (measure → route)
**What.** One fresh-timestamped artifact `~/.organism/fleet/quota-digest.json`, written on Pro and published like `seat-quota.json`, merging: `claude_seat_quota.py` output (session+weekly+per-model), TP1 burn computed locally from `~/.qwen/usage/token-usage-*.jsonl` against the console-verified ceiling, arsenal `last.json` liveness per seat, and a computed `true_slack = min(session headroom, weighted weekly headroom)` per seat. Every dispatcher (`claude-cascade.sh`, `seat_build.sh`, the routing hook, Workflow orchestration prompts) MUST read it (< max-age) or **DECLARE** “dispatching blind” in its output — never silently.
**Why it beats SOTA.** LiteLLM/Portkey route on API rate limits and dollar budgets; RouteLLM routes on $/quality. Nobody routes on 5h/7d **subscription windows across OAuth-swapped consumer seats**, and nobody composes liveness + quota + role permission at dispatch time for CLI seats. This is the organism’s unique asymmetry (6-seat estate + publisher pattern + probe SSOT) made load-bearing.
**Cost.** ~2 days flat-sub tokens; reuses three working scripts. **Gear 2.**
**Risk.** Stale/false-deny → superscar #2 inverted (healthy seat marked dead). Mitigated by fail-open + DECLARE.
**Metric.** Quota-dead launches/dispatches per week: baseline = panel launches 1–2 (10 lanes, ~5 min) + every cascade tier-skip; target −90%. Measured by cascade stderr tier-skip lines + seat-mix.
**Kill criterion.** ≥3 false denies in 2 weeks confirmed by `--deep` probe → disable preflight, keep digest as telemetry.
**First PR.** `scripts/fleet_quota_digest.py` + schema + freshness tests (≤400 lines): writer, `--max-age` reader exit-2-on-stale, guilt/innocence tests incl. stale-report and missing-profile cases.

### R2 — Fresh-first fan-out firewall (context-inheritance budget)
**What.** Make fresh-context the DEFAULT for every fan-out lane with an explicit grounding pack; `fork` becomes opt-in requiring a declared `context_budget:`. Preflight estimates inherited tokens (parent transcript size); above threshold (start: 40K or ~30% of a 5h session budget — calibrate from launch-1’s ~90K) → deny with the fresh-variant command, or convert. `model:` pinning remains mandatory (workflow SKILL §1; mandate D2 hook).
**Why it beats SOTA.** MAST documents these failures post-hoc; Anthropic prices them (~15× tokens) but leaves judgment to the operator. No surveyed orchestrator enforces an **inherited-context budget at spawn time**. Cognition’s essay argues for exactly this but ships no mechanism.
**Cost.** ~1 day (hook/preflight + runbook). **Gear 2.**
**Risk.** Over-conversion breaks legitimate twin-session continuity (scar #3-style over-match); overrides must be logged like `ROUTING_FLOOR_OK`, never silent.
**Metric.** Fan-out lanes dying before first durable artifact: before = 10/10 (panel) + 8/8 (2026-08-21); target 0 quota/context deaths. Measured via seat-mix `fork` bucket + wrapper logs.
**Kill criterion.** If converted-fresh lanes show higher evidence-pack refutation rates (grounding loss) over 30 days → raise threshold or restore fork-by-default for twin sessions only.
**First PR.** Preflight estimator + deny/convert message + guilt (90K fork denied) / innocence (small fork passes, explicit override logged) tests, ≤400 lines.

### R3 — Sunset-or-consume the conductor control plane
**What.** 30-day deadline: every `infra/conductor/endpoint_profiles/*.json` card declares a live consumer (the script that reads it) in a `CONSUMERS.md` registry, or is archived (`infra/conductor/archive/`, never deleted). `task_profiles.v1.json` evidence must move `declared → measured` by actually running `conductor-priority-pilot` (it already specifies `minimum_sample_count: 5`), writing real rows into `calibrations.v1.json` (currently EMPTY). A lint fails new declared-only rows.
**Why it beats SOTA.** RouteLLM/DSPy route only on measured scores; the organism’s own Law 7 (no metric = not an improvement) demands the same. The beyond-SOTA composition: calibration rows joined to **evidence-pack adversarial verdicts** give a quality router whose labels come from refuter seats — no surveyed system has ground-truth quality labels from an institutionalized generator≠grader gate.
**Cost.** ~1 day lint + archive; benchmark runs on flat subs. **Gear 1 (lint) / Gear 2 (benchmarks).**
**Risk.** Doctrine drift re-created (three-copies disease); mitigated by archive-with-provenance.
**Metric.** Profiles with live consumers: 0 → ≥10 (or archive to ≤15 cards); calibration records: 0 → ≥20 measured rows.
**Kill criterion.** None needed — full archival IS the success state (it proves the mechanism works).
**First PR.** `scripts/lint_conductor_consumers.py` + registry file (≤200 lines): guilt = all current cards fail; innocence = card with consumer row passes.

### R4 — Weekly-cap shadow pricing in effort routing
**What.** Dispatch consumes `true_slack` from R1: when `weekly_opus_pct ≥ 80%`, xhigh/max work (a) borrows another Anthropic account via the existing HOME-not-fence ladder — now automated by the digest instead of manual donor rotation, (b) QUEUES until `resets_at` with a visible notice, or (c) moves the BUILD portion to `seat_build.sh` cross-family seats while gates stay Opus-only (invariant intact: gates never cascade, they SUSPEND).
**Why it beats SOTA.** API-world gateways cannot see subscription weekly caps at all; `claude_seat_quota.py` already exposes `weekly_opus_pct`/`weekly_sonnet_pct` — nobody in the survey uses per-model weekly utilization as a routing input.
**Cost.** ~2 days; zero new tokens (routing only). **Gear 2.**
**Risk.** Gate SUSPEND queue latency affects ship pipeline; queue must be loud (scar #2 if invisible).
**Metric.** Unexpected weekly-cap deaths: before = panel launch 2 + third-seat 91% surprise; target 0. Share of autonomous dispatches made with `true_slack` in hand: target 100%.
**Kill criterion.** Merge/ship latency rises >24 h due to gate queueing → revert to manual donor rotation.
**First PR.** `true_slack` field in the digest + `claude-cascade.sh` seat-order reading it (≤300 lines), with DECLARED skip lines.

### R5 — Probe-gated cascade tiers (+ confidence stop)
**What.** `claude-cascade.sh` reads arsenal `last.json`/digest with max-age: skip tiers known QUOTA_DEAD/AUTH_DEAD (DECLARE the skip), attempt tiers whose status is older than per-seat TTLs (kimi’s TTL = Allegro cycle; TP1 = rolling 7d). Add a FrugalGPT-style **confidence stop** for grunt shapes: if tier-N output passes the shape check, never escalate.
**Why it beats SOTA.** Gateway cooldowns (LiteLLM) require a failure first; probe-gating with content-classified liveness prevents it, in a subscription-CLI context no gateway supports.
**Cost.** ~1 day shell + tests. **Gear 2.**
**Risk.** Stale liveness skips a revived tier (superscar #2 inverted) — TTLs must match refresh cycles.
**Metric.** Dead-tier attempts and wall-time per cascade invocation: before = up to 15 s + tokens per dead tier per call; target 0 attempts on known-dead-in-TTL.
**Kill criterion.** 3 events of skipping a tier a concurrent probe shows LIVE → revert to runtime detection.
**First PR.** Digest read + skip-declaration in cascade stderr (≤250 lines) + guilt/innocence tests.

### R6 — Artifact-anchored lane completion (deliverable > idle)
**What.** Every dispatched lane declares `--out <path>`; completion = artifact exists + heartbeat fresh + schema-valid. `notify_when_idle` stays a hint only (measured 2026-08-20: idle-without-report happened twice in one session). `verify-template.js` and fleet mailbox (**MEM unavailable** — integrate when readable) adopt the same contract.
**Why it beats SOTA.** Temporal-style durable completion needs infra; here W81 (a result that lives only in a return value is un-armed) becomes a positive primitive: the artifact IS the completion signal. No surveyed framework treats on-disk artifact as the lane-completion primitive for LLM workers.
**Cost.** ~1 day. **Gear 1–2.**
**Risk.** Empty-artifact gaming (reward hacking — lane 5’s jurisdiction; generator≠grader still applies to content).
**Metric.** Idle-without-deliverable events: before ≥2/session (measured) + panel dead launches; target 0 silent completions.
**Kill criterion.** >2 false “incomplete” flags/week on legitimate lanes → loosen checker.
**First PR.** Completion checker + `verify-template.js` wiring (≤300 lines).

## 6. 90-day roadmap + first PRs

**Wave 1 (days 0–30): measured state becomes dispatch input.**
- PR-A (R1): `scripts/fleet_quota_digest.py` — files: `scripts/fleet_quota_digest.py`, `infra/fleet/quota-digest.schema.json`, `scripts/tests/test_fleet_quota_digest.py`; ≤400 lines; Gear 2; acceptance: digest published on Pro; stale report refused exit 2; Mini/M5 read fresh; guilt (stale, missing profile, TP1 jsonl absent) + innocence tests pass.
- PR-B (R2): dispatch preflight context budget — files: `infra/claude-hooks/dispatch_preflight.py` + declared pair in `infra/home-fork/declared-pairs.json`, tests; ≤400 lines; Gear 2; acceptance: fork with >40K inherited tokens denied with the fresh-variant command; fresh lanes unaffected; override logged.
- PR-C (R3): conductor consumer lint — files: `scripts/lint_conductor_consumers.py`, `infra/conductor/CONSUMERS.md`; ≤200 lines; Gear 1; acceptance: lint fails on all 81 current cards, passes after a consumer row; CI wired.
- Operator (needs-ruling §7): install seat-mix cron on Pro+Mini per `docs/factory/SEAT-MIX.md`; cswap install/test (PENDING-ARMS).

**Wave 2 (days 31–60): routers consume the digest.**
- PR-D (R5): cascade reads digest, skips known-dead tiers with DECLARE (≤250 lines, Gear 2; acceptance: seeded QUOTA_DEAD tier skipped, TTL-expired tier attempted).
- PR-E (R4): `true_slack` + weekly-cap routing in cascade seat order and gate queue notices (≤300 lines, Gear 2; acceptance: at simulated weekly_opus 85% the ladder borrows before A3; queue notice printed).
- PR-F (R3): run `conductor-priority-pilot` on 3 task profiles (mechanical, standard_build, review), write first measured `calibrations.v1.json` rows (Gear 2; acceptance: ≥15 rows with sample counts ≥5, dispersion ≤ spec).

**Wave 3 (days 61–90): completion contracts + retro.**
- PR-G (R6): artifact-anchored completion checker + workflow template wiring (≤300 lines, Gear 1–2; acceptance: lane without artifact never counts complete; heartbeat staleness fails loud).
- PR-H: grunt-shape classifier added to `scripts/seat_mix_report.py` (descriptive only — no floor yet) to size the cheap-seat opportunity (day-0 `cheap_seat_share_pct` = 1.4%); ≤200 lines, Gear 1.
- Retro at day 90: apply every kill criterion; decide fork-budget threshold from 60 days of seat-mix; only then consider a cheap-seat NOTICE-lint (mirroring mandate D3’s 14-day pattern).

## 7. Needs-ruling

1. **Donor auto-pause arming** (`FLEET_TOPOLOGY.json`: A3 cron lane auto-pauses to donate its window to the gate; today manual, mechanism UNARMED pending PENDING-ARMS). Autonomous pausing of a Zero-owned account lane = Legge-5 consent. `needs-ruling`.
2. **Weekly-cap queue latency tolerance**: gates already SUSPEND when all windows die (ruling 2026-08-20). R4 makes queueing the *normal* pressure valve when weekly_opus ≥80%; acceptable ship-pipeline latency before Zero prefers explicit per-token GO overflow is a business decision. `needs-ruling`.
3. **A4 CLI login + cswap install on Pro/M5** (credential/console + machine actions; PENDING-ARMS; `FLEET_TOPOLOGY.json` slots). Operator-only. `needs-ruling`.

(Per-token spend remains unchanged: always requires Zero’s GO — no new ruling requested.)

## 8. §Meta-pattern

What repeats across every finding: the fork lanes that died inheriting 90K tokens; the 8 lanes that inherited Fable and died at 25 s; the 81 conductor cards nobody reads; the quota watcher that stayed DEAD-GREEN for months; the probe that marked live thinking-models dead at `max_tokens=8`; agy returning RC 0 with empty output; the third seat that looked 3% full and was 91% full. One defective belief generates all of them: **“the existence of a channel is evidence of its capacity.”** A spawn that exits 0, a card that is written, a watcher that runs, a tier that is listed, a context that is inherited, a 5h window that looks empty — each is a *declaration*, and each was treated as a *measurement*. Scar #2 (“Esiste ≠ Armato”) is precisely this belief, and the organism has already built the antidote machinery — empirical probes, freshness timestamps, content classification, Law 7 — but applies it **one layer away from the dispatch decision**: probes exist, dispatch doesn’t read them; quota tooling exists, launches didn’t consult the weekly number; pinning rules existed, the default won. The single beyond-SOTA move of this lane is therefore not a new organ but a closure: **no dispatch surface may consume declared state — every dispatch reads measured state with a freshness timestamp, or DECLARES that it is routing blind.** Existence is not capacity; inheritance is not capability; only a fresh measurement at the point of use is.

## 9. Sources

1. Anthropic — “How we built our multi-agent research system” — https://www.anthropic.com/engineering/built-multi-agent-research-system — 2025-06 — orchestrator-worker economics (~15× tokens); closest published analog.
2. Anthropic — “Building effective agents” — https://www.anthropic.com/engineering/building-effective-agents — 2024-12 — workflows/agents taxonomy, evaluator pattern.
3. Anthropic — Claude Code subagents docs — https://docs.anthropic.com/en/docs/claude-code/sub-agents — 2025 — per-agent model pinning, tool scoping.
4. Cognition — “Don’t Build Multi-Agents” — https://cognition.ai/blog/dont-build-multi-agents — 2025-06 — context-engineering case against naive fan-out.
5. OpenAI — Agents SDK docs — https://openai.github.io/openai-agents-python/ — 2025 — handoffs, guardrails, tracing.
6. OpenAI — Swarm (experimental) — https://github.com/openai/swarm — 2024 — handoff primitive lineage.
7. LangGraph docs — https://langchain-ai.github.io/langgraph/ — 2024–26 — supervisor patterns, checkpointed durable execution.
8. Cemri et al. — “Why Do Multi-Agent LLM Systems Fail?” (MAST) — https://arxiv.org/abs/2503.13657 — 2025-03 — failure taxonomy used for preflight checklist.
9. Chen et al. — FrugalGPT — https://arxiv.org/abs/2305.05176 — 2023-05 — cascade with confidence stopping (up to 98% cost cut).
10. Ong et al. — RouteLLM — https://arxiv.org/abs/2406.18665 — 2024-06 — calibrated strong/weak routing (~85% cost cut reported).
11. LiteLLM — https://docs.litellm.ai/ + https://github.com/BerriAI/litellm — 2023– — fallbacks, cooldowns, budgets at the gateway layer.
12. Portkey Gateway — https://github.com/Portkey-AI/gateway — 2023– — declarative fallback/load-balancing policies.
13. Snell et al. — “Scaling LLM Test-Time Compute Optimally…” — https://arxiv.org/abs/2408.03314 — 2024-08 — effort allocation conditioned on task difficulty.
14. Temporal — durable execution docs — https://docs.temporal.io/ (agents essay `(unverified)`) — 2020–25 — durable completion signals; analog = artifact-anchored completion.
15. Google — ADK docs — https://google.github.io/adk-docs/ — 2025; A2A repo https://github.com/a2aproject/A2A `(unverified)` — 2025-04 — inter-agent task/artifact lifecycle shapes for the fleet mailbox.
16. Verma et al. — “Large-scale cluster management at Google with Borg” — https://research.google/pubs/pub43438/ `(unverified)` — EuroSys 2015 — quota-aware scheduling, priority/preemption ancestry of the dispatch digest.