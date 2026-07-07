---
date: 2026-07-06
domain: operations
topic: xAI Grok Build + Composer 2.5 — capability audit and one-week council-seat evaluation
sources: 24
---

# Grok Build + Composer 2.5: What They Actually Are, and Whether They Earn a Council Seat

## Executive Summary

Both names in the mandate are real, current, and distinct — but they are not both xAI products, and "Grok Build" is not one thing over time. Disambiguation verdicts:

1. **"Grok Build" is real and is xAI's terminal-native agentic coding CLI**, launched in early beta May 14-15, 2026 for SuperGrok Heavy ($300/mo) subscribers only, expanded to all SuperGrok ($30/mo) and X Premium+ ($40/mo) subscribers by May 25, 2026 ([Android Headlines](https://www.androidheadlines.com/2026/05/xai-grok-build-agentic-ai-coding-tool-launch-beta.html); [CIO Dive](https://www.ciodive.com/news/xAI-coding-agents-Grok-Build/820422/)). It runs in the terminal, supports up to 8 parallel subagents, a plan-mode gate before execution, an evaluation layer called "Arena Mode" that ranks competing candidate outputs, and a `/goal` long-running autonomous mode added June 22, 2026 ([MarkTechPost](https://www.marktechpost.com/2026/06/22/xai-launches-goal-in-grok-build-adding-long-running-autonomous-execution-with-built-in-verification-for-multi-step-coding-tasks/)).

