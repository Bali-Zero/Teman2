# team-bot (Bot B — agentic team operator)

Standalone app, per `docs/plans/2026-08-25-due-bot-live/MANDATE.md` F4: intended
home is `127.0.0.1:8765` on the Mini, next to the local Qwen3-14B inference
plant (F8). **This directory ships only lane B3's tool-registry unit** —
`team_bot/registry/` (the ten-tool risk-tiered registry, F5) and
`team_bot/loop/` (the `ToolDecision` schema shared with B4's serving
contract, plus the `ActionClaimGate` closing the gc-015 defect class). The
webhook, identity→principal mapping (F7), confirmation state machine (F6),
and sqlite state + Mini→Pro replication are separate units of the same B3
lane and are **not** in this directory yet.

## Everything here is inert

No server, no CRM client, no I/O. `registry/` is pure data (frozen pydantic
models describing ten tool contracts); `loop/` is pure functions (parse a raw
model turn, evaluate a reply against what actually executed). Nothing in this
package is imported by any running service — there is no live path to wire a
dark flag into yet. `team_bot/flags.py` defines the flag future wiring must
check (`is_team_bot_enabled()`, mirrors
`backend/services/rag/agentic/team_crm_tools.py::is_team_crm_tools_enabled()`),
default OFF, so the loop/webhook units that come next have it ready rather
than inventing their own.

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

## Layout

```
team_bot/
  flags.py            dark-flag helper (default OFF), for future wiring
  registry/
    envelope.py        shared enums, ID patterns, common response envelope (Qwen §4 verbatim)
    tools.py            RiskTier / ConfirmPolicy / ToolSpec + the ten frozen ToolSpec entries
  loop/
    tool_decision.py    ToolDecision — parses one raw OpenAI-compatible turn, enforces
                         single-tool-call (tool_calls[0]) since B4 measured that
                         `parallel_tool_calls: false` is honored by neither llama.cpp nor Ollama
    claim_gate.py        ActionClaimGate — blocks a reply that claims a completed action
                         when nothing executed this turn (closes gc-015)
tests/
  test_registry.py
  test_tool_decision.py
  test_claim_gate.py
```
