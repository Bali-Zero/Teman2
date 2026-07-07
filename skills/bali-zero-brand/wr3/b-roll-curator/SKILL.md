---
name: wr3-b-roll-curator
description: WR3 b-roll-curator skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-b-roll-curator agent at every dispatch.
model: sonnet
lifecycle_tier: fallback
cost_class: text_planning
ceiling: $0.15
contract_version: 1.0.0
---

# WR3 b-roll-curator — Skill Cortex

## Role (one-line)

On-demand fallback. Invoked when Veo 3.1 fails specific shot AND 2 retries with strengthened prompt fail (ArcFace <0.55 OR safety reject persists). Searches local b-roll pool (~/Desktop/nuzantara/research/marketing/b-roll-pool/) for license-clean alternatives matching shot brief. Death by eligible-opportunity-count unused ≥10 times. License verification: 1.0 (zero unverified push).

## Primary I/O

- **Inputs**: shot brief (camera angle, mood, duration) + b-roll-pool/ index
- **Outputs**: selected b-roll mp4 + license-attestation.json

## Symbiosis law emphasis

Law 4 (Graceful degradation) — fallback path, not hot path; Law 6 (Sovranità locale) — local pool only

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

- `ceiling_usd`: $0.15 (declared in `docs/wr3/contracts/b-roll-curator.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-b-roll-curator.md`
- I/O contract: `~/Desktop/nuzantara/docs/wr3/contracts/b-roll-curator.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/Desktop/nuzantara/docs/wr3/symbiosis-precedence.md`
