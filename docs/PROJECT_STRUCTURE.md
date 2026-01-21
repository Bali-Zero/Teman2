# 📁 Struttura Progetto Nuzantara

**Ultimo Aggiornamento:** 2026-01-21

---

## 🏗️ Architettura Monorepo

Nuzantara è un monorepo che contiene multiple applicazioni e servizi:

```
nuzantara/
├── apps/
│   ├── backend-rag/          # Backend FastAPI (Python)
│   ├── mouth/                # Frontend Next.js (TypeScript/React)
│   ├── admin-dashboard/      # Dashboard Admin (Next.js)
│   ├── bali-intel-scraper/  # Scraper Intel (Python)
│   ├── zantara-media/        # Media Backend + Dashboard
│   ├── webapp/               # Web App (TypeScript)
│   ├── kb/                   # Knowledge Base
│   ├── evaluator/            # Evaluation Tools
│   └── core/                 # Core Utilities
├── scripts/                  # Script di utilità
├── docs/                     # Documentazione
├── config/                   # Configurazioni (nginx, grafana, etc.)
└── tools/                    # Tools esterni
```

---

## 📦 Apps Principali

### `apps/backend-rag/`

**Backend RAG (Retrieval-Augmented Generation)**

- **Stack:** Python 3.11+, FastAPI, PostgreSQL, Qdrant, Redis
- **Porta:** 8080
- **Deploy:** Fly.io
- **Struttura:**
  ```
  backend/
  ├── app/              # FastAPI application
  │   ├── routers/      # API endpoints
  │   ├── setup/        # App initialization
  │   └── core/         # Core utilities
  ├── services/         # Business logic
  ├── llm/              # LLM providers
  ├── db/               # Database models
  └── tests/            # Test suite
  ```

### `apps/mouth/`

**Frontend Next.js**

- **Stack:** Next.js 14+, React, TypeScript, TailwindCSS
- **Deploy:** Vercel
- **Struttura:**
  ```
  src/
  ├── app/              # Next.js App Router
  │   ├── (workspace)/  # Workspace routes
  │   ├── (blog)/       # Blog routes
  │   └── (portal)/     # Portal routes
  ├── components/       # React components
  ├── lib/              # Utilities
  ├── hooks/            # React hooks
  └── types/            # TypeScript types
  ```

---

## 🔧 Scripts Utili

### Root Scripts

- `scripts/fix-console-and-any.py` - Sostituisce console.\* e any types
- `scripts/fix-wildcard-imports.py` - Sostituisce import wildcard
- `scripts/decide-untracked-files.sh` - Analizza file non tracciati

### Backend Scripts

- `apps/backend-rag/scripts/` - Script Python per backend

---

## 📚 Documentazione

### Root Docs

- `docs/` - Documentazione generale
- `CODEBASE_ISSUES_REPORT.md` - Report problemi codebase
- `FIX_COMPLETION_REPORT.md` - Report fix completati
- `PROJECT_STRUCTURE.md` - Questo file

### App-Specific Docs

- `apps/backend-rag/CLAUDE.md` - Session notes backend
- `apps/mouth/README.md` - Documentazione frontend
- `apps/mouth/DOCUMENTATION.md` - Documentazione completa frontend

---

## 🔐 Configurazione

### Environment Variables

- `.env.example` - Template variabili d'ambiente
- **Backend:** `apps/backend-rag/.env.example`
- **Frontend:** `apps/mouth/.env.example`

### Git Configuration

- `.gitignore` - File da ignorare
- `.husky/` - Git hooks (pre-commit, pre-push)
- `.pre-commit-config.yaml` - Pre-commit hooks

---

## 🧪 Testing

### Backend Tests

- **Location:** `apps/backend-rag/backend/tests/`
- **Config:** `apps/backend-rag/pytest.ini`
- **Run:** `cd apps/backend-rag && pytest tests/`

### Frontend Tests

- **Location:** `apps/mouth/src/**/__tests__/`
- **Config:** `apps/mouth/playwright.config.ts`
- **Run:** `cd apps/mouth && npm test`

---

## 🚀 Deployment

### Backend (Fly.io)

```bash
cd apps/backend-rag
flyctl deploy
```

### Frontend (Vercel)

- Automatico via GitHub integration
- Manual: `cd apps/mouth && vercel deploy`

---

## 📊 Monitoring

### Health Checks

- **Backend:** `https://nuzantara-rag.fly.dev/health`
- **Frontend:** Automatico via Vercel

### Metrics

- **Prometheus:** `/metrics` endpoint (backend)
- **Grafana:** Config in `config/grafana/`

---

## 🔄 Workflow Git

### Branch Strategy

- `main` - Production
- `feature/*` - New features
- `fix/*` - Bug fixes
- `refactor/*` - Refactoring

### Commit Format

- Conventional commits: `feat:`, `fix:`, `docs:`, etc.
- Pre-commit hooks: Lint, format, type check
- Pre-push hooks: Tests, security checks

---

## 🛠️ Development Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis
- Docker (optional)

### Quick Start

```bash
# Backend
cd apps/backend-rag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend
cd apps/mouth
npm install
npm run dev
```

---

## 📝 Note Importanti

1. **Monorepo:** Tutte le app condividono la root
2. **Workspaces:** NPM workspaces configurati in `package.json`
3. **Shared Code:** Utilities condivise in `scripts/` e `tools/`
4. **Type Safety:** TypeScript strict mode abilitato
5. **Logging:** Logger centralizzato (no console.\* in produzione)

---

**Per domande o chiarimenti:** Consultare la documentazione specifica di ogni app nella rispettiva directory.
