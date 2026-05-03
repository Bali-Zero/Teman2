# Brief — Dockerfile cell-core fix (PR #62)

> Data: 2026-04-16
> Target: sessione Opus 4.6 (Pro o Air indifferente, è infra non feature)
> Scope: installare `packages/cell-core` editable nel Docker di `nuzantara-rag` così Skill/Experience/Metabolic funzionano in produzione invece di girare in degraded mode
> Autore brief: Opus 4.6 (Pro, 2026-04-16)

---

## 0. Libri sacri — lettura veloce

Questo è un **infra fix**, non una nuova feature. Leggi solo:

1. `SYMBIOSIS.md` Legge 4 (graceful degradation) + Legge 7 (numeri prima — serve baseline before/after)
2. `CLAUDE.md` §8 (Deployment Architecture Fly.io) + §11 (Pre-Deploy Checklist)
3. `apps/backend-rag/CLAUDE.md` (backend-rag non-inferable knowledge)
4. `.claude/rules/cicatrix-scars.md` (scar pattern — cercane di preesistenti sul Docker/dependencies)

### 5 domande universali (valgono anche per Dockerfile)
1. Sa dove si trova? → build stage del Docker `nuzantara-rag`
2. Persiste? → image layer condiviso
3. Se fallisce? → build fallisce pulito, rollback Fly automatico
4. Cicatrici? → PR #56 fixed CI ma non Dockerfile — questo è il seguito naturale
5. Misurabile? → endpoint `/api/metabolic/stats` passa da 503 → 200, skill `total=0` → real count

---

## 1. Contesto — perché questa PR esiste

### Stato verificato live (2026-04-16 dopo deploy PR #61)

```bash
$ curl -s -H "X-API-Key: ..." https://nuzantara-rag.fly.dev/api/metabolic/stats
{"detail":"cell_core.metabolic not available","correlation_id":"..."}

$ curl -s -H "X-API-Key: ..." https://nuzantara-rag.fly.dev/api/skill/stats
{"total":0,"by_tier":{"tier1":0,"tier2":0,"untiered":0},"by_cell":{},"avg_confidence":0.0}

$ flyctl ssh console --app nuzantara-rag -C 'python -c "from cell_core.genome import Genome"'
ModuleNotFoundError: No module named 'cell_core'
```

### Cosa è shippato ma degraded

