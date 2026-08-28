---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: 9/13 — Multi-agent orchestration, fleet & cost/quota routing
model: claude-fable-5 (pinned lane)
sources: 11
repo_files_verified: 26
status: complete
sections_done: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
---

# Beyond-SOTA 9/13 — Multi-agent orchestration, fleet & cost/quota routing

## §0 — TL;DR

Position in one sentence: **ahead of SOTA where routing meets judgment** (invariant-carrying
fleet topology, family-exclusion as a routing constraint, a living failure corpus, measured
effort economics no lab publishes), **behind where routing meets plumbing** (no pre-dispatch
budget check, no cooldown memory, no durable lane state, a conductor control plane with 75
endpoint cards and **zero** calibration records that no live organ reads).
Biggest gap: **quota is discovered by dying** — the cascade greps error strings post-failure
while LiteLLM-class routers filter pre-call; two panel launches burned 2 seats and 10 lanes
in ~5 minutes on a weekly cap that was invisible at dispatch (3% session / 91% weekly).
Top-3 moves: **R1** seat-state ledger + pre-dispatch budget check denominated in OAuth
windows (the currency no published router models); **R5** `fleet_burst` — account-sharded
headless fan-out (one seat per heavy lane, W132 sterile config, ≤3 spawns, incremental
outputs) as a first-class command; **R2** distill Evidence-Pack merge/revert outcomes into
the empty `calibrations.v1.json` — the first fleet router calibrated on its own shipped
consequences rather than benchmarks.

## §1 — How Nuzantara does it today

### 1.1 Topology: one SSOT, five provider families, twelve role chains

`FLEET_TOPOLOGY.json` (v1.4, updated 2026-08-20) is the single source of truth for the cloud
fleet: 5 account families (`anthropic`, `openai`, `google`, `moonshot`, `alibaba`), 4
orchestrator doors (`claude`, `codex`, `agy`, `kimi` — "Conductor is a ROLE", any door may
drive), 12 role chains (`gear3_final_gate`, `interactive_architect`, `builder_primary`,
`builder_frontend`, `refuter`, `strategy_panel`, `grunt`, `batch_throughput`,
`doc_mass_nonpii`, `pii_intake`, `normative_search`, `gate_gear2`, `reasoner`), and 9
invariants (verified by dumping the JSON in this session). Escalation is codified in the
chains' own `_doc`: *rotate_account (same model) → next model in chain → queue*, with
cross-family hops marking `degraded_execution:true` in the Evidence Pack. Key invariants:
final gate = Opus 5 rotating AZ→A2→A3→A1, never cascades to a weaker model, all-dead ⇒
SUSPEND; PII lanes = local models only, fail-closed; no external seat ever merges or deploys;
per-token spend needs Zero's explicit GO; PROBATION seats never load-bearing and never count
toward refutation quorum. Anthropic seats: 6 OAuth slots (5 MAX x20 + 1 Team premium), Team
LAST by ruling (global CLAUDE.md: enforced by `scripts/tests/test_claude_oauth_slot6_coverage.py`
with an ordering suite that goes red if slot 6 precedes slot 5). Lanes are "HOME assignments,
not fences": each lane drains its home account first, then borrows from the least-loaded.
`research/operations/2026-08-10-fleet-order-spec.md` is the narrative spec behind it (account
map §3.1, continuity ladders §3.2, gate taxonomy §4 — the "drift-killer" table that keeps four
distinct organs called "gate" from being conflated, W86-class).

### 1.2 The conductor control plane — built, and mostly unread

`infra/conductor/` holds a genuinely SOTA-shaped control plane: **75 endpoint profiles**
(counted with `ls | wc -l`: 6 Claude, 10 Codex, 7 Kimi, 4 agy/Gemini, 14 Ollama, the TP1/qwen
wing, NotebookLM), model cards + schemas, seat maps, a capability ontology, host observations,
and **7 task profiles** (`read_only`, `mechanical`, `standard_build`, `hard_build`,
`architecture`, `review`, `pii_local`) each declaring `minimum_quality_tier`, benchmark id,
`minimum_sample_count`, `maximum_dispersion`, context/output floors, and `pii_policy`
(`infra/conductor/task_profiles.v1.json`). But two measured facts undercut it:
`infra/conductor/calibrations.v1.json` contains **zero records** (`records: []`, verified) —
the feedback loop that would tune routing from observed outcomes was never populated; and the
memory `discovery_codex_resume_fan_out_loop_on_pro_conductor_cards_nobody_reads_2026_08_22`
records that the endpoint cards are read only by `scripts/conductor/*` and the KBLI
calibration emitters — **the live routing organs (modus, hooks, CLAUDE.md) route by
`MODEL_ROSTER.md` + `FLEET_TOPOLOGY.json` prose/JSON, not by the cards**. The control plane
exists; the control loop is open.

### 1.3 Cascade mechanics

`infra/launchagents/wrappers/claude-cascade.sh` is the single entry point for autonomous
Claude invocations: tier 1 = explicit OAuth seats token_1..token_5 → legacy env token →
Keychain; tier 2 `agy`; tier 3 Kimi K3; tier 4 `codex exec` (seat list delegated to
`scripts/lib/codex_seat.sh` — "two copies of a seat list is how" drift happens — with a
primary-bucket → spark-model retry per seat, exhaustion rc=98); tier 5 Ollama; tier 6 Apple
on-device Foundation Model (benchmarked 12/15 vs qwen3.5:9b 14/15 on triage shapes, kill
switch `CLAUDE_CASCADE_FM=0`). Quota-exhaust detection is a case-insensitive grep
(`out of extra usage|usage limit|quota exceeded|rate.limit|429|exhausted`). Two hard-won
properties are in the header itself: the W89-class fix (sonnet-5 in `--print` mode can
silently background its work and exit 0 with empty stdout — the ceiling is raised and callers
must add their own anti-background sentence), and **fail-closed on agent contracts**: if
`--claude-only`, a named `--agent`, or extra CLI args are present and every Claude seat fails,
the cascade exits 1 rather than crossing families and silently dropping the tool policy.

