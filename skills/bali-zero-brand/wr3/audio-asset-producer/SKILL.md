---
name: wr3-audio-asset-producer
description: WR3 audio-asset-producer skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-audio-asset-producer agent at every dispatch.
model: sonnet
lifecycle_tier: core
cost_class: audio_gen
ceiling: $0.05
contract_version: 1.0.0
---

# WR3 audio-asset-producer — Skill Cortex

## Role (one-line)

Generates Zantara VO via local Chatterbox Multilingual (Emma locked seed=42 cfg_weight=0.30 temperature=0.70 exaggeration=0.32), compares transcript to script.json segments, normalizes LUFS to -14 ±1, sources licensed music from local pool, drafts attribution. Owns b-roll fallback dispatcher when clip-renderer Veo fails specific shot. Local-only — ZERO cloud TTS (Cartesia BANNED Law 6 sovranità).

## Primary I/O

- **Inputs**: script.json (verbatim)
- **Outputs**: audio/vo.wav + audio/music.wav + license-report.json

## Symbiosis law emphasis

Law 6 (Sovranità locale) — Cartesia API BANNED, Chatterbox local only

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

- `ceiling_usd`: $0.05 (declared in `docs/wr3/contracts/audio-asset-producer.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-audio-asset-producer.md`
- I/O contract: `~/nuzantara/docs/wr3/contracts/audio-asset-producer.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/nuzantara/docs/wr3/symbiosis-precedence.md`