| Router | Path | Status runtime |
|--------|------|----------------|
| `/api/skill/*` (PR #55) | Shipped | 200 con **dati fake** (degraded: total=0 sempre) |
| `/api/experience/*` (PR #54) | Shipped | 200 con dati fake (degraded) |
| `/api/metabolic/*` (PR #60+#61) | Shipped | 503 esplicito |

### Perché

`apps/backend-rag/Dockerfile`:
- Builder stage: installa `requirements-prod.txt` → **NO cell-core**
- Runtime stage: copia `backend/`, `scripts/`, `training-data/`, `*.py` → **NO packages/cell-core/**

`apps/backend-rag/requirements-prod.txt`: nessuna menzione di `cell-core`.

### Scar preesistente documentato

PR #56 (`31ec067b8 fix(ci): install cell-core editable so backend tests pass`) ha fixato **solo CI workflows** (`tests.yml`, `fly-deploy.yml` gate). Non ha toccato il `Dockerfile` che costruisce l'image deployata. Citazione dal body PR #56:

> Also add pre-deploy-gate in fly-deploy.yml (future-proof against tests being added to the gate later; core tests today don't touch cell-core so this is defensive).

Il "defensive" scarico il Dockerfile. Questa è la PR che chiude il cerchio.

---

## 2. Obiettivo

Rendere `cell_core` importabile dentro l'image Docker `nuzantara-rag` senza rompere build time, image size, security.

### Criteri success

1. `flyctl ssh console --app nuzantara-rag -C 'python -c "import cell_core.genome; import cell_core.metabolic; import cell_core.hgt; print(OK)"'` → stampa OK (nessun ModuleNotFoundError)
2. `curl /api/metabolic/stats` → 200 con `{"total_snapshots": 0, ...}` (non più 503)
3. `curl /api/skill/stats` → 200 con counter reali (se SQLite ha dati) invece di empty fake
4. Image size post-build: delta < 5 MB (cell-core è pure Python, non deve inflate l'image)
5. Build time: delta < 30s
6. Post-deploy smoke test `/health` → healthy (rollback automatic se fail)

### Vincoli

- **Non toccare `fly.toml`** (CLAUDE.md Legge: off-limits)
- **Non toccare `requirements-prod.txt` dependencies esistenti** (solo aggiungere cell-core se serve)
- **Non rompere build cache** per il resto delle dependency (cell-core install DOPO requirements-prod)
- **Rolling deploy zero-downtime** (strategy già `rolling` in fly.toml)
- **Red team Gemini pre-deploy** (CLAUDE.md Legge 12)

---

## 3. Architettura target (2 opzioni — brainstorming)

### Opzione A — `pip install -e packages/cell-core` inline nel Dockerfile

**Pro:**
- Zero modifiche a `requirements-prod.txt`
- Riusa pattern PR #56 CI (stessa installazione)
- Editable → update senza rebuild se si cambia cell-core locally

**Contro:**
- `--user` install in builder stage, serve copiare `/root/.local` + `/app/packages` nel runtime
- Bundle `packages/` directory (non solo installed package)

**Patch:**

```dockerfile
# Stage 1: Build
FROM python:3.11-slim as builder
# ... existing ...
COPY requirements-prod.txt .
RUN pip install --no-cache-dir --user -r requirements-prod.txt \
    && find /root/.local -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
    # ...existing cleanup...

# NEW — copy cell-core and install editable
COPY packages/cell-core /app/packages/cell-core
RUN pip install --no-cache-dir --user -e /app/packages/cell-core

# Stage 2: Runtime
FROM python:3.11-slim
# ... existing ...
COPY --from=builder /root/.local /home/nuzantara/.local
COPY --from=builder /app/packages /app/packages   # NEW — needed for editable install
# ... existing COPY backend/scripts/training-data ...
```

**Build context:** Dockerfile oggi ha context `apps/backend-rag/`. Per vedere `packages/cell-core` serve context monorepo root. Due varianti:

- **A.1** Cambiare `fly.toml` `[build]` con `context = "../../"` + `dockerfile = "apps/backend-rag/Dockerfile"` → **VIETATO** (off-limits fly.toml)
- **A.2** Pre-copiare `packages/cell-core/` dentro `apps/backend-rag/` al build time (git submodule? symlink? CI step?) → complica
- **A.3** Usare `fly deploy` con `--dockerfile` custom che monta `../..` → non persisteable

### Opzione B — Package cell-core come wheel pre-built

**Pro:**
- Aggiunta pulita a `requirements-prod.txt` senza toccare Dockerfile structure
- Image slim (wheel only, no packages/ dir)
- Standard Python packaging

**Contro:**
- Richiede CI step per `python -m build packages/cell-core` + upload wheel
- Serve `pyproject.toml` completo in cell-core (probabilmente già esiste, verifica)
- Versioning manuale

**Patch:**

```
# requirements-prod.txt — aggiungi
nuzantara-cell-core @ file:///wheels/cell_core-X.Y.Z-py3-none-any.whl
```

Richiede workflow CI che builda il wheel e lo mette in `apps/backend-rag/wheels/` prima di `fly deploy`.

### Opzione C (raccomandata) — COPY + setup.py editable SENZA cambiare fly context

**Il trucco:** Dockerfile è invocato da Fly con context `apps/backend-rag/`, ma possiamo **cambiare il working directory del Dockerfile** a root via `fly deploy --build-arg` + un wrapper script. OPPURE — più semplice — **aggiungere lo step che pre-copia `packages/cell-core/` sotto `apps/backend-rag/vendor/cell-core/`** prima del build:

```yaml
# .github/workflows/fly-deploy.yml
- name: Stage cell-core for Docker
  run: |
    mkdir -p apps/backend-rag/vendor
    cp -r packages/cell-core apps/backend-rag/vendor/cell-core
```

E poi nel Dockerfile:

```dockerfile
# Stage 1: Build
COPY vendor/cell-core /app/vendor/cell-core
RUN pip install --no-cache-dir --user -e /app/vendor/cell-core

# Stage 2: Runtime  
COPY --from=builder /app/vendor /app/vendor
```

**Pro:**
- Non tocca fly.toml
- Non richiede wheel build
- Pattern visibile in CI YAML (auditabile)
- `.gitignore` exclude `apps/backend-rag/vendor/` (evita commit doppio)

**Contro:**
- CI duplicato: `tests.yml` deve fare lo stesso staging

### Raccomandazione

**Opzione C.** La soluzione più pulita è:
1. Dockerfile: COPY da `packages/cell-core` assumendo build context monorepo root
2. Modificare SOLO il workflow `.github/workflows/fly-deploy.yml` per chiamare `flyctl deploy` con `--dockerfile apps/backend-rag/Dockerfile` dal root del repo (cambia build context ma **non tocca fly.toml**)

Il flag `--dockerfile` passato a `flyctl deploy` dalla working directory root permette di usare il monorepo come context senza modificare `fly.toml` `[build]` section.

Schema preciso:
```yaml
# .github/workflows/fly-deploy.yml — step deploy
- name: Deploy to Fly.io
  run: |
    cd .  # monorepo root
    flyctl deploy \
      --app nuzantara-rag \
      --dockerfile apps/backend-rag/Dockerfile \
      --config apps/backend-rag/fly.toml \
      --strategy rolling
```

Dockerfile diventa:
```dockerfile
# Context: monorepo root (explicit, passed via --dockerfile)

FROM python:3.11-slim as builder
WORKDIR /app
COPY apps/backend-rag/requirements-prod.txt .
RUN pip install --user -r requirements-prod.txt
COPY packages/cell-core /app/packages/cell-core
RUN pip install --user -e /app/packages/cell-core

FROM python:3.11-slim
# ...
COPY --from=builder /root/.local /home/nuzantara/.local
COPY --from=builder /app/packages /app/packages
COPY apps/backend-rag/backend /app/backend
COPY apps/backend-rag/scripts /app/scripts
COPY apps/backend-rag/training-data /app/training-data
COPY apps/backend-rag/*.py /app/
ENV PYTHONPATH=/app:/app/backend:/app/packages/cell-core
```

### Da validare nel brainstorming

- Build context switch rompe cache? Probabile invalidation prima build, OK.
- `EXPERIENCE_DB_PATH` + `METABOLIC_DB_PATH` defaults (`~/.nuzantara/experience.db`, `~/.agent/decisions/organism_metrics.db`) — esistono in container? **Verificare** che `mkdir -p` le crei a runtime (già handled dentro service? controllare).
- Migration `domain` column già applicata via Alembic, ma il SQLite locale del container (non PG) parte vuoto → first write crea schema. Nessun issue.
- Volumi persistenti: `organism_metrics.db` dovrebbe vivere su un volume Fly montato, altrimenti ogni rolling deploy resetta i snapshot. Verificare `[[mounts]]` in fly.toml — c'è `nuzantara_rag_data → /data` solo per process `rag`. Il process `api` (quello che serve /api/metabolic) **non ha volume** → snapshot persi a ogni deploy. **Fix:** DB Metabolic deve vivere in `/data` condiviso O default path spostato a `/data/organism_metrics.db` per process `api`. Richiede env var `METABOLIC_DB_PATH=/data/organism_metrics.db` nei secrets Fly **e** probabile aggiunta `[[mounts]]` per processo `api` (tocca fly.toml — escalate a Zero).

---

## 4. Arsenale autorizzato

### Federation

- **Codex CLI** `./scripts/ai-dispatch.sh codex-sandbox` — critical path: Dockerfile patch + pip install test in sandbox (evita break image di produzione)
- **Gemini CLI** redteam — review pre-deploy obbligatorio (CLAUDE.md Legge 12)
- **Claude CLI** review — conferma che l'image è minimal (non inflata da packages/)

### Ricerca

- Exa + WebSearch — Docker multi-stage best practices 2026, pip install -e in Docker pitfalls
- Paper/reference: Fly.io docs su `--dockerfile` flag + monorepo context

### Sviluppo

- Read/Edit/Write — Dockerfile, workflow yaml, requirements-prod.txt se necessario
- Bash — `docker build` locale per verificare
- **NO `fly.toml` edit** (off-limits)

### Testing

- Build locale: `cd /Users/nuzantara/Projects/nuzantara && docker build -f apps/backend-rag/Dockerfile -t rag-test .`
- Import chain smoke: `docker run --rm rag-test python -c "import cell_core.genome; import cell_core.metabolic; import cell_core.hgt"`
- Size check: `docker images rag-test` — delta vs current production
- Container run: `docker run -p 8080:8080 rag-test` + `curl localhost:8080/api/metabolic/stats`

### MOS

- `mem save decision` per scelta opzione A vs B vs C con trade-off
- `mem save discovery` se emergono pitfall (volumi, env vars, PYTHONPATH)

### Infrastruttura

- GitHub Actions `.github/workflows/fly-deploy.yml` — modifica deploy step
- GitHub Actions `.github/workflows/tests.yml` — potrebbe già avere `pip install -e ../../packages/cell-core` dal PR #56, verifica coerenza
- Fly secrets `fly secrets set METABOLIC_DB_PATH=/data/...` se applicabile

---

## 5. Protocollo brainstorming multi-agente

Regola indipendenza:
- Scrivi posizione prima
- 3/4 concordi velocemente → cerca falla
- Documenta divergenze MOS

### Checkpoint obbligatori

1. **Dopo scelta opzione A/B/C** — build context change è safe? impatti CI?
2. **Prima di modificare Dockerfile** — Codex sandbox test build
3. **Prima di modificare fly-deploy.yml** — ripercussioni su altre PR?
4. **Pre-deploy** — redteam Gemini obbligatorio
5. **Post-deploy** — smoke test `/api/metabolic/stats` + `/api/skill/stats` reali

### Pattern

```bash
./scripts/ai-dispatch.sh redteam "Dockerfile change build context monorepo root for cell-core editable install"
./scripts/ai-dispatch.sh codex-sandbox "docker build -f apps/backend-rag/Dockerfile from repo root, verify cell_core importable"
notebook_query NB-1 "Fly.io monorepo deploy patterns multi-stage Docker"
```

---

## 6. Processo — TDD minimal (infra)

### Fase 0 — Worktree
`superpowers:using-git-worktrees`, branch `feature/dockerfile-cellcore-fix-2026-04-16`

### Fase 1 — Brainstorming
Quick brainstorm (non feature, 15 min):
- Verifica opzione C (build context switch) non rompe altre cose
- Check `requirements-prod.txt` dependencies — cell-core ha deps proprie? (probabilmente solo stdlib SQLite3)
- Verifica volume `/data` disponibilità per process `api`

### Fase 2 — Implementation
1. Edit Dockerfile
2. Edit `.github/workflows/fly-deploy.yml` step deploy
3. Test locale `docker build` + `docker run` + `curl`
4. Commit atomico (1 commit, no split)

### Fase 3 — Verification
- Import chain locale Air/Pro: `python -c "from backend.app.dependencies import get_current_user"` (non toccato, sanity)
- CI backend tests: devono restare green (PR #56 già fixed CI, questo NON regressa)
- Red team Gemini obbligatorio
- `docker run` smoke test locale

### Fase 4 — Deploy
- Merge PR → auto-deploy Fly
- Post-deploy curl verification (3 endpoint)
- Monitoring 30 min per regressioni

---

## 7. Deliverable atteso

### Codice
- `apps/backend-rag/Dockerfile` — COPY + `pip install -e` cell-core
- `.github/workflows/fly-deploy.yml` — `--dockerfile` flag + context change  
- `.dockerignore` (se esiste) — assicurati che `packages/cell-core` non sia escluso
- Eventuale `requirements-prod.txt` — se cell-core ha deps non già installate

### Test
- `apps/backend-rag/tests/docker/test_import_cellcore.py` — test che simula import in container (optional)
- Verifica CI `tests.yml` + `fly-deploy.yml` restano green

### Infrastruttura
- Deploy Fly rolling
- Post-deploy smoke test documentato

### Documentazione
- `docs/research/2026-04-16-dockerfile-cellcore-fix-results.md` — before/after metriche (image size, endpoint status)
- Aggiorna `apps/backend-rag/CLAUDE.md` section "Critical Gotchas" con pattern cell-core editable in Docker
- Aggiorna `.claude/rules/cicatrix-scars.md` con scar risolto

### Git
- Branch `feature/dockerfile-cellcore-fix-2026-04-16`
- Commit atomico con `why` esplicito (chiude scar preesistente PR #56)
- PR verso main
- Link a PR #54 #55 #56 #57 #60 #61 nel body (closing the loop)
- `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`

---

## 8. Anti-pattern da evitare

1. **NO toccare `fly.toml`** — off-limits (CLAUDE.md Legge)
2. **NO toccare `zantara_core.py`** — off-limits
3. **NO aggiungere dependency a `requirements-prod.txt` oltre cell-core** — scope minimal
4. **NO inflate image** > 5 MB — cell-core è pure Python, deve restare slim
5. **NO skip red team Gemini** (CLAUDE.md Legge 12)
6. **NO commit in main** senza PR
7. **NO deploy senza smoke test 3 endpoint** (skill/experience/metabolic tutti e 3)
8. **NO image cache invalidation non necessaria** — step cell-core **DOPO** `requirements-prod.txt` install
9. **NO dimenticare `PYTHONPATH`** — deve includere `/app/packages/cell-core` se usiamo COPY source
10. **NO rimuovere il fallback `_GENOME_AVAILABLE`** nei service — graceful degradation resta (Legge 4)
11. **NO volumi persistenti senza autorizzazione Zero** — se SQLite locale perde dati tra deploy, escalate
12. **NO groupthink** — 4/4 agenti concordi velocemente su una delle opzioni → cerca falla

---

## 9. Criteri di successo

1. **Build Docker completa** senza errori
2. **Image size delta < 5 MB** vs produzione attuale
3. **Build time delta < 30s**
4. `docker run` locale → `python -c "import cell_core.genome; import cell_core.metabolic; import cell_core.hgt"` → OK
5. Post-deploy `/api/metabolic/stats` → **200 con `{total_snapshots: N, ...}`** (non più 503)
6. Post-deploy `/api/skill/stats` → **200 con dati reali dal SQLite** (non più empty fake)
7. Post-deploy `/api/experience/query` → **funziona** con trajectory reale
8. `/health` → healthy per 30 min consecutive
9. Red team Gemini approva
10. CI tests.yml green + fly-deploy.yml green
11. Cicatrice precedente PR #56 marked resolved

---

## 10. Escalation a Zero

- Volume `/data` per process `api` richiesto → tocca `fly.toml` → escalate
- Image size > 5 MB delta → escalate (decision trade-off)
- Build context change rompe altri workflow GitHub Actions → escalate
- Post-deploy endpoint regression → **STOP**, rollback, escalate
- Red team Gemini flag "blocker" → escalate

---

## 11. Promemoria

È **infra fix**, non feature. Scope minimale, chirurgico.

Il cerchio si chiude: PR #57 shippato codice, PR #60/#61 wire router, **#62 rende cell-core realmente importabile.**

Dopo questa PR:
- `curl /api/metabolic/stats` → numeri veri
- Skill Registry può finalmente accumulare
- HGT publisher/consumer hanno un genome che persiste
- Il baseline T0 SYMBIOSIS Pilastro 7 è catturabile

Scrivi con rigore. Testa in sandbox. Deploy con red team. Verifica con 3 curl.

E quando è fatto, per la prima volta l'organismo **sa davvero** cosa sta imparando.

---

**Firma:** Opus 4.6 (Pro, 2026-04-16) — brief per PR #62 chiusura cerchio wire-up
