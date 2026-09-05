# Station 6 key

## Planted (three) — see `plants.diff`

| # | where | planted fact | contradicts | enforced by a machine? |
| --- | --- | --- | --- | --- |
| P1 | `FLEET_TOPOLOGY.json` → `role_chains.refuter.chain` | order is `codex-sol → kimi-k3 → glm-5.2 → gemini → deepseek-v4-pro` | `.claude/skills/modus/SKILL.md` §THE ARSENAL Refuter row: "codex-sol → glm-5.2 → kimi-k3 → gemini-agy-redteam → deepseek-v4-pro" | no script reads the chain order (the lint reads seats, not order) — doc-vs-doc |
| P2 | `AGENTS.md` §17.3 | AZ is "cron/batch, designated donor"; the final gate runs on A1 | `FLEET_TOPOLOGY.json` `accounts.anthropic.slots.AZ.lane` = "GATE PRIMARY"; `_invariants[0]` gate rotation "AZ->A2->A3->A1"; `MODEL_ROSTER.md` §Anthropic; §17.2 carve-out in the SAME file says "rotating across ALL Anthropic accounts (AZ→A2→A3→A1)" | `role_chains.gear3_final_gate.chain[0].accounts` starts with AZ — the machine side says AZ |
| P3 | `MODEL_ROSTER.md` §Local Ollama | `qwen3.5:9b` is the sole vision/OCR seat; "`qwen2.5vl` Q4_K_M strips vision weights" | `MODEL_TOPOLOGY.json` `roles.vision` = `roles.ocr_vision` = `qwen2.5vl:7b`; `CLAUDE.md` §9 data invariant ("qwen3.5 Q4_K_M strips vision weights — never substitute"); the same roster line lists `qwen3.5:9b` as the classifier with `think:false` | `MODEL_TOPOLOGY.json` is read by the cron wrappers — the machine side says qwen2.5vl |

## Real, not planted (known at build time; a candidate that finds one scores up)

| # | where | fact A | fact B |
| --- | --- | --- | --- |
| R1 | `AGENTS.md` §17.2 step 1 "Anthropic ×4 via OAuth profile swap" | `FLEET_TOPOLOGY.json` roster is A1–A5 + AZ (six); `AGENTS.md` §17.3 itself lists A1, A2, A3, AZ only | the ×4 predates the 2026-08-19 estate ruling |
| R2 | `AGENTS.md` §17.2 step 2 "refuter: sol→k3→gemini" | `FLEET_TOPOLOGY.json` refuter chain has glm-5.2 between sol and k3 (and deepseek at the end) | prose omits two hops the machine-side chain has |
| R3 | `MODEL_TOPOLOGY.json` `_doc` "Air was decommissioned on 2026-05-05 and is not an active Ollama node" | `infra/fleet/nodes.json` lists `m5` (Air-M5) as "interactive dev workstation (Zero's primary seat)"; `MODEL_ROSTER.md` says ollama NOT_INSTALLED on M5 | both true in their own scope (Ollama node vs fleet node) — a candidate that calls this a contradiction without noting the scope difference scores 0 for the entry; one that notes it is fine |
| R4 | `MODEL_ROSTER.md` §OpenAI "slugs DEAD 2026-07-21 … the versioned door is live" vs `FLEET_TOPOLOGY.json` `orchestrators.codex.models_note` "slugs dead — do not pass -m until a probe proves slugs live" | the topology note was never walked forward after PR #5044 | `seat_build.sh` passes `-m gpt-5.6-<tier>` — the machine side says live |
| R5 | `MODEL_ROSTER.md` §Anthropic `claude-opus-5` row "Gate roles: xhigh effort" and `_invariants[0]` "Opus 5, xhigh effort" vs `role_chains.gear3_final_gate.chain[0].effort = "max"` and the modus gate table "gate roles run `max`" | xhigh vs max for the same seat in the same role | `harness_fable_gate.py` — check which it passes; whichever it is, one doc is wrong |

Anything else a candidate reports: the consuls re-probe on disk before crediting.

## Scoring

- 0 — none of P1–P3, or ≥2 false contradictions.
- 1 — one or two of P1–P3, entries in the required shape.
- 2 — all three of P1–P3, each with the machine-enforced side identified where one exists.
- 3 — 2 plus at least one of R1–R5 (or a new real one the consuls confirm), and R3 handled
  with the scope note if reported.
- −1 per false contradiction (floor 0). Ordering by blast radius is a tie-breaker between
  seats, not a point.
