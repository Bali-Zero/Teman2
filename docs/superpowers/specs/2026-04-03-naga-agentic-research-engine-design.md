# Naga — Agentic Research Engine

**Date:** 2026-04-03
**Status:** Design Approved
**Author:** Zero + Claude Opus

---

## 1. Overview

Naga is Nuzantara's agentic research engine — a multi-model, multi-source, iterative research system that produces verified intelligence reports with actionable items.

**Name origin:** Naga — the serpent/dragon of Balinese mythology, symbol of depth and knowledge.

**Scope:** Optimized for Indonesian legal/business/immigration domain, but capable of general research on any topic on demand.

**Key differentiators vs commercial deep research (OpenAI, Google, Perplexity):**

- Domain-specialized Indonesia RAG (ask_legal, search_intel, search_kbli, NLM notebooks)
- Dual-model architecture: Opus orchestrates + synthesizes, Gemini bulk-reads (1M context)
- Claims DB as living knowledge base with supersession chains
- Actionable intelligence: auto-generates CRM alerts, article drafts, team notifications
- Zero marginal cost: runs entirely on flat-rate subscriptions (Claude Max x20, Google AI Ultra, Ollama local)

---

## 2. Architecture

### 2.1 High-Level Flow

```
ENTRY POINTS (MCP tool, FastAPI, CLI, Cron/OpenClaw)
       │
       ▼
NAGA GATEWAY — Complexity classifier + Domain router + TTL
  Model: Haiku / qwen3.5:9b (< 1s)
  Output: { tier, domain, mode, ttl_seconds }
       │
       ▼
NAGA ORCHESTRATOR (Claude Opus) — Iterative research loop
  1. Decompose query → sub-questions
  2. Plan search strategy per sub-question
  3. Dispatch to Search Agents (parallel)
  4. Receive results → CRAG-light evaluation
  5. If gaps → refine queries → re-dispatch
  6. Convergence check → stop or iterate
  7. Send accumulated sources to Gemini Bulk Reader
  8. Synthesize final report (multi-perspective for exhaustive)
  9. Generate artefacts + actionable items
       │
       ▼
OUTPUT LAYER — Report + Claims DB + Drive archive + Actions
```

### 2.2 Tier System

| Tier           | Latency  | Max searches | Max sources to Gemini | Max iterations | Models                                                          |
| -------------- | -------- | ------------ | --------------------- | -------------- | --------------------------------------------------------------- |
| **Flash**      | 5-15s    | 2-3          | 0 (no Gemini)         | 1              | Haiku classify + synthesize                                     |
| **Deep**       | 1-5 min  | 15-25        | 20                    | 2-3            | Haiku classify, Opus orchestrate + synthesize, Gemini bulk read |
| **Exhaustive** | 5-30 min | 50-80        | 50                    | 3-5            | Haiku classify, Opus orchestrate + synthesize, Gemini bulk read |

### 2.3 Domain Router (3-way)

| Signal                                                        | Path                             | Priority sources                                        |
| ------------------------------------------------------------- | -------------------------------- | ------------------------------------------------------- |
| **Indonesia domain** (visa, KBLI, pajak, PT PMA, regulasi...) | Domain Agent first, web for gaps | ask_legal, search_intel, NLM NB-2..8, Exa .go.id filter |
| **General knowledge** (tech, science, global business...)     | Web search only                  | Exa, Brave, academic APIs                               |
| **Hybrid** ("compare golden visa Indonesia vs Portugal")      | Both paths in parallel, merge    | Domain + Web                                            |

### 2.4 TTL by Channel

| Channel                | Default TTL | Tier constraint                          |
| ---------------------- | ----------- | ---------------------------------------- |
| Telegram               | 30s         | Forces flash (user can `/deep` override) |
| Web chat               | 60s         | Auto-upgrade to deep if complex          |
| Claude Code / OpenClaw | 1800s       | No practical limit                       |
| API / cron             | 3600s       | Exhaustive permitted                     |

---

## 3. Search Agents

