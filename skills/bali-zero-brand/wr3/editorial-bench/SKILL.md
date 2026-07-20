---
name: wr3-editorial-bench
description: WR3 editorial-bench skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-editorial-bench agent at every dispatch.
model: opus
lifecycle_tier: scheduled
cost_class: reasoning
ceiling: $0.5
contract_version: 1.0.0
---

# WR3 editorial-bench — Skill Cortex

## Role (one-line)

Monthly cron 1st Monday 07:00 WITA. Researches SOTA video editorial from 12 reference brands (NYT Opinion Video, Bloomberg Originals, Reuters, Wired, Pudding, Rest of World, ProPublica, Vox, Quartz, Drift, Vice News, Al Jazeera English) + 3 Bali Zero competitor video accounts (Lets Move Indonesia, Emerhub, Flado IG Reels). Multi-LLM: Gemini 3.1 Pro for long-context ingestion, Claude Opus for synthesis, DeepSeek for pattern extraction.

## Primary I/O

- **Inputs**: 12 reference brand video archives + 3 competitor archives + 2 trend reports
- **Outputs**: ~/.claude/skills/bali-zero-brand/\_external-bench-video-YYYY-MM.md

## Symbiosis law emphasis

Law 8 (Passato/Presente/Futuro) — read by yt-metrics-analyst (weekly) and critic (every run via skill load)

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

## Output structure (`_external-bench-video-YYYY-MM.md`)

1. **Executive Summary** — Claude Opus 4.7, 200-300 words, BZ-field framing
2. **Trends Du Mois** — agy long-context, 10-15 bullets rising/falling
3. **Numerical Patterns** — DeepSeek V4 Pro, p50/p90 (hook ms, cuts/sec, text density chars/sec, emoji freq, title length)
4. **Bali Zero Adoptable Patterns** — Claude synthesis, 5 testable bullets
5. **Anti-Patterns to Avoid** — Claude synthesis, 5 bullets
6. **Per-Brand Briefs** — agy, ~100 words / brand × 15
7. **Cost Report** — per-tier telemetry table (wall, tokens, $)

## Cost budget (monthly)

| Tier      | LLM                                   | Cost       | Quota source                 |
| --------- | ------------------------------------- | ---------- | ---------------------------- |
| 2         | Gemini 3.1 Pro via agy CLI            | $0.00      | Google AI Ultra subscription |
| 3         | Claude Opus 4.7 via claude-cascade.sh | ~$0.30     | Claude MAX OAuth (no SDK)    |
| 4         | DeepSeek V4 Pro reasoning_effort=high | ~$0.05     | DeepSeek API (Keychain key)  |
| **Total** |                                       | **~$0.35** | within $0.50 ceiling         |

## Cost ceiling discipline

- `ceiling_usd`: $0.5 (declared in `docs/wr3/contracts/editorial-bench.yaml`, `hard_halt_on_exceed: true`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-editorial-bench.md`
- I/O contract: `~/nuzantara/docs/wr3/contracts/editorial-bench.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/nuzantara/docs/wr3/symbiosis-precedence.md`
