---
date: 2026-07-06
domain: operations
topic: Google Antigravity ecosystem (agy CLI, Antigravity IDE, Gemini 3.1 Pro, AI Ultra entitlements, Jules) — active inclusion assessment for Nuzantara
sources: 24
---

# Google Antigravity Ecosystem — Deep Research (July 2026)

## Executive Summary

The Antigravity ecosystem has consolidated hard since Google I/O 2026 (May 19): `gemini-cli` is dead (stopped serving Pro/Ultra/free requests June 18, 2026), replaced by **Antigravity CLI (`agy`)**, a Go-rewrite sharing one agent harness with the **Antigravity 2.0** desktop app, the **Antigravity IDE** (VS Code fork), and a new **Antigravity SDK** (Python/TypeScript/Go). All four surfaces read the same `~/.gemini/config/mcp_config.json` and the same `~/.gemini/skills/` directory — this is real infrastructure consolidation, not marketing.

The single most actionable finding for us: **our sshd/headless `agy` auth failures are a known, currently-open, upstream limitation — not a config error on our side.** `agy` has no API-key auth path; GitHub issue #78 (google-antigravity/antigravity-cli) has the Google maintainer on record June 29, 2026 saying "Gemini API Key is not supported currently" for the CLI, with no ETA. The recommended workaround for CI/headless is the **Antigravity SDK**, which talks to a local `LS` process over `127.0.0.1` via ConnectRPC with an ephemeral per-session token — but this still requires an already-authenticated Antigravity install *on that same machine*, so it does not solve pure remote/no-GUI execution any more cleanly than the CLI does. There is a documented pseudo-TTY (`script -qec`) workaround for the separate non-TTY-stdout-drop bug, which is a different, narrower bug than the auth problem.

Capability-wise, the IDE's **Agent Manager / Mission Control** (up to 5 parallel agents, each in its own git-worktree-isolated workspace, each producing **Artifacts** — Task List → Implementation Plan → Walkthrough with screenshots/recordings) is close to a productized version of our own 6-step Antigravity workflow contract — Google independently converged on "isolated worktree + plan artifact + verification walkthrough," which validates our existing design rather than requiring us to copy theirs. Gemini 3.1 Pro's genuine edge over Claude is **abstract reasoning (GPQA Diamond 94.3% vs Opus 4.6's 91.3%) and stable 1M-token ingestion**, not agentic tool-chaining, where Claude Sonnet/Opus still win (Gemini 3.1 Pro's own MCP Atlas multi-step benchmark sits at 69.2%, and it "struggles with multi-step agent pipelines involving 3+ sequential tool calls" per production reports) — this confirms our current split (Claude orchestrates, Gemini ingests/second-opinions) is the empirically correct one, not a workaround.

