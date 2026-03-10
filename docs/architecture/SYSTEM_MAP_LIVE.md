# 🗺️ NUZANTARA SYSTEM MAP (Code-Based Audit)

**Generated:** 2026-01-23
**Method:** "Cold" analysis (Source code & Config only, ignoring docs)

## 🏗️ INFRASTRUCTURE (Docker Compose)

[ NUZANTARA STACK ]
│
├── 🐍 **BACKEND** (FastAPI | Port 8080)
│ ├── Connects to: Postgres, Qdrant, Redis
│ └── Entrypoint: `app.main_cloud:app`
│
├── 🐘 **POSTGRES** (DB Relazionale | Port 5432)
│ └── Stores: CRM data, Users, Auth, Metadata
│
├── 🔮 **QDRANT** (Vector DB | Port 6333)
│ └── Stores: Embeddings, Semantic Knowledge
│
└── ⚡ **REDIS** (Cache/Queue | Port 6379)
└── Handles: Sessioni, Rate limiting, Celery/Queue?

---

## 🧩 APPLICATION ARCHITECTURE

### 1. CORE BACKEND (`apps/backend-rag`)

Il cervello del sistema. Espone API REST per tutto.

**Router Principali (API Surface):**

- **🧠 Intelligence:** `agentic_rag.py`, `autonomous_agents.py`, `oracle_universal.py`
- **🤝 CRM & Team:** `crm_clients.py`, `crm_practices.py`, `team_activity.py`, `zoho_email.py`
- **🗣️ Communication:** `whatsapp_chat.py`, `telegram.py`, `voice.py`
- **📚 Knowledge:** `ingest.py`, `legal_ingest.py`, `knowledge_visa.py`
- **⚙️ System:** `auth.py`, `debug.py`, `system_observability.py`

### 2. FRONTEND (`apps/mouth`)

L'interfaccia utente principale (Next.js).

**Struttura (App Router):**

- **`(workspace)`**: Area di lavoro interna (Dashboard, CRM, Chat).
- **`(portal)`**: Portale clienti esterno.
- **`(blog)`**: Sezione contenuti pubblici.
- **`agents/`, `chat/`**: Interfacce specifiche per AI interaction.

### 3. SATELLITES (Apps Ausiliarie)

- **`admin-dashboard`**: Probabile pannello di controllo tecnico separato.
- **`bali-intel-scraper`**: Pipeline di acquisizione dati (News, Intel).
- **`zantara-media`**: Gestione media/contenuti.
- **`evaluator`**: Tool di valutazione performance RAG.

---

## 🔄 DATA FLOW (Dedotto)

1.  **Ingestion:** `bali-intel-scraper` & `legal_ingest` -> Backend -> **Qdrant** (Vettori).
2.  **Interaction:** User (Mouth/WhatsApp/Telegram) -> Router Specifico -> **Backend Services**.
3.  **Reasoning:** Backend -> `agentic_rag.py` -> Retrieval (Qdrant) + LLM -> Risposta.
4.  **Persistence:** Dati strutturati (Clienti, Pratiche) -> **Postgres**.
