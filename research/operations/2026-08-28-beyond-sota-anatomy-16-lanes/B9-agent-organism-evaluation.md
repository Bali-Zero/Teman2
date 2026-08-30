---
date: 2026-08-28
domain: operations
part: B9 agent-organism-evaluation
scope: cell-core biology framework, mata-garuda, organism/evaluator/autonomous-lab/remediator, backend agent services, A1-A4 self-healing rings — anatomy, SOTA benchmark, gap table, recommendations
sources:
  - https://www.anthropic.com/research/building-effective-agents
  - https://arxiv.org/abs/2406.12045
  - https://sierra.ai/blog/tau-bench-shaping-development-evaluation-agents
  - https://arxiv.org/pdf/2506.07982
  - https://hal.cs.princeton.edu/
  - https://github.com/princeton-pli/hal-harness
  - https://arxiv.org/html/2604.23178
  - https://openai.github.io/openai-agents-python/
  - https://openai.github.io/openai-agents-python/tracing/
  - https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows
  - https://aws.amazon.com/blogs/database/build-durable-ai-agents-with-langgraph-and-amazon-dynamodb/
  - https://arxiv.org/abs/2310.10501
  - https://guardrailsai.com/blog/nemoguardrails-integration
  - https://www.marktechpost.com/2026/08/09/top-llm-observability-and-evaluation-platforms-in-2026-langfuse-langsmith-braintrust-arize-and-more-compared/
  - https://www.braintrust.dev/articles/langsmith-alternatives-2026
  - https://temporal.io/blog/durable-execution-meets-ai-why-temporal-is-the-perfect-foundation-for-ai
  - https://www.letta.com/blog/agent-memory/
  - https://dev.to/agentsindex/ag2-vs-crewai-the-complete-comparison-including-the-autogen-rebrand-explained-248l
status: DONE 2026-08-29
adversarial_review: kimi-k3
---

> ## ⚠️ Read this before acting on anything below
>
> **These findings are pinned to `11a3c89a2e` (2026-08-28). `origin/main` was 123 commits ahead
> when this file was published on 2026-08-30.** A verdict in here is a **LEAD, not a fact**: it
> was true of a tree that no longer exists. Re-measure before you build on it.
>
> **Defects presented below as current that were already CURED before publication** — each fix
> verified as a descendant of the pin with `git merge-base --is-ancestor 11a3c89a2e <sha>`:
>
> | Presented as a live defect | Actually cured by | Verified |
> |---|---|---|
> | R9 harness time-bomb dated 2026-09-02 (X1) | #5190 | ancestor check |
> | Phantom DeepSeek voter (B8) | #5211 / #5207 (`cc82ed62e4`, `0cccbbc925`) | ancestor check |
> | Auth split-brain across the portals (F3, F4) | #5181 (`d6556a75bf`) | ancestor check |
> | Magic-link `result_id` ownership — which F2 calls "replay-safe" (F2) | #5298 (`3861567e52`) | ancestor check |
> | Meta webhook signature unenforced in prod (B3) | fail-closed by default since 2026-08-26; `WHATSAPP_APP_SECRET` deployed | live probe: unsigned `POST /webhook/whatsapp` → **401 `Invalid signature`** (2026-08-30) |
>
> **Counts that were re-measured and found WRONG** (they were not corrected in the text, so that
> the reports stay the artefact the panel actually produced rather than a quietly-improved one):
> `X3:31` reads 10 directories + 6 symlinks, measured 11 + 5. `X3:45` reads 162 `@mcp.tool`,
> measured 153. Other counts flagged by the review but NOT settled either way are listed in this
> PR's evidence pack under `dissent`, marked PLAUSIBLE — treat every number in these files as
> unverified unless you have just re-run it.
>
> **Known internal contradiction, left standing:** `B4` states that OCR of identity documents
> never leaves the machine, and then, two paragraphs later, that OCR'd passport/NPWP/akta text is
> shipped to Gemini by CRM-Guardian. The second statement is the accurate one. It is ledgered.
>
> **Two things were withheld from this publication rather than edited quietly:** the panel's own
> mandate file (self-labelled `IN-PROGRESS` / `internal`), and the location of a live DNS-write
> credential named in `B5`. Both omissions are declared here because a silently-sanitised audit is
> worth less than an audit that says what it removed.
>
> The reports' own thesis is that a written artefact gets presumed to be in force. This header
> exists because that thesis applies, first, to the reports themselves.


# B9 — Agent Organism & Evaluation

## Anatomy (as measured)

All measurements taken on the pinned worktree at `origin/main` `11a3c89a2e`. Line counts are `wc -l` over `*.py` excluding `.venv`/`node_modules`.

