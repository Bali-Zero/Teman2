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
- **AI Providers**: OpenAI, Anthropic, Google Gemini (Flash 2.0/Pro 1.5), ZeroEntropy
- **Deployment**: Docker, Fly.io
- **Database**: PostgreSQL, Redis, Qdrant Vector DB

### 🚀 Ultra Hybrid Features (v5.4)

The system now runs on the **Ultra Hybrid** architecture, featuring:

- **🧠 Quality Routing**: Automatically routes queries to **Fast** (Flash), **Pro**, or **DeepThink** (Reasoning) tiers based on complexity.
- **🔎 Ultra Reranking**: Uses **ZeroEntropy** (zerank-2) for state-of-the-art document retrieval accuracy.
- **📚 Evidence Pack**: All business answers include standard formatting and verified citations.
- **🛡️ Privacy-by-Design**: Automated PII redaction in logs.

See [**Ultra Features Documentation**](./docs/ULTRA_FEATURES.md) for details.

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

> Note: the root uses npm workspaces. Some satellite apps (e.g. `apps/zantara-media`) may use pnpm as an optional alternative.

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

### 6. Evidence Pack UI Integration

The frontend now displays **Verification Score** and **Citation Card** for assistant messages.

- **Verification Score**: A numeric confidence metric rendered within each `MessageBubble` when the backend includes `verification_score`.
- **Citation Card**: A reusable `CitationCard` component that elegantly presents source `title` and `content` arrays.

These UI elements are conditionally rendered based on the presence of `verification_score` and `sources` fields in the API response. See `src/components/CitationCard.tsx` and the updated `MessageBubble` component for implementation details.


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

**Workflow Completo**: Vedi [docs/WORKFLOW.md](docs/WORKFLOW.md) per la guida dettagliata.

**Nota**: Nessun deploy automatico. Il CI (se usato) esegue solo gate di sicurezza/verifica; il deploy resta manuale.

## 📚 Documentation

- [**Development Workflow**](docs/WORKFLOW.md) - **Start Here - Complete development workflow**
- [**Production Usage Guide**](docs/PRODUCTION_USAGE_GUIDE.md) - API & Deploy info
- [Backend Essentials](docs/BACKEND_ESSENTIALS.py) - Core configuration reference
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Agentic RAG System](docs/AGENT_ARCHITECTURE.md)
- [Deployment Guide](docs/DEPLOY_SETUP.md)

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

The platform uses **Qdrant Vector Database** with **25,458+ documents** across 8 collections:

- **Visa & Immigration**: 1,612 documents (`visa_oracle`)
- **Business Codes (KBLI)**: 8,886 documents (`kbli_unified`)
- **Tax Regulations**: 895 documents (`tax_genius`)
- **Legal Framework**: 5,041 documents (`legal_unified`)
- **General Knowledge**: 8,923 documents (`knowledge_base`)
- **Team Profiles**: 43 documents (`bali_zero_team`)
- **Pricing**: 29 documents (`bali_zero_pricing`)
- **Property**: 29 documents (`property_unified`)

All documents use **OpenAI embeddings** (1536-dim) for semantic search. See [ARCHITECTURE.md](./docs/ARCHITECTURE.md#3-qdrant-vector-database-structure) for detailed structure.

## 👥 Team

- **Bali Zero** - Lead Developer & Architect
- **Nuzantara Team** - Development & Support

---

**Built with ❤️ in Bali**
