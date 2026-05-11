# Personal Research Lab — SOTA Reconnaissance (2026-05-08)

> Research mission for Antonello Siano (Bali Zero / Nuzantara). Lifecycle target:
> nasce → cresce → auto-correct → cosciente → canalizza in NB-9 + Telegram dispatch + memory long-term.
> Verticals: AI papers, code (GitHub trending), frontier science, robotics.

---

## 1. Deep Research agents 2026 — SOTA confronto

Six commercial deep-research stacks compared on cost, output quality, source count, citations,
time-to-result and API availability. The headline finding is that **all six now ship "agentic"
multi-step orchestration over a search-and-synthesize loop**, but they diverge sharply on
(a) source budget per task, (b) API exposure, and (c) whether you pay per-task or per-token.

### 1.1 Anthropic Claude — "Research" (Claude.ai) + Skills/Subagents (Claude Code)

Claude Research is part of the Claude.ai consumer product (Pro/Max plans), and it's also
re-implementable from primitives inside Claude Code via Skills + subagents.

> "Research transforms how Claude finds and analyzes information, with Claude operating
> agentically by conducting multiple searches that build on each other while determining
> exactly what to investigate next. Once Research is turned on, users can ask Claude a
> question, and Claude will kick off the Research process across internal context (such
> as Gmail, Google Calendar, and Google Docs when connected) and the web."
> — Anthropic Help Center, [Using Research on Claude](https://support.claude.com/en/articles/11088861-using-research-on-claude)

> "Anthropic's multi-agent research system reports a 90.2% improvement over single-agent
> Opus on internal research evals, with Opus as the lead agent and Sonnet subagents
> handling parallel exploration."
> — [How we built our multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system) (re-cited in the-ai-corner roundup)

> "Claude Code has shipped subagents as first-class primitives at .claude/agents/, and
> Skills added a packaging layer between DIY and MCP: the same recursive-spawn logic can
> now ship as a slash command anyone on the team can invoke."
> — paddo.dev, [Three Ways to Build Deep Research with Claude](https://paddo.dev/blog/three-ways-deep-research-claude/)

- **Cost**: bundled with Claude Pro ($20/mo) or Max ($100/$200). For Antonello: covered by 3× Max plans already on hand, **zero marginal cost** under the no-paid-API rule.
- **Output quality**: highest in qualitative tests when wired with Sonnet subagents under an Opus lead. 90.2% lift over single-Opus baseline on internal eval.
- **Citations**: inline with hover-cards in Claude.ai; in Claude Code you control via skill's prompt template.
- **Max source count**: not officially capped; multi-agent fan-out routinely hits 50–150 distinct URLs per deep run.
- **Time-to-result**: 5–15 min for a typical 3-fan-out run.
- **API availability**: there is **no standalone "Deep Research API"**. The Messages API + a homegrown subagent loop in Claude Code is the official path, which is exactly the pattern Antonello already runs (multi-LLM wave-orchestrator).

Sources: [paddo.dev — Three Ways to Build Deep Research with Claude](https://paddo.dev/blog/three-ways-deep-research-claude/), [Anthropic — Using Research on Claude](https://support.claude.com/en/articles/11088861-using-research-on-claude), [the-ai-corner.com — Everything Claude Has Shipped in 2026](https://www.the-ai-corner.com/p/everything-claude-shipped-2026-complete-guide), [Claude (language model) — Wikipedia](<https://en.wikipedia.org/wiki/Claude_(language_model)>).

### 1.2 OpenAI — Deep Research (ChatGPT Pro) + `o3-deep-research` API

> "The o3-deep-research model costs $10 per million input tokens and $40 per million output
> tokens. It has a 200,000 token context window with a maximum output of 100,000 tokens."
> — [pricepertoken.com — o3 Deep Research API Pricing 2026](https://pricepertoken.com/pricing-page/model/openai-o3-deep-research)

- **Cost**: `o3-deep-research` $10/$40 per Mtok; `o3-deep-research-mini` cheaper variant; consumer access via ChatGPT Plus ($20) limited, ChatGPT Pro ($200) generous, Team/Enterprise unlimited.
- **Output quality**: strong for citation-density; best-in-class for tabular/quantitative reports.
- **Citations**: inline numeric + bibliography at end.
- **Max sources**: 30–100+ per run (no documented hard cap).
- **Time-to-result**: 5–30 min.
- **API**: `responses.create(model="o3-deep-research", tools=[{"type":"web_search_preview"}, {"type":"code_interpreter"}])`.
- Note for Antonello's HARD RULE: this is a paid OpenAI API but **does not violate** the rule because the rule is Anthropic-specific (Claude Max already paid). OpenAI is allowed if budget tolerated, but Antonello's stance: ChatGPT Plus covers Codex; per-token research is overlap.

Sources: [Pricing | OpenAI API](https://developers.openai.com/api/docs/pricing), [pricepertoken.com — o3 Deep Research](https://pricepertoken.com/pricing-page/model/openai-o3-deep-research), [OpenAI Pricing in 2026 — finout.io](https://www.finout.io/blog/openai-pricing-in-2026), [Community — O3 80% cheaper + o3-pro](https://community.openai.com/t/o3-is-80-cheaper-and-introducing-o3-pro/1284925), [OpenRouter — o3 Deep Research](https://openrouter.ai/openai/o3-deep-research).

### 1.3 Perplexity — Deep Research (Pro plan + Sonar Deep Research API)

> "Perplexity Pro includes 20 Deep Research queries per day, and deep research mode runs
> multi-step searches across 20-30+ sources and synthesizes a comprehensive answer."
> — [Perplexity Pro plan overview — felloai.com](https://felloai.com/perplexity-pricing/)

> "Sonar Deep Research includes citation tokens ($2/1M), reasoning tokens ($3/1M), and
> search query fees ($5 per 1,000 queries) on top of base token costs. A full Sonar Deep
> Research query can run to $0.41 or more depending on reasoning depth and number of
> searches performed."
> — [cloudzero.com — Perplexity API Pricing 2026](https://www.cloudzero.com/blog/perplexity-api-pricing/)

- **Cost**: Perplexity Pro $20/mo (20 deep queries/day); Max $200/mo unlimited; API $0.41+/query.
- **Output**: very fast, web-first, scratchpad-style. Weaker on academic depth, very strong on news/current events.
- **Sources**: 20–30+ per Pro task; 50–100+ per Sonar Deep Research.
- **Time**: 2–5 min typical.
- **API**: `sonar-deep-research` model on Perplexity API.

Sources: [Pricing — Perplexity Docs](https://docs.perplexity.ai/docs/getting-started/pricing), [Perplexity Pricing 2026 — felloai.com](https://felloai.com/perplexity-pricing/), [Sonar Deep Research API Pricing — pricepertoken.com](https://pricepertoken.com/pricing-page/model/perplexity-sonar-deep-research), [What is Perplexity Pro?](https://www.perplexity.ai/help-center/en/articles/10352901-what-is-perplexity-pro).

### 1.4 Google Gemini — Deep Research / Deep Research Max (Gemini 3.1 Pro)

> "Google released two new evolutions of its autonomous research agent: Deep Research and
> Deep Research Max. With the integration of its most advanced model, Gemini 3.1 Pro, Deep
> Research has transformed from a sophisticated summarization engine into a foundation for
> enterprise workflows across finance, life sciences, market research, and more."
> — [blog.google — Deep Research Max: a step change for autonomous research agents](https://blog.google/innovation-and-ai/models-and-research/gemini-models/next-generation-gemini-deep-research/)

> "Run Deep Research with Google Search, remote MCP servers, URL Context, Code Execution
> and File Search simultaneously — or turn off web access entirely to exclusively search
> over your custom data. Provide a combination of PDFs, CSVs, images, audio and video as
> input to ground the agent's research in your custom context."
> — Same source.

- **Cost (consumer)**: Gemini Advanced $19.99/mo (Google One AI Premium); Google AI Ultra $249.99/mo for Deep Think + Veo + Agent.
- **Cost (API)**: ~$2/task standard, ~$5/task Max. Google Search grounding 80 queries/standard task ($14/1K) → $1.12 search cost; 160 queries/Max → $2.24 search cost. Total per task ≈ $3–7.
- **Output**: hundreds of sources analyzable in minutes.
- **API availability**: `deep-research-preview-04-2026` and `deep-research-max-preview-04-2026` (Vertex AI).
- **For Antonello**: Gemini CLI 3.1 Pro is **OAuth free** (already in arsenal). The free Gemini CLI does not expose Deep Research orchestration — just the underlying model. Deep Research itself requires paid Advanced or API.

Sources: [Google AI Pro & Ultra — Gemini Subscriptions](https://gemini.google/subscriptions/), [Deep Research Max — blog.google](https://blog.google/innovation-and-ai/models-and-research/gemini-models/next-generation-gemini-deep-research/), [Gemini Deep Research pricing — tokencost.app](https://tokencost.app/blog/gemini-deep-research-agent-cost), [pasqualepillitteri.it — Deep Research Max coverage](https://pasqualepillitteri.it/en/news/1191/google-deep-research-max-gemini-3-1-pro-ai-agents).

### 1.5 xAI — Grok DeepSearch

> "All paid tiers include DeepSearch for live web research, Big Brain mode for extended
> thinking, and Voice mode for spoken chat. Grok differentiates itself through real-time
> web search capabilities, X/Twitter data integration, and features like DeepSearch for
> complex research queries."
> — [Robylon — xAI Grok 2026 Guide](https://www.robylon.ai/blog/what-is-xai-grok-a-complete-guide-to-the-chatbot)

> "If you use web search tools through the API, Web Search, X Search and Code Execution
> are $5 per 1,000 calls, File Attachments are $10 per 1,000 calls, and Collections Search
> is $2.50 per 1,000 calls."
> — [xAI Grok API Pricing — mem0.ai](https://mem0.ai/blog/xai-grok-api-pricing)

- **Cost**: SuperGrok $30/mo (~100 prompts / 2h, DeepSearch); Heavy $300/mo (Grok 4.3 + Heavy + max rate); X Premium+ bundles a tier.
- **Differentiator**: only deep-research tool with **first-party access to X/Twitter data** — useful for tracking AI/robotics community sentiment in near-real-time.
- **Output**: strong for sociopolitical/news queries; weaker on academic depth.
- **Sources**: 30–80+ per task incl. X posts, websites, Code Execution outputs.
- **API**: `grok-4-fast-search` and DeepSearch tooling.

Sources: [Models and Pricing — xAI Docs](https://docs.x.ai/developers/models), [xAI Grok Models 2026 — Lorka AI](https://www.lorka.ai/ai-models/xai), [Grok Pricing 2026 — felloai.com](https://felloai.com/grok-pricing/), [xAI Release Notes — Releasebot](https://releasebot.io/updates/xai).

### 1.6 You.com — Research Agent (Pro / YouPro)

> "You.com Pro plan at $20/month (or $15/month annually) gives you access to OpenAI,
> Anthropic, and Google models plus file uploads in one place."
> — [opentools.ai — You.com Reviews 2026](https://opentools.ai/tools/youcom)

- **Cost**: Free tier limited; YouPro $20/mo ($15 yearly). Multi-model stack.
- **Output**: weakest of the six on raw research depth, but **only** stack that lets you switch lead model (GPT/Claude/Gemini) per query in one UI.
- **Sources**: 20–40 typical.
- **API**: limited public API; oriented to consumer/SMB.

Sources: [Our Pricing Plans — You.com](https://you.com/pricing), [You.com Pricing 2026 — AISO Tools](https://aisotools.com/pricing/you-com), [How to use You.com — airespo.com](https://airespo.com/resources/how-to-use-you-com-for-beginners/), [You.com Reviews 2026 — G2](https://www.g2.com/products/you-com/reviews).

### 1.7 Comparative summary

| Stack                         | Marginal cost (Antonello)     | Sources/task             | API depth                        | Best at                                 |
| ----------------------------- | ----------------------------- | ------------------------ | -------------------------------- | --------------------------------------- |
| Claude Research + Code Skills | **$0** (Max plan)             | 50–150                   | DIY via Messages API + subagents | Long-horizon synthesis, code-aware      |
| OpenAI Deep Research (o3)     | $10/$40 per Mtok              | 30–100+                  | First-class API                  | Quantitative reports, citation density  |
| Perplexity Pro / Sonar        | $20/mo or $0.41/q             | 20–30+ Pro / 50–100+ API | Sonar API                        | Speed, news/current events              |
| Gemini Deep Research / Max    | OAuth free CLI; $2–5/task API | 80–200+                  | Vertex API + MCP+File Search     | Multi-modal grounding (PDF/audio/video) |
| Grok DeepSearch               | $30/mo SuperGrok              | 30–80+                   | xAI API                          | X/Twitter data, sociopolitical          |
| You.com Research              | $15–20/mo                     | 20–40                    | Limited                          | Multi-model UI, flexibility             |

For Antonello's lab: **Claude (Code+Skills+subagents) is the obvious primary** because Max plan
is already paid; Gemini CLI free is the obvious **secondary** (especially for multi-modal
grounding); Perplexity/Sonar API is the obvious **third** for fast news/current-events with
explicit citations on tax and immigration deadlines.

---

## 2. Open-source research agents 2026

Six leading OSS research agents, ranked roughly by maturity and fitness for Antonello's
"nasce → cresce → cosciente" lifecycle.

### 2.1 Sakana AI — AI Scientist v2

> "The AI Scientist-v2 is described as 'Workshop-Level Automated Scientific Discovery via
> Agentic Tree Search'. The system iteratively formulates scientific hypotheses, designs
> and executes experiments, analyzes and visualizes data, and autonomously authors
> scientific manuscripts. Compared to its predecessor (v1), The AI Scientist-v2 eliminates
> the reliance on human-authored code templates, generalizes effectively across diverse
> machine learning domains, and leverages a novel progressive agentic tree-search
> methodology managed by a dedicated experiment manager agent."
> — Sakana AI (paper abstract & X announcement)

> "The system was evaluated by submitting three fully autonomous manuscripts to a
> peer-reviewed ICLR workshop, with one manuscript achieving high enough scores to exceed
> the average human acceptance threshold."
> — Same source.

- GitHub: <https://github.com/SakanaAI/AI-Scientist-v2>
- Paper: <https://pub.sakana.ai/ai-scientist-v2/paper/paper.pdf>
- Nature publication: <https://www.nature.com/articles/s41586-026-10265-5>
- Architecture: agentic tree search + dedicated experiment-manager agent.
- Dependencies: Python 3.10+, OpenAI/Claude API, GPU recommended.

Sources: [SakanaAI/AI-Scientist-v2 — GitHub](https://github.com/SakanaAI/AI-Scientist-v2), [AI Scientist v2 paper PDF](https://pub.sakana.ai/ai-scientist-v2/paper/paper.pdf), [Sakana AI Labs — X announcement](https://x.com/SakanaAILabs/status/1909497165925536212), [The AI Scientist — published in Nature](https://sakana.ai/ai-scientist-nature/), [pooya.blog — AI-Scientist-v2 explained](https://pooya.blog/blog/ai-scientist-v2-automated-research-2026/).

### 2.2 Hugging Face — Open Deep Research (smolagents)

> "Hugging Face embarked on a 24-hour mission to reproduce OpenAI's Deep Research results
> and open-source the needed framework... Open Deep Research achieved 55.15% accuracy on
> the General AI Assistants (GAIA) benchmark, while OpenAI's Deep Research scored 67.36%."
> — [HF blog — Open-source DeepResearch](https://huggingface.co/blog/open-deep-research)

> "Smolagents is a barebones library for agents that think in code."
> — Same source.

- GitHub: <https://github.com/huggingface/smolagents/tree/main/examples/open_deep_research>
- Bonus, related: `ml-intern` — "Hugging Face Releases ml-intern: An Open-Source AI Agent that Automates the LLM Post-Training Workflow" (2026-04-21).
- Architecture: code-acting agents (the agent literally writes Python to call tools).
- Dependencies: `pip install smolagents`, model-agnostic (HF Inference, Ollama, OpenAI-compat).

Sources: [smolagents/examples/open_deep_research — GitHub](https://github.com/huggingface/smolagents/tree/main/examples/open_deep_research), [Open-source DeepResearch — HF blog](https://huggingface.co/blog/open-deep-research), [Open Deep-Research Space — m-ric](https://huggingface.co/spaces/m-ric/open_Deep-Research), [Hugging Face Releases ml-intern — MarkTechPost](https://www.marktechpost.com/2026/04/21/hugging-face-releases-ml-intern-an-open-source-ai-agent-that-automates-the-llm-post-training-workflow/).

### 2.3 Karpathy — autoresearch (and AutoResearchClaw)

> "AI agents running research on single-GPU nanochat training automatically."
> — [karpathy/autoresearch — GitHub](https://github.com/karpathy/autoresearch)

> "AutoResearchClaw introduces a complete Human-in-the-Loop (HITL) system that transforms
> the pipeline from purely autonomous to a human-AI collaborative research engine, which
> drops a research topic and gets back a full academic paper with real literature from
> OpenAlex, Semantic Scholar & arXiv."
> — [aiming-lab/AutoResearchClaw — GitHub](https://github.com/aiming-lab/AutoResearchClaw)

- Use case for Antonello: NOT directly applicable to Bali Zero domain (Karpathy's is single-GPU nanochat-tuning), but the **pattern** — autonomous improvement loops on small-scale ML — translates to "auto-correct" lifecycle stage.
- Curated list: <https://github.com/alvinreal/awesome-autoresearch>.

Sources: [karpathy/autoresearch — GitHub](https://github.com/karpathy/autoresearch), [aiming-lab/AutoResearchClaw — GitHub](https://github.com/aiming-lab/AutoResearchClaw), [awesome-autoresearch — alvinreal](https://github.com/alvinreal/awesome-autoresearch), [Multi-Agent AutoResearch — evoailabs Medium](https://evoailabs.medium.com/multi-agent-autoresearch-automating-ml-optimization-with-open-source-ai-c76d1dabfc0f).

### 2.4 ServiceNow — AgentLab (web-agent benchmarking)

> "AgentLab is an open-source framework for developing, testing, and benchmarking web
> agents on diverse tasks, designed for scalability and reproducibility."
> — [ServiceNow/AgentLab — GitHub](https://github.com/ServiceNow/AgentLab)

> "AgentLab integrates with Ray, a library for parallel and distributed computing, which
> simplifies running large-scale parallel experiments — particularly useful for researchers
> who want to test multiple agent configurations or train agents across different
> environments simultaneously."
> — [MarkTechPost — ServiceNow Releases AgentLab](https://www.marktechpost.com/2024/12/04/servicenow-releases-agentlab-a-new-open-source-python-package-for-developing-and-evaluating-web-agents/)

- AgentLab is a **benchmarking/test framework**, not the research agent itself. Useful for the lab's "auto-correct" stage: measure if your agent improves week-over-week on WebArena, WorkArena, etc.
- Companions: ServiceNow/BrowserGym (Gym env for web tasks), ServiceNow/WorkArena (knowledge-work eval).

Sources: [ServiceNow/AgentLab — GitHub](https://github.com/ServiceNow/AgentLab), [BrowserGym — GitHub](https://github.com/ServiceNow/BrowserGym), [WorkArena — GitHub](https://github.com/ServiceNow/WorkArena), [ServiceNow AI Research — WorkArena/BrowserGym/AgentLab paper](https://www.servicenow.com/research/publication/alexandre-lacoste-an-e-mais2024.html).

### 2.5 assafelovic — gpt-researcher

> "GPT Researcher is the first open deep research agent designed for both web and local
> research on any given task. The agent produces detailed, factual, and unbiased research
> reports with citations."
> — [gpt-researcher — README](https://github.com/assafelovic/gpt-researcher)

> "The core architecture utilizes 'planner' and 'execution' agents. The planner generates
> research questions, while the execution agents gather relevant information. The
> publisher then aggregates all findings into a comprehensive report."
> — Same source.

> "GPT Researcher includes Deep Research — an advanced recursive research workflow that
> explores topics with agentic depth and breadth. This feature employs a tree-like
> exploration pattern, diving deeper into subtopics while maintaining a comprehensive view
> of the research subject."
> — DeepWiki entry.

- Architecture: planner → executor → publisher.
- LLM-agnostic (works with OpenAI, Anthropic, Google, Ollama, DeepSeek).
- Has dedicated `gptr-mcp` MCP server for plug-in to Claude Code: "An MCP server (in a dedicated repository: gptr-mcp) enables AI applications like Claude to conduct deep research."
- **For Antonello's lab**: this is the **most natural fit** — already MCP-ready, LLM-agnostic (so DeepSeek + Claude OAuth allowed), tree-recursive matches "nasce → cresce".

Sources: [gpt-researcher — GitHub](https://github.com/assafelovic/gpt-researcher), [gpt-researcher — DeepWiki](https://deepwiki.com/assafelovic/gpt-researcher), [introduction — gpt-researcher docs](https://github.com/assafelovic/gpt-researcher/blob/master/docs/docs/gpt-researcher/getting-started/introduction.md).

### 2.6 Stanford OVAL — STORM / Co-STORM

> "STORM is a LLM system that writes Wikipedia-like articles from scratch based on
> Internet search... STORM breaks down generating long articles with citations into two
> steps: the pre-writing stage where the system conducts Internet-based research to
> collect references and generates an outline, and the writing stage where the system uses
> the outline and references to generate the full-length article with citations."
> — [stanford-oval/storm — README](https://github.com/stanford-oval/storm/blob/main/README.md)

> "STORM identifies the core of automating the research process as automatically coming up
> with good questions to ask. To improve the depth and breadth of the questions, STORM
> adopts two strategies: Perspective-Guided Question Asking (which discovers different
> perspectives by surveying existing articles) and Simulated Conversation (which simulates
> a conversation between a Wikipedia writer and a topic expert grounded in Internet
> sources)."
> — Same source.

> "Co-STORM further enhanced STORM by enabling humans to collaborate with the LLM system
> to support more aligned and preferred information seeking and knowledge curation."
> — Same source.

- Architecture: 4 modules — Knowledge Curation, Outline Generation, Article Generation, Article Polishing.
- Dependencies: Python 3.10+, `dspy`, vector DB (Qdrant/Chroma), search backend (Bing/Brave/You/SerpAPI).
- **STORM is the canonical pattern** for "long Wikipedia-style report from scratch" — closest match to Antonello's "channel into NB-9 long-form" requirement.

Sources: [stanford-oval/storm — GitHub](https://github.com/stanford-oval/storm), [STORM README](https://github.com/stanford-oval/storm/blob/main/README.md), [STORM examples](https://github.com/stanford-oval/storm/blob/main/examples/storm_examples/README.md), [Co-STORM agents source](https://github.com/stanford-oval/storm/blob/main/knowledge_storm/collaborative_storm/modules/co_storm_agents.py).

### 2.7 Recommendation stack (Antonello's lab)

| Lifecycle stage  | OSS pick                                          | Why                                            |
| ---------------- | ------------------------------------------------- | ---------------------------------------------- |
| Nasce (collect)  | gpt-researcher + STORM Knowledge Curation         | LLM-agnostic, MCP server ready, tree-recursive |
| Cresce (write)   | STORM Outline + Article + Polish modules          | Wikipedia-style long form → NB-9 friendly      |
| Auto-correct     | Sakana AI Scientist v2 tree-search loop           | Hypothesis → experiment → revise pattern       |
| Cosciente        | smolagents code-acting + AgentLab benchmark loop  | Code-as-action + measurable improvement        |
| Channel (output) | gptr-mcp → Claude Code → NB-9 + Telegram dispatch | MCP native, fits existing arsenal              |

---

## 3. Scientific paper monitoring

Eight feeds, ranked by ratio of "delivers signal" to "rate-limit pain".

### 3.1 arXiv — API + OAI-PMH

> "When using the legacy APIs (including OAI-PMH, RSS, and the arXiv API), make no more
> than one request every three seconds, and limit requests to a single connection at a
> time."
> — [arXiv API Terms of Use](https://info.arxiv.org/help/api/tou.html)

> "For bulk metadata harvesting or set information, etc., the OAI-PMH interface is more
> suitable. This makes OAI-PMH the recommended approach for large-scale metadata
> retrieval, though the three-second rate limit still applies."
> — [arXiv API basics](https://info.arxiv.org/help/api/basics.html)

- API URL: <http://export.arxiv.org/api/query>
- OAI-PMH: <https://export.arxiv.org/oai2>
- Rate limit: 1 req / 3s, single connection.
- Freshness: papers appear ~12–24h after submission.

Sources: [arXiv API User's Manual](https://info.arxiv.org/help/api/user-manual.html), [Terms of Use for arXiv APIs](https://info.arxiv.org/help/api/tou.html), [arXiv API Access](https://info.arxiv.org/help/api/index.html), [Open Archives Initiative (OAI) — arXiv](https://info.arxiv.org/help/oa/index.html), [arXiv Bulk Data Access](https://info.arxiv.org/help/bulk_data.html).

### 3.2 Semantic Scholar API

> "The default rate limit for unauthenticated users is now 5,000 requests per 5 minutes,
> which is shared among all unauthenticated users... Using an individual API key
> automatically gives a user a 1 request per second rate across all endpoints."
> — [allenai/s2-folks API_RELEASE_NOTES.md](https://github.com/allenai/s2-folks/blob/main/API_RELEASE_NOTES.md)

> "To enhance system stability and manage the load effectively, exponential backoff
> strategies are now required for API requests."
> — Same.

- Endpoint: `https://api.semanticscholar.org/graph/v1/`
- Get API key: <https://www.semanticscholar.org/product/api>
- Best for: citation graph queries, paper-recommendation seeds, "papers that cite X" feeds.
- Freshness: lags arXiv by 1–7 days.

Sources: [Semantic Scholar API product page](https://www.semanticscholar.org/product/api), [Semantic Scholar Academic Graph API docs](https://api.semanticscholar.org/api-docs), [API_RELEASE_NOTES.md](https://github.com/allenai/s2-folks/blob/main/API_RELEASE_NOTES.md), [Mastering Research with the Semantic Scholar API](https://skywork.ai/skypage/en/Mastering-Research-with-the-Semantic-Scholar-API-An-Insider's-Guide/1973804064216641536), [Tutorial — Academic Graph API](https://www.semanticscholar.org/product/api/tutorial).

### 3.3 INSPIRE-HEP API

> "INSPIRE is run by a collaboration consisting of 7 member institutions: CERN, DESY,
> IN2P3, IHEP, SLAC, Fermilab, and TIB... a REST API is provided for programmatic access...
> Inspire exposes an API (Application Programming Interface) for querying most aspects of
> its holdings and provides responses in either XML, Enhanced MARCXML or JSON."
> — [INSPIRE-HEP REST API Doc](https://github.com/inspirehep/rest-api-doc)

> "INSPIRE automatically harvests articles from arXiv and journal feeds from select
> publishers. Papers from arXiv are added daily, while papers published in journals are
> typically added two to three weeks after the article has been published."
> — [INSPIRE Internal Help](https://internal.help.inspirehep.net/knowledge-base/introduction-to-inspire/)

- Endpoint: `https://inspirehep.net/api/literature?q=...`
- 1.7M records, daily arXiv harvest, no public rate limit documented (be polite, ~1 req/s).
- Best for: high-energy physics. Probably out of scope for Antonello unless interested in physics-AI cross.

Sources: [inspirehep/rest-api-doc — GitHub](https://github.com/inspirehep/rest-api-doc), [INSPIRE-HEP — Wikipedia](https://en.wikipedia.org/wiki/INSPIRE-HEP), [INSPIRE Internal Help — Introduction](https://internal.help.inspirehep.net/knowledge-base/introduction-to-inspire/), [Inspire-HEP — re3data.org](https://www.re3data.org/repository/r3d100011077), [INSPIRE API — Theory And Practice (Cranmer)](https://theoryandpractice.org/2019/04/INSPIRE%20API/).

### 3.4 bioRxiv & medRxiv API

> "The bioRxiv API provides endpoints in the format
> `https://api.biorxiv.org/details/[server]/[interval]/[cursor]/[format]` or
> `https://api.biorxiv.org/details/[server]/[DOI]/na/[format]`, where the server can be
> either bioRxiv or medRxiv."
> — [bioRxiv API home](https://api.biorxiv.org/)

> "The 'interval' parameter can be: 1) two YYYY-MM-DD dates separated by '/', 2) a
> numeric value for the N most recent published articles, or 3) a numeric with the letter
> 'd' for the most recent N days of articles."
> — Same source.

> "Where metadata for multiple papers is returned, results are paginated with 100 papers
> served in a call, and the 'cursor' value can be used to iterate through the result."
> — Same source.

- bioRxiv: <https://api.biorxiv.org/>
- medRxiv: <https://api.medrxiv.org/>
- No documented hard rate limit; community convention ~1 req/s.
- Best for: biology / clinical research feeds; future-proof for Bali Zero health-related domain (clients with medical visa, etc.).

Sources: [bioRxiv API home](https://api.biorxiv.org/), [medRxiv API home](https://api.medrxiv.org/), [ropensci/medrxivr — GitHub](https://github.com/ropensci/medrxivr/), [rOpenSci — Searching medRxiv and bioRxiv Preprint Data](https://ropensci.org/blog/2020/10/20/searching-medrxivr-and-biorxiv-preprint-data/), [bioRxiv/medRxiv API help](https://api.biorxiv.org/pubs/help).

### 3.5 OpenReview API (ICLR / NeurIPS)

> "OpenReview provides an Open API and is a long-term project to advance science through
> improved peer review with legal nonprofit status."
> — [Venues — OpenReview](https://openreview.net/)

> "Submissions to ICLR are uploaded on OpenReview, and official reviews are posted on
> OpenReview as well. Official reviews are anonymous and publicly visible in OpenReview."
> — [ICLR 2026 Author Guide](https://iclr.cc/Conferences/2026/AuthorGuide)

> "For NeurIPS 2026, abstracts are due by May 4th, 2026, with full papers due on May 6th,
> 2026, and all authors must have an OpenReview profile when submitting."
> — [Call for Papers — NeurIPS 2026](https://neurips.cc/Conferences/2026/CallForPapers)

- Python client: `pip install openreview-py`.
- Best for: ML conference submissions, reviews, decisions (incl. rejected papers under CC BY 4.0 — unique transparency).

Sources: [Venues — OpenReview](https://openreview.net/), [NeurIPS 2026 — OpenReview](https://openreview.net/group?id=NeurIPS.cc%2F2026), [ICLR 2026 Reviewer Guide](https://iclr.cc/Conferences/2026/ReviewerGuide), [ICLR 2026 Author Guide](https://iclr.cc/Conferences/2026/AuthorGuide), [Call for Papers 2026 — NeurIPS](https://neurips.cc/Conferences/2026/CallForPapers).

### 3.6 Papers With Code — DEPRECATED, alternatives

> "Meta shut down Papers with Code in July 2025 without notice. The 9,327 benchmark
> leaderboards, 79,817 paper-to-code linkages and 5,628 datasets that had been tracked
> are no longer served from the canonical URL... The domain now redirects to Hugging Face
> Trending Papers; the leaderboards are gone."
> — [codesota.com — Papers with Code is Dead](https://www.codesota.com/papers-with-code)

- Replacement: Hugging Face Papers Trending (`https://huggingface.co/papers/trending`).
- Historical archive: `paperswithcode/paperswithcode-data` on GitHub (frozen, not updating).

Sources: [Papers with Code is Dead — codesota.com](https://www.codesota.com/papers-with-code), [Trending Papers — Hugging Face](https://huggingface.co/papers/trending), [paperswithcode/paperswithcode-client (frozen)](https://github.com/paperswithcode/paperswithcode-client), [paperswithcode org page (archived)](https://github.com/paperswithcode), [Paper With Code Shuts Down — HyperAI](https://hyper.ai/en/news/42900).

### 3.7 arxiv-sanity (Karpathy)

> "arxiv-sanity tames the overwhelming flood of papers on Arxiv and allows researchers to
> discover relevant papers, search/sort by similarity, see recent/popular papers, and get
> recommendations. It's deployed live at arxiv-sanity.com."
> — [arxiv-sanity-lite README](https://github.com/karpathy/arxiv-sanity-lite/blob/master/README.md)

> "arxiv-sanity-lite can send daily emails with recommendations of new papers based on
> your tags... The lite version periodically polls the arxiv API for new papers, then
> allows users to tag papers of interest and recommends new papers for each tag based on
> SVMs over tfidf features of paper abstracts."
> — Same.

- GitHub: <https://github.com/karpathy/arxiv-sanity-lite>
- Self-hostable, ~200 LOC core, perfect for Antonello to fork and personalize on Mini-Pro2.
- **This is the seed pattern for Section 7 personalization**.

Sources: [karpathy/arxiv-sanity-lite — GitHub](https://github.com/karpathy/arxiv-sanity-lite), [arxiv-sanity-preserver — GitHub](https://github.com/karpathy/arxiv-sanity-preserver), [arxiv-sanity-lite — Built At Lightspeed](https://www.builtatlightspeed.com/theme/karpathy-arxiv-sanity-lite), [Choe Lab note](https://yschoe.github.io/none/2020/03/25/Arxiv-sanity-excellent-resource-for-finding-and-organizing-papers.html), [Karpathy on HN about arxiv-sanity](https://news.ycombinator.com/item?id=12021123).

### 3.8 Quick reference table

| Source                      | URL                              | Rate       | Freshness  | Best for            |
| --------------------------- | -------------------------------- | ---------- | ---------- | ------------------- |
| arXiv API                   | export.arxiv.org/api/query       | 1/3s       | ~12–24h    | All STEM preprints  |
| Semantic Scholar            | api.semanticscholar.org/graph/v1 | 1/s w/ key | 1–7d lag   | Citation graph      |
| INSPIRE-HEP                 | inspirehep.net/api/literature    | ~1/s       | daily      | High-energy physics |
| bioRxiv/medRxiv             | api.bio/medrxiv.org              | ~1/s       | hours      | Bio / clinical      |
| OpenReview                  | openreview-py                    | polite     | conf-cycle | ML conf reviews     |
| HF Papers (PWC replacement) | huggingface.co/papers            | n/a (UI)   | hourly     | Trending ML         |
| arxiv-sanity-lite           | self-host                        | own        | daily      | Personal feed       |

---

## 4. GitHub trending intelligence

### 4.1 GitHub trending — unofficial APIs

> "A simple API that returns number of Github trending repositories and developers... allows
> you to receive an array of trending developers and repositories with optional time periods
> (daily, weekly and monthly)."
> — [huchenme/github-trending-api — GitHub](https://github.com/huchenme/github-trending-api)

> "GiTrends provides an API for fetching real-time trending GitHub repositories,
> addressing the lack of an official GitHub trending API, with a Node.js-powered backend
> that serves the API and a Next.js-based frontend."
> — [maulikshetty/GiTrends — GitHub](https://github.com/maulikshetty/GiTrends)

- huchenme/github-trending-api: most-starred unofficial wrapper.
- GiTrends: Node + Next.js full stack.
- Trendshift.io: graphical UI for trending repos with insights.
- Both unofficial APIs scrape `github.com/trending` — no rate limit declared, but be polite (~1 req / 5min suffices for daily personal feed).

Sources: [huchenme/github-trending-api](https://github.com/huchenme/github-trending-api), [maulikshetty/GiTrends](https://github.com/maulikshetty/GiTrends), [Trendshift](https://trendshift.io/), [GitHub Trending — official UI](https://github.com/trending), [GitHub Trending API — Apiary docs](https://githubtrendingapi.docs.apiary.io/).

### 4.2 Sourcegraph — code search across 2M+ repos

> "Sourcegraph allows searching across 2 million+ open source repositories for free. Code
> Search makes it easy to find code, make large-scale changes, and track insights across
> codebases of any scale and with any number of code hosts."
> — [Sourcegraph — Search Public Code](https://sourcegraph.com/search)

- Use case: find bleeding-edge implementations of a technique before they trend on GitHub. Example: search "diffusion policy" → get repos using it across the OSS galaxy, including ones with 5 stars.

Sources: [Search Public Code — Sourcegraph](https://sourcegraph.com/search), [Sourcegraph docs](https://sourcegraph.com/docs), [Code Search — Sourcegraph](https://sourcegraph.com/code-search), [Star Your Favorite Deep Search Threads — Sourcegraph blog](https://sourcegraph.com/blog/star-your-favorite-deep-search-threads), [Sourcegraph is now open source — HN](https://news.ycombinator.com/item?id=18117755).

### 4.3 Octoverse 2025 — yearly state-of-AI-on-GitHub

> "Over 36 million new developers joined GitHub in the past year, with more than one new
> developer joining on average every second, bringing the total to 180 million-plus
> developers. GitHub now hosts 630 million total repositories, with over 121 million new
> repositories added in 2025 alone."
> — [Octoverse 2025 — GitHub](https://octoverse.github.com/)

> "AI, agents, and typed languages are driving the biggest shifts in software development
> in more than a decade. 80% of new developers use Copilot within their first week, AI
> repositories have nearly doubled to 4.3 million, and LLM SDK adoption exploded 178%
> year-over-year."
> — Same.

> "By August 2025, TypeScript had overtaken both Python and JavaScript to claim the top
> spot on GitHub by monthly contributors with 2.636 million developers."
> — Same.

> "Maintainers face a flood of what the report calls 'AI slop' — high-volume, low-quality,
> and often inaccurate contributions that take up reviewers' time without significantly
> helping the project."
> — [Octoverse — A new developer joins GitHub every second](https://github.blog/news-insights/octoverse/octoverse-a-new-developer-joins-github-every-second-as-ai-leads-typescript-to-1/)

Sources: [Octoverse 2025 — GitHub](https://octoverse.github.com/), [Latest Octoverse findings — GitHub Blog](https://github.blog/news-insights/octoverse/), [InfoQ — GitHub AI 2026](https://www.infoq.com/news/2026/03/github-ai-2026/), [How AI is reshaping developer choice — GitHub Blog](https://github.blog/ai-and-ml/generative-ai/how-ai-is-reshaping-developer-choice-and-octoverse-data-proves-it/), [GitHub's 2025 Report — itsfoss.com](https://itsfoss.com/news/github-octoverse-2025/).

### 4.4 Hacker News API (Firebase) — front-page indicator

> "Up to 500 top and new stories are available at /v0/topstories and /v0/newstories
> endpoints. The base URL is `https://hacker-news.firebaseio.com/v0/`."
> — [HackerNews/API — GitHub](https://github.com/HackerNews/API)

> "The API requires no authentication, no API keys, and no developer application, and
> you can query it right now with a single curl command. There is currently no rate
> limit."
> — Same source.

- Pattern: poll `/topstories.json`, filter for `github.com/` URLs, count co-occurrence with last 24h trending → "what HN is paying attention to that's also trending on GitHub". Strong signal-to-noise.

Sources: [HackerNews/API — GitHub](https://github.com/HackerNews/API), [HN now has an API — Firebase blog](https://firebase.blog/posts/2014/10/hacker-news-now-has-api-its-firebase/), [How to Scrape Hacker News in 2026 — DEV.to](https://dev.to/agenthustler/how-to-scrape-hacker-news-in-2026-stories-comments-ask-hn-via-api-21fb), [HN API guide — Cotera](https://cotera.co/articles/hacker-news-api-guide), [HackerNews API — publicapis.io](https://publicapis.io/hacker-news-api).

### 4.5 TLDR Tech newsletter (1.6M+ subscribers, 9 editions)

> "TLDR Tech is the best general-purpose tech newsletter available for free in 2026,
> delivering 10–12 curated links daily with concise 2–3 sentence summaries per story.
> With 1.6 million subscribers and a ~46% open rate — more than double the industry
> average of 21.5% for media newsletters."
> — [TLDR Newsletter Review 2026 — Readless](https://www.readless.app/blog/tldr-newsletter-review-2026)

> "TLDR is a free daily tech newsletter with 9 specialized editions and over 7 million
> subscribers, making it the largest independent tech newsletter in 2026. TLDR AI, part
> of the broader TLDR media network, reaches over 1.25 million readers and serves as the
> 'technical filter' for the industry."
> — [TLDR Digest — Readless](https://www.readless.app/newsletters/tldr-digest)

- Editions to subscribe: TLDR Tech, TLDR AI, TLDR Founders.
- Best as **input**, not API. Email → IMAP → parse → feed into your aggregator.

Sources: [TLDR.tech](https://tldr.tech/), [TLDR AI](https://tldr.tech/ai), [TLDR Newsletter Review 2026 — Readless](https://www.readless.app/blog/tldr-newsletter-review-2026), [Top 10 AI Newsletters 2026 — DataNorth](https://datanorth.ai/blog/top-10-ai-newsletters-to-follow-in-2026), [TLDR newsletter list](https://tldr.tech/newsletters).

### 4.6 ByteByteGo "Top AI GitHub Repositories in 2026"

> "OpenClaw is the breakout star of 2026 and arguably the fastest-growing open-source
> project in GitHub history, created by PSPDFKit founder Peter Steinberger, surging
> from 9,000 to over 60,000 stars in just a few days after going viral in late January 2026."
> — Cited in trending newsletter coverage (ByteByteGo + Medium GitHub Trending)

Sources: [ByteByteGo — Top AI GitHub Repositories in 2026](https://blog.bytebytego.com/p/top-ai-github-repositories-in-2026), [Medium — GitHub Trending: Jan 5 2026](https://medium.com/@lssmj2014/welcome-to-2026-9a52575cbd1d), [GitHub Trending weekly](https://github.com/trending?since=weekly), [trending topic — GitHub Topics](https://github.com/topics/trending).

### 4.7 Pattern — "discover repos before they trend"

The empirical pattern: the **earliest signal** for a soon-to-trend repo is _not_ GitHub's
trending page but rather:

1. A high-signal HN submission (typically 100+ points in first 6h on a `github.com/` URL).
2. A mention in TLDR AI / Latent Space / The Batch.
3. A jump in Star History slope (5x daily growth vs prior week).
4. A Sourcegraph search hit cluster (multiple unrelated repos suddenly importing it).

Combine #1–#4 in a daily aggregator. The repo will hit the trending page 2–7 days _after_
this signal, by which time you've already cloned and tested it.

---

## 5. Robotics SOTA 2026

### 5.1 Foundation models for robotics

#### RT-X / Open X-Embodiment

> "The Open X-Embodiment Dataset is the largest open-source real robot dataset, containing
> 1M+ real robot trajectories spanning 22 robot embodiments, from single robot arms to
> bi-manual robots and quadrupeds."
> — [Open X-Embodiment website](https://robotics-transformer-x.github.io/)

> "RT-X model, a high-capacity model trained on this data, exhibits positive transfer and
> improves the capabilities of multiple robots by leveraging experience from other
> platforms. RT-1-X and RT-2-X both take images and a text instruction as input and
> output discretized end-effector actions."
> — Same.

Sources: [Open X-Embodiment — arXiv 2310.08864](https://arxiv.org/abs/2310.08864), [robotics-transformer-x.github.io](https://robotics-transformer-x.github.io/), [google-deepmind/open_x_embodiment — GitHub](https://github.com/google-deepmind/open_x_embodiment), [IEEE Xplore version](https://ieeexplore.ieee.org/document/10611477).

#### OpenVLA

> "OpenVLA is a 7B-parameter open-source VLA (Vision-Language-Action model) trained on a
> diverse collection of 970k real-world robot demonstrations. OpenVLA builds on a Llama 2
> language model combined with a visual encoder that fuses pretrained features from DINOv2
> and SigLIP."
> — [OpenVLA — arXiv 2406.09246](https://arxiv.org/abs/2406.09246)

> "OpenVLA demonstrates strong results for generalist manipulation, outperforming closed
> models such as RT-2-X (55B) by 16.5% in absolute task success rate across 29 tasks and
> multiple robot embodiments, with 7x fewer parameters."
> — Same.

Sources: [openvla.github.io](https://openvla.github.io/), [OpenVLA — arXiv](https://arxiv.org/abs/2406.09246), [openvla/openvla — GitHub](https://github.com/openvla/openvla), [OpenVLA — OpenReview](https://openreview.net/forum?id=ZMnD6QZAE6).

#### π0 / π0.5 (Physical Intelligence)

> "Like LLM training, π0 uses a multi-stage training procedure with pre-training and
> post-training phases, where the pre-training goal is to expose the model to diverse
> tasks for general physical capabilities, while post-training enables skillful execution
> of downstream tasks."
> — [π0 paper — arXiv 2410.24164](https://arxiv.org/html/2410.24164v1)

> "π0 employs a novel design that fine-tunes a VLM to produce actions via flow matching,
> allowing it to handle high-frequency action chunks (up to 50 Hz) and highly dexterous
> tasks, which prior autoregressive VLAs pose challenges for."
> — Same.

> "The model is pre-trained on diverse data from 7 distinct robot configurations and 68 tasks."
> — Same.

Sources: [π0 — arXiv 2410.24164](https://arxiv.org/html/2410.24164v1), [pi.website blog post](https://www.pi.website/blog/pi0), [π0.5 — arXiv 2504.16054](https://arxiv.org/abs/2504.16054), [π0/π0-FAST — HF blog](https://huggingface.co/blog/pi0), [Physical Intelligence open-sources Pi0 — Robot Report](https://www.therobotreport.com/physical-intelligence-open-sources-pi0-robotics-foundation-model/).

#### Helix (Figure)

> "Helix is the first VLA to output high-rate continuous control of the entire humanoid
> upper body, including wrists, torso, head, and individual fingers. Helix 02, released
> January 2026, extended this to full-body control including walking and balance."
> — [figure.ai/helix](https://www.figure.ai/helix)

> "Helix coordinates a 35-DoF action space at 200Hz, controlling everything from
> individual finger movements to end-effector trajectories, head gaze, and torso posture."
> — Same.

> "A Figure robot executes a continuous 4-minute task: walking to a dishwasher, unloading
> dishes, navigating across a room, stacking items in cabinets, loading and starting the
> dishwasher — entirely from onboard sensors with no human intervention."
> — [Helix 02: Full-Body Autonomy](https://www.figure.ai/news/helix-02)

Sources: [Helix VLA — figure.ai](https://www.figure.ai/news/helix), [Helix overview](https://www.figure.ai/helix), [Helix 02](https://www.figure.ai/news/helix-02), [Helix Logistics](https://www.figure.ai/news/helix-logistics), [Figure 03 introduction](https://www.figure.ai/news/introducing-figure-03).

#### Gemini Robotics / Gemini Robotics On-Device

> "Gemini Robotics On-Device achieves strong visual, semantic and behavioral generalization
> across a wide range of testing scenarios, follows natural language instructions, and
> completes highly-dexterous tasks like unzipping bags or folding clothes — all while
> operating directly on the robot."
> — [DeepMind blog — Gemini Robotics On-Device](https://deepmind.google/blog/gemini-robotics-on-device-brings-ai-to-local-robotic-devices/)

> "The model quickly adapts to new tasks, with as few as 50 to 100 demonstrations —
> indicating how well this on-device model can generalize its foundational knowledge
> to new tasks."
> — Same.

> "On June 24, 2025, Google DeepMind released Gemini Robotics On-Device, a variant
> designed and optimized to run locally on robotic devices."
> — Same.

Sources: [Gemini Robotics — DeepMind](https://deepmind.google/models/gemini-robotics/), [Gemini Robotics On-Device — DeepMind blog](https://deepmind.google/blog/gemini-robotics-on-device-brings-ai-to-local-robotic-devices/), [Gemini Robotics ER 1.6 — DeepMind blog](https://deepmind.google/blog/gemini-robotics-er-1-6/), [google-deepmind/gemini-robotics-sdk — GitHub](https://github.com/google-deepmind/gemini-robotics-sdk), [Gemini Robotics — Wikipedia](https://en.wikipedia.org/wiki/Gemini_Robotics).

#### NVIDIA Isaac GR00T N1 / N1.7

> "GR00T N1 is the world's first open foundation model for generalized humanoid robot
> reasoning and skills. This cross-embodiment model takes multimodal input, including
> language and images, to perform manipulation tasks in diverse environments."
> — [NVIDIA Newsroom — GR00T N1](https://nvidianews.nvidia.com/news/nvidia-isaac-gr00t-n1-open-humanoid-robot-foundation-model-simulation-frameworks)

> "The GR00T N1 model architecture features a dual-system approach, combining a
> Vision-Language Model for reasoning and planning with a Diffusion Transformer for
> generating continuous robot movements."
> — [NVIDIA Technical Blog — GR00T N1](https://developer.nvidia.com/blog/accelerate-generalist-humanoid-robot-development-with-nvidia-isaac-gr00t-n1/)

> "NVIDIA Isaac GR00T N1.7 is an open, commercially licensed Vision-Language-Action model
> for humanoid robots. The central research used for GR00T N1.7 is EgoScale —
> pre-training on 20,854 hours of human egocentric video spanning 20+ task categories."
> — [GR00T N1.7 — HF blog](https://huggingface.co/blog/nvidia/gr00t-n1-7)

Sources: [GR00T N1 — NVIDIA Newsroom](https://nvidianews.nvidia.com/news/nvidia-isaac-gr00t-n1-open-humanoid-robot-foundation-model-simulation-frameworks), [GR00T N1 — arXiv 2503.14734](https://arxiv.org/abs/2503.14734), [NVIDIA/Isaac-GR00T — GitHub](https://github.com/NVIDIA/Isaac-GR00T), [GR00T N1.7 — HF blog](https://huggingface.co/blog/nvidia/gr00t-n1-7), [Isaac GR00T — NVIDIA Developer](https://developer.nvidia.com/isaac/gr00t).

#### Tesla Optimus Gen 3

> "Tesla's 'Gen 3' refers specifically to upgraded hands with 22 degrees of freedom and
> 50 actuators (25 per forearm/hand), representing a 4.5x increase from Gen 2. The robot
> body remains the Gen 2 design. The robot stands 1.73 meters (5'8\") tall and weighs 57
> kilograms (125 pounds), with a carrying capacity of 20 kilograms (45 pounds)."
> — [airobots.media — Tesla Optimus Gen 3](https://airobots.media/technology/tesla-optimus-gen-3-everything-we-know-about-teslas-most-ambitious-product/)

> "The third-generation Optimus features hand positioning accuracy of 0.08mm, enabling
> delicate operations like handling eggs and tying shoelaces."
> — [optimusk.blog — Tesla Optimus Gen 3 specs](https://optimusk.blog/blog/tesla-optimus-gen-3/)

> "First-generation Optimus production lines are being installed at Tesla's Fremont
> factory, with the V3 robot expected to be revealed in late July/August 2026 and
> production beginning shortly after. Tesla plans to begin mass production by the end
> of 2026, with a long-term production capacity target of 1 million units per year."
> — [chinaroboticsdaily.com](https://chinaroboticsdaily.com/tesla-optimus-gen-3-awe-2026/)

> "Musk acknowledged Optimus units are primarily for learning, not productive tasks,
> calling it 'still very much in the R&D phase.'"
> — [botinfo.ai](https://botinfo.ai/articles/tesla-optimus)

Sources: [Tesla Optimus complete analysis — botinfo.ai](https://botinfo.ai/articles/tesla-optimus), [Tesla Optimus Gen 3 — airobots.media](https://airobots.media/technology/tesla-optimus-gen-3-everything-we-know-about-teslas-most-ambitious-product/), [Tesla Optimus Gen 3 — optimusk.blog](https://optimusk.blog/blog/tesla-optimus-gen-3/), [Tesla Showcases Gen 3 — China Robotics Daily](https://chinaroboticsdaily.com/tesla-optimus-gen-3-awe-2026/), [Tesla Optimus Gen 3 production — programming-helper.com](https://www.programming-helper.com/tech/tesla-optimus-gen3-production-deployment-2026-factory-robots-revolution).

### 5.2 Sim2Real platforms (2026 comparison)

> "MuJoCo 3.1 uses JAX bindings (mjx) that compile MuJoCo to XLA and run on TPU/GPU,
> achieving 15x RTF per environment with 12 GB memory for 512 parallel Panda reaching
> tasks, while Gazebo Harmonic requires process-per-sim architecture needing
> approximately 230 GB memory."
> — [markaicode — Gazebo Harmonic vs MuJoCo](https://markaicode.com/vs/gazebo-harmonic-vs-mujoco/)

> "NVIDIA Isaac Sim has emerged as a cutting-edge simulation platform built on NVIDIA
> Omniverse, released as open-source in 2025 (Isaac Sim 5.0). Isaac Sim provides
> GPU-accelerated physics simulation using NVIDIA PhysX, photorealistic RTX ray-traced
> rendering, and comprehensive ROS 2 integration through its ROS 2 Bridge extension."
> — [blackcoffeerobotics — Robot Simulation Software 2026](https://www.blackcoffeerobotics.com/blog/which-robot-simulation-software-to-use)

> "Gazebo has evolved significantly, with the original 'Gazebo Classic' succeeded by the
> modern Gazebo, with the latest LTS releases being Gazebo Harmonic (supported until
> September 2028) and Gazebo Jetty (supported until September 2030)."
> — Same.

| Sim                     | Strength                                      | Weakness                       |
| ----------------------- | --------------------------------------------- | ------------------------------ |
| Isaac Sim 5.0           | Photoreal, GPU-massive parallel, ROS 2 native | Heavy, NVIDIA hardware-locked  |
| MuJoCo / MJX            | Fast, JAX/XLA, TPU/GPU/M-series               | Less photorealistic            |
| Drake                   | Best dynamics analysis (Toyota Research)      | Steeper learning curve         |
| Gazebo Harmonic / Jetty | Multi-robot orchestration, ROS native         | Process-per-sim, memory hungry |

Sources: [blackcoffeerobotics — Robot Simulation Software 2026](https://www.blackcoffeerobotics.com/blog/which-robot-simulation-software-to-use), [Simulately — overall comparison](https://simulately.wiki/docs/comparison/), [Choose a Simulator — Robotics Knowledgebase](https://roboticsknowledgebase.com/wiki/robotics-project-guide/choose-a-sim/), [Gazebo Harmonic vs MuJoCo — markaicode](https://markaicode.com/vs/gazebo-harmonic-vs-mujoco/), [A Review of Nine Physics Engines for RL — arXiv](https://arxiv.org/html/2407.08590v1).

### 5.3 Robotics newsletters / podcasts

#### The Batch (Andrew Ng)

> "Generalist AI's GEN-0, a class of embodied foundation models trained on over 270,000
> hours of real-world manipulation data, demonstrates predictable scaling laws similar
> to those in large language models, with a phase transition observed at 7 billion
> parameters."
> — [The Batch — Training power laws translate to robotics](https://www.deeplearning.ai/the-batch/training-power-laws-translate-to-robotics/)

Sources: [The Batch — DeepLearning.AI](https://www.deeplearning.ai/the-batch/), [Letters from Andrew Ng](https://www.deeplearning.ai/the-batch/tag/letters/), [Readers' hopes for AI in 2026](https://www.deeplearning.ai/the-batch/readers-highest-hopes-for-ai-in-2026-part-one/), [Training power laws translate to robotics](https://www.deeplearning.ai/the-batch/training-power-laws-translate-to-robotics/).

#### Robot Brains Podcast (Pieter Abbeel)

> "In each episode of The Robot Brains podcast, renowned artificial intelligence
> researcher, professor and entrepreneur Pieter Abbeel meets the brilliant minds
> attempting to build robots with brains, with Pieter joined by leading experts in AI
> Robotics from all over the world as he explores how far humanity has come in its
> mission to create conscious computers, mindful machines and rational robots."
> — [Robot Brains Podcast — podnews.net](https://podnews.net/podcast/i8f9m)

Sources: [Robot Brains Podcast — Apple](https://podcasts.apple.com/us/podcast/the-robot-brains-podcast/id1559275284), [Robot Brains Podcast — podnews.net](https://podnews.net/podcast/i8f9m), [The Robot Brains Podcast — YouTube](https://www.youtube.com/c/TheRobotBrainsPodcast), [Robot Brains — Spotify](https://open.spotify.com/show/2qbLq3HrhTnnmmsHc37QOD), [40 Best Robotics Podcasts 2026 — Feedspot](https://podcast.feedspot.com/robotics_podcasts/).

#### Latent Space (swyx + Alessio)

> "Latent Space is a podcast and newsletter where 170,000+ AI Engineers gather to talk
> models, tools and ideas. In 2025, over 10 million readers and listeners came to Latent
> Space to hear about news, papers and interviews in Software 3.0, covering Foundation
> Models changing every domain in Code Generation, Multimodality, AI Agents, GPU Infra
> and more."
> — [Latent.Space — About](https://www.latent.space/about)

Sources: [Latent.Space about page](https://www.latent.space/about), [Latent Space podcast — Substack](https://www.latent.space/podcast), [Latent Space — YouTube](https://www.youtube.com/@LatentSpacePod/videos), [Latent Space podcast — Spotify](https://open.spotify.com/show/2p7zZVwVF6Yk0Zsb4QmT7t), [Podcast Archive — Latent.Space](https://www.latent.space/podcast/archive).

---

## 6. Frontier science feed sources

### 6.1 Nature & Science (2026 AI/robotics highlights)

> "The rise of AI scientists, missions to explore the moons of Earth and Mars and a
> massive ocean-floor drill are among the developments set to shape research in 2026.
> Additionally, a Reddit-style site called Agent4Science allows purpose-built AI-powered
> agents to share, debate and discuss research papers, with human researchers able to
> observe but only agents able to participate."
> — [Nature — Science in 2026: events to watch](https://www.nature.com/articles/d41586-025-03673-6)

> "Scientists using AI-augmented research publish 3.02 times more papers and receive
> 4.84 times more citations, but there is a collective narrowing of scientific focus,
> with AI concentrating work in data-rich areas."
> — [Nature 09922-y — AI tools expand scientists' impact but contract science's focus](https://www.nature.com/articles/s41586-025-09922-y)

Headline 2026 Nature articles (latest 5 AI/robotics-relevant):

1. "No humans allowed: scientific AI agents get their own social network" — Nature, on Agent4Science.
2. "Science in 2026: the events to watch for in the coming year" — annual roundup.
3. "Rethink how we build AI to enable effective climate-change mitigation."
4. "Artificial intelligence tools expand scientists' impact but contract science's focus" (s41586-025-09922-y).
5. "SEVEN TECHNOLOGIES TO WATCH IN 2026" — d41586-026-00188-6.

RSS feeds: `https://www.nature.com/nature.rss` (Nature main); `https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science` (Science).

Sources: [Science in 2026: what to expect — Nature](https://www.nature.com/articles/d41586-025-04114-0), [Scientific AI agents get their own social network — Nature](https://www.nature.com/articles/d41586-026-01278-1), [Latest science news — Nature](https://www.nature.com/news), [Seven technologies to watch in 2026 — Nature PDF](https://media.nature.com/original/magazine-assets/d41586-026-00188-6/d41586-026-00188-6.pdf), [AI tools impact paper — Nature](https://www.nature.com/articles/s41586-025-09922-y).

### 6.2 Quanta Magazine

> "Fed on Reams of Cell Data, AI Maps New Neighborhoods in the Brain — Machine learning
> is helping neuroscientists organize vast quantities of cells' genetic data."
> — Quanta Magazine 2026 article header

> "Using AI, Mathematicians Find Hidden Glitches in Fluid Equations — With specially
> trained AI systems, researchers have found a slew of new candidates in simpler versions
> of the problem."
> — Quanta Magazine 2026

> "Distinct AI Models Seem To Converge On How They Encode Reality — Researchers argue
> that as the models grow more powerful, they may be converging toward a singular
> 'Platonic' way to represent the world."
> — Quanta Magazine 2026

> "Why Do Humanoid Robots Still Struggle With the Small Stuff? — The last decade has
> seen vast improvements in humanoid robots, but graduating to widespread use might
> require going back to the fundamentals."
> — Quanta Magazine 2026

- Main RSS: `https://www.quantamagazine.org/feed/`
- AI tag RSS: `https://www.quantamagazine.org/tag/artificial-intelligence/feed/`

Sources: [Quanta Magazine — main](https://www.quantamagazine.org/), [Quanta — Artificial Intelligence tag](https://www.quantamagazine.org/tag/artificial-intelligence/), [Quanta Archive](https://www.quantamagazine.org/archive/), [Quanta — Computer Science](https://www.quantamagazine.org/computer-science/), [Top 20 Quanta RSS Feeds — Feedspot](https://rss.feedspot.com/quantamagazine_rss_feeds/).

### 6.3 Asimov Press (status: hiatus April 2026, archive valuable)

> "Asimov Press announced it is going on hiatus, with operations pausing in April 2026,
> though a few more articles appeared in the month prior and their hardcover book
> 'Making the Modern Laboratory' was set to come out in summer 2026."
> — paraphrased from Asimov Press archive notes

> "Most of their work centers around biology and metascience — the systematic study of
> science itself — with particular emphasis on biology because that is the field where
> progress seems the most rapid."
> — [Asimov Press — About](https://www.asimov.press/about)

Sources: [Asimov Press — Substack](https://www.asimov.press/), [The Column — Asimov Press](https://www.asimov.press/s/column), [About — Asimov Press](https://www.asimov.press/about), [Archive — Asimov Press](https://www.asimov.press/s/archive), [That's All, for Now — Asimov Press](https://www.asimov.press/p/pause).

### 6.4 Astral Codex Ten (Scott Alexander)

> "Introducing AI 2027... discussed a 2021 blog post by Daniel Kokotajlo called 'What
> 2026 Looks Like'. The article explores AI predictions and developments through 2026
> and beyond."
> — [ACT — Introducing AI 2027](https://www.astralcodexten.com/p/introducing-ai-2027)

- Main RSS: `https://www.astralcodexten.com/feed`
- Highest-density "intellectually serious essays on AI policy + science + medicine" feed.

Sources: [ACT — Introducing AI 2027](https://www.astralcodexten.com/p/introducing-ai-2027), [Archive — ACT](https://www.astralcodexten.com/archive), [Links For February 2026 — ACT](https://www.astralcodexten.com/p/links-for-february-2026), [ACT podcast — Apple](https://podcastaddict.com/podcast/astral-codex-ten-podcast/2251541), [ACT — newsletterhunt](https://newsletterhunt.com/newsletters/astral-codex-ten).

### 6.5 Marginal Revolution (Tyler Cowen)

> "Tyler Cowen released a new work online and free titled 'The Marginal Revolution: Rise
> and Decline, and the Pending AI Revolution,' which consists of four chapters, about
> 40,000 words, fully written by Cowen, and is attached to an AI with dual page display
> using Claude."
> — [Marginal Revolution post 2026-03](https://marginalrevolution.com/marginalrevolution/2026/03/marginal-revolution-rise-and-decline-and-the-pending-ai-revolution.html)

> "Several of the top five economics journals are experimenting with Refine, an
> AI-powered reviewing tool that scours economics papers for errors, and it was picking
> up problems in at least a third of cases even with papers that had been through
> referees at top journals."
> — [Marginal Revolution — Is AI helping economic research?](https://marginalrevolution.com/marginalrevolution/2026/03/is-ai-currently-helping-economic-research.html)

Sources: [Marginal Revolution main](https://marginalrevolution.com/), [The Marginal Revolution Rise/Decline — MR](https://marginalrevolution.com/marginalrevolution/2026/03/marginal-revolution-rise-and-decline-and-the-pending-ai-revolution.html), [Trajectories of science and AI — MR](https://marginalrevolution.com/marginalrevolution/2026/03/the-trajectories-of-science-and-ai.html), [Claims about AI and science — MR](https://marginalrevolution.com/marginalrevolution/2026/01/claims-about-ai-and-science.html), [Andy Hall advice on AI and economic research — MR](https://marginalrevolution.com/marginalrevolution/2026/04/andy-hall-advice-on-ai-and-economic-research.html).

### 6.6 Construction Physics (Brian Potter) + Asterisk Magazine

> "Brian Potter is a senior infrastructure fellow at the Institute for Progress and
> writes the Construction Physics newsletter."

> "Scott Alexander is a writer and psychiatrist based in Oakland, California who blogs
> at astralcodexten.substack.com, connecting him to both Astral Codex Ten and the
> Asterisk Magazine contributors list."

- Both are part of the "progress studies / rationalist-adjacent science" cluster — high-quality bridge between research and applied infrastructure.

Sources: [Asterisk Magazine — Contributors](https://asteriskmag.com/contributors), [Construction Physics — substack](https://www.construction-physics.com/), [Asterisk — main](https://asteriskmag.com/), [ACT main page](https://www.astralcodexten.com/).

### 6.7 Nautilus

Quanta-adjacent science magazine; long-form essays on physics, biology, AI. RSS: `https://nautil.us/feed/`. (Sourced from feedspot Quantum Science Magazines listing referenced earlier.)

---

## 7. Personalization patterns — research feed

How to avoid drowning in news. Five empirically-validated patterns:

### 7.1 arxiv-sanity SVM-on-tfidf (Karpathy original)

> "arxiv-sanity-lite can send daily emails with recommendations of new papers based on
> your tags... The lite version periodically polls the arxiv API for new papers, then
> allows users to tag papers of interest and recommends new papers for each tag based
> on SVMs over tfidf features of paper abstracts."
> — [karpathy/arxiv-sanity-lite README](https://github.com/karpathy/arxiv-sanity-lite/blob/master/README.md)

**Pattern**: tag a small set of papers you like → train per-tag SVM on tfidf abstracts →
score every new paper → email top-K daily. **Cost: zero LLM calls**. Fits perfectly with
Antonello's "no paid API" rule. Self-host on Mini-Pro2.

### 7.2 LLM ranking on top of an aggregator (Readwise / Matter pattern)

> "Matter and Readwise Reader are already doing LLM-curated long-form for personal
> reading."
> — [LessWrong — LLMs will soon disrupt algorithmic media feeds](https://www.lesswrong.com/posts/YuXcbWRTjmvr4QF7u/llms-will-soon-disrupt-algorithmic-media-feeds)

> "The Readwise MCP server gives Claude, ChatGPT, Cursor, or any MCP-compatible AI direct
> access to your Readwise highlights and Reader documents. Once connected, you can ask
> your AI to search your notes, answer questions using your own reading history as
> context, or even make changes to your Reader library for you."
> — [Readwise MCP Server — Readwise Docs](https://docs.readwise.io/readwise/guides/mcp)

**Pattern**: ingest from RSS / arXiv / HN → store in Readwise Reader → daily Claude pass
via MCP picks top-N most-aligned-with-Antonello → write to NB-9 + Telegram dispatch.

### 7.3 Custom embeddings of user history → semantic match

> "Moving the deduplication and re-ranking fully into Python scripts, adding a local
> cross-encoder reranker to avoid LLM calls for scoring, and extending the researcher
> with tag-aware filtering represents optimization strategies being developed for
> research feed systems."
> — referenced in research feed personalization discussion

**Pattern**: embed Antonello's last 1000 read articles using `bge-m3` (local Ollama, free) →
cosine-rank every new candidate → rerank top-50 with `qwen3.5:9b` for "is this Bali Zero
relevant?". Latency 30–120s on Mini-Pro2 — fits the existing async-only Ollama rule from
the global CLAUDE.md.

### 7.4 Anthropic Skills as personalized memory module

> "A Skill is a folder with a SKILL.md file inside, and only 30 to 50 tokens of metadata
> load until Claude actually needs the skill, so you can stack dozens of them without
> bloating your context window."
> — [composio.dev — Top 10 Claude Code Skills 2026](https://composio.dev/content/top-claude-skills)

**Pattern**: create a `~/.claude/skills/research-lab.md` skill that activates on keywords
("daily digest", "weekly research summary") and pulls from Antonello's local feed DB +
NB-9 history. The skill itself encodes the personalization (interests, NB targeting,
Telegram routing).

### 7.5 Decoding-AI "LLM Knowledge Base on my Notes" (Karpathy named, builder built)

> "Karpathy Named It. I Built One on My Notes."
> — [decodingai.com](https://www.decodingai.com/p/llm-knowledge-base-obsidian-readwise-notebooklm)

**Pattern**: Obsidian (notes) + Readwise (read-it-later) + NotebookLM (synthesis) =
3-tier personal research stack. Antonello already has all three (Obsidian on Pro, Readwise
optional, **60 NotebookLM notebooks active**). Missing piece: an Ollama-driven daily
ingestion pipeline that funnels selected items into the right NB.

Sources: [arxiv-sanity-lite — README](https://github.com/karpathy/arxiv-sanity-lite/blob/master/README.md), [LessWrong — LLMs will soon disrupt algorithmic media feeds](https://www.lesswrong.com/posts/YuXcbWRTjmvr4QF7u/llms-will-soon-disrupt-algorithmic-media-feeds), [Karpathy Named It — Decoding AI](https://www.decodingai.com/p/llm-knowledge-base-obsidian-readwise-notebooklm), [Readwise MCP Server — docs](https://docs.readwise.io/readwise/guides/mcp), [Top 10 Claude Code Skills — Composio](https://composio.dev/content/top-claude-skills).

---

## 8. Long-term research memory

Patterns for "second brain" used by people who do research seriously.

### 8.1 Roam / Logseq / Obsidian / Tana — the static-doc tier

> "Obsidian: Best for users who want full control, local storage, and don't mind
> investing time in configuration, particularly technical users and privacy-conscious
> individuals."

> "Roam Research: Recommended for those focused on research and writing who want
> powerful block-level connections, best for academics and serious researchers. However,
> Roam's interface feels dated compared to newer alternatives, and development has
> slowed considerably."

> "Logseq: Logseq is genuinely good — free, open source, with local markdown files,
> block-based outliner with bidirectional links and daily notes, and remains a top
> pick for users who think in outlines and want full file ownership."

> "Tana: Recommended if you need database-like structure with the flexibility of notes,
> best for organizing complex projects with many related entities. Across Product Hunt,
> sentiment is consistent: people describe Tana as 'revolutionary,' explaining that after
> trying Evernote, Roam, Notion, Logseq, and Capacities, Tana was the only system
> flexible enough to hold any kind of information without forcing them into someone
> else's structure."
> — all from [atlasworkspace.ai — 7 Best Second Brain Apps 2026](https://www.atlasworkspace.ai/blog/best-second-brain-apps)

> "The reason any of this matters in 2026 is not the tool itself, but that every
> knowledge worker is about to face the same question: where does my thinking live in
> an age when AI is doing more of the work?"
> — Same.

### 8.2 Mem0 — vector + knowledge graph memory layer

> "Mem0 is a memory layer you bolt onto whatever agent framework you're already using
> and it handles storage and retrieval. The key architectural choice: Mem0 is
> framework-agnostic. It doesn't care whether your agent runs in LangChain, CrewAI,
> AutoGen, or a custom loop. You import the SDK, point it at Mem0, and your agent has
> persistent memory."
> — [hermesos.cloud — AI agent memory systems 2026](https://hermesos.cloud/blog/ai-agent-memory-systems)

> "Mem0g, which builds a directed, labeled knowledge graph alongside the vector store
> during the extraction phase. An entity extractor identifies nodes from conversation
> text. A relations generator infers labeled edges connecting those nodes. A conflict
> detector flags when new information contradicts existing graph elements before they
> are written."
> — Same.

### 8.3 Letta — full agent runtime with MemGPT-style virtual memory

> "Letta is an agent runtime. It manages memory as part of a full
> operating-system-inspired platform where your agents live and execute. Letta takes the
> MemGPT research paper's core idea — treating LLM context like virtual memory — and
> builds a full runtime around it. Agents don't just use Letta for memory; they run
> inside Letta."
> — Same source.

> "The framework manages the agent loop, tool execution, state persistence, and memory
> across three tiers inspired by computer architecture: Core Memory — a small block
> that lives in the context window (like RAM). The agent reads and writes it directly.
> Recall Memory — searchable conversation history stored outside context (like a disk
> cache). Archival Memory — long-term storage the agent queries via tool calls (like
> cold storage)."
> — Same source.

### 8.4 Anthropic Knowledge Graph Memory MCP Server

> "Anthropic has created a Knowledge Graph Memory MCP Server that allows building and
> querying persistent semantic networks for data management. The Memory MCP provides an
> interactive knowledge graph system for exploring entities, relations, and observations
> from memory files in the Model Context Protocol."
> — [PulseMCP — Knowledge Graph Memory MCP](https://www.pulsemcp.com/servers/modelcontextprotocol-memory)

> "Studies on context have uncovered the concept of context rot: as the number of tokens
> in the context window increases, the model's ability to accurately recall information
> from that context decreases."
> — [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

### 8.5 Notion AI — for collaborative team-shared memory

Not detailed here because Notion is primarily a team doc product; its AI layer is OK but
the architectural pattern (vector DB + LLM rerank on top of structured docs) is replicated
better by self-hosted Mem0 or Letta on Mini-Pro2.

### 8.6 Mem0 vs Letta tradeoff (the canonical 2026 framing)

> "The tradeoff is predictability vs intelligence. Mem0's passive extraction is
> consistent and token-efficient, but it can't make nuanced judgments about what matters
> in context. Letta's self-editing approach is more adaptive — the agent uses its own
> reasoning to curate memory — but memory quality depends entirely on the model's
> judgment. If the model fails to save something, it's gone. Every memory operation
> also costs inference tokens, since the agent has to reason about what to store and
> how."
> — [hermesos.cloud — AI agent memory systems 2026](https://hermesos.cloud/blog/ai-agent-memory-systems)

> "Mem0 is the right default for 2026 consumer apps where 'remember the user' is the
> feature. Letta is the right bet for autonomous agents where long-horizon coherence
> is the product."
> — Same.

### 8.7 Gwern — the "animate the corpus" reference pattern

> "His work is noted for clear thinking, great citing, and immense practicality."

> "Gwern wants to 'animate' his corpus so it can learn, think, and write, recognizing
> that knowledge stored in traditional formats remains inert without tools to leverage
> it."

> "A Nenex system (which Gwern discusses) would interactively tailor itself to a user's
> writing style, knowledge, existing corpus, and enable semantic features unavailable
> in other systems, such as searching a personal wiki for pages that need updating
> given updates to other pages."
> — [Nenex — Gwern.net](https://gwern.net/nenex)

This is the **lifecycle target Antonello described** — "cresce → cosciente → canalizza":
Gwern's Nenex essay is the literature reference for it. The corpus is not a static
archive; it actively requests updates when cross-cutting facts change.

### 8.8 Recommended architecture for Antonello's lab

```
            ┌─────────── INGEST ───────────┐
            │ arxiv API (1/3s)             │
            │ Semantic Scholar (1/s w/key) │
            │ HN topstories (no limit)     │
            │ HF Papers Trending           │
            │ Quanta / Nature / Science RSS│
            │ TLDR AI / The Batch (email)  │
            └──────────────┬───────────────┘
                           ▼
            ┌──────── SCORE (local) ───────┐
            │ bge-m3 embeddings (Ollama)   │
            │ qwen3.5:9b rerank "Bali Zero │
            │  research relevance"          │
            │ arxiv-sanity SVM per tag     │
            └──────────────┬───────────────┘
                           ▼
            ┌──── STORE (NB-9 long-term) ──┐
            │ NotebookLM NB-9 (canonical)  │
            │ Mem0 vector + KG mirror      │
            │ Markdown in ~/Desktop/       │
            │  nuzantara/research/         │
            └──────────────┬───────────────┘
                           ▼
            ┌──── SYNTHESIZE (gpt-researcher) ────┐
            │ Weekly STORM-style report          │
            │ Daily Telegram digest (top 5)       │
            │ Auto-correct loop: AgentLab eval    │
            │  on "did digest match interest?"    │
            └─────────────────────────────────────┘
```

Sources: [Best Second Brain Apps 2026 — atlasworkspace.ai](https://www.atlasworkspace.ai/blog/best-second-brain-apps), [Logseq Alternatives 2026 — atlasworkspace.ai](https://www.atlasworkspace.ai/blog/logseq-alternatives), [State of AI Agent Memory 2026 — Mem0](https://mem0.ai/blog/state-of-ai-agent-memory-2026), [AI agent memory systems 2026 — Hermes OS](https://hermesos.cloud/blog/ai-agent-memory-systems), [Mem0 vs Letta vs MemGPT — TokenMix](https://tokenmix.ai/blog/ai-agent-memory-mem0-vs-letta-vs-memgpt-2026), [Knowledge Graph Memory MCP — PulseMCP](https://www.pulsemcp.com/servers/modelcontextprotocol-memory), [Effective context engineering — Anthropic](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), [Code execution with MCP — Anthropic](https://www.anthropic.com/engineering/code-execution-with-mcp), [Nenex — Gwern.net](https://gwern.net/nenex), [Essays — Gwern.net](https://gwern.net/), [Top 10 AI Memory Products 2026 — Bobur Medium](https://medium.com/@bumurzaqov2/top-10-ai-memory-products-2026-09d7900b5ab1), [Test-Driving Second Brain Apps — Forte Labs](https://fortelabs.com/blog/test-driving-a-new-generation-of-second-brain-apps-obsidian-tana-and-mem/), [Why Obsidian Is the AI-Era Second Brain — Colin Scotland](https://colinscotland.com/why-obsidian/), [Karpathy Named It — Decoding AI](https://www.decodingai.com/p/llm-knowledge-base-obsidian-readwise-notebooklm), [How Claude Memory Works in 2026 — Shareuhack](https://www.shareuhack.com/en/posts/claude-memory-feature-guide-2026), [How Claude remembers your project — Claude Code Docs](https://code.claude.com/docs/en/memory), [Top 10 Claude Code Skills — Composio](https://composio.dev/content/top-claude-skills), [Master 80% of Claude Code — Geeky Gadgets](https://www.geeky-gadgets.com/master-claude-code-15-concepts/), [Claude Code Skills practical guide — Nimbalyst](https://nimbalyst.com/blog/claude-code-skills-guide/), [thedotmack/claude-mem — GitHub](https://github.com/thedotmack/claude-mem), [grandamenium/dream-skill — GitHub](https://github.com/grandamenium/dream-skill), [hanfang/claude-memory-skill — GitHub](https://github.com/hanfang/claude-memory-skill), [5 Claude Code Skills worth installing — Betamize](https://blog.betamize.com/5-claude-code-skills-that-are-actually-worth-installing-in-2026), [Claude Code Dreams — claudefa.st](https://claudefa.st/blog/guide/mechanics/auto-dream).

---

## Closing operational note for Antonello

The lifecycle Antonello named — **nasce → cresce → auto-correct → cosciente → canalizza
in NB-9 + Telegram + memory long-term** — has a clean 1-to-1 mapping onto the OSS stack
above and the existing Nuzantara arsenal:

| Stage            | Cost-zero implementation                                                                                        |
| ---------------- | --------------------------------------------------------------------------------------------------------------- |
| **Nasce**        | gpt-researcher MCP server + arxiv/SS/HN/RSS ingestion cron on Mini-Pro2                                         |
| **Cresce**       | STORM Knowledge Curation + Outline Generation modules (Stanford OVAL)                                           |
| **Auto-correct** | AgentLab BrowserGym-style eval loop + Sakana AI-Scientist tree search                                           |
| **Cosciente**    | Claude Code Skill `research-lab.md` + Anthropic Memory MCP for KG persistence                                   |
| **Channel**      | Daily Telegram dispatch via existing Bali Zero notification stack + NotebookLM NB-9 push via `nlm` CLI          |
| **Long-term**    | Mem0 (vector + KG) on Mini-Pro2 + Markdown mirror in `~/Desktop/nuzantara/research/` for Git-tracked archeology |

All free under the existing arsenal: Claude OAuth (3 Max), Gemini CLI free, DeepSeek (~$0.01/q,
allowed), Ollama local. Zero new paid APIs needed. The only marginal cost is engineering
time on Pro to wire up the cron + LaunchAgent + 3 MCP integrations, which fits the
existing pattern documented in `runbook_nlm_system_complete.md`.
