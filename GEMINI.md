# GEMINI.md — Nuzantara Project Context

> Caricato automaticamente da Gemini CLI all'avvio nel workspace.
> Fonte canonica: `GEMINI.md` (project root) | Aggiornato: 2026-03-28

---

<!-- CANON:builder-contract -->

## THE BUILDER CONTRACT — identical in every door, compared by machine

This block is the same in `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` and `QWEN.md`, and
`scripts/proprioception.py`'s `door_canon_parity` probe goes RED if any copy drifts from
`CLAUDE.md`'s. "The same" is what the machine actually enforces, not more: the comparison
hashes the block with TRAILING whitespace and line endings normalised away, so an editor that
strips or adds them is not drift — and anything else, including one reworded sentence or one
extra space mid-line, is. It exists because the CI layer already binds every model equally — a gate does
not care which family opened the PR — while the harness layer did not: a seat that BUILDS used
to start with whatever its own door happened to say. **Do not reword this block in one door.**
Fix it in `CLAUDE.md` and copy it outward, or the probe will name your door.

**1 — PR contract.** One PR, one concern, ≤ ~400 net lines where the work allows. Arming means
freezing: after auto-merge is armed, the branch is read-only and every follow-up starts from a
fresh `origin/main`. Never rerun a red check before you know WHY it is red — the right gesture
depends on the cause, and a blind rerun replays a stale merge ref. Serialize PRs that share a
lockfile. Work in a dedicated worktree on an `agent/<host>/<lane>/...` branch. Three reds for
the SAME cause and the PR suspends instead of taking a fourth round; a fix-of-a-fix stops at
depth 1 — if the correction is itself wrong, the surface is under-specified, so write the spec.

**2 — Every PR body carries a `Bites:` line** naming the CONSUMER and the observation that
proves the change is in force. "A future job will run it" is not a consumer: the job ships in
the same PR. Make the observation before reporting the work done — a merged diff is not a live
one, and this repo's scar record is mostly the distance between those two.

**3 — Bans, stated as an ENTITY and not as a spelling.** What is forbidden is reaching a Claude
model through a **paid per-token Anthropic endpoint** — because the subscription is already paid
and a per-token key duplicates it. The sole sanctioned path is the `claude` CLI with
`CLAUDE_CODE_OAUTH_TOKEN`. `from anthropic import Anthropic` and `ANTHROPIC_API_KEY` are the two
shapes that usually carry it, and grepping for them is a useful first pass — but an alias, a
renamed env var, a wrapper library or a Bedrock/Vertex route reaches the same endpoint without
either literal, and is equally banned. Refuse any new tool, MCP server or cron that requires it. Other paid per-token APIs are not banned but are not
yours to install: they need the owner's explicit authorization first. Never `--dangerously-bypass`
a sandbox; never echo, print or commit a credential — `${VAR:+SET}` reports presence,
`${VAR:-default}` prints the value.

**4 — PII boundary, and it is an OUTPUT boundary.** Processing client data under an authorized
lane is allowed; transcribing it is not. No output, memory, log, alert, report, skill, prompt
saved for reuse, or shared artifact may carry client PII or OSINT in cleartext — use a
`client_id`, a hash, a placeholder or a redaction. This binds every vendor identically: there is
no cloud whose terms make cleartext PII acceptable here, and no seat exempt from it.

**5 — Ship sequence.** The session that owns a mandate runs it end to end: review → merge → arm
→ deploy → prove-live. The codeowner does not merge, does not review and does not deploy — by
design. Arm auto-merge at PR-open. Push, create and merge are three SEPARATE commands, never a
compound one. What stays with the human: business decisions, credentials and consents, and
physical/GUI actions. **The one exception both ways:** an external builder seat (`AGENTS.md`,
`GEMINI.md`, `QWEN.md`) prepares and never ships — it does not merge, arm or deploy its own
work, and a Claude session verifies it. Generator is never grader, in either direction.

<!-- /CANON:builder-contract -->

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

