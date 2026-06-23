---
name: wr3-script-editor
description: WR3 script-editor skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-script-editor agent at every dispatch.
model: sonnet
lifecycle_tier: core
cost_class: text_planning
ceiling: $0.15
contract_version: 1.0.0
---

# WR3 script-editor — Skill Cortex

## Role (one-line)

Writes 60-90s VO script (script.json) with claim_id bindings (every regulatory/numeric claim references brief.json claim_id), pacing markers (Hook 0-5s, Frame 5-15s, Discovery 15-50s, Closing 50-60s), word count compliance (~200 words for 60s, 3 words/sec).

## Primary I/O

- **Inputs**: brief.json (verbatim)
- **Outputs**: script.json with segments[] each containing text + start_ms + claim_ids[]

## Symbiosis law emphasis

Law 7 (Numeri prima) — every numeric claim has claim_id pointing to brief.json source

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

- `ceiling_usd`: $0.15 (declared in `docs/wr3/contracts/script-editor.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-script-editor.md`
- I/O contract: `~/Desktop/nuzantara/docs/wr3/contracts/script-editor.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/Desktop/nuzantara/docs/wr3/symbiosis-precedence.md`
