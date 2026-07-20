---
name: wr3-brief-interpreter
description: WR3 brief-interpreter skill cortex — operational heuristics, on-tone examples, lessons growth surface. Loaded by wr3-brief-interpreter agent at every dispatch.
model: sonnet
lifecycle_tier: core
cost_class: text_planning
ceiling: $0.15
contract_version: 1.0.0
---

# WR3 brief-interpreter — Skill Cortex

## Role (one-line)

SOLE consumer of NotebookLM ground-truth queries — routes to domain NBs (NB-2 visa, NB-3 company/PMA/KBLI, NB-4 tax, NB-5 property, NB-6 compliance, NB-7 editorial) per `nb-routing-domain-map.md`. NB-1 (codebase) and NB-INTEL family (OSINT) are OUT OF SCOPE for regulatory grounding. Returns structured brief JSON with key_facts, key_numbers, audience segment, regulatory citations verbatim, claim_ids for legal_claim_gate, bilingual lexicon, taboo notes, archetype recommendation. Filters NB source_ids and raw synthesis OUT of brief.json (Law 2 OSINT boundary).

## Primary I/O

- **Inputs**: topic + audience + mode payload (from design-architect dispatch)
- **Outputs**: brief.json + claim_ids list + (separate file) nb_source_ids.private.json (NEVER pushed downstream)

## Symbiosis law emphasis

Law 2 (OSINT blindato) — ZERO NB source_ids in brief.json output

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

- `ceiling_usd`: $0.15 (declared in `docs/wr3/contracts/brief-interpreter.yaml`)
- `BudgetExceededError` → cascade decision per `Law 7 (Numeri prima)`:
  - If agent is GATE (design-architect, pre-render-gatekeeper) → HARD HALT + Telegram P0
  - If agent is HOT PATH (lifecycle_tier=core) → cascade to Gemini fallback
  - Otherwise → mark FAIL, retry next cycle

## Resources

- Agent definition: `~/.claude/agents/wr3-brief-interpreter.md`
- I/O contract: `~/nuzantara/docs/wr3/contracts/brief-interpreter.yaml`
- Brand cortex (shared): `~/.claude/skills/bali-zero-brand/`
- Symbiosis precedence: `~/nuzantara/docs/wr3/symbiosis-precedence.md`
