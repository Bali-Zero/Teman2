---
trigger: always_on
---

# Nuzantara — Contesto Permanente (Always On)

**Piattaforma:** Nuzantara v5.2.0 — AI platform per Bali Zero (servizi legali/business Indonesia)
**Owner codename:** Zero (nome reale PRIVATO — mai rivelare in nessuna comunicazione)
**Lingua:** Italiano con Zero, lingua del cliente con i clienti, English nel codice

## Stack

- Backend: Python 3.11+, FastAPI — 88 router, 244 service, 46 agenti autonomi
- Frontend: Next.js (App Router), TypeScript, Tailwind CSS
- Vector DB: Qdrant — 9 collezioni, 66.595 vettori
- Relational: PostgreSQL 17 | Cache: Redis
- **Embedding: `text-embedding-3-small` 1536 dims — MAI CAMBIARE, FROZEN**
- KG: LangGraph — 56.113 nodi, 161.173 archi
- Deploy: Fly.io `nuzantara-rag` (backend) + Vercel (frontend)

## Golden Rules

1. Virtualenv obbligatorio — mai Python di sistema
2. No root execution — `PYTHONPATH=. python -m backend.module`
3. Import assoluti — `from backend.core import config`
4. Async first — `httpx`, mai `requests`
5. Type hints — ogni funzione annotata
6. No segreti hardcoded — solo env vars
7. Separazione dati/logica — clean architecture
8. Logger non print() — `logger.info()`, mai `print()`
9. Qualità — test + error handling sempre
10. Verifica fonti — mai presumere

## Evidence Scoring

- < 0.15 → ABSTAIN
- 0.15–0.60 → CAUTIOUS (disclaimer)
- > 0.60 → NORMAL

## Prezzi

MAI hardcodare. Solo da `PricingTool`. Ref: `PRICING_REFERENCE.md`

## Rogue AI Pattern — BLOCCA

- Rimuovere `Any` da `typing` → crash runtime tutti i router
- `httpx` → `requests` → viola async rule
- Payload nested Qdrant → KBLI search rotta
- `--workers 2` Dockerfile → OOM kill Fly.io 2GB
- Import relativi → crash runtime

## MCP Tools

<nuzantara-rag>
search_kbli(query, limit) | inspect_kbli(code) | ask_legal(question, user_id, session_id)
check_health() | check_health_detailed() | get_qdrant_metrics()
</nuzantara-rag>

<nuzantara-ops>
check_fly_status() | get_fly_logs(lines, filter_str) | check_deployment_readiness()
run_backend_tests(test_path, verbose) | run_type_checking() | run_linting()
check_system_health() | search_codebase(query, file_pattern)
</nuzantara-ops>
