---
trigger: glob
globs: apps/backend-rag/**/*.py
---

# Backend Python — Regole (attiva su file \*.py in apps/backend-rag)

## Struttura

```
backend/app/routers/     # 88 router — endpoint per dominio
backend/app/services/    # 244 service — business logic
backend/core/            # config, dipendenze, logging
backend/models/          # Pydantic models
backend/db/              # database access layer
backend/main_cloud.py    # entrypoint Fly.io
```

## Pattern Corretto

```python
from typing import Optional, Any, List
from backend.core.logging import logger
import httpx

async def fetch_data(id: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient() as client:
            result = await client.get(f"/api/{id}")
            logger.info(f"Fetch OK: {id}")
            return result.json()
    except Exception as e:
        logger.error(f"Fetch failed: {id}", exc_info=True)
        raise
```

## Lazy Imports (critico per Fly.io)

Import pesanti (torch, sentence-transformers) DENTRO le funzioni, non a livello modulo.
Il server deve rispondere a /health entro 60s dal boot.

## Test dopo ogni modifica

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. pytest tests/unit/app/routers/test_<nome>.py -v
```

Test debt: CLEANED — 0 failed, 0 errors dopo cleanup. Non ci sono più failure bloccanti.

## Comandi

```bash
cd apps/backend-rag && source .venv/bin/activate
PYTHONPATH=. python -m uvicorn backend.app.main:app --reload --port 8001
PYTHONPATH=. pytest tests/ -v
ruff check backend/ && ruff format backend/
mypy backend/
```
