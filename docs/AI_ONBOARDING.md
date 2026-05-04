# AI ONBOARDING GUIDE - Nuzantara Project

**Last Updated:** 2026-04-10
**Purpose:** Technical reference for AI assistants. For behavioral rules, see `CLAUDE.md`. For the founding principles of the organism, see `SYMBIOSIS.md` (monorepo root).

<!-- DOCSYNC:QUICK_NUMBERS_START -->
`257 routers · 534 services · 905 tests · 12 Qdrant collections · 104,154 vectors · 108,068 KG nodes`
<!-- DOCSYNC:QUICK_NUMBERS_END -->

> **Role split:** `CLAUDE.md` = how to act (rules, delegation, language, deploy QA). This file = how to build (architecture, code patterns, debugging, workflows).

---

## QUICK START

**1. Identify machine + verify setup:**

```bash
echo "Machine: $(whoami)@$(hostname)" && \
OTHER=$(if [ "$(whoami)" = "nuzantara" ]; then echo "air"; else echo "pro"; fi) && \
ssh -o ConnectTimeout=3 $OTHER 'echo "Peer: $(whoami)@$(hostname)"' 2>/dev/null || echo "Peer: UNREACHABLE"
```

- `nuzantara@Nuzantara` → **Pro** (48GB, dev) | `antonellosiano@Nuzantara-9` → **Air** (16GB, server H24)
- Always prefix first response with **[Pro]** or **[Air]**

**2. Verify backend works:**

```bash
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('✅ Import chain OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_confidence.py -q --tb=no && echo "✅ Tests OK"
```

**3. Confirm you know** (see `CLAUDE.md §3` for full Golden Rules):

- [ ] Virtualenv: `.venv` (NEVER `venv/` or system Python)
- [ ] Absolute imports, async-first (`httpx`), type hints, `logger` not `print()`
- [ ] Embedding model `text-embedding-3-small` is **FROZEN** (93,283 vectors depend on it)

---

## CRITICAL KNOWLEDGE (PREVENTS REAL BUGS)

### Embedding Model — FROZEN

All vectors use `text-embedding-3-small` (1536 dims). Changing it invalidates 93,283 existing vectors.

```bash
curl https://nuzantara-rag.fly.dev/health | jq '.embeddings.model'  # Must be "text-embedding-3-small"
fly secrets list -a nuzantara-rag | grep EMBEDDING_MODEL
```

**Incident:** Was set to `text-embedding-ada-002` (fixed 2026-02-06). Caused silent search quality degradation.

### KBLI Collection — Flat Payload

The `kbli_2025_final` collection has a **flat payload** (NOT nested under `metadata`/`text`):

```json
{
  "kode_kbli": "56101",
  "judul": "Restoran",
  "content": "...",
  "sektor_id": "I",
  "pma_status": "Terbuka",
  "skala_usaha": "Menengah",
  "kategori_risiko": "Menengah Rendah"
}
```

- `SearchService.search_collection()` assumes nested — **do NOT use for KBLI**
- KBLI router queries Qdrant directly via `_search_kbli_qdrant()`
- Router: `backend/app/routers/kbli_notebook.py` (public, no auth)
- Qdrant is source of truth for `pma_status` and `kategori_risiko` (not PostgreSQL KG)

### Auth Middleware

**File:** `backend/middleware/hybrid_auth.py` — 40 public endpoint patterns.

Key public: `/api/v1/kbli-notebook/`, `/health`, `/webhook/*`, `/api/agentic-rag/stream`, `/api/blog/`, `/api/auth/*/login`
Protected infra: `/docs`, `/openapi.json`, `/redoc`, `/metrics` (require admin API key)
Agentic RAG (`/api/agentic-rag/query`) requires JWT.

### Evidence Scoring (TWO systems — don't confuse them)

**System 1 — Response behavior** (`reasoning.py`): Decides what Zantara says to the user.

| Score     | Action                         | Threshold           |
| --------- | ------------------------------ | ------------------- |
| < 0.15    | ABSTAIN (refuse to answer)     | Too uncertain       |
| 0.15-0.60 | CAUTIOUS (answer + disclaimer) | Low confidence      |
| > 0.60    | NORMAL (confident answer)      | Sufficient evidence |

**Bypass:** If LLM had tools and produced an answer, trust it (fixes English query ABSTAIN bug).
**Trusted tools** (bypass evidence check): `calculator`, `get_pricing`, `team_knowledge`.

**System 2 — KG confidence** (`confidence.py`): Rates Knowledge Graph chain quality.

| Level    | Score   | Meaning      |
| -------- | ------- | ------------ |
| High     | >= 0.80 | Strong chain |
| Medium   | >= 0.55 | Decent chain |
| Low      | >= 0.35 | Weak chain   |
| Very Low | < 0.35  | Unreliable   |

6-factor scoring: chain base (30%), entity confidence (20%), relationship strength (20%), multi-source boost (15%), recency (10%), intent clarity (5%).

---

## PROJECT STRUCTURE