Five specialized agents, dispatched selectively by the Orchestrator (not broadcast).

### 3.1 Exa Neural Agent

- **Tool:** `web_search_advanced_exa` + `crawling_exa`
- **When:** Always (general + indonesia)
- **Strategy:** Neural search → if <3 relevant results, reformulate → retry → crawl top-5 URLs
- **Output:** `[{url, title, content_md, relevance_score}]`

### 3.2 Brave Web Agent

- **Tool:** `brave_web_search` + `nuzantara-fetch`
- **When:** Always as diversifier (independent index from Exa)
- **Strategy:** Query → max 20 results → fetch top-5 full content
- **Output:** `[{url, title, content_md, freshness}]`

### 3.3 Indonesia Domain Agent

- **Tools:** `ask_legal` + `search_intel` + `search_kbli` + NLM `notebook_query` + `recall_similar` + Exa with `.go.id` domain filter
- **When:** domain = indonesia | hybrid
- **Strategy:**
  1. `ask_legal` for normativa/visa/tax
  2. `search_intel` for recent regulatory news
  3. `search_kbli` if business activity codes mentioned
  4. NLM `notebook_query` on relevant NB (2-8)
  5. Exa with domain filter `.go.id` for official gov sources
  6. `recall_similar` for validated interpretations from past episodes
- **Output:** `[{source, content, confidence, citations}]`

### 3.4 Academic Agent

- **Tools:** Semantic Scholar API + OpenAlex + arXiv API
- **When:** tier = exhaustive, or academic query detected
- **Strategy:**
  1. Semantic Scholar → relevance search + citation graph
  2. OpenAlex → broader coverage, open access full-text
  3. arXiv → recent preprints if tech/science topic
  4. Fetch abstracts + key findings via nuzantara-fetch
- **Output:** `[{doi, title, abstract, year, citations, key_findings}]`

### 3.5 Deep Crawl Agent (Reactive)

- **Tools:** `nuzantara-fetch` + `crawling_exa`
- **When:** Cycle 2+ only — Orchestrator identifies promising URLs from initial results
- **Never dispatched in cycle 1**
- **Strategy:** Full page fetch (up to 1M chars), multi-page handling, structured section extraction
- **Output:** `[{url, full_content_md, sections, metadata}]`

### 3.6 Cross-Iteration Dedup

- `url_history[]` persisted in NagaSession, checked before every fetch
- Content near-duplicate detection via simhash on fetched content
- Prevents circular/redundant searches across iterations

---

## 4. Quality Layer

Four-stage pipeline separating concerns by model capability.

### Stage 1: Source Scoring (Haiku — fast batch)

Per source:

- **credibility**: configurable by domain in `source_weights.json`
  - Default: `.go.id` = 0.9, paper DOI = 0.85, major news = 0.6, blog = 0.4, forum = 0.2
  - Per-domain overrides: `pajak.go.id` = 0.95, random kabupaten = 0.6
- **freshness**: <30d = 1.0, <1y = 0.7, <3y = 0.5, >3y = 0.3
- **relevance**: CRAG-light score from search cycle
- **source_score** = weighted combination → filter out < 0.3

### Stage 2: Gemini Bulk Read (Gemini 3 Pro — 1M context)

Input: top-N ranked sources (full content).

Structured prompt requesting:

1. Key facts per sub-question with `[SOURCE_ID]`
2. Contradictions between sources
3. Gaps — what is NOT covered
4. Quantitative data points (prices, dates, percentages)

Output: `evidence_map` JSON with per-sub-question facts, contradictions, gaps, data_points.

### Stage 3: Claim Extraction & Verification (Opus)

Per fact from evidence_map:

1. Extract atomic verifiable claim
2. Cross-reference: count independent supporting sources
3. Contradiction check: any source negating?
4. Temporal check: still valid? For normative claims, `valid_as_of` is **mandatory** — no date = auto-downgrade to UNVERIFIED
5. Assign verification level:

