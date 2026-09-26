---
date: 2026-06-09
domain: operations
client_case: none
sources:
  - 4-LLM asymmetric-adversarial panel (Gemini 3.1 red-team, Codex GPT-5.5 constructive, DeepSeek V4 Pro logic, Claude Opus 4.8 synthesis)
  - https://ast-grep.github.io/advanced/core-concepts.html
  - https://semgrep.dev/docs/getting-started/cli
  - https://mutmut.readthedocs.io/en/latest/
  - https://docs.astral.sh/ruff/linter/
  - https://docs.astral.sh/uv/
  - https://testmon.org/
  - cicatrix W68/W72/W73 (_guard_* over-match family)
  - reference_anthropic_recursive_self_improvement_2026_06_06 (memory)
panel:
  - Gemini 3.1 Pro (agy) — red-team lens — LIVE
  - Codex GPT-5.5 — constructive lens — LIVE
  - DeepSeek V4 Pro (reasoning_effort=high) — logic/numbers lens — LIVE (token-truncated mid-reasoning, content preserved)
  - Claude Opus 4.8 — 4th voice + synthesizer
---

# Dev AI stack additions — 4-LLM panel verdict (2026-06-09)

> **Question (Antonello)**: "Now that you know the system well, which Dev AI tools do you
> recommend adding to my stack?" Stated pain: (1) code review/verification is the
> bottleneck (AI generates faster than he can verify); (2) wants raw coding speed.

## 0. Why a panel

Per CLAUDE.md §6, any architectural/stack recommendation gets a mandatory 4-LLM panel,
asymmetric-adversarial (never consensus). All three external tiers were health-checked
LIVE before convening (Gemini PONG, Codex PONG, DeepSeek 200) — anti-hallucination:
no dead-tier answers were fabricated.

## 1. The proposal under review (Claude's initial recommendation)

Do NOT add a 5th LLM/agent. ARM 3 local, $0, PII-safe things:
- **A.** `ast-grep` + `semgrep` (OSS, deterministic, non-LLM) as pre-commit hook + hot-zone PR gate — turn each cicatrix into ONE structural rule that catches the whole bug-class forever.
- **B.** Finish mutation testing (`mutmut`/`cosmic-ray`) — already half-specced as `p1s2-mutation-incremental` — to find which of 10,500+ tests are theater.
- **C.** Consolidate `ruff`+`uv` as the single lint/format inner-loop path.
- **D (optional).** `Continue.dev` → local Ollama for PII-safe inline autocomplete.
- Contrarian thesis: more tools = more decaying surfaces; arm what exists, don't add capability.

## 2. Panel verdict per item

| Item | Gemini (red-team) | Codex (constructive) | DeepSeek (logic) | SYNTHESIS |
|---|---|---|---|---|
| **C ruff+uv** | "trivial, keep" | "right, add ONE wrapper not docs" | "no hole" | ✅ **SHIP** (unanimous) — but already 80% armed (pre-commit runs `ruff check` on staged py) |
| **A ast-grep** | "FATAL: non-coder won't write/maintain AST rules; false-positives block PRs" | "right with stricter scope: ast-grep for structural, Semgrep CE only cross-file; no broad packs; each cicatrix = rule+pos fixture+neg fixture+hot-zone path" | "claim 'one rule catches all 5' SURVIVES with minor overclaim — catches the *class* (`in` substring) not *semantic correctness* of the fix" | ✅ **SHIP, hot-zone only**, AI writes the rules but each needs pos+neg fixture (Codex). Gemini's "non-coder won't write them" is countered by: agent writes them, fixtures prove them. |
| **B mutation** | "MASSIVE busywork; report tells non-coder tests are weak → spawns more agents → infinite AI-on-AI loop; destroys speed" | "right but `mutmut` not cosmic-ray; hot-zone ONLY (guards/pricing/RBAC/RAG-confidence); survivors = tickets not a quality project" | "INFEASIBLE on 10,500 tests without incremental — incremental is MANDATORY not nice-to-have, and it's NOT armed, so arming it is itself a big task" | ⚠️ **DEFER, hot-zone only**, after p1s2-incremental is real. Never full-suite. |
| **D Continue.dev** | "NONSENSICAL: autocomplete is for humans who type; Zero orchestrates, doesn't type" | "acceptable low-priority, local-only; TabbyML narrower if autocomplete-only" | "contradicts own anti-decay thesis (adds a tool)" | ❌ **WITHDRAWN** (2 of 3 reject + it violates the contrarian thesis) |

## 3. The omission ALL THREE flagged (highest-value finding)

The proposal ignored the REAL bottleneck. Gemini stated it explicitly; Codex and DeepSeek
implied it:

> **Gemini**: "weaponize local `deepseek-r1` on the Pro as an asynchronous, deterministic
> auto-reviewer agent. The bottleneck isn't missing AST rules; it's the lack of an autonomous
> AI supervisor that auto-rejects PRs and prunes dead branches *before* Zero ever has to look
> at them."

This ties directly to what we saw THIS session: 32 orphan stash, 75 local branches, 39 dead
DLQ jobs with healing=0. The problem isn't generation power — it's that **nothing filters
before the human**. This is exactly the Anthropic "code review becomes the constraint" thesis
(memory `reference_anthropic_recursive_self_improvement`).

## 4. Codex's concrete addition (promoted)

`pytest-testmon` — local/OSS, runs ONLY tests impacted by the changed code (coverage
dependency tracking). Full suite stays in CI/nightly. Real review-speed gain, deterministic,
$0, no LLM trust. Not in the original proposal. **Adopted.**

## 5. Final recommendation (post-panel) — ship-order

| # | What | Why | Risk | Status |
|---|---|---|---|---|
| **1** | `ruff` explicit config + `pytest-testmon` as a single fast local gate wrapper (`scripts/fast-gate.sh`) | inner-loop speed, deterministic, 3/3 consensus | ~zero | THIS PR (a+b) |
| **2** | `ast-grep` cicatrix rules, hot-zone only, each rule + pos/neg fixture | closes W68/W72/W73 class forever | low (false-pos if too broad) | next |
| **3** | Async review supervisor (local deepseek-r1 on Pro) that auto-rejects PRs + prunes dead branches before the human | THE real bottleneck per all 3 panelists | medium (new agentic piece) | dedicated spec + own panel |
| **defer** | `mutmut` hot-zone only, after p1s2-incremental armed | find theater tests | medium | after #1-3 |
| **drop** | `Continue.dev` / any human-autocomplete | agent-centric workflow, not human-typing | — | rejected |

## 6. Hard-constraint compliance (all survivors)

- No paid Anthropic endpoint touched. ✅
- No client PII to any third-party cloud (all tools local/deterministic). ✅
- Free-first: every survivor is OSS/local, $0. ✅
- Solo-dev maintenance: #1-2 are low-surface; #3 is the only one that adds a daemon (gets its own spec + panel before arming). ✅

## 7. Method note (anti-hallucination)

DeepSeek's response was token-truncated mid-reasoning (it ignored the 350-word cap and
reasoned aloud to the limit); its logical content was fully captured before cutoff and is
reflected above. `agy -p` requires the prompt as the `-p` argument, NOT via stdin pipe
(first attempt failed with "flag needs an argument"). Both noted so a future panel run
doesn't repeat them.
