# Pro-1 — L2 Client App Portal (A breve 3-5h)

## Obiettivo

Eseguire il plan `docs/superpowers/plans/2026-04-17-v2-rollout-03-client-app.md`.

Trasformare `my.balizero.com/portal/*` da feature-tabs a **matter-first dashboard** con 3 hero cards sempre visibili, WA push opt-in, family route, theme riallineato.

## Contesto

- Macchina: Pro (cwd `/Users/nuzantara/Desktop/nuzantara`)
- Branch nuovo: `v2-client-app` (worktree `.worktrees/v2-client-app`)
- Blocked by: foundation + funnel-hub (entrambi ✅ già mergiati)
- Plan completo: `docs/superpowers/plans/2026-04-17-v2-rollout-03-client-app.md`
- Design: `docs/superpowers/specs/2026-04-17-v2-subdomain-rollout-design.md`

## Scope SÌ

- Creare worktree `.worktrees/v2-client-app` su branch `v2-client-app` da `main`
- Eseguire tutti i task del plan in ordine (Task 1 → fine)
- Migration 110 (`migrations/110_*.sql`) per `notification_prefs`
- Endpoint GET/PUT `/api/portal/notification-prefs`
- Endpoint `/api/portal/dashboard-summary` (aggregato 3 hero)
- Portal `apps/mouth/app/portal/*`: refactor home con 3 hero + lista MatterCard
- Cron `portal_deadline_watchdog.py` scansione `lkpm_reports.due_date` + `clients.visa_expiry_date`
- Test (vitest frontend, pytest backend)
- Commit piccoli, messaggi `feat(portal):`, `feat(api):`, `feat(migration):`

## Scope NO

- NON toccare L3 Team Ops (slot Pro-3)
- NON toccare L1 Funnel Hub (già live)
- NON merge in main — fermati prima
- NON push senza review umana
- NON creare PR (lascia a me al rientro)

## Deliverables attesi

1. Branch `v2-client-app` con N commit atomici
2. Migration 110 applicabile (test su dev DB)
3. Test pass: `pytest apps/backend-rag/backend/tests/` rilevanti + `npm test` mouth
4. `tsc --noEmit` pulito
5. Report finale in `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-1.log`

## Stop conditions

- Loop errori > 3 sullo stesso task → ferma, scrivi log, esci
- Plan task segna dipendenza che non esiste → ferma, scrivi log
- Test regression su altri moduli → rollback, ferma
- Tempo > 5h → checkpoint e ferma

## Skills da invocare in ordine

1. `superpowers:using-superpowers` (gate iniziale)
2. `superpowers:using-git-worktrees` (per creare il worktree)
3. `superpowers:executing-plans` (per eseguire il plan)
4. `superpowers:verification-before-completion` (prima di marcare done)

## Prompt da incollare

```
Esegui il plan docs/superpowers/plans/2026-04-17-v2-rollout-03-client-app.md
nel worktree .worktrees/v2-client-app (branch v2-client-app da main).

Vincoli:
- piccoli commit atomici
- NO push, NO merge in main, NO PR
- stop dopo 5h o errori loop >3
- log finale in docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-1.log

Usa superpowers:executing-plans. Inizia ora.
```
