---
name: wr3-clip-renderer
description: WR3 clip-renderer skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-clip-renderer agent at every dispatch.
model: sonnet
lifecycle_tier: core
cost_class: render
ceiling: n/a
contract_version: 1.0.0
---

# WR3 clip-renderer — Skill Cortex

## Role (one-line)

Submits Veo 3.1 Fast Tier_ONE jobs via wr3_flowkit_client.py (Flow UI Pro plan, 10 cr/clip 720x1280 9:16 8s native-audio-off), watchdog 300s wall-clock per clip, fallback selection (Opus escalation for fallback strategy decision), ingest MP4s to clips/. ALSO owns Identity Gate: ArcFace cosine ≥0.6 verification + VLM holistic check.

## Primary I/O

- **Inputs**: shot-pack.json (gate-passed)
- **Outputs**: clips/<n>.mp4 (12-15 files) + identity-report.json

## Symbiosis law emphasis

Law 6 (Sovranità locale) — Flow API is cloud touchpoint, all orchestration local

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

- `ceiling_usd`: n/a (declared in `docs/wr3/contracts/clip-renderer.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-clip-renderer.md`
- I/O contract: `~/Desktop/nuzantara/docs/wr3/contracts/clip-renderer.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/Desktop/nuzantara/docs/wr3/symbiosis-precedence.md`
