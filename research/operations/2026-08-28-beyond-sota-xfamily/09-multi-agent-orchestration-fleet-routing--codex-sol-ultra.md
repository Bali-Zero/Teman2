---
panel: beyond-sota-xfamily
lane: 09-multi-agent-orchestration-fleet-routing
seat: codex-sol-ultra
model: "gpt-5.6-sol · reasoning_effort=ultra · Codex CLI read-only sandbox · web search on"
started: 2026-08-28T19:00:16Z
finished: 2026-08-28T19:08:48Z
duration_s: 512
exit: 0
words: 5066
prompt_sha256_16: d2221f4f15987947
prompt_chars: 19288
blind: true
note: "Same lane brief + protocol §0-§4 as the Fable panel; seat-neutral preamble; API seats got a redacted ground pack instead of file access; cwd = read-only shared clone of 45fd97f5c."
adversarial_review: "exempt-raw-external-seat-output — verbatim blind output of a non-Anthropic seat, kept unedited as evidence; its claims are weighed seat-against-seat in the INDEX §I cross-family section, never adopted from this file directly"
---

---
date: 2026-08-28
domain: operations
panel: beyond-sota-2026-08-28
part: "9/13 — Multi-agent orchestration, fleet & cost/quota routing"
model: "OpenAI GPT-5.6 sol, reasoning effort ULTRA (pinned lane)"
sources: 10
repo_files_verified: 20
status: complete
---

## 0. TL;DR

Nuzantara is ahead of SOTA in fleet diversity, sovereignty constraints, and role doctrine, but behind SOTA in the mechanical control plane that turns those assets into reliable throughput.
The largest gap is admission control: routing currently knows model roles but not trustworthy seat identity, quota headroom, inherited-context cost, host capacity, or calibrated task outcomes.
The six-account Anthropic estate and six canonical aliases create 36 nominal seat-model combinations, yet the probe verifies one generic Claude door—not the six identities.
This panel reproduced the failure: ten lanes across two launches exhausted two seats within minutes; a third seat had 97% five-hour headroom but only 9% weekly headroom.
Top move 1: compile every cascade and dispatch plan from `FLEET_TOPOLOGY.json`, then reject topology drift before execution.
Top move 2: make context weight, quota dimensions, machine capacity, and fresh-versus-fork mode mandatory dispatch inputs.
Top move 3: close the loop with outcome calibrations and a durable, cursor-based fleet journal.
The target is not “more agents”; it is at least 95% first-attempt starts, zero quota storms, 25–30% fewer reasoning tokens per accepted artifact, and no quality regression.

## 1. How Nuzantara does it today

### Fleet and role model

The current topology declares five Anthropic MAX accounts plus one Team Premium account, A1–A5 and AZ. Fable is manual-only when Zero explicitly opens it; PII work stays local; external seats cannot merge or deploy; and per-token spending requires a ruling. The topology also says homes are affinity hints rather than fences and that work should borrow the least-loaded eligible account, although donor auto-pause remains unarmed (`FLEET_TOPOLOGY.json:3-19`).

The three execution nodes have distinct intended roles: M5 is interactive, Pro combines development and runtime work, and Mini is the H24 heavy worker (`infra/fleet/nodes.json`). The client manifest enforces machine-specific availability, including no Ollama on M5 and local-model requirements on Pro/Mini (`infra/fleet/llm-clients.json`).

The canonical Anthropic roster contains six aliases: Fable 5, Opus 5, Opus 4.8, Sonnet 5, Sonnet 4.6, and Haiku 4.5. Opus 5 is the final judge, Sonnet 5 the default implementer, and Fable is excluded from automatic routing. The same roster defines OpenAI Sol/Terra/Luna roles, Google, Kimi, local models, and a TP1 wing (`MODEL_ROSTER.md:27-103`). Its throughput doctrine is explicitly workhorse-first: TP1 and Gemini should absorb implementation, batch, and review iteration before scarce Anthropic capacity; Anthropic should concentrate on orchestration and judgment (`MODEL_ROSTER.md:226-265`).

This yields a nominal Anthropic address space of six accounts × six aliases = 36 seat-model combinations, or 30 automatically eligible combinations after excluding Fable. That is a declaration, not proof of entitlement or capacity on each account.

### Conductor and empirical coverage

The conductor has substantial declarative breadth: read-only enumeration found 75 endpoint profiles and 75 corresponding model cards under `infra/conductor/endpoint_profiles/` and `infra/conductor/model_cards/`. It also has seven task profiles—read-only, mechanical, standard build, hard build, architecture, review, and PII-local—but their capability evidence is declared rather than benchmark-derived (`infra/conductor/task_profiles.v1.json`).

