---
date: 2026-07-12
domain: operations
client_case: How senior devs actually run a frontier model with cheaper models — orchestrator pattern research
sources: MindStudio, GitHub/pilotfish, Anthropic benchmarks (via secondary), Hacker News threads (routing/local-model/GLM)
adversarial_review: exempt-source-compilation-not-a-finding
---

# What senior devs actually do: the orchestrator pattern (not model extraction)

**Trigger** (Zero, 2026-07-12): the original mandate — misunderstood across three prior turns — was
NOT "how to extract Fable's weights" and NOT the reframed "make cheap models perform." It was:
**find out what senior devs are really doing to use Fable-5 together with Opus/Sonnet, from the
communities.** This document is that research, done directly against real sources with citable links,
not summarized second-hand by sub-agents.

---

## 0. The one finding that matters

Senior devs are not stealing Fable's brain. There is nothing to steal — the weights don't leave
Anthropic, and scraping outputs to clone it violates ToS. What they actually do has a plain name:
**the orchestrator pattern.** The expensive model (Fable/Opus) is the *director* — it plans,
decides, and judges the final result. Cheap models (Sonnet, Haiku) are the *hands* — they write,
edit, execute. The director touches ~10-20% of tokens; the hands touch ~80-90%.

**The number that anchors it** — from Anthropic's own benchmarks (reported via MindStudio/pilotfish,
flagged below as needing a primary-source confirmation):

> **Fable-5 orchestrator + Sonnet-5 workers = 96% of all-Fable quality, at 46% of the cost.**
> BrowseComp: 86.8% vs 90.8% accuracy · $18.53 vs $40.56 per problem.

This is the direct answer to Zero's real question — *how do you use Fable together with Opus/Sonnet*:
as director, never as laborer. It is also empirical backing for the "don't pay for Fable as an
executor" decision already taken (2026-07-12): you lose ~4% of quality, not the model's value.

⚠️ **Provenance caveat**: the 96%/46% figure is cited by two secondary sources (MindStudio blog,
pilotfish README) as "Anthropic's own benchmarks." It has NOT been confirmed against a primary
Anthropic source in this research. Treat as strong-but-unverified until traced to the Anthropic
page/paper. Same caveat class as prior reports' unverified figures.

---

## 1. What survives, per source

| Source | What it says | Link |
|---|---|---|
| MindStudio — Smart Orchestrator | Opus-orchestrator + Haiku/DeepSeek sub-agents = 5-10x token cost cut, no meaningful quality loss; 80-90% of tokens move to cheap models. The `Task` tool is the delegation mechanism. | https://www.mindstudio.ai/blog/smart-orchestrator-cheaper-sub-agent-models-claude-code |
| GitHub — pilotfish | An open-source package of exactly this pattern for Claude Code. Architecture strikingly close to our `modus` (role-per-model tiers, fresh-context adversarial verifier). Two ideas we don't have — see §2. | https://github.com/Nanako0129/pilotfish |
| Medium — "Frontier Models... Almost Never Use Them" | The senior-dev thesis: running a frontier model on every task is "hiring a senior architect to carry boxes." | https://medium.com/analysts-corner/frontier-models-are-incredible-454320562bad |
| HN — Smart model routing | Router as an endpoint that inspects each request and dispatches to the right model (DeepSeek/GLM/Kimi cheap, Opus/GPT-5.5 when necessary). | https://news.ycombinator.com/item?id=48688700 |
| HN — GLM 5.2 beats Claude | Community benchmark chatter (context for our GLM-as-refuter seat). | https://news.ycombinator.com/item?id=48709670 |

**Consistent caveat across sources**: smaller models "don't do the thinking for you" — they need
precise, complete specification. This is exactly the generator≠grader + full-spec discipline we
already run; it's a warning against under-specifying delegated work, not against delegation itself.

---

## 2. modus (us) vs pilotfish — the honest comparison

Same core pattern. `modus` is more mature everywhere else (the 10 scar families, the full
prod→fleet→clean lifecycle, the PII boundary, anti-hallucination discipline). pilotfish is a routing
pattern; modus is an operating system. **But pilotfish has two architectural mechanisms we lack**,
and both cure problems we actually lived through:

### Idea 1 — role-alias instead of hardcoded model (the fix for THIS session's bug)
pilotfish's main session points at a **role alias** that resolves to "best available, falling back
automatically," never a hardcoded model ID. Our `~/.claude/settings.json` has `"model": "opus"`
written by hand, no fallback.

