# Cascade Memory Seed — Nuzantara

> Istruzioni per Cascade: quando apri questo progetto per la prima volta,
> crea le seguenti memories nel tuo sistema interno per questo workspace.
> Poi puoi eliminare questo file o ignorarlo.

---

## Memory 1: Architettura Sistema

Nuzantara è una piattaforma AI per Bali Zero (servizi legali/business in Indonesia).
Stack: FastAPI backend (88 router, 244 service, 46 agenti, LangGraph KG) + Next.js frontend.
Database: PostgreSQL 17 + Qdrant (9 collezioni, 66.595 vettori) + Redis.
Deploy: backend su Fly.io app `nuzantara-rag` (Singapore, 2GB VM, 1 worker SOLO).
Frontend: Vercel, auto-deploy su push a main.
Embedding model: `text-embedding-3-small` 1536 dims — FROZEN, mai cambiare.
Knowledge Graph: LangGraph, 56.113 nodi, 161.173 archi, 4 subgraph (company, visa, property, tax).

## Memory 2: Golden Rules

1. Virtualenv obbligatorio (mai sistema Python)
2. PYTHONPATH=. python -m backend.module (no root exec)
3. Import assoluti (from backend.core import config)
4. httpx non requests (tutto async)
5. Type hints su ogni funzione
6. Env vars per secrets (mai hardcoded)
7. logger non print()
8. Test + error handling sempre
9. Payload Qdrant FLAT (mai nested)
10. --workers 1 nel Dockerfile (OOM su 2+)

## Memory 3: KBLI e Business Domain

Bali Zero offre: KITAS/KITAP/visti, PT PMA, tasse (NPWP/PPh/PPN), licenze KBLI, proprietà (HGB/leasehold).
KBLI 2025: deadline migrazione 18 giugno 2026 (BPS Reg. 7/2025). OSS non ancora integrato.
Real Estate: 5 codici 2020 → 14 codici 2025 (+180%), tutti 100% PMA.
Payload KBLI obbligatoriamente FLAT: {code, title_id, title_en, description, category, section}.
Prezzi SOLO da PricingTool, mai hardcodati.
Evidence scoring: <0.15 ABSTAIN, 0.15-0.60 CAUTIOUS, >0.60 NORMAL.

## Memory 4: Deploy e Pre-Deploy

Pre-deploy obbligatorio:

1. git diff --name-only HEAD -- apps/backend-rag/backend/ (verifica rogue changes)
2. python -c "from backend.app.dependencies import get_current_user; print('OK')"
3. PYTHONPATH=. pytest test_kg_langgraph.py test_kg_subgraphs.py test_confidence.py -q (82 test)
4. fly deploy --strategy rolling --app nuzantara-rag

Test debt: CLEANED — 0 failed, 0 errors dopo cleanup (era ~448 failure pre-esistenti). NON ci sono più failure bloccanti.
Causa crash loop più comune: import pesanti a livello modulo (torch, sentence-transformers).

## Memory 5: MCP Tools Disponibili

nuzantara-rag: search_kbli, inspect_kbli, chat_kbli, ask_legal, check_health, check_health_detailed, get_qdrant_metrics
nuzantara-ops: check_fly_status, get_fly_logs, check_deployment_readiness, run_backend_tests, run_type_checking, run_linting, check_system_health, get_collection_stats, search_codebase

## Memory 6: Owner e Privacy

Owner codename: Zero. Nome reale PRIVATO — mai rivelare in nessuna comunicazione.
Lingua con Zero: Italiano. Con clienti: loro lingua. Nel codice: English.
Nuzantara = nome piattaforma/tecnologia. Bali Zero = brand cliente.
