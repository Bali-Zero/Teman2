# Autonomous Lab SOTA Coding Workflow Review

Date: 2026-06-16
Machine: Pro (`nuzantara@Nuzantara`)
Worktree: `.worktrees/ops-autonomous-lab-watchtower`
Branch: `agent/nuzantara/ops/autonomous-lab-watchtower`

## Scope

This review looks at the current Autonomous Lab coding surface as an agentic
research-to-implementation workflow, not just as isolated Python modules.

Code and artifacts reviewed:

- `apps/backend-rag/backend/services/autonomous_lab/`
- `apps/backend-rag/backend/app/routers/autonomous_lab.py`
- `scripts/autonomous_lab_draft.py`
- `scripts/autonomous_lab_run.py`
- `apps/backend-rag/backend/tests/unit/services/autonomous_lab/`
- `apps/backend-rag/backend/migrations/migration_124_autonomous_lab_runtime.py`
- `research/operations/autonomous-lab/`

The Mini peer was unreachable during the session-start sync check, so
cross-machine git sync was not verified. All review work was performed on Pro.

## Four-Model Council

| Reviewer | Status | Main verdict |
| --- | --- | --- |
| Gemini CLI, `gemini-3-pro-preview` | Completed | The lab has a good deterministic control plane, but needs durable graph state, sandboxed execution, repo maps, trajectory memory, and evaluator-first orchestration. |
| Codex nested reviewer, `gpt-5.5` read-only | Completed | This is not yet a SOTA autonomous lab. It is a cautious planning and receipt layer without a durable worker loop, real sandbox, live source adapters, or eval harness. |
| Ollama `gemma3:27b` offline refuter | Completed | The main risk is phantom safety: the system can look safe because it records plans, while actual component behavior remains unverified. |
| Claude Opus 4.8 + `opus-mythos` | Completed after two failed attempts | Strongest invariant is deterministic allowlist governance. Fatal gaps are no durable worker loop and no sandbox. Disease-of-diseases: "built equals working." |

Claude note: the first Opus CLI attempt hung, the second hit a low budget cap,
and the final compact no-tool prompt completed. Its output was therefore an
adversarial architecture verdict from supplied context, not a fresh source walk.

## Executive Verdict

The Autonomous Lab is a solid safety-first control-plane foundation. It is not
yet an autonomous research/coding lab at SOTA level.

The current organism can draft a plan, sanitize receipts, route NotebookLM
research buckets, identify target paths, and surface planned verification
commands. It does not yet live as an executable, checkpointed, observable,
sandboxed, evaluator-driven loop.

The main architectural inversion needed is this:

> Stop treating planning as the core loop. Make evaluation the core
> orchestrator, and make every planning/execution step a checkpointed,
> sandboxed, replayable state transition.

## Anatomy Review

### 1. Watchtower and Source Acquisition

Current strengths:

- `default_research_notebooks()` defines a clear NotebookLM routing contract for
  frontier radar, agent-engineering core, and overflow intake.
- The source-cap problem is explicitly represented, including overflow routing.

Current gaps:

- Notebook IDs and source counts are hardcoded in
  `planner.py:279-330`; they are useful control-plane metadata, but not a live
  watchtower.
- There are no real source adapters yet for arXiv, GitHub releases, papers,
  MCP registries, SDK docs, package changelogs, or internal PRs.
- There is no freshness, novelty, credibility, duplication, or implementation
  impact score.

SOTA target:

- Treat NotebookLM as a research memory and synthesis layer, not as the
  execution brain.
- Add source adapters that produce canonical `FrontierSignal` records with
  provenance, license, novelty score, risk class, and reusable implementation
  hints.

### 2. Intake and Receipt Safety

Current strengths:

- The planner avoids storing raw material text and uses fingerprints for
  objective/title/source data.
- `receipt_store.py` is append-only, atomic, permission-conscious, and refuses
  obvious raw/content keys.

Current gaps:

- `_receipt_safe_material_id()` preserves safe-looking IDs when they match the
  command-arg pattern (`planner.py:523-527`). That is convenient, but default
  preservation is weaker than default hashing for a Law 2 system.
- `state_store.py` preserves token-like values for operational keys such as
  `source_ref`, `task_id`, and `worker_id` (`state_store.py:61-83`). This is
  acceptable only if those keys are strictly generated internal IDs.
- `scripts/autonomous_lab_run.py:187-196` persists bounded stdout/stderr. Size
  limits are not the same as redaction.

SOTA target:

