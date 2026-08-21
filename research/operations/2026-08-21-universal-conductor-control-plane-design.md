# Universal Conductor Control Plane

**Status:** implementation-ready design + compiled MIR baseline; router/hooks not yet armed

**Date:** 2026-08-21

**Scope:** Air-M5, Pro, Mini-Pro2; Claude, Codex, Antigravity (`agy`), Kimi, and future CLI-backed LLMs

**Decision owner:** Zero

## 1. Decision

The LLM that opens an interactive session is the **conductor** for that session. The
conductor owns the mandate, plan, routing decisions, evidence synthesis, and final
conversation with Zero. It is not automatically the architect, builder, or grader.

The conductor routes through a **Model Intelligence Registry (MIR)**. The MIR is the
router's evidence-backed knowledge of every sanctioned model and every concrete way of
invoking it: techniques, modalities, tool support, context/output limits, reasoning
controls, known failure modes, task-specific quality, latency, quota pressure, privacy
eligibility, and current availability. Routing from model names or provider reputation
alone is forbidden.

For every non-trivial code mutation, the conductor must route the implementation to a
separate builder session when a healthy, policy-eligible builder is available. The
builder is selected by task shape and minimum sufficient capability, not by the model
that happened to open the session.

Examples:

- Codex Sol may route mechanical work to Luna or Haiku and standard implementation to
  Terra, Sonnet, Kimi 2.7, Qwen 3.7, DeepSeek V4 Flash, or any future eligible builder.
  Cross-provider builders are first-class candidates, not merely emergency fallbacks.
  Sol remains available for architecture, integration judgment, and red-team.
- Codex Terra or Luna may also be the conductor. They keep control of the session but
  must request a stronger architect when the task exceeds their capability, and use a
  separate builder session for non-trivial mutations.
- Claude, `agy`, and Kimi follow the same role protocol. Provider-specific names are
  adapters around one model-independent contract.
- The grader is selected independently and must be from a different model family than
  the principal builder when the repository's generator-not-grader rule applies.

This is a **session-local control plane**, not a new central daemon. Each session owns
its own state and emits durable receipts. This preserves SYMBIOSIS Law 3: no central
polling orchestrator and no new always-on service.

## 2. What the live system proves today

The current system has the right doctrine but does not enforce it consistently:

1. `AGENTS.md` already defines conductor as a role and allows any frontier LLM to open
   the session.
2. `FLEET_TOPOLOGY.json` contains useful role chains, but it mixes current decisions,
   historical prose, accounts, and stale availability claims. It is not a small runtime
   policy that a hook can validate deterministically.
3. `scripts/fleet_dispatch.py` answers **where** a lane may run and protects file scope.
   It explicitly does not choose or run an LLM. It should remain the placement engine.
4. The current `orchestrate_gate.py` gates on transcript length (`>800` lines) and lack
   of recent dispatches. It does not know the task class, conductor model, builder
   capability, mutation scope, or whether a valid implementation receipt exists.
5. The current home-level `model_routing_gate.py` only requires an explicit model on an
   `Agent` call. Its message still names the former Fable-only doctrine. It governs how
   a dispatch is expressed, not whether a conductor must delegate.
6. Codex hook state is split across the fleet:
   - Pro has orchestration, model-routing, dispatch-nudge, and subagent-stop hooks.
   - Air-M5 launches `orchestrate_gate.py` with `ORCHESTRATE_GATE_OFF=1` and lacks the
     Codex model-routing and subagent-stop hooks.
   - Mini-Pro2 has no `~/.codex/hooks.json`.
7. A zero-token inventory on 2026-08-21 found Codex CLI 0.148.0 on Pro/Mini and 0.147.0
   on Air-M5. All three caches list `gpt-5.6-sol`, `gpt-5.6-terra`, and
   `gpt-5.6-luna`, but cache presence proves discovery only, not authenticated inference.
   The stale topology sentence that the slugs are dead and the opposite claim that they
   are live are therefore both too strong until an explicit endpoint probe succeeds.
8. `MODEL_TOPOLOGY.json` is stale against the same live inventory. Pro currently lists
   only `qwen3.5:9b`, `qwen2.5vl:7b`, and `bge-m3`; Mini lists nine models, including
   newer Qwen/VL/OCR entries absent from the topology. Static role assignments cannot be
   used as live model availability.

Conclusion: current behavior is advisory and host-dependent. It cannot prove that Sol
did not implement a delegable task, nor that a session begun in another LLM obeyed the
same role split.

## 3. Architectural boundaries

### 3.1 Responsibilities

| Component | Owns | Must not own |
| --- | --- | --- |
| Conductor | mandate, decomposition, routing, synthesis, evidence, user interaction | default implementation of delegable mutations |
| Architect | design and hard technical judgment | grading its own implementation |
| Builder | scoped code mutation and builder-local tests | session mandate or final verdict |
| Grader | independent review and verdict | mutation of the diff it judges |
| Placement engine | machine capacity, repo alignment, file-scope collision | model quality decisions |
| Model Intelligence Registry | versioned model/endpoint facts, evidence, benchmark results | live process execution or task policy |
| Capability probe | observed CLI/model/seat availability and feature checks | task quality claims or routing policy |
| Hook adapter | translate harness event into canonical event | provider-specific policy |

### 3.2 Hard invariants

The runtime must enforce these invariants:

