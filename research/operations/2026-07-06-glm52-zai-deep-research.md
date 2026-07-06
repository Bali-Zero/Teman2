---
date: 2026-07-06
domain: operations
topic: "Zhipu GLM 5.2 (z.ai) — model, Coding Plan, platform surface, ecosystem, and exploitation for Nuzantara"
sources: 27
---

# GLM 5.2 / z.ai Deep Research — Second Brain Exploitation Audit

## Executive Summary

GLM-5.2 (Zhipu/Z.ai, shipped June 13–17, 2026, ~753B params, MIT-licensed open weights) is a genuinely near-frontier, text-only coding/agentic model: 62.1 SWE-bench Pro, 81.0 Terminal-Bench 2.1 (within a few points of Claude Opus 4.8's 85.0), 91.2 GPQA-Diamond, native 1M context via an architecture called IndexShare that cuts per-token FLOPs 2.9× at that length. It is **not** multimodal — vision lives in a separate sibling model (GLM-5V-Turbo), and the "Vision Understanding" tool visible in our GLM Coding Plan is almost certainly a routed call to that sibling, not native 5.2 sight. Our current usage — `claude-glm` wrapper as an exhausted-MAX fallback and 3rd council refuter seat — captures maybe two of at least seven capabilities the flat-fee Coding Plan actually bundles: it also includes Web Search/Web Reader (with monthly call allocations by tier), a Vision Understanding MCP tool, and — separately, at the API-platform layer rather than the plan — video generation (CogVideoX-3, up to 4K), embeddings, speech-to-text/TTS, and prompt caching (~80-90% discount on repeated prefix). The plan is genuinely a full second harness: Z.ai ships its own agentic IDE (ZCode) and lists 20+ compatible clients.

The single most operationally important finding: **the "529 load-shedding" we've been observing on large requests is very likely not literal server overload — it's Z.ai's peak-hour quota multiplier.** Z.ai deducts prompt-quota at 3× during peak hours (14:00–18:00 China time = 14:00–18:00 UTC+8, i.e. roughly 07:00–11:00 UTC / 15:00–19:00 WITA) and 2× off-peak, with a promotional 1× off-peak rate through end of September 2026. A large request during Bali business hours (which overlaps China peak) burns 3× the prompt-quota of the same request run late at night. This reframes "hours of 529s" from an infrastructure problem to a scheduling problem we can route around today, for free.

On judge-quality specifically: I could not find dedicated research or practitioner writeups on GLM-5.2 as a PR-reviewer/refuter role. The closest evidence is a single-task Semgrep security benchmark (IDOR vulnerability detection only) where GLM-5.2 scored 39% F1 vs Claude Code (Opus 4.6/4.7/4.8) at 28-37% F1 — the authors themselves caveat this hard ("one task, one dataset, one run," may not generalize to other vuln classes). This is suggestive, not proof, that GLM is a credibly independent second opinion on security-adjacent code review; it is not evidence about sycophancy or adversarial-council behavior specifically. Treat any "GLM beats Claude" headline in vendor/practitioner blogs with the same skepticism CLAUDE.md already applies to single-source benchmark claims.

Roadmap risk over a 6-month horizon looks low-to-moderate: GLM has shipped on a ~2-month cadence (GLM-5 Feb 2026 → 5.1 Apr → 5.2 June), Zhipu's founder publicly polled the community on June 29 asking what GLM 5.3 needs (answer: vision, near-unanimously), and CGTN reported "GLM 5.5" rumored for August 2026 — none of this is confirmed by Zhipu itself. The MIT license is the real stabilizer: even if the hosted API changes pricing/availability, the GLM-5.2 weights themselves are permanently ours to self-host, unlike a closed API dependency.

## Model Capability Map

### Coding & agentic (official Zhipu blog, huggingface.co/blog/zai-org/glm-52-blog)

| Benchmark | GLM-5.2 | Notes |
|---|---|---|
| SWE-bench Pro | 62.1 | up from 58.4 on GLM-5.1 (+3.7) |
| Terminal-Bench 2.1 (Terminus-2 harness) | 81.0 | best-reported harness config: 82.7. Claude Opus 4.8 = 85.0 (from search synthesis, [single-source cross-ref, not independently re-verified against an Anthropic-published number in this pass]) |
| DeepSWE | 46.2 | |
| ProgramBench | 63.7 | |
| NL2Repo | 48.9 | |
| FrontierSWE (long-horizon) | 74.4 | described as "trails Opus 4.8 by only 1%" |
| PostTrainBench | 34.3 | outperforms Opus 4.7 and GPT-5.5 per Zhipu's own framing — vendor self-report, needs independent confirmation |
| SWE-Marathon | 13.0 | "13% behind Opus 4.8" — this is one of the weaker relative results, i.e. GLM's long-horizon edge narrows on the longest tasks |
| HLE (Humanity's Last Exam) | 40.5 | |
| HLE w/ tools | 54.7 | |
| AIME 2026 | 99.2 | |
| GPQA-Diamond | 91.2 | |
| MCP-Atlas (public set) | 76.8 | agentic tool-use |
| Tool-Decathlon | 48.2 | agentic tool-use |

A second independent tracker (BenchLM.ai, provisional leaderboard) gives category composites: Coding 83.7/100, Agentic 70.9/100, Knowledge 84.0/100, ranking GLM-5.2 #17/124 overall — consistent directionally with the official numbers but not a like-for-like re-derivation (BenchLM's Reasoning/Math/Multimodal rows showed 0.0, likely meaning "not yet scored" rather than a real zero — treat as incomplete data, not a finding).

**vs DeepSeek V4 Pro** (the model we already use as council refuter): GLM-5.2 reportedly leads on 4 shared benchmarks — Pro (+6.7), HLE w/tools (+6.5), MCP Atlas (+3.4), HLE (+2.8) — but DeepSeek V4-Pro leads LiveCodeBench (93.5) with no published GLM-5.2 LiveCodeBench score found. **[Both figures single-source from search-engine synthesis of the same comparison article; I did not independently reproduce the underlying benchmark run.]**

### Context, architecture, reasoning modes

- **1,000,000 token native context**, enabled via the `glm-5.2[1m]` model-ID suffix (matches our own `claude-glm` wrapper config — confirmed this is not a typo on our side, it's the documented activation mechanism).
- **IndexShare**: reuses the same indexer across every 4 sparse-attention layers, cutting per-token FLOPs 2.9× at 1M context — this is the architectural reason GLM can offer 1M context at plausible cost/latency where many competitors can't.
- **Effort-level control**: "High" or "Max" reasoning-effort modes trading capability for speed/cost — conceptually parallel to Claude's `reasoning_effort` and our own DeepSeek `low/high/max` modes. No published absolute latency numbers found in this pass.
- **Vision: GLM-5.2 itself is text-only.** Multiple sources agree ("no explicit vision capabilities mentioned" — official blog; "text-only... cannot process images" — comparison blogs). Vision is a **separate model, GLM-5V-Turbo** (native multimodal, CogViT vision encoder, images/video/document-layout). This resolves the apparent contradiction with the z.ai FAQ's "Vision Understanding" MCP tool inside the Coding Plan — that tool is almost certainly a server-side route to GLM-5V-Turbo, not a 5.2 capability. **Practical implication for us: GLM cannot replace qwen2.5vl:7b for OCR/vision under our sovereignty rules regardless — that boundary was never really in question — but if we ever wanted cloud vision fallback for non-PII use, GLM-5V-Turbo (not 5.2) is the actual target, and it appears to be closed-weight (unlike 5.2's MIT release).**

### Stated/observed weaknesses vs Claude

- Claude Opus maintains an edge on **knowledge-heavy accuracy** — the "AA-Omniscience Hallucination Rate" benchmark reportedly shows the widest gap here (practitioner comparison blog, not independently verified).
- Claude pulls ahead on **debugging complex issues** specifically (same source class).
- GLM is **multimodal-blind** — cannot read screenshots/diagrams, a real practical gap for any workflow (like our WR2 critic, or CRM document review) that needs to look at an image.
- One practitioner anecdote: GLM-5.2 "sometimes hallucinates plans it does not follow" — i.e., states an intended approach then silently deviates. This is a single anecdote, not a benchmark, but it's a concrete, checkable failure mode worth watching for in our own usage (does the plan GLM states in its first message match what it actually did?).
- Positive counter-finding: GLM reportedly handles **code-switching / mixed-language prompts** with fewer hallucination artifacts than Western-centric models — plausibly relevant to us given how much of our work is Italian/Indonesian/English mixed.

## Platform Surface & Quotas

### Coding Plan tiers (flat subscription — this is what we're on)

| Tier | Price/mo (list → promo) | 5-hr prompt cap | Weekly cap | MCP calls/mo |
|---|---|---|---|---|
| Lite | $18 → ~$16.20 promo | ~80 | ~400 | not specified (Web Search: 100/mo per FAQ) |
| Pro | $72 → ~$50.40 promo (~$64.80 per another source — figures disagree slightly, both single-source) | ~400 | ~2,000 | ~1,000 |
| Max | $160 → ~$112 promo | ~1,600 | ~8,000 | ~4,000 |

**[Two price-figure sources disagree on exact promo pricing ($50.40 vs $64.80 for Pro) — this is a live promotional pricing page that different scrapes caught at different moments; treat exact $ as approximate, the tier ratios (Lite:Pro:Max ≈ 1:5:20 in the "20+×" framing from ZCode's own materials) as more reliable.]**

- Each prompt typically drives 15-20 underlying model calls; Z.ai frames the monthly token allowance as "equivalent to approximately 15-30× the monthly subscription fee" if bought via metered API — i.e., the flat plan is explicitly a bulk discount, not a rate-limited trial.
- **The 529/overload behavior we've hit**: no dedicated Z.ai "load-shedding policy" doc was found, but the quota-multiplier mechanic is the best explanation for what we're calling load-shedding. **Peak = 14:00-18:00 China Standard Time (UTC+8) = 06:00-10:00 UTC = 14:00-18:00 WITA.** During that window GLM-5.2/5-Turbo burn quota at 3× the nominal rate; off-peak it's 2×, with a limited-time 1× off-peak promo live through end of September 2026. A large batch job run during Bali/China business-hour overlap will exhaust a 5-hour window ~1.5-3× faster than the same job run at 22:00-06:00 WITA.
- Quota exhaustion just blocks until the next 5-hour window resets — **it does not overflow into metered billing.** No surprise-charge risk from hammering it.
- Separately, GitHub issue trackers show real operational friction: a documented "concurrent request limit of 1" complaint (opencode project) suggests GLM Coding Plan connections may not parallelize well — worth testing before we assume we can run multiple simultaneous GLM sessions across the fleet without contention. Also documented: 404-classified-as-overloaded bugs and a system-prompt-string-triggered 429 (both third-party-tool bug reports, not Z.ai-acknowledged issues) — evidence the ecosystem around GLM is younger/rougher than Claude's, consistent with our own observed instability.

### API platform (pay-per-token, separate from Coding Plan)

- **Prompt caching**: ~80-90% discount on cached-prefix tokens (cached rate ~$0.26/1M vs $1.40/1M fresh input on the primary API; third-party hosts like Fireworks/DeepInfra offer steeper cached discounts). This matters if we ever move any GLM workflow to metered API — repo-context-heavy agentic loops benefit disproportionately.
- **Beyond chat**: Z.ai's broader platform (confirmed via official GitHub org + docs, not just the Coding Plan) includes video generation (CogVideoX-3, quality/speed modes, up to 4K/60fps), text embeddings (custom dimensions, batch), and speech-to-text/TTS — none of this is bundled in the Coding Plan; it's separate metered API surface under the same account.
- Could not confirm a batch API in the OpenAI/Anthropic sense (async bulk job submission) — no source found confirming or denying this exists.

## Ecosystem Tooling

- **ZCode** — Z.ai's own official agentic coding harness (Electron desktop app), launched as a Cursor/Claude-Code/Copilot competitor. Features: 1M context held across a whole repo simultaneously, multi-agent "Goals," remote bot control from WeChat/Feishu/Telegram (notably not Slack/Telegram-only — this is a China-market-first tool), plugin architecture, BYOK support for Claude Code/Gemini/Codex models too. Pricing $16-144/mo tiers roughly mirroring the Coding Plan. This is a genuine alternative interface we are not using — we exclusively drive GLM through the Claude-Code-compatible endpoint.
- **Claude Code compatibility** (what we already use): confirmed official first-class support. Setup is exactly 3 env vars (`ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`, `API_TIMEOUT_MS`) in `~/.claude/settings.json`, or an automated helper (`npx @z_ai/coding-helper`). Because it's the Anthropic-compatible endpoint, **our existing MCP servers, skills, and hooks all pass through unmodified** — confirming there's no reason our GLM seat should be missing any tool access our Claude seats have, other than model-quality differences.
- **AutoGLM / GLM-PC**: Zhipu's separate computer-use / phone-use agent line (AutoGLM-Web browser agent, GLM-PC desktop agent, AutoGLM2.0 phone agent for apps like Douyin/Meituan). Reportedly beats ChatGPT Agent and Claude 4 Sonnet on the "DeviceUse" benchmark. This is architecturally distinct from GLM-5.2-the-LLM — it's a separate product line built on GLM-4.5/4.5V, oriented at Chinese consumer apps. Low relevance to us today (we have no computer-use need it would serve better than our existing browser-automation skill), but worth flagging as a capability that exists if we ever need autonomous desktop-UI operation.
- **20+ supported clients** claimed for the Coding Plan (Claude Code, Cline, Roo Code, OpenCode, OpenClaw among named ones) — we're using exactly one of these paths.

## Roadmap & Stability

- Release cadence: GLM-5 (Feb 2026) → GLM-5.1 (Apr 2026) → GLM-5.2 (June 13-17, 2026) — roughly bimonthly major version bumps, each with real benchmark movement (not cosmetic version bumps).
- June 29, 2026: Zhipu founder Jie Tang publicly polled the community on X for "must-have" features in the next GLM version; the poll (466k+ views) returned vision as the overwhelming answer — strong signal Zhipu is listening to exactly the gap this report identified (5.2 is vision-blind).
- "GLM 5.5" rumored for August 2026 per a June 30 CGTN report — **[single-source, not confirmed by Zhipu]**. No confirmed GLM-5.3 date or scope.
- **Stability for a 6-month build horizon: moderate-to-good.** The API/Coding-Plan surface could shift pricing or quota terms (it already has, with the peak/off-peak multiplier being a fairly recent and not-obviously-permanent mechanic), but the **MIT-licensed open weights are a durable hedge** — if Z.ai's hosted service degrades or the Coding Plan is discontinued, GLM-5.2's actual weights remain self-hostable indefinitely (we already run Ollama fleet-wide; a 753B model is far beyond what we'd self-host today, but the option exists in principle via a rented GPU box if the hosted plan ever became unavailable). No deprecation-policy document was found for older GLM versions specifically.

## Judge-Quality Evidence

This was the weakest-evidenced research question. Direct academic literature on GLM-5.2-as-judge does not appear to exist yet (the sycophancy/LLM-judge papers found are all provider-agnostic, from before GLM-5.2's release). The one concrete data point:

**Semgrep security benchmark** (semgrep.dev blog, 2026): single task = IDOR (Insecure Direct Object Reference) vulnerability detection, single dataset, single run. F1 scores: GLM-5.2 (bare prompt, Pydantic AI harness) 39% vs Claude Code Opus-4.6 37%, Opus-4.7/4.8 28%. Cost ~$0.17/vuln found for GLM. The authors are explicit that this is **not generalizable** ("might well" differ for other vuln classes like SSRF) and that harness/tooling quality (a custom multimodal endpoint-discovery harness scored 53-61% regardless of underlying model) mattered more than model choice. This tells us GLM-5.2 is *competent* at a narrow, well-specified code-analysis task when compared head-to-head with Claude under matched-ish conditions — it does not tell us anything about GLM's behavior as an adversarial council refuter (does it hold a contrarian position under pushback, or fold?) or as a PR-quality judge across the kind of heterogeneous changes our repo actually produces.

**Assessment for our two roles**:
- **"Standing second opinion on every PR"**: plausible fit on narrow, benchmark-adjacent code-quality/security checks (the Semgrep result is weak-but-real evidence here); untested on architectural/style/business-logic review, which is most of what our PRs actually need judged.
- **"Refuter in adversarial councils"**: no evidence found either way on GLM's specific sycophancy or independence characteristics. The general LLM-judge literature (not GLM-specific) suggests models are more reliable at *evaluating* two given answers than at *holding* a position under user pushback — if that generalizes to GLM, its refuter value is probably real for "does this claim have a hole" but should not be assumed to hold up if council participants push back hard on GLM's own refutation.
- **Compared to DeepSeek** (our incumbent refuter): GLM appears to have a real edge on agentic/tool-use benchmarks (MCP-Atlas +3.4, Tool-Decathlon) but DeepSeek leads LiveCodeBench by a wide margin (93.5 vs unpublished for GLM). For "logical hole-finding in a finished dossier" (DeepSeek's current CLAUDE.md-assigned role), no evidence surfaced that GLM is better or worse — this would need an actual side-by-side test on our own real dossiers, not benchmark inference.

## Active Inclusion Proposals for Nuzantara

Ranked by expected-gain/cost/risk, most compelling first:

1. **Reschedule large `claude-glm` batch calls off China peak hours.** What: nothing to build — just avoid firing large/long GLM requests during 14:00-18:00 WITA (which overlaps 14:00-18:00 China time, i.e. GLM peak). Invocation path: any cron/wrapper currently calling `claude-glm` for heavy work (regulatory-watcher tier-2 fallback, wr2-ig-metrics-analyst if ever routed to GLM) should prefer off-peak windows, and ideally the 22:00-06:00 WITA window to also catch the 1× off-peak promo (through Sept 2026). Expected gain: directly attacks the "hours of 529s" pain reported today — likely converts several-times-faster quota burn into normal burn, for zero engineering cost. Risk: none — this is a scheduling change, fully reversible.
2. **Route GLM's bundled Web Search/Web Reader MCP tool into deep-researcher and regulatory-watcher as an additional free search lane.** What: the Coding Plan already includes Web Search & Web Reader with monthly call allocations (100/1,000/4,000 by tier) that we are currently paying for and not using — we do all web research through Claude's own WebSearch. Invocation path: when running `claude-glm` sessions (already the Tier-2/refuter path), explicitly invoke its native web-search tool for cross-verification searches instead of relying solely on Claude's. Expected gain: a second, differently-biased search index (Chinese-model search routing may surface different/complementary sources, useful for adversarial verification per our 4-LLM-panel doctrine) at zero marginal cost since it's already paid for. Risk: low — PII boundary applies exactly as it already does for any cloud search (no client data in queries).
3. **Add GLM-5.2 as a documented 4th benchmark-adjacent second-opinion specifically for security/vuln-pattern review, not general PR review.** What: given the Semgrep IDOR result, GLM plausibly adds real signal specifically for "does this code have an authorization/access-control hole" style checks — a narrower, better-evidenced claim than "GLM reviews all PRs." Invocation path: `devils-advocate`-style agent step, gated to security-relevant diffs (auth, RBAC, `dependencies.py`, migrations touching permissions) rather than every PR. Expected gain: incremental — one more lens on a class of bug we've been bitten by before (CRM RBAC, off-limits files). Risk: low, but don't over-claim generality — the evidence is one task, one dataset, one run; treat GLM's verdict here as a hint to investigate, not a pass/fail gate.
4. **Try ZCode as an alternative interface for one bounded experiment (not a switch), specifically to test the "multi-agent Goals" and full-repo-in-context claims on a real overnight task.** What: Z.ai's own harness, not the Claude-Code-compatible endpoint we already use — a genuinely different surface (Electron desktop app, remote bot control via Telegram). Invocation path: a single supervised trial task (e.g., a large but well-scoped refactor or a KBLI-book batch-consistency sweep) run through ZCode instead of `claude-glm`, to see if its long-horizon repo-in-context handling meaningfully outperforms our current Claude-Code+GLM combo for that task class. Expected gain: unclear until tested — this is explicitly a "go find out" proposal, not a confirmed win. Risk: low (sandboxed trial), but real setup cost (new tool, new auth, Electron app on a Mac we'd need to dedicate).
5. **Do NOT route vision/OCR work to GLM under any circumstance** — this is a negative-inclusion finding worth recording explicitly so nobody "helpfully" tries it later. GLM-5.2 is confirmed text-only; the only vision-capable sibling (GLM-5V-Turbo) is closed-weight and unverified for our purposes, and our sovereignty rule (qwen2.5vl:7b local-only for PII-scope OCR) was never actually in tension with GLM anyway. Recording this closes the "wait, could GLM read a KTP" question before someone spends time testing it.
6. **Skip prompt caching / metered-API optimization for now** — it's real (~80-90% discount) but only matters if/when we move any GLM workflow off the flat Coding Plan onto pay-per-token API, which we have no current plan to do. Flag as a lever to pull only if Coding Plan quota (even off-peak) becomes the binding constraint.
7. **Do not adopt AutoGLM/GLM-PC computer-use** at this time — it's a different product line (built on GLM-4.5/4.5V, not 5.2), China-consumer-app-oriented (Douyin/Meituan), and we already have a working browser-automation skill via Playwright/claude-in-chrome. No evidence found that it would outperform our existing stack for our actual use cases (deploy QA, WR2 IG publish).

## What We're Wasting

Concretely, on the current flat-fee Coding Plan we appear to be paying for and not using: (a) the bundled Web Search/Web Reader MCP tool (proposal #2), (b) any peak/off-peak scheduling awareness (proposal #1 — this is the one costing us the most in observed pain today), (c) the ZCode native harness as an alternative surface (proposal #4, unconfirmed value), and (d) — outside the Coding Plan but same account — video-gen, embeddings, and TTS/STT on the metered API side, none of which currently have an obvious fit in our pipeline (WR3 already has its Veo-based video pipeline and Chatterbox TTS fallback under separate governance) but are worth knowing exist.

## Open Questions

- Exact Pro-tier promo price ($50.40 vs $64.80/mo — two sources disagreed); worth checking the live billing page or our own invoice rather than trusting either search result.
- Whether the "concurrent request limit of 1" GitHub complaint (from a different tool, opencode) applies to our own `claude-glm` wrapper usage pattern — untested by us directly.
- No primary-source confirmation of the exact peak-hour UTC+8 window boundaries beyond "14:00-18:00" — worth reading the actual docs.z.ai overview page directly (fetch of that URL in this pass returned only nav-menu content, not the pricing/quota body text) rather than relying on search-engine synthesis of it.
- Whether GLM-5.2's LiveCodeBench score exists anywhere (unpublished per every source checked) — if Zhipu hasn't run/released it, that's itself informative (possible weak spot they're not advertising).
- No test in this research of GLM's actual behavior as an adversarial refuter under pushback (holds position vs folds) — this needs an empirical trial on our own council transcripts, not more searching.

## Sources

1. https://huggingface.co/blog/zai-org/glm-52-blog — official Zhipu benchmark blog (primary source for benchmark table)
2. https://benchlm.ai/models/glm-5-2 — independent benchmark tracker
3. https://arxiv.org/pdf/2602.15763 — GLM-5 technical paper (metadata confirmed; body not extractable as text in this pass)
4. https://apidog.com/blog/glm-5-2-benchmarks/ — SWE-bench Pro benchmark cross-reference
5. https://codingfleet.com/blog/glm-5-2-vs-deepseek-v4-pro/ — GLM vs DeepSeek comparative benchmarks
6. https://docs.z.ai/devpack/faq — official Coding Plan FAQ (quota tiers, MCP tools)
7. https://docs.z.ai/devpack/tool/claude — official Claude Code integration docs
8. https://docs.z.ai/devpack/overview — Coding Plan overview
9. https://z.ai/subscribe — pricing page (nav-only in this fetch; pricing cross-verified via search)
10. https://www.aipricing.guru/z-ai-subscription-pricing/ — third-party pricing tracker
11. https://medium.com/@elio.verhoef/glm-coding-plan-how-i-get-3-claude-max-code-usage-for-30-month-07503db5eeb2 — practitioner value analysis
12. https://github.com/anomalyco/opencode/issues/8618 — concurrent-request-limit bug report
13. https://github.com/openclaw/openclaw/issues/31234 — z.ai provider usage-error bug report
14. https://github.com/letta-ai/letta-code/issues/1394 — base_url/subagent bug report
15. https://github.com/openclaw/openclaw/issues/67532 — baseUrl/404-as-overloaded bug report
16. https://github.com/NousResearch/hermes-agent/issues/47685 — 429/system-prompt-trigger bug report
17. https://semgrep.dev/blog/2026/we-have-mythos-at-home-glm-52-beats-claude-in-our-cyber-benchmarks/ — IDOR security benchmark (primary source for judge-quality evidence)
18. https://www.techtimes.com/articles/319547/20260702/glm-53-must-include-vision-zais-developer-poll-returns-unanimous-answer.htm — Zhipu founder vision-poll story
19. https://www.verdent.ai/guides/glm-5v-turbo — GLM-5V-Turbo sibling-model details
20. https://www.mindstudio.ai/blog/what-is-glm-5-2-open-weight-model — GLM-5.2 vision/multimodal claims (contradicted by #1, resolved via #19)
21. https://zcode.z.ai/en — official ZCode harness site
22. https://flowtivity.ai/blog/zcode-glm-coding-agent-harness/ — ZCode feature/pricing analysis
23. https://venturebeat.com/technology/z-ai-launches-zcode-to-challenge-cursor-claude-code-and-github-copilot-in-ai-coding — ZCode launch coverage
24. https://huggingface.co/zai-org/GLM-5.2 — official weights repo (MIT license confirmation)
25. https://www.interconnects.ai/p/glm-52-is-the-step-change-for-open — independent analyst commentary on open-weight release
26. https://aiagentindex.mit.edu/2025/autoglm/ — AutoGLM product-line background
27. https://news.aibase.com/news/14961 — GLM-PC computer-use agent coverage

Additional searches that returned no usable primary evidence (recorded for audit trail, not cited as claims): dedicated z.ai 529-policy documentation page (none found — inferred from quota-multiplier mechanic instead); GLM-specific sycophancy/independence academic literature (none found, only provider-agnostic papers); confirmed GLM-5.2 LiveCodeBench score (not published by any source checked); batch-API confirmation for z.ai platform (neither confirmed nor denied).
