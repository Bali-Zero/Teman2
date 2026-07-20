---
name: wr3-critic
description: WR3 critic skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-critic agent at every dispatch.
model: opus
lifecycle_tier: core
cost_class: reasoning
ceiling: $0.5
contract_version: 1.0.0
---

# WR3 critic — Skill Cortex

## Role (one-line)

MANDATORY quality gate. Reviews 4 lanes: (1) Identity — ArcFace cosine + 5-frame sample VLM holistic; (2) Audio sync — VO/video drift, LUFS compliance, transcript match ≥0.95; (3) Brand voice + cliche pattern — on-tone-examples + cliche-library scan; (4) Legal/regulatory — verbatim citations + cost-disclosure + cross-check vs brief.json claim_ids. Multi-pass: Haiku VLM pre-pass for cheap checks, Opus for nuanced. Returns binary PASS/FAIL per rubric + retry feedback JSON. NO Agent tool — cannot recurse.

## Primary I/O

- **Inputs**: master.mp4 + episode_manifest.json + brief.json + script.json + brand cortex pointer
- **Outputs**: critic-report.json with per-lane verdict + retry feedback

## Symbiosis law emphasis

Law 5 (Zero ultima istanza) — gate before Antonello/Damar manual publish

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

- `ceiling_usd`: $0.5 (declared in `docs/wr3/contracts/critic.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-critic.md`
- I/O contract: `~/nuzantara/docs/wr3/contracts/critic.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/nuzantara/docs/wr3/symbiosis-precedence.md`