1. `session_starter == conductor` for the lifetime of the interactive session.
2. `conductor_session_id != builder_session_id` for every delegable mutation.
3. A conductor write requires either a valid builder/integration receipt or a typed
   direct-write exemption.
4. An exemption is explicit, bounded by files and expiry, and stored in the evidence
   ledger. There is no boolean kill switch that silently disables the policy.
5. Builder selection uses the least expensive healthy **endpoint** whose evidence-backed
   capabilities and task score meet the task profile. The abstract model name is not a
   routable target.
6. Architecture may route upward; implementation normally routes downward or laterally.
7. Grading is independently routed and observes the repository's family-separation
   rule.
8. One writer owns a file scope at a time. Existing `fleet_dispatch.py` remains the
   authority for machine placement and collision refusal.
9. PII/OSINT tasks obey the local-only policy and never write cleartext into session
   manifests, prompts persisted for reuse, receipts, or telemetry.
10. Unknown model identity, unreadable policy, invalid receipt, or unprovable file scope
    is visible degradation. It is never reported as compliant.
11. Read-only exploration is never blocked by the delegation gate.
12. No hook performs a token-consuming health probe on every tool call.
13. Every routing decision binds the hashes of the task profile, model card, endpoint
    profile, capability snapshot, benchmark version, and executable policy it used.
14. A vendor declaration, CLI model listing, or model self-report never becomes an
    empirical quality score without an external benchmark or observed task outcome.

## 4. Proposed repository layout

```text
infra/conductor/
├── policy.v1.json                 # small executable routing policy
├── policy.schema.json             # JSON Schema, rejects drift at load time
├── capability_ontology.v1.json    # canonical feature and technique vocabulary
├── task_profiles.v1.json          # typed requirements and quality floors per task shape
├── model_cards/                   # model-level facts, limitations, and evidence
│   └── *.json
├── endpoint_profiles/             # CLI/harness/account-class/node invocation surfaces
│   └── *.json
├── benchmark_manifest.v1.json     # benchmark suites, versions, and promotion rules
├── model_capability_index.v1.json # generated normalized router projection
├── hook_manifest.v1.json          # desired adapters per harness
└── fixtures/
    ├── claude_events.jsonl
    ├── codex_events.jsonl
    └── session_examples.json

scripts/conductor/
├── __init__.py
├── contracts.py                   # enums + frozen dataclasses
├── policy.py                      # load, schema validate, policy hash
├── identity.py                    # engine/model/family/session/host resolution
├── model_registry.py              # load, join, validate, and hash MIR records
├── capability.py                  # cached observed endpoint availability/features
├── benchmarks.py                  # ingest external benchmark evidence
├── outcomes.py                    # privacy-safe task outcome calibration
├── classifier.py                  # deterministic task and mutation classifier
├── router.py                      # pure role assignment function
├── receipts.py                    # signed/hash-bound append-only receipts
├── state.py                       # atomic session manifest state machine
├── hooks.py                       # canonical hook decisions
├── adapters/
│   ├── claude.py
│   ├── codex.py
│   └── subprocess.py              # agy/Kimi and future CLI engines
└── doctor.py                      # local and three-node conformance checks

scripts/conductor/conductor_ctl.py # SHADOW doctor/status/smoke/fleet-doctor entry point
scripts/nuz_session.py             # universal session launcher
scripts/install_conductor_hooks.py # idempotent, path-aware home installer

scripts/tests/
├── test_conductor_router.py
├── test_conductor_policy.py
├── test_conductor_model_registry.py
├── test_conductor_benchmarks.py
├── test_conductor_receipts.py
├── test_conductor_hook_contract.py
├── test_conductor_installer.py
└── test_conductor_fleet_doctor.py
```

`FLEET_TOPOLOGY.json` remains the strategic fleet/account SSOT and
`MODEL_TOPOLOGY.json` remains the local-model inventory SSOT. Model cards and endpoint
profiles add technical intelligence; they do not duplicate account or node topology.
The small `policy.v1.json` and `model_capability_index.v1.json` are executable
projections consumed by hooks and the router. A generator builds them from the topology,
MIR records, and explicit corrections; CI fails if either checked-in projection is
stale. Runtime hooks never parse historical prose.

## 5. Canonical contracts

The core is standard-library Python, fully typed, deterministic, and importable without
the backend virtualenv. The following shapes are the implementation contract.

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal


class Role(StrEnum):
    CONDUCTOR = "conductor"
    ARCHITECT = "architect"
    BUILDER = "builder"
    GRADER = "grader"


class TaskClass(StrEnum):
    READ_ONLY = "read_only"
    MECHANICAL = "mechanical"
    STANDARD_BUILD = "standard_build"
    HARD_BUILD = "hard_build"
    ARCHITECTURE = "architecture"
    REVIEW = "review"
    PII_LOCAL = "pii_local"


class Decision(StrEnum):
    ALLOW = "allow"
    DELEGATE_REQUIRED = "delegate_required"
    BLOCK = "block"
    DEGRADED = "degraded"


class EvidenceKind(StrEnum):
    DECLARED = "declared"
    PROBED = "probed"
    BENCHMARKED = "benchmarked"
    PRODUCTION = "production"


@dataclass(frozen=True)
class SessionIdentity:
    session_id: str
    root_session_id: str
    parent_session_id: str | None
    role: Role
    engine: Literal["claude", "codex", "agy", "kimi", "unknown"]
    model: str
    family: str
    host: str
    repo_root: Path
    repo_head: str
    started_at: str


