# 📚 BACKEND NUZANTARA - Indice Studio

> Guida completa per capire il backend RAG

---

## 🗺️ Mappa Documenti

| # | Documento | Contenuto | LOC Coperti |
|---|-----------|-----------|-------------|
| 0 | [BACKEND_DEEP_STUDY.md](./BACKEND_DEEP_STUDY.md) | Overview completo | Tutti |
| 1 | [STUDY_01_ORACLE_RAG.md](./STUDY_01_ORACLE_RAG.md) | Oracle Service (RAG Core) | ~3,000 |
| 2 | [STUDY_02_LLM_PROVIDERS.md](./STUDY_02_LLM_PROVIDERS.md) | LLM Multi-Provider | ~5,000 |
| 3 | [STUDY_03_CORE_ENGINE.md](./STUDY_03_CORE_ENGINE.md) | Vector DB, Embeddings | ~3,600 |
| 4 | [STUDY_04_SERVICES_AND_MORE.md](./STUDY_04_SERVICES_AND_MORE.md) | Services, DB, Middleware | ~30,000 |

---

## 🎯 Quick Start per Ruolo

### 👨‍💻 Sviluppatore Backend
1. Leggi `BACKEND_DEEP_STUDY.md` per overview
2. Studia `STUDY_03_CORE_ENGINE.md` per Qdrant/Embeddings
3. Studia `STUDY_01_ORACLE_RAG.md` per capire il flow

### 🤖 AI/ML Engineer
1. Leggi `STUDY_02_LLM_PROVIDERS.md` per i provider
2. Studia `STUDY_01_ORACLE_RAG.md` per prompting
3. Esplora `services/memory/` per il sistema memoria

### 🏗️ Architect
1. Leggi `BACKEND_DEEP_STUDY.md` per architettura
2. Studia `STUDY_04_SERVICES_AND_MORE.md` per i domini
3. Analizza `middleware/` per auth/security

---

## 📊 Statistiche Codebase

```
backend/
├── app/           →  ~20,000 LOC (routers, setup)
├── services/      →  ~25,000 LOC (26 domini)
├── core/          →   ~3,600 LOC (RAG engine)
├── llm/           →   ~5,000 LOC (AI providers)
├── middleware/    →   ~1,600 LOC (auth, rate limit)
├── db/            →   ~1,000 LOC (migrations)
├── agents/        →   ~3,000 LOC (autonomous AI)
├── plugins/       →     ~500 LOC (extensibility)
└── tests/         →  ~10,000 LOC (unit + integration)
───────────────────────────────────────────────
TOTALE             →  ~70,000 LOC
```

---

## 🔑 File Critici (Must-Read)

| File | Perché | Dimensione |
|------|--------|------------|
| `services/oracle/oracle_service.py` | Cuore del RAG | 500 LOC |
| `llm/zantara_ai_client.py` | Orchestratore LLM | 700 LOC |
| `core/qdrant_db.py` | Vector operations | 1,225 LOC |
| `middleware/hybrid_auth.py` | Sistema auth | 800 LOC |
| `app/metrics.py` | Prometheus metrics | 1,200 LOC |
| `app/dependencies.py` | DI container | 400 LOC |

---

## 🧩 Architettura a Livelli

```
Layer 1: HTTP (Routers)
         ↓
Layer 2: Middleware (Auth, Rate Limit)
         ↓
Layer 3: Services (Business Logic)
         ↓
Layer 4: Core (RAG Engine)
         ↓
Layer 5: Infrastructure (DB, Qdrant, LLM)
```

---

## 🔄 Request Flow Tipico

```
1. Request → Router (FastAPI)
2. → Middleware (auth check)
3. → Dependencies (inject services)
4. → Service (business logic)
5. → Core/LLM (RAG processing)
6. → Response formatting
7. ← Response
```

---

## 📝 Convenzioni Codice

### Naming
- Services: `*_service.py` → `ServiceNameService`
- Routers: `*.py` → `router = APIRouter()`
- Models: `models.py` → `PascalCase`

### Patterns
- Singleton via `get_service()` functions
- Async everywhere (`async def`)
- Type hints required
- Structured logging (no `print()`)

### Testing
- Unit tests: `tests/unit/`
- Integration: `tests/integration/`
- Coverage target: >80%

---

## 🚀 Comandi Utili

```bash
# Avvia backend locale
cd apps/backend-rag
source .venv/bin/activate
uvicorn backend.app.main:app --reload

# Run tests
pytest -v

# Run sentinel (quality checks)
./sentinel

# Check coverage
pytest --cov=backend --cov-report=html
```

---

## 📖 Ordine di Lettura Consigliato

### Giorno 1: Overview
- [ ] `BACKEND_DEEP_STUDY.md`
- [ ] Esplora struttura cartelle

### Giorno 2: Core RAG
- [ ] `STUDY_01_ORACLE_RAG.md`
- [ ] Leggi `oracle_service.py`

### Giorno 3: LLM & Embeddings
- [ ] `STUDY_02_LLM_PROVIDERS.md`
- [ ] `STUDY_03_CORE_ENGINE.md`

### Giorno 4: Services
- [ ] `STUDY_04_SERVICES_AND_MORE.md`
- [ ] Esplora 3 services a scelta

### Giorno 5: Integrazione
- [ ] Leggi un router completo
- [ ] Segui un request flow end-to-end

---

## 🎓 Risorse Aggiuntive

- **Docs progetto:** `apps/backend-rag/docs/`
- **CLAUDE.md:** `apps/backend-rag/CLAUDE.md` (60KB!)
- **AI Handover:** `docs/ai/AI_HANDOVER_PROTOCOL.md`

---

*Generato il 2026-01-28 | "Capire prima, codare poi" 🧠*
