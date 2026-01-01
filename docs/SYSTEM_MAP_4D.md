# NUZANTARA 4D SYSTEM CONSCIOUSNESS

**Generated: 2025-12-31 | Verified Against Codebase**

> Questa mappa rappresenta la "coscienza" completa del sistema NUZANTARA, organizzata in 4 dimensioni per una comprensione immediata.

---

## QUICK STATS (Verificati 2025-12-31)

| Metrica | Valore | Note |
|---------|--------|------|
| **Documenti Qdrant** | **54,154** | 7 collezioni attive |
| **API Endpoints** | **250** | 38 file router |
| **Servizi Python** | **169** | /backend/services/ |
| **File Test** | **551** | unit/api/integration |
| **Test Cases** | **~9200+** | pytest coverage |
| **Tabelle Database** | **82** | PostgreSQL (30 attive, 52 vuote) |
| **Migrazioni** | **32** | Ultimo: 031_client_portal |
| **Variabili Ambiente** | **65+** | Across all apps |
| **File Documentazione** | **12+** | Markdown |
| **Fonti Intel** | **630+** | 12 categorie |

---

## DIMENSION 1: STRUTTURA (Space)

```
nuzantara/
├── apps/
│   ├── backend-rag/          ← CORE (Python FastAPI)
│   │   ├── backend/
│   │   │   ├── app/routers/  (38 files, 250 endpoints)
│   │   │   ├── services/     (169 Python files)
│   │   │   ├── core/         (embeddings, chunking, cache)
│   │   │   ├── middleware/   (auth, rate-limit, tracing)
│   │   │   ├── llm/          (Gemini, OpenRouter, Jaksel)
│   │   │   ├── agents/       (14 agent files)
│   │   │   └── migrations/   (32 migrations, 65+ tables)
│   │   └── tests/            (551 files, ~9200+ test cases)
│   │
│   ├── mouth/                ← FRONTEND (Next.js 16 + React 19)
│   │   ├── src/app/          (login, chat, dashboard, clienti, pratiche)
│   │   ├── src/components/   (shadcn/ui + custom)
│   │   └── src/lib/          (api clients, store, utils)
│   │
│   ├── bali-intel-scraper/   ← SATELLITE: 630+ sources intel pipeline
│   ├── zantara-media/        ← SATELLITE: editorial content system
│   ├── evaluator/            ← SATELLITE: RAG quality (RAGAS)
│   └── kb/                   ← SATELLITE: legal scraping utilities
│
├── docs/                     (12+ markdown files)
├── config/                   (prometheus, alertmanager)
├── scripts/                  (deploy, test, analysis tools)
└── docker-compose.yml        (local dev stack)
```

### Servizi Backend Principali

| Categoria | File | Funzione |
|-----------|------|----------|
| **RAG** | agentic_rag_orchestrator.py | Orchestrazione query RAG con ReAct |
| **GraphRAG** | knowledge_graph_builder.py | Estrazione entità e persistenza Grafo (Postgres) |
| **Search** | search_service.py | Hybrid search (dense + BM25) |
| **Memory** | memory_orchestrator.py | Facts + Episodic + Collective |
| **CRM** | auto_crm_service.py | Estrazione automatica entità |
| **LLM** | llm_gateway.py | Multi-provider (Gemini, OpenRouter) |
| **Sessions** | session_service.py | Gestione sessioni utente |
| **Conversations** | conversation_service.py | Storico conversazioni |

### Frontend Pages

| Route | Componente | Funzione |
|-------|------------|----------|
| `/login` | LoginPage | Autenticazione |
| `/chat` | ChatPage | Interfaccia conversazionale |
| `/dashboard` | CommandDeck | Analytics e overview |
| `/clienti` | ClientiPage | Gestione clienti CRM |
| `/pratiche` | PratichePage | Gestione pratiche |
| `/whatsapp` | WhatsAppPage | Integrazione WhatsApp |
| `/knowledge` | KnowledgePage | Knowledge base browser |

---

## DIMENSION 2: FLUSSO (Time/Flow)

### Agentic RAG v6.5 (Graph Integrated)