@dataclass(frozen=True)
class TaskIntent:
    task_id: str
    task_class: TaskClass
    gear: Literal[1, 2, 3]
    mutation: bool
    files: tuple[str, ...]
    requires: frozenset[str]
    task_profile_id: str
    estimated_context_tokens: int | None
    required_modalities: frozenset[str]
    required_tools: frozenset[str]
    contains_pii: bool


@dataclass(frozen=True)
class CapabilityEvidence:
    capability: str
    value: bool | int | float | str | None
    kind: EvidenceKind
    evidence_ref: str
    observed_at: str
    expires_at: str | None
    confidence: float


@dataclass(frozen=True)
class TaskScore:
    task_profile_id: str
    score: float | None
    benchmark_id: str | None
    benchmark_version: str | None
    sample_count: int
    observed_at: str | None


@dataclass(frozen=True)
class EndpointCandidate:
    endpoint_id: str
    engine: str
    model_card_id: str
    model: str
    family: str
    role: Role
    features: tuple[CapabilityEvidence, ...]
    task_scores: tuple[TaskScore, ...]
    healthy: bool
    health_observed_at: str
    machine_allowlist: tuple[str, ...]
    cost_rank: int
    latency_rank: int
    quota_pressure_rank: int
    quality_tier: int
    enforcement_mode: Literal["enforced", "shadow", "advisory"]
    identity_confidence: float
    model_card_hash: str
    endpoint_profile_hash: str
    capability_snapshot_hash: str


@dataclass(frozen=True)
class RoleAssignment:
    role: Role
    engine: str
    endpoint_id: str
    model: str
    family: str
    machine: str
    reason_code: str
    model_card_hash: str
    capability_snapshot_hash: str
    benchmark_version: str | None


@dataclass(frozen=True)
class DispatchPlan:
    decision: Decision
    conductor: SessionIdentity
    task: TaskIntent
    assignments: tuple[RoleAssignment, ...]
    policy_hash: str
    task_profile_hash: str
    capability_index_hash: str
    degraded_reasons: tuple[str, ...]


@dataclass(frozen=True)
class DispatchReceipt:
    receipt_id: str
    parent_session_id: str
    child_session_id: str
    role: Role
    task_id: str
    model: str
    family: str
    machine: str
    allowed_files: tuple[str, ...]
    worktree: str
    base_commit: str
    policy_hash: str
    created_at: str
    expires_at: str
```

The receipt hash binds task, child session, model, machine, worktree, file scope, base
commit, and policy version. A textual mention of delegation in a transcript is not a
receipt.

Only a root interactive session (`parent_session_id is None`) acquires the conductor
role automatically. A CLI launched by `conductor_ctl dispatch` is a child actor even if
it uses the same engine/model as the parent. This prevents the sentence "every starting
LLM is a conductor" from accidentally promoting every spawned worker into a second
conductor.

## 6. Routing policy

### 6.1 Task-to-builder matrix

The first implementation must treat the complete sanctioned arsenal as one builder pool.
The examples below are candidates, not fixed chains; the exact model identifiers and
seats come from the executable policy and fresh capability snapshot.

| Task class | Minimum capability | Example eligible builders | Conductor behavior |
| --- | --- | --- | --- |
| Read-only exploration | current conductor | current conductor | execute directly |
| Mechanical mutation | fast/grunt | Luna, Haiku, Kimi fast lane, Qwen/DeepSeek flash lane, eligible local model | delegate unless micro exemption applies |
| Standard implementation | balanced coding | Terra, Sonnet, Kimi 2.7 coding, Qwen 3.7, DeepSeek V4 Flash | delegate |
| Hard implementation | strong coding/reasoning | Terra high, Sonnet high, Qwen high-capability lane, separate Sol/Opus worker when genuinely required | delegate and integrate |
| Architecture | frontier reasoner | Sol, Opus, Gemini/other policy-approved architect | conduct directly if capable; otherwise delegate architect |
| Red-team/review | frontier reviewer, different family where required | Sol, Opus, Gemini, Kimi, Qwen or another independent eligible reviewer | never grade own builder output |
| PII/local-only | eligible local model | policy-approved Ollama/local models only | route local or queue |

Sol therefore does **not** own a private `Sol -> Terra -> Luna` cascade. That is only the
Codex subset of a fleet-wide candidate graph. Claude, Gemini, Kimi, Qwen, DeepSeek, Codex,
and local models are normalized into the same `EndpointCandidate` contract and compete on task
fit. Model names belong in policy data, never router branches.

Selection is lexicographic rather than based on a fabricated all-purpose score:

1. Reject endpoints that violate sovereignty, hard feature requirements, context/output
   bounds, machine, role, worktree, enforcement-adapter, verified identity, or
   fresh-health requirements.
2. Require a benchmarked task score at or above the task profile's quality floor. An
   unmeasured endpoint may enter shadow/probation, never a load-bearing lane.
3. Prefer the endpoint specialized for the task shape, using first-pass success and
   re-entry evidence rather than provider reputation.
4. Prefer already-paid subscription/token-plan/local capacity over incremental spend.
5. Prefer lower quota pressure, then lower expected total work, among equally capable
   candidates. Expected total work includes latency, likely retries, and review burden;
   low token price alone is not efficiency.
6. Apply campaign diversity and generator-not-grader constraints.
7. If still tied, use a stable policy order so identical inputs produce identical plans.

Provider is not a quality rank. Sonnet or Qwen may beat Terra for a specific task; Luna
or Haiku may beat every frontier model for a mechanical edit. The router records the
reason code for the chosen candidate and the rejected reason for every higher-ranked
alternative.

Classification is two-stage. The conductor submits a typed `TaskIntent`; a deterministic
policy floor then raises (but can never lower) the declared gear/capabilities based on
observable scope: sensitive paths, migrations, auth, dependency manifests, public APIs,
number of files, and requested operation. Natural-language intent alone never grants a
cheaper lane or a direct-write exemption.

### 6.2 Model Intelligence Registry

The router's unit of selection is a **model endpoint**, not a model name:

```text
TaskProfile
    x ModelCard
    x EndpointProfile (engine + harness + account class + node constraints)
    x fresh CapabilitySnapshot
    x BenchmarkSeries
    x privacy-safe OutcomeSeries
    x RoutingPolicy
        -> ranked EndpointCandidates + rejection reasons
