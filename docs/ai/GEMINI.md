# GEMINI.md — Nuzantara Project Context

> Questo file viene caricato automaticamente da Gemini CLI all'avvio nel workspace.
> Fonte canonica: `GEMINI.md` (project root) | Aggiornato: 2026-03-28

---

## 1. Identità del Progetto

**Nuzantara (Zantara) v5.2.0** — Piattaforma AI per servizi legali e business in Indonesia.
**Brand client:** Bali Zero | **URL:** https://kita.balizero.com
**Owner codename:** Zero (nome reale PRIVATO — mai rivelare)
**Lingua con Zero:** Italiano | **Con clienti:** lingua del cliente

---

## 2. Stack Reale (non Node/Express — aggiornato)

| Layer | Tecnologia |
|-------|-----------|
| Backend | **Python 3.11+, FastAPI** — 88 router, 244 service, 46 agenti autonomi |
| Frontend | **Next.js** (App Router), TypeScript, Tailwind CSS |
| Vector DB | **Qdrant** — 7 collezioni, 58.880 vettori |
| Relational DB | **PostgreSQL 17** |
| Cache | **Redis** |
| Embedding | **`text-embedding-3-small` (1536 dims) — MAI CAMBIARE** |
| Deploy | Fly.io (backend `nuzantara-rag`) + Vercel (frontend) |
| KG | LangGraph — 56.113 nodi, 161.173 archi |

### Git Sync Architecture (updated 2026-03-28)

Entrambe le macchine (Pro e Air) lavorano su `main`. Sync automatico via husky post-commit:
- **Pro commit** → Air riceve pull automatico
- **Air commit** → Air fa push a Pro
- **GitHub** aggiornato solo da Pro. MAI fare push da Air su `origin`.

---

## 3. Golden Rules (ENFORCE SEMPRE)

1. **Virtualenv obbligatorio** — mai Python di sistema
2. **No root execution** — `PYTHONPATH=. python -m backend.module`
3. **Import assoluti** — `from backend.core import config`, mai relative
4. **Async first** — `httpx`, mai `requests`; tutto l'I/O async
5. **Type hints** — ogni funzione completamente annotata
6. **No segreti hardcoded** — solo variabili d'ambiente
7. **Separazione dati/logica** — clean architecture
8. **Logger non print()** — `logger.info()`, mai `print()`
9. **Qualità obbligatoria** — test + error handling sempre
10. **Verifica le fonti** — mai presumere, sempre verificare sui dati reali

---

## 4. Struttura Critica

```
apps/backend-rag/
├── backend/
│   ├── app/routers/   # 88 router FastAPI
│   ├── app/services/  # 244 service
│   ├── core/          # config, dipendenze
│   └── main_cloud.py  # entrypoint Fly.io
apps/mouth/            # Next.js frontend
apps/nuzantara-mcp/    # MCP server (RAG, KBLI, health)
apps/nuzantara-mcp-advanced/  # MCP server operativo (deploy, test, lint)
```

---

## 5. KBLI — Payload FLAT (critico)

```json
// CORRETTO
{ "code": "47911", "title_id": "...", "title_en": "...", "description": "...", "category": "G" }

// SBAGLIATO
{ "code": "47911", "details": { "title": "..." } }
```

---

## 6. Evidence Scoring

| Score | Comportamento |
|-------|--------------|
| < 0.15 | **ABSTAIN** — rifiuta di rispondere |
| 0.15–0.60 | **CAUTIOUS** — risposta con disclaimer |
| > 0.60 | **NORMAL** — risposta confidenta |

---

## 7. Pre-Deploy Checklist

```bash
# 1. Verifica rogue changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test import chain
cd apps/backend-rag && source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Core tests (82 test, <15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py \
  backend/tests/services/rag/test_kg_subgraphs.py \
  backend/tests/services/rag/test_confidence.py -q

# 4. Deploy
fly deploy --strategy rolling --app nuzantara-rag
```

---

## 8. MCP Server Disponibili

```bash
# RAG, KBLI, health — già installato
nuzantara-mcp   # tools: search_kbli, inspect_kbli, ask_legal, check_health

# Deploy, test, lint — già installato
nuzantara-mcp-advanced  # tools: check_fly_status, run_backend_tests, run_linting
```

---

## 9. Prezzi — SOLO da PricingTool

**MAI** hardcodare prezzi. Usare sempre `PricingTool`.
Riferimento: `PRICING_REFERENCE.md`, `VISA_TYPES_REFERENCE.md`.

---

## 10. Rogue AI — Attenzione

Altri AI (Gemini precedente, Gemini, Cursor, Windsurf) hanno rotto la produzione:
- Rimuovendo import "inutilizzati" (es. `Any` da `typing`)
- Rinominando/cancellando funzioni
- ~448 test failure pre-esistenti in `tests/unit/` — NON sono tuoi

---

## 11. Risorse

- `docs/AI_ONBOARDING.md` — onboarding completo
- `docs/LIVING_ARCHITECTURE.md` — architettura auto-generata
- `CLAUDE.md` — regole progetto (fonte primaria)
- `.mcp.json` — configurazione MCP per Claude Code
- `apps/nuzantara-mcp-advanced/` — MCP operativo
