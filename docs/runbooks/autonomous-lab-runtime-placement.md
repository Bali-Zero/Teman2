# Autonomous Lab Runtime Placement

Date: 2026-06-09

## Contract

The Autonomous Lab is a control plane before it is a daemon. Queue, outbox, and
receipts may be developed from Air-M5, but run execution belongs on Pro.

The Lab's steady-state job is continuous research-to-implementation discovery:
watch AI research, model releases, SDK/framework changelogs, and software
implementation patterns; turn fresh signals into bounded Nuzantara experiment
candidates; test them in isolated prod-like contexts; and surface only
decision-grade proposals. A tick with no valid signal is still a receipt, not a
silent pass.

| Machine                      | Role             | Allowed                                                                                           | Blocked                                                                                    |
| ---------------------------- | ---------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Air-M5 (`balizero@Air-M5`)   | `air_m5_cockpit` | Edit code, enqueue/manual draft, light unit tests, review receipts                                | Claim Lab runs, consume Lab outbox, DB/vector local replicas, deploys, Ollama/heavy render |
| Pro (`nuzantara@Nuzantara`)  | `pro_runtime`    | Claim Lab runs, execute allowlisted verification, consume outbox, DB/Qdrant/Ollama/deploy tooling | Direct `main` push, autonomous promotion, raw private corpus persistence                   |
| Mini (`nuzantara@Mini-Pro2`) | `mini_scheduler` | H24 scheduling, enqueue, consume outbox, watchdog/deadman checks                                  | Execute Lab run patches, deploy, copy OSINT/WhatsApp data                                  |

Unknown hosts fail closed.

## Runtime Foundation

Migration `124` creates:

- `autonomous_lab_runs`: idempotent run queue, status machine, retry metadata,
  worker ownership, heartbeat fields.
- `autonomous_lab_events_outbox`: at-least-once event log, claimed with
  `FOR UPDATE SKIP LOCKED`, acked only after downstream success.

Run state transitions that create lifecycle events use a single SQL CTE for the
state update plus outbox insert. If the outbox insert fails, the state mutation
fails with it.

The code contract lives in:

- `apps/backend-rag/backend/services/autonomous_lab/state_store.py`
- `apps/backend-rag/backend/services/autonomous_lab/receipt_store.py`
- `apps/backend-rag/backend/migrations/migration_124_autonomous_lab_runtime.py`

## Status Flow

Run queue:

1. `pending`: inserted by cockpit/scheduler with an idempotency key.
2. `running`: claimed by a Pro worker with `FOR UPDATE SKIP LOCKED`.
3. `succeeded`: worker completed and emitted `run_succeeded`.
4. `pending`: retryable failure before max attempts.
5. `failed`: terminal failure after max attempts.
6. `cancelled`: explicit future operator action only.

Outbox:

1. `pending`: event is ready to deliver.
2. `in_progress`: Pro/Mini consumer claimed it.
3. `consumed`: handler succeeded, then ack was written.
4. `failed_dlq`: max attempts exhausted.

## Operator Rules

- Do not start an H24 Lab daemon until queue/outbox tests and migration tests
  are green on the target branch.
- Do not run an unbounded watch loop. Continuous AI/software scouting must have
  an allowlisted source set, cost/rate bounds, and a fresh-signal or idle-tick
  receipt.
- Do not execute run workers from Air-M5.
- Do not trust caller-provided machine role. Runtime code resolves the current
  host/user placement and only test fixtures may inject a placement override.
- Do not install Postgres, Qdrant, Ollama, Fly, Docker-heavy workloads, or
  render pipelines on Air-M5 as a fallback.
- Do not persist raw material, raw OSINT, raw WhatsApp content, secrets, or PII
  into Lab receipts, run metadata, or outbox payloads.
- Do not wire deploy, merge, push, or Google Workspace writes into the Lab
  without an explicit operator gate.

## NotebookLM Research Routing

The Lab treats NotebookLM as a research sensor layer, not as a final decision
engine. Each Lab run should record the NotebookLM route it used before it
produces an experiment proposal.

| Route                    | Notebook                                                 | UUID                                   | Observed sources | Lab use                                                                                              |
| ------------------------ | -------------------------------------------------------- | -------------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------- |
| `frontier_radar`         | `NB-INTEL-AIResearch — Daily AI Intelligence`            | `dc5d01cd-e99f-4c8f-aae4-75060b43d0de` | 493 / 500        | Read daily AI/software frontier signals, model releases, SDK changes, and implementation candidates. |
| `agent_engineering_core` | `NB-LAB-AGENT-ENGINEERING-2026 — AI Coding Core`         | `dff45303-4b51-45ad-8718-502d4f8a8e3f` | 404 / 500        | Read stable engineering patterns from NB-AGENTS plus the consolidated MATA GARUDA notebooks.         |
| `ai_research_overflow`   | `NB-INTEL-AIResearch-2 — Daily AI Intelligence Overflow` | `069f009c-ce74-42e5-b75c-e584aa18feb1` | 1 / 500          | Write fresh frontier sources while `frontier_radar` is near the NotebookLM source cap.               |

Operational contract:

1. Query `frontier_radar` for novelty: what changed in AI research, agent
   platforms, coding tools, SDKs, MCP, world models, CTI, and software patterns
   since the previous tick.
2. Query `agent_engineering_core` for implementation shape: what architecture,
   sandboxing, evaluation, code hygiene, or multi-agent pattern should Nuzantara
   reuse.
3. Write new AI/software sources to `ai_research_overflow` while
   `frontier_radar` remains at or above the overflow threshold.
4. Promote a Lab candidate only when its receipt can show at least one frontier
   signal and one engineering-pattern grounding, or explicitly record why the
   tick is idle.

## Pro Worker Activation Slice

`scripts/autonomous_lab_worker.py` is a bounded Pro-only queue worker. It claims
at most one pending `autonomous_lab_runs` item per iteration, maps target paths
to the shared command allowlist, executes verification without a shell, and then
marks the run `succeeded` or retryable/failed through owner-scoped state-store
transitions.

From Pro only:

```bash
cd ~/nuzantara
source apps/backend-rag/.venv/bin/activate
DATABASE_URL="$DATABASE_URL_LOCAL" \
  python scripts/autonomous_lab_worker.py --execute-verification --iterations 1
```

From Air-M5, use dry-run only:

```bash
python scripts/autonomous_lab_worker.py --dry-run
```

The worker intentionally does not create a worktree experiment, merge, deploy,
push, write Google Workspace files, or start a persistent scheduler. H24
scheduling remains gated by `scheduler_daemon`.

## Local Verification

From the worktree:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/unit/services/autonomous_lab -q
PYTHONPATH=. pytest backend/tests/migrations/test_migration_124_autonomous_lab_runtime.py -q
ruff check backend/services/autonomous_lab backend/migrations/migration_124_autonomous_lab_runtime.py ../../scripts/autonomous_lab_worker.py
```

These checks are intentionally Air-safe: they use fake async connections and do
not require a local Postgres instance.
