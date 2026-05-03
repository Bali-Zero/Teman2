# Air-2 — S09 Services Layer Solidification (C estesa 12-24h)

## Obiettivo

Nuovo ciclo di solidification (dopo S07 DB, S08 CRM, S10 Cron): **S09 Services layer** in `apps/backend-rag/backend/services/`.

## Contesto

- Macchina: Air (cwd `/Users/antonellosiano/Projects/nuzantara`)
- Pattern solidification: vedi `docs/superpowers/solidification-reports/S06-*`, `S07-*`, `S08-*`, `S10-*`
- Ciclo solidification = fix multipli coordinati in un layer specifico, con report finale strutturato
- Target: `apps/backend-rag/backend/services/` (inclusi `services/events/` EventBus già solidificato)
- Memory: 414k LOC backend-rag, 1783 TODO/FIXME

## Scope SÌ (C estesa — lavoro di volume)

1. **Fase 1: Audit** (3-4h)
   - Enumerare file in `backend/services/`
   - Per ogni file: LOC, TODO count, test coverage, ultima modifica
   - Identificare top 10 candidati (alta LOC + bassa coverage + alto TODO)
2. **Fase 2: Fix multipli** (8-12h)
   - 5-8 fix concreti sui file top
   - Pattern tipici: error handling, retry policies, timeout, connection pooling, logging strutturato, metric emission
   - NO refactor architetturale — SOLO solidification (fix bug, robustezza, osservabilità)
3. **Fase 3: Report** (1-2h)
   - `docs/superpowers/solidification-reports/S09-services-layer.md`
   - Sezioni: Audit, Fix applicati, Test coverage before/after, Raccomandazioni future
4. **Fase 4: Test + commit atomici**
   - Branch `solidification/s09-services`
   - 1 commit per fix (atomic)
   - Test pytest verdi alla fine

## Scope NO

- NON refactor architetturali (creazione nuovi moduli, move file, rename)
- NON toccare EventBus (già solidificato)
- NON toccare DB layer (S07 già fatto)
- NON toccare CRM (S08 già fatto)
- NON toccare cron (S10 già fatto)
- NON merge main, NON push, NON deploy

## Deliverables attesi

1. Branch `solidification/s09-services` con 5-8 commit atomici
2. Audit JSON `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-2-s09-audit.json`
3. Report strutturato `docs/superpowers/solidification-reports/S09-services-layer.md`
4. Test pytest verdi
5. Coverage report before/after
6. Log finale `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-2.log`

## Stop conditions

- Tempo > 20h → checkpoint + stop 24h hard
- Se un fix richiede cambiamento API pubblico → ferma, log, skippa
- Se test regression su layer diverso → rollback + stop
- Checkpoint ogni 4h nel log

## Skills

1. `superpowers:using-superpowers`
2. `superpowers:using-git-worktrees`
3. `superpowers:systematic-debugging`
4. `superpowers:test-driven-development`
5. `superpowers:verification-before-completion`
6. `simplify` (per fix di qualità)

## Prompt da incollare (Air via tmux)

```
Sessione Air C estesa 12-24h. Obiettivo: S09 Services layer solidification.

Pattern: segui stile S07/S08/S10 in docs/superpowers/solidification-reports/.
Target: apps/backend-rag/backend/services/ (escluso events/ già solidificato).

Fasi:
1. Audit (3-4h) — JSON enum file+metriche
2. Fix multipli (8-12h) — 5-8 commit atomici, NO refactor architetturale
3. Report (1-2h) — S09-services-layer.md
4. Test pytest verdi

Worktree .worktrees/s09-services branch solidification/s09-services da main.

NO merge, NO push. Checkpoint ogni 4h. Stop hard 24h.
Log: docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-2.log

Usa superpowers:systematic-debugging + TDD + simplify. Inizia.
```
