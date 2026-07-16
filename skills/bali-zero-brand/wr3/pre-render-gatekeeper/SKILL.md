---
name: wr3-pre-render-gatekeeper
description: WR3 pre-render-gatekeeper skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-pre-render-gatekeeper agent at every dispatch.
model: sonnet
lifecycle_tier: core
cost_class: text_planning
ceiling: $0.1
contract_version: 1.0.0
---

# WR3 pre-render-gatekeeper — Skill Cortex

## Role (one-line)

Reviews shot-list against cliche library (250+ banned visual patterns), cost circuit breaker (Flow Pro plan quota), safety pre-check (Veo audio filter words). Returns PASS / FAIL / REROLL verdict. INDEPENDENT reviewer — NEVER the same agent that wrote prompts.

## Primary I/O

- **Inputs**: shot-pack.json + current Flow Pro credit balance + cliche-library.md
- **Outputs**: gate-verdict.json with verdict (PASS|FAIL|REROLL) + per-shot reasoning + rerolled prompts (if REROLL)

## Symbiosis law emphasis

Law 7 (Numeri prima) — cost ceiling hard halt before any Veo spend

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

- `ceiling_usd`: $0.1 (declared in `docs/wr3/contracts/pre-render-gatekeeper.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-pre-render-gatekeeper.md`
- I/O contract: `~/nuzantara/docs/wr3/contracts/pre-render-gatekeeper.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/nuzantara/docs/wr3/symbiosis-precedence.md`
