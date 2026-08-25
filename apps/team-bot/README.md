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

## Everything here is inert

No server, no CRM client, no I/O. `registry/` is pure data (frozen pydantic
models describing ten tool contracts); `loop/` is pure functions (parse a raw
model turn, evaluate a reply against what actually executed). Nothing in this
package is imported by any running service — there is no live path to wire a
dark flag into yet. `team_bot/flags.py` defines the flags future wiring must
check (`is_team_bot_enabled()`, mirroring
`backend/services/rag/agentic/team_crm_tools.py::is_team_crm_tools_enabled()`;
`is_team_bot_multistep_reads_enabled()`/`max_read_steps()` for the
directive #1 §2 amendment below), all default OFF, so the loop/webhook
units that come next have them ready rather than inventing their own.

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

## Layout

```
team_bot/
  flags.py            dark-flag helpers (default OFF): TEAM_BOT_ENABLED,
                       TEAM_BOT_MULTISTEP_READS_ENABLED + max_read_steps()
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
tests/
  test_registry.py
  test_tool_decision.py
  test_claim_gate.py
  test_turn_plan.py
  test_loop_detector.py
  test_flags.py
  test_confirmation_*.py, test_outcomes.py, test_reply_composer.py, test_idempotency.py
```

The webhook and identity→principal mapping (F7) are not in this directory yet.
