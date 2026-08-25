# team-bot (Bot B — agentic team operator)

Standalone app, per `docs/plans/2026-08-25-due-bot-live/MANDATE.md` F4: intended
home is `127.0.0.1:8765` on the Mini, next to the local Qwen3-14B inference
plant (F8). **This directory ships lane B3's units built so far**: the
tool registry (`team_bot/registry/`, F5), the typed tool loop
(`team_bot/loop/` — `ToolDecision`/`ActionClaimGate` and, as of the
directive #1 §2 amendment, the multi-step-reads type split), and F6's
confirmation-gated mutation state machine (`team_bot/confirmation/` — data
shape, sqlite CAS store, encryption, confirm-code parsing, server-authored
outcome text, and the reply-composition structural fix). The webhook and
identity→principal mapping (F7), and sqlite Mini→Pro replication, are
separate units of the same B3 lane and are **not** in this directory yet.

## `registry/`/`loop/`/`confirmation/` are inert; `executor/` is not (lane B9)

`registry/` is pure data (frozen pydantic models describing ten tool
contracts); `loop/` is pure functions (parse a raw model turn, evaluate a
reply against what actually executed); `confirmation/`'s sqlite store is
I/O but never a network call. **This is no longer true of the package as
a whole**: `team_bot/executor/` (lane B9, F5's "the CRM endpoints" — see
its own module docstrings for the full account) is real, importable,
network-carrying code — an `httpx.AsyncClient`-backed `BackendClient`
calling the Fly backend's own REST endpoints (never the `nuzantara-mcp`
server; RECON domain 4), gated behind `team_bot.flags.is_team_bot_enabled()`
and `is_team_bot_read_tools_enabled()` (both default OFF), and wired for
exactly ONE of the ten tools — `get_required_documents` (R0). The other
nine registered tool names have no `executor/tools/<name>.py` module yet
and return `ExecutorErrorCode.NOT_IMPLEMENTED`, not a crash or a guess.
Still nothing here is imported by a running webhook/loop RUNTIME (that
piece — F7's identity mapping plus the actual model-driven loop — is a
separate, not-yet-built B3 unit), but "nothing in this package does I/O"
is no longer accurate as a description of the package's own contents.

`team_bot/flags.py` defines the flags this and future wiring must check
(`is_team_bot_enabled()`, mirroring
`backend/services/rag/agentic/team_crm_tools.py::is_team_crm_tools_enabled()`;
`is_team_bot_multistep_reads_enabled()`/`max_read_steps()` for the
directive #1 §2 amendment below; `is_team_bot_read_tools_enabled()`, lane
B9's first real read of the previously-registered-but-unwired
`TEAM_BOT_READ_TOOLS_ENABLED` switch), all default OFF.

## Naming note — Qwen §4 verbatim, not the MANDATE's F5 prose shorthand

MANDATE.md F5's own paragraph uses a dotted-namespace shorthand
(`client.lookup`, `practice.status_change`, a `practice.open_preview` /
`practice.open_commit` split) that does not 1:1 match either the tool names
or the risk tiers in research capture §4 (Qwen)'s verbatim JSON schemas and
"Tool summary" table — e.g. Qwen tiers `update_practice_status` and
`open_practice` both R3, while F5's prose groups the status-change tool
under "R2 confirmed writes" and splits practice-opening into two tools.

This registry implements **Qwen §4's ten tools verbatim** — exact names,
exact JSON schemas, exact per-tool risk tier and confirmation nuance — for
one concrete, load-bearing reason: lane B4 already ran real empirical
golden-suite evaluations (`docs/plans/2026-08-25-due-bot-live/evidence/
b4b-golden-cases-kimi.json` + the two `14b-*-golden.json` result files)
against exactly this name/schema/tier set on the actual Qwen3-14B model
across two serving stacks. Renaming or resplitting tools here would silently
disconnect this registry from that measured evidence — including the gc-015
fixture `claim_gate.py` is built to close — and break the cross-lane law
that B3 and B4 "share only the ToolDecision schema and the serving endpoint
contract" (MANDATE.md "Lanes"). F5's prose is read as a compressed paraphrase
of the same ten tools, not a second, independently-binding technical spec.
Flagged to the orchestrator per the brief's instruction to surface any case
where closing gc-015 "turns out to require touching something frozen."

## Multi-step reads (owner directive #1 §2, 2026-08-25 — amends F4/F5)

"One tool per turn" now applies ONLY to mutations (always confirmed, unchanged). Reads/searches
may chain across multiple sequential turns, gated by the dark flag
`TEAM_BOT_MULTISTEP_READS_ENABLED` (default off — `flags.py::max_read_steps()` returns exactly
1, today's original behavior, whenever it is off, regardless of `TEAM_BOT_MAX_READ_STEPS`'s
value). See `docs/plans/2026-08-25-due-bot-live/ops/KILL-SWITCHES.md` for the registered switch.

This is implemented as a TYPE SPLIT, not a validator, so `tool_decision.py` is untouched:
`turn_plan.py` adds `ReadPlan` (an ordered, bounded sequence of read steps) alongside
`MutationDecision` (exactly one call — structurally incapable of representing more than one,
which is what makes "one mutation per turn" unrepresentable-if-violated rather than merely
checked) and `FinalAnswer`. `loop_detector.py` adds `detect_stuck_loop`, a narrow guard that
flags a chain only when the identical call repeats on the CONSECUTIVE tail — deliberately not
triggered by an ordinary non-consecutive repeat (e.g. the same client looked up for two
different practices).

