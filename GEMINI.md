# GEMINI.md — Nuzantara Project Context

> Caricato automaticamente da Gemini CLI all'avvio nel workspace.
> Fonte canonica: `GEMINI.md` (project root) | Aggiornato: 2026-03-28

---

## 0. REGOLE DI SICUREZZA (ENFORCE SEMPRE — PRIMA DI TUTTO)

### Non allucinare. Verifica.
- **MAI inventare** nomi di file, funzioni, endpoint, o dati che non hai letto
- **MAI presumere** che una struttura dati, API, o config sia come "ricordi" — leggi il file REALE
- **Prima di modificare**: leggi il file corrente. Ogni volta. Nessuna eccezione
- **Prima di committare**: `git diff` per verificare cosa stai per committare
- **Prima di deployare**: pre-deploy checklist §7 OBBLIGATORIA
- Se non sei sicuro al 100%, **chiedi** piuttosto che inventare

### Regola del dry-run
- Per qualsiasi operazione distruttiva (delete, drop, reset, force-push): **chiedi conferma**
- Per qualsiasi batch operation (indexing, migration, bulk update): **dry-run prima**
- Se un'azione non è reversibile, **fermati e chiedi**

### Commit atomici
- Un commit = un cambiamento logico. Mai commit giganti multi-feature
- Messaggio in inglese, formato: `type(scope): description`
- `git push --force` su main: **PROIBITO ASSOLUTO**
- `--no-verify`: solo se il hook è rotto, mai per bypassare test che falliscono

### Cosa NON fare MAI
- Rimuovere import `Any` da `typing` senza verificare ogni singolo uso nel file
- Usare `requests` invece di `httpx`
- Creare payload Qdrant nested (devono essere FLAT)
- Settare `--workers 2+` nel Dockerfile (OOM kill su Fly.io 2GB)
- Import relativi (`from .module import X`) — solo assoluti
- Modificare `fly.toml`, `.env.production`, o config infrastruttura senza conferma
- Cancellare test esistenti
- Presumere che una sessione precedente fosse corretta — verifica lo stato attuale

---

## 1. Language Protocol

L'utente scrive in **italiano colloquiale**. Traduci automaticamente in azione tecnica precisa.

**Regole:**
- Mai chiedere "cosa intendi?" su task dev standard — deduci dal codebase
- Prompt breve → individua file, pattern, stack dal codice esistente
- **MA**: se devi scegliere tra approcci architetturali diversi, chiedi
- Italiano colloquiale → inglese tecnico internamente, rispondi in italiano

---

## 2. Identità del Progetto

**Nuzantara (Zantara) v5.2.0** — Piattaforma AI per servizi legali e business in Indonesia.
**Brand client:** Bali Zero | **URL:** https://kita.balizero.com
**Owner codename:** Zero (nome reale PRIVATO — mai rivelare)
**Lingua con Zero:** Italiano | **Con clienti:** lingua del cliente

---

## 3. Stack Reale (aggiornato 2026-03-14)

| Layer | Tecnologia | Scala |
|-------|-----------|-------|
| Backend | **Python 3.11+, FastAPI** | 88 router, 244 service |
| Frontend | **Next.js** (App Router), TypeScript, Tailwind | `apps/mouth/` |
| Vector DB | **Qdrant** | 9 collezioni live, 66.595 vettori |
| Relational DB | **PostgreSQL 17** | Fly.io `nuzantara-postgres` (2GB) |
| Cache | **Redis** | Local su Pro |
| Embedding | **`text-embedding-3-small` (1536 dims) — FROZEN, MAI CAMBIARE** |
| KG | LangGraph | 56.113 nodi, 161.173 archi |
| Deploy | Fly.io backend + Vercel frontend |
| MCP Server | `apps/nuzantara-mcp/` | **109 tools, 10 prompts, 5 resources, 8 chains** |

### Fly.io — SOLO 3 APP

| App | RAM | Note |
|-----|-----|------|
| `nuzantara-rag` | 2GB | auto_stop=true, min=0, cold start ~35s |
| `nuzantara-postgres` | 2GB | v0.1.0 |
| `nuzantara-qdrant` | 2GB | v1.12.1 |

