# Wave 3 — Track C: 3 fix paralleli

**Goal:** Completare audit zero-crash 2026-04-29. Track C era originariamente "dipendente da Wave 2 foundation". Con Wave 2 mergeded, le dipendenze HARD sono soddisfatte → Wave 3 può essere parallelo aggressivo come Wave 2.

## Architettura

| Sessione | Macchina | Tipo | Agent del team | Fix |
|---|---|---|---|---|
| **Sessione 1** | Pro | Mia (questa) | A, B | P0-2 fase 2 (callsite refactor), P0-5 fase 2 (httpx rewrite) |
| **Sessione 2** | Pro | Tu apri | X | P0-6 (Channels webhook ack-first + Twitter CRC) |

**Totale fix concurrent: 3.**

## Comandi per te

### Sessione 2 (Pro)

In nuovo tmux pane Pro:
```
claude
```
Poi:
```
leggi /Users/nuzantara/Desktop/nuzantara/docs/audits/2026-04-29-zero-crash-audit/prompts/wave3/wave3-team-pro.md ed esegui
```

### Niente Sessione Air per Wave 3

P0-6 è troppo grosso (2-3 giorni) per un team-share. Lo lasciamo solo a Sessione 2 Pro (1 agent dedicato).

P0-2 fase 2 e P0-5 fase 2 li gestisco io qua nel team `wave3-mio` (2 agent paralleli).

## Fix dettaglio

### P0-2 fase 2 — Outbox callsite refactor

- **Effort:** 2 giorni
- **Cosa:** ~50 callsite `pg_notify(...)` in `services/` da convertire a `outbox.publish(conn, channel, payload)`. Aggiornare consumer per chiamare `outbox.acknowledge()`. SQL trigger functions in migrations 112, 113, 114 da migrare a Outbox-aware via nuova migration trigger replacement.
- **Test:** integration test che droppa PG connection durante 100 war_room events e verifica 0 events lost dopo replay.

### P0-5 fase 2 — httpx mass rewrite

- **Effort:** 1-2 giorni
- **Cosa:** Eseguire l'audit P0-5 fase 1 (PR #349) report. Per ogni violator (~50-200 callsite), convertire `httpx.AsyncClient(...)` in method body → lazy-singleton module-level. Registrare `close_X_client` in lifespan shutdown. Aggiungere CI guardrail `lint-golden-rule-10.yml`.
- **Test:** `lsof -p <pid>` stable FD count under load (vs current monotonic climb).

### P0-6 — Channels webhook ack-first + Twitter CRC

- **Effort:** 2-3 giorni
- **Cosa:** Tutti i webhook router (whatsapp, telegram, instagram, twitter) → ack-first pattern: persist payload in `inbound_webhooks` table → return 200 OK in <200ms → background worker process async. Twitter CRC handshake HMAC SHA-256 restoration (era disabilitato). ChannelSensor per Cell.
- **Test:** 100 webhook concurrent → 100% 200 OK in <200ms. Twitter CRC `?crc_token=X` → corretto response.

## Pattern uniforme tutti gli agent

Replicato da Wave 1 e Wave 2:

1. **Brainstorm cross-LLM** (Codex+Gemini+DeepSeek+NotebookLM) via `coord_brainstorm`. NB: dopo Wave 2 storm, alcuni LLM hanno avuto quota issues — accept partial brainstorm, fall back su brainstorm doc già in `11_brainstorms/` se necessario.
2. **Worktree isolato** in `../nuzantara-wt/<fix-id>/`
3. **TDD**: tests prima
4. **Self-review** prima di commit
5. **Coord commit + push + PR + auto-merge**
6. **Watch CI + deploy** + **verify deploy success**
7. **MOS save** + worktree cleanup
8. **Report DONE** solo dopo step 7 verificato

## Lock coordination

Riusa `_coordination.sh` da wave1/. Lock files in `~/.claude/locks/`.

**Critical:** TDD enforcement — verificare pytest CWD = `apps/backend-rag/` (lesson da Wave 2 #343 import bug). Aggiungere step esplicito al verify locale: `cd apps/backend-rag && PYTHONPATH=. pytest ...` (NON dal worktree root).

## Track D — Zero handoff (NON in Wave 3)

Restano 2 fix che richiedono decisione tua:
- **NB-E** Brevo email fallback provider (account creation Resend/SES)
- **P1-9** MCP partition (115-tool monolite split — architetturale)

Te li proponemo quando Wave 3 chiusa.

## File index

- `00_README.md` — questo file
- `wave3-team-pro.md` — prompt per Sessione 2 (P0-6)
