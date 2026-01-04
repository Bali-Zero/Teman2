# NUZANTARA Platform

**Production-ready AI platform powered by ZANTARA - Bali Zero's intelligent business assistant**

## 🌟 Overview

Nuzantara is a comprehensive AI-powered knowledge management platform built with modern technologies. It provides intelligent business assistance, RAG (Retrieval-Augmented Generation) capabilities, memory management, and a beautiful Next.js frontend.

## 🏗️ Architecture

### Monorepo Structure

```
nuzantara/
├── apps/
│   ├── backend-rag/              # Python FastAPI backend (RAG + Auth + CRM + tools)
│   ├── mouth/                    # Next.js 16 + React 19 webapp (primary UI)
│   ├── bali-intel-scraper/       # Satellite: 630+ sources intel pipeline
│   ├── zantara-media/            # Satellite: editorial production system
│   ├── evaluator/                # Satellite: RAG evaluation harness
│   ├── kb/                       # Satellite/legacy: scraping utilities
│   └── core/                     # Scribe/Sentinel tooling
├── docs/                         # Documentation (mix of curated + auto-generated)
├── scripts/                      # Automation scripts
├── docker-compose.yml            # Local stack (qdrant + backend + observability)
└── package.json                  # npm workspaces (root)
```

### Technology Stack

- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS
- **Backend**: Python 3.11+, FastAPI, PostgreSQL, Redis, Qdrant
- **AI Providers**:
  - Google Gemini via `google-genai` SDK (3 Flash Preview → 2.0 Flash fallback)
  - OpenAI (text-embedding-3-small for embeddings)
  - OpenRouter (fallback)
  - ZeroEntropy (zerank-2 reranking)
- **Deployment**: Docker, Fly.io (Singapore region)
- **Database**: PostgreSQL, Redis, Qdrant Vector DB

### 🚀 Agentic RAG v6.5 + Conscious GraphRAG

The system now runs on the **Agentic RAG** architecture with **Conscious GraphRAG**, featuring:

- **🧠 ReAct Pattern**: Thought→Action→Observation loop for intelligent multi-step reasoning.
- **🔧 Tool Execution**: VectorSearchTool, PricingTool, TeamKnowledgeTool, CalculatorTool, VisionTool, **KnowledgeGraphTool**.
- **⚡ LLM Cascade**: Gemini 3 Flash Preview → 2.0 Flash fallback for reliability.
- **🔎 Ultra Reranking**: Uses **ZeroEntropy** (zerank-2) for state-of-the-art document retrieval accuracy.
- **📚 Federated Search**: Hybrid search (Dense + BM25) across multiple knowledge collections.
- **🧠 Memory System**: Facts, Episodic, and Collective memory for personalized responses.
- **🛡️ Privacy-by-Design**: Automated PII redaction in logs.
- **🕸️ Knowledge Graph**: PostgreSQL-backed graph with `source_chunk_ids` for full provenance tracking.

#### GraphRAG Architecture (v6.5 - Dec 2025)

```
┌─────────────────────────────────────────────────────────┐
│                  Conscious GraphRAG                      │
├─────────────────────────────────────────────────────────┤
│  PostgreSQL                                              │
│  ├── kg_nodes (entity_id, type, name, source_chunk_ids) │
│  └── kg_edges (source, target, relationship, chunks)    │
├─────────────────────────────────────────────────────────┤
│  KnowledgeGraphBuilder ← LLMGateway (Hybrid Extraction) │
│  └── Regex patterns + LLM semantic extraction           │
├─────────────────────────────────────────────────────────┤
│  KnowledgeGraphTool (Agentic)                           │
│  └── Traversal queries with provenance tracking         │
└─────────────────────────────────────────────────────────┘
```

## 📊 Code Quality & Test Coverage

### Test Coverage
The project maintains **95.01%** test coverage (exceeding 90% target):
- **reasoning.py**: 96.30% coverage
- **feedback.py**: 89.61% coverage
- **72+ comprehensive tests** covering all critical paths
- Run coverage tests: `cd apps/backend-rag && pytest --cov=services.rag.agentic.reasoning --cov=app.routers.feedback --cov-report=html`

### Code Quality & Linting
- **Linting Tool:** Ruff (Python linter and formatter)
- **Current Status:** ~1001 warnings (reduced from 2574, ~61% reduction)
- **Critical Warnings:** ~673 (excluding intentional ARG001/ARG002/E402)
- **Key Improvements:**
  - B904 (exception chaining): Mostly fixed - remaining cases require manual review
  - SIM117 (nested with statements): Many fixed automatically
  - ARG001/ARG002/E402: Often intentional (FastAPI API compatibility, circular imports)
- **Run Linting:** `cd apps/backend-rag && ruff check backend/`
- **Auto-fix:** `cd apps/backend-rag && ruff check backend/ --fix`

## 🚀 Quick Start

### Prerequisites

- Node.js 20+ and npm
- Python 3.11+ and pip
- PostgreSQL 15+ (or use Docker Compose)
- Redis 6+ (or use Docker Compose)
- Docker and Docker Compose
- Fly.io CLI (`flyctl`) for deployment

