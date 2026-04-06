# Nuzantara System Brief — Per Agenti AI Esterni

> Questo documento descrive il sistema Nuzantara/Bali Zero nella sua interezza.
> Scopo: permettere ad agenti AI esterni (Gemini, DeepSeek, xAI, NotebookLM) di
> analizzare il nostro stack e proporre enhancement tecnologici specifici.

---

## Identity

**Nuzantara** (brand: Bali Zero, AI persona: Zantara) — Production AI-powered business
intelligence platform per servizi business indonesiani (visa, company setup, tax, property).
5,000+ clienti, operativo da Bali, Indonesia.

**URL**: kita.balizero.com (workspace), my.balizero.com (portal clienti)

---

## Numbers

| Metrica                 | Valore                                                                                       |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| Clienti                 | 5,000+                                                                                       |
| App nel monorepo        | 20                                                                                           |
| Backend routers         | 90+                                                                                          |
| Backend services        | 257 files across 34 service directories                                                      |
| Communication channels  | 7 (WhatsApp, Telegram, Instagram, Web, X, GChat, Slack)                                      |
| MCP tools               | 131 (118 Nuzantara + 13 Advanced)                                                            |
| MCP workflow chains     | 8 deterministic automation chains                                                            |
| Qdrant vector documents | 93,283 across 10 live collections                                                            |
| Knowledge Graph nodes   | 56,113                                                                                       |
| Knowledge Graph edges   | 161,173                                                                                      |
| Frontend pages          | 84+ (SSG + dynamic)                                                                          |
| KBLI SSG pages          | 1,563                                                                                        |
| Test files              | 419                                                                                          |
| Embedding model         | text-embedding-3-small (1536 dims) — FROZEN, non cambiabile                                  |
| Backend LOC (key files) | orchestrator_core 1,124 + search_service 1,382 + reasoning 1,828 + service_initializer 1,195 |

---

## MACRO AREA 1: RAG Pipeline

**Cosa fa**: Riceve domande utente → classifica intent → cerca documenti → ragiona → genera risposta con citazioni.

**File chiave**:

- `services/rag/agentic/orchestrator_core.py` (1,124 righe) — orchestratore principale
- `services/rag/agentic/reasoning.py` (1,828 righe) — ragionamento + confidence enforcement
- `services/rag/confidence.py` (323 righe) — 6-factor evidence scoring
- `services/classification/intent_classifier.py` — classifica query in categorie

**Stack**: LangGraph (state machine), Gemini 2.5 Flash (LLM primario su Fly.io), Ollama (locale gemma4:26b)

**Pipeline**: Query → Intent Classification → Search (Qdrant hybrid) → Grade (LLM) → Generate (LLM) → Confidence Check → Response

**Confidence thresholds**: <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL

**Limitazioni note**:

- Gemini a volte risponde direttamente senza usare tools → confidence score = 0 → ABSTAIN anche su query valide (fixato con tools-available bypass)
- Scoring system progettato per tool-calling pipeline, non per LLM che rispondono diretto
- Orchestrator è monolitico (1,124 righe)

### Micro aree:

1. **Intent Classification** — keyword + regex, non ML. Funziona ma grezzo.
2. **Evidence Scoring** — 6 fattori (source count, tool usage, citation density, recency, agreement, specificity). Hardcoded thresholds.
3. **LLM Gateway** — multi-provider (Gemini, Ollama, OpenRouter). Pattern: Ollama locale → fallback Gemini API.
4. **Streaming** — SSE streaming per risposte real-time, accumulator pattern.
5. **Tool Calling** — 9 tools disponibili all'LLM (search, pricing, KBLI, legal, KG, etc.)

---

## MACRO AREA 2: Knowledge Graph

**Cosa fa**: Grafo di entità e relazioni estratte da documenti legali/regolamentari indonesiani. Usato per query strutturali (chi richiede cosa, cosa dipende da cosa).

**File chiave**:

- `services/knowledge_graph/` — extraction + query
- `services/rag/kg_subgraph_visa.py` — subgraph visa (KITAS, KITAP, VITAS)
- `services/rag/kg_subgraph_company.py` — subgraph company (PT PMA)

**Stack**: PostgreSQL (kg_nodes, kg_edges tables), asyncpg, LangGraph subgraphs

**Numeri**: 56,113 nodi, 161,173 edges. Top entity types: kbli (6,932), biaya (6,060), pasal (3,954), dokumen (3,674)

**Limitazioni note**:

- Confidence hardcoded a 0.9 su tutti i nodi (non riflette vera qualità)
- ~5,000 nodi orfani (14.5%) senza relazioni
- Estrazione batch (Gemini) disabilitata — troppo costosa (€230 per 37M chiamate)
- Subgraph property e tax non verificati

### Micro aree:

1. **KG Extraction** — batch via Gemini (disabilitato), incremental pipeline
2. **KG Query** — asyncpg su PostgreSQL, 4 subgraphs (visa, company, property, tax)
3. **KG-RAG Integration** — KG tool disponibile nell'orchestrator come tool #4