```
apps/backend-rag/
├── backend/
│   ├── app/                # ⚠️ FastAPI app (routers, services, setup)
│   │   ├── routers/        # 88 router files
│   │   ├── services/       # App-level services (CRM, auth)
│   │   ├── setup/          # app_factory, router_registration, service_initializer
│   │   ├── dependencies.py # ⚠️ Imported by ALL routers — test before deploy
│   │   └── main_cloud.py   # Fly.io entrypoint
│   ├── services/           # Core business logic (244 total)
│   │   ├── rag/agentic/    # Orchestrator, ReAct, LLM Gateway
│   │   └── knowledge_graph/ # KG extraction + query
│   ├── channels/           # 7: whatsapp, telegram, instagram, twitter, web, gchat, slack
│   ├── prompts/            # ⭐ zantara_core.py = Single Source of Truth
│   ├── llm/                # Gemini, Ollama, OpenRouter clients
│   ├── middleware/          # Auth, rate-limit, tracing
│   └── migrations/         # Alembic (up to 060)
├── tests/                  # 385 test files
└── .venv/                  # Python virtualenv (ALWAYS .venv)
```

**Key detail:** Routers are in `backend/app/routers/`, NOT `backend/routers/`. Services span both `backend/services/` (core) and `backend/app/services/` (app-level). Router registration is in `backend/app/setup/router_registration.py`, NOT `main_cloud.py`.

---

## QDRANT COLLECTIONS

10 live on Fly.io (93,283 docs). Config: `backend/services/ingestion/collection_manager.py`.

**Search Pipeline (ENABLED 2026-03-24):** Hybrid search (BM25 sparse + Dense vector + RRF fusion) → CrossEncoder reranking (ms-marco-MiniLM-L-6-v2, top-20→top-5). Flags: `ENABLE_HYBRID_SEARCH=true`, `ENABLE_RERANKER=true`, `ENABLE_BM25=true`, `ENABLE_QUERY_EXPANSION=true`.

| Collection                      | Docs    | Purpose                       |
| ------------------------------- | ------- | ----------------------------- |
| `collective_memories`           | dynamic | Conversation memories         |
| `bali_zero_pricing_hybrid`      | 29      | Service pricing               |
| `bali_zero_team`                | 22      | Team profiles                 |
| `visa_oracle`                   | 1,612   | Visa requirements             |
| `kbli_2025_final`               | 8,886   | KBLI codes (**FLAT payload**) |
| `tax_genius`                    | 895     | Tax knowledge                 |
| `legal_unified`                 | 5,041   | Legal documents               |
| `legal_unified_hybrid`          | 47,959  | Legal hybrid search           |
| `tax_genius_hybrid`             | 332     | Tax hybrid search             |
| `training_conversations_hybrid` | 2,898   | Training data                 |
| `immigration_circulars`         | 4       | Immigration circulars         |

**Aliases:** `legal_architect`, `kb_indonesian`, `kbli_comprehensive`, `zantara_books`, `cultural_insights`, `tax_updates`, `tax_knowledge`, `property_listings`, `property_knowledge`, `legal_updates`, `legal_intelligence`.

---

## CHAT STREAMING

**Endpoint:** `POST /api/agentic-rag/stream` (SSE)

- Timeout: 120s request, 300s idle, 600s max
- 13+ event types (token, sources, metadata, thinking, tool_call, reasoning_step, etc.)
- Vision support (base64 images), conversation persistence, correlation ID tracing
- Frontend: `useChatStreaming.ts` → `api.sendMessageStreaming()`

---

## LANGGRAPH KNOWLEDGE GRAPH

**Status:** ✅ ENABLED in production (2026-03-24) · 82/82 tests passing · `ENABLE_KG_LANGGRAPH=true` on Fly.io

**5 Core Nodes:** understand_query → resolve_entities → traverse_graph → reason_over_graph → synthesize_workflow

**4 Domain Subgraphs:** Company (PT PMA, CV), Visa (KITAS, KITAP), Property (Hak Pakai, HGB), Tax (PPh, PPN, NPWP)

| File                                                              | Purpose              |
| ----------------------------------------------------------------- | -------------------- |
| `backend/services/rag/kg_graph_state.py`                          | State definitions    |
| `backend/services/rag/kg_graph_nodes.py`                          | 5 core nodes         |
| `backend/services/rag/kg_langgraph_orchestrator.py`               | StateGraph + routing |
| `backend/services/rag/kg_subgraph_{company,visa,property,tax}.py` | Domain subgraphs     |
| `backend/services/rag/confidence.py`                              | 6-factor scoring     |

**Integration:** 3-way parallel in `orchestrator_core.py`: Entity Extraction + KG Legacy + KG LangGraph

**Performance:** Subgraph <350ms, 3-hop traversal <500ms, full pipeline <3s

---

## CRITICAL FIXES & KNOWN ISSUES

### Lazy Loading (Fly.io Startup)

Heavy imports deferred to background init. Health returns `"initializing"` (HTTP 200) while loading.

Key files: `app_factory.py` (background init), `service_initializer.py` (lazy imports), `router_registration.py` (lazy router imports), `Dockerfile` (--workers 1, DO NOT change).

