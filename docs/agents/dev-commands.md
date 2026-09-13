# Development commands, testing strategy and the pre-deploy checklist

> Moved out of `AGENTS.md` on 2026-09-10 (boot diet). Substance unchanged.

## 5. Development Commands

### Backend (FastAPI)

```bash
# Activate virtualenv
source venv/bin/activate  # or: . venv/bin/activate

# Run backend locally
cd apps/backend-rag
PYTHONPATH=. python -m uvicorn backend.main:app --reload --port 8000

# Run tests
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. pytest tests/test_specific.py::test_function -v

# Type checking
mypy backend/

# Linting
ruff check backend/
ruff format backend/

# Database migrations (custom SQL system — NOT Alembic)
# Create: backend/db/migrations_v2/NNN_name.sql with mandatory `-- === ROLLBACK ===` marker
PYTHONPATH=. python -m backend.db.migrate apply-all
PYTHONPATH=. python -m backend.db.schema_audit
```

### Frontend (Next.js)

```bash
cd apps/mouth
npm run dev        # Development server
npm run build      # Production build
npm run start      # Production server
npm run lint       # ESLint
npm run test       # Jest tests
```

### Deployment

```bash
# Backend to Fly.io
fly deploy --config apps/backend-rag/fly.toml --app nuzantara-rag

# Frontend to Vercel (auto-deploy on git push to main)
vercel --prod
```

## 8. Testing Strategy

```bash
# Unit tests (fast)
PYTHONPATH=. pytest tests/unit/ -v

# Integration tests (slower)
PYTHONPATH=. pytest tests/integration/ -v

# E2E tests (slowest)
PYTHONPATH=. pytest tests/e2e/ -v

# Coverage report
PYTHONPATH=. pytest --cov=backend --cov-report=html tests/
```

**Standards:**

- Unit tests: > 80% coverage
- Critical paths: 100% coverage
- All new features: tests required before merge

## 13. Pre-Deploy Checklist

Before any production deployment:

```bash
# 1. Check for rogue AI changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test critical import chain (dependencies.py is imported by ALL routers)
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Run core KG tests (82 tests, <15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q

# 4. Deploy
fly deploy --strategy rolling
```

**Test debt:** Cleaned 2026-03-20 (0 failed, 0 errors). Previously ~448 failures from rogue AI refactors — resolved by Windsurf cleanup. Details in `memory/session-2026-02-16-hotfix-and-tests.md`.
