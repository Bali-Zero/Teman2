---
date: 2026-08-12
domain: operations
client_case: none
sources:
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://cognition.com/blog/dont-build-multi-agents
  - https://research.trychroma.com/context-rot
  - https://www.anthropic.com/engineering/multi-agent-research-system
  - https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - https://docs.litellm.ai/docs/proxy/users
  - https://www.augmentcode.com/guides/ai-coding-cost-analysis-agent-token-spend
  - https://changelog.com/podcast/648
discovered_by: token-audit session 2026-08-12 (M5); width pass Gemini 3.1 Pro
---

# How the frontier handles LLM token / cost / quota at agentic scale

**Question:** when the best AI-native teams run agentic coding + autonomous agents at scale,
what do they actually DO about token cost and quota — and where does our 3-Mac fleet diverge?

**Method:** 10 targeted web searches + 2 primary-source fetches (Anthropic context-engineering,
Cognition) + a Gemini 3.1 Pro width pass. Every named-company internal detail from the width
pass that I could not independently confirm is flagged **[reported]**; measured/vendor-documented
claims are flagged **[measured]**. Even a width source hallucinates (W65) — treated as leads.

**The one-line finding:** the frontier has converged on a single idea we implement only as
prose — **context is a managed, budgeted resource, and the machinery that manages it
(caching, compaction, isolation, routing, metering) is ARCHITECTURE, not discipline.** Every
practice below is enforced by a system, never by a human remembering to be frugal. That is
exactly the gap our 7-cure plan closes.

---

## 1. Prompt caching is treated as architecture, not an optimization

- For any agent that runs >3-5 steps, caching is **not optional** — cache reads are ~$0.30/M
  vs $3.00/M fresh (a 90% cut per hit) **[measured]**, and multi-step tasks are simultaneously
  the most expensive AND the most cacheable.
- **The load-bearing rule is prefix stability.** Most-cited concrete number: moving dynamic
  content out of the cacheable prefix took one deployment from **7% to 74% hit-rate**
  ([PromptHub]) **[measured]**; another cut cost 59% ([ProjectDiscovery]). The named
  cache-killer is *our exact bug*: "injecting `Today is March 6, 2026` into a system prompt
  invalidates the cache every day" ([Augment Code]) — our hook output puts timestamps ahead of
  static doctrine. Cursor/Windsurf reportedly structure the prefix as 4 stable breakpoints
  (system → tool schemas → codebase summaries → dynamic intent last) **[reported]**.
- **Cache-hit-rate is tracked as a tier-1 SLO**; up to 4 cache breakpoints cache the static
  system prompt while leaving per-request content uncached ([Claude docs]) **[measured]**.
- **TTL is a scheduling constraint.** Default ephemeral TTL 5 min (1-hour tier at extra cost;
  Bedrock added 1-hour Jan 2026) **[measured]**. *Implication for us:* cron scattered across
  the day **cannot** reuse cache regardless of prefix identity — the fix is burst-batching
  within the TTL window.

## 2. Context engineering: the smallest high-signal token set

Anthropic's "Effective context engineering for AI agents" is canonical. Verbatim principle:
*"finding the smallest possible set of high-signal tokens that maximize the likelihood of some
desired outcome."* Four named techniques:

- **Compaction** — summarize a near-full window and reinitiate; preserve "architectural
  decisions, unresolved bugs, and implementation details", discard "redundant tool outputs".
  Lightest touch = **tool-result clearing**. Claude Code / Continue reportedly trigger at ~85%
  of budget or after ~15 tool calls, summarizing with a cheap model into a fresh window
  **[reported]**.
- **Sub-agent context isolation** — a subagent "might explore extensively, using tens of
  thousands of tokens … but returns only a condensed, distilled summary (often 1,000-2,000
  tokens)." Detailed context stays isolated; lead agent sees only the distillate.
- **Just-in-time retrieval** — hold lightweight identifiers (file paths, queries), load at
  runtime via tools (`head`/`tail`, targeted queries). "Progressive disclosure." Sourcegraph
  reportedly extracts exact line ranges rather than stuffing whole files **[reported]**.
- **Structured note-taking / external memory** — agent writes notes to disk outside the window
  and re-reads later (Claude playing Pokémon keeps tallies + maps across thousands of steps).
  Anthropic shipped a **memory tool** for this.

## 3. Context rot: big context is a COST even when it fits

Chroma Research, July 2025 ("Context Rot", Hong/Troynikov/Huber), 18 frontier models: accuracy
drops **non-uniformly as input grows, sometimes 30-50% well before the documented limit**
**[measured]**. Mechanisms: lost-in-the-middle, quadratic attention (100K tokens ≈ 10B pairwise
relations), and semantically-similar-but-irrelevant content actively misleading the model.
Anthropic frames it as an **"attention budget" every token depletes.** *This reframes our M5
300-500K sessions:* not just expensive — measurably DUMBER. A quality argument for the
session-breaker (M1), not only a cost one.

## 4. Agent topology — the real, published trade-off

Both poles are public and both right, for different problems:

- **Cognition, "Don't Build Multi-Agents" (Walden Yan):** multi-agent is fragile because of
  **fragmented context** and **conflicting decisions**. Two principles: *"Share context …
  full agent traces, not just individual messages"* and *"Actions carry implicit decisions,
  and conflicting decisions carry bad results."* Rec: *"the simplest way … is to just use a
  single-threaded linear agent"*, and for long tasks a dedicated **context-compression model**,
  not a swarm.
- **Anthropic multi-agent research system:** orchestrator-worker beats single-agent by **90.2%**
  on breadth-first research — but **agents ≈4× chat tokens, multi-agent ≈15×**; token usage
  explains ~80% of performance variance **[measured]**. Economics work ONLY when "the question
  is large, the directions are independent, and the answer is worth a lot of tokens."
