---
name: wr3-yt-metrics-analyst
description: WR3 yt-metrics-analyst skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-yt-metrics-analyst agent at every dispatch.
model: sonnet
lifecycle_tier: scheduled
cost_class: text_planning
ceiling: $0.15
contract_version: 1.0.0
---

# WR3 yt-metrics-analyst — Skill Cortex

## Role (one-line)

Weekly cron Monday 06:00 WITA. Reads YouTube Analytics API + IG/TikTok engagement scrape for last 30-90 days WR3 episodes, correlates engagement signals with episode attributes (domain, register, archetype, ArcFace avg, critic lane scores). Proposes amendments to _proposed-amendments/. Runs AFTER Reflexion (Sun 02:30).

## Primary I/O

- **Inputs**: YouTube Analytics API + IG/TT scrape + episode_manifest.json batch
- **Outputs**: _proposed-amendments/<date>-yt-insights.md

## Symbiosis law emphasis

Law 7 (Numeri prima) — every amendment cites engagement metric

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

- `ceiling_usd`: $0.15 (declared in `docs/wr3/contracts/yt-metrics-analyst.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-yt-metrics-analyst.md`
- I/O contract: `~/Desktop/nuzantara/docs/wr3/contracts/yt-metrics-analyst.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/Desktop/nuzantara/docs/wr3/symbiosis-precedence.md`