---

## MACRO AREA 3: Search & Retrieval

**Cosa fa**: Ricerca ibrida su 93K documenti vettoriali. BM25 (keyword) + Dense (semantic) + RRF (fusion) + CrossEncoder reranking.

**File chiave**:

- `services/search/search_service.py` (1,382 righe)

**Stack**: Qdrant (vettori, Fly.io), text-embedding-3-small (1536 dims), CrossEncoder reranking (abilitato 2026-03-24)

**Collections** (10 live su Fly.io):

- legal_unified_hybrid, visa_oracle, tax_genius_hybrid, kbli_atlas, training_conversations, property_intel, intel_articles, e altre

**Limitazioni note**:

- Embedding model FROZEN (text-embedding-3-small) — cambiarlo invalida 93K vettori
- Named vectors vs single vector: inconsistenza tra collection vecchie e nuove
- No late chunking o contextual retrieval — chunking standard

### Micro aree:

1. **Embedding** — OpenAI text-embedding-3-small, 1536 dims, $0.02/M tokens
2. **Hybrid Search** — BM25 sparse + dense vectors + Reciprocal Rank Fusion
3. **Reranking** — CrossEncoder (ms-marco-MiniLM-L6-v2), abilitato recentemente
4. **Collection Routing** — intent → collection mapping basato su classificazione

---

## MACRO AREA 4: Agentic Layer

**Cosa fa**: Orchestrazione agent-based con LangGraph. ReAct pattern, tool calling, multi-step reasoning.

**Stack**: LangGraph (StateGraph), 9 tools, Gemini 2.5 Flash / Ollama qwen3.5

**File chiave**:

- `app/agents/graph.py` — workflow LangGraph (retrieve → grade → generate)
- `services/rag/agentic/` — orchestrator, reasoning, llm_gateway

**Limitazioni note**:

