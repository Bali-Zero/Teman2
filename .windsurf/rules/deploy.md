---
trigger: glob
globs: "**/fly.toml,**/Dockerfile,**/fly.*.toml"
---

# Deploy — Regole Critiche

## Fly.io Backend

**CRITICO: 1 worker SOLO** — 2 workers = OOM kill garantito su VM 2GB

```bash
# SEMPRE rolling
fly deploy --strategy rolling --app nuzantara-rag --config apps/backend-rag/fly.toml
```

## Pre-Deploy Checklist OBBLIGATORIA

```bash
# 1. Verifica modifiche
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Import chain
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Core tests (82 test, <15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py \
  backend/tests/services/rag/test_kg_subgraphs.py \
  backend/tests/services/rag/test_confidence.py -q

# 4. Deploy
fly deploy --strategy rolling --app nuzantara-rag
```

## Health Check

- Endpoint: `/health`
- Risponde `"initializing"` (HTTP 200) durante boot
- Grace period: 60 secondi
- Causa crash loop: import pesanti a livello modulo

## Vercel Frontend

Auto-deploy su push a `main`. Nessun comando manuale.

## MAI

- Committare `.env`, `.env.production`, secrets
- `--workers 2` nel Dockerfile
- `fly deploy` senza `--strategy rolling`
- `git push --force` su main