The feedback loop is empty: `infra/conductor/calibrations.v1.json` contains no records. The inspected Opus profile is `known_unmeasured`, with automated routing disabled, while its model card has no task scores (`infra/conductor/endpoint_profiles/claude-claude-opus-5.json`; `infra/conductor/model_cards/claude-opus-5.json`). The conductor is therefore a detailed catalog, not yet a scheduler.

The current empirical probe defines 16 logical rows: nine broad client doors plus seven explicit TP1 models. It probes only one generic `claude` row, not A1–A5 and AZ independently (`scripts/arsenal_probe.py:89-163`). The last repository-retained fleet review reported that the published board covered only 3 of roughly 15 doors and was not consumed by a scheduler (`research/operations/2026-08-26-retro-fleet-sessions-25-26.md:93-107`). Consequently:

| Surface | Declared | Empirically distinguished |
|---|---:|---:|
| Anthropic accounts | 6 | 1 generic Claude probe row |
| Anthropic seat-model combinations | 36 nominal | Not measured as a matrix |
| Conductor endpoint profiles | 75 | 0 calibrated |
| Probe logical doors | 16 in current code | Last retained board: 3/~15 |
| TP1 roster | 14 plan-visible models; 7 exact text seats | 7 current probe rows |

Fresh panel telemetry improves—but does not close—the account evidence. Two different seats returned account-limit failures, and a third exposed quota state; thus at least three distinct control surfaces were reached. It does not prove six simultaneously healthy seats.

### Cascade behavior and quota visibility

`claude-cascade.sh` detects quota, authentication, timeout, empty-output, and CLI failures that sometimes exit zero. That defensive classification is valuable (`infra/launchagents/wrappers/claude-cascade.sh:1-29,173-176,381-407`).

Its actual order, however, is hard-coded: five Claude slots, then Gemini, Kimi, Codex, Ollama, and Apple FM. TP1 is absent. More seriously, the wrapper treats slot 5 as Team while the current topology maps Team to slot 6 and assigns slot 5 elsewhere (`infra/launchagents/wrappers/claude-cascade.sh:787-864`; `FLEET_TOPOLOGY.json:24-63`). It therefore conflicts with both topology and workhorse-first doctrine. “All Anthropic first” consumes the scarcest shared windows before attempting intended workhorses.

Quota inspection has an unavoidable credential distinction. Long-lived setup tokens can execute work but lack the interactive profile scope needed by the usage endpoint; the token itself carries no account identity. Only warmed interactive credentials on Pro can report five-hour and weekly consumption, and stale reports older than 90 minutes are rejected (`scripts/claude_seat_quota.py:1-56`). Execution liveness and quota observability are therefore separate capabilities.

This panel exposed why both quota dimensions matter:

- Launch 1: five Fable `fork` lanes inherited roughly 90,000 tokens each—about 450,000 duplicated input tokens—and hit the first account’s session limit within roughly two minutes.
- Launch 2: five fresh-context pinned lanes hit a second account’s limit within roughly three minutes.
- Seat 3: only 3% of its five-hour window was used, but 91% of its weekly allocation was consumed.
- Recovery: execution moved to headless `claude -p` processes distributed across fleet seats.

These are measured panel-launch observations supplied directly in the 2026-08-28 lane brief. They show two independent defects: inherited context can create a burst multiplier, while fresh context cannot cure bad capacity admission.

### Dispatch, Workflow, and twin sessions

The Workflow skill requires explicit invocation, pinned models, durable output, and generator-versus-grader separation. It documents an earlier incident where eight unpinned lanes inherited Fable and exhausted the limit together 25 seconds into execution (`.claude/skills/workflow/SKILL.md:23-49`). It also distinguishes bounded specialists, verification pipelines, councils, sweeps, tournaments, and twin sessions. Twins must have disjoint scopes, durable handoffs, no overlapping files, independent workflow ownership, and one deploy lease (`.claude/skills/workflow/SKILL.md:130-190`).

The templates embody sensible patterns: a manager plus an independent clean-context skeptic, with three graders reserved for high-stakes work (`infra/workflows/README.md`). Adoption is negligible. A 48-hour sample found no genuine production Workflow run, despite 845–882 dispatches depending on the denominator used (`research/operations/2026-08-26-retro-fleet-sessions-25-26.md:36-107`).

The more focused seat census found 148 Agent dispatches:

- Sonnet: 127, or 85.8%.
- Inherited model: 18, or 12.2%.
- Haiku: 2, or 1.4%.
- Opus: 1, or 0.7%.
- Explicit `fork`: 5, or 3.4% of all dispatches.
- Cross-family evidence packs: 5 of 20.
- Workflow runs: 1 in that narrower parse.

“Fresh” was not recorded as a category, so 96.6% cannot honestly be called fresh; the fork/fresh share is unobservable beyond the five explicit forks (`docs/factory/SEAT-MIX.md:6-17,72-119`).

