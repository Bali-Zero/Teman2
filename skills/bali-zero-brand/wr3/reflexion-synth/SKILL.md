---
name: wr3-reflexion-synth
description: WR3 reflexion-synth skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-reflexion-synth agent at every dispatch.
model: sonnet
lifecycle_tier: scheduled
cost_class: text_planning
ceiling: $0.15
contract_version: 1.0.0
---

# WR3 reflexion-synth — Skill Cortex

## Role (one-line)

Weekly cron Sunday 02:30 WITA via LaunchAgent. Reads last 7 days episodes + designer-override diffs (final-published vs critic-passed draft). Synthesizes ≤10 verbal lessons per agent, appends to skill cortex lessons.md. Also proposes Voyager skill drafts in _proposed/. Standalone — NOT in orchestrator hot-path.

## Primary I/O

- **Inputs**: apps/war-room/output/episode/<recent>/* + human-review-queue.json diffs
- **Outputs**: lessons appended to <agent>/lessons.md + drafts in _proposed/

## Symbiosis law emphasis

Law 8 (Passato/Presente/Futuro) — institutional memory growth via curriculum

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

- `ceiling_usd`: $0.15 (declared in `docs/wr3/contracts/reflexion-synth.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-reflexion-synth.md`
- I/O contract: `~/Desktop/nuzantara/docs/wr3/contracts/reflexion-synth.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/Desktop/nuzantara/docs/wr3/symbiosis-precedence.md`
