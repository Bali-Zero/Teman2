---
date: 2026-05-31
domain: operations
client_case: nuzantara-autonomous-lab
status: scaffold-v0
machine: Pro
worktree: ops-autonomous-lab-scaffold
grounding:
  - research/wr2/2026-05-27-wr2-autonomous-workflow-spec.md
  - research/wr3/06-architecture-skeleton.md
  - research/operations/2026-05-25-sota-workflow-gap-analysis-and-l5-spec.md
  - docs/runbooks/agent-worktree-broker.md
  - apps/backend-rag/backend/services/research/*
  - apps/backend-rag/backend/services/misc/autonomous_research_service.py
---

# Nuzantara Autonomous Lab - Technical Map v0

## 0. Frame

Objective: build a source-agnostic autonomous lab that continuously ingests
research material, normalizes it, composes hypotheses and operational specs,
simulates changes against prod-like Nuzantara contexts, applies experiments in
isolated worktrees, verifies them, and surfaces only decision-grade candidates
for operator promotion.

Smallest useful output in this pass:

1. A concrete pipeline and component map.
2. A minimal backend contract that can turn arbitrary material into a lab run
   plan and durable receipt without persisting raw material.
3. Focused tests proving source-agnostic input, safety gates, simulation plan,
   and receipt writing.

Non-goals for v0:

- No production deployment.
- No Google Workspace write flow.
- No autonomous merge, push, or promotion.
- No raw WhatsApp or private corpus persistence.

## 1. Pipeline

| Step | Stage | Input | Output | Gate |
| --- | --- | --- | --- | --- |
| 1 | Intake | URL, repo file, dataset, CLI result, operator note, Drive metadata, chat metadata | `ResearchMaterial` envelope | Source adapter allowlist and provenance captured |
| 2 | Normalize | Raw or semi-structured material | `NormalizedMaterial` with checksum, summary, tags, claims, risks | Raw text not persisted in lab receipt |
| 3 | Compose | Normalized materials plus current repo map | Hypotheses, implementation spec, operational brief | Evidence quorum and conflict labels |
| 4 | Reconstruct | Git HEAD, env allowlist, fixtures, schema contracts, relevant prod config snapshot | Prod-like simulation context | No secrets, no live Workspace mutations |
| 5 | Experiment | Spec plus simulation context | Worktree branch, patch, generated artifacts | `scripts/agent_start.py` worktree isolation |
| 6 | Verify | Patch plus expected behavior | Tests, diff, metrics, failure analysis | Empirical checks pass or failure is explicit |
| 7 | Promote Candidate | Verified run receipt | Decision-grade proposal | Manual operator decision only |

The lab is not a scheduler first. It is a contract first. Cron, LaunchAgent,
MCP, or backend endpoints can feed this same contract later.

## 2. Components

| Component | Responsibility | Existing anchor | v0 status |
| --- | --- | --- | --- |
| Source adapters | Wrap heterogeneous inputs into one material contract | `backend/services/research/*`, `infra/skills/regulatory-ingest.md` | Contract only |
| Normalizer | Strip raw content, derive summary/tags/claims/checksum | New `backend/services/autonomous_lab/planner.py` | Implemented |
| Composer | Convert materials into hypotheses and specs | `ConsiglioV1`, `LiteratureAgent` | Planned |
| Prod-like context builder | Rebuild relevant runtime context from git, fixtures, config allowlist, and schemas | WR2/WR3 specs, backend tests | Planned |
| Worktree experiment runner | Create worktree, apply patch, collect diff | `scripts/agent_start.py` | Planned, command emitted |
| Verification runner | Execute tests, lint, metrics, failure analysis | existing pytest/ruff patterns | Planned, commands emitted |
| Decision gate | Show only high-potential proposals with receipts | WR2 manual publish gate pattern | Contracted |
| Receipt writer | Persist JSON state and audit trail | WR2 artifact discipline | Implemented |

## 3. Storage And State

State should be append-only by default.

| Layer | Storage | Data |
| --- | --- | --- |
| v0 local receipts | `research/operations/autonomous-lab/receipts/*.json` or caller-provided path | Run ID, material checksums, derived summaries, gates, simulation plan, verification commands |
| v1 operational queue | Postgres table `autonomous_lab_runs` | Run state machine, idempotency key, timestamps, last error |
| v1 events | Postgres outbox `autonomous_lab_events_outbox` | `material_ingested`, `run_drafted`, `experiment_ready`, `verification_failed`, `candidate_ready` |
| v1 artifacts | Repo worktree plus local artifact dir | Patches, metrics, test logs, failure analysis |
| v2 vector memory | Existing Qdrant/knowledge collections | Only derived and permission-safe summaries |

Raw material is adapter-owned. The lab receipt stores only checksum and derived
fields unless a future adapter is explicitly approved for archival.

## 4. Agents Or Jobs

| Agent/job | Trigger | Runs where | Output |
| --- | --- | --- | --- |
| `lab-intake-sweeper` | Scheduled or manual | Pro/Mini H24 lane | Material envelopes |
| `lab-normalizer` | New material | Backend service or CLI | Normalized material receipt |
| `lab-composer` | Enough related material | LLM council when justified | Hypotheses and specs |
| `lab-simulator` | Candidate spec | Isolated worktree | Prod-like context manifest |
| `lab-experimenter` | Approved experiment budget | Isolated worktree | Patch and artifact bundle |
| `lab-verifier` | Patch ready | Same worktree | Test report, diff report, metrics |
| `lab-curator` | Verification complete | Read-only | Decision-grade proposal or archive |

The first implementation keeps these as service contracts, not long-running
agents. That avoids creating another autonomous process before the state
contract is stable.

## 5. Safety Gates

Hard blockers:

- No production deploy command generated by the lab.
- No `origin/main` push from Mini.
- No Google Workspace write flow unless explicitly requested.
- No raw private corpus persistence in receipts.
- No experiment outside an `agent_start.py` worktree.
- No promotion without manual operator decision.
- No pricing or visa claims without their existing canonical tools/references.

Soft warnings:

- One-source synthesis.
- Missing prod-like fixture.
- Verification command cannot be inferred.
- Failure analysis absent after a failed check.

## 6. Prod-Like Simulation

The simulator must reconstruct context before patching:

1. Git base: current branch, commit SHA, diff status, peer sync status when
   relevant.
2. Runtime contract: target app, import path, router/service boundaries, env
   key names without values.
3. Data shape: fixtures, schema snippets, Qdrant payload shape, migration state,
   or sanitized CRM/WhatsApp metadata as applicable.
4. Execution path: exact command that production or cron uses, with local
   substitutes for external services.
5. Metrics: expected test count, latency/cost budget when measurable, and a
   failure taxonomy.

For v0 the scaffold emits the simulation plan. Later phases can execute it.

## 7. Nuzantara Integration

Integration starts in backend service code because it is easiest to test and
least coupled to a specific scheduler.

Current v0.1 files:

- `apps/backend-rag/backend/services/autonomous_lab/planner.py`
- `apps/backend-rag/backend/tests/unit/services/autonomous_lab/test_planner.py`
- `apps/backend-rag/backend/tests/unit/services/autonomous_lab/test_draft_cli.py`
- `scripts/autonomous_lab_draft.py`
- `research/operations/autonomous-lab/examples/bootstrap-input.json`
- `research/operations/autonomous-lab/receipts/2026-05-31-bootstrap.json`
- `research/operations/autonomous-lab/receipts/autonomous-lab-bootstrap-example.json`

Next integration points:

- Optional router under `backend/app/routers/autonomous_lab.py`, disabled by
  default and API-key gated.
- Postgres state machine only after local receipts prove stable.
- Outbox consumers only after ack-after-success behavior is implemented.

## 7.1 2026-06-09 v1 Control-Plane Update

The Lab now exposes a receipt-safe operational plan that separates the repo's
meta workflow from the P1-P9 governance pieces:

- Meta workflow: `0 STUDY`, `1 SPEC`, `2 ARCH`, `3 PLAN/SQUAD`,
  `4 BUILD_parallel`, `5 SEAM_VERIFY`, `6 ENRICH`, `7 TEST_PROD`,
  `8 REVIEW`, `9 SHIP`, `10 LEARN`, plus `GOVERN`.
- Governance pieces: `P1` verifier verification, `P2` private-material
  confinement, `P3` prod-like sandbox, `P4` contract verification, `P5` spec
  as gate, `P6` parallel fanout gate, `P7` quarantined learning, `P8` bounded
  internal app design, `P9` liveness governance.

Beyond the anchored `lab-intake-sweeper`, the v1 plan names ten control-plane
pieces:

| Component | State | Parallel group | Gate |
| --- | --- | --- | --- |
| `operational_queue` | Implemented foundation | Foundation | `skip_locked_or_equivalent_claim` |
| `events_outbox` | Implemented foundation | Foundation | `ack_after_success` |
| `source_adapters` | Planned | Ingestion | `no_raw_receipt_persistence` |
| `composer` | Planned | Reasoning | `evidence_quorum_or_warning` |
| `prod_like_context_builder` | Planned | Reasoning | `no_secret_values` |
| `worktree_experiment_runner` | Planned | Execution | `worktree_isolation` |
| `verification_runner` | Planned | Execution | `empirical_result_recorded` |
| `curator_decision_gate` | Planned | Curation | `manual_operator_decision_only` |
| `scheduler_daemon` | Blocked | Ops | `state_contract_stable_first` |
| `dashboard_api` | Planned | Ops | `read_only_until_operator_action` |

Parallelization rule:

- Serial first: `operational_queue` and `events_outbox`.
- Parallel after shared envelope contract: `source_adapters`, `composer`,
  `prod_like_context_builder`.
- Parallel after worktree contract: `worktree_experiment_runner`,
  `verification_runner`.
- Parallel read-only visibility and curation: `curator_decision_gate`,
  `dashboard_api`.
- Last/manual gate: `scheduler_daemon`, because H24 automation amplifies every
  upstream mistake.

## 7.2 2026-06-09 v1 Runtime Foundation

The first durable runtime foundation is implemented, but no H24 daemon is
enabled by default.

Files:

- `apps/backend-rag/backend/services/autonomous_lab/state_store.py`
- `apps/backend-rag/backend/migrations/migration_124_autonomous_lab_runtime.py`
- `docs/runbooks/autonomous-lab-runtime-placement.md`

Placement:

- Air-M5 is `air_m5_cockpit`: edit, enqueue, light tests, receipt review.
- Pro is `pro_runtime`: claim and execute Lab runs, consume outbox.
- Mini is `mini_scheduler`: schedule/enqueue and consume outbox, but route run
  execution to Pro.
- Unknown hosts fail closed.

Durable storage:

- `autonomous_lab_runs` is idempotent on `idempotency_key`, claimed with
  `FOR UPDATE SKIP LOCKED`, and owns run retry/heartbeat state.
- `autonomous_lab_events_outbox` is an at-least-once queue. Consumers claim
  events with `FOR UPDATE SKIP LOCKED`, then ack only after the downstream
  handler succeeds.
- Run lifecycle transitions use a single SQL CTE for state update plus outbox
  insert. The state mutation and lifecycle event are not split across separate
  storage calls.
- Runtime placement is resolved from current host/user and enforced fail-closed;
  caller-provided roles are treated only as a consistency check.

Still blocked:

- `scheduler_daemon`: blocked until queue/outbox and migration tests are green
  on the target branch.
- `worktree_experiment_runner`: blocked from deploy, merge, push, and Workspace
  writes until an explicit operator gate exists.
- `dashboard_api`: read-only only until operator actions have a separate
  authorization model.

CLI usage:

```bash
source apps/backend-rag/.venv/bin/activate
python scripts/autonomous_lab_draft.py \
  research/operations/autonomous-lab/examples/bootstrap-input.json
```

## 8. Decision Metric

v0 is useful if a caller can provide heterogeneous material and receive a
receipt that:

- Contains no raw material text.
- Names the worktree isolation command.
- Names verification commands.
- Blocks Workspace writes and production promotion by default.
- Is deterministic enough to diff and review.