| Layer         | Tecnologia                                                      | Scala                                            |
| ------------- | --------------------------------------------------------------- | ------------------------------------------------ |
| Backend       | **Python 3.11+, FastAPI**                                       | 90 router, 253 service                           |
| Frontend      | **Next.js** (App Router), TypeScript, Tailwind                  | `apps/mouth/`                                    |
| Vector DB     | **Qdrant Cloud**                                                      | 10 collezioni live, 93.283 vettori, 20 defined   |
| Relational DB | **PostgreSQL 17**                                               | Fly.io `nuzantara-postgres` (2GB)                |
| Cache         | **Redis**                                                       | Local su Pro                                     |
| Embedding     | **`text-embedding-3-small` (1536 dims) — FROZEN, MAI CAMBIARE** |
| KG            | LangGraph                                                       | 108.068 nodi, 242.827 archi                      |
| Deploy        | Fly.io backend + Vercel frontend                                |
| MCP Server    | `apps/nuzantara-mcp/`                                           | **115 tools, 10 prompts, 5 resources, 8 chains** |

### Fly.io — SOLO 2 APP

| App                  | RAM | Note                                   |
| -------------------- | --- | -------------------------------------- |
| `nuzantara-rag`      | 2GB | auto_stop=off, min=1 (always-on)       |
| `nuzantara-postgres` | 2GB | v0.1.0                                 |

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
│   ├── app/routers/   # 90 router FastAPI (IMPORTANT: in app/routers/, NOT routers/)
│   ├── services/      # 253 service
│   ├── core/          # config, dipendenze
│   ├── prompts/       # ⭐ Single Source of Truth prompt (zantara_core.py)
│   └── main.py        # entrypoint (alias main_cloud.py)
apps/mouth/            # Next.js frontend (deploy da ROOT monorepo, NON da apps/mouth)
apps/nuzantara-mcp/    # MCP server v2.1 (115 tools, 8 chains)
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

| Score     | Comportamento                          |
| --------- | -------------------------------------- |
| < 0.15    | **ABSTAIN** — rifiuta di rispondere    |
| 0.15–0.60 | **CAUTIOUS** — risposta con disclaimer |
| > 0.60    | **NORMAL** — risposta confidenta       |

---

## 10. Test debt pre-esistente

Test debt pulito il 2026-03-20 (0 failed, 0 errors). Precedentemente ~448 failure da rogue AI — risolti.
Non rimuovere import "inutilizzati", non rinominare funzioni senza verificare OGNI uso.

---

## 11. Agenti Autonomi (attivo dal 2026-03-14)

Il sistema ha un agent framework autonomo in `apps/evaluator/`.

Il SEO layer OBSERVE/DECIDE/ACT/MEASURE/LEARN è stato rifondato come
cellula viva in `apps/evaluator/seo_cell/` (SYMBIOSIS lifecycle,
cell-core PulseLoop). La struttura legacy a 4 file
(`seo_guardian_{core,agent,measure,learn}.py`) è stata rimossa il
2026-04-20. Spec: `docs/superpowers/specs/2026-04-19-seo-guardian-cell-design.md`.

Workspace (storico): `~/.openclaw/workspace/autonomous/seo-guardian/`
**NON modificare** la cellula senza leggere `apps/evaluator/seo_cell/__init__.py`.

---

## 12. Risorse

- `CLAUDE.md` — regole progetto complete (fonte primaria, PIÙ DETTAGLIATO di questo file)
- `docs/AI_ONBOARDING.md` — onboarding
- `PRICING_REFERENCE.md`, `VISA_TYPES_REFERENCE.md` — prezzi e visa

---

## Conduttore e flotta (2026-08-09)

Gemini CLI è DEPRECATO (2026-06-18) — la porta Google è **agy/Antigravity**. Quando Zero avvia agy come orchestratore interattivo vale AGENTS.md §17: stessa legge, altra porta.

- Dispatch agenti secondo `FLEET_TOPOLOGY.json`; Evidence Pack; mai merge a mano (PR → required checks → auto-merge → CI deploy).
- Verdetto Gear-2 da famiglia diversa dal builder; Gear-3 sempre check Fable.
- Fence agy invariata (MODEL_TOPOLOGY notes): candidate-only, no KG writes, no merge identità, no credenziali, no scraping account privati.
- Quota AI Ultra: refresh ~5h + cap settimanali; overage a crediti = spesa per-token → richiede GO di Zero.
- PII: mai. Quote cliente: mai. Legge 5: mai pubblicare **di propria iniziativa** — l'unica deroga nominata (ordine esplicito di Zero o Damar da canale autenticato, gate dell'artefatto verdi) è definita in `AGENTS.md` §0.0 punto 2, che governa anche te; non ri-derivarne l'estensione da questa riga.
- Roster completo modelli × punti di forza × effort di TUTTA la flotta: `MODEL_ROSTER.md` (repo root) — leggilo prima di scegliere un seat (ruling Zero 2026-08-14).