### 1. Environment Setup

Copy the environment template:

```bash
cp .env.example .env
# Edit .env with your configuration

# Service-specific templates
cp apps/backend-rag/.env.example apps/backend-rag/.env
cp apps/mouth/.env.example apps/mouth/.env.local

# Optional: Google service account (do NOT commit)
cp apps/backend-rag/google_credentials.example.json apps/backend-rag/google_credentials.json
# Then set GOOGLE_APPLICATION_CREDENTIALS=apps/backend-rag/google_credentials.json
```

### 3. Install Dependencies

```bash
# Install Node.js dependencies (root + workspaces)
npm install

# Install Python dependencies (backend)
cd apps/backend-rag
pip install -r requirements.txt
cd ../..
```

> Note: the root uses npm workspaces.

### 4. Run Locally (recommended: Docker Compose)

```bash
# Start qdrant + backend + observability stack
docker compose up --build
```

Default URLs:
- Frontend (dev): http://localhost:3000 (run separately, see below)
- Backend API (compose): http://localhost:8080
- Backend docs: http://localhost:8080/docs
- Qdrant dashboard: http://localhost:6333/dashboard
- Grafana: http://localhost:3001
- Jaeger: http://localhost:16686

### 5. Frontend Dev Mode

```bash
cd apps/mouth
npm run dev
```

### 6. Access the Applications

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8080
- **API Documentation**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/health

## 🔄 Development Workflow

Nuzantara usa un **workflow completamente locale**:

1. **Sviluppo Locale**: Modifica codice, testa localmente
2. **Commit Locale**: `git commit` (solo locale, nessun push automatico)
3. **Build Test**: Verifica build Docker localmente prima di deploy
4. **Deployment Manuale**: Deploy su Fly.io usando gli script helper

### ⚖️ Separation of Data and Logic (Crucial)

To maintain system integrity and avoid frequent code updates for business changes, **NEVER** hardcode "Volatile Data" in the codebase:
- **Specific Prices**: Never write prices (e.g., `15.000.000 IDR`) in the code. Use the Knowledge Base (KB) or configuration files.
- **Employee Names**: Do not use specific names (e.g., `if "Zainal" in query`) in the logic. Use the dynamic `team_knowledge` tools.
- **Legal Details**: Do not hardcode specific visa or tax requirements (e.g., `60k USD income`). These must be retrieved from the KB.
- **Contact Info**: Do not hardcode addresses or specific contact details in response strings. Use `settings` or the KB.

**🚨 ATTENZIONE: NO CI/CD DEPLOYMENT**
Il deploy è **manuale e locale** tramite `flyctl deploy` per garantire il controllo totale sulla build e sui tempi di rilascio.

**Workflow Completo**: Vedi [docs/AI_ONBOARDING.md](docs/AI_ONBOARDING.md) per standards e procedure. Deploy manuale tramite `flyctl deploy`.

**Nota**: Nessun deploy automatico. Il deploy resta manuale tramite `flyctl deploy`.

## 📖 Onboarding (Start Here!)

### 🚨 LETTURA OBBLIGATORIA - Da tenere a mente in OGNI sessione

**Questa scaletta è OBBLIGATORIA per ogni AI/sviluppatore:**

---

#### 1️⃣ Il Punto di Partenza (OBBLIGATORIO)

| File | Descrizione |
|------|-------------|
| [`docs/AI_ONBOARDING.md`](docs/AI_ONBOARDING.md) | Manuale operativo completo, Golden Rules, struttura |
| [`docs/ai/AI_HANDOVER_PROTOCOL.md`](docs/ai/AI_HANDOVER_PROTOCOL.md) | System prompt, fix critici, regole di handover |

---

#### 2️⃣ Per Capire l'Architettura

| File | Descrizione |
|------|-------------|
| [`docs/SYSTEM_MAP_4D.md`](docs/SYSTEM_MAP_4D.md) | Mappa 4D del sistema (Space, Time, Logic, Scale) |
| [`docs/LIVING_ARCHITECTURE.md`](docs/LIVING_ARCHITECTURE.md) | Documentazione API auto-generata, moduli, endpoints |

---

#### 3️⃣ Per le Operazioni (DevOps/Deploy)

| File | Descrizione |
|------|-------------|
| [`docs/DEPLOYMENT_QUICKSTART.md`](docs/DEPLOYMENT_QUICKSTART.md) | Guida rapida al deployment |
| [`docs/operations/ALERTS_RUNBOOK.md`](docs/operations/ALERTS_RUNBOOK.md) | Runbook per allarmi e incidenti |

---

#### 4️⃣ Per lo Sviluppo Specifico

| File | Descrizione |
|------|-------------|
| [`apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md`](apps/bali-intel-scraper/docs/PIPELINE_DOCUMENTATION.md) | Pipeline Intel Scraper (RSS → Enrichment → Telegram → Publish) |
| [`apps/backend-rag/CLAUDE.md`](apps/backend-rag/CLAUDE.md) | Istruzioni specifiche per backend RAG |

