# Merge Strategy — Strategic-8 (Pro + Air)

**Data analisi:** 2026-04-17 sera
**Pro main HEAD:** `848999e7e`
**Air main HEAD:** `758cd34d3` (2 settimane indietro di Pro)
**origin/main HEAD:** `848999e7e` (sincronizzato con Pro)

## Situazione attuale

### Pro — 4 branch pronti per review

| Branch                    | Commits | Files | +/-             | Rischio   | Note                                                                                     |
| ------------------------- | ------: | ----: | --------------- | --------- | ---------------------------------------------------------------------------------------- |
| `v2-client-app`           |      10 |    40 | +2420/−564      | **basso** | Tutti fix focalizzati portal; 47 test; tsc clean; migration 111 inclusa                  |
| `v2-team-ops`             |       7 |   206 | +901/**−25545** | **ALTO**  | Include cleanup 4 orphan apps (commit `f31dc5b22`) — verifica necessaria                 |
| `opus47-routing-audit`    |       6 |    40 | +2200/−1364     | **medio** | OAuth migration completa; richiede `claude` CLI in container Fly.io prima di deploy prod |
| `fix/portal-bundle-audit` |       0 |     — | —               | —         | Zero commit — cancellabile                                                               |

### Air — 4 branch che _sembrano_ molto più grandi di quanto siano

Il count Air è distorto perché **Air main è indietro di ~2 settimane da Pro main**:

| Branch                          | "Commit ahead" | Commit _effettivi_ nuovi | Rischio                           |
| ------------------------------- | -------------: | -----------------------: | --------------------------------- |
| `compliance/pdp-coverage-push`  |             59 | **1** (solo `865d4ec5a`) | **basso**                         |
| `solidification/s09-services`   |             68 |                    **9** | **basso** (7 fix atomici + 2 doc) |
| `graphrag/completion-gaps`      |              3 |                    **3** | **basso** (solo subtask commits)  |
| `solidification/s13-middleware` |             61 |                    **3** | **basso** (tutti test + 1 fix)    |

## Strategy

### Fase 1 — Air sync con Pro (PRIMA di tutto)

Air main è 2 settimane indietro. Va sincronizzato **prima** di mergere qualsiasi cosa, altrimenti:

- i branch Air importerebbero 2 settimane di Pro come "nuovi commit"
- potenziali conflitti con i lavori Pro paralleli (v2-client-app, v2-team-ops)

**Comando proposto:**

```bash
# Su Air (via SSH)
ssh air 'cd /Users/antonellosiano/Projects/nuzantara && \
  git checkout main && \
  git pull pro main'   # o "origin main" se origin è configurato su Air
```

**Verifica:** dopo il pull, i 4 branch Air devono rebase-re o mostrare solo i loro commit effettivi sopra main.

### Fase 2 — Cleanup branch morti

```bash
# fix/portal-bundle-audit ha zero commit. Rimuovere.
git worktree remove .worktrees/fix-portal-bundle-audit
git branch -D fix/portal-bundle-audit
```

### Fase 3 — Merge ordine consigliato (una PR per volta)

**Ordine:** dal meno rischioso al più rischioso. Ogni merge seguito da pytest + tsc.

#### PR 1: `v2-client-app` → main

- **Rischio:** basso
- **Review focus:**
  - Migration 111 (notification_log): safe, `CREATE TABLE IF NOT EXISTS`, rollback incluso
  - Schema mismatch fix (plan vs reality) — documentati nel log
  - portal_deadline_watchdog cron (6h) — NON attivare finché migration 111 non applicata
- **Checklist prima del merge:**
  - [ ] Applicare migration 111 su dev DB
  - [ ] Verificare `pytest backend/tests/unit/routers/portal_*`
  - [ ] QA visivo `/portal/*` su preview Vercel
- **Merge:** `git merge --no-ff v2-client-app -m "feat(portal): L2 Client App — 3 hero cards + family + notification prefs"`

#### PR 2: `compliance/pdp-coverage-push` (Air-1) → main

- **Rischio:** basso
- Un solo commit, solo additive (nuove exception classes + audit tool)
- Zero fix a business logic
- **Merge:** `git merge --no-ff compliance/pdp-coverage-push`

#### PR 3: `solidification/s09-services` (Air-2) → main

- **Rischio:** basso
- 7 fix atomici + 2 doc, scope chiaro
- **Review focus:** verificare nessun fix tocchi `services/events/`, `services/crm/`, `services/database/` (enforced in audit)
- **Checklist:**
  - [ ] Sweep tests: `pytest backend/tests/services/{monitoring,memory,oracle,routing,misc,article_composer,rag/agentic}`
- **Merge:** `git merge --no-ff solidification/s09-services`

#### PR 4: `solidification/s13-middleware` (Air-4) → main

- **Rischio:** basso
- +23 test middleware, 1 fix fail-open su rate_limiter
- **Merge:** `git merge --no-ff solidification/s13-middleware`

#### PR 5: `graphrag/completion-gaps` (Air-3) → main

- **Rischio:** basso (lavoro su KG DB, no business logic)
- **Review focus:**
  - Entity linker 58→33,562 mentions (dati, non codice critico)
  - Community summaries 6,310 (deterministic fallback ben documentato)
  - RRF decisione negativa motivata — no behavior change in produzione
- **Merge:** `git merge --no-ff graphrag/completion-gaps`

#### PR 6: `opus47-routing-audit` → main

- **Rischio:** MEDIO — richiede coordination con deploy Fly.io
- **BLOCCATO da:** Dockerfile update per imbarcare `claude` CLI (vedi DOCKER-CLAUDE-CLI.md)
- **Review focus:**
  - 4 call site migrati: article_composer, coreference, multi_ai_adapter, kg_langgraph
  - Fallback OAuth: keychain, token_1/2/3, token_legacy (test in place)
  - Env `KG_REASONING_PROVIDER=openai` come escape hatch
- **Checklist obbligatoria prima del merge:**
  - [ ] Dockerfile apps/backend-rag con `claude` CLI installato
  - [ ] Secret `CLAUDE_CODE_OAUTH_TOKEN` iniettato su Fly.io (`fly secrets set`)
  - [ ] Test live `complete_async()` su staging Fly.io
  - [ ] Preparato rollback (env var per forzare OpenAI fallback)
- **Merge:** `git merge --no-ff opus47-routing-audit`

#### PR 7 (ULTIMA, rischio alto): `v2-team-ops` → main

- **Rischio:** ALTO — -25545 linee (cleanup 4 orphan apps)
- **Review focus:**
  - Commit `f31dc5b22` "chore: remove 4 orphan satellite apps"
  - Verificare le 4 app siano davvero orphan (grep referenze cross-repo)
  - Controllare nessun workflow CI / Vercel project dipenda
- **Checklist obbligatoria:**
  - [ ] Full grep delle 4 app cancellate su tutto il repo + altri repo Balizero
  - [ ] Verify Vercel deployments (console) per 4 app
  - [ ] Backup branch tag prima del merge: `git tag backup-pre-team-ops-cleanup`
- **Se cleanup non sicuro:** fare un cherry-pick dei 6 commit "puliti", NON mergere `f31dc5b22`.
- **Merge (se OK):** `git merge --no-ff v2-team-ops`

### Fase 4 — Pulizia post-merge

```bash
# Rimuovere worktree mergiati
git worktree remove .worktrees/v2-client-app
git worktree remove .worktrees/opus47-routing
git worktree remove .worktrees/v2-team-ops
# Air:
ssh air 'cd /Users/antonellosiano/Projects/nuzantara && \
  git worktree remove .worktrees/pdp-coverage && \
  git worktree remove .worktrees/s09-services && \
  git worktree remove .worktrees/graphrag-completion && \
  git worktree remove .worktrees/s13-middleware'

# Push main sincronizzato
git push origin main
ssh air 'cd /Users/antonellosiano/Projects/nuzantara && git push pro main'
```

## Alternative se vuoi limitare il rischio

- **Solo PR 1–5** (basso rischio) e bloccare PR 6–7 per revisione più accurata.
- **PR 6** (opus47) può restare su branch finché Dockerfile non è pronto.
- **PR 7** (v2-team-ops) può essere splittato: cherry-pick dei 6 commit feature, scartare `f31dc5b22`.