### Effort economics

The token-ceremony audit measured 140 M5 sessions, about 31.9 million output tokens, a 42,000-token doctrine prefix, and approximately 290,000 average context tokens. Only about 14% of output was visible text or tool calls; roughly 86% was reasoning. A trivial Codex PONG consumed 8,289 tokens after context injection (`research/operations/2026-08-21-token-ceremony-ci-system-audit.md:109-179`).

A valid cost-per-gear curve cannot yet be calculated. Only 17 of 140 sessions declared a gear—11 Gear 3, two Gear 2, and four Gear 1—so 87.9% lacked the label needed for attribution. The audit instead prescribes medium effort for Gear 1/2, xhigh for Gear 3, and max only for the final gate, estimating that a 30% thinking reduction on lower gears could save roughly eight million output tokens per week (`research/operations/2026-08-21-token-ceremony-ci-system-audit.md:204-239`).

Flat subscriptions eliminate marginal API invoices, not scarcity. The real cost function is quota opportunity cost, wall time, inherited context, retry amplification, host capacity, and the probability of consuming the final-gate reserve.

### Machine and mailbox pressure

The fleet reached 12 concurrent interactive sessions. A burst of 14 implementer lanes on Pro produced 13 `fork failed: Device not configured`/ENXIO failures even though only 31 of 511 PTYs were in use; sequential starts and batches of two or three worked. The operational ceiling is therefore no more than three concurrent subagent or tmux starts on Pro until the allocation race is removed (`research/operations/2026-08-26-retro-fleet-sessions-25-26.md:521-555`).

The fleet mailbox had 94 unarchived messages, no per-consumer TTL, and a three-message oldest-first delivery limit. Every session and subagent reread a three-day backlog. The retro estimated approximately six million repeated mailbox tokens in 48 hours; 45 of 94 messages were queue-unstick traffic, and one PR was paged 12 times (`research/operations/2026-08-26-retro-fleet-sessions-25-26.md:123-142`).

## 2. Scars & ledger evidence in this area

| Failure | Verified evidence | What actually failed | Recurrence/status |
|---|---|---|---|
| Numeric quota matcher | W92 records that a bare `429` matcher interpreted valid KBLI 429xx output as rate limiting and entered infinite backoff (`.claude/rules/cicatrix-scars.md:589-599`). | The cascade classified substrings instead of parsed provider state. | Still exposed: `claude-cascade.sh` retains a bare `429` alternative. This is superscar family #3, matcher/guard semantic drift. |
| Inherited-model burst | Eight unpinned Workflow lanes inherited Fable and died together after about 25 seconds (`.claude/skills/workflow/SKILL.md:23-49`). | A missing model pin silently multiplied the parent’s most expensive execution surface. | Recurred in this panel: five forked Fable lanes inherited ~90K context each and exhausted a seat in ~2 minutes. |
| Capacity-blind fresh burst | Five fresh pinned lanes exhausted a second seat in ~3 minutes; a third showed 3% five-hour but 91% weekly use (panel measurement, 2026-08-28). | Fresh context fixed inheritance but routing still ignored the limiting weekly window. | Current; recovery was manual redistribution through headless processes. |
| Host fan-out storm | Thirteen of fourteen simultaneous Pro pane starts failed with ENXIO (`research/operations/2026-08-26-retro-fleet-sessions-25-26.md:521-555`). | Dispatch treated logical lanes as free resources and ignored host admission rate. | Mitigated procedurally by a ≤3 start cap; not represented in conductor profiles. |
| Catalog without actuation | Seventy-five endpoint profiles exist, but calibration records are empty and the inspected Opus route is unmeasured and disabled (`infra/conductor/calibrations.v1.json`; `infra/conductor/endpoint_profiles/claude-claude-opus-5.json`). | Availability, quality, and task fitness are declarations rather than live scheduler inputs. | Current superscar-family-#2 risk: “exists” can be mistaken for “armed.” |
| Topology/cascade drift | Fleet topology declares six accounts and Team at slot 6; the wrapper iterates five and labels slot 5 Team (`FLEET_TOPOLOGY.json:24-63`; `infra/launchagents/wrappers/claude-cascade.sh:787-864`). | Two manually maintained representations disagree on account identity and order. | Current and load-bearing. |
| Homogeneous dispatch | Sonnet received 85.8% of Agent dispatches; Haiku received 1.4%; only 5/20 evidence packs used another family (`docs/factory/SEAT-MIX.md:6-17,72-119`). | Doctrine says task-shaped and cross-family; behavior remains inherited/default-heavy. | Current; no calibrated evidence says this allocation is optimal. |
| Workflow theater | No genuine production Workflow run was found in the broader 48-hour retro (`research/operations/2026-08-26-retro-fleet-sessions-25-26.md:93-107`). | Templates exist but are outside the dominant dispatch path. | Current family-#2 risk. |
| Mailbox amplification | Ninety-four unarchived messages drove an estimated six million repeated tokens in 48 hours (`research/operations/2026-08-26-retro-fleet-sessions-25-26.md:123-142`). | Delivery lacks durable per-consumer cursors, deduplication, and lifecycle compaction. | Current; repeated queue-unstick pages show operational recidivism. |
| Learning ledger silence | The same retro found no AMENDMENTS entries for August 24–26 despite multiple misfires, while 476 of 586 PENDING items were overdue or otherwise unresolved (`research/operations/2026-08-26-retro-fleet-sessions-25-26.md:123-168`; `.claude/skills/modus/AMENDMENTS.md`; `.claude/skills/modus/PENDING-ARMS.md`). | Failures generated traffic but did not reliably become routing corrections. | Current. |