- **Sourcegraph/Amp (Thorsten Ball):** subagents as **"a multiplication of context windows"** —
  fresh window per task so garbage tokens don't accumulate; plus an **Oracle** (stronger model
  for second-opinion) and specialized roles. "Some tokens are more important than others, and
  some tokens are just garbage."

*Synthesis (matches our modus doctrine):* one strong agent + more budget for coding (barely
parallelizes); **fan-out for READS, funnel-in for WRITES** — writes single-threaded, and never
a frontier model for broad exploratory reads. Multi-agent is a token multiplier bought
deliberately, never a default.

## 5. The LLM gateway / control-plane — the lever we're missing whole

The frontier does not let app/cron code call providers directly. A **gateway** (LiteLLM,
Portkey, OpenRouter, Requesty) sits in the middle and enforces, in one place:

- **Hard budget caps + real-time spend tracking** per key/user/tag; returns partial results
  when a task's token budget is exhausted. On depletion it emits a **clean 429 the orchestrator
  catches and pauses on — instead of a silent channel death** ([LiteLLM]) — the direct cure for
  our Gemini-outage class.
- **Model-tier routing** — cheap model for tool-selection/formatting/classification, expensive
  only for reasoning. Repeatedly quoted: **~60-70% of agent tasks → small model at ~1/10th cost
  with no noticeable quality loss**; RouteLLM reports up to 85% savings **[reported ranges]**.
- **Semantic caching** (GPTCache) — ~31% of queries semantically similar to prior; catching
  40-60% saves $4-6k at $10k spend **[reported]**.
- **Admission control / no-op suppression** — decide mid-run whether a workflow continues,
  narrows, needs approval, or stops; cache deterministic tool outputs to skip redundant calls.

**Both Codex and Gemini in our own panel independently converged on this as our #1 missing
lever** — our cure X2 (broker), with P1+P2 as the first brick.

## 6. Batch APIs + off-peak scheduling (a discount we don't touch)

OpenAI and Anthropic both offer a flat **50% discount** on async batch (input AND output),
results within 24h (Anthropic most <1h; ≤10k requests/batch) **[measured]**. Rule the frontier
follows: **if no human is waiting, it is batch work.** Our ~700/day cron are the textbook batch
workload we pay full sync price for. (N.B. metered-API territory; our Claude lanes are flat MAX
subs, so batch matters most for the Gemini prod seat + future metered lanes — but the
*scheduling* insight, off-peak + burst, maps straight onto §1's TTL batching.)

## 7. Counter-intuitive / 2025-26 findings a mid-size shop would miss

1. **More context makes agents WORSE, not just pricier** (context rot) — the strongest argument
   against "just use the 1M window."
2. **Prefix order is worth more than prefix size** — a 7%→74% swing from *reordering*, not
   shrinking. Slimming the corpus (C1) helps; normalizing volatile content OUT of the prefix
   (timestamps/paths behind tools) is the bigger multiplier.
3. **Cache TTL turns cost into a scheduling problem** — sparse cron can't reuse cache;
   burst-batching within 5 min can. Invisible without measuring.
4. **Caching is a governance risk, not only a saving** — "stale cached definitions can serve
   incorrect answers at the same speed as correct ones." (Ties to G1 model-manifest lint.)
5. **Cost per SHIPPED unit, not per call** — Augment's discipline: sum ALL spend for a task
   (failed attempts + escalations), divide by changes meeting a quality bar. Per-call flatters;
   per-outcome is honest.
6. **Same-model self-reflection is mostly wasted tokens** — a model re-checking its own output
   with no new information tends to confirm its own hallucination; the frontier verifies with
   **deterministic tools (linter/compiler/tests)** and only re-invokes the LLM on an explicit
   error **[reported, DeepMind/OpenAI line of work]**. *Caveat for us:* this is NOT an argument
   against our VERIFY stage — an **independent adversarial refuter on fresh context** (different
   training prior, generator≠grader) is a different thing and stays valuable. The waste is
   same-model, same-context "reflect and double-check."
7. **Model-downgrade mid-task** — plan with a strong model, then route rote execution (apply a
   documented change across N files) to a cheap/local model. Using the top tier for rote typing
   is capital misallocation **[reported]** — reinforces X1 (local Ollama for grunt lanes).

---

## Where our fleet already matches the frontier, and where it doesn't

**Already right:** worktree/sub-agent isolation exists; modus prefers one-strong-agent + budget
and treats multi-agent as a deliberate token buy; interactive cache reuse is high (near-zero
uncached input in the audit); cron tier-1 migrated to Sonnet.

**Diverging (each maps to a cure):**
- Volatile content ahead of static doctrine in the prefix → **C1 + a volatility lint** (bigger
  than pure byte-slimming) — §7.2.
- No cache-TTL-aware cron batching → **P1/P2 launcher + burst scheduling** — §1/§6.
- Interactive sessions unbounded (300-500K, context-rot territory) → **M1 session breaker** —
  §2/§3.
- No single egress gateway; app/cron call the CLI directly → **X2 broker**, the panel's #1
  lever — §5; P1+P2 first brick.
- Metered Gemini seat with no budget projection/manifest, dies silent → **G1 pin+lint, G2
  closed-loop burn-rate**, and a gateway that turns depletion into a catchable 429 — §5/§6.
- Cost measured per-call, never per-shipped-outcome → adopt per-outcome metering as the KPI the
  whole plan is judged by — §7.5.

**§Solo-operatore:** none new — this is research, not an action. Model-default (M2) and Gemini
top-up remain Zero's per the plan file.

Related: `plan_token_consumption_7_structural_cures_2026_08_12` (the fleet-specific cures this
research backs).