The AI Ultra entitlement audit surfaces real underuse: **NotebookLM Ultra tier gives 5,000 chats/day and 500-600 sources/notebook** (vs Pro's 500/300) plus Cinematic Video Overviews (Veo 3.1-based) that we've never touched; **Jules** (async coding agent, GitHub-native, 2M-token context, up to 60 concurrent tasks on Ultra) is fully included and currently 100% unused — it is a plausible async implementer lane analogous to Codex, with a materially different risk profile (runs in Google's cloud VM, not our worktree). One important negative-finding correction: a widely-repeated "AI Ultra Access ends July 7, 2026" story refers to a **Google Workspace admin-managed business add-on** with a similar name, NOT our consumer **Google AI Ultra** ($200/mo Google One personal subscription) — our 25,000 Flow-credits/month entitlement is unaffected by that deprecation.

---

## 1. Capability Map

### 1.1 `agy` CLI (Antigravity CLI)

- **Lineage**: successor to `gemini-cli`. Migration announced by Google Developers Blog; `gemini-cli` and Gemini Code Assist IDE extensions **stopped serving Pro/Ultra/free-tier requests on June 18, 2026**. [developers.googleblog.com](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)
- **Implementation**: rewritten in Go (vs the old Node.js `gemini-cli`), marketed for faster startup/execution. [datacamp.com](https://www.datacamp.com/tutorial/antigravity-cli), [agentpedia.codes](https://agentpedia.codes/blog/antigravity-cli-deep-dive)
- **Shared harness**: "Antigravity CLI shares the same agent harness as Antigravity 2.0" — meaning core-agent improvements land simultaneously across CLI/IDE/desktop-app without separate CLI releases. [developers.googleblog.com](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)
- **Default model**: Gemini 3.5 Flash by default (fast-loop use case); can be pointed at Gemini 3.1 Pro. [datacamp.com](https://www.datacamp.com/tutorial/antigravity-cli)
- **Feature parity preserved from gemini-cli**: Agent Skills, Hooks, Subagents, Extensions (renamed "Antigravity plugins"). [developers.googleblog.com](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)
- **New in agy vs gemini-cli**: parallel subagents, `/goal` and `/schedule` slash commands, asynchronous background-agent orchestration ("Antigravity CLI orchestrates multiple agents for complex tasks in the background"). [datacamp.com](https://www.datacamp.com/tutorial/antigravity-cli), [developers.googleblog.com](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/)
- **MCP support**: first-class, shared config file `~/.gemini/config/mcp_config.json` across CLI, IDE, and desktop app. Two connection types:
  - stdio: `{"command": "npx", "args": [...]}`
  - HTTP remote: `{"serverUrl": "...", "authProviderType": "google_credentials"}` (note: field is `serverUrl`, NOT the older `httpUrl`; per-server `timeout` key is deprecated in favor of `MCP_SERVER_REQUEST_TIMEOUT` env var; no inline JSON comments supported). [medium.com/@Dazbo](https://medium.com/google-cloud/configuring-mcp-servers-and-skills-for-antigravity-cli-and-ide-a938c7eebb78)
  - Google Workspace MCP servers (Docs/Sheets/Calendar) ship out-of-the-box. [search summary, corroborated across 2 independent sources]
- **Skills location**: `~/.gemini/skills/` — NOT `~/.gemini/antigravity/skills/` as some docs imply; this is a documented gotcha ("Antigravity tools do not pick up skills placed in [the documented] location"). [medium.com/@Dazbo](https://medium.com/google-cloud/configuring-mcp-servers-and-skills-for-antigravity-cli-and-ide-a938c7eebb78)
- **Recent changelog (v1.0.11–1.0.16, per GitHub CHANGELOG, dates not always stamped but confirmed within the June–July 2026 window by the source article's "as of 2026-07-02" framing)**:
  - v1.0.16: `/tasks` panel auto-scroll, client-side auto-retry on transient errors, subagent invocation moved JSON→Markdown format, crash fixes, goroutine/DB-connection leak fixes.
  - v1.0.15: live subagent/background-task status indicator, editor integration (`ctrl+g`), Windows clipboard paste (`alt+v`), **MCP connection timeout raised to 60s**, Windows non-TTY output fix.
  - v1.0.14: image paste in tmux, `/goal` execution-limit removed, "always proceed" auto-approval mode for subagents, MCP config path-mismatch fix.
  - v1.0.1 (May 22, 2026): fixed OAuth-not-persisting bug in some environments, added "proceed in sandbox" permission control.
  [github.com/google-antigravity/antigravity-cli/blob/main/CHANGELOG.md](https://github.com/google-antigravity/antigravity-cli/blob/main/CHANGELOG.md) — **[single-source: exact dates for v1.0.11-16 not independently corroborated beyond the changelog file and one secondary blog summary]**
- **`agy changelog` command**: added June 4, 2026, prints release notes in-terminal. [releasebot.io / gradually.ai, cross-corroborated]

**Authentication model (the load-bearing finding for us):**

- Primary auth is interactive OAuth via browser popup/URL. In headless/SSH contexts, `agy` "prints a URL to your terminal that you authenticate in any browser" — i.e., it still expects a human with a browser somewhere to complete the flow, then (in theory) persist the token back to the CLI host. [cloud.google.com surface-comparison blog](https://cloud.google.com/blog/topics/developers-practitioners/choosing-your-surface-antigravity-20-antigravity-cli-antigravity-ide-or-antigravity-sdk)
- **No API-key auth path exists for the CLI as of July 2026.** GitHub issue #78 explicitly requests `GEMINI_API_KEY`/`ANTIGRAVITY_API_KEY` env-var support with CLI-flag override; Google's own maintainer (**@rodydavis, comment dated Jun 29, 2026**) states: *"Gemini API Key is not supported currently"* and that the team is "reviewing feedback... but do not have any updates at this time." Issue is **open, unresolved, no linked PR**. [github.com/google-antigravity/antigravity-cli/issues/78](https://github.com/google-antigravity/antigravity-cli/issues/78)
- Documented failure modes matching our own experience:
  - **SSH-session URL corruption**: "OAuth authorization URL corrupted by terminal line-wrapping during remote SSH sessions" — filed as issue #315 against v1.0.6. [github.com/google-antigravity/antigravity-cli/issues/315]
  - **Token non-persistence in headless/WSL2 envs**: "agy CLI fails to persist authentication state" across terminal sessions in headless Linux, forcing re-auth every session. [discuss.ai.google.dev thread #146059] — **this is very likely our own Mini sshd symptom** (`GLM Mini armato + leak fable-5[1m]` memory notes "agy Mini ancora auth-failed sotto sshd (GUI-bound)").
  - **Non-TTY stdout drop** (a *separate* bug from auth): `agy -p "..."` run under pipes/cron/GitHub-Actions can silently drop the final response to stdout while returning exit code 0. Documented, community-sourced workaround: wrap in a pseudo-TTY (`script -qec 'agy -p "..."' /dev/null` on Linux, different arg order on macOS BSD `script`), strip ANSI codes (`sed -r 's/\x1B\[[0-9;]*[A-Za-z]//g' | tr -d '\r'`), verify a self-chosen output marker (e.g. `SUMMARY:` prefix) rather than trusting exit code alone, cap timeout ~180s with one retry. `--output-format json` is explicitly flagged as **currently non-functional / not a stable feature**. [antigravitylab.net headless-CI article](https://antigravitylab.net/en/articles/integrations/antigravity-cli-agy-headless-non-tty-stdout-ci) — **[single-source: this is one community blog, not an official doc; treat the exact workaround recipe as unverified-but-plausible until we test it]**
- **Officially recommended headless/CI path is the Antigravity SDK, not the CLI.** But the SDK's actual mechanics undercut the "headless" framing for our specific problem: the SDK "communicates with the LS process on 127.0.0.1 using the same ConnectRPC protocol Antigravity itself uses," authenticating via "an ephemeral per-session CSRF token (not the user's OAuth token)" — meaning **the SDK still requires a locally-running, already-OAuth'd Antigravity process on that same box**. It is a better *programmatic* interface once you're authenticated, not a way to skip authentication or avoid needing a GUI-capable session at least once. Google's own surface-comparison blog does not clarify whether the SDK can run against a headless/no-GUI daemon at all — this remains genuinely unresolved. [github.com/google-antigravity/antigravity-sdk-python](https://github.com/google-antigravity/antigravity-sdk-python) + [cloud.google.com surface-comparison](https://cloud.google.com/blog/topics/developers-practitioners/choosing-your-surface-antigravity-20-antigravity-cli-antigravity-ide-or-antigravity-sdk) — **[open question, flagged below]**

### 1.2 Antigravity IDE / Antigravity 2.0 (desktop app)

- Antigravity 2.0 is now a **standalone application, independent of any IDE** (the original Nov-2025 Antigravity was a VS Code fork; the "2.0" branding at I/O 2026 separated the orchestration shell from the code-editing surface — though a VS-Code-fork "Antigravity IDE" variant still exists for line-by-line diff review). [multiple sources, cross-corroborated: buildmvpfast.com, aicodingtools.im, beginnersinai.org]
- **Agent Manager / "Mission Control"**: dashboard to spawn/monitor/manage **up to 5 parallel agents**, each in an isolated workspace, each on a different task. Real example cited: one agent on Next.js frontend, one on API layer, one on Google SSO config, one browser-subagent verifying RBAC — "a project that typically required two sprints was prototyped in a single afternoon." [jangwook.net I/O recap](https://jangwook.net/en/blog/en/google-io-2026-antigravity-2-agent-platform-analysis/), [analyticsvidhya.com](https://www.analyticsvidhya.com/blog/2026/05/google-antigravity-2-0/)
- **Git-worktree-native**: "Antigravity treats parallel agent management as the primary workflow... opening each worktree directory as a separate workspace gives you isolated AI agents operating on independent branches" — each branch gets its own physical directory, own `node_modules`, own agent conversation history. There is even a published community "using-git-worktrees" Agent Skill (works across Claude Code / Cursor / Antigravity) that does pre-flight checks like verifying worktree dirs are gitignored. [antigravitylab.net worktree guide](https://antigravitylab.net/en/articles/editor/antigravity-git-worktree-parallel-workspace-guide), [playbooks.com skill](https://playbooks.com/skills/sickn33/antigravity-awesome-skills)
- **Artifacts system** (the transparency/trust layer): agents are required to produce tangible deliverables at each stage:
  1. **Task List** — structured plan, reviewable/editable before code is written.
  2. **Implementation Plan** — architecture of the intended change, technical detail on required revisions.
  3. **Walkthrough** — produced on completion: human-readable doc with verification results, step-by-step text, **and screenshots/screen-recordings**.
  [aibuilderclub.com](https://www.aibuilderclub.com/blog/antigravity-complete-guide), [dev.to/googleai launch post](https://dev.to/googleai/where-were-going-we-dont-need-chatbots-introducing-the-antigravity-ide-2c3k)
- **Browser Subagent**: powered by "Gemini 2.5 Computer Use," actuated via a custom Chrome extension. Can click/scroll/type/inspect-DOM/read-console-logs, take before/after screenshots, record video. Example task quoted: *"Go to this staging site, identify five core user journeys, and make a tutorial for all of them."* This is functionally close to our `mcp__claude-in-chrome__*` usage but packaged as an autonomous exploratory agent rather than a driven tool. [dev.to launch post](https://dev.to/googleai/where-were-going-we-dont-need-chatbots-introducing-the-antigravity-ide-2c3k)
- **Chrome DevTools MCP + BrowserMCP + Playwright integration** documented via a Google Codelab for automated UI testing specifically with agy CLI. [codelabs.developers.google.com/agentic-ui-automation-with-antigravity]

### 1.3 Gemini 3.1 Pro (model)

- **Released**: February 11, 2026 (Preview). [llm-stats.com](https://llm-stats.com/blog/research/gemini-3.1-pro-launch)
- **Context window**: 1M tokens, described as "stable and production-ready" (vs Claude Opus 4.6's 1M context, which multiple comparison sites describe as still in beta as of mid-2026). [contracollective.com](https://contracollective.com/blog/gemini-3-1-pro-2026), [verdent.ai](https://www.verdent.ai/guides/gemini-3-1-pro-vs-claude-opus-4-sonnet-4)
- **Reasoning**: ARC-AGI-2 verified score 77.1% (Google states "more than double" Gemini 3 Pro's prior score on the same test); GPQA Diamond 94.3% (vs Claude Opus 4.6's 91.3%). [multiple sources cross-corroborated: myclaw.ai, whatllm.org, acecloud.ai]
- **Multimodal**: MMMU-Pro 81.0% (vs GPT-5.1's 76.0% — a 5-point gap Google/independent benchmarkers both cite); Video-MMMU 87.6%, described as showing "advanced ability to comprehend and synthesize information from dynamic video content." [labellerr.com](https://www.labellerr.com/blog/google-gemini-3-1-pro-review-and-analysis/)
- **Long-context degradation is real and documented**: MRCR v2 (multi-round co-reference, a "needle in haystack"-style long-context quality test) scores 84.9% at 128K average but drops to **26.3% at the full 1M pointwise test** — meaning the "1M context" marketing figure is real for *ingestion* (it will read the tokens) but quality at the far end of that window is meaningfully worse than at 128K. This is directly relevant to our "long-context ingestion" use case (60-NB inventory, 64-past-carousel corpus) — full-window queries should be treated as lower-confidence than sub-200K queries. [deepmind.google/models/model-cards/gemini-3-1-pro] — **cross-corroborated across 3 independent benchmark aggregator sites, treated as reliable**
- **Code execution as a tool**: supported natively (sandboxed code execution alongside reasoning). [llm-stats.com]
- **Agentic/tool-chaining is the acknowledged weak point vs Claude**: "Gemini 3.1 Pro struggles with multi-step agent pipelines involving 3 or more sequential tool calls, with its MCP Atlas multi-step benchmark at 69.2%." Claude Sonnet 4.6 is independently described as "the best production agent model for most teams in 2026, maintaining task instruction across multi-step tool chains," leading GDPval-AA Elo at 1,633. Claude Opus 4.6 "narrowly takes the win on SWE-Bench Verified." [llmx.tech real-agent-pipeline-test](https://llmx.tech/blog/gemini-31-pro-vs-claude-sonnet-46-opus-46-real-agent-pipeline-test-2026/) — **cross-corroborated by verdent.ai independently**
- **Cost**: ~$2,000/mo at 1B input tokens vs ~$15,000/mo for Claude Opus 4.6 at the same volume (roughly 7.5x cheaper). [verdent.ai]
- **Grounding with Google Search**: Gemini's native grounding tool auto-decides whether a query benefits from search, issues one-or-more queries, synthesizes results into a cited answer. Google's own material claims "reducing hallucinations by 40% compared to ungrounded models" — **[single-source, Google's own marketing figure, not independently benchmarked in what I found; treat with skepticism]**. Functionally this is a *managed RAG* — "you skip vector databases, embedding models, chunking, reranking... tradeoff is zero customization." This is architecturally different from and complementary to (not a replacement for) our NotebookLM ground-truth RAG, which is exactly why CLAUDE.md correctly keeps NotebookLM as sole regulatory ground-truth and doesn't ask this question to move that role. [ai.google.dev/gemini-api/docs/google-search], [sparkco.ai grounding explainer]

### 1.4 Google AI Ultra entitlements (July 2026)

**Confirmed current bundle** (Google AI Ultra, $200/month consumer/Google-One tier — this is OUR subscription):
- Gemini 3.1 Pro with "Deep Think" reasoning mode, priority model access.
- Flow (video generation) with full Veo 3.1 including audio generation, 1080p cinematic tools.
- **25,000 Flow credits/month** at the $200 tier (a cheaper $100/mo "developer-focused" tier introduced at I/O 2026 gets 10,000 credits/mo; AI Pro gets 1,000/mo; AI Plus gets 200/mo). [support.google.com/flow/answer/16526234]
- NotebookLM at the **highest tier** ("Ultra"): 500-600 sources/notebook (vs Pro's 300), up to 500 notebooks/user, **5,000 chat queries/day** (vs Pro's 500/day — a 10x gap), 200 Audio Overviews/day, **200 Video Overviews/day**, 200 Deep Research sessions/day, 1,000 Reports/Flashcards/Quizzes/day. **Cinematic Video Overviews (built on Veo 3) are Ultra-exclusive** — not available at any lower tier. Per-source ceiling (500K words / 200MB) is identical across all tiers, so this isn't a hard-limit differentiator, just throughput. [xda-developers.com Ultra-tier launch], [elephas.app limits guide], [notebooklm-guide.com] — cross-corroborated across 3 independent sources.
- Jules (async coding agent) — see §1.5 below, fully included.
- Workspace with 30TB storage.
[blog.google AI-subscriptions I/O recap](https://blog.google/products-and-platforms/products/google-one/google-ai-subscriptions/), [eesel.ai Ultra explainer]

**Important correction to a widely-circulated but wrong story**: multiple search results surfaced a claim that "AI Ultra Access is being deprecated July 7, 2026." **This refers to a different product**: "AI Ultra Access" is a **Google Workspace admin-managed license add-on** for business/enterprise Workspace customers (sits alongside a newer "AI Expanded Access" tier), being sunset and folded into "AI Expanded Access" starting July 7, 2026, per Google Workspace's own admin help center. **This is unrelated to the consumer Google AI Ultra ($200/mo Google One personal subscription) that Bali Zero holds** — our 25,000 Flow-credits/month entitlement, NotebookLM Ultra tier, and Jules access are unaffected by this July 7 change. [knowledge.workspace.google.com/admin/generative-ai/workspace-with-gemini/ai-ultra-access], [digigen.io "AI Ultra Access Is Going Away"] — the naming collision between "Google AI Ultra" (consumer) and "AI Ultra Access" (Workspace admin license) is genuinely confusing in Google's own materials; I flag this explicitly so it doesn't get miscopied into a future memory file as "our Flow credits end this week," which would be false.

### 1.5 Jules (async coding agent)

- Built on Gemini 3.1 Pro (default model for paid plans, priority access for Ultra subscribers since March 9, 2026). [jules.google]
- **Context window**: 2M tokens as of I/O 2026 (larger than Gemini 3.1 Pro's own 1M — Jules apparently uses an extended-context variant or chunked-retrieval layer for full-repo analysis). [digitalapplied.com]
- **Concurrency**: 15 concurrent tasks on the standard plan; **60 concurrent tasks + "highest task limits" + priority model access on Ultra** (one source states "300 tasks/day" for Ultra). [agent-finder.co], [morphllm.com comparison]
- **Workflow**: task submitted via Jules web UI, a GitHub issue @mention, or the Jules API → scheduler provisions a fresh cloud VM → checks out the repo into that VM → hands the brief to a Gemini planner instance → Jules shows its plan (editable before/during/after execution) → on completion, opens a PR against the branch → **if CI fails on the Jules-authored PR, Jules automatically receives the error, analyzes it, applies a fix, and re-pushes the commit, often without human intervention**. [blog.google Jules launch], [jules.google/docs]
- **Distribution**: `jules-action` (GitHub Actions integration), `jules-sdk`, and a "Jules extension for Gemini CLI" (predating the agy rename, likely being folded in) all exist as separate repos under `google-labs-code`. [github.com/google-labs-code/jules-action], [cloud.google.com Jules-multi-tasking blog]
- **Risk-relevant architectural note for us**: Jules runs in **Google's own cloud VM**, not in our worktree, not on our fleet. This is a materially different trust boundary than our Antigravity-IDE contract (which is worktree-isolated on our own Mac) or Codex (`--sandbox workspace-write` on our own filesystem). Any repo Jules touches leaves our infrastructure boundary for the duration of the task — this needs explicit non-PII scoping exactly like our other cloud-LLM rules, and probably a narrower one than Codex gets (Codex reads/writes our local filesystem; Jules's cloud VM holds a full repo checkout persistently for the task's duration).

---

## 2. What Changed Recently (last ~90 days, Apr–Jul 2026)

1. **`gemini-cli` → `agy` full cutover**: announced pre-May 19, general availability May 19, 2026; `gemini-cli` + Gemini Code Assist IDE extensions stopped serving Pro/Ultra/free requests **June 18, 2026**. If any of our scripts/wrappers still invoke the legacy `gemini` binary at `/opt/homebrew/bin/gemini` (flagged as DEPRECATED in our own CLAUDE.md already, dated pre-migration), those calls are now **hard-dead**, not just discouraged — worth a repo-wide grep to confirm nothing silently fails-closed on a dead binary. [developers.googleblog.com]
2. **Antigravity 2.0 + Antigravity CLI + Antigravity SDK all launched/GA'd at I/O 2026** (May 19), consolidating four previously-separate surfaces (old VS-Code-fork Antigravity, gemini-cli, Gemini Code Assist, ad-hoc Google Cloud agent tooling) into one shared harness. [jangwook.net I/O recap]
3. **Gemini 3.1 Pro released Feb 11, 2026**, then became the **default model for AI Ultra/Pro paid plans March 9, 2026** — meaning our existing `agy` usage has almost certainly already been running against 3.1 Pro (or 3.5 Flash by CLI default) without us pinning a version, which is worth verifying explicitly in our wrapper scripts since "3.1 Pro" behavior differs meaningfully from whatever model our memory files assumed when routing rules were written.
4. **Flow credit tier restructure at I/O 2026**: single $250/mo Ultra tier split into $100/mo (10K credits) and $200/mo (25K credits, our tier) — a price *cut* on our existing tier ($249.99→$200) plus a new cheaper entry point, not a cut to our credits.
5. **NotebookLM Ultra tier launched** (exact date not pinned in sources, but framed as a 2026 rollout distinct from the long-standing free/Plus/Pro tiers) — this is the first time NotebookLM has had a tier above "Pro," and it appears our AI Ultra subscription auto-entitles us to it without a separate action, worth confirming against our actual NotebookLM account settings.
6. **Jules exited beta** (2025) then got "major updates at I/O 2026" including the 2M-token context bump and the CI-auto-fix loop — the auto-fix-on-CI-failure behavior specifically is new-ish and the single most interesting differentiator vs a plain PR-bot.
7. **`agy` v1.0.1–v1.0.16 shipped** across May–July: notable fixes include OAuth-persistence bug fix (v1.0.1, May 22), MCP timeout raised 60s (v1.0.15), subagent auto-approval "always proceeds" mode (v1.0.14) — the pace of point releases (16 in ~7 weeks) signals this is still an actively-hardening, pre-1.0-stability product despite the version number, consistent with the still-open headless-auth gap.

---

## 3. Where Antigravity/Gemini Beats Claude — and Where It Loses

**Genuinely beats Claude for us:**
- **Long-document/corpus ingestion at scale with cost sensitivity**: 1M stable context + ~7.5x cheaper input tokens than Opus makes Gemini the correct tool for "read everything, summarize/correlate" tasks — exactly what `wr2-ig-metrics-analyst` and `wr2-external-bench` already do. Confirms current design, doesn't suggest expansion.
- **Video/multimodal understanding**: Video-MMMU 87.6% is a real capability gap vs Claude (which has no comparable native video-ingestion benchmark story) — relevant to any future WR3 video-QA or Veo-output review task.
- **Abstract/scientific reasoning**: GPQA Diamond edge (94.3 vs 91.3) is real but narrow (3 points) and likely doesn't move the needle for our domain (Indonesian tax/visa/company law is not GPQA-shaped reasoning).
- **Raw cost** for high-volume, low-stakes classification/summarization work where Claude MAX quota is the constraint, not judgment quality.

**Loses to Claude — do not move these:**
- **Multi-step agentic tool-chaining** (69.2% on 3+ sequential tool calls) — this is core to almost everything Claude Code / our subagent fleet does. Do not consider Gemini/agy as an orchestrator replacement.
- **SWE-Bench-style real-world software engineering** — Claude Opus/Sonnet still ahead.
- **Anything requiring the headless/unattended execution our cron fleet depends on** — `agy`'s auth model is fundamentally interactive-OAuth-first with no API-key escape hatch, which is disqualifying for most of our cron-fleet use cases beyond narrow, already-authenticated-session invocations.
- **Ground truth on Indonesian regulation** — settled already, NotebookLM stays sole authority; Gemini's Google-Search grounding is public-web RAG, structurally the wrong tool for jurisdiction-specific curated-source ground truth.

---

## 4. ACTIVE INCLUSION PROPOSALS for Nuzantara

Ranked by expected-gain/risk/cost ratio, most to least compelling.

### P1 — Fix the sshd/headless `agy` auth gap by moving the auth boundary, not chasing an API key

**What**: Stop waiting for GitHub issue #78 (API-key support) — it has no ETA and the maintainer has explicitly deprioritized it. Instead, authenticate `agy` **once, interactively, on Mini's actual console/GUI session** (not over sshd), let the OAuth token persist to `~/.gemini/`, and have cron/sshd-invoked calls **reuse that already-materialized token file** rather than attempting a fresh OAuth handshake under sshd. This mirrors exactly the W84 cure pattern we already applied to launchd/TCC (trampoline through a session that has the grant, rather than trying to grant it to the constrained session).
**Invocation path**: on Mini, run `agy auth login` from an actual Terminal.app/iTerm session (not `ssh mini '...'`), confirm token file lands in `~/.gemini/`, verify sshd-invoked `agy -p "ping"` afterward reuses it without re-prompting.
**Slots into**: cron cascade Tier 2 (`regulatory-watcher-run.sh` and siblings), which currently silently falls through past a broken Tier 2 to Tier 3/4.
**Expected gain**: restores the documented 4-tier cascade to actually 4-deep instead of the "2-deep in practice" state flagged in our own CLAUDE.md (`Audit 2026-05-24 trovò Tier 3 + Tier 4 entrambi disarmed silently`).
**Risk/cost**: near-zero — one interactive login, no new infra, no cost. **Verify empirically before declaring fixed** — this is a #2-family (Esiste≠Armato) risk if we assume it works without testing an actual sshd-invoked call afterward.

### P2 — Adopt the `script -qec` pseudo-TTY wrapper for all existing `agy -p` cron invocations

**What**: our cascade wrapper (`~/scripts/regulatory-watcher-run.sh` and any other Tier-2 `agy -p` call) should be audited for the documented non-TTY stdout-drop bug — a silent exit-0-with-empty-output failure mode that would currently be indistinguishable from "Gemini had nothing to say" in our logs.
**Invocation path**: wrap existing `agy -p "$PROMPT"` calls as `script -qec "agy -p \"$PROMPT\"" /dev/null | sed -r 's/\x1B\[[0-9;]*[A-Za-z]//g' | tr -d '\r'`, add an empty-output check that treats blank stdout as a cascade-fallthrough trigger (it should already do this per our `grep stdout for out of extra usage|...` pattern — extend that grep pattern to also fire on **empty** stdout, not just matching error strings).
**Slots into**: `~/.claude/CLAUDE.md §Cascade detection` — the existing grep-based fallthrough logic.
**Expected gain**: closes a specific, named, currently-undetected failure mode in a system we already depend on for quota-exhaust fallback.
**Risk/cost**: low — pure defensive wrapper, no behavior change on the happy path. **Caveat**: this workaround recipe is single-source (one community blog); test it empirically on Mini/Pro before trusting it in a cron path, per our own anti-hallucination discipline.

### P3 — Pilot Jules as a bounded async implementer lane for non-PII, low-stakes repo maintenance (dependency bumps, lint fixes, doc-sync)

**What**: Jules is fully included in our existing AI Ultra subscription and currently 100% unused. Its GitHub-native PR workflow with auto-fix-on-CI-failure is a genuine capability gap vs our current Codex lane (Codex needs a human/Claude-driven loop to re-run after a CI failure; Jules does this autonomously).
**Invocation path**: install the Jules GitHub App scoped to a **single low-stakes repo or even a single directory** (NOT the full Nuzantara monorepo on day one, given secrets/PII exposure risk of a persistent cloud-VM checkout) — good first candidate: the `agent-library` or a research-only repo with no client data. Submit tasks via GitHub issue @mention (`@jules fix the dependabot warning in X`).
**Slots into**: a new lane parallel to Codex, explicitly scoped narrower — candidate first tasks: Python patch-safe dependency bumps (`audit_weekly_dependencies` already tracks 15 patch-safe items), CHANGELOG/docs-sync mechanical updates.
**Expected gain**: offloads pure-mechanical PR-and-fix-CI work without spending Claude MAX quota or Codex ChatGPT-Pro quota; validates whether the auto-CI-fix loop is trustworthy before considering wider scope.
**Risk/cost**: **medium** — this is the one proposal that changes our trust boundary (cloud VM holds a full repo checkout, not our filesystem/worktree). Requires: (a) explicit repo scoping away from any PII/secrets-bearing path, (b) Antonello's authorization before first use per our "new tool/workflow touching repo" norm, (c) a human merge gate identical to what we already require for Codex/Antigravity (never auto-merge from an external agent). This is NOT pre-authorized by existing CLAUDE.md rules (it's a new cloud surface, not a "paid per-token API" in the strict sense, but the PII-boundary logic applies identically) — **surface to Antonello before first real use.**

### P4 — Wake the sleeping Antigravity IDE 6-step workflow using its native Agent Manager instead of manual worktree-spawn, for the specific case of 2-3 independent parallel front-end/UI fixes

**What**: our existing "Antigravity = autonomous arm, Claude Code verifies" contract has been dormant since June. Google's Agent Manager (up to 5 parallel agents, each auto-isolated in its own worktree, each producing a Walkthrough artifact with screenshots) is now mature enough that it substantially reduces the manual "Zero creates worktree fresh, launches Antigravity" step in our 6-step workflow — the tool now does worktree creation itself.
**Invocation path**: next time there are 2+ independent, scoped, non-architectural UI/frontend fixes queued (e.g., a batch of WR2 app or KBLI Navigator polish items), dispatch them as parallel Agent-Manager tasks instead of one at a time, keeping our step-4 (Claude Code independent re-verification, re-run tests, scope/reward-hacking check) unchanged and non-negotiable.
**Slots into**: existing `decision_how_we_use_antigravity_ide_2026_06_23` contract — this is a refinement of an existing approved pattern, not a new one.
**Expected gain**: reclaims value from a subscription entitlement we're already paying for and already approved using, currently idle since June; potential throughput gain on the kind of small-scoped parallel UI work we've been doing serially (KBLI app, WR2 Control app polish items).
**Risk/cost**: low — this is literally re-activating dormant, already-approved capability with an unchanged verification gate. The only new risk is Agent-Manager's auto-worktree-creation needs to be checked against our own `scripts/agent_start.py` lease/broker discipline (family #5, Sibling-race) — confirm Antigravity's own worktrees don't collide with our broker's TTL/reap logic if both systems create worktrees under `.worktrees/`.

### P5 — Use NotebookLM Ultra's higher chat-query ceiling (5,000/day vs Pro's 500/day) to remove an artificial throttle on `nb-curator` and the NB-INTEL delta pipeline

**What**: we are apparently on the NotebookLM Ultra tier already (bundled with AI Ultra) but multiple cron agents (`regulatory-watcher`, `nb-curator`, `nb-intel-delta-watcher`) may have been designed under Pro-tier assumptions (500 chats/day) given how often our own memory notes mention NLM auth/quota friction. Confirming we're actually drawing on the 5,000/day Ultra ceiling (not silently capped at a lower default) could resolve some of the recurring "nlm auth expired again" friction if any of that friction is actually quota-adjacent rather than pure auth-token expiry.
**Invocation path**: check NotebookLM account settings under `antonellosiano@gmail.com` (our single NLM account per memory) to confirm Ultra-tier badge is showing; audit `nb-curator`'s health-check cron for any hardcoded Pro-tier assumptions (300 sources/notebook cap, 500 chats/day cap) that should be raised to Ultra's 500-600/5,000.
**Slots into**: `nb-curator` weekly health-check.
**Expected gain**: low-effort verification that could remove a false ceiling; also unlocks Cinematic Video Overviews (Veo-3-based) as a possible input to WR3 video pipeline research (untested territory, not proposing adoption yet — just flagging the entitlement exists and is unused).
**Risk/cost**: near-zero, pure audit task.

**Not proposing** (considered and rejected): moving any part of the Antigravity IDE / agy orchestration role to replace Claude as our master loop driver — the benchmark evidence (69.2% on 3+-tool-call chains) directly contradicts that this would be a net gain, and it would also violate our own settled model-routing philosophy (Fable/Claude = architect/final-gate). Also not proposing NotebookLM-role migration to Gemini's Google-Search grounding — different tool, different job, current split is correct.

---

## 5. What We're Wasting (Unused Entitlements, Audited)

| Entitlement | Included in our $200/mo AI Ultra | Current usage | Gap |
|---|---|---|---|
| Jules async coding agent | Yes, up to 60 concurrent tasks | **Zero** | Full — see P3 |
| NotebookLM Ultra 5,000 chats/day | Yes | Unknown — may be silently capped by agent code assuming Pro limits | Partial — see P5 |
| NotebookLM Cinematic Video Overviews (Veo 3) | Yes, Ultra-exclusive | **Zero** | Full — no proposed use yet, flagged only |
| Antigravity IDE Agent Manager (5 parallel agents) | Yes | Dormant since June (per our own memory) | Partial — see P4 |
| Antigravity SDK (programmatic surface) | Yes | **Zero** | Investigated as a potential headless-auth fix (P1), found to not actually solve headless auth cleanly — deprioritized until Google clarifies whether SDK can run against a truly no-GUI daemon |
| Flow 25,000 credits/month | Yes | "Under-consumed" per task brief — FlowKit bridge exists for Nano Banana Pro/Veo but volume not audited in this research pass | Needs a separate usage-volume check against actual monthly credit burn, out of scope for this report |
| Gemini 3.5 Flash (agy CLI default model) | Yes | Used implicitly whenever `agy` is called without explicit model flag | Verify our wrapper scripts explicitly pin 3.1 Pro where long-context/quality matters — CLI default may silently be routing to the cheaper/faster 3.5 Flash for tasks that assumed 3.1 Pro |

---

## 6. Open Questions / Unresolved / [single-source] Flags

1. **[Open, high-value]** Can the Antigravity SDK run against a headless (no-GUI-ever) Antigravity daemon, or does the local `LS` process it talks to over `127.0.0.1` fundamentally require the desktop app/IDE to have been launched at least once with a display? Google's own surface-comparison blog does not say. This determines whether P1's workaround (auth once on console, reuse token under sshd) is even necessary, or whether the SDK route could be made to work with a service-account-style flow if Google ships one. Worth a direct, minimal empirical test on Mini: install Antigravity SDK, attempt to drive it purely over SSH with no local display ever opened, observe the actual failure mode.
2. **[single-source]** The exact `script -qec` pseudo-TTY workaround recipe for the non-TTY stdout-drop bug comes from one community blog (antigravitylab.net), not an official Google doc or a second independent report. Treat the recipe as a starting point to test, not a verified fix, before wiring it into any cron path.
3. **[single-source]** Google's "40% hallucination reduction" claim for Google-Search grounding is Google's own marketing figure; I found no independent benchmark corroborating that specific number. Doesn't affect our recommendations (we don't propose using grounding for anything ground-truth-critical) but shouldn't be repeated as an established fact elsewhere.
4. **[Open]** Exact dates for `agy` v1.0.11 through v1.0.16 point releases were not independently corroborated beyond the GitHub CHANGELOG.md file itself plus one secondary blog's "as of 2026-07-02" framing — the sequence and content of the changes is credible (matches the CHANGELOG verbatim) but a precise release-date table would need a direct GitHub Releases page fetch, which returned a generic listing page without per-version dates in this pass.
5. **[Open]** Whether our existing `agy` wrapper scripts across the fleet explicitly pin `gemini-3.1-pro` or are relying on the CLI's default (`gemini-3.5-flash`) was not verified in this research pass (out of scope — this report is about the ecosystem, not our own code; recommend a follow-up grep of `~/scripts/*.sh` and repo wrapper scripts for `agy -p` invocations and their model flags, since CLAUDE.md's model-routing table references "Gemini 3.1 Pro (1M context, high reasoning)" as the assumed model for Tier-2 fallback, which may not match what's actually being invoked).
6. **[Open, low-priority]** Whether Jules's "auto-fix-on-CI-failure" loop has any documented safety rail against infinite-retry-loops or runaway-cost scenarios was not found in the sources reviewed — worth checking Jules's own docs (`jules.google/docs`) directly before any pilot use (P3), since this is exactly the kind of "green-but-looping" failure mode our own cicatrix family #2 (Esiste≠Armato) would predict for an under-scrutinized auto-retry agent.

---

## Sources

1. [An important update: Transitioning Gemini CLI to Antigravity CLI](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/) — Google Developers Blog
2. [Orchestrating Google Workspace with Antigravity CLI](https://medium.com/google-cloud/orchestrating-google-workspace-with-antigravity-cli-a-high-performance-agentic-framework-499cae446161) — Medium/Google Cloud Community
3. [Automated UI Testing with Antigravity (AGY) CLI, BrowserMCP, Playwright](https://codelabs.developers.google.com/agentic-ui-automation-with-antigravity) — Google Codelabs
4. [I/O '26 news for agent developers on Google Cloud](https://cloud.google.com/blog/topics/developers-practitioners/io26-news-for-agent-developers-on-google-cloud) — Google Cloud Blog
5. [Google I/O 2026 Antigravity 2.0 — Gemini CLI Shutdown and Agent IDE War](https://jangwook.net/en/blog/en/google-io-2026-antigravity-2-agent-platform-analysis/)
6. [Configuring MCP Servers and Skills for Antigravity CLI and IDE](https://medium.com/google-cloud/configuring-mcp-servers-and-skills-for-antigravity-cli-and-ide-a938c7eebb78) — Medium/Google Cloud Community
7. [Google Antigravity CLI: Orchestrating Parallel AI Agents](https://www.datacamp.com/tutorial/antigravity-cli) — DataCamp
8. [Antigravity CLI Deep Dive: Google's Go-Based Terminal Agent](https://agentpedia.codes/blog/antigravity-cli-deep-dive)
9. [Google Antigravity Documentation — Agent Manager](https://antigravity.google/docs/agent-manager)
10. [Google Antigravity 2.0: The Full Developer Guide](https://www.analyticsvidhya.com/blog/2026/05/google-antigravity-2-0/) — Analytics Vidhya
11. [Feature Request: Support Gemini API Key Authentication for Headless Environments — Issue #78](https://github.com/google-antigravity/antigravity-cli/issues/78) — GitHub, google-antigravity/antigravity-cli
12. [OAuth authorization URL corrupted during remote SSH sessions — Issue #315](https://github.com/google-antigravity/antigravity-cli/issues/315) — GitHub
13. [Bug: Antigravity CLI fails to persist authentication state in WSL2](https://discuss.ai.google.dev/t/bug-antigravity-cli-agy-fails-to-persist-authentication-state-in-wsl-2-environment/146059) — Google AI Developers Forum
14. [Running the Antigravity CLI (agy) Headless in CI](https://antigravitylab.net/en/articles/integrations/antigravity-cli-agy-headless-non-tty-stdout-ci) — Antigravity Lab
15. [Claude Code vs. Antigravity: Which AI Tool Is Better?](https://www.datacamp.com/blog/claude-code-vs-antigravity) — DataCamp
16. [Gemini 3.1 Pro vs Claude Sonnet 4.6 & Opus 4.6: Real Agent Pipeline Test](https://llmx.tech/blog/gemini-31-pro-vs-claude-sonnet-46-opus-46-real-agent-pipeline-test-2026/)
17. [Gemini 3.1 Pro — Model Card](https://deepmind.google/models/model-cards/gemini-3-1-pro/) — Google DeepMind
18. [Gemini 3.1 Pro vs Claude Opus 4.8: Long Context vs Reasoning](https://contracollective.com/blog/gemini-3-1-pro-2026)
19. [Manage your Google Flow credits](https://support.google.com/flow/answer/16526234?hl=en) — Google Flow Help
20. [Google Antigravity - Antigravity SDK](https://antigravity.google/product/antigravity-sdk)
21. [Choosing your surface: Antigravity 2.0, CLI, IDE, or SDK](https://cloud.google.com/blog/topics/developers-practitioners/choosing-your-surface-antigravity-20-antigravity-cli-antigravity-ide-or-antigravity-sdk) — Google Cloud Blog
22. [Jules - An Autonomous Coding Agent](https://jules.google/)
23. [Master multi-tasking with the Jules extension for Gemini CLI](https://cloud.google.com/blog/topics/developers-practitioners/master-multi-tasking-with-the-jules-extension-for-gemini-cli/) — Google Cloud Blog
24. [NotebookLM's new Ultra tier](https://www.xda-developers.com/notebooklm-launches-new-ultra-tier-with-higher-limits/) — XDA Developers
25. [AI Ultra Access | Google Workspace Help](https://knowledge.workspace.google.com/admin/generative-ai/workspace-with-gemini/ai-ultra-access) — Google Workspace Help (source for the AI-Ultra-Access-vs-consumer-AI-Ultra naming-collision correction)
26. [Parallel Development with Antigravity and git worktree](https://antigravitylab.net/en/articles/editor/antigravity-git-worktree-parallel-workspace-guide) — Antigravity Lab
27. [Where we're going, we don't need chatbots: introducing the Antigravity IDE](https://dev.to/googleai/where-were-going-we-dont-need-chatbots-introducing-the-antigravity-ide-2c3k) — Google AI DEV Community