### 1.4 Quota measurement and seat liveness

`scripts/claude_seat_quota.py` (header, verified) documents the two non-obvious measured
facts that define the **quota-visibility gap**: (1) long-lived `setup-token` credentials get
HTTP 403 on `GET /api/oauth/usage` (missing `user:profile` scope) — only the interactive
Keychain credential can read quota, so **a machine holding six perfectly good cron tokens can
report nothing**; (2) the Keychain access token goes stale in ~1h, so the tool warms each
profile before reading (`--deep` adds a 1-token inference). Consequence: **Pro measures and
publishes; Mini and M5 read**, with a freshness gate (`--max-age` 90 min, exit 2 on stale —
"a cached report that outlives its truth is the same disease as the watcher this file
replaced", the Playwright usage-watcher that was DEAD-GREEN for months reporting
SESSION_EXPIRED). Tokens carry no identity: the slot→account map is documental (from the
2026-08-23 setup-token transcript), not re-measurable from the token — `.claude.json` is an
explicitly-named stale proxy that produced a false registry on 2026-08-22 (global CLAUDE.md).
`scripts/arsenal_probe.py` closes the liveness half: 16+ seats probed with real 1-shot calls,
classified by **output content, never exit code alone** (W84), `scrub()` redaction on every
evidence tail, blind-scan guard (0 seats probed ⇒ exit 2, "an infrastructure failure
masquerading as calm"), and a declared identity: "SIGNALER, NEVER ACTUATOR". At this
session's boot the last probe (22h old) showed claude/agy/codex/codex-spark/qwen-cloud-code
all `✗timeout` while kimi/ollama/nlm/jules and 7 TP1 text models were live — the probe works;
the seats flap.

### 1.5 Routing doctrine: workhorse-first, consiglieri, effort as the cost dial

Three layered rulings govern who does what. **Workhorse-first (Zero 2026-08-15, binding, in
memory `decision_workhorse_first_routing_doctrine_2026_08_15`)**: Anthropic seats do
orchestration, architectural judgment and final gates ONLY; all implementer/batch/sweep/
iterative-review work routes to flat workhorse doors (TP1 `deepseek-v4-flash-0731` — 806
calls/131M tokens measured, the de-facto workhorse — `qwen3.7-plus`, GLM 5.2, Codex
terra/luna/Spark, Gemini flash/Spark, Jules). The triggering measurement: one /bot lane
burned **14% of the monthly Kimi quota in a single day** (21 review rounds with ~870KB
embedded diffs), zeroed one Max weekly and consumed 67% of another. A "consiglieri" tier
(Fable 5 · Codex Sol xhigh/max · Kimi K3 · Qwen3.8-Max) is to be used "il meno possibile".
**Task-shaped routing (Zero 2026-08-14, `MODEL_ROSTER.md` §Routing rule)**: grunt→haiku/
luna/kimi-highspeed, standard→sonnet/terra, hard→opus-xhigh/sol; multi-PR campaigns must
route ≥1 lane through a non-Anthropic builder — enforced by `scripts/evidence_pack_lint.py`
and the `model_routing_gate.py` routing-floor hook (which self-describes as "a hint with a
guard, not a safety boundary" — it fails open by design). **Throughput doctrine (Zero
2026-08-19, "costantemente in movimento")**: H24 standing lanes (Codex Spark 2h tick, Jules
3/day, Gemini Spark) "must WORK, not exist" (family #2); feeding `infra/army/spark-queue/` is
part of every conductor session's CLEAN stage; the consumption dashboard is informative,
never a limiter (verbatim: "che non sia un limite!"). Effort economics: the token-ceremony
audit (`research/operations/2026-08-21-token-ceremony-ci-system-audit.md`) measured **~86% of
32.3M output tokens/7d as invisible thinking** (visible text 0.7M + tool payloads 3.7M =
14%; tool-less turns are 96% thinking), Fable at 63% of output tokens, **median 178K output
tokens per PR** (mean 253K), and a ~45K static SessionStart prefix accounting for **≈15% of
9.1B cache-read tokens/7d**. Its L0/L6 levers (gear-gated effort; a *ceiling* for the
deterministic gear floor: "floor 1 ⇒ no council, no external refuter, effort=medium") sit in
PENDING-ARMS, operator-gated.

### 1.6 Dispatch machinery

Five distinct mechanisms coexist. (a) **Agent tool** — in-session subagents, fork (inherits
session context) vs fresh, pane vs background; nested chains capped at 5 levels since
v2.1.172 (AMENDMENTS row: budget must count descendants). (b) **Workflow tool** +
`infra/workflows/` — durable, citable orchestration scripts (`verify-template.js` =
generator≠grader gather→refute→synthesize; `kbli-pilot-a1.js` = D1→D5→D2 per-code
adjudication with blind re-derivation; `modus-bench.js`), born because ad-hoc session
workflow files "vanish". (c) **Headless CLI lanes** — `claude -p` processes, one OAuth seat
per lane; since 2026-08-28 the panel's own failures made this the ONLY sanctioned shape for
>2 Opus/Fable lanes (AMENDMENTS 2026-08-28), and W132 (#5176, landed on main after this
worktree's HEAD, observed in the boot feed) pins `claude -p` children to a sterile config
dir with no session persistence. (d) **Cross-machine**: `scripts/fleet_dispatch.py` over
`infra/fleet/nodes.json` (3 nodes; repo path deliberately NOT stored per node — resolved as
`$HOME/nuzantara` on target to kill family-#1 path drift), the twin-Opus protocol
(`.claude/skills/workflow/SKILL.md` §4: claim-before-work in a ledger, disjoint file scopes,
handoff = merged artifact + ledger line never chat memory, one deploy lease at a time,
workflows die with their session), and the **fleet mailbox** (memory
`project_fleet_mailbox_..._2026_08_23`: Remote Control is per-account and thus a dead end
across Max/Team logins; socket forwarding is anti-tampered; so a file mailbox
`~/.nuzantara-mailbox/<session_id>/` 0700 + a PostToolUse/Stop hook injects ≤3 messages/fire
with at-most-once rename semantics — PR #4602). (e) **Hooks as dispatch governors**:
`dispatch_nudge.py` (empirically-corrected DISPATCH_KEYWORDS after "Agent(" scored 0
occurrences in real transcripts), `orchestrate_gate.py` (phase-aware, fail-safe when
`_phase` missing), `model_routing_gate.py` (routing floor). Dispatch concurrency discipline:
**≤3 panes at a time on Pro** — 13/14 tmux pane spawns failed with `fork failed: Device not
configured` (ENXIO pty-allocation race, 31/511 ptys in use, fds fine; memory
`project_receptor_live_mandate_2026_08_26`).

### 1.7 Cost observability

`scripts/seat_mix_report.py` (spec in `docs/factory/SEAT-MIX.md`) stream-parses the fleet's
own transcripts and counts Agent dispatch mix, non-Anthropic seat calls, and Workflow runs —
**deliberately descriptive, not a gate** (the retro's A5 target-ratio proposal was rejected).
It is complementary to `scripts/usage/seat_usage_collector.py` (tokens per profile seat). The
one hand parse that motivated it (2026-08-26): **882 Agent dispatches fleet-wide in 48h
(Sonnet 86%, Haiku 0.9%, Opus the rest), ~512 non-Anthropic shell calls, the Workflow tool at
0 genuine runs, and only 5 of 20 evidence packs carrying a cross-family reviewer.**

### 1.8 Fresh panel evidence (2026-08-28, measured in/around this run)

Launch 1: 5 parallel `fork` lanes on Fable each inherited ~90K tokens of session context and
died on the account session limit within ~2 minutes. Launch 2: 5 fresh-context pinned pane
lanes died the same way on a second seat within ~3 minutes. A third seat then measured **3%
of its 5h session window but 91% of its WEEKLY cap** — the two budgets are independent and
the weekly one is invisible until probed. A third launch of 2 lanes was killed by the
orchestrator on the belief they were stuck while their output files had already reached
4.4K/4.6K words (AMENDMENTS 2026-08-28 row, verified in this session). The panel completed as
headless `claude -p` processes spread across fleet seats, writing incrementally — the shape
this very report obeys.

## §2 — Scars & ledger evidence in this area

**The router's own quota detector over-matched (W92, 2026-07-11, family #3).** `QUOTA_RE`
contained bare `429`; the KBLI queue resumed exactly at codes 42911-42919, whose digits appear
in every valid completion → every SUCCESS on that block classified as quota → infinite
backoff, 0 drafts written. Part of the earlier "Codex quota genuinely exhausted" diagnosis
was this over-match. The bare-`429` cascade-detection pattern is COPIED across N wrappers —
the scar warns each copy is a mine wherever payloads can contain "429" as data.

**Fan-out shape scars, in chronological order (all from `.claude/skills/modus/AMENDMENTS.md`,
grepped this session).** 2026-07-02: all 6 parallel Agent dispatches died in a headless
session ("Could not determine current tmux pane/window") → probe the Agent tool with 1 cheap
dispatch before planning fan-out. Same day: the refuter cascade's middle tiers were dead
(DeepSeek 402 twice, GLM permission-denied) → a seat that fails its live probe is itself an
un-armed artifact needing a PENDING-ARMS line, not a narrative. 2026-07-05: background
read-subagents delivered AFTER the orchestrator had re-done both lanes first-hand; a red-team
verdict landed after auto-merge was armed and #1963 merged carrying a fixable regression.
2026-07-14: a 9-lane BUILD fan-out ran 9 full pre-push suites against ONE local test DB —
spurious reds under 7-18 concurrent suites, livelock; the push-train lock (mkdir-atomic, one
push per machine) was instituted only after the THIRD storm; also: subagents systematically
stall "waiting for the Monitor" (~8 hand-resumed), and a finisher was dispatched onto a
branch whose PR had already merged. 2026-07-16: **lane silent-idle is the dominant delivery
failure mode** (5+ occurrences over 4 lanes in one arc) — SendMessage is the last mile of the
deliverable. 2026-08-08: 9 false lane-deaths declared from `ListAgents` alone while `ps`
showed the processes alive; an owner-only `TaskUpdate` re-armed a stalled lane (an owner
change IS a dispatch); wave sizing must respect the ONE-suite-per-machine push lock, or
"parallel" dispatch degrades to a serial queue; a resumed Workflow received its args
JSON-stringified (recurrence of the 2026-07-02 dispatch-time bug at the resume entry point).

**The meta-scar (AMENDMENTS 2026-08-22).** Two sessions mandated to "cut token waste" ran
44h and 31h, opened 180 PRs, spent 8.6M output tokens, and shipped ~10 business commits;
27/200 commits on main that window existed only to correct a previous commit's claim; PR
#4547 (a 1-file hook regex) took 14 commits, 11 adversarial rounds, ~6h. Lead time for
≥100-line PRs did NOT improve (1.5h→1.6h median) while the CI lane did (23.9→12.9 min).
Verbatim: "the loop optimised itself and nothing else." Shipped cures same day: boot digest
no longer injects the overdue count by default; PR-contract rule 8 (three reds same cause ⇒
SUSPEND); a waste-reduction mandate is itself meta-work, geared 2 with a stop-loss.

**Refuter-on-live-worktree (AMENDMENTS 2026-08-23).** Kimi K3 dispatched against a worktree
being edited returned a fabricated CRITICAL from a torn read (old `shard_tests.py`, new test
file). Cure: refuters get an IMMUTABLE snapshot (`git archive <sha>`), never a live tree —
and a torn finding is indistinguishable in tone from a true one.

**The unread control plane + runaway loop (memory
`discovery_codex_resume_fan_out_..._2026_08_22`).** An interactive `codex resume` ran 21h
spawning `codex mcp-server` subagents — 281 rollouts/day, 60 live processes — editing 83
conductor endpoint cards in Pro's MAIN checkout (family #5). Zero's question — "imporrà
all'orchestratore o questo se ne sbatte?" — had the measured answer *se ne sbatte*: no live
organ reads the cards. Cost was CPU, sibling-race risk and attention, not tokens (flat-sub).
Also inside: `kill -9 $PIDS` silently no-ops under zsh (no word-splitting) — even killing a
runaway fleet has a scar.

**Hooks fail open under load (AMENDMENTS 2026-08-26, blind Kimi seat).** Claude Code
`command`-type PreToolUse hooks pass on timeout/crash per official docs — every dispatch
governor in §1.6 is advisory under load, which is why the same row found 22 proposed gates
share one shape: convert an existing prose rule into a check at a door that ALREADY exists
(pack linter, harness-floor, mailbox hook, ruleset API, `seat_build`), never a new prose
classifier.

**Quota-visibility scars.** The Playwright usage-watcher was DEAD-GREEN for months
(SESSION_EXPIRED on every account, exits 0, knew only 3 of 6 accounts) — the disease
`claude_seat_quota.py` §WHY exists to kill. `FLEET_TOPOLOGY.pending_arms[0]`: the cswap OAuth
profile swapper is still not installed/tested on Pro and M5 — seat rotation inside ONE
interactive session remains manual. The 2026-08-22 false seat registry (built from
`.claude.json` emails with `loggedIn:false`) is the identity-proxy scar: tokens carry no
identity.

**Panel self-scar (AMENDMENTS 2026-08-28 + protocol §4bis).** Two launches died leaving zero
bytes; a third was killed while alive. Codified: headless one-seat-per-lane for >2 heavy
lanes; incremental resumable output; ping every seat and classify with
`hit your (session |usage |weekly )?limit`; `ls -la` a lane's output before declaring it
dead. W132 (#5176) then pinned `claude -p` children to a sterile config dir — the panel's
failure became infrastructure within hours.

**Recurrence picture.** The dominant families here are #2 (green-but-dead: dead seats in
armed cascades, DEAD-GREEN watchers, H24 lanes ticking on empty queues, the empty
calibrations file) and #3 (over-match in the quota regex); the fan-out scars recur roughly
monthly since 2026-07 despite each being individually codified — because the codification
lands in prose (AMENDMENTS) faster than in enforced doors, which is precisely what the
2026-08-26 row itself concluded.

## §3 — World SOTA survey

| System / practice | Source | Mechanism | Measured effect | Transfers here? |
|---|---|---|---|---|
| Anthropic multi-agent research system | [1] | Orchestrator-worker; lead agent scales effort to query complexity (1 agent/3-10 calls → 10+ subagents); parallel tool calls; external-memory checkpoints; rainbow deploys | Multi-agent ≈ **15× chat tokens**; token use explains **80% of performance variance**; parallelism cut research time up to 90% | YES — we already run orchestrator-worker; the effort-scaling table and checkpoint/resume discipline map directly onto gears and §4bis |
| Cognition "Don't build multi-agents" | [2] | Single-threaded linear agent; share FULL traces not messages; "actions carry implicit decisions"; compressor model for long histories | Qualitative; production Devin practice | YES — matches our funnel-in-for-WRITES rule and the torn-snapshot scar (AMENDMENTS 2026-08-23); argues against peer-to-peer handoffs we also avoid |
| FrugalGPT | [3] | LLM cascade: query cheap model first, score answer, escalate only on low confidence | Matches GPT-4 at **up to 98% cost reduction**; 50-98% across benchmarks | PARTIAL — our cascade escalates on *availability/quota*, not on answer quality; the scoring idea transfers as verify-then-escalate for workhorse output |
| RouteLLM (Berkeley, ICLR 2025) | [4] | Learned router on preference data decides strong-vs-weak model per query | **85% cost cut on MT-Bench at 95% GPT-4 quality**, only 14% of queries to the strong model | PARTIAL — no paid API and no per-request logits here, but the *learned-from-outcomes* loop transfers to calibrations.v1.json (currently empty) |
| MAST failure taxonomy (Berkeley) | [5] | 14 failure modes from 1,600+ traces across 7 frameworks | Specification issues 41.8%, inter-agent misalignment 36.9%, verification 21.3% | YES — a public mirror of our AMENDMENTS corpus; their "verification failures" bucket is our generator≠grader doctrine vindicated |
| LiteLLM Router | [6] | Pre-call tpm/rpm filtering (Redis-tracked), per-deployment cooldowns (429 ⇒ 5s cooldown), tiered fallbacks (`order`), retry policies per exception class, traffic mirroring | Production-grade; mechanism doc, no benchmark | YES, ADAPTED — the pre-call budget check and event-driven cooldown are exactly what `claude-cascade.sh` lacks; our currency is OAuth session/weekly windows, not tpm |
| OpenAI Agents SDK handoffs | [7] | Handoff = tool call transferring the conversation; input filters shape carried history; agents-as-tools for structured sub-calls | Mechanism doc | PARTIAL — maps to our fork (full history) vs fresh subagent (task message) split; input filters ≈ our spawn-prompt discipline |
| Google A2A protocol (Linux Foundation) | [8] | AgentCard discovery at a well-known URL; 8-state task lifecycle (submitted…rejected); SSE/webhooks for long tasks | 50 → 150+ partner orgs (2025→2026) | PARTIAL — cross-vendor ceremony we don't need, but the explicit task lifecycle and capability card shame our `ListAgents` false-deaths and mandate-line ambiguity |
| Temporal / durable execution | [9] | Event-history replay: every step recorded; crash ⇒ replay history, skip completed activities, resume exactly where left off; OpenAI Agents SDK integration GA 2026-03 | Category "crossed into early majority in 2025" (AWS/Cloudflare/Vercel entries) | YES, ADAPTED — full Temporal is over-ceremony for a 3-node fleet, but replay-from-recorded-state is the cure for lane silent-idle and the panel's zero-bytes deaths |
| Adaptive test-time compute (Ares; AdaCtrl; TALE; survey) | [10] | Difficulty-aware effort: classifier or self-estimate sets reasoning budget per input; L1 controllability vs L2 adaptiveness taxonomy | e.g. exact budget targeting via monotone dual variable; large token cuts at flat accuracy (per-paper) | YES — we hold a deterministic difficulty signal none of them have: the CI-recomputed gear floor; binding effort to it is the armed version of this research |
| Claude Code subagents (official docs) | [11] | Fresh isolated context vs fork (inherits everything, shares prompt cache); background tool restriction; ≤20 concurrent, 3-deep nesting; per-subagent model/effort/memory/worktree isolation | Mechanism doc | YES — this IS our harness; fork's cache-sharing explains why the panel's 5 fork lanes each carried ~90K tokens into a shared session window |

**The five that matter most.** (1) **Anthropic's own numbers justify the whole routing
doctrine**: if token spend explains 80% of variance and multi-agent costs 15× chat, then an
org on FLAT subscriptions with SIX seats gets the 15× without the bill — but only if the
*window* accounting (session + weekly) is engineered as carefully as labs engineer dollar
accounting. Their explicit effort-scaling rubric (simple = 1 agent/3-10 calls) is the
published twin of our gear system; their checkpoint + rainbow-deploy discipline is what our
lanes lack. (2) **LiteLLM is the reference mechanism for the gap W92 exposed**: it filters
deployments BEFORE the call from tracked usage and cools down failing deployments
event-driven; our cascade greps error strings AFTER failure, re-tries dead seats every
invocation, and learned about weekly caps only when a seat died at 3% session / 91% weekly.
(3) **Cognition vs Anthropic is not a contradiction but a division of labor** we already
practice implicitly: parallel fan-out for READS (research lanes, this panel), single-threaded
context for WRITES (funnel-in) — the scar corpus (torn snapshot, twin-race) is our measured
proof of Cognition's "actions carry implicit decisions". (4) **Temporal's replay model** is
the structural answer to the AMENDMENTS' dominant failure class (silent-idle, stalls, false
deaths, zero-bytes window deaths): not adopting Temporal, but adopting its invariant —
*progress lives in a durable log, liveness is judged from the log, resume replays the log* —
which §4bis already applies to report files and W132 applies to child sessions. (5)
**RouteLLM's lesson is the loop, not the model**: the router is only as good as the
preference data feeding it; our equivalent preference data (Evidence-Pack verdicts, revert/
correction commits, seat attribution) already exists on main and feeds nothing — the empty
`calibrations.v1.json` is the one-file summary of our distance from learned routing.

## §4 — Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Fleet topology & role-chain routing | **AHEAD** | A versioned, invariant-carrying SSOT (`FLEET_TOPOLOGY.json` v1.4) with 12 role chains, PROBATION quorum rules, and `degraded_execution:true` marking on cross-family hops. No surveyed system encodes *adversarial integrity as a routing constraint* (refuter family ≠ builder family, fleet-order-spec §3.2); A2A standardizes transport, not judgment topology. |
| Quota / rate-limit-aware dispatch | **BEHIND** | LiteLLM filters deployments PRE-call from Redis-tracked tpm/rpm and cools down failing ones event-driven [6]. We detect exhaustion POST-failure by grepping strings (`claude-cascade.sh`), re-try dead seats on every invocation, and met the session-vs-weekly cap split only when a seat died at 3%/91% (2026-08-28). W92 is the scar of string-matching quota. |
| Cascade / fallback design | **AT** | 6-tier cascade with per-seat retry + spark-bucket fallback matches LiteLLM's tiered `order` semantics; **fail-closed on agent contracts** (never silently drop a tool policy crossing families) is a correctness property most gateways lack. Missing: cooldown memory between invocations; arsenal_probe liveness is a separate cadence, not an input to tier selection. |
| Cost-aware model routing | **MIXED: doctrine AHEAD, mechanism BEHIND** | Workhorse-first is a measured ruling (14%-monthly-in-a-day) with CI teeth (`evidence_pack_lint`, routing-floor hook) — stronger governance than any published practice. But the router itself is prose read by an LLM; `calibrations.v1.json` has 0 records; RouteLLM-class learning-from-outcomes [4] exists nowhere in the loop. |
| Effort economics | **AHEAD on measurement, BEHIND on actuation** | Nobody publishes per-org numbers like "~86% of output tokens are thinking; median 178K output tokens/PR" (token-ceremony audit). Yet effort is still hand-picked per session; Ares/AdaCtrl [10] auto-bind budget to difficulty, and our deterministic difficulty signal (CI-recomputed gear floor) has "no ceiling" (audit L6, in PENDING-ARMS un-armed). |
| Orchestration topology (fork/fresh/pane/headless) | **AT → AHEAD (post 2026-08-28)** | Matches Anthropic orchestrator-worker [1] + Cognition's reads-parallel/writes-serial caution [2]. The panel's failure produced a shape no surveyed doc has: **account-sharded fan-out** (one OAuth seat per heavy lane, headless, sterile config — W132) because our parallelism currency is seats, not tpm. Codified in AMENDMENTS 2026-08-28 within hours. |
| Durable execution / resumability | **BEHIND** | Temporal-class replay [9] is the category answer to our dominant delivery failure (lane silent-idle, 5+ per arc; ~8 hand-resumed lanes in one session; 9 false deaths on 2026-08-08; two panel launches leaving zero bytes). We have craft-level cures (§4bis incremental files, PENDING-ARMS as durable queue, Workflow resume — itself scarred by JSON-stringified args) but no event log a resume can replay. |
| Failure taxonomy & fleet telemetry | **AHEAD** | MAST built 14 modes from 1,600 traces once [5]; AMENDMENTS + scars are a *living* per-incident corpus with executable antidotes, and `seat_mix_report.py` parses our own transcripts as first-class telemetry (882 dispatches/48h measured). Deliberately descriptive-not-gate — a maturity most orgs lack. |
| Cross-machine / cross-session protocol | **AT** | Fleet mailbox (hook-injected, at-most-once, 0700) + twin-Opus claim-based lanes ≈ A2A's task lifecycle without the ceremony — appropriate for a 3-node fleet. BEHIND on discovery/liveness: `ListAgents` false deaths vs A2A's explicit 8-state lifecycle [8]. |
| Quota observability | **AHEAD (honesty) / structural gap (coverage)** | `claude_seat_quota.py`'s freshness-gated publish/read and `arsenal_probe.py`'s blind-scan guard + content classification are anti-DEAD-GREEN designs beyond typical dashboards. The coverage gap is structural: cron tokens 403 on usage; only Pro can measure; weekly caps invisible to the cascade at dispatch time. |

Honest summary: the organism is **ahead where routing meets judgment** (role chains,
family-exclusion, measured doctrine, failure corpus) and **behind where routing meets
plumbing** (pre-dispatch budget checks, cooldown memory, durable lane state, learned
calibration). Every BEHIND above is a composition of parts that already exist on disk.

## §5 — Beyond-SOTA recommendations (ranked by impact × confidence / cost)

**R1 — Seat-state ledger + pre-dispatch budget check ("LiteLLM cooldowns, denominated in OAuth windows").**
*What:* one machine-local, fleet-published state file (`~/.organism/seat-state.json`, same
publish/read + freshness-gate pattern as `claude_seat_quota.py`) holding, per Anthropic seat:
last quota read (session%, weekly%), last limit-hit (classified by the AMENDMENTS regex
`hit your (session |usage |weekly )?limit`), and a cooldown-until timestamp written
event-driven at failure time by `claude-cascade.sh` and by headless-lane wrappers. Every
dispatcher (cascade tier-1 loop, `fleet_burst` in R5, Agent-tool bursts via a PreToolUse
advisory) consults it BEFORE spending a call; seats >85% weekly or in cooldown are skipped
with a logged reason.
*Why beyond SOTA:* LiteLLM/Portkey/OpenRouter track tpm/rpm because dollars are their
currency [6]; nobody engineers **5h-session + weekly-cap OAuth windows across 6 accounts** as
the routing currency, because no lab runs on flat subscriptions by doctrine. This composes
three pieces that already exist (quota publisher, cascade, probe) into a closed pre-call
loop none of the surveyed systems has for this resource class.
*Cost:* ~1 day, Gear 2, ≤400 lines. *Risk:* family #2 — the ledger itself going DEAD-GREEN;
mitigated by inheriting the exit-2 staleness gate, and #3 — over-matching the limit regex
(W92 precedent: anchor it, guilt+innocence corpus).
*Metric:* dispatches-onto-exhausted-seat per week (panel baseline: 10 lanes lost across 2
launches in ~5 min, 2 seats burned) → 0; cascade stderr gains `skip <seat> reason=weekly:91%`.
*Kill criterion:* if 2 weeks of ledger entries show <1 skip/week, the check is ceremony —
fold it back into the cascade and delete the file.

**R2 — Close the conductor loop: calibrations distilled from merge outcomes.**
*What:* a nightly distiller (`scripts/conductor/distill_calibrations.py`) that joins
Evidence-Pack seat attributions with observed outcomes already on main (merged / reverted /
correction-commit within 7d / adversarial-round count) and writes real rows into
`infra/conductor/calibrations.v1.json` (schema exists, records: 0). First consumer: the
`model_routing_gate.py` floor hook reads ONE derived number (e.g. per-seat correction-rate on
standard_build) to bias its NOTICE text; second consumer: `seat_build.sh` default-seat pick.
*Why beyond SOTA:* RouteLLM learns from human preference pairs on benchmarks [4]; no
surveyed system calibrates routing on **its own merge/revert/correction telemetry** — we
uniquely have it because sessions own the full lifecycle and 27/200 commits in one window
were measurable self-corrections. This turns the built-but-unread control plane (§1.2) into
a closed loop instead of deleting it.
*Cost:* 2-3 days, Gear 3 (touches routing surfaces). *Risk:* #9 (schema drift between pack
fields and distiller — pin with a fixture test) and #6 (garbage-in: attribute outcomes only
where seat attribution is explicit in the pack).
*Metric:* `records > 0` within a week; after 30 days, at least one routing default changed
WITH a cited calibration row; correction-commit share on routed lanes vs baseline.
*Kill criterion:* if after 60 days no routing decision cites a record, archive
`infra/conductor/` as research and stop pretending it is a control plane.

**R3 — Bind effort to the gear floor at dispatch (arm the audit's L0/L6).**
*What:* `seat_build.sh` and subagent dispatch defaults read `compute_floor` and set
`effort`: floor 1 ⇒ medium, floor 3 ⇒ xhigh; `max` stays opt-in for declared Gear-3
adjudications; the final on-disk gate is untouched. One doctrine line (already drafted in
PENDING-ARMS 2026-08-21) + one mechanical default.
*Why beyond SOTA:* Ares/AdaCtrl estimate difficulty from the input [10]; we hold a
**deterministic, CI-recomputed, non-gameable difficulty signal** (the gear floor,
`evidence_pack_lint.py::compute_floor`) that no lab has, because no lab makes CI recompute
task difficulty from the diff. Binding effort to it is difficulty-aware compute with a
provable selector.
*Cost:* ~0.5 day mechanical, Gear 2; the doctrine line is `needs-ruling`. *Risk:*
under-thinking a mis-floored task (audit's own caveat) — floor may only be raised by the
model, never lowered; shadow-sample 20% of floor-1 lanes at xhigh for two weeks.
*Metric:* the audit's own: output tokens/PR ↓ ≥25% with correction-PR rate flat (baseline:
median 178K, ~86% thinking).
*Kill criterion:* correction-PR rate rises above baseline on floor-1 lanes ⇒ revert the
default, keep the telemetry.

**R4 — Durable lane log + resume ("Temporal-lite on files").**
*What:* every headless/background lane appends single-line events (dispatched, seat,
output-file, bytes-grown, limit-hit, done) to `~/.organism/lanes/<lane>.jsonl` via the same
hook family as the fleet mailbox; `scripts/lane_status.sh` derives liveness from **event
recency + output-file growth** (never `ListAgents` alone — 2026-08-08 scar), and
`scripts/lane_resume.sh` re-dispatches a dead lane with `claude -p --resume`-equivalent
context: its own output file + a "continue from first missing section" preamble (the §4bis
resume contract, generalized from reports to all lanes).
*Why beyond SOTA:* Temporal replays event history inside one runtime [9]; Anthropic
checkpoints inside one product [1]. Composing *file-based event logs + git-visible outputs +
seat-aware re-dispatch* gives replayable lanes across THREE machines and SIX accounts with
zero new infrastructure — durable execution for a fleet whose only shared substrate is the
filesystem and the repo.
*Cost:* 2 days, Gear 2. *Risk:* #5 (two resumers racing one lane — claim line in the lane
log is the lock, twin-protocol rule 1) and #2 (the log itself unread — wire `lane_status`
into the SessionStart digest).
*Metric:* hand-resumed lanes/week (~8 in the 2026-07-14 session; 2 panel lanes killed-while-
alive on 2026-08-28) → ≤1; false-death declarations → 0.
*Kill criterion:* if lanes keep silent-idling WITH events flowing, the failure is upstream
(SendMessage last-mile) — stop, fix that, don't grow the log.

**R5 — `fleet_burst`: account-sharded fan-out as a first-class dispatcher.**
*What:* one command that turns "N heavy lanes" into the only shape measured to survive:
headless `claude -p` per lane, **one OAuth seat per lane** (from R1's ledger, skipping hot
seats), sterile per-child config + no session persistence (W132), spawn staggered ≤3
concurrent process-creations (ENXIO scar), each lane's prompt carrying the §4bis
incremental-output contract, outputs under a declared directory `lane_status` watches.
*Why beyond SOTA:* every surveyed system parallelizes within one account's rate limits;
**sharding by account** is the native parallelism unit of a 6-seat flat-sub fleet and exists
in no published orchestration doc. It is also the codification of this panel's own measured
failure→recovery (0/10 lanes across two launches → completion via exactly this shape).
*Cost:* ~1 day, Gear 2 (compose R1 + W132 + AMENDMENTS 2026-08-28 rules a-d). *Risk:* #4 —
per-lane env must not leak sibling seat tokens (sterile config is the mitigation, verified by
W132's own test); #5 — output dirs must be per-lane.
*Metric:* heavy-fanout completion rate (baseline 0/10 first two launches; 13/13 required);
seats burned per panel (2 → 0).
*Kill criterion:* if two bursts in a row complete fine WITHOUT the seat ledger (quota
headroom returns), demote to a documented recipe and keep only the W132 pinning.

**R6 — Liveness-aware cascade memory (probe → tier selection).**
*What:* `claude-cascade.sh` consults `~/.organism/arsenal/last.json` (probe report, exists)
at entry: seats with a fresh `AUTH_DEAD`/`TIMEOUT` classification are tried LAST, not in
fixed order; a cascade failure writes back a one-line observation the next probe confirms.
*Why beyond SOTA:* closes the loop the probe's own header declares open ("SIGNALER, NEVER
ACTUATOR" stays true — the cascade acts, the probe only informs); LiteLLM has this as
cooldown [6], but denominated per-provider-seat with content-classified causes it becomes a
cross-family health-ordered cascade, which no gateway offers because no gateway spans 5
provider families through CLIs.
*Cost:* 0.5 day, Gear 2. *Risk:* #3 — stale probe inverting a healthy order; bound by
freshness window (probe older than 24h ⇒ ignore, keep static order).
*Metric:* wasted tier-attempts per cascade invocation (stderr already logs skips/failures —
count before/after).
*Kill criterion:* if measured wasted attempts <1 per invocation at baseline, skip — the
static order is already fine.

## §6 — 90-day roadmap + first PRs

**Wave 1 (days 0-30) — stop burning seats.** Ship R1 (seat-state ledger) and R5
(`fleet_burst`) together — they compose, and both are codifications of measured 2026-08-28
failures. Submit the R3 doctrine line for ruling; ship its mechanical half behind the ruling.
Success: zero dispatches onto an exhausted seat; one real burst (≥5 lanes) completes 100%.

**Wave 2 (days 30-60) — stop losing lanes.** Ship R4 (lane log + status + resume); wire
`lane_status` into the SessionStart digest; ship R6 (probe-ordered cascade). Success:
hand-resumes ≤1/week, false deaths 0, wasted cascade tiers measured and reduced.

**Wave 3 (days 60-90) — close the learning loop.** Ship R2 (calibration distiller); first
routing default changed with a cited calibration record; publish the weekly seat-mix delta
(SEAT-MIX exists) as the standing receptor for all of the above. Success: `records > 0` and
one documented routing change traced to a record — or the R2 kill criterion fires and the
conductor is honestly archived.

**First PRs** (each one concern, ≤400 net lines, acceptance test named):

1. `feat(fleet): seat-state ledger + cascade pre-dispatch check` — files:
   `scripts/lib/seat_state.sh` (new), `infra/launchagents/wrappers/claude-cascade.sh`
   (consult+writeback), `scripts/tests/test_seat_state.sh` (guilt: exhausted seat skipped;
   innocence: fresh seat used; staleness: old ledger ignored with exit-2 pattern). Gear 2.
2. `feat(fleet): fleet_burst — account-sharded headless fan-out` — files:
   `scripts/fleet_burst.sh` (new), `scripts/tests/test_fleet_burst.sh` (dry-run asserts: one
   distinct seat per lane, ≤3 concurrent spawns, sterile config flags present, output dir
   per lane). Gear 2.
3. `feat(effort): bind dispatch effort to compute_floor` — files: `scripts/seat_build.sh`,
   `scripts/tests/test_seat_build_effort.sh` (floor-1 diff ⇒ medium; floor-3 ⇒ xhigh;
   explicit override wins). Gear 2 + one `needs-ruling` doctrine line.
4. `feat(lanes): durable lane event log + status` — files: `scripts/lane_status.sh`,
   `infra/claude-hooks/lane_events.py` (same family as mailbox hook),
   `scripts/tests/test_lane_status.sh` (liveness from growth, not registry; dead lane with
   grown output reported ALIVE — the 2026-08-28 killed-while-alive case as the guilt test).
   Gear 2.
5. `feat(conductor): calibration distiller v0` — files:
   `scripts/conductor/distill_calibrations.py`, fixture pack + test asserting schema
   round-trip and ≥1 record from a fixture Evidence Pack. Gear 3 (hot routing surface —
   auto-merge per hot-zone rules).

## §7 — Needs-ruling (Legge 5)

- **R3 doctrine line** (effort default per floor) — already drafted in PENDING-ARMS
  2026-08-21 as `operator[business]`; the mechanical default ships only after the ruling.
- **Any change to Anthropic seat ORDER** (Team-last is Zero's 2026-08-23 ruling; R1's
  "skip hot seats" must never reorder Team ahead of MAX seats — it only skips).
- **TP1 credit-spend thresholds** for burst-scale workhorse use (spend order flat→credits→
  local is invariant [6 of FLEET_TOPOLOGY]; a burst that would dip into credits needs GO).
- **cswap/OAuth profile swapper install** on Pro and M5 — `FLEET_TOPOLOGY.pending_arms[0]`,
  `operator[control-plane]` (interactive Keychain logins only the human holds).

## §8 — §Meta-pattern (Gear 3)

One defective belief generates nearly every finding in this lane: **"a routing rule stated
in prose — or a control plane built on disk — IS a router."** The topology is written but
the dispatcher greps error strings after the fact (W92, quota-invisible-until-hit); the
control plane has 75 endpoint cards and 0 calibration records, and no live organ reads the
cards; the routing-floor hook fails open by design and PreToolUse gates fail open under load;
the H24 lanes exist and tick on empty queues; the fan-out shape was re-derived from scratch
roughly monthly (2026-07-02 → 07-14 → 08-08 → 08-26 → 08-28) because each codification
landed in AMENDMENTS prose faster than in an enforced door. This is superscar family #2
applied to the orchestration layer itself: *declared topology ≠ measured state*. The
organism already invented the antidote shape elsewhere — the receptor (seat-mix report,
freshness-gated quota publish, blind-scan-guarded probe). Every recommendation in §5 is the
same move repeated: take a routing belief that lives in prose, give it a measured state file
and a pre-action check, and let its kill criterion delete it if the measurement says it is
ceremony. The deeper asymmetry worth naming: this fleet's scarcity is not dollars (flat
subs) but **windows and attention** — SOTA tooling optimizes $/token and is therefore
blind exactly where this organism bleeds; that blindness is the beyond-SOTA opening.

## §9 — Sources

1. Anthropic — "How we built our multi-agent research system" — https://www.anthropic.com/engineering/multi-agent-research-system — accessed 2026-08-28 — first-party engineering account with published token-economics numbers (15×, 80% variance).
2. Cognition — "Don't build multi-agents" — https://cognition.com/blog/dont-build-multi-agents — accessed 2026-08-28 — Devin builders' production argument for context-sharing principles.
3. Chen, Zaharia, Zou — "FrugalGPT" — https://arxiv.org/abs/2305.05176 — accessed 2026-08-28 — the founding LLM-cascade paper (98% cost reduction result).
4. Ong et al. (LMSYS/Berkeley) — "RouteLLM" (ICLR 2025) — https://arxiv.org/abs/2406.18665 — accessed 2026-08-28 via survey results — learned strong/weak routing, 85% cost cut at 95% quality.
5. Cemri et al. (Berkeley) — "Why Do Multi-Agent LLM Systems Fail?" (MAST) — https://arxiv.org/abs/2503.13657 + https://github.com/multi-agent-systems-failure-taxonomy/MAST — accessed 2026-08-28 — 14 failure modes from 1,600+ traces; the field's failure taxonomy.
6. LiteLLM — Router documentation (routing strategies, cooldowns, fallbacks) — https://docs.litellm.ai/docs/routing — accessed 2026-08-28 — reference open-source implementation of pre-call rate-limit-aware routing.
7. OpenAI — Agents SDK "Handoffs" — https://openai.github.io/openai-agents-python/handoffs/ — accessed 2026-08-28 — official mechanism doc for delegation-as-tool-call and history filters.
8. A2A Project (Linux Foundation, orig. Google) — Agent2Agent Protocol Specification — https://a2a-protocol.org/latest/specification/ — accessed 2026-08-28 — the cross-vendor task-lifecycle/AgentCard standard (8-state lifecycle).
9. Temporal — durable execution for AI agents (event-history replay; OpenAI Agents SDK integration GA 2026-03) — https://temporal.io/blog — accessed 2026-08-28 via search — the category-defining durable-execution vendor.
10. Adaptive test-time compute cluster — Ares (https://arxiv.org/pdf/2603.07915), AdaCtrl (https://arxiv.org/pdf/2505.18822), BudgetThinker (https://arxiv.org/pdf/2508.17196), survey "Reasoning on a Budget" — accessed 2026-08-28 — difficulty-aware effort allocation research line.
11. Anthropic — Claude Code subagents documentation — https://code.claude.com/docs/en/sub-agents — accessed 2026-08-28 — authoritative mechanics of fork-vs-fresh context, background tool sets, concurrency caps (the harness this fleet runs on).