### The in-product agent runtimes that actually exist

**`packages/cell-core` — the organ contract (79 files, 13,257 lines).** A clean, Protocol-based agent contract: `cell_core/protocols.py:15-60` defines `Sensor` (perceive), `Thinker` (reason over readings + homeostatic state + memory), `Actor` (execute with `can_execute` capability check), and three memory tiers — `STMStore` (TTL volatile), `LTMStore` (learned rules with `condense`), `EpisodicStore` (ACT-R-style activation recall). `cell_core/lifecycle.py:16-31` implements a biological maturation gate: five phases (EMBRIONE day 0-3 observe-only → NEONATO confidence ≥0.8 → GIOVANE ≥0.5 + dreams → ADULTO full autonomy → ANZIANO stability-priority), each mapping to a minimum-confidence threshold for autonomous action. Also present: `hgt/` + `hgt_coordinator/` (horizontal gene transfer — cross-cell rule propagation with proposal + audit-log), `metabolic/` (collector/trend), `observability/` (Prometheus-compatible exporter, cardinality guard), `genome.py` (SQLite trajectory store).

**`apps/cell` — the running organism (112 files, 19,960 lines).** A dual-process architecture: `cell/fast/` is System-1 (homeostatic_controller, cost_guard, health_triage, log_anomaly, mutation_filter, trend_detector), `cell/slow/reasoner.py` is System-2, and `cell/cortex/` holds the self-improvement organs — `curiosity_engine.py`, `goal_generator.py`, `strategy_mutator.py`, `critic.py`, and `skill_library.py`, whose docstring describes an "evolvable procedure store with fitness-weighted recall" where skills are "discovered, tested, promoted, and eventually apoptose" (`skill_library.py:1-7`) — a Voyager-style library with a pruning mechanism Voyager itself lacks. It is live-wired: three LaunchAgents (`infra/launchagents/com.nuzantara.cell-observatory{,-prune,-selfcheck}.plist`) and a registered organ `cell.organism` at `apps/organism/organism/organs_registry.yaml:312`.

**`apps/organism` — the self-healing supervisor (101 files, 10,981 lines).** Event bus + stateless supervisor + idempotent actuators (`organism/actuators/`: fly_machines_restart, fly_machines_start, python_env_repair, restart_agent, adopt_module, consolidate_redundancy). Its SSOT is `organism/organs_registry.yaml`: **170 organs** (`grep -c "^- id:"`), each with runtime, expected heartbeat, dependencies, a named `recovery_action`, and `severity_on_silence` — the whole file protected by a SHA256 checksum (line 3) enforced by a pre-commit validator. This is the concrete implementation of the A1-A4 "self-healing rings".

**`apps/evaluator` — the evaluation estate (153 files, 46,935 lines).** The largest app in scope, and the most heterogeneous:
- `rag_eval/` — the real gem. Two harnesses (`rag_eval/README.md`): `rag_eval.py` + `golden_set.json` (**13 verified Q&A pairs**, single-turn, recall@k + must_contain + optional LLM judge) and `multi_turn_eval.py` + `multi_turn_golden.json` (**11 scenarios**) that targets `/api/agentic-rag/query` — *the live WhatsApp bot's actual endpoint* — and grades a four-outcome gate (SEND/CLARIFY/ABSTAIN/ESCALATE) plus key-fact coverage.
- `judgement_day.py` — RAGAS (faithfulness, answer_relevancy) with Gemini as judge over **3 hardcoded questions** (`judgement_day.py:33-38`).
- `red_team_evaluator.py` — adversarial harness with 5 attack categories (router confusion, infinite loop, prompt injection, evidence manipulation, policy bypass; `red_team_evaluator.py:5-11`).
- `core_guardian/` — scout/surgeon/watchdog/rollback_engine/risk_scorer/regression_monitor + `cron_guardian.py`, `cron_ragas.py`, `cron_red_team.py`.
- Scope creep: `seo_cell/`, `gsc_coverage_monitor.py`, `apply_seo_gaps.ts`, indexing-sweep JSON snapshots — SEO operations living inside "evaluator".

**Critical wiring fact:** a grep for `rag_eval|judgement_day|red_team_evaluator|zantara_fleet_check` across `.github/workflows/` and `infra/launchagents/` returns **zero hits**. The evaluation harnesses — including the only multi-turn eval of the live bot — run only when a human remembers to run them. This is the repo's own scar family #2 ("Esiste ≠ Armato") applied to its own evaluation layer.