## The executor seam (lane B9)

`docs/plans/2026-08-25-due-bot-live/RECON-domains-2-4.md`'s own framing:
"The team bot cannot call anything ... the bottleneck is not the content
of domains 2-4 ... that layer is the keystone lane." `team_bot/executor/`
is that layer — it turns one validated `ProposedToolCall`
(`team_bot.loop.tool_decision`) into a `ToolResult`
(`team_bot.registry.envelope`) via `ToolExecutor.execute`, chaining:
feature flags → F5 registry + per-tool binding lookup → the local,
early-deny-only scope gate (`scope_gate.py`, F7) → argument re-validation
→ auth resolution (`auth.py`'s `TokenProvider` — F7's identity mapping is
NOT built here; `NullTokenProvider` fails every call closed until it is)
→ the network call (`http_client.py`'s `BackendClient`) → untrusted-
response validation (`response_mapping.py`, F4). A closed error
vocabulary (`errors.py`'s `ExecutorErrorCode`) is the ONLY thing
`ToolExecutor.execute` ever returns for a failure — it never raises for a
business-outcome failure, only for a genuinely unexpected bug (caught at
one deliberate chokepoint and turned into `INTERNAL`).

**One tool wired, nine deliberately not**: `get_required_documents` (R0)
runs end to end against a fake `httpx.MockTransport` (no test in this
suite touches a real network — B6 law). Its own module docstring
(`executor/tools/get_required_documents.py`) records a real discovery: no
LIVE backend endpoint answers this tool's frozen, `practice_type`-only
question today — `crm_practices.py:2122`'s real, live `required-documents`
endpoint is keyed by `practice_id` instead, a genuinely different query
domain 2's "missing: X" actually needs, and building the frozen tool's
OWN static reference data would mean this lane inventing which documents
a KITAS/work-permit/company-setup application requires, which is a
content decision outside an executor-seam lane's standing to make. Read
that docstring before wiring either this tool for real or the next one.

**Known gap, not resolved here**: `confirmation/store.py`'s
`SqlitePendingActionStore.execute`'s injected `execute_fn` contract is
SYNCHRONOUS; this package's `BackendClient` is `httpx.AsyncClient`-based
and async throughout. A future mutation-tool lane (R1/R2/R3, gated by
`TEAM_BOT_MUTATIONS_ENABLED`, not built here) will need to resolve that
mismatch — most likely a sync `httpx.Client` variant for the mutation
execution path specifically, not forcing this read-path executor to serve
both.

## Layout

```
team_bot/
  flags.py            dark-flag helpers (default OFF): TEAM_BOT_ENABLED,
                       TEAM_BOT_MULTISTEP_READS_ENABLED + max_read_steps(),
                       TEAM_BOT_READ_TOOLS_ENABLED (lane B9)
  registry/
    envelope.py        shared enums, ID patterns, common response envelope (Qwen §4 verbatim)
    tools.py            RiskTier / ConfirmPolicy / ToolSpec + the ten frozen ToolSpec entries
  loop/
    tool_decision.py    ToolDecision — parses one raw OpenAI-compatible turn, enforces
                         single-tool-call (tool_calls[0]) since B4 measured that
                         `parallel_tool_calls: false` is honored by neither llama.cpp nor Ollama
    claim_gate.py        ActionClaimGate — blocks a reply that claims a completed action
                         when nothing executed this turn (closes gc-015)
    turn_plan.py        ReadStep/ReadPlan/MutationDecision/FinalAnswer/classify_step —
                         the structural type split for the multi-step-reads amendment above
    loop_detector.py     detect_stuck_loop — the read chain's loop guard
  confirmation/
    models.py, store.py, crypto.py, idempotency.py, confirmation_input.py, outcomes.py,
    reply_composer.py — F6's confirmation-gated mutation state machine (data shape, CAS
    behavior, encryption, confirm-code parsing, server-authored outcome text, and the
    structural reply-composition fix that supersedes claim_gate.py as the primary control)
  executor/            lane B9 — the executor seam (see section above)
    errors.py            ExecutorErrorCode — the closed error vocabulary
    auth.py              AuthMaterial / TokenProvider / NullTokenProvider (F7 seam, not F7 itself)
    scope_gate.py         the local, early-deny-only scope gate (F7)
    http_client.py        BackendClient — the ONE persistent httpx.AsyncClient
    response_mapping.py    BackendCallResult -> ToolResult (untrusted-response validation, F4)
    tool_executor.py       ToolExecutor — the class that chains all of the above
    tools/
      get_required_documents.py  args/result models + the one wired tool's network call
tests/
  test_registry.py
  test_tool_decision.py
  test_claim_gate.py
  test_turn_plan.py
  test_loop_detector.py
  test_flags.py
  test_confirmation_*.py, test_outcomes.py, test_reply_composer.py, test_idempotency.py
  executor/             lane B9's suite (guilt+innocence pairs throughout;
                         mutation-verified — see B9's own report, not committed here)
```

The webhook and identity→principal mapping (F7) are not in this directory yet.