### Date Conversion (asyncpg)

```python
date_value = row['date_field'].isoformat() if row['date_field'] else None
```

### Rogue AI Changes

Other AI tools (Gemini, Windsurf, Cursor) have broken production by removing "unused" imports. **2026-02-16 Incident:** `Any` removed from `dependencies.py` → entire app crashed.

Test debt cleaned (2026-03-20): 0 failed, 0 errors. Core Guardian V3 runs every 3h for deterministic fixes.

---

## DEBUGGING

```bash
# Evidence scoring
fly logs -a nuzantara-rag | grep -E "Evidence|Trusted|ABSTAIN"

# Embedding model
curl -s https://nuzantara-rag.fly.dev/health | python3 -m json.tool | grep model

# Import errors → activate venv + PYTHONPATH
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -m backend.scripts.script_name

# Fly.io crashes (common: missing PORT, QDRANT_URL, DATABASE_URL, or --workers 2)
fly logs -a nuzantara-rag
fly ssh console -a nuzantara-rag
```

---

## ENVIRONMENT VARIABLES

| Variable          | Purpose                          | Where   |
| ----------------- | -------------------------------- | ------- |
| `DATABASE_URL`    | PostgreSQL connection            | Backend |
| `QDRANT_URL`      | Vector DB                        | Backend |
| `OPENAI_API_KEY`  | Embeddings                       | Backend |
| `EMBEDDING_MODEL` | Must be `text-embedding-3-small` | Backend |
| `GOOGLE_API_KEY`  | Gemini LLM                       | Backend |
| `JWT_SECRET_KEY`  | Auth tokens                      | Backend |
| `PORT`            | Server port                      | Fly.io  |

```bash
fly secrets list -a nuzantara-rag
```

---

## COMMON WORKFLOWS

### Adding a New API Endpoint

1. Create router in `backend/app/routers/`
2. Add logic in `backend/services/`
3. Register in `backend/app/setup/router_registration.py` (NOT `main_cloud.py`)
4. Add tests in `tests/`
5. If public, add to `hybrid_auth.py`

### Modifying RAG Pipeline

Key files: `reasoning.py` (evidence), `llm_gateway.py` (LLM routing), `orchestrator.py` (main flow)

### Adding a Qdrant Collection

Flat payload → query Qdrant REST directly (KBLI pattern). Nested → use `SearchService.search_collection()`.
Config: `CollectionManager` in `backend/services/ingestion/collection_manager.py`.

### Frontend Changes

```bash
cd apps/mouth && npm run dev
```

Pages: `src/app/`, Components: `src/components/`, API: `src/lib/api/`

---

## ESSENTIAL DOCUMENTATION

| Document                  | Path                                                     | When to Read                                                 |
| ------------------------- | -------------------------------------------------------- | ------------------------------------------------------------ |
| **CLAUDE.md**             | Root                                                     | Behavioral rules, golden rules, deploy QA, language protocol |
| **Cicatrix Scars**        | `.claude/rules/cicatrix-scars.md`                        | 20 known bugs/gotchas — before modifying referenced files    |
| **KG Architecture**       | `docs/KG_LANGGRAPH_ARCHITECTURE.md`                      | Knowledge Graph deep dive                                    |
| **System Map 4D**         | `docs/SYSTEM_MAP_4D.md`                                  | Full architecture overview                                   |
| **Database Architecture** | `docs/DATABASE_ARCHITECTURE_V2.md`                       | DB schema reference                                          |
| **Deploy Checklist**      | `scripts/preflight.sh` (automated) or `CLAUDE.md §15`    | Before deploying — run `./scripts/preflight.sh full`         |
| **Monitoring**            | `scripts/system_doctor.py`                               | 47 checks: infra, frontend, SSL, LLM, security, quality      |
| **RAG Quality**           | `scripts/rag_canary.py`                                  | Embedding drift + golden query regression (monthly/weekly)   |
| **Intel Pipeline**        | `apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md` | News scraper                                                 |
| **Archive**               | `docs/archive/MANIFEST.md`                               | Old docs & reports                                           |

---

## NOTES FOR AI ASSISTANTS

1. Embedding model + KBLI flat payload = most common source of real bugs
2. Before deploy run `./scripts/preflight.sh full` (automated import chain + tests + post-deploy health)
3. `--no-verify` is OK for non-JS commits (prettier pre-commit hook limitation)
4. Router registration is in `router_registration.py`, NOT `main_cloud.py`
5. Lazy loading — health returns 200 during startup, don't panic
6. bali-intel-scraper runs ONLY on Pro locally, NOT on Fly.io
7. Core Guardian V3 runs every 3h — don't interfere with its worktree fixes
8. See `.claude/rules/cicatrix-scars.md` before modifying files it references
9. For behavioral rules, delegation, language protocol → see `CLAUDE.md`
10. This is a production system serving 5000+ real clients. Be careful.
11. System Doctor (`scripts/system_doctor.py`) runs 47 health checks — check its output before and after changes
12. Qdrant + PostgreSQL backed up daily to Tigris S3 (cron 03:00 + 03:30 on Pro)