---

### 📋 Quick Reference (per sessioni rapide)

| # | File | Tempo | Cosa Impari |
|---|------|-------|-------------|
| 1 | [`docs/AI_ONBOARDING.md`](docs/AI_ONBOARDING.md) | 5 min | Regole, struttura, standards |
| 2 | [`docs/ai/AI_HANDOVER_PROTOCOL.md`](docs/ai/AI_HANDOVER_PROTOCOL.md) | 2 min | Golden rules, tech stack |
| 3 | [`backend/app/core/config.py`](apps/backend-rag/backend/app/core/config.py) | 2 min | Tutte le env vars |
| 4 | [`services/rag/agentic/orchestrator.py`](apps/backend-rag/backend/services/rag/agentic/orchestrator.py) | 5 min | Il cervello del sistema |
| 5 | [`services/rag/agentic/tools.py`](apps/backend-rag/backend/services/rag/agentic/tools.py) | 3 min | I 5 tool disponibili |

## 📚 Documentation

- [**AI Onboarding**](docs/AI_ONBOARDING.md) - **START HERE** - System overview and standards
- [**System Map 4D**](docs/SYSTEM_MAP_4D.md) - Space, Time, Logic, Scale dimensions
- [**Living Architecture**](docs/LIVING_ARCHITECTURE.md) - Auto-generated API & module reference
- [**Race Conditions & Locking**](docs/RACE_CONDITIONS_LOCKING.md) - Locking behavior and race condition prevention
- [**Code Quality Status**](docs/operations/CODE_QUALITY_STATUS.md) - Linting status and code quality metrics
- [**Deploy Checklist**](docs/operations/DEPLOY_CHECKLIST.md) - Deployment procedures

### 🦟 Flyctl Management (Crucial)

To avoid configuration errors, **ALWAYS** use the provided helper scripts to interact with Fly.io. Do not run `flyctl` directly from the root.

```bash
# Manage Backend
./scripts/fly-backend.sh status
./scripts/fly-backend.sh logs
./scripts/fly-backend.sh deploy

# Manage Frontend
./scripts/fly-frontend.sh status
./scripts/fly-frontend.sh logs
```

To regenerate documentation:

```bash
# Backend Docs
python3 apps/core/scribe.py

# Frontend Docs
python3 apps/core/scribe_frontend.py
```

## 🛠️ The Toolkit

- **Sentinel**: Quality Control (`./sentinel`)
- **Scribe**: Documentation Generator
- **Qdrant Analyzer**: Document structure analysis (`python scripts/analyze_qdrant_documents.py`)
- **Document Structure Extractor**: Extract data patterns from text (`python scripts/extract_document_structure.py`)
- **Quality Validator**: Validate document quality (`python scripts/validate_qdrant_quality.py`)
- **Metadata Schema Generator**: Generate standardized metadata schemas (`python scripts/create_metadata_schema.py`)
- **Metadata Extractor**: Extract structured metadata from text (`python scripts/extract_and_update_metadata.py`)
- **Metadata Updater**: Apply metadata updates to Qdrant (`python scripts/apply_metadata_updates.py`)
- **Final Report Generator**: Generate comprehensive analysis reports (`python scripts/generate_final_report.py`)
- **RAG Evaluator**: Local RAG health check (`tests/evaluation/evaluate_rag.py`)

## 📊 Knowledge Base

The platform uses **Qdrant Vector Database** with **54,154 documents** across 7 active collections:

- **Business Codes (KBLI)**: ~8,886 documents (`kbli_unified`)
- **Legal Framework**: ~5,041 documents (`legal_unified_hybrid`)
- **Visa & Immigration**: ~1,612 documents (`visa_oracle`)
- **Tax Regulations**: ~332 documents (`tax_genius`)
- **Team & Pricing**: ~51 documents (`bali_zero_team`, `bali_zero_pricing`)
- **Training Conversations**: dynamic (`training_conversations`)

All documents use **OpenAI embeddings** (1536-dim) for semantic search. See [ARCHITECTURE.md](./docs/ARCHITECTURE.md#3-qdrant-vector-database-structure) for detailed structure.

## 👥 Team

- **Bali Zero** - Lead Developer & Architect
- **Nuzantara Team** - Development & Support

---

## 📝 Recent Changes (Dec 2025)

### v6.5.0 - Conscious GraphRAG (2025-12-31)
- ✅ **LLM Gateway Injection**: KnowledgeGraphBuilder now receives LLM for semantic extraction
- ✅ **Pricing Service Fix**: Corrected JSON path (`backend/data/` vs `backend/services/data/`)
- ✅ **DB Migrations 028-029**: Knowledge Graph tables (`kg_nodes`, `kg_edges`) with `source_chunk_ids`
- ✅ **Category Alignment**: Updated PricingService to match actual JSON schema
- ✅ **conversation_trainer Fix**: Fixed `timedelta` interval bug for asyncpg

---

**Built with ❤️ in Bali**