```

This distinction is load-bearing. The same underlying model may expose native tool use,
subagents, resumable sessions, vision, a different context limit, or no enforceable
mutation hook depending on the CLI/harness and account surface. A model can therefore
have several endpoint profiles with different eligibility.

The MIR contains four evidence layers. Later layers do not erase earlier ones; conflicts
remain explicit:

| Layer | What it proves | What it does not prove |
| --- | --- | --- |
| `declared` | documented modality, limit, parameter, or intended role | that the current seat can invoke it or that it performs well |
| `probed` | exact endpoint identity, auth/access, CLI version, feature handshake, node availability | task quality from a ping or model listing |
| `benchmarked` | performance on a versioned, PII-free Nuzantara task suite with external deterministic grading | production reliability outside the measured distribution |
| `production` | first-pass success, retry, re-entry, latency, and failure outcomes from real routed work | capabilities that were never exercised |

Every capability assertion carries `kind`, `evidence_ref`, `observed_at`, optional
`expires_at`, and `confidence`. Hard capabilities with missing, stale, contradictory, or
self-reported-only evidence are ineligible. Soft preferences may remain `unmeasured` and
receive no positive score. The registry never converts `GET /models`, a CLI cache, a
marketing claim, or the model saying its own name into proof of access or quality.

#### Capability ontology

The ontology must cover at least these independently addressable dimensions:

- reasoning controls and supported effort levels;
- code implementation by stack: Python/FastAPI, TypeScript/React, tests/debugging,
  refactors, shell/infra, and large-repository navigation;
- architecture, synthesis, adversarial review, and instruction adherence;
- native tool calls, structured output, streaming, parallel calls, subagents, MCP,
  resumability, sandbox modes, and hook-enforcement compatibility;
- text, vision, PDF/document, image generation, audio, video, embedding, and OCR
  modalities;
- declared and empirically usable context/output limits, prompt caching/compaction, and
  tokenizer behavior;
- known invocation constraints and failure modes: allowed parameters, reasoning defaults,
  refusal semantics, tool-call reliability, aliases, and model-identity ambiguity;
- privacy/sovereignty eligibility, machine restrictions, account class, incremental cost
  class, quota window, p50/p95 latency, and health freshness;
- task-specific benchmark score, first-pass acceptance, retry/re-entry rate, grader
  findings, and sample size.

There is no single global intelligence or Elo score. A fast model may lead mechanical
edits and lose on migrations; a vision model may be eligible for OCR and forbidden from
code; a strong reasoner may remain ineligible when its harness cannot enforce file scope.

#### Task profiles and evidence-backed calibration

Each deterministic `TaskProfile` declares required and preferred features, minimum task
score, expected context, modality/tool needs, privacy class, maximum acceptable latency,
and whether probation endpoints are allowed. Initial scores come only from a versioned
benchmark suite built from redacted or synthetic Nuzantara-shaped tasks. Deterministic
tests, not the candidate model, grade functional correctness wherever possible; an
independent model family grades judgment tasks.

Production outcomes update a time-series calibration record, not the immutable model
card. Promotion follows `identity probe -> feature census -> benchmark -> probation ->
armed`; failures may demote an endpoint without rewriting its historical evidence. New
versions and aliases receive new card or endpoint identities rather than inheriting an
old score silently.

#### Initial compiled baseline (2026-08-21)

The initial MIR dataset in this worktree contains 80 abstract ModelCards and 81 concrete
EndpointProfiles. Abstract cards are deliberately non-invocable. After reconciling the
static roster with zero-token live inventory, only four endpoints retain automated
eligibility:

- `claude-glm-glm-5.2`;
- `qwen-deepseek-v4-flash-0731`;
- `qwen-qwen3.7-plus`;
- `qwen-qwen3.8-max`.

Every other endpoint remains catalogued but non-routable under an explicit state such as
`known_unmeasured`, `investigation_required`, `probation`, `manual_only`, `denied`,
`phantom`, or `listed_unexploited`. This is intentionally conservative: compiling a card
does not promote an endpoint. The baseline passes eight standard-library registry tests,
schema/JSON parsing, uniqueness checks, evidence-reference checks, and deterministic
index regeneration. It does **not** make the conductor operational; the router, runtime
snapshots, benchmark corpus, adapters, hooks, and three-node enforcement remain to be
built and armed.

Every plan returns the full ranked candidate list internally, including typed rejection
reasons such as `missing_native_tools`, `benchmark_unmeasured`, `identity_ambiguous`,
`context_insufficient`, `health_stale`, `privacy_ineligible`, or
`generator_family_conflict`. The persisted audit record contains hashes and reason codes,
not prompts, code, PII, or secret-bearing command lines.

### 6.3 Pure routing function

```python
def plan_dispatch(
    *,
    session: SessionIdentity,
    task: TaskIntent,
    candidates: tuple[EndpointCandidate, ...],
    policy: RoutingPolicy,
) -> DispatchPlan:
    if task.task_class is TaskClass.READ_ONLY:
        return allow_conductor(session, task, policy)

    eligible = filter_by_sovereignty_capability_and_health(
        task=task,
        candidates=candidates,
        policy=policy,
    )

    if task.mutation:
        builder = choose_best_eligible_builder(eligible, task, policy)
        if builder is None:
            return degraded_or_queue(session, task, policy)
        return require_delegation(session, task, builder, policy)

    if task.task_class is TaskClass.ARCHITECTURE:
        return route_architect_if_needed(session, task, eligible, policy)

    return route_review(session, task, eligible, policy)