2. **"Composer 2.5" is NOT an xAI model.** It is **Cursor's** in-house coding model, released by Cursor (Anysphere) on May 18, 2026, built on Moonshot's open-source Kimi K2.5 checkpoint with heavy additional RL training ([cursor.com/blog/composer-2-5](https://cursor.com/blog/composer-2-5)). The operator's framing ("Composer 2.5 as available inside a Grok super-premium subscription") is a **real but easy-to-misread integration**, not a conflation error on the operator's part: on June 1, 2026 — three days after `grok-build-0.1` entered public API beta — xAI **licensed and embedded Composer 2.5 as a selectable model inside the Grok Build CLI** ([TechJack](https://techjacksolutions.com/ai-brief/xai-launches-composer-25-in-grok-build-cli-three-days-after/); [KuCoin](https://www.kucoin.com/news/flash/grok-build-integrates-composer-2-5-xai-terminal-agent-uses-cursor-s-core-model); [Surf AI](https://asksurf.ai/pulse/en/xai-cursor-composer-grok-build-orchestration)). So: **yes, a SuperGrok/X Premium+ subscriber genuinely gets Composer 2.5 access through the Grok Build terminal** — but the model itself is Cursor's, xAI is the orchestration/distribution layer, and this is an unusual cross-vendor licensing arrangement (xAI betting "orchestration matters more than owning the model," per the Surf AI headline) rather than an xAI-authored model with a confusingly similar name.

3. **Grok 5 has NOT shipped** as of this writing (2026-07-06) — it missed both its Q1 and Q2 2026 targets and remains in training on the Colossus 2 cluster ([NxCode](https://www.nxcode.io/resources/news/grok-5-release-date-latest-news-2026); [felloai](https://felloai.com/all-we-know-so-far-about-grok-5/)). The flagship chat model in the operator's subscription today is **Grok 4.3** (and the 4.20 family: reasoning/non-reasoning/multi-agent variants), all with 1M-token context. The coding-specific model is **`grok-build-0.1`**, 256K context — narrower than Grok 4.3's 1M and narrower than Claude/GPT-5.4 ([docs.x.ai/developers/models](https://docs.x.ai/developers/models), fetched directly, authoritative).

**Bottom line for the council-seat question**: Grok Build's own coding intelligence trails our existing arsenal on every published number (70.8% SWE-Bench Verified for the underlying `grok-code-fast-1`, vs. Codex CLI 88.7% and Claude Code 87.6% vendor-reported — not apples-to-apples methodology, but directionally consistent with practitioner reviews saying Grok "wins on autonomy/multi-file orchestration, loses on deep reasoning"). It does **not** clear bar (a) heterogeneous judgment in a meaningfully useful way for us, since Grok's underlying reasoning model isn't a distinct-enough prior to matter as a fifth refuter voice for KBLI/tax/legal work — we already have DeepSeek and GLM for that role. It **does** clear bar (b): it is the **only** member of our arsenal with native, first-party real-time X-platform search grounding, which is a genuine capability gap for our Indonesian-regulatory-chatter and 3-competitor OSINT monitoring. It does **not** clear bar (c) — there is no flat-subscription quota relief path for headless/automated use; the CLI's subscription-linked OAuth is built for a human at a terminal, and any cron/automation path requires a **separate, metered `console.x.ai` API key** ($1-2.50/M tokens on the coding model, plus $5/1,000 calls for X Search/Web Search) that falls under our "paid per-token API — requires Zero's explicit authorization" policy, not under the existing SuperGrok subscription entitlement.

**Recommendation**: use the one-week trial to (1) hand-test X Search/OSINT value directly in the Grok chat UI (subscription-included, zero incremental cost) against our existing competitor/regulatory-watcher outputs — this is the one capability worth verifying hard; (2) spot-check Grok Build CLI once against Claude Code on 2-3 throwaway non-PII coding tasks purely to have a first-hand data point, not to adopt it; (3) do **not** wire it into any cron/automation path during the trial — that requires a metered API key, which requires Antonello's authorization first, and the trial week alone doesn't justify that ask given the underlying model's benchmark and practitioner standing versus what we already run.

---

## 1. Subscription & Entitlements

### 1.1 Tier structure (as of July 2026)

| Tier | Price | What it includes |
|---|---|---|
| X Premium | $8/mo | Base X (Twitter) feature bundle, minimal Grok |
| SuperGrok Lite | $10/mo | Entry Grok chat |
| SuperGrok | $30/mo | Grok chat, Imagine, Build access (added May 25, 2026) |
| X Premium+ | $40/mo | X bundle + SuperGrok-equivalent Grok access, including Build |
| **SuperGrok Heavy** | **$300/mo** | Everything above **plus** Grok 4 Heavy (multi-agent reasoning, 256K ctx, parallel test-time compute), maximum rate limits, priority access at peak load, early previews |

Sources: [felloai.com/grok-pricing](https://felloai.com/grok-pricing/); [costbench.com/grok](https://costbench.com/software/ai-chatbots/grok/); [aitoolanalysis.com SuperGrok pricing](https://aitoolanalysis.com/supergrok-subscription-price-2026/); [Grokipedia SuperGrok Heavy](https://grokipedia.com/page/SuperGrok_Heavy).

SuperGrok Heavy originally launched July 9, 2025 at $300/mo and, as of the May 2026 tier expansion, is **no longer the sole gate to Grok Build** — that gate opened to the $30/$40 tiers ten days after Heavy-only early access. Heavy's remaining differentiators for coding purposes are Grok 4 Heavy access (a distinct multi-agent *chat* reasoning model, not itself a coding CLI) and unthrottled rate limits. **If the operator's "top-tier" subscription is Heavy, the coding-specific capability (Grok Build + Composer 2.5) is now also available on the far cheaper $30-40 tiers** — Heavy's marginal value for *this specific evaluation* is mainly headroom (no rate-limit throttling during a week of heavy testing) plus Grok 4 Heavy chat access, not an exclusive unlock of Build/Composer.

### 1.2 Usage model: pooled, not API-metered

SuperGrok Heavy subscribers draw from **one shared weekly usage pool spendable across any Grok surface** (Chat, Imagine, Voice, Build) rather than separate quotas per product ([search synthesis, multiple sources; treat exact numeric caps as unpublished/unverified per xAI's own non-disclosure of consumer quota tables]). This is architecturally similar to how Claude MAX pools usage across Claude Code/chat.

**Critical distinction for our automation ambitions**: this pooled subscription quota is tied to **interactive OAuth login** in the Grok Build CLI (browser-based, ties to the account holding the subscription). For **headless/CI/cron use**, Grok Build explicitly requires a **separate `GROK_CODE_XAI_API_KEY` created at console.x.ai** — a metered, pay-per-token API key, billed independently of the SuperGrok subscription ([Grok CLI installation docs](https://www.grokcli.dev/docs/getting-started/installation); corroborated by [github.com/superagent-ai/grok-cli](https://github.com/superagent-ai/grok-cli)). This means: **the "free-quota-relief" angle does not exist for our cron/automation use case.** The subscription gives a human at a terminal free rein; any unattended agent needs the metered key, which triggers our CLAUDE.md paid-API-authorization gate exactly like OpenRouter or a direct OpenAI key would.

---

## 2. Agentic Coding Surface Map

### 2.1 What Grok Build actually is

- **Form factor**: terminal-native CLI, single-command install (`curl -fsSL https://x.ai/cli/install.sh | bash`, or `npx grok-cli-hurry-mode@latest` for zero-install trial) ([Verdent install guide](https://www.verdent.ai/guides/grok-build-install); [uniflow.kr install guide](https://www.uniflow.kr/en/grok-build-cli-installation-guide/)).
- **Model powering it**: `grok-build-0.1`, xAI's coding-specific model, 256K context, $1.00/M input · $2.00/M output on the metered API (20% cheaper than flagship Grok 4.3's $1.25/$2.50) — confirmed directly from [docs.x.ai/developers/models](https://docs.x.ai/developers/models).
- **Multi-agent architecture**: runs up to 8 parallel subagents through a plan → search → build three-stage workflow per task ([buildfastwithai.com Grok Build review](https://www.buildfastwithai.com/blogs/grok-build-xai-cli-ai-agents-2026)).
- **Arena Mode**: an automated evaluation layer that scores/ranks multiple candidate outputs from parallel agents *before* a human reviews any of them — a built-in "best-of-N" selection step ([x.ai/news/grok-build-cli via search synthesis](https://x.ai/news/grok-build-cli) — page itself returned HTTP 403 to direct fetch, corroborated by 3 independent secondary sources).
- **Plan mode**: review/edit/approve a logical plan before any code changes execute — directly analogous to Claude Code's plan mode and Codex's approval gates.
- **`/goal` long-running mode** (added June 22, 2026): hands off a larger implementation task; the agent plans, executes to completion with built-in verification, and exposes status/pause/resume/clear controls ([MarkTechPost](https://www.marktechpost.com/2026/06/22/xai-launches-goal-in-grok-build-adding-long-running-autonomous-execution-with-built-in-verification-for-multi-step-coding-tasks/)) — comparable in spirit to our own `/goal`-shaped autonomous work but xAI-native rather than something we'd need to build.
- **Local-first**: xAI states no source code is transmitted to xAI servers for the local-first workflow claim (repeated across multiple secondary sources; **not independently verified against xAI's own privacy policy text in this pass** — flagged as single-thread-of-sources, worth a direct policy read before trusting for anything beyond throwaway test repos).

### 2.2 Benchmark reality check

- The oft-cited **70.8% SWE-Bench Verified** score belongs to the **now-deprecated `grok-code-fast-1`**, not the production `grok-build-0.1` CLI released May 20, 2026. **xAI has not published a SWE-Bench Verified number for the actual production model** ([codersera.com Grok Build vs Claude Code vs Codex](https://codersera.com/blog/grok-build-vs-claude-code-vs-codex-cli-2026/)).
- For scale reference (all vendor-self-reported, **not directly comparable** — different harnesses): Codex CLI 88.7%, Claude Code 87.6%, Grok's (deprecated model) 70.8%. A ~17-point gap on the last hard number xAI put out. Treat all three as marketing-adjacent; none is a controlled third-party eval.
- [Verdent's honest guide](https://www.verdent.ai/guides/grok-for-coding-2026) states plainly: the coding model is "not a replacement for a full reasoning model on complex architecture decisions, deep refactors spanning many files, or tasks requiring strong general knowledge" — and notes the 256K context "trails competitors" (Claude/GPT-5.4 both 1M+).

### 2.3 Practitioner verdicts (Hacker News / independent reviews, not vendor marketing)

- Consistent theme across [buildfastwithai](https://www.buildfastwithai.com/blogs/grok-build-xai-cli-ai-agents-2026), [jingrey.com beta review](https://jingrey.com/tools/grok-build-beta-review/), and secondary HN-thread synthesis: **"wins on autonomy and multi-file orchestration, Claude Code wins on conversational reasoning and code explanation."**
- Concrete honest limitations, direct from reviews (not spun): sometimes **invents API endpoints/method signatures that don't exist** (hallucination under agentic pressure — a familiar failure mode, worth guarding the same way we guard any model output); **no plugin ecosystem**; MCP support exists but is "powerful but requires manual configuration" (i.e., not turnkey); **skills ecosystem is tiny**; language support outside TypeScript/Python/JavaScript is "mediocre" — this matters for us since our stack is Python-heavy backend + some Swift native apps, and Swift specifically is not in Grok Build's strong-language list; **every invocation starts fresh, no persistent memory across sessions** (worse than Claude Code's session continuity); requires constant internet (no offline mode, a non-issue for us but notable).
- HN direct thread fetch (`news.ycombinator.com/item?id=48656943`) returned HTTP 429 on this pass — could not read raw comment text; relying on the secondary synthesis above from independent review sites is the honest caveat here, not a fabricated read of the thread.
- [CIO Dive](https://www.ciodive.com/news/xAI-coding-agents-Grok-Build/820422/) frames Grok Build as **entering a saturated, mature market late** — Claude Code and Codex "launched more than a year ago," and the same week Grok Build launched, PwC expanded Claude Code deployment to hundreds of thousands of employees and OpenAI shipped Codex into ChatGPT mobile. The enterprise-adoption signal is currently pointing away from Grok Build, not toward it.

**Verdict on Question 2**: Grok Build is a legitimate, functional, well-architected v1 coding agent (parallel subagents + Arena Mode + `/goal` are genuinely novel UX ideas worth studying even if we don't adopt the tool). It is **not currently competitive on raw coding capability** with Claude Code or Codex for our architecture-heavy, PII-sensitive, multi-service Python/Swift stack. The most interesting thing about it operationally is that it now **ships Composer 2.5 as a selectable engine** (see §3), which is arguably more relevant to us than xAI's own model.

---

## 3. Composer 2.5 Identity & Capabilities

**It is not an xAI model.** Full identity, confirmed directly from [cursor.com/blog/composer-2-5](https://cursor.com/blog/composer-2-5) (fetched and read in full):

- **Author**: Cursor (Anysphere), released **May 18, 2026** — two weeks *before* Grok Build's own coding model beta.
- **Base checkpoint**: Moonshot AI's open-source **Kimi K2.5**.
- **Training additions over Composer 2**: targeted RL with textual feedback for localized behavior correction, **25x more synthetic training tasks**, a "Sharded Muon" optimizer with distributed orthogonalization and dual-mesh HSDP for large-scale distributed training.
- **Design focus**: sustained work on extended tasks, complex instruction-following, multi-file high-precision editing, long-range instruction following.
- **Cursor's own pricing**: standard tier $0.50/M input · $2.50/M output; a "fast" interactive tier at $3/M input · $15/M output (Cursor's own blog explicitly says this fast tier undercuts "the fast tiers of other frontier models"). Cursor's CEO has stated Composer 2.5 is the most-chosen model inside Cursor today.
- **Note on future roadmap**: Cursor's blog post also discloses a forward-looking partnership — training "a significantly larger model from scratch" with **SpaceXAI**, using "10x more total compute" on Colossus 2's "million H100-equivalents." (This is the connective tissue explaining *why* xAI and Cursor ended up cross-licensing: SpaceX/xAI merged in February 2026 per the CIO Dive piece, and Cursor is now training its next model on xAI compute — Composer 2.5 riding inside Grok Build looks like an early fruit of that compute relationship, not a coincidence.)

### 3.1 How it's accessed via Grok Build specifically

- xAI embedded Composer 2.5 **inside the Grok Build CLI on June 1, 2026** — three days after `grok-build-0.1`'s own public API beta opened ([TechJack](https://techjacksolutions.com/ai-brief/xai-launches-composer-25-in-grok-build-cli-three-days-after/)).
- Access mechanics, per an X post from a tracked account (single-source on the exact number, flagged): "For SuperGrok and X Premium+ users, that means a 200,000-token context window, subagents and Git integration in the terminal" ([x.com/muskonomy status](https://x.com/muskonomy/status/2061527073026613340) — **this is a single social-media source for the 200K figure specifically; treat with more skepticism than the Cursor-blog-sourced facts above**).
- The operator's SuperGrok subscription genuinely surfaces Composer 2.5 as a selectable engine choice inside Grok Build's terminal — this is real, not a naming coincidence, per [KuCoin news](https://www.kucoin.com/news/flash/grok-build-integrates-composer-2-5-xai-terminal-agent-uses-cursor-s-core-model) and [Surf AI's analysis](https://asksurf.ai/pulse/en/xai-cursor-composer-grok-build-orchestration), both independently corroborating the TechJack report.

**Practical read for us**: if the operator wants Composer 2.5's actual editing quality (widely regarded — per Cursor's own claim of "most chosen model in Cursor" — as strong for sustained multi-file work), the **cheapest and most native path is a Cursor subscription itself**, not routing through Grok Build. Using it via Grok Build only makes sense if the value-add is specifically the Grok Build *orchestration* (8 parallel subagents, Arena Mode, `/goal`) wrapped around the Composer 2.5 *model* — i.e., testing whether xAI's agent harness gets more out of Composer 2.5 than Cursor's own IDE harness does. That is a genuinely interesting, narrow experiment, and it is one the one-week trial is well suited to answer cheaply.

---

## 4. Unique Assets — Realtime X/OSINT (the actual differentiator)

This is the section that matters most for whether Grok earns a seat, independent of coding capability.

### 4.1 What's unique

- **Real-time X (Twitter) search grounding is xAI-exclusive** among frontier labs — "no other frontier lab offers live social-graph retrieval" at this depth, per multiple pricing/comparison sources ([intuitionlabs.ai comparison](https://intuitionlabs.ai/articles/ai-api-pricing-comparison-grok-gemini-openai-claude); [aipricing.guru](https://www.aipricing.guru/xai-pricing/)).
- Grok 4.3/4.20 ships with **server-side X Search and Web Search tools** invokable through the API's tool-calling interface — `x_search` and `web_search`, following the same function-calling schema as OpenAI's (Grok's API is explicitly OpenAI-compatible at `https://api.x.ai/v1`, migration is "generate a key and change a URL" per multiple sources including [AG2 docs](https://docs.ag2.ai/latest/docs/user-guide/models/grok-and-oai-compatible-models/)).
- **X launched a hosted MCP server on June 30, 2026** giving "AI agents like Grok and Cursor instant, no-configuration access to real-time data from the X platform" ([basenor.com](https://www.basenor.com/blogs/news/x-launches-hosted-mcp-grok-and-ai-agents-get-real-time-data)) — this is directly relevant to us: **it means X-platform OSINT could in principle be wired into our existing MCP-based arsenal without touching the Grok CLI at all**, if we're willing to accept the metered API cost.
- Grok Build also natively supports **"Bring Your Own MCP"**, meaning we could point Grok Build's own agent at our internal MCP servers (`nuzantara-mcp`, `postgres-nuzantara` read-only, etc.) rather than the reverse ([Superagent blog on Grok CLI MCP support](https://www.superagent.sh/blog/grok-cli-mcp-support)).

### 4.2 Cost reality for our specific use case (competitor + regulatory OSINT)

- **X Search / Web Search: $5 per 1,000 calls** ($0.005/call), separate from token costs, confirmed directly from [docs.x.ai/developers/cost-tracking](https://docs.x.ai/developers/cost-tracking) via search synthesis and corroborated by [costgoat.com](https://costgoat.com/pricing/grok-api).
- This is a **metered, per-token/per-call API cost**, distinct from the SuperGrok subscription pool. For our `competitor-monitor` and `regulatory-watcher` agents, which currently run free (Ollama local vision pre-filter + Sonnet analysis, or Sonnet + NB-INTEL grounding), adding X Search calls would be a genuinely new recurring cloud spend line, not something the existing subscription absorbs.
- Concretely: a daily regulatory-watcher X-search sweep, even at a modest 20-30 calls/day, is ~$0.10-0.15/day (~$3-5/month) — trivially cheap in isolation, but it is **still a paid per-token API surface requiring the CLAUDE.md-mandated authorization step**, and it would need its own `console.x.ai` API key separate from the SuperGrok chat subscription.
- **Non-metered alternative worth testing during the trial**: simply **asking Grok chat directly** (inside the SuperGrok subscription, zero incremental cost) about live X sentiment/chatter on a specific Indonesian regulatory topic or one of our 3 competitors. This exercises the same underlying X-grounding capability without touching the metered API at all, and is fully within the one-week trial's "free" scope. This is the single highest-value, zero-cost experiment available to us this week.

### 4.3 Grok Imagine / Aurora (secondary asset, lower priority for us)

- Aurora is xAI's autoregressive image/video engine (paired with a Flux-based image stack), notable for **native audio+video sync generated in a single step** rather than diffusion-then-dub, and **Grok Imagine Video 1.5 currently tops the Image-to-Video Arena leaderboard**, ahead of ByteDance Seedance 2.0 and Google Veo ([atlascloud.ai guide](https://www.atlascloud.ai/blog/guides/grok-imagine-video-generation)).
- This is genuinely relevant background for our WR2/WR3 image/video pipelines (currently FlowKit/Veo-based) but is **out of scope for a coding-council evaluation** and would need its own separate cost/quality bake-off against Veo 3.1 if ever pursued — noting only as a flag for a future, different research task, not folding it into this week's plan.

---

## 5. Integration Paths

| Path | Mechanism | Cost model | Fits our arsenal? |
|---|---|---|---|
| Grok chat UI (web/app) | Browser, subscription login | Included in SuperGrok pool | Yes — zero-friction, zero-cost trial surface |
| Grok Build CLI, interactive | `curl` install, OAuth browser login | Included in SuperGrok pool (usage-pooled) | Yes for **manual, human-driven** spot-checks only |
| Grok Build CLI, headless/CI | `GROK_CODE_XAI_API_KEY` env var from console.x.ai | **Metered, separate from subscription** — $1/$2 per M tokens on grok-build-0.1 | **No** without Zero's explicit paid-API authorization (CLAUDE.md gate) |
| Grok API direct (chat/reasoning) | OpenAI-compatible endpoint, `api.x.ai/v1` | Metered — $1.25/$2.50 per M on Grok 4.3 | **No** without authorization; would slot as a 5th refuter/council seat if ever authorized |
| X Search / Web Search tools | Server-side tool call via API | **Metered, additional** — $5/1,000 calls | **No** without authorization; cheapest genuinely-unique capability if it ever is authorized |
| Hosted X MCP server (June 30, 2026) | `mcp__x-hosted__*`-style remote MCP | Unclear if bundled with API costs or subscription — **unverified, flag for follow-up if pursued** | Potentially the cleanest wiring path into our existing MCP-first architecture, but pricing model needs a direct docs.x.ai read before any commitment |
| Zero Data Retention (enterprise) | Enterprise sales contact (`sales@x.ai`) | Enterprise-negotiated | Not relevant at trial scale; consumer/API default is 30-day auto-delete unless ZDR negotiated ([x.ai enterprise ToS via search synthesis](https://x.ai/legal/terms-of-service-enterprise)) |

**ToS/data note**: the default (non-enterprise) retention is **auto-delete within 30 days of session end** unless retention is contractually extended or legally required; enterprise Zero Data Retention exists as an add-on. Since our policy is non-PII-only for any external paid API regardless, the default 30-day retention is acceptable for the kind of testing this week's trial would involve (public regulatory text, competitor public posts, throwaway code) — no PII would touch this surface under any circumstance per our absolute boundary, so the retention nuance is low-stakes here.

---

## 6. ONE-WEEK EVALUATION PLAN

Scope constraint: **stay entirely inside the SuperGrok subscription's included usage** (chat + Build CLI interactive use). Do **not** create a `console.x.ai` API key or touch metered X Search/Web Search calls this week — that step requires a separate authorization conversation with Antonello per CLAUDE.md, and this trial doesn't need it to get a real verdict on the two things that matter (X-grounding value, and Composer-2.5-via-Grok-Build coding quality).

| Day | Experiment | Non-PII task | Success criterion |
|---|---|---|---|
| **Day 1** | Baseline + install | Install Grok Build CLI (`curl -fsSL https://x.ai/cli/install.sh \| bash`), OAuth login with the trial subscription. Read xAI's own privacy/local-first claims directly (the x.ai/news pages 403'd on automated fetch — read manually in-browser) before pointing it at any repo, even non-PII. | CLI installed and authenticated; privacy claim independently confirmed, not just secondary-sourced. |
| **Day 2** | X-grounding value test (the highest-priority experiment) | In Grok chat (not Build, not API), ask 3-5 questions we'd normally route to `competitor-monitor` or `regulatory-watcher` — e.g. "what is Lets Move Indonesia / Emerhub / Flado posting on X this week about KBLI 2025 conversion" and "what's the live X chatter on [specific recent Permenkumham/PMK]." | Compare answer quality/freshness/specificity against what our existing Sonnet+NB-INTEL pipeline produced for the same week. Decide: did it surface anything our pipeline missed? |
| **Day 3** | Coding spot-check #1 — orchestration test | Point Grok Build (interactive, subscription-pooled) at a **throwaway clone** of a small, self-contained, non-PII utility script (e.g., a standalone formatter or a KBLI-lookup CLI stub) — never the production repo, never anything touching `dependencies.py`, migrations, or PII-adjacent code per our off-limits list. Try `/goal` mode for one multi-step task. | Does the 8-parallel-subagent + Arena Mode workflow produce a materially better first-pass result than a single Sonnet 5 pass on the same task? Note hallucination rate (watch specifically for invented API/method signatures — the documented failure mode). |
| **Day 4** | Coding spot-check #2 — Composer 2.5 via Grok Build | Same throwaway repo, explicitly select the Composer 2.5 engine inside Grok Build (if the model picker is exposed to non-Heavy tiers — confirm this Day 1). Compare its multi-file edit quality against the same task run through Claude Code / Sonnet 5. | Is there a discernible quality delta specifically attributable to Composer 2.5's editing model, separate from Grok Build's orchestration layer? This isolates "is the model good" from "is xAI's harness good." |
| **Day 5** | MCP wiring feasibility check (research only, no live wiring) | Read `docs.x.ai/developers/tools/remote-mcp` and the "Bring Your Own MCP" docs for Grok Build directly. Determine: could our `postgres-nuzantara` (read-only) or `nuzantara-mcp-advanced` servers be pointed at from Grok Build without any code change, purely as a manual/documentation exercise — do NOT actually connect it to production MCP servers this week. | Produce a one-paragraph feasibility note: yes/no/complexity, for a future authorized trial if we ever go further. |
| **Day 6** | Practitioner-parity gut check | Re-read the HN thread on Grok Build 0.1 directly in-browser (automated fetch 429'd twice this pass) and 2-3 fresh reviews from the trial week itself (search "Grok Build" + current week) to catch any capability changes mid-trial — xAI ships fast (May 14 → May 25 → June 1 → June 22 were all distinct capability jumps in under 6 weeks). | Confirm nothing material changed under us mid-week that would flip a Day 2-4 verdict. |
| **Day 7** | Synthesis + keep/drop decision | Write a 1-page internal verdict: (1) X-grounding — worth a future authorized metered trial? (2) Coding — does Grok Build/Composer 2.5 clear the bar to justify a 5th CLI in the council, or does it stay a "watch, don't adopt" item? (3) Concrete recommendation to Antonello, with cost estimate if any further step requires the paid-API authorization gate. | A decision, not a survey — keep, drop, or "revisit when Grok 5 ships / when hosted X MCP pricing is confirmed." |

**What this plan deliberately does NOT do**: it does not touch the metered API, does not create any recurring cron dependency, does not put Composer-2.5-via-Grok-Build in any production path, and does not process any client PII through xAI infrastructure at any point — consistent with the absolute PII boundary regardless of authorization status.

---

## 7. ACTIVE INCLUSION PROPOSALS (if it earns a seat beyond the trial)

These are concrete, scoped proposals — **each requires Antonello's explicit paid-API authorization before implementation**, per CLAUDE.md. None should be built during the trial week itself; they are what the trial's Day 7 verdict should be measured against.

1. **X-grounding sidecar for `regulatory-watcher` and `competitor-monitor`**: a narrow, capped-budget (e.g., $10/month hard ceiling) X Search integration that runs *only* as a supplementary signal alongside the existing NB-INTEL + Sonnet pipeline, never as a replacement. Justification would rest entirely on Day 2's trial finding.
2. **Grok 4.3 as a 5th council refuter voice** for non-PII architectural/spec review, specifically when we want a genuinely different training-prior opinion beyond DeepSeek/GLM — only if Day 3-4 shows its reasoning quality (not just its coding-agent orchestration) is distinctive enough to be worth the token cost over adding a third DeepSeek/GLM pass.
3. **Hosted X MCP server as a read-only OSINT tool** wired into our existing MCP-first architecture (`mcp__x-hosted__*`), gated the same way `postgres-nuzantara` is gated (read-only role, no mutation surface) — contingent on confirming its actual pricing model (unresolved in this pass, flagged in §5).
4. **Composer 2.5 via a direct Cursor subscription** (not through Grok Build) if Day 4's isolation test shows the model itself — independent of xAI's harness — is meaningfully better than Sonnet 5 for sustained multi-file edits. This would be a Cursor subscription decision, not an xAI one, and cheaper/cleaner than routing through Grok Build's orchestration layer if the orchestration isn't adding value.
5. **Grok Imagine/Aurora bake-off** against our current Veo 3.1/FlowKit pipeline for WR2/WR3 — explicitly out of scope for this trial, proposed only as a *separate future research task* given Aurora's leaderboard position, not something to fold into the coding-council decision.
6. **Do NOT propose**: Grok Build as a cron-automated coding agent in any production path. Nothing in the research this week supports it clearing our bar over Claude Code/Codex for architecture-sensitive, PII-adjacent work, and the headless path requires the same metered-key authorization as any other option with a worse benchmark standing.

---

## 8. Risks / ToS Notes

- **Fast-moving target**: capability jumped 4 times in 6 weeks (May 14 beta → May 25 tier expansion → June 1 Composer 2.5 integration → June 22 `/goal` mode). Any verdict from this week's trial has a short shelf life; treat it as a snapshot, not a permanent ruling.
- **Hallucinated API/method signatures** under agentic pressure is a documented, repeated finding across independent reviews — same failure class we already guard against with any LLM output, but worth explicit attention if any Grok Build output is ever considered for even throwaway-repo use, let alone anything closer to production.
- **No offline mode** — irrelevant operationally for us (we're always networked) but confirms it's a pure cloud dependency, same trust model as our existing cloud LLM CLIs.
- **x.ai/news pages return HTTP 403 to automated fetch** — this affected two direct-source verifications in this research pass (the original Grok Build launch post and the Composer 2.5 announcement post). All claims from those pages in this report are corroborated through ≥2 independent secondary sources instead of the primary xAI blog text; flagged per the mandate's disambiguation-with-evidence requirement. A human should manually verify these two pages in-browser before any authorization decision, since 403-to-automation is not the same as unavailable-to-a-logged-in-human.
- **ToS/data retention** is standard for a consumer/API product (30-day auto-delete, enterprise ZDR available on request) and is compatible with our non-PII-only usage policy for any external paid surface.
- **Merger context**: xAI/SpaceX merged in February 2026 per CIO Dive's framing; SpaceX's anticipated IPO was cited as backdrop to the Grok Build launch. This is background noise for our evaluation, not a direct risk, but explains the compute relationship behind the Cursor/Composer-2.5 licensing deal (§3) and the aggressive shipping cadence.

---

## 9. Open Questions (unresolved in this pass, worth a follow-up if pursued further)

1. Exact numeric weekly usage-pool caps for SuperGrok Heavy are **not published by xAI** — any claim of a specific number found in secondary sources should be treated as unverified until read directly from an authenticated `grok.com/plans` account view.
2. Whether the Composer-2.5-inside-Grok-Build model picker is exposed to **all** SuperGrok tiers or gated to Heavy specifically — Day 1 of the trial plan resolves this empirically since the operator has Heavy access this week.
3. Pricing model for the newly-launched (June 30, 2026) hosted X MCP server — bundled with subscription, or its own metered line — unresolved; flagged in §5 and §7.3, needs a direct `docs.x.ai` read before any wiring proposal.
4. The 200,000-token context figure for Composer-2.5-via-Grok-Build (vs. the 256K figure for Grok's own coding model) comes from a single X-post source ([§3.1](#31-how-its-accessed-via-grok-build-specifically)) and should not be treated as load-bearing without a second corroboration.
5. Whether xAI's "local-first, no source code transmitted" claim for Grok Build holds up against a direct read of their privacy policy text — flagged as Day 1 due diligence in the evaluation plan, not yet independently confirmed in this research pass.

---

## Sources

Primary (directly fetched, full text read):
- [cursor.com/blog/composer-2-5](https://cursor.com/blog/composer-2-5) — Composer 2.5 identity, training, pricing, release date
- [docs.x.ai/developers/models](https://docs.x.ai/developers/models) — authoritative model list, context windows, pricing

Attempted-but-blocked primary (403/429, corroborated via ≥2 secondary sources instead):
- x.ai/news/grok-build-cli (403)
- x.ai/news/composer-2-5 (403)
- news.ycombinator.com/item?id=48656943 (429)

Secondary (search-synthesized, cross-corroborated):
- [buildfastwithai.com — Grok Build CLI Reviewed](https://www.buildfastwithai.com/blogs/grok-build-xai-cli-ai-agents-2026)
- [ciodive.com — xAI joins crowded coding agent race](https://www.ciodive.com/news/xAI-coding-agents-Grok-Build/820422/)
- [verdent.ai — Grok for Coding 2026](https://www.verdent.ai/guides/grok-for-coding-2026)
- [verdent.ai — Grok Build Install Guide](https://www.verdent.ai/guides/grok-build-install)
- [devops.com — xAI Enters the Coding Agent Race](https://devops.com/xai-enters-the-coding-agent-race-with-grok-build/)
- [codersera.com — xAI Dev Stack 2026](https://codersera.com/blog/xai-grok-build-skills-connectors-guide-2026/)
- [androidheadlines.com — Grok Build launch beta](https://www.androidheadlines.com/2026/05/xai-grok-build-agentic-ai-coding-tool-launch-beta.html)
- [marktechpost.com — /goal launch](https://www.marktechpost.com/2026/06/22/xai-launches-goal-in-grok-build-adding-long-running-autonomous-execution-with-built-in-verification-for-multi-step-coding-tasks/)
- [llmreference.com — Composer 2.5 vs Grok Build 0.1 compare](https://www.llmreference.com/compare/composer-2-5/grok-build-0.1)
- [techjacksolutions.com — Composer 2.5 in Grok Build CLI](https://techjacksolutions.com/ai-brief/xai-launches-composer-25-in-grok-build-cli-three-days-after/)
- [note.com/ai_masaki — Grok Composer 2.5 launch (Cursor pricing comparison)](https://note.com/ai_masaki/n/n53ea66c1b3b7?hl=en)
- [kucoin.com — Grok Build integrates Composer 2.5](https://www.kucoin.com/news/flash/grok-build-integrates-composer-2-5-xai-terminal-agent-uses-cursor-s-core-model)
- [asksurf.ai — xAI puts Cursor's Composer 2.5 inside Grok Build](https://asksurf.ai/pulse/en/xai-cursor-composer-grok-build-orchestration)
- [x.com/muskonomy status (single-source, flagged)](https://x.com/muskonomy/status/2061527073026613340)
- [felloai.com — Grok Pricing 2026](https://felloai.com/grok-pricing/)
- [costbench.com — Grok pricing breakdown](https://costbench.com/software/ai-chatbots/grok/)
- [aitoolanalysis.com — SuperGrok Subscription Price 2026](https://aitoolanalysis.com/supergrok-subscription-price-2026/)
- [grokipedia.com — SuperGrok Heavy](https://grokipedia.com/page/SuperGrok_Heavy)
- [grokipedia.com — Grok 5](https://grokipedia.com/page/Grok_5)
- [nxcode.io — Grok 5 release date](https://www.nxcode.io/resources/news/grok-5-release-date-latest-news-2026)
- [intuitionlabs.ai — AI API Pricing Comparison](https://intuitionlabs.ai/articles/ai-api-pricing-comparison-grok-gemini-openai-claude)
- [docs.ag2.ai — Grok API OpenAI-compatible guide](https://docs.ag2.ai/latest/docs/user-guide/models/grok-and-oai-compatible-models/)
- [basenor.com — X launches hosted MCP](https://www.basenor.com/blogs/news/x-launches-hosted-mcp-grok-and-ai-agents-get-real-time-data)
- [superagent.sh — Grok CLI Gets MCP Support](https://www.superagent.sh/blog/grok-cli-mcp-support)
- [atlascloud.ai — Grok Imagine Video Generation guide](https://www.atlascloud.ai/blog/guides/grok-imagine-video-generation)
- [grokcli.dev — Installation & Setup Guide](https://www.grokcli.dev/docs/getting-started/installation)
- [github.com/superagent-ai/grok-cli](https://github.com/superagent-ai/grok-cli)
- [costgoat.com — Grok API Pricing Calculator](https://costgoat.com/pricing/grok-api)
- x.ai enterprise ToS / data retention (search-synthesized from x.ai/legal/terms-of-service-enterprise, direct fetch not attempted this pass — page requires no auth per prior 403 pattern being news-subdomain-specific, but not independently confirmed)

Total distinct sources cited: 30 (24 unique domains).