- Single-agent (no multi-agent collaboration)
- No planning step (l'agente non pianifica prima di agire)
- No reflection/self-correction loop
- No memory across sessions (stateless per request)

---

## MACRO AREA 5: Communication Channels

**Cosa fa**: 7 canali di comunicazione, ciascuno con adapter + formatter + webhook.

| Canale      | Status   | Provider               |
| ----------- | -------- | ---------------------- |
| WhatsApp    | LIVE     | Meta Cloud API         |
| Telegram    | LIVE     | Bot API (@Balizerobot) |
| Instagram   | LIVE     | Meta webhook           |
| Web Chat    | LIVE     | SSE custom             |
| X/Twitter   | BROKEN   | CRC auth failure       |
| Google Chat | Scaffold | —                      |
| Slack       | Scaffold | —                      |

**Stack**: FastAPI webhooks, adapter pattern, channel_router.py

**Limitazioni note**:

- X/Twitter broken (CRC)
- Telegram: Pro polls, Air/Fly send only
- No unified conversation history across canali
- Ogni canale ha formatter separato (duplicazione)

---

## MACRO AREA 6: CRM & Business Logic

**Cosa fa**: Gestione clienti, practices (casi attivi), compliance, document management, automation engine.

**File chiave**:

- `app/routers/crm_enhanced.py` (2,028 righe) — CRUD clienti
- `app/routers/crm_clients.py` (1,928 righe) — client management
- `services/crm/` — 6 service files
- `scripts/crm_automation_engine.py` — 4 moduli: quality, docs, renewals, stale

**Stack**: PostgreSQL (asyncpg), RBAC (admin vs team member), Google Drive integration

**Numeri**: 5,000+ clienti, 2,070 companies, 1,803 company_docs

**Limitazioni note**:

- Router god files (2,028 righe crm_enhanced.py) — necessitano split
- Automation engine è script standalone, non integrato nel backend lifecycle
- No real-time notifications per cambiamenti CRM

---

## MACRO AREA 7: Intelligence Pipeline

**Cosa fa**: Scraping regolamentare → classificazione → editorial → pubblicazione → social monitoring.

**Componenti**:

- `apps/bali-intel-scraper/` — scraper (corre su Pro via OpenClaw, 03:00 WITA)
- `apps/war-room/` — pipeline giornalismo multi-stage (Grok→Qwen→Gemini→Claude→Canva)
- `services/social/x_monitor_service.py` — social listening X
- `services/article_composer/` — composizione articoli con Claude

**Stack**: OpenClaw cron, Exa API, xAI x_search (appena integrato), Gemini for SEO optimization

**Limitazioni note**:

- War Room pipeline complesso (8 stage, 10 minuti) — fragile
- Social monitor X mai attivato in produzione
- No real-time regulatory alert (solo batch notturno)

---

## MACRO AREA 8: Infrastructure

**Cosa fa**: Deploy, database, caching, monitoring.

| Componente  | Dove               | Specs                             |
| ----------- | ------------------ | --------------------------------- |
| Backend API | Fly.io (Singapore) | shared-cpu-2x, 2GB RAM, auto_stop |
| PostgreSQL  | Fly.io             | 2GB RAM                           |
| Qdrant      | Fly.io             | 2GB RAM, v1.17.0                  |
| Redis       | Upstash/Fly        | Cache                             |
| Frontend    | Vercel             | CDN + Edge                        |
| Ollama      | Pro locale         | gemma4:26b, qwen3.5:9b            |
| OpenClaw    | Pro/Air            | Agent runtime                     |

**Limitazioni note**:

- 2GB RAM su backend (cold start ~35s con auto_stop)
- PostgreSQL 2GB (era OOM, upgradato da 1GB)
- No Kubernetes, no horizontal scaling
- Single region (Singapore)

---

## MACRO AREA FRONTEND 1: Workspace (kita.balizero.com)

**Cosa fa**: CRM UI per il team, gestione clienti, omnichannel, documents, analytics.

**Stack**: Next.js App Router, TypeScript, Tailwind CSS, Framer Motion

**Pagine chiave**: /clients, /clients/[id], /omnichannel, /documents, /analytics, /hr

---

## MACRO AREA FRONTEND 2: Client Portal (my.balizero.com)

**Cosa fa**: Portale self-service per clienti. Visa status, companies, documents vault, tax, messages.

**Stack**: Next.js, 14 pagine authenticated, SSO cross-domain via httpOnly cookie

**Limitazioni note**:

- Cross-domain auth necessita fallback cookie (localStorage non funziona cross-subdomain)
- No real-time updates (polling manuale)

---

## MACRO AREA FRONTEND 3: KBLI Navigator

**Cosa fa**: 1,563 pagine SSG per codici classificazione business + AI explorer per search semantico.

**Stack**: Next.js SSG, 9.2MB JSON data source, AI chat con backend RAG

---

## MACRO AREA FRONTEND 4: Prime Intelligence

**Cosa fa**: Mappe 3D zoning Bali con overlay regolamentare (Green/Yellow/Pink zones).

**Stack**: Google Maps 3D (maps3d), PostGIS backend, bali_zoning_layers table

---

## MACRO AREA FRONTEND 5: Subdomain Ecosystem

6 Vercel apps: kita, mail, calendar, drive, knowledge, zantara
SSO via `nz_access_token` httpOnly cookie su `.balizero.com`

---

## MACRO AREA FRONTEND 6: Design System

**Stack**: BZ design tokens in `packages/core/styles/bz-tokens.css`
Palette: --bz-base #0c0c0e, --bz-accent #d4845a (warm depth)
Logo: BZLogo.tsx (balizero-logo-clean.png)

---

## MCP Ecosystem

- **nuzantara-mcp**: 118 tools, 10 prompts, 5 resources, 8 workflow chains
- **nuzantara-mcp-advanced**: 14 tools (Fly.io ops, diagnostics)
- **Workflow chains**: daily_ops_autopilot, new_client_onboarding, practice_lifecycle_check, intel_pipeline, weekly_report, client_health_monitor, compliance_autopilot, journey_accelerator

---

## Federation (AI Agent Orchestration)

**Agenti**: Claude Code (Opus 4.6), Gemini CLI (1M ctx), Codex CLI (sandbox), Claude CLI (review), DeepSeek R1 (reasoning), Aider (multi-model coding)
**Servizi**: NotebookLM, GWS CLI, OCR, Websearch, Canva
**Pipelines**: Core Guardian V3, Intel Scraper, War Room, SEO Guardian
**Dispatch**: `scripts/ai-dispatch.sh` v3 — 30+ commands

---

## Domande Aperte per gli Agenti

1. Il RAG pipeline (orchestrator 1,124 righe + reasoning 1,828 righe) è monolitico. Come scomporlo mantenendo performance?
2. L'embedding model è frozen (93K docs). Esistono tecniche per migliorare retrieval SENZA re-indexing?
3. Il Knowledge Graph ha 5K nodi orfani e confidence hardcoded. Come renderlo più utile?
4. L'agentic layer è single-agent, no planning, no reflection. Quali pattern 2026 adottare?
5. 7 canali di comunicazione ma no unified conversation history. Come unificare?
6. I router backend sono god files (2,028 righe). Qual è il pattern di split migliore per FastAPI?
7. 2GB RAM su Fly.io con auto_stop — come ottimizzare cold start e memory footprint?
8. Il frontend ha 6 subdomain Vercel. SSO cross-domain è fragile. Alternative?
9. MCP ha 131 tools ma nessun tool discovery/recommendation automatico. Come implementarlo?
10. La War Room pipeline (8 stage, 5 agenti AI) è fragile. Come renderla resiliente?
11. Qual è la combinazione di tecnologie 2026 che darebbe il massimo salto di qualità?
12. Dove il sistema è over-engineered? Dove è under-engineered?