```

The router is pure: no subprocesses, filesystem writes, SSH, or network calls. Live
observations are inputs. This makes every policy decision table-testable.

### 6.4 Direct-write exemptions

An exemption is not a global environment variable. It is a scoped record with one of
these reason codes:

- `micro_change`: one file, at most 20 changed lines, no dependency/config/schema/auth/
  migration/security surface, and Gear 1.
- `integration_only`: conductor applies a bounded integration patch after a builder
  receipt; it may not replace the builder's assigned scope.
- `worker_unavailable`: every eligible builder has a fresh negative health observation;
  the session is visibly degraded and the exemption expires in 15 minutes.
- `emergency_recovery`: active incident, explicit incident ID, bounded files, automatic
  expiry.

`micro_change` reconciles role discipline with the anti-waste rule: a one-line typo does
not need a second 100k-token context. Sol still delegates normal feature/debug work.
Hooks reject unknown reason codes, wildcard file scopes, expired records, and exemptions
whose base commit no longer matches.

## 7. Session lifecycle

```text
Zero starts any supported CLI
          │
          ▼
  nuz_session bootstrap
  - resolve engine/model/host/repo
  - create session manifest
  - starter becomes conductor
          │
          ▼
  conductor_ctl plan
  - classify task/gear/mutation
  - join task profile + MIR + fresh endpoint snapshot
  - rank architect/builder/grader endpoints with evidence
          │
          ├── read-only ───────────────► conductor executes
          │
          └── mutation
                 │
                 ▼
          fleet_dispatch place
          - capacity
          - worktree
          - file-scope collision
                 │
                 ▼
          conductor_ctl dispatch
          - spawn selected CLI/model
          - persist receipt
                 │
                 ▼
          builder mutates/tests in lane
                 │
                 ▼
          result receipt + diff evidence
                 │
                 ▼
          conductor synthesizes/integrates
                 │
                 ▼
          independent grader + final gate
```

The state machine is:

```text
BOOTSTRAPPED -> PLANNED -> DISPATCHED -> BUILT -> VERIFIED -> CLOSED
                    \-> DEGRADED -> QUEUED