| Level      | Confidence | Criteria                                                             |
| ---------- | ---------- | -------------------------------------------------------------------- |
| VERIFIED   | 0.85-1.0   | 3+ concordant sources, no negation                                   |
| LIKELY     | 0.50-0.84  | 1-2 sources, no contradiction                                        |
| CONTESTED  | 0.30-0.49  | Sources in contradiction → report both positions + `resolution_hint` |
| UNVERIFIED | 0.15-0.29  | Single source, not independently verifiable                          |
| ABSTAIN    | —          | No source or all unreliable → NOT included in report, noted in gaps  |

**resolution_hint** for CONTESTED claims: Opus generates interpretive guidance based on freshness + credibility (e.g., "Source A (2024, gov) vs Source B (2022, blog) — A likely more current").

Compatible with existing RAG evidence scoring: <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL.

### Stage 4: Convergence Detector (Haiku — fast decision)

Metrics:

- **coverage**: % sub-questions with at least 1 VERIFIED or LIKELY claim
- **novelty**: new claims in last iteration / total claims (if <10% → saturation)
- **gap_severity**: are remaining gaps critical for the original query?
- **budget_remaining**: search calls remaining + TTL remaining

Decision:

- **CONVERGED**: coverage >80% AND novelty <10% → proceed to synthesis
- **ITERATE**: coverage <80% AND budget remaining → return to Orchestrator with gap list
- **TIMEOUT**: budget exhausted OR TTL reached → proceed with disclaimer

---

## 5. Synthesis & Output

### 5.1 Synthesis Engine (Opus)

**Flash:** Direct answer (1-3 paragraphs), inline citations `[1][2]`.

**Deep:** Structured report — executive summary + thematic sections + "Contradictions & Uncertainty" section + "Research Limitations" section. Citations with source quality indicators.

**Exhaustive:** Multi-perspective synthesis (STORM-style):

- 3+ perspectives chosen by Opus based on topic (e.g., legal/normative, practical/operational, comparative/international)
- Executive summary with aggregated confidence
- Evidence status map: `████ VERIFIED  ░░░ LIKELY  ╳╳╳ CONTESTED`
- Timeline of changes (if normative)
- Operational recommendations
- Appendix: all sources with scores + metadata

### 5.2 Artefact Generator

**All tiers:**

- Report Markdown → local file + response
- Session log → PostgreSQL `naga_sessions`

**Deep + Exhaustive:**

- Claims → PostgreSQL `naga_claims` (with confidence, valid_as_of, superseded_by)
- Sources → PostgreSQL `naga_sources` (with credibility_score, content_hash)
- Report → Google Drive `/Naga/reports/YYYY-MM/topic-slug.md`

**Exhaustive only:**

- NLM Upload → notebook "NB-NAGA" (report as source for future grounding)
- Audio Briefing → NLM `studio_create(audio)` → Drive `/Naga/audio/`
- Qdrant ingest → collection `naga_research` (chunks for future semantic queries)

### 5.3 Action Engine

Opus analyzes claims and decides if actions are needed.

**Trigger types:**

| Trigger                                       | Action                                                | Trust level                                  |
| --------------------------------------------- | ----------------------------------------------------- | -------------------------------------------- |
| VERIFIED claim impacting clients              | `get_expiry_alerts()` → draft email → Telegram notify | notify=auto, email=auto-draft, send=approval |
| VERIFIED newsworthy claim                     | `compose_article()` draft → `publish_intel()` staging | draft=auto, publish=approval                 |
| Unresolved contradiction on active regulation | Escalation → `shared/escalations.json` → Telegram     | auto                                         |
| Critical gap on Indonesia domain              | `submit_scraper_job()` → schedule follow-up 48h       | auto                                         |

**trusted_mode stratification:**

- `notify` (Telegram alerts): auto-execute always
- `draft` (email drafts, article drafts): auto-execute in trusted_mode
- `publish` / `send` (email send, intel publish): always requires approval

All actions output as `action_items[]` with type + payload + rationale.

---

## 6. Conversational Mode