- Default-hash all external IDs, titles, notebook source refs, URLs, stdout,
  stderr, trace snippets, and tool results.
- Keep private reversible mappings only in a local Pro-only store with tight
  permissions and explicit retention.

### 3. Planner and Orchestrator

Current strengths:

- `default_pipeline()` is the right high-level flow: watch, intake, normalize,
  compose, reconstruct, experiment, verify, promote.
- `AutonomousLabOrchestrator.orchestrate()` is deterministic and explicitly
  side-effect-free (`orchestrator.py:254-284`).

Current gaps:

- The pipeline stages are descriptive receipts, not executable contracts.
- The orchestrator creates stages but does not checkpoint, resume, retry,
  cancel, or consume queue rows.
- `planner.write_receipt()` writes JSON receipts directly
  (`planner.py:397-409`), partially duplicating the stronger receipt-store
  path.

SOTA target:

- Convert the pipeline into typed state-machine nodes with idempotent inputs,
  outputs, preconditions, postconditions, receipts, and trace IDs.
- Keep the deterministic planner, but put it behind a durable executor rather
  than leaving it as the whole lab.

### 4. Durable Execution

Current strengths:

- `state_store.py` has the right database primitives: run statuses, outbox
  statuses, event vocabulary, placement policy, and `FOR UPDATE SKIP LOCKED`
  queue semantics.
- The migration creates a credible runtime substrate.

Current gaps:

- The queue/outbox is not wired into a worker lifecycle.
- There is no heartbeat, reclaim, pause, resume, cancel, curator interrupt, or
  replay surface exposed as the real Lab API.
- The router currently surfaces drafts rather than the full lifecycle.

SOTA target:

- Implement one canonical lifecycle:
  `draft -> enqueue -> claim -> checkpointed stages -> curator interrupt ->
  sandbox experiment -> evaluation -> candidate proposal -> manual promotion`.
- Use LangGraph checkpointers or Temporal-like durable execution semantics for
  resumable state, plus the existing Postgres queue/outbox as the authoritative
  work ledger.

### 5. Sandbox and Experiment Runner

Current strengths:

- The command policy avoids shell execution and maps allowlisted commands to
  argv.
- The current CLI is dry-run by default.

Current gaps:

- `execute_command_plan()` uses host `subprocess.run()` without timeout,
  resource limits, network policy, filesystem boundary, or secret boundary
  (`scripts/autonomous_lab_run.py:177-186`).
- There is no sandbox runner contract, only a local command runner.
- Allowlists are not isolation. They reduce command surface, but they do not
  make experiments safe.

SOTA target:

- Define a `SandboxRunner` interface before adding richer execution:
  worktree root, mount list, egress policy, secret policy, CPU/memory/time
  limits, artifact manifest, stdout/stderr redaction, and cleanup guarantees.
- Phase 0 can use local worktrees. Phase 1 should support Vercel Sandbox,
  E2B, Modal sandboxes, or Firecracker-backed microVMs where appropriate.

### 6. Verification and Evaluation

Current strengths:

- Unit tests cover current safety plumbing well.
- Verification commands are planned explicitly and reviewed.

Current gaps:

- Tests mostly prove the receipts and guardrails, not candidate behavior.
- There is no differential fuzzing, sandbox escape test suite, Law 2 leak fuzz,
  regression benchmark, or automatic evaluator scorecard.
- `verification_commands_for_paths()` emits an unsupported mouth lint command
  for `apps/mouth/` paths (`command_policy.py:87-96`), while the allowlist does
  not execute it.
- `_pytest_executable()` falls back to system `pytest` if the local backend
  venv command is missing (`command_policy.py:141-145`), conflicting with the
  repo rule that virtualenv use is mandatory.

SOTA target:

- Add an evaluator-first harness. The proposer only matters if the evaluator can
  reproduce the claimed improvement.
- Score every experiment with: correctness, regression risk, Law 2 risk,
  sandbox integrity, cost, latency, and implementation maintainability.

### 7. Curator Gate and Promotion

Current strengths:

- The promotion policy is manual-only.
- Unsafe verbs and deployment-like commands are blocked in receipts.

Current gaps:

- There is no operator interrupt/resume API or dashboard.
- Manual promotion is a policy string, not a real workflow.

SOTA target:

- Add an explicit curator gate with resumable interrupts, compact evidence
  bundle, decision log, and no auto-merge/deploy path.

### 8. Memory and Learning

Current strengths:

- The code avoids raw research persistence in receipts.
- The notebooks are routed into read-mostly and overflow roles.