```

State transitions are atomic and monotonic. Repeated commands are idempotent. A child
process cannot promote the parent session's state beyond `BUILT`.

Dispatch uses a parent-child handshake:

1. The parent writes an `ISSUED` receipt after placement succeeds.
2. The dispatcher launches the child with `NUZ_AGENT_ROLE`, `NUZ_AGENT_SESSION_ID`,
   `NUZ_PARENT_SESSION_ID`, and `NUZ_DISPATCH_RECEIPT_ID` set explicitly.
3. The child's startup adapter validates the on-disk receipt, policy hash, base commit,
   worktree, model assignment, and file scope, then transitions it to `ACTIVE`.
4. Pre-mutation hooks validate state from disk; environment variables are locators, not
   authority.
5. On completion, the child records evidence hashes and transitions to `COMPLETED`.
6. The parent may request a separate, bounded `integration_only` grant. A builder receipt
   never authorizes conductor writes by itself.

## 8. Universal launcher and engine adapters

### 8.1 Launcher

Supported entry points:

```bash
python3 scripts/nuz_session.py codex --model gpt-5.6-sol
python3 scripts/nuz_session.py claude --model opus
python3 scripts/nuz_session.py agy
python3 scripts/nuz_session.py kimi
```

The launcher exports only non-secret context:

```text
NUZ_CONDUCTOR_SESSION_ID
NUZ_CONDUCTOR_ENGINE
NUZ_CONDUCTOR_MODEL
NUZ_CONDUCTOR_FAMILY
NUZ_CONDUCTOR_POLICY_HASH
NUZANTARA_ROOT
```

It then `exec`s the requested CLI. Direct starts remain supported: a native SessionStart
hook reconstructs identity when possible and marks the session `identity_degraded` when
the effective model cannot be proven. It never guesses from the CLI flag alone.

### 8.2 Hook adapters

Claude and Codex adapters translate native hook payloads into:

```json
{
  "event": "pre_mutation",
  "session_id": "...",
  "tool": "Edit",
  "cwd": "...",
  "files": ["relative/path.py"],
  "command_class": null
}
```

The core returns one canonical decision:

```json
{
  "decision": "block",
  "reason_code": "delegation_receipt_missing",
  "message": "Standard mutation must be executed by the assigned builder",
  "required_action": "conductor_ctl dispatch --task <id>"
}
```

For `agy` and Kimi, which do not expose the same complete hook surface, the universal
launcher is the enforcement boundary. Their mutation-capable subprocess/tool command
must pass through `conductor_ctl authorize`. An engine without a provable enforcement
adapter is declared `advisory_only` and cannot receive a mutation role.

## 9. Semantic mutation gate

The current line-count gate should be replaced, not extended. Transcript length may
remain an observability metric but must not authorize code mutation.

`conductor_ctl hook pre-mutation` performs only local, bounded work:

1. Resolve session and policy hash.
2. Normalize affected repo-relative files.
3. Allow read-only tools immediately.
4. If this is a builder child session, require a valid unexpired receipt whose file
   scope contains every target.
5. If this is the conductor session, require either:
   - a valid integration receipt covering the target; or
   - a valid typed direct-write exemption.
6. Refuse writes in the main checkout using the existing worktree discipline.
7. Emit a structured decision without prompt content or PII.

Shell commands require a conservative command classifier. Known read-only commands are
allowed. Known mutation commands (`sed -i`, redirect, package install, `git commit`,
formatters, generators, migrations) require authorization. Unknown shell syntax is
`cannot_verify`, not silently read-only.

## 10. Model intelligence refresh without token waste

The MIR separates slow-changing knowledge from live state:

- **Model cards** are reviewed, version-controlled descriptions of the abstract model.
- **Endpoint profiles** describe the concrete invocation surface and its enforcement,
  account-class, engine, and node constraints.
- **Capability snapshots** are TTL-bound observations of endpoint identity, access,
  feature handshakes, CLI version, health, and quota pressure.
- **Benchmark series** are append-only results keyed by model-card hash, endpoint-profile
  hash, task-profile hash, repository fixture version, and grader version.
- **Outcome series** hold only privacy-safe operational counters and reason codes.

`conductor_ctl probe` refreshes zero-token/static facts first: executable/version,
configuration shape, installed-model inventory, endpoint metadata, and auth-state checks
that do not invoke inference. Session bootstrap reads the cached snapshot; it does not
spend an LLM turn. A minimal live inference probe is reserved for stale or ambiguous
state, explicit health runs, new endpoint onboarding, and recovery from a real failure.

`conductor_ctl benchmark` is an explicit, bounded job, never a hook side effect. It uses
the same frozen PII-free task packet for competing endpoints, records token/wall-time
usage when the harness exposes it, runs deterministic tests, and writes an immutable
result. Benchmarks expire or are invalidated when model identity, CLI/harness major
version, invocation profile, task suite, or relevant policy changes.

The router never treats a model cache entry as proof that authentication/quota is live.
It also never treats a model CLI flag as proof of the effective served model unless the
provider returns independently verifiable identity metadata. A model-list endpoint proves
discovery only, not access; a successful `PONG` proves reachability only, not coding
quality; a model's prose about its own features proves nothing.

Mini's missing Kimi executable, a revoked Codex token, a locked Keychain, an alias silently
serving another tier, or a tool-use feature absent from one harness therefore becomes a
typed endpoint observation instead of a silent fallback or inherited family claim.

## 11. State, receipts, and privacy

Session state lives outside the repository:

```text
~/.local/state/nuzantara/conductor/<session-id>/
├── manifest.json
├── decisions.jsonl
├── receipts.jsonl
├── hook-observations.jsonl
└── evidence.json

