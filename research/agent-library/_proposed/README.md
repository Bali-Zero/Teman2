# S13 Evolution Cycle — Proposed Skill Drafts (2026-06-02)

Output of the **S13 agent-library-evolution** manual cycle. These are **drafts
only** — Antonello approves any graduation (append to `lessons.md` / promotion to
an agent's skill dir). NO production agent was modified by this cycle.

## Why a *manual* cycle

The autonomous evolution loop (Reflexion + Voyager + EvoSkill) **has never closed** —
see `S13-P6`. This manual cycle is the substitute: it does by hand what the broken
loop was supposed to do automatically.

## Files

| File | What |
|---|---|
| `2026-06-02-s13-p1..p7-*.md` | 7 proposal drafts, each with cross-vendor adversarial verdict + post-adversarial disposition |
| `S13_build_frozen.py` | Idempotent builder that regenerates `../S13-evolution-FROZEN.json` (pure I/O, reads the two adversary verdict files) |
| `S13-adversarial-deepseek.json` | DeepSeek V4 Pro red-team verdict (reasoning_effort=high) |
| `S13-adversarial-codex.json` | Codex GPT-5.5 red-team verdict (cross-vendor isolation) |

## Verdict summary (after cross-vendor adversarial pass)

| ID | Proposal | Converged verdict |
|---|---|---|
| S13-P6 | FIX-evolution-loop-closure | **KEEP — PRIMARY** |
| S13-P7 | agent-library-contract-test-harness | **KEEP — PRIMARY (adversary-demanded)** |
| S13-P1 | provider-cascade-protocol | REVISE → executable runner, not prose |
| S13-P2 | nb-ground-truth-protocol | REVISE → split routing-config from call-authority |
| S13-P4 | metrics-analyst-protocol | REVISE → keep gate+schema, defer correlation |
| S13-P5 | orchestrator-contract-protocol | SPLIT → downgrade to contract-test |
| S13-P3 | review-gate-protocol | **KILLED (unanimous)** |

## The load-bearing correction

Both adversaries independently said: *duplication-of-words ≠ duplication-of-behavior;
a skill loaded as guidance enforces nothing. The real deliverable is enforcement
(S13-P6 loop repair + S13-P7 contract-test harness), not more prose-protocol skills.*

That correction is why two of the six original proposals (P3, P5) collapse into the
contract-test harness rather than graduating as skills, and why the two highest-value
items are an infra-fix and a test harness — not new prose.

## Regenerate

```bash
python3 research/agent-library/_proposed/S13_build_frozen.py --emit \
  > research/agent-library/S13-evolution-FROZEN.json
```

Deterministic: same inputs (the two adversary verdict JSONs + hardcoded findings) →
byte-identical output. No network, no LLM, no `Date.now()`.