When Gateway classifies mode=conversational (complex queries, ambiguous scope):

1. Orchestrator presents sub-topics found and asks user to prioritize
2. User can: confirm all, select subset, reorder priority, add new angles
3. Research executes with state persisted in `NagaSession`
4. Intermediate results presented with verification levels
5. User can: "go deeper on X" → delta-merge into existing evidence_map (no full re-research)
6. Final report generated when user says "enough" or convergence detected

**State management:** `naga_sessions.parent_session_id` chains conversational turns. Each turn creates a child session inheriting the parent's evidence_map. Evidence_map is cumulative — new sources merge incrementally. Each session remains immutable.

Also used for 48h follow-up research: the follow-up session is a child of the original.

---

## 7. Database Schema

### naga_sessions

```sql
CREATE TABLE naga_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_session_id UUID REFERENCES naga_sessions(id),
    query TEXT NOT NULL,
    tier VARCHAR(20) NOT NULL,        -- flash/deep/exhaustive
    domain VARCHAR(20) NOT NULL,      -- indonesia/general/hybrid
    mode VARCHAR(20) NOT NULL,        -- oneshot/conversational
    channel VARCHAR(30),              -- telegram/claude_code/openclaw/api/cron
    ttl_seconds INTEGER,
    trusted_mode BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'running',

    -- Metrics
    duration_ms INTEGER,
    iterations INTEGER DEFAULT 0,
    search_calls INTEGER DEFAULT 0,
    sources_found INTEGER DEFAULT 0,
    claims_extracted INTEGER DEFAULT 0,
    avg_confidence FLOAT,

    -- Output
    report_markdown TEXT,
    report_drive_path TEXT,
    action_items JSONB DEFAULT '[]',

    -- Conversational state
    evidence_map JSONB,
    sub_questions JSONB,
    url_history TEXT[],

    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

### naga_sources

```sql
CREATE TABLE naga_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES naga_sessions(id),
    url TEXT NOT NULL,
    title TEXT,
    domain VARCHAR(255),
    source_type VARCHAR(20),          -- web/gov/academic/internal/blog
    credibility_score FLOAT,
    freshness_date DATE,
    content_hash VARCHAR(64),
    content_archived BOOLEAN DEFAULT FALSE,
    drive_archive_path TEXT,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE(url, session_id)
);
```

### naga_claims

```sql
CREATE TABLE naga_claims (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES naga_sessions(id),
    claim_text TEXT NOT NULL,
    domain VARCHAR(20),
    topic_tags TEXT[],

    -- Verification
    verification_level VARCHAR(20),   -- VERIFIED/LIKELY/CONTESTED/UNVERIFIED
    confidence FLOAT,
    source_ids UUID[],
    cross_ref_count INTEGER,

    -- Temporal
    valid_as_of DATE,                 -- MANDATORY for normative claims
    expires_at DATE,

    -- Contestation
    resolution_hint TEXT,
    contradicting_source_ids UUID[],

    -- Lifecycle
    superseded_by UUID REFERENCES naga_claims(id),
    superseded_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Indexes

```sql
CREATE INDEX idx_naga_claims_domain ON naga_claims(domain);
CREATE INDEX idx_naga_claims_topic ON naga_claims USING GIN(topic_tags);
CREATE INDEX idx_naga_claims_confidence ON naga_claims(confidence DESC);
CREATE INDEX idx_naga_claims_valid ON naga_claims(valid_as_of DESC);
CREATE INDEX idx_naga_claims_verification ON naga_claims(verification_level);
CREATE INDEX idx_naga_sources_url ON naga_sources(url);
CREATE INDEX idx_naga_sources_hash ON naga_sources(content_hash);
CREATE INDEX idx_naga_sessions_parent ON naga_sessions(parent_session_id);
CREATE INDEX idx_naga_sessions_status ON naga_sessions(status);
```

---

## 8. Infrastructure

### 8.1 Code Location

```
apps/naga/                         ← New app in monorepo
├── engine/
│   ├── gateway.py                 # Router + classifier
│   ├── orchestrator.py            # Main loop (Opus)
│   ├── search_agents/
│   │   ├── exa_agent.py
│   │   ├── brave_agent.py
│   │   ├── domain_agent.py        # Indonesia specialist
│   │   ├── academic_agent.py
│   │   └── crawl_agent.py         # Deep crawl (reactive, cycle 2+)
│   ├── quality/
│   │   ├── source_scorer.py
│   │   ├── crag_light.py          # Fast relevance gate
│   │   ├── crag_deep.py           # Full claim verification
│   │   ├── claim_extractor.py
│   │   └── convergence.py
│   ├── synthesis/
│   │   ├── report_writer.py       # Opus synthesis
│   │   ├── perspectives.py        # Multi-perspective gen
│   │   └── templates/             # Report templates per tier
│   ├── actions/
│   │   ├── action_engine.py       # Trigger detector
│   │   ├── crm_actions.py         # Client impact alerts
│   │   ├── intel_actions.py       # Publish/compose
│   │   └── followup_actions.py    # Self-healing gaps
│   ├── readers/
│   │   ├── gemini_reader.py       # Bulk read via Gemini CLI
│   │   └── academic_apis.py       # Semantic Scholar, OpenAlex, arXiv
│   ├── state/
│   │   ├── session.py             # NagaSession object
│   │   ├── budget_tracker.py      # Cost + calls tracker
│   │   ├── url_history.py         # Cross-iteration dedup
│   │   └── domain_weights.py      # Loads source_weights.json
│   └── config/
│       ├── naga_config.py         # Tier budgets, TTLs, thresholds
│       └── source_weights.json    # Configurable domain credibility
├── db/
│   ├── models.py                  # SQLAlchemy models
│   └── migrations/                # Alembic
├── tests/
│   ├── test_gateway.py
│   ├── test_orchestrator.py
│   ├── test_quality.py
│   └── test_integration.py
└── README.md
```

MCP tool registration in `apps/nuzantara-mcp/` (imports from `apps/naga/engine/`).

FastAPI router in `apps/backend-rag/backend/app/routers/naga.py`.

### 8.2 Entry Points

1. **MCP Tool** (primary): `naga_research(query, tier, domain, mode, trusted_mode)` — registered in nuzantara-mcp, invocable from Claude Code, OpenClaw, any MCP client
2. **FastAPI**: `POST /api/naga/research`, `GET /api/naga/session/{id}`, `GET /api/naga/claims/search` — for web chat, Telegram, client-facing channels
3. **CLI**: `python -m apps.naga.engine.orchestrator "query" --tier deep` — for debug, testing, cron
4. **Cron/OpenClaw**: Nightly exhaustive on topic watchlist, triggered by intel_scraper or T4 monitor

### 8.3 Integration Map

**Naga consumes:** ask_legal, search_intel, search_kbli, recall_similar, NLM notebook_query (NB-2..8), Exa MCP, Brave MCP, nuzantara-fetch, WebSearch, Gemini CLI

**Naga produces to:** PostgreSQL (sessions/sources/claims), Google Drive (30TB archive), NLM NB-NAGA, Qdrant naga_research collection, compose_article, publish_intel, get_expiry_alerts, send_email drafts, Telegram notifications, shared/escalations.json

**Naga is consumed by:** Claude Code, OpenClaw, Telegram bot, Web chat, intel_scraper (trigger), T4 monitor (trigger), future Zantara client-facing channels

### 8.4 Relationship with Existing Pipeline

Naga complements (does not replace) `apps/evaluator/nlm_deep_research/`. The existing pipeline is a specialized cron batch for NLM NB-2 with claim extraction. Naga is on-demand, multi-source, multi-output. Natural convergence: T4 monitor may become a trigger for Naga rather than operating independently.

---

## 9. Research Foundation

This design is informed by a comprehensive survey of the state of the art (April 2026):

**Commercial systems studied:** OpenAI Deep Research (o3), Google Gemini Deep Research, Perplexity Deep Research, Anthropic multi-agent research, xAI Grok DeepSearch

**Open-source frameworks studied:** STORM (Stanford), GPT-Researcher, LangChain Open Deep Research, HuggingFace smolagents, CrewAI, AutoGen/AG2, Auto-Deep-Research (HKUDS)

**Academic patterns incorporated:**

- CRAG (Corrective RAG) — retrieval evaluation + web fallback (arXiv:2401.15884)
- Self-RAG — adaptive retrieval with reflection tokens (ICLR 2024)
- Adaptive-RAG — complexity-based routing (NAACL 2024)
- RAPTOR — recursive tree retrieval (ICLR 2024)
- GraphRAG — community summaries (Microsoft, arXiv:2404.16130)
- STORM — perspective-guided multi-turn QA (Stanford)
- DeepTRACE — 8-dimensional research quality evaluation
- DR Tulu — RL-trained research with evolving rubrics (Allen AI)
- BATS — budget-aware tool-use scaling

**Search APIs evaluated:** Exa, Tavily, Brave, SerpAPI, Serper, You.com, Jina AI, Firecrawl, OpenAlex, Semantic Scholar, arXiv API, Crossref, CORE

**Key architectural decisions:**

1. Multi-agent orchestrator-worker (Anthropic pattern: 90% improvement) over single-agent
2. Dual-model (Opus reasoning + Gemini bulk reading) over single-model
3. Adaptive routing by domain over uniform search
4. Iterative convergence over fixed-depth
5. Claims DB as living knowledge base over ephemeral reports
6. Flat-rate models over per-token APIs (zero marginal cost)

---

## 10. Pipeline Convergence — Naga Absorbs Intel Scraper + War Room

Naga is not just a research tool — it becomes the central intelligence brain that subsumes existing pipelines.

### Current State (3 separate pipelines)

| Pipeline          | Schedule         | What it does                                                      |
| ----------------- | ---------------- | ----------------------------------------------------------------- |
| Intel Scraper     | 03:00 WITA daily | Scrape regulatory sources → publish articles → post-publish queue |
| T4 Social Monitor | Every 6h         | RSS/social → 3-layer filter → SVS scoring → NLM NB-2 ingest       |
| War Room          | On-demand        | Ops dashboard + Canva automation + team briefing                  |

### Target State (unified under Naga)

```
Naga Continuous Intelligence
  ├── Monitor (ex-T4): watches sources, triggers deep research on novelty
  ├── Scrape (ex-Intel Scraper): URL source list becomes a Search Agent
  ├── Verify: every finding goes through 4-stage Quality Pipeline
  ├── Publish: Action Engine handles article composition + staging
  ├── Brief (ex-War Room): nightly exhaustive generates team briefing from Claims DB
  └── Alert: client impact detection across all channels
```

### Migration Path (non-destructive)

| Phase | Change                                                                                                                                                               | Risk                                      |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| v1    | Naga on-demand. Existing pipelines unchanged.                                                                                                                        | Zero — additive only                      |
| v2    | T4 monitor triggers Naga deep instead of direct NLM ingest. T4 still fetches/filters, but hands off to Naga for verification + storage.                              | Low — T4 becomes thinner, not deleted     |
| v3    | Intel Scraper's source list becomes a Naga Search Agent. Scraper still crawls, but Naga orchestrates when/what/why. Post-publish queue reads from Naga action_items. | Medium — requires careful wiring          |
| v4    | War Room briefing generated by Naga nightly exhaustive. Claims DB replaces manual dashboard queries. Audio briefing via NLM studio.                                  | Low — new output format, same data        |
| v5    | Full convergence. Intel Scraper and T4 are thin adapters feeding Naga. War Room is a view on Claims DB.                                                              | Complete — old code becomes adapter layer |

---

## 11. Autonomy — Self-Learning and Self-Direction

This is what makes Naga qualitatively different from any commercial or open-source research system. Naga doesn't just answer questions — it learns from every research cycle and decides what to investigate next.

### 11.1 Claims DB as Cumulative Memory

Every research session deposits verified claims into PostgreSQL. Over time:

| Timeline | Claims   | Effect                                                             |
| -------- | -------- | ------------------------------------------------------------------ |
| Day 1    | 0        | Pure external search for everything                                |
| Day 30   | ~500     | Common Indonesia questions answered from DB in <1s                 |
| Day 180  | ~5,000   | 80% of recurring queries hit cached verified claims                |
| Day 365  | ~15,000+ | Most comprehensive Indonesia business intelligence DB in existence |

The `superseded_by` chain creates temporal awareness — Naga knows not just what is true NOW, but what WAS true and WHEN it changed. This enables:

- Trend detection: "KITAS fees have increased 3 times in 18 months"
- Regulatory velocity: "This ministry changes policy every 4 months on average"
- Reliability profiling: "This source published the fee change 2 weeks before the official gazette"

### 11.2 Source Weight Auto-Calibration

Initial source weights (`source_weights.json`) are human-configured. Over time, Naga adjusts them based on observed accuracy:

```
Event: Naga finds claim C from Source X (confidence 0.7)
  → Later research confirms C from 3 independent gov sources
  → Source X was correct → credibility_adjustment += 0.02

Event: Naga finds claim D from Source Y (confidence 0.6)
  → Later research contradicts D with gov gazette
  → Source Y was wrong → credibility_adjustment -= 0.05
```

Implementation: `naga_source_track` table tracks per-domain accuracy over time. Monthly recalculation updates `source_weights.json`. Human review gate: auto-adjustments > 0.1 require approval.

```sql
CREATE TABLE naga_source_track (
    id SERIAL PRIMARY KEY,
    source_domain VARCHAR(255) NOT NULL,
    claim_id UUID REFERENCES naga_claims(id),
    outcome VARCHAR(20),  -- confirmed / contradicted / superseded
    weight_delta FLOAT,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 11.3 Gap-Driven Self-Research

Every research session produces gaps — things Naga could not find. Currently logged and forgotten. With autonomy:

```
Research completes → gaps[] = ["No source found for PP 12/2026"]
  │
  ▼
Gap Analyzer (runs post-session):
  1. Classify gap severity: critical (active regulation) / medium (background) / low (nice-to-know)
  2. For CRITICAL gaps:
     a. Add topic to naga_watchlist table
     b. Submit scraper job for likely sources (jdih.kemenkumham.go.id, peraturan.bpk.go.id)
     c. Schedule follow-up Naga deep in 48h (child session of original)
  3. For MEDIUM gaps:
     a. Add to watchlist with weekly check frequency
  4. For LOW gaps:
     a. Log only — no action
```

```sql
CREATE TABLE naga_watchlist (
    id SERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    source_session_id UUID REFERENCES naga_sessions(id),
    gap_text TEXT,
    severity VARCHAR(20),  -- critical / medium / low
    check_frequency_hours INTEGER DEFAULT 48,
    last_checked_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolved_by_session_id UUID REFERENCES naga_sessions(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 11.4 Proactive Research (v5 — Full Autonomy)

At full maturity, Naga doesn't wait to be asked. It decides what to research based on:

1. **Watchlist items** due for re-check
2. **Expiring claims** — claims with `expires_at` approaching need re-verification
3. **High-velocity domains** — topics where claims get superseded frequently deserve more frequent monitoring
4. **Client portfolio signals** — if a new client is onboarded with KITAS, Naga proactively monitors KITAS regulatory changes

**Nightly Autonomous Cycle:**

```
02:00 WITA: Naga Autonomous Scheduler runs
  1. Query watchlist for items due → dispatch deep research per item
  2. Query claims expiring in 30 days → re-verify
  3. Query high-churn topics (>3 supersessions/month) → monitoring pass
  4. Generate morning briefing from overnight findings
  5. Push briefing to Telegram + NLM audio

06:00 WITA: Team receives briefing:
  "Overnight: 3 regulatory changes detected, 12 claims updated,
   2 gaps resolved, 1 client impact alert (Eduardo — KITAS fee change).
   Full report: /Naga/reports/2026-04/daily-2026-04-04.md"
```

### 11.5 Topic Graph (v5+ — Knowledge Graph Evolution)

As Claims DB grows, relationships between claims form a graph:

```
[Golden Visa] ──requires──→ [Investment $350K]
     │                            │
     ├──alternative_to──→ [KITAS Investasi]
     │                            │
     └──regulated_by──→ [PP 40/2024] ──amends──→ [PP 28/2019]
                                                       │
                                                  ──impacts──→ [12 clients]
```

When any node changes, Naga propagates impact through the graph:

- PP changed → Golden Visa rules changed → investment threshold changed → 12 clients affected → alert

Implementation: extend `naga_claims` with a `naga_claim_relations` table:

```sql
CREATE TABLE naga_claim_relations (
    id SERIAL PRIMARY KEY,
    source_claim_id UUID REFERENCES naga_claims(id) ON DELETE CASCADE,
    target_claim_id UUID REFERENCES naga_claims(id) ON DELETE CASCADE,
    relation_type VARCHAR(50),  -- requires / alternative_to / regulated_by / amends / impacts
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_claim_id, target_claim_id, relation_type)
);
```

---

## 12. Autonomy Roadmap

| Version | Capability                                                                                                                           | Dependencies                                     | Timeline  |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------ | --------- |
| **v1**  | On-demand research. Claims DB passive storage. Gateway + Orchestrator + 5 agents + Quality Pipeline + Report Writer + Action Engine. | Phase 1-4 of implementation plan                 | Week 1-2  |
| **v2**  | T4 as trigger. Gap follow-up (48h auto-schedule). Watchlist table.                                                                   | v1 complete + naga_watchlist table               | Week 3-4  |
| **v3**  | Source weight auto-calibration. Claim supersession detection. Intel Scraper as Naga agent.                                           | v2 + naga_source_track table                     | Month 2   |
| **v4**  | War Room briefing from Claims DB. Audio briefing via NLM. Qdrant naga_research collection for semantic claim search.                 | v3 + NLM integration + Qdrant collection         | Month 2-3 |
| **v5**  | Full autonomy: proactive research, expiring claim re-verification, client portfolio monitoring, morning briefing, topic graph.       | v4 + naga_claim_relations + autonomous scheduler | Month 3-4 |

---

## 13. Cost Model

### Zero-Budget (current design)

| Resource              | Cost                                | Notes                             |
| --------------------- | ----------------------------------- | --------------------------------- |
| Claude Max x20        | Flat (already paid)                 | Opus + Sonnet + Haiku unlimited   |
| Google AI Ultra       | Flat (already paid)                 | Gemini 3 Pro unlimited            |
| Ollama local          | Free                                | qwen3.5, gemma3, deepseek-r1      |
| Brave Search          | Free tier ~1K/month                 | Sufficient for diversifier role   |
| Academic APIs         | Free                                | Semantic Scholar, OpenAlex, arXiv |
| PostgreSQL            | Existing Fly.io                     | naga tables in same DB            |
| Google Drive 30TB     | Existing (antonellosiano@gmail.com) | Archive storage                   |
| **Total incremental** | **$0/month**                        |                                   |

### Optional Budget Tiers

| Budget  | Tools Added                            | Impact                                                |
| ------- | -------------------------------------- | ----------------------------------------------------- |
| $50/mo  | Exa Pro ($49)                          | +40% web search quality — single highest-ROI upgrade  |
| $100/mo | + Tavily ($30) + Firecrawl ($16)       | 3 independent search indices + authenticated crawling |
| $200/mo | + You.com ($100) + Jina Reranker ($20) | Flash tier accuracy boost + neural reranking          |

Recommendation: Start at $0. After 2 weeks of real usage, evaluate where Naga fails. Most likely gap: general web search quality → add Exa at $49/mo.