The lane brief named nine `MEM:` records. The access contract explicitly prohibited reading `$HOME` or any memory directory, so those records were unavailable. No claim above relies on them; repository retros, doctrine, scars, and executable configuration were used instead.

## 3. World SOTA survey

| System/practice | Primary source | Mechanism | Published effect | Transferability |
|---|---|---|---|---|
| Anthropic multi-agent Research | [Anthropic, 2025](https://www.anthropic.com/engineering/multi-agent-research-system) | Lead orchestrator decomposes breadth-first research into independent parallel searches; workers return compressed findings. | 90.2% better than single-agent Opus 4 on Anthropic’s internal research evaluation; token use explained 80% of outcome variance. | High for independent read-only research; poor justification for parallel writers or indiscriminate fan-out. |
| Claude Code subagents | [Anthropic documentation](https://code.claude.com/docs/en/sub-agents) | Isolated contexts, explicit model selection, parallel independent exploration, resumable agent identity, and fork semantics. | No causal productivity benchmark published. | Directly transferable. Nuzantara should distinguish fresh, forked, and resumed contexts in dispatch telemetry and admission. |
| OpenAI Agents SDK orchestration | [OpenAI documentation](https://openai.github.io/openai-agents-python/multi_agent/) | Explicit choice between manager-owned “agents as tools,” control-transferring handoffs, and deterministic code orchestration. | No comparative effect published in the documentation. | Transfer the contracts, not the API runtime: Nuzantara’s LLM path remains CLI-only. |
| Google A2A | [Google Developers Blog, 2025](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) | Agent capabilities and collaboration are represented through a vendor-neutral protocol built on HTTP, SSE, and JSON-RPC. | No controlled deployment metric published. | Useful for mailbox envelopes, capability cards, task lifecycle, and opaque identity—not as a reason to add cloud infrastructure. |
| MAST | [“Why Do Multi-Agent LLM Systems Fail?”, 2025](https://arxiv.org/abs/2503.13657) | Empirically derived taxonomy of 14 failure modes across system design, inter-agent alignment, and verification/termination. | Three-expert annotation reached Cohen’s κ=0.88. | High: every failed dispatch should receive a machine-readable failure code rather than free-text “quota” or “agent failed.” |
| RouteLLM | [Ong et al., 2024/2025](https://arxiv.org/abs/2406.18665) | Learned router uses preference data to choose strong versus weak models by query. | More than 2× cost reduction in some evaluations without loss of response quality. | Adapt “cost” to subscription quota, latency, context, and correction probability; shadow-evaluate before enforcement. |
| FrugalGPT | [Chen, Zaharia, and Zou, 2023](https://arxiv.org/abs/2305.05176) | Learned cascades attempt cheaper models and escalate when confidence is insufficient. | Up to 98% cost reduction at matched quality, or 4% higher accuracy at equal cost in its evaluated API setting. | Mechanism transfers, but current Nuzantara’s Claude-first cascade is the reverse of a scarcity-aware cascade. |
| Temporal durable execution | [Temporal documentation](https://docs.temporal.io/) | Append-only event history, deterministic replay, durable workflow identity, retries, and resume after process or infrastructure failure. | Official guarantee, but no general agent-productivity benchmark. | Transfer the event-history semantics locally; do not violate the organism’s no-central-orchestrator doctrine by blindly adding a service. |
| Cognition’s working multi-agent pattern | [Cognition, 2026](https://cognition.com/blog/multi-agents-working) | Manager coordinates map-reduce work; parallel agents contribute intelligence while writes remain single-threaded. | No controlled metric for this pattern; Cognition reports it is live in Devin. | Very high for a shared repo: parallel read/review, disjoint write lanes, one synthesizer, one merge owner. |
| Mixture-of-Agents | [Wang et al., 2024](https://arxiv.org/abs/2406.04692) | Heterogeneous proposers feed later aggregators; diverse model outputs outperform repeated samples from one model. | 65.1% AlpacaEval 2.0 LC win rate versus 57.5% for GPT-4 Omni; six diverse proposers scored 61.3% versus 56.7% for repeated same-model proposals. | Use only for Gear-3 synthesis and adversarial review; its token multiplication is unsuitable for routine builds. |

The most important result is Anthropic’s boundary condition: parallelism wins when the query has independent breadth. It also wins largely because it spends more tokens. Nuzantara’s panel launches reproduced the cost side without obtaining the result side because account capacity was not admitted first.

Cognition supplies the coding-specific correction. Parallel intelligence can help, but concurrent writers embed unstated local decisions and fragment the codebase. Nuzantara’s worktree and twin-session doctrine already points in this direction; the missing layer is enforcement that separates read/review fan-out from write ownership.

RouteLLM and FrugalGPT show that routing should be learned from outcomes rather than expressed only as a static hierarchy. Their dollar-cost objective does not transfer literally to flat subscriptions. Their mechanism does: optimize the probability of acceptable completion per unit of weekly headroom, wall time, inherited context, and correction work.

MAST provides the vocabulary needed for calibration. “Quota,” “empty,” or “failed” are not sufficient outcomes. Nuzantara needs distinctions such as admission rejection, identity ambiguity, context overflow, provider window exhausted, host allocation failure, incomplete handoff, and incorrect termination.

Temporal’s event-history model is the right comparison for the mailbox. A fleet task should have one durable identity, replayable transitions, idempotent delivery, and per-consumer cursors. Reinjecting a shared three-day transcript into every session is neither communication nor durability.

## 4. Position vs SOTA

| Sub-dimension | Position | Evidence |
|---|---|---|
| Fleet diversity and sovereignty | **AHEAD** | Six Anthropic accounts, several cloud families, local models, machine locality, PII restrictions, manual-only Fable, and external-seat authority limits are encoded in `FLEET_TOPOLOGY.json:3-19` and `infra/fleet/llm-clients.json`. Few surveyed systems combine this diversity with local-sovereignty constraints. |
| Declarative capability inventory | **AHEAD in breadth; BEHIND in truthfulness** | Seventy-five profile/card pairs and seven task profiles exceed typical ad hoc routing tables, but `infra/conductor/calibrations.v1.json` is empty and inspected routing remains `known_unmeasured`. |
| Runtime account routing | **BEHIND** | `claude-cascade.sh` encodes five slots and the wrong Team position, omits TP1, and contradicts least-loaded/workhorse-first policy. SOTA routers make the selection policy one evaluated control surface. |
| Quota-aware admission | **BEHIND** | Execution tokens lack identity, quota needs warmed interactive profiles, and current probing does not distinguish six Claude accounts (`scripts/claude_seat_quota.py:1-56`; `scripts/arsenal_probe.py:89-163`). The panel launched into two exhausted accounts. |
| Context-aware fan-out | **BEHIND** | The system documents model pinning but admitted five ~90K forks simultaneously. Claude’s own primitives distinguish isolated, forked, and resumed state; Nuzantara does not record their predicted context cost. |
| Effort economics | **BEHIND** | Approximately 86% of output was reasoning, but only 12.1% of sampled sessions carried a gear label, making cost-per-gear unmeasurable (`research/operations/2026-08-21-token-ceremony-ci-system-audit.md:109-239`). |
| Host scheduling | **BEHIND** | Machine roles are explicit, but 14 simultaneous Pro starts caused 13 ENXIO failures. A procedural ≤3 cap is not an admission controller. |
| Orchestration patterns | **AT doctrine; BEHIND adoption** | Workflow templates match manager/worker and independent-grader SOTA, but the wider retro found zero genuine production uses (`infra/workflows/README.md`; `research/operations/2026-08-26-retro-fleet-sessions-25-26.md:93-107`). |
| Cross-family diversity | **AT concept; BEHIND execution** | The roster assigns distinct epistemic roles, yet only 5/20 evidence packs used another family and Sonnet received 85.8% of dispatches (`docs/factory/SEAT-MIX.md:6-17,72-119`). |
| Single-writer safety | **AHEAD in doctrine** | Twin sessions require disjoint scope and durable handoff, closely matching Cognition’s 2026 conclusion (`.claude/skills/workflow/SKILL.md:151-190`). Mechanical conformance remains incomplete. |
| Durable coordination | **BEHIND** | Mailbox replay is backlog reinjection rather than task-scoped event history, producing an estimated six million repeated tokens in 48 hours. |
| Failure learning | **BEHIND** | The scars are unusually rich, but empty calibrations and silent AMENDMENTS mean the router does not consume them. Nuzantara owns better failure data than surveyed systems yet does not close the loop. |

## 5. Beyond-SOTA recommendations

Ranking uses ordinal impact (1–5) × confidence ÷ implementation-cost band (1–5).

### 1. Topology-compiled, quota-aware admission controller — score 2.38

**What.** Produce a dry-run dispatch receipt before every multi-agent launch. It resolves task profile, model, opaque seat ID, machine, context mode, five-hour and weekly headroom, PTY-start budget, PII locality, and fallback chain. Generate cascade ordering from `FLEET_TOPOLOGY.json`; hand-maintained slot maps become invalid.

**Why it beats SOTA.** RouteLLM optimizes model quality/cost, while cluster schedulers admit machine resources. This composes both with constraints unique to Nuzantara: multiple flat-subscription windows, tokens without identity, manual-only Fable, local PII lanes, host-specific clients, final-gate reserves, and scars. None of the surveyed systems exposes that combined resource vector.

**Before/after metric.** Baseline: two five-lane panel launches failed on two accounts; one topology/cascade identity conflict; zero calibrated endpoints. Target after 100 dispatches: ≥95% first-attempt execution, zero seat-limit fan-out storms, zero generated-versus-canonical topology differences, and zero launches above three simultaneous Pro starts.

**Cost and gear.** Gear 3; 18–28 engineering hours; approximately 0.5–1.0 million flat-subscription evaluation tokens.

**Risk and scar family.** False admission rejection or stale quota state; families #2 and #3. Credential handling also touches family #4, so receipts must contain opaque IDs and percentages only.

**Kill criterion.** Disable enforcement if more than 2% of healthy dispatches are falsely rejected over 100 attempts or median start latency rises by more than 20% without reducing failure rate.

**First PR.** New `scripts/lint_fleet_routing.py` plus focused tests, ≤350 net lines. It only detects slot-count, Team-position, Fable, TP1, and fallback-order drift between `FLEET_TOPOLOGY.json` and `infra/launchagents/wrappers/claude-cascade.sh`; no actuation.

### 2. Context-weighted fan-out admission — score 2.25

**What.** Make `fresh`, `fork`, and `resume` explicit dispatch modes. Before spawning, estimate inherited tokens × lane count plus projected reasoning effort. Independent work defaults to fresh pinned contexts; forks require a declared dependency on parent state and a batch context ceiling.

**Why it beats SOTA.** Claude exposes the primitives, and Anthropic measures token volume as the dominant multi-agent performance factor. Nuzantara can go further by treating context as a schedulable resource tied to quota and machine admission, not merely a prompt-design concern.

**Before/after metric.** Baseline: about 450K inherited tokens in panel launch 1; roughly 900K across the two five-lane attempts if the second launch’s five fresh prompts are conservatively excluded from inherited-cost counting, the first alone still establishes the burst. Target: ≤100K inherited tokens per five-lane batch, ≥80% reduction in inherited context for independent lanes, and 30% fewer reasoning tokens per accepted artifact with no more than a two-point increase in correction rate.

**Cost and gear.** Gear 3 policy, Gear 2 implementation; 10–16 hours; under 0.5 million flat-subscription test tokens.

**Risk and scar family.** An over-simple estimator may remove context that a worker needs—family #3 semantic mismatch.

**Kill criterion.** Roll back automatic fresh selection if correction or rework rises by more than five percentage points over 50 comparable tasks.

**First PR.** New `scripts/dispatch_context_budget.py` and tests, ≤300 net lines. Read-only input produces a receipt with context mode, estimated inherited tokens, fan-out multiplier, and PASS/REJECT; it does not spawn agents.

### 3. Durable task journal with per-consumer cursors — score 1.80

**What.** Replace shared backlog reinjection with local append-only task transitions: `created`, `admitted`, `started`, `checkpointed`, `completed`, `failed`, `consumed`, `expired`. Each consumer owns a cursor; messages carry correlation ID, idempotency key, reply-to, expiry, and a compact artifact reference rather than repeated prose.

**Why it beats SOTA.** It imports Temporal’s event-history semantics without centralizing the organism or using a paid service. It also adds fleet-specific quota receipts and worktree/artifact identity. This exploits always-on local machines and the existing mailbox while respecting per-channel durability.

**Before/after metric.** Baseline: 94 unarchived messages, 45 queue-unstick messages, one PR paged 12 times, and approximately six million repeated tokens per 48 hours. Target: <600K repeated mailbox tokens per 48 hours, zero duplicate page delivery after acknowledgement, and 100% task-state recovery in 20 forced process-interruption tests.

**Cost and gear.** Gear 3 design, Gear 2 build; 16–24 hours; negligible LLM quota after schema review.

**Risk and scar family.** A journal that writers update but consumers ignore would reproduce family #2.

**Kill criterion.** Stop migration if any accepted message becomes unrecoverable or if cursor bookkeeping exceeds 10% of current mailbox processing time.

**First PR.** New `infra/fleet/mailbox-contract.v1.json` and a schema test, ≤250 net lines. It defines lifecycle and invariants only; no consumer migration.

### 4. Scar-calibrated shadow router — score 1.33

**What.** Populate `calibrations.v1.json` from dispatch receipts and outcomes: accepted artifact, correction count, elapsed time, reasoning tokens, quota consumed, machine, model, task profile, failure code, and gate result. Run a constrained contextual-bandit or simpler empirical policy in shadow mode before allowing automated routing.

**Why it beats SOTA.** RouteLLM learns from preferences, while MAST labels coordination failures. Nuzantara can combine both with its own unusually deep scar corpus and full review-to-prove-live lifecycle. The objective becomes expected accepted completion per scarce quota unit—not superficial answer preference.

**Before/after metric.** Baseline: zero calibration records; Sonnet handles 85.8% of Agent dispatches; cost per gear is unmeasurable. Target by day 60: ≥200 valid calibration records, ≥95% gear attribution, 25% lower reasoning tokens per accepted PR, and no statistically meaningful increase in correction rounds or gate failures.

**Cost and gear.** Gear 3; 24–40 hours; 1–2 million flat-subscription shadow-evaluation tokens.

**Risk and scar family.** Reward hacking, sparse cohorts, or routing to a cheap model that produces downstream rework—family #3.

**Kill criterion.** Do not arm if shadow recommendations lose more than two quality points against fixed routing or if any cohort has fewer than 30 comparable outcomes.

**First PR.** New `scripts/conductor_calibration_ingest.py`, schema validation for `infra/conductor/calibrations.v1.json`, and tests, ≤400 net lines. It ingests completed receipts only; no model choice.

### 5. Risk-triggered heterogeneous intelligence portfolio — score 1.20

**What.** Use one manager and single-threaded writes. Gear 1 gets no automatic council. Gear 2 may get one bounded specialist. Gear 3 requires at least one clean-context cross-family refuter or proposer, selected by capability and headroom, followed by one accountable synthesizer.

**Why it beats SOTA.** Mixture-of-Agents shows heterogeneous proposals can outperform repeated same-model samples, while Cognition shows coding writes should remain single-threaded. Nuzantara can selectively combine both and exploit six OAuth seats plus independent OpenAI, Google, Kimi, TP1, and local families—without paying per-token Anthropic API fees.

**Before/after metric.** Baseline: cross-family review in 5/20 evidence packs and roughly 3% of PRs; zero genuine Workflow use in the broader retro. Target: 100% cross-family participation on Gear-3 artifacts, ≤10% multi-agent use on Gear 1, and ≥20% more unique high-severity findings per million review tokens than homogeneous review.

**Cost and gear.** Gear 2 implementation; 8–14 hours; ongoing quota limited to Gear 3.

**Risk and scar family.** More coordination can amplify context and leak sensitive material across a non-local boundary; families #3 and #4. PII-local tasks remain excluded.

**Kill criterion.** Remove an additional proposer if its marginal accepted-finding yield stays below one finding per 250K tokens across 20 reviews.

**First PR.** Update `infra/workflows/verify-template.js` and its existing test area, ≤250 net lines, to require an explicit gear, family-diversity plan, context mode, and token ceiling before launch.

## 6. 90-day roadmap + first PRs

### Wave 1 — Days 0–30: make drift and cost visible

- Land topology/cascade conformance checking.
- Emit read-only context-budget and dispatch receipts.
- Add explicit failure codes aligned to quota dimension, host allocation, context mode, and MAST category.
- Establish the mailbox lifecycle schema.
- Publish metrics without changing routing.

### Wave 2 — Days 31–60: shadow the scheduler

- Warm and publish quota reports for every consented interactive account.
- Ingest at least 200 calibrated completions.
- Run the router in shadow mode and compare it with fixed workhorse-first routing.
- Enforce the ≤3 Pro start-rate limit independently of total PTY count.
- Add per-consumer mailbox cursors and duplicate-delivery tests.

### Wave 3 — Days 61–90: arm only proven decisions

- Arm topology-generated fallback ordering.
- Arm context admission if the correction-rate guard remains green.
- Enable calibrated routing only for cohorts with sufficient evidence.
- Require Gear-3 heterogeneous review while keeping writes single-threaded.
- Run interruption, stale-quota, exhausted-weekly-window, identity-unknown, and machine-unreachable drills.

| First PR | Files | Limit | Gear | Acceptance test |
|---|---|---:|---:|---|
| `fix(fleet): detect topology-cascade drift` | New `scripts/lint_fleet_routing.py`; focused test | ≤350 | 3 | Current snapshot fails with the slot-5/slot-6 and missing-seat findings; a corrected fixture passes. |
| `feat(conductor): emit context-budget receipts` | New `scripts/dispatch_context_budget.py`; focused test | ≤300 | 2 | Five 90K forks are rejected; five independent fresh lanes pass subject to quota and host caps. |
| `feat(fleet): define durable mailbox lifecycle` | New `infra/fleet/mailbox-contract.v1.json`; schema test | ≤250 | 3 | Duplicate idempotency keys and acknowledgement without prior delivery fail validation. |
| `feat(conductor): ingest outcome calibrations` | New `scripts/conductor_calibration_ingest.py`; `infra/conductor/calibrations.v1.json`; test | ≤400 | 3 | Invalid gear, unknown profile, missing outcome, or PII-bearing free text is rejected. |
| `feat(workflow): require bounded diversity plan` | `infra/workflows/verify-template.js`; existing workflow tests | ≤250 | 2 | Gear 3 without an eligible second family fails preflight; Gear 1 fan-out above one fails. |

## 7. Needs-ruling

1. **Interactive credential ceremony.** Zero must consent to logging each of the six Claude accounts into distinct interactive profiles on Pro and approving an opaque A1–A5/AZ mapping. Tokens alone cannot establish identity. No account names or credentials should enter repository artifacts.

2. **Quota reserve policy.** Zero must choose the protected reserve for final gates and urgent work—for example, whether dispatch should stop ordinary work at 20% remaining weekly capacity, 20% remaining five-hour capacity, or the stricter of the two. This is a business-priority allocation, not an engineering inference.

3. **TP1 billing ambiguity.** Before TP1 becomes a load-bearing workhorse, Zero must confirm which currently reachable models are covered by the subscription and which could generate per-token charges.

4. **Team-seat priority.** The topology says Team is last, but its desired role during MAX exhaustion is a commercial capacity decision. The compiler should preserve the existing order until Zero rules otherwise.

Fable’s manual-only status is already ruled and should not be reopened by the scheduler.

## 8. §Meta-pattern

The single defective belief is: **a fleet becomes orchestrated once its models, roles, and fallbacks are documented.**

That belief generates every major defect here. A profile is mistaken for a measured capability; a valid token for an identified seat; a cascade for capacity-aware routing; a mailbox for durable coordination; more panes for more throughput; and more reasoning tokens for higher quality. The organism has accumulated an exceptional cognitive arsenal, but its dispatch path still behaves as if cognition were free and resources were interchangeable.

The beyond-SOTA move is to treat intelligence as a typed, scarce, failure-prone resource. Every launch must be admitted, every transition journaled, every outcome calibrated, and every extra agent justified by marginal accepted value.

## 9. Sources

1. [Anthropic — “How we built our multi-agent research system”](https://www.anthropic.com/engineering/multi-agent-research-system), 2025-06-13; accessed 2026-08-29. Primary engineering account with architecture and internal evaluation results.
2. [Anthropic — “Create custom subagents”](https://code.claude.com/docs/en/sub-agents), continuously updated; accessed 2026-08-29. Official definition of fresh, forked, parallel, and resumed Claude Code subagents.
3. [OpenAI — “Agent orchestration”](https://openai.github.io/openai-agents-python/multi_agent/), continuously updated; accessed 2026-08-29. Official manager, handoff, and code-orchestration contracts.
4. [Google — “Announcing the Agent2Agent Protocol”](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/), 2025-04-09; accessed 2026-08-29. Primary A2A protocol announcement and design principles.
5. [Wang et al. — “Why Do Multi-Agent LLM Systems Fail?”](https://arxiv.org/abs/2503.13657), 2025-03-17; accessed 2026-08-29. Primary MAST paper and empirical failure taxonomy.
6. [Ong et al. — “RouteLLM: Learning to Route LLMs with Preference Data”](https://arxiv.org/abs/2406.18665), 2024-06-26, revised 2025-02-23; accessed 2026-08-29. Primary learned-routing research and cost-quality evaluation.
7. [Chen, Zaharia, and Zou — “FrugalGPT”](https://arxiv.org/abs/2305.05176), 2023-05-09; accessed 2026-08-29. Primary learned-cascade research.
8. [Temporal — Platform documentation](https://docs.temporal.io/), continuously updated; accessed 2026-08-29. Authoritative durable-execution and replay contract.
9. [Cognition — “Multi-Agents: What’s Actually Working”](https://cognition.com/blog/multi-agents-working), 2026-04-22; accessed 2026-08-29. Primary production account of manager/worker coding-agent coordination.
10. [Wang et al. — “Mixture-of-Agents Enhances Large Language Model Capabilities”](https://arxiv.org/abs/2406.04692), 2024-06-07; accessed 2026-08-29. Primary heterogeneous-agent aggregation study.