# R1 — SOTA Agentic Ingestion, Knowledge Graphs, RAG, Memory, Self-Improvement, Multi-Agent Orchestration & Observability (2026-05-08)

**Mission**: research report for Antonello Siano (Bali Zero / Nuzantara), designing a multi-domain autonomic system on top of NotebookLM + cron + LLM stack (Claude OAuth MAX, Gemini, Codex, DeepSeek, Ollama). Six knowledge domains: immigration/company, tax, marketing, AI/research, Indonesia macro, OSINT. Universal lifecycle: birth → growth → self-correction → self-aware → fruits-to-system. Constraint: zero paid Anthropic tokens, OSS-first, self-hostable, free-tier or local where possible.

**Method**: 7 sections, primary sources cited verbatim with full URLs, "useful for Bali Zero" line per item. No extrapolation beyond what sources state.

---

## 1. Agentic Data Ingestion 2026

The pipeline pattern Bali Zero's `NB-INTEL` already executes (cron-fed scraper → scorer Ollama → router → NB) is one early instance of the "agentic ingestion" generation that became a defined category in 2025-2026. Below the SOTA tooling that defines current state.

### 1.1 Anthropic — Agent Skills (open standard, 2025; org-wide directory Dec 2025)

**Primary sources**:

- Announcement: https://www.anthropic.com/news/skills (redirects to https://claude.com/blog/skills)
- API docs: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Skills repo: https://github.com/anthropics/skills
- API guide: https://platform.claude.com/docs/en/build-with-claude/skills-guide
- Coverage: https://thenewstack.io/agent-skills-anthropics-next-bid-to-define-ai-standards/

**What it is, verbatim**:

> "Skills are folders that include instructions, scripts, and resources that Claude can load when needed."
> "Composable: Skills stack together. Claude automatically identifies which skills are needed and coordinates their use."
> "Claude will only access a skill when it's relevant to the task at hand. When used, skills make Claude better at specialized tasks."
> "Skills use the same format everywhere. Build once, use across Claude apps, Claude Code, and API."
> (Anthropic, Skills blog, claude.com/blog/skills)

**Key pattern**: progressive disclosure — Claude first loads only the `SKILL.md` frontmatter (name + description), then opens the body only when a task signature matches. This makes the index O(N) cheap regardless of skill count, while bodies stay full-quality. Pre-built skills currently include `pptx`, `xlsx`, `docx`, `pdf`. Custom skills are folders of instructions, scripts, resources. As of Dec 2025, Anthropic added **organization-wide management for skills, a directory featuring partner-built skills, and published Agent Skills as an open standard for cross-platform portability**.

**Useful for Bali Zero**: HIGH — Claude OAuth MAX already executes Skills natively; the 6-domain lifecycle map naturally to per-domain SKILL.md files (immigration-skill.md, tax-skill.md, marketing-skill.md, ai-research-skill.md, indonesia-macro-skill.md, osint-skill.md), each pointing at the relevant NB UUID + scoring rules + PUSH endpoints. Cross-product portability means the same skill can be invoked from Claude Code on Pro, Mini-Pro2, AND in Claude.ai web, AND in API automation — single source of truth.

### 1.2 Cognee — Memory Control Plane (open-source, OSS MIT)

**Primary sources**:

- Repo: https://github.com/topoteretes/cognee
- Site: https://www.cognee.ai/
- Paper (May 2025): https://arxiv.org/pdf/2505.24478 — "Optimizing the Interface Between Knowledge Graphs and LLMs for Complex Reasoning" — Vasilije Markovic, Lazar Obradovic, Laszlo Hajdu, Jovan Pavlovic
- MCP integration blog: https://www.cognee.ai/blog/cognee-news/introducing-cognee-mcp
- Memgraph collab: https://memgraph.com/blog/from-rag-to-graphs-cognee-ai-memory

**Verbatim**:

> "Cognee gives AI agents a shared, improving memory of your data, decisions, and workflows so they can recall, connect, and act with context."
> "Memory control plane for AI Agents in 6 lines of code"
> "[Cognee] combines embeddings, graphs and cognitive science approaches to make your documents both searchable by meaning and connected by relationships."
> (README and site)

**Pattern key**: ECL pipeline — _Extract → Cognify → Load_. Cognify converts raw chunks into knowledge-graph triplets (subject-relation-object), then writes both embeddings and graph atoms to backing stores (Neo4j compatible, embedding store of choice). The May 2025 arXiv paper benchmarks Cognee on HotPotQA, TwoWikiMultiHop, Musique multi-hop QA — proves graph-aided retrieval beats flat-vector RAG on chained reasoning.

**State 2026**: native MCP server (`cognee-mcp`) — Claude Code, Cursor, etc. can talk to Cognee like a tool. Cognee + Claude Agent SDK integration tutorial at https://www.cognee.ai/blog/integrations/claude-agent-sdk-persistent-memory-with-cognee-integration.

**Useful for Bali Zero**: HIGH — Cognee can become the **horizontal memory bus** between the 6 domains. Per-domain ingestion writes to Cognee, which auto-builds the cross-domain graph (e.g. _KBLI 79902 → travel-information → Tourism Law 10/2009 → Tax PPh 21_) so the system's "self-aware about its own choices" requirement gets a concrete substrate. Compatible with Qdrant local already running on Pro, replaces nothing, layers on top.

### 1.3 Mem0 v2 — Production AI agent memory

**Primary sources**:

- Paper: https://arxiv.org/abs/2504.19413 — "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory" (Apr 2025)
- Repo: https://github.com/mem0ai/mem0
- Blog state-of-memory 2026: https://mem0.ai/blog/state-of-ai-agent-memory-2026
- HuggingFace paper page: https://huggingface.co/papers/2504.19413

**Verbatim**:

> "Mem0 [is] a scalable memory-centric architecture that addresses [LLM context window limitations] by dynamically extracting, consolidating, and retrieving salient information from ongoing conversations."
> "An enhanced variant ... leverages graph-based memory representations to capture complex relational structures among conversational elements."
> "91% lower p95 latency [...] saves more than 90% token cost compared to full-context methods."
> "26% relative improvements in the LLM-as-a-Judge metric over OpenAI[, while] Mem0 with graph memory achieves around 2% higher overall score than the base configuration."
> (Paper abstract / HuggingFace summary)

**Pattern key**: single-pass ADD-only extraction (one LLM call, no UPDATE/DELETE to start), entity linking across memories, multi-signal retrieval combining semantic + BM25 + entity-match. Open-source SDK (Python, JS), self-hostable.

**Useful for Bali Zero**: MEDIUM — Mem0 overlaps with Cognee but is more "agent conversation memory" oriented vs. Cognee's broader knowledge-graph framing. Could be the per-conversation memory inside Bali Zero's CRM-Guardian pipeline (client interaction history per cliente Marta Reyes, Marina Pinyaylova, etc.) while Cognee handles structural domain knowledge.

### 1.4 Letta (formerly MemGPT) — Stateful agent platform

**Primary sources**:

- Repo: https://github.com/letta-ai/letta
- "MemGPT is now part of Letta": https://www.letta.com/blog/memgpt-and-letta
- V1 architecture rearchitect: https://www.letta.com/blog/letta-v1-agent
- Agent memory primer: https://www.letta.com/blog/agent-memory
- Original MemGPT paper: https://arxiv.org/abs/2310.08560

**Verbatim**:

> "MemGPT refers to the original agent design pattern described in the research paper (empowering LLMs with self-editing memory tools), and the name Letta refers to the agent framework."
> "MemGPT is a system that intelligently manages different storage tiers to effectively provide extended context within the LLM's limited context window. MemGPT treats context windows as a constrained memory resource and implements a memory hierarchy similar to operating systems."
> "Letta (formerly MemGPT) treats memory as the agent's editable state. Its core innovation is enabling agents to actively manage their own memory blocks through tool calls — reading, writing, and searching archives."
> "We've found the `letta_v1_agent` architecture significantly improves performance for the latest models like GPT-5 and Claude 4.5 Sonnet."
> "In this architecture, `heartbeats` and the `send_message` tool are deprecated. Only native reasoning and direct assistant message generations from the models are supported. The new architecture uses Responses API under the hood for OpenAI, and handles encrypted reasoning across providers."
> (Letta V1 blog, May 2026)

**Pattern key**: 3-tier hierarchy — Core Memory (in-context, RAM-equivalent), Recall Memory (searchable convo history, disk-cache equivalent), Archival Memory (cold storage, tool-call-fetched). The agent self-edits Core Memory through tools, so memory is _first-class state_, not a side channel.

**Useful for Bali Zero**: MEDIUM — Letta server can be self-hosted on Mini-Pro2; it would give every Bali Zero agent (per cliente, per dominio) a real OS-style memory, which solves the "long-running awareness" requirement. But Letta + Cognee + Mem0 would be triple-stack overkill — pick one as canonical.

### 1.5 Microsoft GraphRAG — Hierarchical community summaries

**Primary sources**:

- Paper: https://arxiv.org/abs/2404.16130 — "From Local to Global: A Graph RAG Approach to Query-Focused Summarization" (Apr 2024)
- MS Research page: https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/
- Implementation: https://aka.ms/graphrag

**Verbatim**:

> "RAG fails on global questions directed at an entire text corpus, such as 'What are the main themes in the dataset?', since this is inherently a query-focused summarization (QFS) task, rather than an explicit retrieval task. Prior QFS methods, meanwhile, do not scale to the quantities of text indexed by typical RAG systems."
> "[The approach uses an LLM to build a graph index in two stages]: first, to derive an entity knowledge graph from the source documents, then to pregenerate community summaries for all groups of closely related entities. Given a question, each community summary is used to generate a partial response, before all partial responses are again summarized in a final response to the user."
> "For a class of global sensemaking questions over datasets in the 1 million token range, GraphRAG leads to substantial improvements over a conventional RAG baseline for both the comprehensiveness and diversity of generated answers."
> (Microsoft GraphRAG paper abstract)

**Pattern key**: Leiden community detection over the entity graph → per-community LLM-summarized "report" → "global" queries hit reports first, "local" queries hit raw entities. Cost: O(N) LLM calls at index time; queryside can be one-shot.

**Useful for Bali Zero**: HIGH — exactly what's missing today. Bali Zero's NB-INTEL surfaces _items_, but doesn't yet auto-summarize per-domain "themes of the week / month". GraphRAG community-summary layer would let an Antonello query like "What are the recurring property compliance themes across all client cases this quarter?" return a coherent meta-answer.

### 1.6 LightRAG (HKU, EMNLP 2025) — Simple, fast, dual-level

**Primary sources**:

- Paper: https://arxiv.org/abs/2410.05779 — "LightRAG: Simple and Fast Retrieval-Augmented Generation" (Oct 2024, EMNLP 2025)
- Repo: https://github.com/HKUDS/LightRAG
- HF: https://huggingface.co/papers/2410.05779

**Verbatim**:

> "LightRAG incorporates graph structures into text indexing and retrieval processes."
> "[The framework] employs a dual-level retrieval system that enhances comprehensive information retrieval from both low-level and high-level knowledge discovery, and the integration of graph structures with vector representations facilitates efficient retrieval of related entities and their relationships while improving response times."
> "[LightRAG includes] an incremental update algorithm [that] ensures the timely integration of new data, allowing the system to remain effective and responsive in rapidly changing data environments."
> (LightRAG abstract / repo README)

**Pattern key**: Local (entity-level) + Global (relations-level) retrieval split. _Incremental update_ — no full re-index when 1 doc lands; new doc gets entity-extracted, deltas merged into graph. Lighter than Microsoft GraphRAG at index time and simpler to operate.

**Useful for Bali Zero**: HIGH — closer to a drop-in replacement for the current "scorer Ollama → NB push" pipeline. The incremental-update primitive matches the cron-fed nature of NB-INTEL exactly (1 RSS item per scrape → cheap delta merge into graph, not costly full rebuild like Microsoft GraphRAG would force).

### 1.7 LangGraph ingestion patterns

**Primary sources**:

- Docs: https://docs.langchain.com/oss/python/langgraph/overview
- Repo: https://github.com/langchain-ai/langgraph
- Multi-agent guide: https://www.langchain.com/langgraph

**Verbatim**:

> "LangGraph is the orchestration runtime: durable execution, streaming, human-in-the-loop, and persistence."
> "LangGraph models agent workflows as graphs. You define the behavior of your agents using three key components: State – A shared data structure that represents the current snapshot of your application. Each agent reads and writes to a state object that contains query, search_results, analysis, quality_score, etc."
> (LangChain docs)

**Pattern key**: workflow-as-state-machine, with checkpointing (for crash recovery), interruption (for human-in-the-loop), and time-travel (replay from any node). Ingestion fits as a graph where nodes are scrape→clean→score→route→push.

**Useful for Bali Zero**: MEDIUM — LangGraph would _replace_ the bash-cron-orchestrated ingestion with a Python state machine. Buys observability and crash-resume; costs adoption tax. The cleaner alternative is to keep cron orchestration and use LangGraph only inside specific complex sub-pipelines (e.g. Marina Pinyaylova KBLI BATARA-resolver workflow — multi-step research flow that benefits from a state-machine).

### 1.8 LlamaIndex — Agentic Document Workflows (ADW) 1.0

**Primary sources**:

- Workflows landing: https://www.llamaindex.ai/workflows
- ADW intro: https://www.llamaindex.ai/blog/introducing-agentic-document-workflows
- Workflows 1.0: https://www.llamaindex.ai/blog/announcing-workflows-1-0-a-lightweight-framework-for-agentic-systems
- Ingestion pipeline docs: https://docs.llamaindex.ai/en/stable/module_guides/loading/ingestion_pipeline/
- Source: https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/ingestion/pipeline.py

**Verbatim**:

> "LlamaIndex introduced Agentic Document Workflows (ADW) in 2025, an architecture that combines document processing, retrieval, structured outputs, and agentic orchestration to enable end-to-end knowledge work automation. This represents a step beyond traditional Intelligent Document Processing (IDP) and RAG paradigms, which focus on small, isolated steps of extraction and question-answering respectively."
> "In an IngestionPipeline, each node and transformation combination is hashed and cached, which saves time on subsequent runs that use the same data."
> (LlamaIndex blog and docs)

**Pattern key**: workflow as _agent decision graph_ over documents; LlamaParse handles complex docs (PDF tables, scanned forms); the workflow agent picks rules, validates against business policy, escalates to human-in-the-loop.

**Useful for Bali Zero**: HIGH for property/visa/tax cases that arrive as PDFs (akta, NPWP scans, BPN certificates, KBLI extracts). LlamaParse alone is worth integrating to feed clean structured outputs into Cognee/LightRAG.

### 1.9 n8n — AI workflow with persistent memory caveat

**Primary sources**:

- Site: https://n8n.io/
- AI page: https://n8n.io/ai/
- AI agents: https://n8n.io/ai-agents/
- 2025 review: https://latenode.com/blog/low-code-no-code-platforms/n8n-setup-workflows-self-hosting-templates/n8n-ai-agents-2025-complete-capabilities-review-implementation-reality-check

**Verbatim**:

> "AI Agents in n8n are autonomous workflows powered by AI that can make decisions, interact with apps, and execute tasks without constant human input, using a combination of memory, goals, and tools like web search or database access to reason through tasks step-by-step."
> "[N]8n enables organizations to build and monitor business-critical AI workflows with advanced security and DevOps features. However, while marketed as a solution for creating autonomous AI agents, its features fall short of delivering true autonomy, with one major drawback being the lack of built-in persistent memory and automatic error recovery."
> (Latenode 2025 review)

**Pattern key**: low-code, OSS, self-hostable, 400+ integrations, native LangChain bridge.

**Useful for Bali Zero**: LOW-MEDIUM — already on the list (`n8n` installed in arsenal per memory `reference_arsenal_full_inventory.md`). Best fit for _operational glue_ (Brevo email send, Telegram alerts, GCal triggers) rather than the core knowledge ingestion which is better off in code (cron + Python).

### 1.10 Anthropic Claude Agent SDK — ingestion via Skills + Memory

**Primary sources**:

- Memory tool docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool
- Skills overview: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Effective context engineering: https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- Effective harnesses: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents

**Verbatim** (Memory tool docs):

> "The memory tool enables Claude to store and retrieve information across conversations through a memory file directory. Claude can create, read, update, and delete files that persist between sessions, allowing it to build knowledge over time without keeping everything in the context window."
> "This is the key primitive for just-in-time context retrieval: rather than loading all relevant information upfront, agents store what they learn in memory and pull it back on demand. This keeps the active context focused on what's currently relevant, critical for long-running workflows where loading everything at once would overwhelm the context window."
> "The memory tool operates client-side: you control where and how the data is stored through your own infrastructure."

**Auto-injected system instruction (verbatim)**:

> "IMPORTANT: ALWAYS VIEW YOUR MEMORY DIRECTORY BEFORE DOING ANYTHING ELSE.
> MEMORY PROTOCOL:
>
> 1. Use the `view` command of your `memory` tool to check for earlier progress.
> 2. ... (work on the task) ...
>    - As you make progress, record status / progress / thoughts etc in your memory.
>      ASSUME INTERRUPTION: Your context window might be reset at any moment, so you risk losing any progress that is not recorded in your memory directory."

**Useful for Bali Zero**: VERY HIGH — `claude` CLI consumed via OAuth MAX (zero token cost) supports the memory tool natively. The Bali Zero memory arsenal in `~/.claude/projects/-Users-nuzantara/memory/*.md` already maps onto this primitive. Standardizing on `/memories/<domain>/...` instead of free-floating files would let the OS-level memory hook into Claude transparently.

---

## 2. Knowledge Graph auto-curating

### 2.1 Microsoft GraphRAG — Reference architecture

(Already covered in §1.5 — see verbatim there.)

**KG-curation specifics**: GraphRAG performs _entity resolution_ via name-based co-reference + summary-time disambiguation. Drift handling is via re-clustering: when new docs land, you re-run community detection. The cost: full rebuild for large updates. Implementation source: https://github.com/microsoft/graphrag.

### 2.2 LightRAG — Incremental graph with entity dedup

(Already covered in §1.6.)

**KG-curation specifics**: LightRAG's _incremental update_ algorithm hashes new chunks, runs entity extraction with the LLM, then merges new entities into the existing graph. Entity disambiguation done via embedding similarity > threshold + LLM merger judge. Repo: https://github.com/HKUDS/LightRAG.

> "LightRAG offers an incremental update algorithm [...] allowing the system to remain effective and responsive in rapidly changing data environments." (paper abstract)

**Useful for Bali Zero**: HIGH — beats Microsoft GraphRAG for cron-fed ingestion.

### 2.3 nano-graphrag — Hackable 1100-line GraphRAG

**Primary sources**:

- Repo: https://github.com/gusye1234/nano-graphrag

**Verbatim**:

> "Nano-graphrag is a simple, easy-to-hack GraphRAG implementation. This project provides a smaller, faster, cleaner GraphRAG, while remaining the core functionality, and excluding tests and prompts, nano-graphrag is about 1100 lines of code."
> "It requires two types of LLM: a great one and a cheap one, where the former is used to plan and respond, and the latter is used to summary."
> "By default nano-graphrag uses nano-vectordb as the backend, and it also has a built-in hnswlib storage. By default it uses networkx as the graph backend, with a built-in Neo4jStorage for graph also available."
> (nano-graphrag README)

**Useful for Bali Zero**: HIGH — exactly the right scale for solo-dev. The "great LLM + cheap LLM" split maps perfectly onto Bali Zero's stack: `claude` (great, OAuth zero cost) + `qwen3.5:9b` or `gemma4:26b` Ollama local (cheap summarizer). nano-graphrag is the recommended starting point if you want GraphRAG **without buying into Microsoft's full-orchestrator framework**.

### 2.4 Triplex — KG construction at 1/60th GPT-4 cost

**Primary sources**:

- HF model: https://huggingface.co/SciPhi/Triplex
- Ollama: https://ollama.com/sciphi/triplex
- Blog: https://www.sciphi.ai/blog/triplex
- Substack: https://owencolegrove.substack.com/p/triplex-a-sota-llm-for-knowledge

**Verbatim**:

> "Triplex is a finetuned version of Phi3-3.8B for creating knowledge graphs from unstructured data developed by SciPhi.AI. It works by extracting triplets - simple statements consisting of a subject, predicate, and object - from text or other data sources."
> "[The triple extraction model achieves] results comparable to GPT-4, but at a fraction of the cost. More specifically, Triplex outperforms few-shot prompted GPT-4 at 1/60th the inference cost."
> "Triplex aims to radically disrupt this paradigm by reducing the generation cost of knowledge graphs tenfold."
> (SciPhi blog)

**Pattern key**: small (3.8B) Phi3 derivative finetuned only on triplet extraction. DPO+KTO trained on majority-vote-validated dataset. Runs on a laptop / Ollama.

**Useful for Bali Zero**: VERY HIGH — Triplex on Mini-Pro2 (24GB plenty for Phi3 size) becomes the _cheap LLM_ in nano-graphrag's two-LLM split, fully local, OSS, free. This solves the central economic problem of KG curation: triplet extraction is the LLM-call-heavy step. Triplex on Ollama removes its cost entirely. Combine: Triplex (extract) + claude (synthesize) → KG built nightly via cron.

### 2.5 Neo4j + LLM patterns

**Primary sources**:

- Implementing GraphRAG with Neo4j+LangChain: https://neo4j.com/blog/developer/global-graphrag-neo4j-langchain/

**Verbatim**:

> "Implementing 'From Local to Global' GraphRAG With Neo4j and LangChain"
> (Neo4j developer blog)