Current gaps:

- There is no trajectory memory of failures, evaluator scores, rejected
  approaches, or reusable implementation moves.
- There is no quarantine between "candidate learning" and "approved memory."

SOTA target:

- Keep a candidate archive inspired by Reflexion, Voyager, and Darwin Godel
  Machine patterns, but promotion-gate anything that could affect future runs.
- Store failure taxonomies and evaluator summaries, not raw data or PII.

### 9. Observability and Tracing

Current strengths:

- Receipts exist.
- Outbox event vocabulary exists.

Current gaps:

- There are no per-stage traces, spans, artifacts, or replayable trajectory
  views.
- There is no compact dashboard for stuck runs, blocked gates, recurring
  failures, or sandbox health.

SOTA target:

- Add OpenAI Agents-style traces or equivalent spans for every stage.
- Correlate run ID, trace ID, source fingerprints, worktree ID, sandbox ID,
  evaluator report ID, and curator decision ID.

### 10. MCP and Tool Governance

Current strengths:

- The lab already thinks in contracts and receipts, which maps well to MCP.

Current gaps:

- There is no MCP tool/source registry for research adapters or experiment
  tools.
- Tool risk, auth scope, egress policy, and data class are not first-class.

SOTA target:

- Create a tool/source registry aligned with MCP tool metadata and authorization
  patterns.
- Every tool gets a declared risk class, allowed machine, credential boundary,
  input data class, output data class, and receipt policy.

## Meta-Pattern

The lab currently models governance as receipts and policies before executable
contracts. That is a good safety instinct, but it becomes a failure mode if the
receipts are mistaken for life.

SOTA agents are not "more autonomous prompts." They are evaluated state
machines. The lab should become a durable experimental organism whose smallest
unit of truth is:

`checkpointed state + sandboxed action + empirical evaluator result + curator decision`

## Reuse-First Target Architecture

1. Control plane
   - Keep Postgres queue/outbox and placement rules.
   - Add durable execution semantics through LangGraph checkpointers or a
     Temporal-like workflow layer.

2. Graph runtime
   - Convert watch, intake, normalize, compose, reconstruct, experiment, verify,
     and promote into checkpointed nodes.
   - Add explicit pause/resume/cancel/retry/reclaim semantics.

3. Sandbox runner
   - Start with local worktree runner only for phase 0.
   - Add an interface that can back onto E2B, Vercel Sandbox, Modal sandboxes,
     or Firecracker-backed microVMs.

4. Repo context
   - Steal from Aider-style repo maps and tree-sitter symbol maps.
   - Build sanitized prod-like context manifests from import graphs, route
     ownership, fixtures, env-key allowlists, and production command paths.

5. Coding loop
   - Steal mini-swe-agent's minimalism for the first executable loop.
   - Steal SWE-agent/OpenHands event-stream ideas for trajectories and
     debugging.

6. Evaluation
   - Steal DSPy GEPA's proposer/evaluator optimization mindset.
   - Make the evaluator the orchestrator, not a final decorative step.

7. Learning
   - Borrow Reflexion/Voyager/DGM ideas only behind a promotion gate.
   - Never let a self-improvement archive auto-edit prompts, policies, or
     notebooks without review.

8. MCP
   - Use MCP-style tool metadata and auth boundaries for every research source,
     code tool, browser tool, notebook tool, and sandbox tool.

## Roadmap

### P0 - Make the Lab Alive but Contained

1. Build the canonical lifecycle worker.
   - Consume `autonomous_lab_runs`.
   - Claim with `SKIP LOCKED`.
   - Write heartbeat.
   - Execute checkpointed stage nodes.
   - Emit outbox events.
   - Support retry, fail, cancel, and reclaim.

2. Add the sandbox runner contract.
   - Include timeouts, CPU/memory limits, network policy, secret policy,
     filesystem mounts, artifact manifests, stdout/stderr redaction, and
     cleanup.

3. Make Law 2 default-deny in receipts and traces.
   - Hash external IDs by default.
   - Redact command output before persistence.
   - Keep reversible maps private and Pro-only.

4. Build the evaluator-first harness.
   - Include unit/regression tests, differential fuzzing, sandbox escape tests,
     Law 2 leak tests, command-policy tests, and candidate behavior tests.

5. Add repo-map and prod-like context manifests.
   - Tree-sitter or AST symbol index.
   - Import graph.
   - Route/service ownership.
   - Fixture shape manifests.
   - Env-key allowlist without values.

### P1 - Make It Useful Every Day

