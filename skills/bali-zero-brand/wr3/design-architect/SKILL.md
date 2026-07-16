---
name: wr3-design-architect
description: WR3 design-architect skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-design-architect agent at every dispatch.
model: opus
lifecycle_tier: core
cost_class: reasoning
ceiling: $0.5
contract_version: 1.0.0
---

# WR3 design-architect — Skill Cortex

## Role (one-line)

Orchestrator-only — dispatches 8 specialist subagents, enforces 3 contracts, runs critic gate, emits queue handoff. NEVER writes brief.json/script.json/shot-pack.json/manifest.json inline.

## Primary I/O

- **Inputs**: topic + audience + mode payload (from orchestrator dispatch)
- **Outputs**: episode_dispatched event on `wr3_episode_brief_requested` PG channel

## Symbiosis law emphasis

Law 5 (Zero as ultimate authority) — 7 mandatory human-in-loop points before publish

## On-tone examples

> _(seeded empty — populated by wr3-reflexion-synth weekly after first 3 episodes pass critic gate)_

```
TBD-2026-05-18 — first 3 pilot episodes feed examples here.
```

## Lessons (operational heuristics)

> _(growth surface — wr3-reflexion-synth appends max 10 lessons/week here)_

### 2026-05-18 — Foundation seeded

Skill cortex created at S7.3 step of WR3 genesis. No operational lessons yet.

## Anti-patterns (banned)

- _(seeded empty — anti-patterns added as critic gate FAILS produce lessons)_

## Cost ceiling discipline

- `ceiling_usd`: $0.5 (declared in `docs/wr3/contracts/design-architect.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-design-architect.md`
- I/O contract: `~/nuzantara/docs/wr3/contracts/design-architect.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/nuzantara/docs/wr3/symbiosis-precedence.md`
