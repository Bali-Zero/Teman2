# NUZANTARA Documentation

Questa directory contiene la documentazione del progetto (in parte auto‑generata).

## Start Here

- `docs/ARCHITECTURE.md` — architettura “umana” (stack, flussi, DB, RAG)
- `docs/SYSTEM_OVERVIEW.md` — sommario API (auto‑generato)
- `docs/LIVING_ARCHITECTURE.md` — dettaglio API & moduli (auto‑generato)
- `docs/FRONTEND_ARCHITECTURE.md` — struttura frontend (auto‑generato)

## Deep Dives (qualità & prodotto)

- `docs/COMPARATIVE_TECH_BUSINESS_ANALYSIS.md` — analisi tecnica+business comparata globale
- `docs/ULTRA_UPGRADE_AUDIT.md` — audit per componente + roadmap Ultra
- `docs/AI_MODEL_STRATEGY.md` — strategia “Super model” + routing + quality gates
- `docs/RAG_ARCHITECTURE.md` — overview RAG/agentic (semi‑auto)

## Operations

- `docs/operations/LOCAL_TESTING_GUIDE.md`
- `docs/operations/DEBUG_GUIDE.md`
- `docs/operations/DEBUG_FINDINGS.md`
- `docs/DEPLOY_CHECKLIST.md`
- `docs/FULL_STACK_OBSERVABILITY.md`

## Reports

- `docs/reports/PROJECT_DATA_INVENTORY.md`
- `docs/reports/CLEANUP_SUMMARY.md`
- `docs/reports/IMPLEMENTATION_COMPLETE.md`
- `docs/reports/AUTOMATION_COMPLETE.md`

## AI Ops

- `docs/ai/AI_HANDOVER_PROTOCOL.md`
- `docs/JAKSEL_API_DOCUMENTATION.md`

## Archive

- `docs/_archive/` contiene documenti storici/one‑off non essenziali (es. `docs/_archive/root-docs/`).

## Getting Started

1. Nuovi dev: `docs/ARCHITECTURE.md`
2. AI agent: `AI_ONBOARDING.md`
3. Deploy: `docs/DEPLOY_CHECKLIST.md`
4. API reference: `docs/LIVING_ARCHITECTURE.md`

## Auto‑Generated Docs

I seguenti file sono auto‑generati da “The Scribe” e non vanno editati a mano:
- `docs/SYSTEM_OVERVIEW.md`
- `docs/LIVING_ARCHITECTURE.md`
- `docs/FRONTEND_ARCHITECTURE.md`
- (extended) `docs/MIGRATIONS_CHANGELOG.md`, `docs/PLUGIN_REGISTRY.md`, `docs/INFRASTRUCTURE_STATUS.md`, `docs/ARCHITECTURE_STATS.md`

Rigenera:
```bash
python apps/core/sentinel.py --scribe
# o singolarmente:
python apps/core/scribe.py
python apps/core/scribe_extended.py
python apps/core/scribe_frontend.py
```