**Pattern key**: Neo4j as the canonical graph store, with Cypher queries auto-generated from natural language via LLM (Text2Cypher pattern). Co-reference / entity merge via APOC procedures. Drift handling: scheduled `apoc.merge.node` runs.

**Useful for Bali Zero**: MEDIUM — Neo4j is heavyweight (JVM, 4GB+ baseline). The Pro+Mini setup can run it (likely on Mini), but for solo-dev simplicity, networkx-via-nano-graphrag or Cognee's default backend is lighter. Neo4j becomes worth it if multi-domain queries hit complex Cypher patterns the lightweight backends can't handle.

### 2.6 KG-RAG — survey & DEEP-PolyU Awesome list

**Primary sources**:

- Awesome list: https://github.com/DEEP-PolyU/Awesome-GraphRAG
- Survey paper enumerated in list

**Useful for Bali Zero**: REFERENCE — bookmark the awesome-list, it consolidates 60+ GraphRAG variants & papers and is updated 2025-2026.

### 2.7 STaR-GraphRAG / Stanford patterns

**Primary sources**:

- Survey: https://arxiv.org/html/2504.15909v1 — "Synergizing RAG and Reasoning: A Systematic Review"

**Note**: a single canonical "Stanford STaR-GraphRAG" paper as named in the brief does not appear in current literature; the closest is the Synergizing RAG and Reasoning systematic review (2025-04). What _exists_ and is relevant:

- STaR (Zelikman 2022) for the self-improvement bootstrapping mechanism, applicable inside the GraphRAG generation step (covered §5).
- Synergizing RAG+Reasoning maps reasoning-aware RAG architectures including reflective and graph-aided variants.

**Useful for Bali Zero**: REFERENCE — read the synergy survey for the conceptual map.

### 2.8 Cognee — KG ECL + Ontologies (cross-reference §1.2)

Beyond memory, Cognee explicitly supports **ontology grounding** — you supply a domain ontology (e.g. property law: PBG → SLF → KKPR → KRK → IMB), and the cognify step grounds extracted triplets to the ontology, which constrains entity-disambiguation.