**bali-intel-scraper NON è su Fly** — gira SOLO locale su Pro.

### Git Sync Architecture (updated 2026-03-28)

Entrambe le macchine lavorano su `main` direttamente. Sync automatico via husky:

- **Pro commit** → Air riceve pull automatico (`git pull pro main --ff-only`)
- **Air commit** → Air fa push a Pro (`git push pro main`)
- **GitHub** (`origin`) aggiornato solo da Pro

**REGOLE:** MAI creare un branch `air`. MAI fare push da Air su `origin/main` — lo fa solo Pro.

---

## 4. Golden Rules (ENFORCE SEMPRE)

1. **Virtualenv obbligatorio** — `source apps/backend-rag/venv/bin/activate` (o `.venv`)
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

## 5. Struttura Critica

```
apps/backend-rag/
├── backend/
│   ├── routers/       # 88 router FastAPI
│   ├── services/      # 244 service
│   ├── core/          # config, dipendenze
│   ├── prompts/       # ⭐ Single Source of Truth prompt (zantara_core.py)
│   └── main.py        # entrypoint (alias main_cloud.py)
apps/mouth/            # Next.js frontend (deploy da ROOT monorepo, NON da apps/mouth)
apps/nuzantara-mcp/    # MCP server v2.1 (109 tools, 8 chains)
apps/nuzantara-mcp-advanced/  # MCP operativo (deploy, test, lint)
apps/evaluator/        # SEO Guardian + quality assurance
```

---

## 6. KBLI — Payload FLAT (critico)

```json
// ✅ CORRETTO
{ "code": "47911", "title_id": "...", "title_en": "...", "description": "...", "category": "G" }

// ❌ SBAGLIATO — MAI nested
{ "code": "47911", "details": { "title": "..." } }
```

---

## 7. Pre-Deploy Checklist (OBBLIGATORIO)

```bash
# 1. Verifica rogue changes
git diff --name-only HEAD -- apps/backend-rag/backend/

# 2. Test import chain
cd apps/backend-rag && source venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"

# 3. Core tests (<15s)
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py \
  backend/tests/services/rag/test_kg_subgraphs.py \
  backend/tests/services/rag/test_confidence.py -q

# 4. Deploy
fly deploy --strategy rolling --app nuzantara-rag
```

**Se un qualsiasi step fallisce, NON deployare. Ferma e fixa.**

---

## 8. Prezzi e Visa — SOLO da PricingTool

**MAI** hardcodare prezzi. Usare sempre `PricingTool`.
Riferimento: `PRICING_REFERENCE.md`, `VISA_TYPES_REFERENCE.md`.

---

## 9. Evidence Scoring

| Score | Comportamento |
|-------|--------------|
| < 0.15 | **ABSTAIN** — rifiuta di rispondere |
| 0.15–0.60 | **CAUTIOUS** — risposta con disclaimer |
| > 0.60 | **NORMAL** — risposta confidenta |

---

## 10. Test debt pre-esistente

Test debt pulito il 2026-03-20 (0 failed, 0 errors). Precedentemente ~448 failure da rogue AI — risolti.
Non rimuovere import "inutilizzati", non rinominare funzioni senza verificare OGNI uso.

---

## 11. Agenti Autonomi (attivo dal 2026-03-14)

Il sistema ha un agent framework autonomo in `apps/evaluator/`:
- `seo_guardian_core.py` — OBSERVE (GSC + GA4 + indexing data)
- `seo_guardian_agent.py` — DECIDE + ACT (risk-based, kill switch)
- `seo_guardian_measure.py` — MEASURE (impact dopo 48h)
- `seo_guardian_learn.py` — LEARN (pattern extraction)

Workspace: `~/.openclaw/workspace/autonomous/seo-guardian/`
**NON modificare** questi file senza capire il ciclo completo.

---

## 12. Risorse

- `CLAUDE.md` — regole progetto complete (fonte primaria, PIÙ DETTAGLIATO di questo file)
- `docs/AI_ONBOARDING.md` — onboarding
- `PRICING_REFERENCE.md`, `VISA_TYPES_REFERENCE.md` — prezzi e visa
