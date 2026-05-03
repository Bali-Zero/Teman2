# Air-1 — UU PDP Coverage Push (A breve 3-5h)

## Obiettivo

Alzare coverage compliance UU PDP (Indonesian Personal Data Protection) da 0.67% attuale verso target 20%+ tramite typing delle silent exceptions.

## Contesto

- Macchina: Air (cwd `/Users/antonellosiano/Projects/nuzantara`)
- SSH: `ssh air`
- Memory "X Blitz + Tech Enhancement + UU PDP": 943 silent exceptions, CI coverage 0.67%
- Memory ref: revenue UU PDP compliance upsell $30K MRR → **rischio legale reale**
- Backend path: `apps/backend-rag/backend/`

## Scope SÌ

1. Enumerare tutte le `except:` / `except Exception:` silent (no re-raise, no log) in `apps/backend-rag/backend/`
2. Categorizzare per modulo (auth, crm, kg, llm, middleware, ...)
3. Tipizzare le eccezioni critical path (auth, crm write, PII handling) con classi tipate in `backend/core/exceptions.py`
4. Aggiungere logging strutturato (richiesta UU PDP: audit trail)
5. CI coverage target: portare almeno moduli critical path (auth, crm, PII) a coverage >50%
6. Branch `compliance/pdp-coverage-push` worktree dedicato
7. Test pytest per ogni exception typed

## Scope NO

- NON cambiare business logic, SOLO exception handling
- NON toccare frontend (Air non ha browser)
- NON toccare cron o infrastruttura deploy
- NON toccare Fly.io config
- NON merge main, NON deploy

## Deliverables attesi

1. Branch `compliance/pdp-coverage-push` con N commit (raggruppati per modulo)
2. `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-1-pdp-audit.json` con enum completo silent exceptions (path, line, severity)
3. Coverage report prima/dopo in log
4. `backend/core/exceptions.py` esteso con classi tipate (es. `PDPAuditRequired`, `PIIAccessDenied`, ...)
5. Test pass `pytest apps/backend-rag/backend/tests/`
6. Log finale `docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-1.log`

## Stop conditions

- Tempo > 5h → stop e report parziale
- Se loop errori test > 3 → stop
- Se enum silent exceptions > 500 in un singolo modulo → stop e chiedi priorità
- Se un modulo richiede modifica business logic → skippa e segnala in log

## Skills

1. `superpowers:using-superpowers`
2. `superpowers:using-git-worktrees`
3. `superpowers:systematic-debugging`
4. `superpowers:test-driven-development`
5. `superpowers:verification-before-completion`

## Prompt da incollare (su Air via SSH/tmux)

```
Sessione Air A breve 3-5h. Obiettivo: UU PDP compliance coverage push.

Partenza: 0.67% coverage, 943 silent exceptions in apps/backend-rag/backend/.
Target: tipizzare critical path (auth, crm, PII) + coverage >50% su quei moduli.

Worktree .worktrees/pdp-coverage branch compliance/pdp-coverage-push da main.

Deliverables:
1. audit JSON (path, line, severity) in log/air-1-pdp-audit.json
2. backend/core/exceptions.py esteso
3. test pytest passing
4. coverage report before/after

NO merge, NO deploy, NO business logic changes. Stop 5h.
Log: docs/superpowers/sessions/2026-04-17-strategic-8/logs/air-1.log

Usa superpowers:systematic-debugging + TDD. Inizia.
```