1. Add source adapters and novelty scoring.
2. Add an MCP tool/source registry with risk classes and auth scopes.
3. Add curator interrupt/resume APIs and a small dashboard.
4. Add traces and artifact provenance.
5. Add a target-zone risk matrix so the lab can work beyond its own files.
6. Add stuck-run detection, heartbeat reclaim, and outbox DLQ surfacing.

### P2 - Make It Learn Safely

1. Add GEPA-style prompt and workflow optimization on safe benchmark tasks.
2. Add a DGM-like candidate archive with strict promotion gates.
3. Add a reusable technique library from approved successful experiments.
4. Add multiple sandbox backends and compare cost/reliability.
5. Add periodic model/tool benchmark refreshes.

## Findings to Fix

1. `orchestrator.py:254-284`
   - The orchestrator drafts and reviews but does not execute durable stage
     transitions.

2. `planner.py:279-330`
   - Notebook routing is useful, but hardcoded source counts and notebook IDs
     are not a live watchtower.

3. `planner.py:397-409`
   - Planner writes receipts directly instead of delegating all persistence to
     the stronger append-only receipt store.

4. `planner.py:523-527`
   - Safe-looking material IDs may be preserved. External identifiers should be
     hashed by default unless generated internally.

5. `state_store.py:61-83`
   - Token-like operational keys are preserved. Keep this only for generated
     internal IDs and add tests proving external IDs are hashed.

6. `scripts/autonomous_lab_run.py:177-196`
   - Allowlisted commands run on the host without timeout or sandbox policy, and
     stdout/stderr are persisted without semantic redaction.

7. `reviewer.py:23-31`
   - Allowed target scope is mostly self-referential. The lab needs risk-zoned
     target permissions to safely work on real Nuzantara subsystems.

8. `command_policy.py:87-96`
   - The planner can emit an unsupported frontend lint command that the runner
     cannot execute.

9. `command_policy.py:141-145`
   - Falling back to system `pytest` violates the repo's virtualenv-mandatory
     rule.

## Things Not To Do

- Do not start an H24 daemon before the worker loop, sandbox runner, evaluator,
  curator gate, and dashboard exist.
- Do not treat NotebookLM as the decision engine.
- Do not add auto-merge, auto-deploy, or production write paths.
- Do not copy old multi-agent frameworks blindly; prefer current durable
  execution and sandbox patterns.
- Do not persist raw OSINT, PII, notebook text, raw stdout, raw stderr, prompts,
  or tool results.

## Sources and Reuse Targets

- LangGraph persistence:
  <https://docs.langchain.com/oss/python/langgraph/persistence>
- LangGraph interrupts:
  <https://docs.langchain.com/oss/python/langgraph/interrupts>
- OpenAI Agents SDK agents:
  <https://openai.github.io/openai-agents-python/agents/>
- OpenAI Agents SDK tracing:
  <https://openai.github.io/openai-agents-python/tracing/>
- Temporal durable execution:
  <https://temporal.io/blog/what-is-durable-execution>
- Temporal docs:
  <https://docs.temporal.io/>
- Microsoft Agent Framework:
  <https://learn.microsoft.com/en-us/agent-framework/overview/>
- SWE-agent:
  <https://github.com/SWE-agent/SWE-agent>
- mini-swe-agent:
  <https://github.com/SWE-agent/mini-swe-agent>
- OpenHands:
  <https://github.com/OpenHands/OpenHands>
- OpenHands SDK:
  <https://github.com/OpenHands/software-agent-sdk>
- Aider:
  <https://github.com/Aider-AI/aider>
- Darwin Godel Machine:
  <https://github.com/jennyzzt/dgm>
- Sakana AI DGM writeup:
  <https://sakana.ai/dgm/>
- ReAct:
  <https://arxiv.org/abs/2210.03629>
- Reflexion:
  <https://arxiv.org/abs/2303.11366>
- Voyager:
  <https://arxiv.org/abs/2305.16291>
- DSPy GEPA:
  <https://dspy.ai/getting-started/gepa-optimization/>
- E2B coding agents:
  <https://e2b.dev/docs/use-cases/coding-agents>
- Vercel Sandbox:
  <https://vercel.com/docs/vercel-sandbox>
- Modal sandboxes:
  <https://modal.com/docs/guide/sandboxes>
- Firecracker:
  <https://firecracker-microvm.github.io/>
- MCP tools spec:
  <https://modelcontextprotocol.io/specification/2025-06-18/server/tools>
- MCP authorization:
  <https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization>