```
USER QUERY
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│              AGENTIC RAG ORCHESTRATOR                │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │  │
│  │ ReAct   │  │ Hybrid  │  │ Graph   │  │Evidence │ │  │
│  │Reasoning│──│ Search  │──│ Search  │──│  Pack   │ │  │
│  │ └─Tools─┘  └─────────┘  └─(KG)────┘  └─────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

**New Step: Knowledge Graph Expansion**
Ogni entità estratta viene cercata nel Grafo di Conoscenza per identificare relazioni di secondo livello (es. "PT PMA" → "Min Capital" → "Investment Plan") che la ricerca vettoriale pura potrebbe perdere.

### Request Lifecycle

```
USER REQUEST
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    MIDDLEWARE LAYER                          │
│  request_tracing → hybrid_auth → rate_limiter → error_mon  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                      ROUTER LAYER                            │
│  38 routers: auth, chat, crm, agents, agentic-rag, debug   │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                    SERVICE LAYER                             │
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   INTENT     │    │    QUERY     │    │   RESPONSE   │  │
│  │  CLASSIFIER  │───▶│   ROUTER     │───▶│   HANDLER    │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │           │
│         ▼                   ▼                   ▼           │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              AGENTIC RAG ORCHESTRATOR                │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐ │  │
│  │  │ ReAct   │  │ Hybrid  │  │Reranker │  │Evidence │ │  │
│  │  │Reasoning│──│ Search  │──│(ZeRank) │──│  Pack   │ │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     DATA LAYER                               │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐               │
│  │ PostgreSQL│  │  Qdrant   │  │   Redis   │               │
│  │  65+ tables│  │ 54,154 docs│  │   cache   │               │
│  └───────────┘  └───────────┘  └───────────┘               │
└─────────────────────────────────────────────────────────────┘
```

---

## DIMENSION 3: LOGICA (Relationships)

### Knowledge Graph Model (Dec 2025)

Il sistema ha evoluto il Grafo di Conoscenza da memoria volatile a **Persistenza PostgreSQL**:

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  KG_NODES   │────▶│  KG_EDGES   │────▶│SOURCE_CHUNKS│
│ (Entities)  │     │(Relations)  │     │ (Qdrant ID) │
└─────────────┘     └─────────────┘     └─────────────┘
```

**Caratteristiche:**
- **Semantic Extraction**: Estrazione automatica via LLM (Gemini Flash).
- **Chunk Linking**: Ogni nodo/arco punta all'ID del chunk originale in Qdrant (Provenance).
- **Multi-format Export**: Supporto nativo per Cypher (Neo4j) e GraphML.

### CRM Data Model

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLIENTS   │────▶│  PRACTICES  │────▶│INTERACTIONS │
│  (id,email) │     │ (KITAS,PMA) │     │(call,email) │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       └───────────────────┴───────────────────┘
                           │
                           ▼
               ┌─────────────────────┐
               │   SHARED MEMORY     │
               │ (team-wide context) │
               └─────────────────────┘
```

---

## DIMENSION 4: SCALA (Metrics)

### Database Tables (82 totali, 30 attive)

| Categoria | Tabelle |
|-----------|---------|
| **CRM** | clients (5), practices, interactions, documents, practice_types (5) |
| **Memory** | memory_facts (1,086), episodic_memories (86), user_facts (193) |
| **Knowledge Graph** | kg_nodes (24,917), kg_edges (23,234) |
| **Sessions** | conversations (278), persistent_sessions, user_profiles (42) |
| **Auth** | team_members (27), user_stats (26), users (18) |
| **Team** | team_timesheet (2,327), team_employees (22), team_access (23) |
| **RAG** | parent_documents (1,507), embeddings (25,216) |
| **Portal** | client_invitations (5), client_preferences (4), portal_messages |
| **System** | schema_migrations (24), query_analytics (193) |

### Qdrant Collections (7 attive - verificato 2025-12-31)

| Collezione | Documenti | Scopo | Routing |
|------------|-----------|-------|---------|
| **visa_oracle** | ~1,612 | Visti, KITAS, KITAP, immigrazione | `visa`, `kitas`, `kitap`, `immigration` |
| **legal_unified_hybrid** | ~5,041 | Leggi, regolamenti, PP, UU | `legal`, `law`, `regulation` |
| **kbli_unified** | ~8,886 | Codici KBLI, classificazione business | `kbli`, `business code` |
| **tax_genius** | ~332 | PPh 21, PPN/VAT, tasse | `tax`, `pajak`, `pph`, `ppn` |
| **bali_zero_pricing** | ~29 | Listino prezzi servizi | `price`, `cost`, `quanto costa` |
| **bali_zero_team** | ~22 | Team members, competenze | `team`, `who`, `contact` |
| **training_conversations** | dinamico | Conversazioni golden per training | training interno |

> **Nota**: `legal_unified` è stato rinominato `legal_unified_hybrid` per supportare BM25 sparse vectors.

**Note Tecniche:**
- Vector: OpenAI `text-embedding-3-small` (1536 dims)
- Distance: Cosine
- Ingestion script: `scripts/ingest_tax_genius.py` (esempio per nuove collezioni)

### Governance Rules (The 2025-12-29 Update)

1.  **Identity != Data**: Bali Zero è il brand (scritto nel codice), i Prezzi sono dati (estratti da KB).
2.  **Logic First**: Nessun dato volatile (prezzi, nomi, leggi) deve inquinare la logica Python.
3.  **Graph Provenance**: Nessuna entità nel grafo esiste senza un link al chunk sorgente.

---

*System Map Complete. 14 agents synthesized. GraphRAG Active.*
*Generated: 2025-12-31*