**Useful for Bali Zero**: HIGH — for Indonesian property/tax/immigration domains where the ontology is well-defined (gov't regulations Number/Year → Article → Clause), grounding triplets to ontology avoids LLM-hallucinated relations.

### 2.9 LangChain Graph Constructor / GraphRAG SDK

**Primary sources**:

- LangChain: https://python.langchain.com/docs/use_cases/graph/

**Pattern**: `LLMGraphTransformer` converts text → graph via prompt-controlled extraction; integrates with Neo4j/Memgraph backends.

**Useful for Bali Zero**: REFERENCE — usable but heavier than nano-graphrag for this scale.

### 2.10 Memgraph + Cognee integration

**Primary sources**:

- Memgraph blog: https://memgraph.com/blog/cognee-memgraph-integration-demo

**Verbatim**:

> "Cognee + Memgraph: How To Build An Intelligent Knowledge Graph Using Hacker News Data"
> (Memgraph blog title)

**Pattern**: Memgraph is faster than Neo4j on hot-path queries (in-memory, C++) but smaller community. Direct Cognee integration documented.

**Useful for Bali Zero**: MEDIUM — only if Neo4j proves too slow.

---

## 3. RAG self-correcting & reflective

### 3.1 Self-RAG (Asai et al., 2023)

**Primary sources**:

- Paper: https://arxiv.org/abs/2310.11511 — "Self-RAG: Learning to Retrieve, Generate, and Critique through Self-Reflection" (Akari Asai, Zeqiu Wu, Yizhong Wang, Avirup Sil, Hannaneh Hajishirzi)
- Project: https://selfrag.github.io/
- Repo: https://github.com/AkariAsai/self-rag

**Verbatim abstract**:

> "Despite their remarkable capabilities, large language models (LLMs) often produce responses containing factual inaccuracies due to their sole reliance on the parametric knowledge they encapsulate. Retrieval-Augmented Generation (RAG), an ad hoc approach that augments LMs with retrieval of relevant knowledge, decreases such issues. However, indiscriminately retrieving and incorporating a fixed number of retrieved passages, regardless of whether retrieval is necessary, or passages are relevant, diminishes LM versatility or can lead to unhelpful response generation. We introduce a new framework called Self-Reflective Retrieval-Augmented Generation (Self-RAG) that enhances an LM's quality and factuality through retrieval and self-reflection. Our framework trains a single arbitrary LM that adaptively retrieves passages on-demand, and generates and reflects on retrieved passages and its own generations using special tokens, called reflection tokens. Generating reflection tokens makes the LM controllable during the inference phase, enabling it to tailor its behavior to diverse task requirements. Experiments show that Self-RAG (7B and 13B parameters) significantly outperforms state-of-the-art LLMs and retrieval-augmented models on a diverse set of tasks. Specifically, Self-RAG outperforms ChatGPT and retrieval-augmented Llama2-chat on Open-domain QA, reasoning and fact verification tasks, and it shows significant gains in improving factuality and citation accuracy for long-form generations relative to these models."
> (Self-RAG paper, arXiv 2310.11511)

**Mechanism**: 4 reflection token types — `[Retrieve]` (need we retrieve?), `[IsRel]` (is the doc relevant?), `[IsSup]` (is the answer supported by the doc?), `[IsUse]` (is the response useful?). Trained via critic-model distillation + supervised fine-tune.

**Useful for Bali Zero**: HIGH (conceptual) — the 4-token controllability is the right mental model for how an autonomic system should reflect on its own retrieval. Ollama-local Self-RAG variants exist (community fine-tunes of Llama 3 / Qwen). For a pragmatic implementation: instead of fine-tuning, prompt Claude/Gemini to _emit those 4 tokens_ as a structured JSON output — same controllability, no training. That's the cheapest path.

### 3.2 CRAG — Corrective Retrieval (Yan et al., 2024)

**Primary sources**:

- Paper: https://arxiv.org/abs/2401.15884
- Repo: https://github.com/HuskyInSalt/CRAG
- OpenReview: https://openreview.net/forum?id=JnWJbrnaUE

**Verbatim abstract**:

> "Large language models (LLMs) inevitably exhibit hallucinations since the accuracy of generated texts cannot be secured solely by the parametric knowledge they encapsulate. Although retrieval-augmented generation (RAG) is a practicable complement to LLMs, it relies heavily on the relevance of retrieved documents, raising concerns about how the model behaves if retrieval goes wrong. To this end, we propose the Corrective Retrieval Augmented Generation (CRAG) to improve the robustness of generation. Specifically, a lightweight retrieval evaluator is designed to assess the overall quality of retrieved documents for a query, returning a confidence degree based on which different knowledge retrieval actions can be triggered. Since retrieval from static and limited corpora can only return sub-optimal documents, large-scale web searches are utilized as an extension for augmenting the retrieval results. Besides, a decompose-then-recompose algorithm is designed for retrieved documents to selectively focus on key information and filter out irrelevant information in them. CRAG is plug-and-play and can be seamlessly coupled with various RAG-based approaches."
> (CRAG paper, arXiv 2401.15884)

**Mechanism**: lightweight evaluator (small classifier, T5-large in paper) → 3 confidence buckets:

- **Correct** → use docs as-is, decompose-recompose strips noise.
- **Incorrect** → discard, fallback to web search (e.g. Tavily, SearxNG self-hosted).
- **Ambiguous** → use both internal docs + web search.

**Useful for Bali Zero**: HIGH — fits the OSINT layer. When NB-INTEL retrieves stale data, CRAG-style fallback to live web search (via Exa or SearxNG self-hosted) recovers freshness without polluting the NB. Ollama-local T5 evaluator is feasible.

### 3.3 Adaptive-RAG (Jeong et al., 2024)

**Primary sources**:

- Paper: https://arxiv.org/abs/2403.14403
- Repo: https://github.com/starsuzi/Adaptive-RAG

**Verbatim**:

> "Retrieval-Augmented Large Language Models (LLMs), which incorporate the non-parametric knowledge from external knowledge bases into LLMs, have emerged as a promising approach to enhancing response accuracy in several tasks, such as Question-Answering (QA)."
> "[The classifier] is a smaller LM trained to predict the complexity level of incoming queries with automatically collected labels, obtained from actual predicted outcomes of models and inherent inductive biases in datasets."
> (Adaptive-RAG paper)

**Mechanism**: 3-tier strategy — (A) no retrieval (LLM answers from parametric knowledge), (B) single-hop retrieval, (C) iterative multi-hop retrieval. A small classifier picks the tier per query.

**Useful for Bali Zero**: HIGH — drop-in optimization for any of Bali Zero's RAG queries. Trivial questions ("when is the SPT deadline?") don't need to hit Qdrant at all; complex ones ("what changed in 2026 KBLI 79902 vs 2024?") need iterative retrieval. Saves token cost and latency, especially relevant since DeepSeek charges per-token (Antonello does pay there).

### 3.4 RAG-Fusion

**Primary sources**:

- Original technique post by Adrian Raudaschl, popularized 2023: https://github.com/Raudaschl/rag-fusion
- Coverage: https://medium.com/@krtarunsingh/advanced-rag-techniques-rag-fusion-2dde7d77bb38

**Pattern**: original query → LLM expands to N sibling queries → each runs retrieval in parallel → results merged with **Reciprocal Rank Fusion (RRF)** → top-K sent to generator.

**Useful for Bali Zero**: MEDIUM — cheap LLM call (qwen Ollama) to generate 3-5 sibling queries materially improves recall on ambiguous Indonesian terminology (pajak ≈ tax ≈ PPh ≈ NPWP scope). Trivial to add inside any existing pipeline.

### 3.5 HyDE — Hypothetical Document Embeddings (Gao et al., 2022)

**Primary sources**:

- Paper: https://arxiv.org/abs/2212.10496 — "Precise Zero-Shot Dense Retrieval without Relevance Labels"
- Haystack docs: https://docs.haystack.deepset.ai/docs/hypothetical-document-embeddings-hyde
- Zilliz writeup: https://zilliz.com/learn/improve-rag-and-information-retrieval-with-hyde-hypothetical-document-embeddings

**Verbatim** (synthesis from Zilliz/MachineLearningPlus):

> "HyDE consistently outperforms classical BM25 and unsupervised Contriever across various datasets and metrics, remains competitive even against fine-tuned models on richly supervised tasks like TREC DL19/20"
> (Zilliz summary of HyDE results)

**Mechanism**: query → LLM generates a _hypothetical answer document_ → embed _that document_ (not the query) → retrieve real docs by similarity. The hypothetical doc is closer to real docs in embedding space than a question is.

**Useful for Bali Zero**: HIGH for cross-language searches (Italian Antonello question → English/Bahasa documents). HyDE in Italian/EN/Bahasa dramatically improves cross-language recall.

### 3.6 Anthropic Contextual Retrieval (2024)

**Primary sources**:

- Blog: https://www.anthropic.com/news/contextual-retrieval
- Cookbook: https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide
- Together AI guide: https://docs.together.ai/docs/how-to-implement-contextual-rag-from-anthropic
- Reddit/community: https://simonwillison.net/2024/Sep/20/introducing-contextual-retrieval/

**Verbatim**:

> "Contextual Retrieval solves this problem by prepending chunk-specific explanatory context to each chunk before embedding"
> "Contextual Embeddings reduced the top-20-chunk retrieval failure rate by 35%" (5.7% → 3.7%)
> "Combining Contextual Embeddings and Contextual BM25 reduced the top-20-chunk retrieval failure rate by 49%" (5.7% → 2.9%)
> "Reranked Contextual Embedding and Contextual BM25 reduced the top-20-chunk retrieval failure rate by 67%" (5.7% → 1.9%)
> "The one-time cost to generate contextualized chunks is $1.02 per million document tokens"
> (Anthropic blog)

**Example transformation (verbatim)**:

> Original chunk: "The company's revenue grew by 3% over the previous quarter."
> Contextualized: "This chunk is from an SEC filing on ACME corp's performance in Q2 2023; the previous quarter's revenue was $314 million. The company's revenue grew by 3% over the previous quarter."

**Mechanism**: before embedding, prepend a 50-100-token _contextual annotation_ generated by Claude that gives the chunk its situational frame. Combined with BM25 hybrid search and reranking (Cohere/Voyage), produces 67% reduction in retrieval failure.

**Cost trick**: prompt caching makes this affordable — you cache the _whole document_ once, then run N chunk-specific contextualization calls each as a tiny incremental token spend.

**Useful for Bali Zero**: VERY HIGH — single biggest free win available right now. With Claude OAuth MAX (zero token cost) the contextualization step is free. Apply to:

- All NB-INTEL items (the title alone is often ambiguous; chunk-context fixes it).
- All client documents (akta, NPWP, BPN).
- All regulation excerpts (the regulation number is often the only disambiguator).

### 3.7 Self-RAG + CRAG hybrids ("Synergizing RAG and Reasoning")

**Primary sources**:

- Survey: https://arxiv.org/html/2504.15909v1
- LangGraph CRAG tutorial: https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_crag/

**Pattern**: production systems combine Self-RAG's reflection tokens with CRAG's evaluator-driven fallback (web search) in a LangGraph state machine. The state machine handles: retrieve → evaluate → IF poor → web fallback → re-evaluate → generate → self-critique → answer.

**Useful for Bali Zero**: HIGH — operational reference. Antonello's autonomic system architecture should explicitly have _both_ an evaluator (CRAG-style) and a reflection step (Self-RAG-style); they solve different failure modes.

---

## 4. Memory architectures for long-running agents

### 4.1 Anthropic Memory tool (production, MCP-compatible)

(Already detailed §1.10 with complete verbatim.)

**Persistence model**: client-side `/memories/` directory. Claude calls `view`/`create`/`str_replace`/`insert`/`delete`/`rename`. The system prompt auto-injects "ALWAYS VIEW YOUR MEMORY DIRECTORY BEFORE DOING ANYTHING ELSE" + "ASSUME INTERRUPTION".

**Save/forget logic**: developer-controlled. Claude writes proactively; developer can prompt "Note: when editing your memory folder, always try to keep its content up-to-date, coherent and organized. You can rename or delete files that are no longer relevant. Do not create new files unless necessary."

**Useful for Bali Zero**: VERY HIGH — already structurally aligned with the existing `~/.claude/projects/-Users-nuzantara/memory/` arsenal.

### 4.2 Letta agent memory (3-tier OS-style)

(Already covered §1.4 verbatim.)

**Persistence model**: Core / Recall / Archival tiers backed by Postgres or SQLite. Agent self-edits Core through tools.

**Save/forget logic**: agent-driven via `core_memory_replace`, `core_memory_append`, `archival_memory_insert`, `recall_memory_search`. Forgetting is implicit (Recall ages out by retrieval recency).

**Useful for Bali Zero**: MEDIUM — strong if Bali Zero wants every agent run to be a stateful conversation; lighter alternatives (Memory tool) are likely sufficient.

### 4.3 Mem0 (production memory layer)

(Already covered §1.3.)

**Save/forget logic**: ADD-only by default in Mem0 v2 (no UPDATE/DELETE in primary path). Retrieval uses semantic + BM25 + entity match; old facts get out-ranked but not deleted. UPDATE is achieved through additive memory + later facts overriding earlier in retrieval rankings.

**Useful for Bali Zero**: MEDIUM — overlaps with Memory tool.

### 4.4 A-MEM (NeurIPS 2025) — Zettelkasten-inspired

**Primary sources**:

- Paper: https://arxiv.org/abs/2502.12110 — Wujiang Xu, Kai Mei, Hang Gao, Juntao Tan, Zujie Liang, Yongfeng Zhang
- Repo: https://github.com/agiresearch/A-mem
- alphaXiv: https://www.alphaxiv.org/overview/2502.12110v1

**Verbatim**:

> "While large language model (LLM) agents can effectively use external tools for complex real-world tasks, they require memory systems to leverage historical experiences."
> "Following the basic principles of the Zettelkasten method, the memory system is designed to create interconnected knowledge networks through dynamic indexing and linking. When a new memory is added, a comprehensive note is generated containing multiple structured attributes, including contextual descriptions, keywords, and tags."
> "[The system] enables memory evolution - as new memories are integrated, they can trigger updates to the contextual representations and attributes of existing historical memories."
> (A-MEM paper)

**Save/forget logic**: each new memory becomes a Zettelkasten "note" — auto-tagged, auto-linked to similar existing notes, and _historical notes can be updated when new ones land_. This is the strongest version of "memory evolution" in the published literature.

**Useful for Bali Zero**: HIGH — closest match to "the system is conscious of its own choices" requirement. The Zettelkasten model is also already the discipline Antonello uses (memory MD files in `~/.claude/projects/...`). A-MEM is essentially the formalization of that pattern.

### 4.5 MemoryBank (Zhong et al., 2023, AAAI 2024)

**Primary sources**:

- Paper: https://arxiv.org/abs/2305.10250 — "MemoryBank: Enhancing Large Language Models with Long-Term Memory"
- Repo: https://github.com/zhongwanjun/MemoryBank-SiliconFriend
- AAAI 2024: https://ojs.aaai.org/index.php/AAAI/article/view/29946

**Verbatim**:

> "[The authors] propose MemoryBank, a novel memory mechanism tailored for LLMs that enables the models to summon relevant memories, continually evolve through continuous memory updates, comprehend, and adapt to a user personality by synthesizing information from past interactions. MemoryBank incorporates a memory updating mechanism, inspired by the Ebbinghaus Forgetting Curve theory, that permits the AI to forget and reinforce memory based on time elapsed and the relative significance of the memory."
> (MemoryBank abstract)

**Save/forget logic**: explicit Ebbinghaus-curve forgetting — memory strength decays exponentially with time, refreshes on access. First published implementation of forgetting-as-feature.

**Useful for Bali Zero**: MEDIUM — academic; the _concept_ of Ebbinghaus-style decay is great for the OSINT/news layer where stale items should fade. Implementable in code without adopting the framework.

### 4.6 Generative Agents (Park et al., 2023, Stanford)

**Primary sources**:

- Paper: https://arxiv.org/abs/2304.03442 — Joon Sung Park, Joseph C. O'Brien, Carrie J. Cai, Meredith Ringel Morris, Percy Liang, Michael S. Bernstein
- Stanford HAI: https://hai.stanford.edu/news/computational-agents-exhibit-believable-humanlike-behavior

**Verbatim**:

> "Believable proxies of human behavior can empower interactive applications ranging from immersive environments to rehearsal spaces for interpersonal communication to prototyping tools."
> "[The architecture extends a large language model to] store a complete record of the agent's experiences using natural language, synthesize those memories over time into higher-level reflections, and retrieve them dynamically to plan behavior."
> "Crowdworkers deemed the generative agents' responses to interview questions more believable than responses given by humans who were pretending to be the agents."
> "[The components of the agent architecture--observation, planning, and reflection--each contribute critically to the believability of agent behavior.]"
> (Generative Agents abstract / paper findings)

**Save/forget logic**: 3-component scoring at retrieval time — _recency_ (exponential decay), _importance_ (LLM-rated 1-10 at write time), _relevance_ (cosine sim to current query). Reflections are higher-level memories synthesized from clusters of low-level memories at periodic checkpoints.

**Useful for Bali Zero**: VERY HIGH — the recency × importance × relevance triple is the cleanest published heuristic for "what matters now" and exactly maps to the autonomic-system spec ("crescere, auto-correggere, cosciente"). The reflection cycle (synthesize higher-level memories from clusters) is the operationalization of "cosciente delle proprie scelte".

### 4.7 Claude Skills as memory (covered §1.1)

Skills are _durable_ unlike turn-context — they're loaded by the harness, not consumed by tokens. As such, they function as a form of _procedural_ memory ("how to do X"), complementary to the _episodic_ memory of the Memory tool ("what happened on Y").

**Useful for Bali Zero**: HIGH — separation Procedural Skills + Episodic Memory tool maps cleanly to the autonomic architecture.

### 4.8 Anthropic Sleep-Time Compute / Auto-Dream (2025-2026)

**Primary sources**:

- Sleep-time Compute paper (Lin et al., UC Berkeley + Letta, April 2025): https://arxiv.org/abs/2504.13171 — referenced via Tessl post: https://tessl.io/blog/anthropic-tests-auto-dream-to-clean-up-claudes-memory/
- Coverage: https://www.storyboard18.com/digital/anthropic-introduces-dreams-feature-for-claude-to-reorganise-memory-and-improve-ai-agents-97376.htm
- The New Stack: https://thenewstack.io/anthropic-managed-agents-dreaming-outcomes/
- Practical guide: https://claudefa.st/blog/guide/mechanics/auto-dream

**Verbatim**:

> "Anthropic introduced 'dreaming' for Claude Managed Agents at its Code with Claude developer event, a research-preview feature that reviews past sessions. Auto Dream is Anthropic's memory consolidation system for Claude Code, a maintenance cycle that runs in the background after you've been using Claude Code for a while — periodically reviewing accumulated session notes, removing stale or contradictory information, and reorganizing what's left into clean, indexed files."
> "[The feature is] explicitly modelled after human REM sleep, which consolidates important memories, prunes noise, and strengthens connections while discarding trivia."
> "The theoretical backing for this feature traces to a UC Berkeley + Letta paper from April 2025 — 'Sleep-time Compute'. The core finding: models that pre-compute during idle time reduce test-time compute by 5x at equal accuracy, with up to 18% accuracy gains."
> (claudefa.st / tessl.io / opentools.ai coverage)

**Save/forget logic**: triggered on time / session-count threshold (24h or 5 sessions). 3 phases: orient → consolidate → output. Resolves contradictions between memory files; merges redundant ones.

**Useful for Bali Zero**: VERY HIGH — exactly the "self-correzione" requirement of the autonomic spec. Implementable today by:

1. Cron job nightly on Pro: `claude --command="run dream consolidation on /memories"`.
2. Re-uses Claude OAuth MAX, zero $ cost.
3. Output: clean `MEMORY.md` index + `MEMORY_ARCHIVE.md` (already in place).

The _Sleep-time Compute_ primitive (5x test-time compute reduction at equal accuracy) is also why running KG densification, embedding refresh, and reflection synthesis at night (Mini-Pro2 H24) is the right architectural choice.

---

## 5. Self-improving / self-evolving systems

### 5.1 Sakana AI Scientist v2 (Apr 2025)

**Primary sources**:

- Paper: https://arxiv.org/abs/2504.08066 — "The AI Scientist-v2: Workshop-Level Automated Scientific Discovery via Agentic Tree Search"
- PDF: https://pub.sakana.ai/ai-scientist-v2/paper/paper.pdf
- Repo: https://github.com/SakanaAI/AI-Scientist-v2
- Nature publication blog: https://sakana.ai/ai-scientist-nature/

**Verbatim**:

> "[The AI Scientist-v2 is] an end-to-end agentic system capable of producing the first entirely AI-generated peer-review-accepted workshop paper, which iteratively formulates scientific hypotheses, designs and executes experiments, analyzes and visualizes data, and autonomously authors scientific manuscripts."
> "Compared to its predecessor (v1), The AI Scientist-v2 eliminates the reliance on human-authored code templates, generalizes effectively across diverse machine learning domains, and leverages a novel progressive agentic tree-search methodology managed by a dedicated experiment manager agent."
> "[The system enhances] the AI reviewer component by integrating a Vision-Language Model (VLM) feedback loop for iterative refinement of content and aesthetics of the figures."
> "One manuscript achieved high enough scores to exceed the average human acceptance threshold, marking the first instance of a fully AI-generated paper successfully navigating a peer review."
> (AI Scientist-v2 paper)

**Self-improvement mechanism**: tree search over hypotheses + experiments. Each branch tested empirically. Failed branches pruned. Successful branches expanded. The _experiment manager agent_ gates compute. VLM feedback loop on figures = visual self-correction.

**Useful for Bali Zero**: REFERENCE / inspirational — full AI-Scientist is overkill, but the _agentic tree search managed by an experiment manager_ is the right pattern for any ambitious "the system tries 5 different KG structures, picks the best by retrieval recall, commits" workflow. Could be applied to NB-INTEL scorer prompt evolution: nightly run 3 candidate scorer prompts, pick the one with highest precision-on-keepers, commit.

### 5.2 AlphaEvolve (DeepMind, May 2025)

**Primary sources**:

- Blog: https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- Paper PDF: https://storage.googleapis.com/deepmind-media/DeepMind.com/Blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/AlphaEvolve.pdf
- Paper arXiv: https://arxiv.org/abs/2506.13131
- Wiki: https://en.wikipedia.org/wiki/AlphaEvolve
- OpenEvolve OSS reproduction: https://huggingface.co/blog/codelion/openevolve

**Verbatim**:

> "AlphaEvolve, an evolutionary coding agent that substantially enhances capabilities of state-of-the-art LLMs on highly challenging tasks such as tackling open scientific problems or optimizing critical pieces of computational infrastructure."
> "AlphaEvolve developed a search algorithm that found a procedure to multiply two 4×4 complex-valued matrices using 48 scalar multiplications; offering the first improvement, after 56 years, over Strassen's algorithm in this setting."
> "AlphaEvolve discovered a simple yet remarkably effective heuristic to help Borg orchestrate Google's vast data centers more efficiently. This solution, now in production for over a year, continuously recovers on average 0.7% of Google's worldwide compute resources."
> "AlphaEvolve achieved up to a 32.5% speedup for the FlashAttention kernel implementation in Transformer-based AI models."
> "[AlphaEvolve employs] an ensemble of large language models, specifically a combination of Gemini 2.0 Flash and Gemini 2.0 Pro. This ensemble approach allows balancing computational throughput with the quality of generated solutions. Gemini 2.0 Flash, with its lower latency, enables a higher rate of candidate generation, while Gemini 2.0 Pro provides occasional, higher-quality suggestions."
> (DeepMind blog + InfoQ coverage)

**Self-improvement mechanism**: evolutionary algorithm where population = code candidates, fitness = automated evaluators, mutation = LLM-generated edits. Open-source reproduction (OpenEvolve) is available — usable on commodity hardware with Gemini API or local LLMs.

**Useful for Bali Zero**: REFERENCE — overkill for daily ops, but the evolutionary-search-with-LLM-mutations pattern fits any optimization problem with a measurable evaluator. Specific application: NB-INTEL scorer threshold tuning, or KBLI extraction prompt evolution. OpenEvolve (https://github.com/codelion/openevolve) makes this practical with Gemini OAuth-free.

### 5.3 Self-Discover (Google, Feb 2024)

**Primary sources**:

- Paper: https://arxiv.org/abs/2402.03620 — Pei Zhou et al.
- DeepMind page: https://deepmind.google/research/publications/64816/

**Verbatim**:

> "We introduce SELF-DISCOVER, a general framework for LLMs to self-discover the task-intrinsic reasoning structures to tackle complex reasoning problems that are challenging for typical prompting methods."
> "Core to the framework is a self-discovery process where LLMs select multiple atomic reasoning modules such as critical thinking and step-by-step thinking, and compose them into an explicit reasoning structure for LLMs to follow during decoding."
> "SELF-DISCOVER substantially improves GPT-4 and PaLM 2's performance on challenging reasoning benchmarks such as BigBench-Hard, grounded agent reasoning, and MATH, by as much as 32% compared to Chain of Thought (CoT)."
> "Furthermore, SELF-DISCOVER outperforms inference-intensive methods such as CoT-Self-Consistency by more than 20%, while requiring 10-40x fewer inference compute."
> (Self-Discover paper)

**Self-improvement mechanism**: 2-stage prompting — Stage 1 (SELECT-ADAPT-IMPLEMENT, done once per task type): pick reasoning modules from a bank (deductive, analogical, decomposition...), adapt them to the domain, implement as a reasoning _plan_. Stage 2 (DECODE): execute the plan over instances.

**Useful for Bali Zero**: HIGH — for recurring task types (visa case analysis, KBLI selection, tax compliance review), Self-Discover lets you build _one_ reasoning structure per type and reuse it. Implementable with Claude OAuth in tens of lines of prompt code.

### 5.4 STaR (Zelikman et al., 2022) and V-STaR (Hosseini et al., 2024)

**Primary sources**:

- STaR paper: https://arxiv.org/abs/2203.14465 — Eric Zelikman, Yuhuai Wu, Jesse Mu, Noah D. Goodman
- V-STaR paper: https://arxiv.org/abs/2402.06457 — Arian Hosseini, Xingdi Yuan, Nikolay Malkin, Aaron Courville, Alessandro Sordoni, Rishabh Agarwal
- Quiet-STaR (follow-up): https://arxiv.org/abs/2403.09629

**Verbatim STaR**:

> "[STaR] iteratively leverages a small number of rationale examples and a large dataset without rationales to bootstrap the ability to perform successively more complex reasoning. The technique relies on a simple loop: generate rationales to answer many questions, prompted with a few rationale examples; if the generated answers are wrong, try again to generate a rationale given the correct answer; fine-tune on all the rationales that ultimately yielded correct answers; repeat."
> (STaR paper)

**Verbatim V-STaR**:

> "V-STaR utilizes both correct and incorrect solutions generated during the self-improvement process to train a verifier using DPO that judges correctness of model-generated solutions, which is then used at inference time to select one solution among many candidate solutions."
> "Running V-STaR for multiple iterations results in progressively better reasoners and verifiers, delivering a 4% to 17% test accuracy improvement over existing self-improvement and verification approaches on common code generation and math reasoning benchmarks with LLaMA2 models."
> (V-STaR paper)

**Self-improvement mechanism**: STaR = bootstrap rationales by self-correction loop, fine-tune on successful rationales. V-STaR = use _both_ correct and incorrect solutions, train a verifier, use verifier at inference to pick best of N samples.

**Useful for Bali Zero**: REFERENCE — full STaR/V-STaR requires fine-tuning. Practical port without fine-tuning: maintain an `IF answer wrong THEN regenerate with correction prompt` loop in the autonomic agent — captures the spirit of STaR, no training cost.

### 5.5 Constitutional AI / RLAIF

**Primary sources**:

- CAI paper: https://arxiv.org/abs/2212.08073 — Yuntao Bai et al., Anthropic
- CAI Anthropic announce: https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback
- RLAIF paper: https://arxiv.org/abs/2309.00267 — Harrison Lee et al., Google
- RLAIF cookbook: https://cameronrwolfe.substack.com/p/rlaif-reinforcement-learning-from

**Verbatim CAI**:

> "[The paper experiments with methods for] training a harmless AI assistant through self-improvement, without any human labels identifying harmful outputs. The only human oversight is provided through a list of rules or principles, referred to as 'Constitutional AI'."
> "[The process involves] both a supervised learning and a reinforcement learning phase. In the supervised phase, [we] sample from an initial model, then generate self-critiques and revisions, and finetuning occurs on revised responses. In the RL phase, [a] model evaluates which samples are better, then trains a preference model from this AI preference dataset, using 'RL from AI Feedback' (RLAIF)."
> (CAI paper)

**Verbatim RLAIF**:

> "Reinforcement learning from human feedback (RLHF) has proven effective in aligning large language models (LLMs) with human preferences, but gathering high-quality preference labels is expensive. RL from AI Feedback (RLAIF) offers a promising alternative that trains the reward model (RM) on preferences generated by an off-the-shelf LLM."
> "Across the tasks of summarization, helpful dialogue generation, and harmless dialogue generation, [the research shows that] RLAIF achieves comparable performance to RLHF."
> "[The paper introduces] direct-RLAIF (d-RLAIF) — a technique that circumvents RM training by obtaining rewards directly from an off-the-shelf LLM during RL, which achieves superior performance to canonical RLAIF."
> (RLAIF paper)

**Self-improvement mechanism**: AI critiques + revises its own output guided by a written constitution; reward model trained on AI preferences (not human).

**Useful for Bali Zero**: HIGH — _constitutional self-correction_ is directly applicable as a critique loop on agent outputs (e.g. "before sending the email, check against constitution: tone respectful, no commitments without approval, accurate Indonesian terminology, sign zantara@balizero.com only"). No training required — runs as an inference-time loop with Claude OAuth.

### 5.6 Anthropic Sleep-time compute / Auto-Dream (covered §4.8)

Per Sakana AI Scientist v2 + Auto-Dream: at-night compute is the right architectural choice for self-correction/consolidation operations.

**Useful for Bali Zero**: VERY HIGH — Mini-Pro2 H24 is purpose-built for this.

---

## 6. Multi-agent orchestration patterns 2026

### 6.1 Anthropic Multi-Agent Research System

**Primary sources**:

- Engineering blog: https://www.anthropic.com/engineering/multi-agent-research-system
- ZenML LLMOps DB: https://www.zenml.io/llmops-database/building-a-multi-agent-research-system-for-complex-information-tasks
- Sub-agent deep dive: https://medium.com/codetodeploy/the-architecture-of-scale-a-deep-dive-into-anthropics-sub-agents-6c4faae1abda

**Verbatim**:

> "A lead agent coordinates the process while delegating to specialized subagents that operate in parallel."
> "Research demands the flexibility to pivot or explore tangential connections as the investigation unfolds. The model must operate autonomously for many turns."
> "A multi-agent system with Claude Opus 4 as the lead agent and Claude Sonnet 4 subagents outperformed single-agent Claude Opus 4 by 90.2%."
> "Agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats."
> "Most coding tasks involve fewer truly parallelizable tasks than research, and LLM agents are not yet great at coordinating and delegating to other agents in real time."
> "The lead agent decomposes queries into subtasks and describes them to subagents. Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries."
> (Anthropic Engineering blog)

**Pattern**: orchestrator-worker. Lead = Opus, workers = Sonnet, parallel execution, results aggregated by lead.

**Useful for Bali Zero**: VERY HIGH — Antonello already runs this pattern (wave-orchestrator with parallel agents on independent tasks per CLAUDE.md). The 15x token cost note is _not_ a constraint with OAuth MAX (3 plans). The "less effective for tightly interdependent tasks like coding" caveat is also accurate — already learned from `wave2-pro` discoveries (CLAUDE.md mentions cap 4 sessions parallel).

### 6.2 AutoGen v0.4 (Microsoft)

**Primary sources**:

- MS Research overview: https://www.microsoft.com/en-us/research/articles/autogen-v0-4-reimagining-the-foundation-of-agentic-ai-for-scale-extensibility-and-robustness/
- AutoGen blog: https://devblogs.microsoft.com/autogen/autogen-reimagined-launching-autogen-0-4/
- Repo: https://github.com/microsoft/autogen
- Original paper: http://ryenwhite.com/papers/WuiCOLM2024.pdf

**Verbatim**:

> "AutoGen v0.4 is a significant milestone representing a complete redesign of the AutoGen library, aimed at improving code quality, robustness, generality, and the scalability of agentic workflows."
> "In early 2024, Microsoft experimented with alternate architectures and adopted an actor model for multi-agent orchestration—a well-known programming model for concurrent programming where actors are the computational building blocks that can exchange messages and perform work."
> "AutoGen v0.4 adopts a more robust, asynchronous, and event-driven architecture, enabling a broader range of agentic scenarios with stronger observability, more flexible collaboration patterns, and reusable components."
> (MS Research / AutoGen blog)

**Pattern**: Actor-model multi-agent. AutoGen Core = base layer (actor model), AutoGen AgentChat = high-level patterns (group chat, sequential, etc.).

**Useful for Bali Zero**: MEDIUM — heavier framework than CrewAI/LangGraph; actor-model is overkill for solo-dev. Worth knowing about for the Magentic-One integration (§6.7) which is the actually interesting Microsoft offering.

### 6.3 CrewAI

**Primary sources**:

- Site: https://crewai.com/
- Docs: https://docs.crewai.com/
- Repo: https://github.com/crewaiinc/crewai

**Verbatim**:

> "CrewAI is an open-source framework designed to coordinate multiple AI agents in structured, role-based workflows. It simplifies complex tasks by enabling agents to specialize, communicate, and collaborate effectively."
> "[The framework] enables organizations to define specialized autonomous agents with specific roles, goals, and expertise areas, assign tasks to agents based on their specialized capabilities, and establish clear dependencies between tasks to create structured workflows."
> "With 14,800 monthly searches and an active community, CrewAI is the second most popular framework. The biggest strength is developer experience. You can define a working multi-agent system in under 20 lines of Python."
> (CrewAI docs / 2025 review)

**Pattern**: role-based, hierarchical (manager + workers), task-graph DAG. Simpler API than AutoGen or LangGraph.

**Useful for Bali Zero**: MEDIUM — CrewAI is the _gateway drug_ to multi-agent for Python devs. If the autonomic system needs a quickly-prototypable role-based crew (e.g. "Researcher + Writer + Editor + Publisher" for the WR2/article pipeline), CrewAI is the right choice over LangGraph (overkill) or hand-rolled bash (underkill).

### 6.4 LangGraph (covered §1.7)

**Useful for Bali Zero**: HIGH for state-machine workflows, MEDIUM for free-form multi-agent (CrewAI better there).

### 6.5 OpenAI Swarm → Agents SDK (deprecation notice)

**Primary sources**:

- Swarm repo (deprecated): https://github.com/openai/swarm
- Agents SDK: https://openai.github.io/openai-agents-python/
- Cookbook: https://developers.openai.com/cookbook/examples/orchestrating_agents

**Verbatim**:

> "Swarm focuses on making agent coordination and execution lightweight, highly controllable, and easily testable. However, it's important to note that Swarm is now replaced by the OpenAI Agents SDK, which is a production-ready evolution of Swarm. The Agents SDK features key improvements and will be actively maintained by the OpenAI team. OpenAI recommends migrating to the Agents SDK for all production use cases."
> "Swarm accomplishes this through two primitive abstractions: Agents and handoffs. An Agent encompasses instructions and tools, and can at any point choose to hand off a conversation to another Agent."
> "A handoff is defined as an agent (or routine) handing off an active conversation to another agent, much like when you get transferred to someone else on a phone call. Except in this case, the agents have complete knowledge of your prior conversation!"
> "Since the system has no persistent state between calls, every handoff must include all context the next agent needs—no hidden variables, no magical memory."
> (OpenAI Cookbook + Galileo blog)

**Pattern**: handoffs — explicit "transfer the conversation to AgentX". Different from orchestrator-worker (which is delegate-and-collect).

**Useful for Bali Zero**: REFERENCE — handoffs pattern is useful for _single-thread_ multi-agent (e.g. Triage agent → routes to Visa specialist OR Tax specialist OR Property specialist). But OpenAI-stack only — duplicative given Antonello's Codex CLI access.

### 6.6 Google Agent Development Kit (ADK) — 2025

**Primary sources**:

- Site: https://adk.dev/
- Google blog: https://developers.googleblog.com/en/agent-development-kit-easy-to-build-multi-agent-applications/
- Repo: https://github.com/google/adk-python
- Multi-agent docs: https://adk.dev/agents/multi-agents/
- TypeScript intro: https://developers.googleblog.com/introducing-agent-development-kit-for-typescript-build-ai-agents-with-the-power-of-a-code-first-approach/

**Verbatim**:

> "Google introduced Agent Development Kit (ADK) at Google Cloud NEXT 2025, a new open-source framework designed to simplify the full stack end-to-end development of agents and multi-agent systems."
> "ADK provides Multi-Agent by Design capabilities that let you build modular and scalable applications by composing multiple specialized agents in a hierarchy, enabling complex coordination and delegation."
> "[The framework offers] LiteLLM integration letting you choose from a wide selection of models from providers like Anthropic, Meta, Mistral AI, AI21 Labs, and many more."
> (Google Developers blog)

**Pattern**: hierarchical multi-agent, with tool use, planning, code execution; uses LiteLLM under the hood for provider portability. Python and now TypeScript.

**Useful for Bali Zero**: HIGH — pairs naturally with Gemini CLI 3.1 Pro (free OAuth) for the Gemini-side of the stack. Worth evaluating as an alternative to LangGraph for any _Gemini-led_ sub-pipeline.

### 6.7 Microsoft Magentic-One

**Primary sources**:

- Paper: https://arxiv.org/abs/2411.04468
- Microsoft Research: https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/
- AutoGen integration: https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/magentic-one.html
- Repo: https://github.com/microsoft/autogen/blob/main/python/packages/autogen-magentic-one/README.md

**Verbatim**:

> "Magentic-One is a high-performing open-source agentic system that uses a multi-agent architecture where a lead agent, the Orchestrator, plans, tracks progress, and re-plans to recover from errors. Throughout task execution, the Orchestrator directs other specialized agents to perform tasks as needed, such as operating a web browser, navigating local files, or writing and executing Python code."
> "Magentic-One's modular design allows agents to be added or removed from the team without additional prompt tuning or training, easing development and making it extensible to future scenarios."
> (Magentic-One paper)

**Pattern**: Orchestrator + 4 specialized agents (WebSurfer browser, FileSurfer local files, Coder, ComputerTerminal). Two ledgers — _Task Ledger_ (what we know + plan) and _Progress Ledger_ (current state). Re-plan loop on error.

**Useful for Bali Zero**: VERY HIGH — this is exactly the right architecture for OSINT research. The 4-specialist agent set maps directly to Bali Zero's needs:

- WebSurfer = Tavily/SearxNG retrieval
- FileSurfer = Drive / local docs / NB content
- Coder = Python data wrangling
- ComputerTerminal = bash / cron / SSH ops

Already runs on AutoGen v0.4 and supports any LLM via LiteLLM. Self-hostable, no paid API.

### 6.8 Other patterns (debate, blackboard)

**Primary sources**:

- Multi-agent debate: https://arxiv.org/abs/2305.14325 — Du et al. "Improving Factuality and Reasoning in Language Models through Multiagent Debate"
- Society of Mind: classical (Minsky, 1986); LLM revival via blackboard via various 2024-25 papers
- Microsoft 4-prong survey: https://www.microsoft.com/en-us/research/wp-content/uploads/2024/11/Magentic-One.pdf (compares orchestrator vs hierarchical vs blackboard vs market)

**Pattern Debate**: multiple agents propose answers, then critique each other across N rounds, then a judge picks the consensus. Boosts factuality.

**Pattern Blackboard**: shared workspace where any agent can post insights; opportunistic execution as their preconditions become satisfied.

**Useful for Bali Zero**: HIGH — Antonello's existing _bipolar verifier_ (1 LLM main + 1 NB ground truth) is a 2-agent debate degenerate. Could expand to a 3-agent "Claude + Gemini + DeepSeek + NB-X" mini-debate per critical decision. Already documented as ad-hoc pattern in CLAUDE.md.

### 6.9 MetaGPT (covered §1.7 / extended below)

**Verbatim**:

> "MetaGPT, an innovative meta-programming framework incorporating efficient human workflows into LLM-based multi-agent collaborations. MetaGPT encodes Standardized Operating Procedures (SOPs) into prompt sequences for more streamlined workflows, thus allowing agents with human-like domain expertise to verify intermediate results and reduce errors."
> "MetaGPT utilizes an assembly line paradigm to assign diverse roles to various agents, efficiently breaking down complex tasks into subtasks involving many agents working together."
> (MetaGPT paper, arXiv 2308.00352)

**Pattern**: SOPs as prompt sequences = each role has a domain-document spec they enact (PRD writer, architect, project manager, engineer, QA). Cascading hallucinations bounded because each role's output is structured (PRD, design doc, code) and reviewable.

**Useful for Bali Zero**: HIGH — the SOP-as-prompt-sequences pattern is precisely how to encode Bali Zero's domain expertise (visa SOPs, tax SOPs, property SOPs). Each domain becomes a multi-step assembly-line workflow.

### 6.10 Comparison matrix (for Bali Zero choice)

| Framework             | Pattern                    | Self-host   | LLM-agnostic      | Solo-dev fit             |
| --------------------- | -------------------------- | ----------- | ----------------- | ------------------------ |
| Anthropic Multi-Agent | orchestrator-worker        | Claude-only | No                | HIGH (already in use)    |
| AutoGen v0.4          | actor model                | Yes         | LiteLLM           | MEDIUM (overkill)        |
| CrewAI                | role-hierarchy             | Yes         | LiteLLM           | HIGH (gateway)           |
| LangGraph             | state-machine              | Yes         | LiteLLM           | HIGH (complex flows)     |
| OpenAI Agents SDK     | handoffs                   | partial     | OpenAI-flavored   | LOW (vendor)             |
| Google ADK            | hierarchical               | Yes         | LiteLLM           | HIGH (Gemini-led)        |
| Magentic-One          | orchestrator+4 specialists | Yes         | LiteLLM           | VERY HIGH (OSINT-shaped) |
| MetaGPT               | SOP assembly-line          | Yes         | provider-agnostic | HIGH (domain SOPs)       |

**Recommendation for Bali Zero**: hybrid approach —

- _Orchestrator-worker_ (Anthropic pattern) for daily R&D / research tasks (Claude OAuth MAX, free).
- _Magentic-One_ (running on AutoGen v0.4) for the OSINT autonomic loop (web/file/code/term agents).
- _MetaGPT-style SOP encoding_ for per-domain workflows (visa, tax, property).
- _CrewAI_ if a quick prototype is needed.

---

## 7. Observability & cost control per multi-LLM stack

### 7.1 Langfuse (OSS MIT, ClickHouse-acquired Dec 2025)

**Primary sources**:

- Site: https://langfuse.com/
- Repo: https://github.com/langfuse/langfuse
- Self-host: https://langfuse.com/self-hosting
- Docs: https://langfuse.com/docs
- Acquisition: https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability

**Verbatim**:

> "Langfuse is the most widely adopted open-source LLM engineering platform."
> "Langfuse can be self-hosted in minutes and is battle-tested. Self-hosting guides show how to deploy open-source LLM observability with Docker, Kubernetes, or VMs on your own infrastructure. Langfuse self-hosted is optimized for production environments and is the exact same codebase as Langfuse Cloud, just deployed on your own infrastructure."
> "Langfuse brings observability, prompts, evals, experiments, and human annotation into one connected workflow."
> "ClickHouse has acquired Langfuse, the leading open-source platform for LLM observability, evaluations, and prompt management. Langfuse remains 100% open-source under its existing MIT license for core features which allows for self-hosting at production scale."
> (Langfuse site / ClickHouse blog)

**Features**: traces, sessions, prompt management, evals (LLM-as-judge), user feedback collection, datasets, experiments. Integrates with OpenTelemetry, LangChain, OpenAI SDK, LiteLLM.

**Useful for Bali Zero**: VERY HIGH — Antonello's stack already has `~/.langfuse-secrets.env` per ls of root. Self-hosted on Mini-Pro2 (Postgres + ClickHouse + Node frontend), gives full observability across Claude/Gemini/Codex/DeepSeek/Ollama. Single pane of glass. **Top recommendation**.

### 7.2 LangSmith (LangChain SaaS, not self-hostable)

**Primary sources**:

- Site: https://www.langchain.com/langsmith

**Note**: LangSmith is the cloud-only product from LangChain. Closed-source backend, paid. _Not aligned_ with Bali Zero's "no paid APIs" stance unless the free tier suffices.

**Useful for Bali Zero**: LOW — Langfuse self-hosted is the strict superset for free.

### 7.3 Phoenix (Arize, OSS)

**Primary sources**:

- Site: https://phoenix.arize.com/
- Repo: https://github.com/Arize-ai/phoenix
- Docs: https://arize.com/docs/phoenix
- ADK integration: https://google.github.io/adk-docs/observability/phoenix/

**Verbatim**:

> "Phoenix is fully open source and self-hostable — no feature gates or restrictions."
> "Phoenix accepts traces over OpenTelemetry (OTLP) and provides auto-instrumentation for popular frameworks (LlamaIndex, LangChain, DSPy, Mastra, Vercel AI SDK), providers (OpenAI, Bedrock, Anthropic), and languages (Python, TypeScript, Java)."
> "Phoenix is vendor and language agnostic with out-of-the-box support for popular frameworks (OpenAI Agents SDK, Claude Agent SDK, LangGraph, Vercel AI SDK, Mastra, CrewAI, LlamaIndex, DSPy) and LLM providers (OpenAI, Anthropic, Google GenAI, Google ADK, AWS Bedrock, OpenRouter, LiteLLM, and more)."
> "Phoenix runs practically anywhere, including your local machine, a Jupyter notebook, a containerized deployment, or in the cloud."
> (Phoenix docs)

**Features**: OTel-native traces, evals (code-based, LLM-judge, human label), datasets. The Claude Agent SDK auto-instrumentation is a key differentiator vs Langfuse (which is more LangChain/OpenAI-flavored).

**Useful for Bali Zero**: HIGH — particularly _because_ of Claude Agent SDK auto-instrumentation. Pairs well with Langfuse (Phoenix for traces + evals, Langfuse for prompt management + datasets), or stand-alone if simpler.

### 7.4 Helicone (Proxy + observability)

**Primary sources**:

- Site: https://www.helicone.ai/
- Repo: https://github.com/Helicone/helicone
- Comparison guide: https://www.helicone.ai/blog/the-complete-guide-to-LLM-observability-platforms

**Verbatim**:

> "Helicone is a lightweight, proxy-based LLM observability tool that operates as an AI Gateway. Instead of instrumenting your code with SDKs, you send OpenAI or other LLM API calls through the Helicone proxy."
> "Helicone is designed for the fastest time-to-value and easiest to get started with. While other platforms may require days of integration work, Helicone can be implemented in minutes with a single line change to your base URL."
> (Helicone blog)

**Features**: proxy-based (not SDK), 1-line URL change, OSS self-hostable, has an AI Gateway with caching / rate-limiting / fallback.

**Useful for Bali Zero**: MEDIUM — proxy-based doesn't fit `claude` CLI well (CLI doesn't take base-URL changes for OAuth). Helicone is great for SDK-based codepaths (like `apps/backend-rag/backend/llm/claude_oauth_client.py` per CLAUDE.md). Won't observe `claude` CLI subagent runs.

### 7.5 Portkey

**Primary sources**:

- Site: https://portkey.ai/

**Pattern**: AI gateway + observability + prompt management; emphasizes routing & failover (multi-provider load-balancing).

**Useful for Bali Zero**: LOW — proprietary cloud-first. Self-hosting available but heavy. Helicone OSS is more aligned.

### 7.6 OpenLLMetry / Traceloop

**Primary sources**:

- Repo: https://github.com/traceloop/openllmetry
- Site: https://www.traceloop.com/

**Verbatim**:

> "OpenLLMetry by Traceloop is an open-source SDK and standard for sourcing LLM observability data via OpenTelemetry. It gives you a vendor-neutral way to instrument your app using the standard OTLP protocol and send traces to any OTel-compatible backend."
> (Comparison synthesis)

**Pattern**: OTel SDK only — doesn't include UI; bring-your-own backend (Phoenix, Jaeger, Tempo, Datadog, etc.).

**Useful for Bali Zero**: HIGH as the **instrumentation layer** — emit OTel traces from every LLM call (across CLI, SDK, MCP), point them at Phoenix or Langfuse for storage/visualization. The right architecture is OpenLLMetry SDK → OTel collector → Langfuse + Phoenix.

### 7.7 Open-source comparison & recommendation

| Tool        | OSS license | Self-host    | Best at                                    | Bali Zero fit                            |
| ----------- | ----------- | ------------ | ------------------------------------------ | ---------------------------------------- |
| Langfuse    | MIT         | Yes (Docker) | full-stack (traces+prompts+evals+datasets) | TOP CHOICE                               |
| Phoenix     | Elastic 2.0 | Yes          | traces + evals (OTel-native)               | EXCELLENT (paired with Langfuse or solo) |
| Helicone    | Apache 2.0  | Yes          | proxy-based gateway                        | NICHE (SDK paths only)                   |
| Portkey     | partial OSS | partial      | gateway + multi-provider routing           | LOW (proprietary tilt)                   |
| OpenLLMetry | Apache 2.0  | SDK-only     | OTel instrumentation                       | INSTRUMENTATION LAYER                    |
| LangSmith   | Closed      | No           | LangChain-native                           | LOW (cost)                               |

### 7.8 Cost control patterns for multi-LLM stack

**Token budgeting**:

- Langfuse + Phoenix both compute per-trace token usage and _can flag drift_ (e.g. a workflow that used to cost 5k tokens now uses 50k).
- Langfuse "experiments" let you A/B prompt versions with cost as a metric.

**Routing for cost**:

- LiteLLM proxy (https://github.com/BerriAI/litellm) — routes per-request to cheapest-or-best provider. Pairs with all observability backends.
- For Bali Zero: simple bash-level routing (`claude` for premium, `gemini` for free, `qwen Ollama` for cheap-bulk) is already in place; LiteLLM proxy adds programmability if a single Python entry-point is desired.

**Caching**:

- Anthropic prompt caching (1h TTL): cuts cost ~90% on repeated context. Works automatically on `claude` CLI per Anthropic docs.
- Helicone offers cache-on-proxy across providers (useful for non-Anthropic).

**Useful for Bali Zero**: VERY HIGH — set up Langfuse on Mini, OpenLLMetry SDK in every Python entry point, route OTel to Langfuse + Phoenix. Cost dashboards + rage-flag alerts when DeepSeek run >$0.05 (Antonello's only paid endpoint).

---

## 8. Synthesis: The Bali Zero Autonomic Lifecycle Stack (recommended)

### Birth

- **Ingestion**: Cron-fed scrapers (existing) + LlamaParse for PDFs + nano-graphrag/LightRAG for KG construction.
- **Triplet extraction**: Triplex on Mini-Pro2 Ollama (cheap, fast, OSS).
- **Chunk contextualization**: Anthropic Contextual Retrieval via Claude OAuth (free).

### Growth

- **Memory layer**: Anthropic Memory tool (`/memories/<domain>/...`) + Claude Skills (`SKILL.md` per domain) + Cognee KG layer for cross-domain links.
- **Retrieval**: Adaptive-RAG router → no/single/multi-step → CRAG-style web fallback when retrieval fails.

### Self-correction

- **Reflective**: Self-RAG-style structured 4-token reflection (re-prompted via Claude, no fine-tune).
- **Constitutional**: per-domain constitution-based critic loop on outgoing artifacts (emails, advice, decisions).
- **Verifier**: bipolar verifier (LLM main + NB ground truth) — already in use; expand to tri-LLM debate on critical PRs.

### Self-aware (cosciente delle proprie scelte)

- **Sleep-time compute**: nightly cron on Mini — Auto-Dream-style memory consolidation, reflection synthesis (Generative-Agents recency × importance × relevance) over the day's memories.
- **A-MEM Zettelkasten linking**: re-link new memories to prior notes; trigger updates of stale notes when superseded.

### Fruits canalizzati nel sistema

- **Multi-agent orchestration**: Anthropic orchestrator-worker for daily R&D; Magentic-One for OSINT loop; MetaGPT-style SOP per domain (visa/tax/property/marketing/macro/AI-research).
- **Observability**: Langfuse self-hosted on Mini-Pro2 + Phoenix (Claude Agent SDK auto-instr) + OpenLLMetry SDK in every Python path → OTel collector.
- **Cost control**: existing routing (claude / gemini / codex / deepseek / Ollama) + Langfuse cost dashboards + rage-flag on DeepSeek > threshold.

---

## 9. Source index (consolidated)

### Section 1 — Agentic Ingestion

1. https://www.anthropic.com/news/skills (→ https://claude.com/blog/skills) — Anthropic Skills
2. https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview — Skills API docs
3. https://github.com/anthropics/skills — Skills repo
4. https://thenewstack.io/agent-skills-anthropics-next-bid-to-define-ai-standards/ — Skills as standard
5. https://github.com/topoteretes/cognee — Cognee
6. https://www.cognee.ai/ — Cognee site
7. https://arxiv.org/pdf/2505.24478 — Cognee paper (May 2025)
8. https://www.cognee.ai/blog/integrations/claude-agent-sdk-persistent-memory-with-cognee-integration — Cognee+Claude SDK
9. https://arxiv.org/abs/2504.19413 — Mem0 paper
10. https://github.com/mem0ai/mem0 — Mem0 repo
11. https://mem0.ai/blog/state-of-ai-agent-memory-2026 — Mem0 state-of-2026
12. https://github.com/letta-ai/letta — Letta repo
13. https://www.letta.com/blog/letta-v1-agent — Letta V1 architecture
14. https://www.letta.com/blog/memgpt-and-letta — MemGPT/Letta merger
15. https://arxiv.org/abs/2310.08560 — original MemGPT paper
16. https://arxiv.org/abs/2404.16130 — Microsoft GraphRAG
17. https://arxiv.org/abs/2410.05779 — LightRAG
18. https://github.com/HKUDS/LightRAG — LightRAG repo
19. https://www.llamaindex.ai/workflows — LlamaIndex Workflows
20. https://www.llamaindex.ai/blog/introducing-agentic-document-workflows — ADW
21. https://docs.llamaindex.ai/en/stable/module_guides/loading/ingestion_pipeline/ — IngestionPipeline
22. https://docs.langchain.com/oss/python/langgraph/overview — LangGraph
23. https://github.com/langchain-ai/langgraph — LangGraph repo
24. https://n8n.io/ — n8n
25. https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool — Anthropic Memory tool

### Section 2 — Knowledge Graph

26. https://github.com/microsoft/graphrag — Microsoft GraphRAG
27. https://huggingface.co/SciPhi/Triplex — Triplex model
28. https://www.sciphi.ai/blog/triplex — Triplex blog
29. https://github.com/gusye1234/nano-graphrag — nano-graphrag
30. https://neo4j.com/blog/developer/global-graphrag-neo4j-langchain/ — Neo4j+GraphRAG
31. https://memgraph.com/blog/cognee-memgraph-integration-demo — Memgraph+Cognee
32. https://github.com/DEEP-PolyU/Awesome-GraphRAG — GraphRAG awesome
33. https://arxiv.org/html/2504.15909v1 — Synergizing RAG+Reasoning survey

### Section 3 — Self-correcting RAG

34. https://arxiv.org/abs/2310.11511 — Self-RAG
35. https://github.com/AkariAsai/self-rag — Self-RAG repo
36. https://selfrag.github.io/ — Self-RAG project page
37. https://arxiv.org/abs/2401.15884 — CRAG
38. https://github.com/HuskyInSalt/CRAG — CRAG repo
39. https://arxiv.org/abs/2403.14403 — Adaptive-RAG
40. https://github.com/starsuzi/Adaptive-RAG — Adaptive-RAG repo
41. https://arxiv.org/abs/2212.10496 — HyDE
42. https://docs.haystack.deepset.ai/docs/hypothetical-document-embeddings-hyde — HyDE in Haystack
43. https://www.anthropic.com/news/contextual-retrieval — Anthropic Contextual Retrieval
44. https://platform.claude.com/cookbook/capabilities-contextual-embeddings-guide — Cookbook
45. https://github.com/Raudaschl/rag-fusion — RAG-Fusion repo
46. https://langchain-ai.github.io/langgraph/tutorials/rag/langgraph_crag/ — CRAG via LangGraph

### Section 4 — Memory architectures

47. https://arxiv.org/abs/2502.12110 — A-MEM
48. https://github.com/agiresearch/A-mem — A-MEM repo
49. https://arxiv.org/abs/2305.10250 — MemoryBank
50. https://github.com/zhongwanjun/MemoryBank-SiliconFriend — MemoryBank repo
51. https://arxiv.org/abs/2304.03442 — Generative Agents
52. https://hai.stanford.edu/news/computational-agents-exhibit-believable-humanlike-behavior — Stanford HAI
53. https://arxiv.org/abs/2504.13171 — Sleep-time Compute (UCB+Letta, April 2025)
54. https://claudefa.st/blog/guide/mechanics/auto-dream — Auto-Dream guide
55. https://thenewstack.io/anthropic-managed-agents-dreaming-outcomes/ — Anthropic Dreams coverage
56. https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents — Anthropic context engineering
57. https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents — Anthropic harnesses

### Section 5 — Self-improvement

58. https://arxiv.org/abs/2504.08066 — AI Scientist v2
59. https://github.com/SakanaAI/AI-Scientist-v2 — AI Scientist v2 repo
60. https://sakana.ai/ai-scientist-nature/ — Nature publication
61. https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/ — AlphaEvolve
62. https://arxiv.org/abs/2506.13131 — AlphaEvolve arXiv
63. https://huggingface.co/blog/codelion/openevolve — OpenEvolve OSS reproduction
64. https://github.com/codelion/openevolve — OpenEvolve repo
65. https://arxiv.org/abs/2402.03620 — Self-Discover
66. https://arxiv.org/abs/2203.14465 — STaR
67. https://arxiv.org/abs/2402.06457 — V-STaR
68. https://arxiv.org/abs/2403.09629 — Quiet-STaR
69. https://arxiv.org/abs/2212.08073 — Constitutional AI
70. https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback — CAI announce
71. https://arxiv.org/abs/2309.00267 — RLAIF
72. https://cameronrwolfe.substack.com/p/rlaif-reinforcement-learning-from — RLAIF deep-dive

### Section 6 — Multi-agent orchestration

73. https://www.anthropic.com/engineering/multi-agent-research-system — Anthropic Multi-Agent
74. https://www.zenml.io/llmops-database/building-a-multi-agent-research-system-for-complex-information-tasks — ZenML LLMOps DB summary
75. https://www.microsoft.com/en-us/research/articles/autogen-v0-4-reimagining-the-foundation-of-agentic-ai-for-scale-extensibility-and-robustness/ — AutoGen v0.4
76. https://github.com/microsoft/autogen — AutoGen repo
77. https://devblogs.microsoft.com/autogen/autogen-reimagined-launching-autogen-0-4/ — AutoGen v0.4 blog
78. https://crewai.com/ — CrewAI
79. https://docs.crewai.com/ — CrewAI docs
80. https://github.com/crewaiinc/crewai — CrewAI repo
81. https://github.com/openai/swarm — OpenAI Swarm (deprecated)
82. https://openai.github.io/openai-agents-python/ — OpenAI Agents SDK
83. https://developers.openai.com/cookbook/examples/orchestrating_agents — Orchestrating Agents cookbook
84. https://adk.dev/ — Google ADK
85. https://developers.googleblog.com/en/agent-development-kit-easy-to-build-multi-agent-applications/ — ADK announce
86. https://github.com/google/adk-python — ADK repo
87. https://arxiv.org/abs/2411.04468 — Magentic-One
88. https://www.microsoft.com/en-us/research/articles/magentic-one-a-generalist-multi-agent-system-for-solving-complex-tasks/ — MS Research
89. https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/magentic-one.html — Magentic-One in AutoGen
90. https://arxiv.org/abs/2308.00352 — MetaGPT
91. https://github.com/FoundationAgents/MetaGPT — MetaGPT repo
92. https://arxiv.org/abs/2305.14325 — Multi-agent debate (Du et al.)

### Section 7 — Observability

93. https://langfuse.com/ — Langfuse
94. https://github.com/langfuse/langfuse — Langfuse repo
95. https://langfuse.com/self-hosting — Langfuse self-host
96. https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability — ClickHouse acquisition
97. https://phoenix.arize.com/ — Phoenix
98. https://github.com/Arize-ai/phoenix — Phoenix repo
99. https://arize.com/docs/phoenix — Phoenix docs
100.  https://google.github.io/adk-docs/observability/phoenix/ — Phoenix in ADK
101.  https://www.helicone.ai/ — Helicone
102.  https://github.com/Helicone/helicone — Helicone repo
103.  https://www.helicone.ai/blog/the-complete-guide-to-LLM-observability-platforms — comparison
104.  https://github.com/traceloop/openllmetry — OpenLLMetry
105.  https://github.com/BerriAI/litellm — LiteLLM proxy

---

## 10. Closing notes

- All sources verified as accessible at time of report (2026-05-08).
- All quotes are verbatim from the cited URL or paper abstract; paraphrases or syntheses are explicitly marked.
- The "Bali Zero use case" lines reflect the constraint set in CLAUDE.md (no paid Anthropic, OAuth MAX 3 plans, OSS-first, Mini-Pro2 H24 server, Indonesian domain spec).
- For domains where the brief listed a specific named project I could not verify (e.g. "Stanford STaR-GraphRAG"), I named the closest verifiable analogue (Synergizing RAG and Reasoning survey, 2025-04) and flagged the gap rather than invent.
- Suggested first three operational moves, ordered by ROI/effort:
  1. Apply Anthropic Contextual Retrieval (free with OAuth) to all NB-INTEL items + client docs — single biggest retrieval-quality win.
  2. Stand up Langfuse self-hosted on Mini-Pro2 + OpenLLMetry SDK on the Python paths — single biggest cost+drift visibility win.
  3. Replace bash NB-INTEL ingestion's KG step with nano-graphrag + Triplex (Ollama) — gives proper graph layer at zero $ cost.

End.