~/.local/state/nuzantara/conductor/
├── install-state.json             # current generation/policy binding, mode 0600
├── .install.lock                  # persistent inode; kernel lock owns liveness
└── install-backups/               # rollback journal and prior bytes
```

Files are user-only (`0700` directory, `0600` files), atomically replaced where mutable,
and append-only where audit history matters. Payloads contain task IDs, hashes, relative
file paths, model/family names, reason codes, timings, and verdicts. They do not contain
raw user prompts, code bodies, client data, credentials, or OSINT.

Receipts use keyed HMAC only if an existing local secret authority can provision it
without creating a new secret distribution problem. The minimum viable implementation
uses SHA-256 content binding plus ownership/permission checks and never claims
cryptographic signer identity it cannot prove.

### 11.1 Producer-consumer map

| Artifact | Producer | Consumer | Durability |
| --- | --- | --- | --- |
| Session manifest | launcher/start adapter | router, hooks, doctor | atomic local JSON |
| Dispatch receipt | dispatcher | child startup, mutation gate, verifier | append-only local JSONL + indexed manifest state |
| Completion evidence | builder adapter | conductor, grader, final gate | content hashes and bounded metadata |
| Model card | reviewed registry source | capability-index generator, benchmark runner | versioned repository JSON |
| Endpoint profile | reviewed registry source + fleet topology | probe, router, doctor | versioned repository JSON |
| Task profile | policy maintainer + benchmark owner | classifier, router, benchmark runner | versioned repository JSON |
| Benchmark result | explicit benchmark runner + external grader | capability-index generator, router | append-only local evidence + reviewed aggregate |
| Outcome series | completion/verifier adapters | calibration job, doctor | privacy-safe append-only counters |
| Capability snapshot | explicit probe/health wrapper | router, doctor | TTL-bound local JSON |
| Executable policy | topology projection generator | router, hooks, CI | versioned repository JSON |
| Fleet conformance report | doctor | conductor and verification gate | ephemeral output or explicitly captured evidence |

No artifact has an undefined consumer. No session prompt or code body is copied into the
control-plane state.

## 12. Three-machine installation

The repository is the SSOT; home files are generated projections.

```bash
# Run with the repository's Python >=3.11; the installer attests this exact
# interpreter in the generated shim rather than relying on PATH's python3.
.venv/bin/python scripts/install_conductor_hooks.py --check
.venv/bin/python scripts/install_conductor_hooks.py --apply
.venv/bin/python scripts/conductor/conductor_ctl.py status --require wired
.venv/bin/python scripts/conductor/conductor_ctl.py status --require observed
.venv/bin/python scripts/conductor/conductor_ctl.py fleet-doctor --require static
```

In SHADOW, `doctor`, `status`, `smoke`, and `fleet-doctor` report
`static_registry_valid`, `shadow_wired`, `shadow_observed`, and `enforced` as
separate facts. `operational` remains false until an enforcing policy is
actually active; a manual-origin wrapper or a static registry is never evidence
of a native hook. The default requirement remains `static` for compatibility;
automation must select `--require wired|observed|shadow|enforced` explicitly.
Exit status is `0` only when the selected threshold is met, `1` when it is
verifiably unmet, and `2` when the local host or contract cannot be verified.

Codex native evidence is captured after a completed collaboration dispatch via
`PostToolUse`, where the function call can be correlated with its result. A
`PreToolUse` callback or an arbitrary non-empty `0600` file is never counted as
`shadow_observed`. Every accepted observation is bound to the current installer
generation and policy hash and is rejected when malformed, replayed, stale, or
from a previous generation.

Installer requirements:

1. Resolve the repository from `git rev-parse` or `$HOME/nuzantara`; never commit an
   absolute `/Users/...` path.
2. Detect `hostname` and home directory; M5's `balizero` user is not a special-case string
   copied into templates.
3. Merge managed hook entries idempotently while preserving unrelated home hooks.
4. Store a managed-block version and policy hash.
5. Install a small stable shim in `~/.local/bin`, not duplicate policy code into home.
6. Support `--check`, `--diff`, `--apply`, and `--rollback <backup>`.
7. Re-run `--check` after apply and require byte-equivalent managed sections.
8. Reject an installer runtime below Python 3.11; the generated shim executes the
   compatible interpreter that performed the installation.
9. Derive local host identity from hostname plus effective UID. Reject a claimed
   `--machine` mismatch; only `--diff --offline-target --machine <node>` may render
   an explicitly offline target and it never attests or applies that node.
10. Hold an owner-only interprocess lock across the complete read/backup/write/verify
    or rollback transaction. Compare digests before atomic replacement so a
    concurrent hook or generation mutation fails without losing the other writer.
11. Keep paths redacted from public JSON. Absolute local paths appear only with the
    explicit `--verbose-paths` diagnostic flag.

Target behavior:

| Node | Interactive conductor | Builder placement | Heavy/local lanes |
| --- | --- | --- | --- |
| Air-M5 | primary | light code/edit lanes | route to Pro/Mini |
| Pro | supported | standard and hard lanes | supported |
| Mini-Pro2 | supported/headless | batch and isolated lanes | preferred where eligible |

Deployment is two-phase:

1. **Shadow:** adapters calculate and log decisions but never block. Compare planned
   routing with actual mutations for at least 30 representative sessions.
2. **Enforce:** arm per engine and node only after guilt/innocence canaries pass. A failed
   node remains visibly `SHADOW` or `UNARMED`; no fleet-wide green claim is allowed.

## 13. CLI surface

```text
conductor_ctl bootstrap      create/recover session identity
conductor_ctl classify       print deterministic TaskIntent
conductor_ctl plan           print DispatchPlan; no mutation
conductor_ctl place          call fleet_dispatch with declared scope
conductor_ctl dispatch       run selected CLI and create receipt
conductor_ctl authorize      authorize one bounded mutation
conductor_ctl exempt         create typed, scoped, expiring exemption
conductor_ctl complete       close a child receipt with evidence hashes
conductor_ctl verify         verify state/receipt/policy invariants
conductor_ctl probe          refresh local capability snapshot
conductor_ctl models         list cards/endpoints/evidence/rejection reasons
conductor_ctl benchmark      run a bounded versioned capability suite explicitly
conductor_ctl doctor         local or --fleet conformance report
```

Every command supports `--json`. Human output is concise; machine output has versioned
schemas and stable reason codes.

## 14. Test strategy

### 14.1 Unit and table tests

- Sol conductor + mechanical mutation -> Luna builder, direct write denied.
- Sol conductor + standard mutation -> Terra builder, direct write denied.
- Sol conductor + task where Sonnet/Kimi/Qwen has the best measured fit -> that
  cross-provider endpoint wins; no Codex-family preference is applied.
- Terra/Luna/Claude/agy/Kimi starter -> remains conductor; builder is a separate child.
- Underpowered conductor + architecture -> architect routed upward; conductor retained.
- Read-only exploration -> no dispatch required.
- PII task + cloud-only candidates -> queue, no cloud fallback.
- Builder family equals grader family -> plan rejected.
- Missing/expired/wrong-policy/wrong-commit/wrong-file receipt -> write rejected.
- Valid receipt within scope -> builder write allowed.
- Micro exemption crossing 20 lines or a sensitive path -> rejected.
- Unknown shell command -> cannot-verify, never mislabeled read-only.
- Same model through two harnesses with different tool support -> only the qualifying
  endpoint is eligible.
- Model-list presence without an access probe -> endpoint remains unavailable.
- Successful reachability probe without a task benchmark -> probation only.
- Stale, contradictory, self-reported, wrong-hash, or inherited-alias capability -> hard
  requirement rejected.
- Cheaper endpoint with high measured retry/re-entry burden -> loses to lower expected
  total-work endpoint.
- Model/version change -> historical benchmark is retained but not inherited.

### 14.2 Installer and adapter tests

- Temporary homes for `nuzantara`-style and `balizero`-style paths.
- Existing unrelated hooks preserved.
- Second apply produces zero diff.
- Codex and Claude fixture payloads produce the same canonical decision.
- Missing hook file is `UNARMED`, not green.
- Disarmed environment variable cannot silently convert an enforcement gate to allow.

### 14.3 Fleet canaries

On each node and each supported engine:

1. Start a session and prove the starter is recorded as conductor.
2. Attempt a standard direct mutation; prove it is blocked.
3. Dispatch the selected builder into an isolated worktree; prove its scoped mutation is
   allowed.
4. Attempt an out-of-scope builder write; prove it is blocked.
5. Complete the builder and invoke an independent grader.
6. Compare policy hash and managed hook version across all three nodes.

## 15. Metrics and acceptance criteria

The design is operational only when all of these are measured:

| Metric | Acceptance |
| --- | --- |
| Delegable conductor mutation rate | `0%` in enforcement mode |
| Builder receipt coverage | `100%` of non-exempt code mutations |
| Invalid out-of-scope write blocks | `100%` guilt canaries |
| Innocent read-only false blocks | `0%` |
| Policy hash drift across fleet | `0` armed nodes |
| Managed hook drift | `0` armed nodes |
| Router latency | p95 `<100 ms` local, excluding capability refresh |
| Bootstrap overhead | p95 `<1 s`, excluding an explicitly requested live LLM probe |
| PII/prompt bodies in state | `0` occurrences in audit corpus |
| Fan-out waste | fan-out only for at least three independent units |
| Armed endpoint registry coverage | `100%` have model card, endpoint profile, and fresh identity snapshot |
| Load-bearing task-score coverage | `100%` have a current benchmark for the selected task profile |
| Unproven hard-capability assumptions | `0` |
| Decision evidence binding | `100%` contain policy/task/card/endpoint/snapshot/benchmark hashes |
| Capability alias inheritance | `0` unreviewed transfers across model/version identities |

The before/after benchmark must record, for a representative session corpus: conductor
tokens, builder tokens, wall time to first mutation, total wall time, direct conductor
write count, dispatch count, retry count, first-pass acceptance, re-entry, and final-gate
outcome. Token reduction is not accepted if defect/re-entry rate increases. Routing regret
is estimated through a bounded sampled bake-off, not by duplicating every production task
across every model.

## 16. Build sequence

Implement in the following narrow slices:

1. **Capability ontology, model cards, endpoint profiles, and task profiles** — compile the
   complete sanctioned roster; unknowns remain explicitly unmeasured.
2. **Registry schemas, integrity tests, and generated capability index** — no routing yet.
3. **PII-free benchmark fixtures and baseline run** — establish task-specific quality and
   expected-work evidence before choosing defaults.
4. **Core contracts and pure router** — no hooks or home mutation.
5. **Policy schema and generated executable projection** — remove stale runtime prose.
6. **Session state and receipts** — atomic, private, idempotent.
7. **Codex adapter in shadow mode** — prove Sol can select any qualifying fleet endpoint,
   not only Terra/Luna.
8. **Claude adapter in shadow mode** — same core decisions, different payload parser.
9. **Universal launcher and subprocess adapter** — `agy`/Kimi supported without pretending
   they expose native hook parity.
10. **Installer and fleet doctor** — path-aware, managed-block merge, rollback.
11. **Three-node shadow benchmark** — 30 representative sessions.
12. **Per-node enforcement canaries** — arm only proven combinations.
13. **Delete/supersede legacy gates** — only after every consumer is mapped and the new
    enforcement path is live.

Each slice is one concern, one worktree, one PR, with generator-not-grader verification.
Do not combine policy, installer, and enforcement into a single large change.

## 17. Explicit non-goals

- No new central scheduler, daemon, Redis polling loop, or LaunchAgent.
- No automatic fan-out for every task.
- No model quality judgment derived solely from brand names.
- No manually maintained universal score or router branch per model name.
- No inheritance of capability or benchmark evidence across an unverified alias/version.
- No live LLM probe before every tool call.
- No duplicate implementation of worktree placement or file collision logic.
- No silent global bypass comparable to `ORCHESTRATE_GATE_OFF=1`.
- No Codex-only routing funnel. Sol may delegate to the full sanctioned builder fleet.
- No forced use of Sol for ordinary coding when any lower-cost eligible builder is sufficient.
- No replacement of the existing final-gate doctrine in this design.

## 18. Final assessment

The organization has already made the correct conceptual decision: conductor is a role,
generator and grader are separate, and task-shaped routing is preferable to reflexively
spending the strongest model. The implementation has not caught up with the doctrine.

The proposed control plane closes that gap with one evidence-backed Model Intelligence
Registry, typed task profiles, one policy, one pure router, one session receipt protocol,
thin engine adapters, and an idempotent three-node installer. It makes
the intended behavior measurable: a Sol session can own the work without spending Sol
tokens on code that Terra, Luna, Sonnet, Haiku, Kimi, Qwen, DeepSeek Flash, or another
eligible builder can implement, and the same law holds when the session starts from any
other supported LLM.