**Why it matters concretely**: the A/B bug earlier today (2026-07-11 report) happened *because* the
model depended on the mutable session default — omitting `model` inherited whatever `/model` had last
set. A role alias makes that class of bug structurally impossible: the role resolves the same way
regardless of session state.

### Idea 2 — policy written in ROLES, never model names
pilotfish's `CLAUDE.md` policy says "the verifier does X", not "Opus does X". When a model
changes/disappears, **zero lines to edit**. Our `modus` and `CLAUDE.md` name `claude-sonnet-5`,
`claude-fable-5` literally — which is why every model change costs a PR (two of them today alone).
pilotfish's degradation is automatic; ours is manual.

### What WE do better (do NOT blindly copy)
- **The never-cascade final-gate rule**: pilotfish degrades *everything* automatically, including
  final judgment. We keep the final gate on Fable and SUSPEND rather than silently degrade it. On a
  safety decision, ours is more prudent. **Idea 1 must NOT be applied to the final gate** — only to
  the rest of the routing. This is the one place where their automation is a liability and our
  rigidity is correct.
- Scar families, full lifecycle, PII boundary, PENDING-ARMS ledger — all beyond pilotfish's scope.

---

## 3. The proposal (what to actually change) — config VERIFIED against official docs

Adopt the TWO good ideas, ring-fenced away from the final gate. Config keys below confirmed against
official Claude Code docs (v2.1.207) via the claude-code-guide agent — no invented keys.

### ⚠️ Critical adaptation: pilotfish uses `"best"` — WE MUST NOT

pilotfish's main session points at `"model": "best"`. Officially, **`"best"` resolves to Fable 5
when the org has access, else latest Opus.** That is the *opposite* of Zero's 2026-07-12 decision
("io non voglio pagare"): once Fable-5 is metered, `"best"` would default the interactive session
straight onto paid Fable. **Do NOT copy `"best"` verbatim.**

The correct adaptation for us: primary `"opus"` with an explicit `fallbackModel` chain. This buys
the automatic-degradation benefit (Idea 1) WITHOUT ever pointing at paid Fable.

```jsonc
// ~/.claude/settings.json  — OPERATOR-APPLIED (control-plane, ~/.claude/, host_boundary)
// CURRENT:  "model": "opus"
// PROPOSED:
  "model": "opus",
  "fallbackModel": ["sonnet"]   // auto-degrade if opus unavailable; NEVER resolves to paid Fable
```

- `fallbackModel`: array, max 3, aliases or full IDs; does NOT merge across settings files (highest-
  precedence file supplies the whole chain) — verified.
- We deliberately keep `"opus"` (not `"best"`) as primary so no path silently escalates to paid Fable.
- The final gate is a SEPARATE concern (modus §Arsenal), governed by the never-cascade rule, not by
  this session-model setting — this change does not touch it.

### Idea 2 — role-alias in subagent frontmatter (survives model churn)
Verified: subagent `.md` frontmatter `model:` accepts aliases (`sonnet`, `opus`, `haiku`) and an
alias auto-tracks the latest version of that tier, surviving model-generation changes. Where our
subagents pin full IDs (`claude-sonnet-5`) purely to track "the current Sonnet", an alias (`sonnet`)
would remove the need for a PR on every model bump — EXCEPT where a full ID is load-bearing (a probe
that must pin an exact version, or the final-gate model which must stay explicit and never-cascade).

### modus §Arsenal + CLAUDE.md — phrase routing by ROLE where safe
Bind role→model in one table; a model-generation change updates that binding, not every mention.
**Explicit carve-out: the final-gate row stays model-named and never-cascade — load-bearing, must
not become a role that can auto-degrade.**

### Split of responsibility
- **Operator-only** (control-plane, `~/.claude/settings.json`): the `fallbackModel` line above.
  This session does NOT edit it — host_boundary is hard by design.
- **Repo / this PR**: this research doc + (optionally) the modus §Arsenal role-binding phrasing,
  which are normal repo files under Legge-5 review.

---

## 4. §Solo-operatore

1. Whether to adopt the role-alias in settings.json (and confirm the final-gate carve-out).
2. Trace the 96%/46% figure to a primary Anthropic source before citing it as fact anywhere
   load-bearing.
3. Whether to look harder at pilotfish's actual role files (the `agents/` dir 404'd on plain fetch —
   would need `gh` to read) for anything else worth borrowing.
