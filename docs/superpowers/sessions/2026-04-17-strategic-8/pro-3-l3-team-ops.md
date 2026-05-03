# Pro-3 — L3 Team Ops End-to-End (C estesa 12-24h)

## Obiettivo

Eseguire il plan `docs/superpowers/plans/2026-04-17-v2-rollout-04-team-ops.md` end-to-end: spec → implementazione → test → deploy staging → verify.

## Contesto

- Macchina: Pro (cwd `/Users/nuzantara/Desktop/nuzantara`)
- Dipende da: L2 Client App (Pro-1) idealmente completato, ma può girare in parallelo su branch separato
- Plan: `docs/superpowers/plans/2026-04-17-v2-rollout-04-team-ops.md`
- Design: `docs/superpowers/specs/2026-04-17-v2-subdomain-rollout-design.md` sezione L3
- Target subdomain: `team.balizero.com` (o path `/team-ops` in app esistente — verifica plan)

## Scope SÌ

- Worktree `.worktrees/v2-team-ops` branch `v2-team-ops` da main
- Eseguire tutti task del plan L3 in ordine
- Backend endpoints `/api/team-ops/*` (RBAC Zero+Asya=admin)
- Frontend pagine team ops (dashboard, assegnazioni, carichi, metriche)
- Migration se serve (numerare dopo 110 di L2, o coordinare)
- Test coverage nuovi endpoint
- Deploy su staging/preview Vercel se possibile
- Screenshot QA in `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-3-qa/`

## Scope NO

- NON merge in main senza review
- NON deploy production
- NON toccare L2 Client App (Pro-1 ci lavora)
- NON cambiare RBAC esistente
- NON inventare feature oltre plan

## Deliverables attesi

1. Branch `v2-team-ops` con N commit atomici
2. Test pass (pytest + vitest + tsc)
3. Preview Vercel funzionante (URL nel log)
4. Screenshot QA principali viste
5. Checklist plan tutta spuntata
6. Log finale in `docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-3.log`
7. PR draft **non aperta** — pronta da aprire con `gh pr create` ma aspetta umano

## Stop conditions

- Plan L3 non esiste o incompleto → leggi design, ma **ferma e chiedi** prima di inventare scope
- Errori loop > 3 stesso task → checkpoint + stop
- Tempo > 20h → checkpoint ogni 4h, stop forzato a 24h
- Merge conflict irrisolvibili con main → stop e chiedi

## Checkpoint intermedi (C estesa)

Ogni 3-4h, scrivere update in log con:

- task completati
- task in corso
- blocker aperti
- decisioni prese autonomamente

## Skills

1. `superpowers:using-superpowers`
2. `superpowers:using-git-worktrees`
3. `superpowers:executing-plans` (o `subagent-driven-development` se plan ha task indipendenti)
4. `superpowers:test-driven-development`
5. `superpowers:verification-before-completion`
6. `superpowers:requesting-code-review` (self-review prima del log finale)

## Prompt da incollare

```
Sessione Pro C estesa 12-24h. Obiettivo: eseguire end-to-end il plan
docs/superpowers/plans/2026-04-17-v2-rollout-04-team-ops.md.

Worktree .worktrees/v2-team-ops branch v2-team-ops da main.

Deliverables: implementazione completa + test + preview Vercel + screenshot QA.
Checkpoint ogni 3-4h nel log.

Regole:
- NO merge main, NO deploy prod, NO PR open (draft pronta)
- Stop hard 24h
- Se plan incompleto, FERMA e chiedi

Log: docs/superpowers/sessions/2026-04-17-strategic-8/logs/pro-3.log

Usa superpowers:executing-plans + TDD. Inizia.
```
