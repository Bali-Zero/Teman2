---
name: wr3-shot-director
description: WR3 shot-director skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-shot-director agent at every dispatch.
model: opus
lifecycle_tier: core
cost_class: reasoning
ceiling: $0.5
contract_version: 1.0.0
---

# WR3 shot-director — Skill Cortex

## Role (one-line)

Drafts shot-list aligned to script pacing markers, writes Veo 3.1 Fast Tier_ONE prompt pack (positive + negative + identity tokens A007 Zantara anchor + transition map between shots). LARGEST hallucination surface in WR3 pipeline. Does NOT approve own prompts — pre-render-gatekeeper reviews.

## Primary I/O

- **Inputs**: brief.json + script.json (both verbatim)
- **Outputs**: shot-pack.json with shots[] containing positive_prompt + negative_prompt + identity_tokens + duration_s + transition_to_next

## Symbiosis law emphasis

Law 8 (passato/presente/futuro) — anti-cliche-library scan before submit

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

- `ceiling_usd`: $0.5 (declared in `docs/wr3/contracts/shot-director.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-shot-director.md`
- I/O contract: `~/nuzantara/docs/wr3/contracts/shot-director.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/nuzantara/docs/wr3/symbiosis-precedence.md`