**`apps/mata-garuda` — OSINT hub with a Lamarckian meta-agent (291 files, 42,309 lines).** Per its README: a 5-layer intelligence pipeline plus a meta-agent layer where "every failure becomes a rule, every rule a GENOME.md mutation, validated with fitness metrics and auto-revertible". The README still says "Stato: Sprint 1 — walking skeleton" while the tree holds 42K lines across cells/tools/domains/security/bridge/runtime/agents/foundations/api/workers — the self-description is badly stale. Historical scar: 2026-05-07 active-active split-brain (12+1 concurrent instances, superscar family #10).

**`apps/graph-engine` — LangGraph reasoning engine (101 files, 14,364 lines).** `src/nuzantara_graph/` with an understand→retrieve→reason→synthesize node pipeline, a `graph/checkpointer.py`, and a router. It has real non-test callers: `apps/backend-rag/backend/services/rag/grading/base.py`, `scripts/kg_propose.py`, `scripts/gap_fill_autonomous.py`. This is the one place the repo already uses the sector-standard framework (LangGraph) rather than a bespoke loop.

**`apps/remediator` — one file (220 lines).** `main.py`: Redis subscriber + SQLite `remediation_attempts` log. Minimal but coherent; overlaps in role with `apps/organism`'s actuators.

**`apps/autonomous-lab` — a frontend without its backend switch flipped.** The app directory contains **zero Python files** — it is a Next.js UI (`app/`, `components/`, `next.config.mjs`). The actual lab is `apps/backend-rag/backend/services/autonomous_lab/` (**7,980 lines, 21 modules**): `sandbox_policy.py` (network `DENY_ALL`/`ALLOWLIST_ONLY`, filesystem `WORKTREE_ONLY` modes, versioned policy id `autonomous-lab-v1-sandbox-policy`), `receipt_safety.py` (secret-redaction of evidence), `shadow_run.py`, `planner.py`/`reviewer.py`/`orchestrator.py` ("deterministic, side-effect-free orchestration" per its own docstring). It is dark by default: `autonomous_lab_enabled: bool = Field(default=False)` at `apps/backend-rag/backend/app/core/config.py:970`, consumed by conditional router registration at `app/setup/router_manifest.py:71-75,128-131`.

### Backend agent services (the product-facing runtime)

- **`services/agents` (1,315 lines) — the authorization chokepoint.** `tool_authorizer.py` is server-side RBAC for the agentic ReAct loop: default-deny via `team_agent_config.is_tool_allowed`, blocked-tool enforcement, audit logging on every allow AND deny, invoked from the single chokepoint `tool_executor.execute_tool` (`tool_authorizer.py:1-20`). Its docstring honestly documents a known two-source-of-truth situation with `crm_utils` admin lists (`tool_authorizer.py:33-41`). `confirmation_service.py` implements human-approval gates: Redis-persisted `conf:{uuid}` with 180s TTL, `asyncio.Future` local fast path plus Redis pub/sub cross-process wakeup, **fail-closed** on Redis-down and on timeout, SSE `confirmation_required` event to the frontend (`confirmation_service.py:1-32`).
- **`services/olympus` (1,868 lines) — DB guardian, not a pantheon.** Heartbeat + Pulse + RulesEngine + Alerts wired by `guardian.py`, which closes a feedback loop — `record_applied()` on rule-governed success, `lower_confidence()` on failure — and treats `asyncpg.InterfaceError` as a circuit-breaker trip (W64 scar, `guardian.py:29-33`). Exposed only as an internal admin router (`router_manifest.py:325`).
- **`services/autonomous_agents` (868 lines)** — `knowledge_graph_builder.py`, with real callers (routers `agents.py` and `autonomous_agents.py`, `services/tools/knowledge_graph_tool.py`, the agentic RAG package). The `autonomous_agents.py` router (875 lines) exposes run-on-demand agents (conversation-trainer, client-value-predictor, knowledge-graph-builder) plus an execution log and scheduler enable/disable endpoints (`autonomous_agents.py:120-845`).
- **`services/cognitive` (3,754 lines)** — oracle/strategos/anomaly-detector with delivery + CLI modules. Despite the name, it is the WR2 editorial-intel layer; it IS cron-wired (`infra/launchagents/com.balizero.wr2.{oracle,strategos,connector}.plist`).
- **`services/sota_loop` (951 lines)** — the M13 Instagram-metrics loop (collect 6h / weekly / monthly / checkpoint; module docstring). The name says SOTA; the code is social-media KPI plumbing.
- **`services/experience` (239) + `services/skill` (346) + `services/skill_coach` (432)** — thin trajectory/skill-catalog wrappers over `cell_core.genome.Genome` with graceful degradation (`experience/service.py:1-8`). Router manifest line 6 records their scar: "/api/experience, /api/skill, /api/metabolic silently 404'd in prod" (registration had been forgotten — family #2 again).
- **`services/learner` (984) + `services/measurer` (2,015)** — the WR2 learning loop (genome_adapter, injection_builder, score_calculator; IG Graph sensors, token watchdog, UTM attribution). Wired: `com.balizero.wr2.learner-nightly.plist`; measurer boots from `app/setup/app_factory.py`.
- **`services/federation` — does not exist.** The `federation.py` router (193 lines) is a Postgres-backed inter-node message bus whose `VALID_NODES = {"pro", "air", "krisna", "damar", "all"}` (`federation.py:24`) still includes `air`, decommissioned 2026-05-05. The real federation logic lives in `scripts/federation_orchestrator.py`, outside the service tree.
- **`dream.py` router (177 lines)** — the "Dream Thinking Room": an admin-gated inspiration/moodboard CRUD with LLM generation borrowed from `article_composer` ("Ideally we should move it to a shared LLM service", `dream.py:17-19`). It is a UI feature, not a dreaming subsystem.
- **Router registration** is declarative and honest: `app/setup/router_manifest.py` (540 lines) + `router_registration.py` (1,032 lines) define `RouterEntry` rows with process-groups, conditions and scar-tagged rationale — born from the silent-404 scar documented on its own line 6.

### Honest caller-count verdicts

| Component | Non-test callers | Verdict |
|---|---|---|
| `tool_authorizer` / `confirmation_service` | agentic tool_executor chokepoint | **Live, load-bearing** |
| `organism` registry + actuators | 170 organs, pre-commit hook, watchdog plists | **Live, load-bearing** |
| `graph-engine` | rag/grading, kg_propose, gap_fill | Live |
| `cognitive`, `learner`, `measurer`, `sota_loop` | WR2 plists + app_factory | Live (cron) |
| `experience`, `skill`, `skill_coach` | 1 router + 1-2 seed/backfill scripts each | Wired but **thin traffic** |
| `autonomous_lab` (backend) | router gated by default-False flag | **Built, dark** — "costruito ≠ attivato" |
| `evaluator` harnesses | zero CI/cron references | **Dead switch** — highest-value unwired asset in scope |
| `remediator` | standalone daemon | Redundant with organism actuators |
| `federation` router | JWT'd nodes incl. decommissioned `air` | Stale contract |

## Honest state vs. SOTA

**At or above sector practice.** Three things here are genuinely strong by 2026 production standards. (1) The **authorization chokepoint**: server-side default-deny tool RBAC with audit on both allow and deny, at a single enforcement point, is precisely what OpenAI's Agents SDK guardrails and the NeMo "tool-call validation" pattern prescribe — and it is *live*, not aspirational. (2) The **fail-closed human confirmation gate** (Redis + Future + pub/sub, SSE to a modal) is the human-in-the-loop suspend/resume pattern Temporal markets as its flagship AI capability, implemented at appropriate scale for one operator. (3) The **organs registry** — 170 organs, each with heartbeat expectation, dependency list, named recovery action, and checksummed SSOT — is a self-healing inventory most funded platform teams do not have.

**At parity in ideas, bespoke in execution.** The cell-core memory tiers (STM/LTM/Episodic) map almost one-to-one onto Letta/MemGPT's core/recall/archival tiers; the cortex skill library is Voyager with apoptosis added; WR2/WR3 run real Reflexion crons. The organism has independently converged on the published research — but as bespoke code whose *effectiveness is unmeasured*: nothing reports whether episodic recall ever changed a decision, or how many skills were promoted vs apoptosed.

**Below sector practice.** Evaluation and observability. The eval assets exist (13 + 11 + 3 golden cases, a five-category red-team harness, RAGAS integration) but are **entirely unwired** — no CI gate, no cron, no trend line, no pass^k, no cost accounting. There is no trace-first observability: no Langfuse/LangSmith-class store where an agentic request's tool-call spans, cost, and outcome live together; the evidence is scattered across Python logs, SQLite files, and Telegram alerts. And naming inflation ("dream", "olympus", "cognitive", "sota_loop") imposes a real discovery tax: an auditor must read the code to learn that "sota_loop" is Instagram KPIs.

## Deep research: the world's best

**Orchestration frameworks.** The sector consolidated on a small set of production frameworks: **LangGraph** (stateful graphs, first-class checkpointing/threads, time-travel debugging, human-in-the-loop interrupts — see the [LangGraph + DynamoDB durable-agents pattern](https://aws.amazon.com/blogs/database/build-durable-ai-agents-with-langgraph-and-amazon-dynamodb/)) and **CrewAI** are the two most deployed; CrewAI shows ~1.3M monthly PyPI installs vs ~100K for AG2, the community fork of AutoGen ([AG2 vs CrewAI](https://dev.to/agentsindex/ag2-vs-crewai-the-complete-comparison-including-the-autogen-rebrand-explained-248l)). The **OpenAI Agents SDK** distilled the runtime contract to four primitives — agents, handoffs, guardrails, sessions — with [tracing enabled by default](https://openai.github.io/openai-agents-python/tracing/) capturing generations, tool calls, handoffs and guardrail triggers per run. **Anthropic's [Building Effective Agents](https://www.anthropic.com/research/building-effective-agents)** remains the doctrinal anchor: the most successful implementations use "simple, composable patterns" (prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer) rather than heavy frameworks — a direct endorsement of Nuzantara's chokepoint-plus-plain-loop shape, and a warning against its bespoke sprawl.

**Durable execution.** The important critique ([Diagrid: checkpoints are not durable execution](https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows)) is that framework checkpointing is fault *recovery*, not fault *prevention*: someone must detect the failure, trigger the resume, and dedupe side effects. [Temporal's model](https://temporal.io/blog/durable-execution-meets-ai-why-temporal-is-the-perfect-foundation-for-ai) — activities executed exactly-once with stored results, retries under declared policy, human approval as a first-class suspend/resume that survives restarts — is the reference bar for agents whose actions have side effects.

**Agent evaluation.** **[τ-bench](https://arxiv.org/abs/2406.12045)** (Sierra) is the sector's reliability wake-up call: agents graded on *database end-state* against simulated users, with the **pass^k** metric ("all k trials succeed", vs pass@k's "at least one") exposing that even top function-calling agents scored <50% task success and pass^8 <25% in retail; [Anthropic's own model cards now report pass^k](https://sierra.ai/blog/tau-bench-shaping-development-evaluation-agents). [τ²-bench](https://arxiv.org/pdf/2506.07982) extends this to dual-control conversations where the user also acts. Princeton's **[Holistic Agent Leaderboard](https://hal.cs.princeton.edu/)** ([harness](https://github.com/princeton-pli/hal-harness), ICLR 2026) sets the harness standard: one command, nine benchmarks, **cost-controlled by default** — every score published next to its dollar cost, with token usage and full traces logged. The methodological lesson for any in-house eval: measure outcome-state not transcript vibes, report cost beside accuracy, and run k trials.

**LLM-as-judge calibration.** The systematic-evaluation literature ([Judging the Judges](https://arxiv.org/html/2604.23178)) quantifies position bias at 10-15 percentage points and verbosity bias as model-family-dependent, and finds the effective mitigations are position swapping with tie-on-inconsistency, separating correctness from style, forcing chain-of-thought rationale before verdict, and multi-judge ensembles. An uncalibrated single judge is a coin with unknown weighting.

**Guardrails frameworks.** [NeMo Guardrails](https://arxiv.org/abs/2310.10501) contributes *programmable rails* — declarative, LLM-independent, interpretable dialogue/tool rails, including pre/post tool-call validation; [Guardrails AI](https://guardrailsai.com/blog/nemoguardrails-integration) contributes a hub of reusable I/O validators (toxicity, PII scrubbing) that compose with rails. The engineering pattern: validation as *declared configuration at a chokepoint*, not scattered if-statements.

**Observability.** The 2026 platform comparison ([MarkTechPost survey](https://www.marktechpost.com/2026/08/09/top-llm-observability-and-evaluation-platforms-in-2026-langfuse-langsmith-braintrust-arize-and-more-compared/), [Braintrust's own positioning](https://www.braintrust.dev/articles/langsmith-alternatives-2026)) converges on: the **trace is the primary object** (nested spans across agent/retriever/tool with scores attached to production traffic); **Langfuse** is the standard self-hostable option (relevant under Law 6 sovereignty); **Braintrust**'s distinctive move is eval-as-deploy-gate — block the ship when scores regress. Survey data in the same cluster: ~52% of orgs run offline evals, ~37% online evals — running *neither* on an LLM product is now behind the median.

**Memory and self-improvement.** [Letta/MemGPT](https://www.letta.com/blog/agent-memory/) formalized the three-tier memory model (core in-context, recall, archival) that cell-core mirrors; Voyager's skill library and Reflexion's verbal self-critique are the canonical self-improvement loops — both already present here in `cortex/` and the WR2/WR3 reflexion crons. The frontier concern is *verification* of self-improvement: fitness metrics and auto-revert (which mata-garuda's Lamarckian design and the cortex apoptosis mechanic already sketch) are ahead of most published practice — if they were measured.

## Gap table

| Dimension | Nuzantara today (measured) | SOTA reference | Gap |
|---|---|---|---|
| Tool authorization | Default-deny RBAC + dual audit at one chokepoint (live) | OpenAI SDK guardrails; NeMo tool-rails | **None** — at/above |
| Human-approval gates | Fail-closed Redis confirmation, SSE modal (live) | Temporal HITL suspend/resume | Small: no durable resume after process death |
| Self-healing inventory | 170-organ checksummed registry + idempotent actuators | Bespoke SRE runbooks at best | **Ahead** of typical practice |
| Sandboxing for autonomous work | Versioned DENY_ALL policy, receipt redaction — **dark** (flag False) | E2B/containerized sandboxes, armed | Built ≠ armed |
| Outcome evaluation | 13+11 golden cases, four-outcome gate — **zero CI/cron wiring** | τ-bench pass^k; HAL cost-controlled harness | **Largest gap** |
| Eval-as-deploy-gate | None | Braintrust block-on-regression | Missing |
| LLM-as-judge calibration | Optional judge, no bias mitigation | Position-swap, CoT-first, ensembles | Missing |
| Observability | Logs + SQLite + Telegram, no unified traces | Langfuse/LangSmith trace-first | Missing |
| Cost accounting per agent run | llm_burn_alarm organ (aggregate) | HAL per-task $ beside score | Partial |
| Orchestration framework | Bespoke loops; LangGraph only in graph-engine | LangGraph/CrewAI consolidated | Partial, fragmented |
| Memory tiers | STM/LTM/Episodic ≈ Letta, SQLite-backed | Letta core/recall/archival | Parity in design, unmeasured in effect |
| Skill library / self-improvement | Voyager+apoptosis, Reflexion crons, Lamarckian genome | Voyager/Reflexion/ExpeL | Parity-to-ahead in design, unmeasured |
| Naming honesty | dream/olympus/cognitive/sota_loop misdescribe contents | Boring names, discoverable | Self-inflicted tax |
| Duplication | remediator vs organism; federation stale nodes; SEO in evaluator | One owner per concern | Cleanup debt |

## Recommendations — reach SOTA

Sized for one operator plus an agent fleet; each has a falsifiable acceptance metric.

1. **P0 — Arm the multi-turn eval as a nightly organ and a merge gate for the bot lane.** Register `multi_turn_eval.py` in `organs_registry.yaml` with a heartbeat, run it nightly against the live endpoint (read-only scenarios), and add a CI job that runs it on every PR touching `services/rag/agentic/` or `whatsapp` surfaces. Report **pass^4** per scenario, not single-run pass. *Acceptance: a deliberately-broken abstain threshold on a test branch turns the gate red; nightly JSON artifacts exist for 7 consecutive days; a pass^4 baseline number is recorded in the report.*
2. **P0 — Grow the golden set from 13/11 to ≥50/25 using real traffic.** Source from PII-scrubbed WA conversations (client_id placeholders per Law 2), stratified across the four outcome classes and the visa/tax/kbli/pricing domains whose abstain thresholds already diverge by design. *Acceptance: ≥50 single-turn pairs + ≥25 multi-turn scenarios, every outcome class ≥5 cases, provenance field on each.*
3. **P0 — Stand up self-hosted Langfuse (or OTel + Postgres) as the trace store for the agentic loop.** Free, self-hostable on Pro/Mini, satisfies Law 6. Instrument `tool_executor.execute_tool` and the orchestrator so every agentic request emits one trace with tool-call spans, authorizer decisions, cost, latency, and final outcome class. *Acceptance: 100% of `/api/agentic-rag/query` requests produce a queryable trace; one dashboard shows p50/p95 latency, $/request, and outcome distribution over 7 days.*
4. **P1 — Calibrate every LLM judge.** For `rag_eval`'s optional judge and the WR2/WR3 critics: position-swap with tie-on-inconsistency for pairwise judgments, rationale-before-verdict, and a 20-case human-labeled agreement check. *Acceptance: judge-vs-Zero agreement ≥85% on the labeled subset, documented; the swap harness exists as a test.*
5. **P1 — One owner per concern: fold `apps/remediator` into an organism actuator; move `seo_cell` and the GSC/indexing scripts out of `apps/evaluator`; fix `federation.py` VALID_NODES (drop `air`) or retire the router if traffic is zero.** *Acceptance: `apps/remediator` deleted with its behavior covered by an actuator test; `apps/evaluator` contains only evaluation; a measured request count justifies federation's keep-or-kill.*
6. **P1 — Decide autonomous_lab: arm dark or archive.** If armed: flip the flag in a staging process group, and prove the sandbox by a test that attempts network egress from inside a `DENY_ALL` run and asserts failure. If not: move the Next.js shell to `.disabled-*` per house convention. *Acceptance: either one end-to-end shadow_run with receipts on disk, or the directory renamed.*
7. **P2 — Report cost beside every eval score (HAL discipline).** The `llm_burn_alarm` organ already tracks `llm_cost_events`; join eval runs to it. *Acceptance: nightly eval artifact includes tokens and $ per scenario.*
8. **P2 — Consolidate new agent loops on graph-engine/LangGraph.** No new bespoke ReAct loop; new lanes use `nuzantara_graph` with its checkpointer. *Acceptance: the next agent feature PR imports `nuzantara_graph`; a lint or review rule names the prohibition.*

## Recommendations — beyond SOTA

1. **Registry-driven eval coverage (the organism audits its own mirror).** Extend `organs_registry.yaml` with an `eval_ref` field: every organ whose `owner_module` invokes an LLM must name its eval harness and last-green timestamp; the pre-commit validator (already checksummed and enforced) fails when an LLM-bearing organ has none. No published framework ties a *self-healing inventory* to *eval coverage*. *Acceptance: CI red on adding an LLM organ without eval_ref; coverage ratio (LLM organs with green eval / total) published weekly.* P1.
2. **Evidence-earned maturation.** `cell_core/lifecycle.py` currently advances phases by *age in days*. Make phase advancement earned: EMBRIONE→NEONATO requires a first green eval; GIOVANE→ADULTO requires pass^4 ≥ threshold on the organ's harness; any regression auto-demotes one phase (lowering the autonomy confidence floor). This turns the biological metaphor into a real safety mechanism nobody in the sector has: **autonomy as a function of measured reliability, not uptime**. *Acceptance: a forced eval regression on a test cell demotes it within one cycle; the demotion appears in the pulse log.* P1.
3. **Cicatrix-to-eval pipeline.** Every new W-scar whose surface is an LLM behavior auto-generates a regression case in the red-team or golden set (the five red-team categories are the taxonomy). The scar archive becomes a growing adversarial benchmark — a τ-bench built from the organism's own pathology, which is exactly the data public benchmarks lack. *Acceptance: ≥10 scars mapped to runnable cases; the mapping is a lintable table.* P2.
4. **Cross-family judge ensemble at flat cost.** The arsenal already holds flat-subscription seats across four model families (Claude, GPT, Gemini, Kimi) — most shops cannot afford ensemble judging; here it is marginal-cost-zero. Three-judge ensemble on eval verdicts, disagreement >1 outcome class → human review queue. This directly implements the ensemble mitigation the bias literature recommends, at a price only this architecture gets. *Acceptance: ensemble verdict + disagreement rate in nightly artifact; disagreement cases land in a queue Zero can read.* P2.
5. **Fitness-gated HGT.** `hgt_coordinator` already has proposal + audit-log; mata-garuda already declares auto-revertible GENOME mutations. Close the loop: a propagated rule/mutation carries the eval delta that justified it, and auto-reverts if the receiving cell's pass^k drops within N cycles. This is the safe, measured version of "agents improving agents" — the A4 safety primitive the repo itself correctly says must precede RSI. *Acceptance: one full propagate→measure→(revert|keep) cycle logged end-to-end.* P2.

## §Meta-pattern

**The organism built the muscles but not the mirror.** Everything that *acts* — authorizer, confirmation gates, actuators, sandbox policy — is genuinely strong and mostly live; everything that would *measure whether the acting is any good* — golden sets, red-team harness, RAGAS, fleet check — exists as code but is wired to nothing. This is superscar family #2 (Esiste ≠ Armato) expressed at the architecture level, and the same meta-disease the 28/8 engineering-craft panel named: "the artifact written/armed/announced is treated as the thing in force". Aspirational naming (dream, olympus, cognitive, sota_loop) is the linguistic symptom of the same disease — the name announces a capability the code does not hold. The single highest-leverage move in this whole report is not building anything new: it is connecting the already-written evaluation estate to CI, cron, and the organs registry, so the organism's claimed reliability becomes a number that can go red.

## §Solo-operatore

Decisions only Zero can take:

1. **Does a red eval block the bot lane?** Recommendation 1 makes bot-quality regressions un-mergeable; that trades shipping velocity for answer reliability on a client-facing surface. Business call (Legge 5).
2. **autonomous_lab: arm or archive.** Flipping `AUTONOMOUS_LAB_ENABLED` in any live process group is an autonomy-expansion decision with risk appetite attached; archiving 8K lines is a sunk-cost acceptance. Either is fine technically; the choice is his.
3. **mata-garuda's future.** 42K lines, Zero-exclusive by charter, README two sprints stale, one split-brain scar. Invest (bring under the same eval discipline), freeze, or shrink — an owner-level portfolio decision.
4. **Eval data provenance.** Growing golden sets from real WA conversations, even PII-scrubbed to client_id placeholders, is a data-use decision under Law 2 that Zero should ratify explicitly before the set is committed to the public repo (recommendation: keep golden sets with real-traffic provenance in a private store, only synthetic ones in-repo).
5. **Judge-ensemble seat usage.** The cross-family ensemble (beyond-SOTA #4) runs eval transcripts through Gemini/Kimi/GPT seats; vendor parity was RULED 2026-08-24, but eval transcripts derived from client conversations still need his content-level ok.
6. **Observability spend.** Langfuse self-hosted is $0 in licenses but not $0 in operator attention (one more daemon on Pro/Mini in the 170-organ registry). Worth it in this report's judgment — but it is his machine budget.

## Sources

1. Anthropic — Building Effective Agents: https://www.anthropic.com/research/building-effective-agents
2. τ-bench (Sierra), arXiv 2406.12045: https://arxiv.org/abs/2406.12045 — and Sierra's account of pass^k adoption: https://sierra.ai/blog/tau-bench-shaping-development-evaluation-agents
3. τ²-bench, arXiv 2506.07982: https://arxiv.org/pdf/2506.07982
4. Holistic Agent Leaderboard (Princeton SAgE, ICLR 2026): https://hal.cs.princeton.edu/ — harness: https://github.com/princeton-pli/hal-harness
5. Judging the Judges: bias mitigation in LLM-as-judge pipelines, arXiv 2604.23178: https://arxiv.org/html/2604.23178
6. OpenAI Agents SDK — primitives and tracing: https://openai.github.io/openai-agents-python/ · https://openai.github.io/openai-agents-python/tracing/
7. Diagrid — Checkpoints are not durable execution: https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows
8. AWS — Durable AI agents with LangGraph + DynamoDB: https://aws.amazon.com/blogs/database/build-durable-ai-agents-with-langgraph-and-amazon-dynamodb/
9. NeMo Guardrails, arXiv 2310.10501: https://arxiv.org/abs/2310.10501 — Guardrails AI integration: https://guardrailsai.com/blog/nemoguardrails-integration
10. Observability platform comparison 2026 (Langfuse/LangSmith/Braintrust/Arize): https://www.marktechpost.com/2026/08/09/top-llm-observability-and-evaluation-platforms-in-2026-langfuse-langsmith-braintrust-arize-and-more-compared/ · https://www.braintrust.dev/articles/langsmith-alternatives-2026
11. Temporal — Durable execution meets AI: https://temporal.io/blog/durable-execution-meets-ai-why-temporal-is-the-perfect-foundation-for-ai
12. Letta — Agent memory (MemGPT tiers): https://www.letta.com/blog/agent-memory/
13. AG2 vs CrewAI adoption comparison: https://dev.to/agentsindex/ag2-vs-crewai-the-complete-comparison-including-the-autogen-rebrand-explained-248l

## Adversarial review

**Reviewer: `kimi-k3` (Moonshot K3) and `codex` (OpenAI gpt-5.6-sol at xhigh effort), 2026-08-30 — cross-family, generator ≠ grader.** Neither seat wrote any part of this panel. Both read all 18 files of the set in full and were asked the *publication* question rather than a proof-reading one: what in this diff creates real incremental risk beyond what the repository already discloses, whether "it is already public elsewhere" is a sound argument or a rationalisation, whether the sequencing is wrong, and what is simply FALSE. Every concrete file claim either seat made was then re-derived independently with `grep`/`git` before being recorded, and objections that measurement falsified are kept as RETRACTED rather than quietly dropped. The full journal and the complete objection list, with per-objection status, are in this PR's evidence pack (`council-journal.jsonl` and the pack's `dissent` block).

**Limits of this review, stated so it is not read as more than it was.** It happened at PUBLICATION time, not at authoring time: no seat re-derived this lane's technical findings against the codebase, so it is not a correctness review of the analysis. Nine numeric objections across the set were recorded PLAUSIBLE because the fact-checking pass ran out of time, not because they were investigated and cleared — an open list, not an all-clear.

**Finding for this file:** No file-specific finding beyond the panel-wide staleness recorded in the header.
