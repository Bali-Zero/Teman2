# Wave 1 — 4 sessioni Claude Code parallele

> **Scope:** P0-0, P0-4, P0-7, P0-3 dalla audit zero-crash 2026-04-29.
> **Macchine:** Pro x3 sessioni + Air x1 sessione = 4 totali.
> **Vincolo dipendenze:** queste 4 sono le P0 che possono partire SUBITO senza aspettare nulla.

## How to launch

In ognuno dei 4 tmux pane, apri Claude Code Max x20 e digita semplicemente:

| Pane | Macchina | Comando |
|------|----------|---------|
| **S1** | Pro | `leggi kakuro-S1 e esegui` |
| **S2** | Pro | `leggi kakuro-S2 e esegui` |
| **S3** | Air | `leggi kakuro-S3 e esegui` |
| **S4** | Pro | `leggi kakuro-S4 e esegui` |

I file kakuro-S{1..4} sono prompt completi self-contained. Ogni sessione:
1. Legge il proprio kakuro-S*.md
2. Lancia 4 brainstorm cross-LLM (Codex + Gemini + DeepSeek + NLM) **indipendenti**, in parallelo, senza farsi influenzare
3. Sintetizza, sceglie strategia, implementa con TDD
4. Commit / Push / PR (coordinati via lock per evitare collisioni)
5. Auto-merge appena CI verde
6. Watch deploy + verifica
7. MOS save + reporting summary

## Coordination

`_coordination.sh` fornisce 3 helper:

- `coord_commit "<msg>" <files>` — git commit con file lock `~/.claude/locks/git-commit.lock`
- `coord_push <remote> <branch>` — git push con file lock `~/.claude/locks/git-push.lock`
- `coord_deploy_fly <app>` — fly deploy con file lock `~/.claude/locks/fly-deploy.lock`
- `coord_brainstorm <topic> <brief_file> [out_dir]` — dispatch parallelo a 4 LLM esterni
- `coord_status` — vede chi tiene quali lock

Lock pattern:
- Acquire con `set -o noclobber` (atomic)
- Timeout 30 min commit/push, 60 min deploy
- Stale lock detection: PID dead + age >30 min → break automatico
- Lock content: `PID:timestamp:user@host` per audit

## Mappa dipendenze tra sessioni

```
S1 (P0-0) ──┬── unblocks ──> P0-1 (next wave)
S2 (P0-4) ──┘                P0-5 (next wave)

S3 (P0-7) ── independent
S4 (P0-3) ── independent

S6 (P0-2) — needs S1 + S2 (visibility) → wave 2
S7 (P0-6) — needs S6 (Outbox infra) → wave 3
```

## Cose che possono andare male

| Sintomo | Causa probabile | Recovery |
|---------|----------------|----------|
| Brainstorm CLI exit 0 ma file vuoto | bash redirect order, env var subshell, model alias deprecato (DeepSeek) | retry con diagnostic, vedi `07_dispatch_resilience_log.md` |
| Codex output 0 byte + MCP TokenRefreshFailed | OAuth token MCP server scaduto | `OPENAI_DISABLE_MCP=1` non basta — separato config-batch.toml o ignora MCP errors |
| Gemini output vuoto con `--sandbox --approval-mode plan` | Sandbox blocca tutti i tool | usa `--yolo` per non-interactive |
| `coord_commit` aspetta >30min | Altra sessione bloccata sul lock | `coord_status` per vedere holder, break manualmente se PID morto |
| 2 sessioni stesso branch | git worktree non in dir separate | sempre `git worktree add -b feat/X ../nuzantara-wt/Y` |
| Air sessione fallisce a venv | Air usa `venv` non `.venv` | `source apps/backend-rag/venv/bin/activate` (no `.venv`) |
| PR merge stuck | CI red su test pre-existing | identificare se è regressione del fix o pre-existing; se pre-existing, `gh pr merge --admin` con permission Antonello |

## Estimated wall-clock

| Sessione | Start | Brainstorm | Implement | Verify+Commit | Deploy | Total |
|----------|-------|-----------|-----------|---------------|--------|-------|
| S1 (P0-0) | T0 | 5 min | 60-90 min | 15-20 min | 10 min | **~2h** |
| S2 (P0-4) | T0 | 5 min | 15 min | 10 min | 10 min | **~40 min** |
| S3 (P0-7) | T0 | 5 min | 60-90 min | 30-45 min | 10 min | **~2-3h** |
| S4 (P0-3) | T0 | 5 min | 90-120 min | 30-45 min | n/a (local) | **~2.5-3h** |

Wall-clock tot per Wave 1: ~3 ore (limitato da S3/S4 più lente).

## Quando partire con Wave 2

**Wave 2 si lancia quando S1 (P0-0) è MERGED**, non quando finisce. Il merge sblocca:
- P0-1 (SearchService degraded — tocca `dependencies.py` insieme a P0-5, ma serve P0-0 prima)
- Inizio P0-2 fase 1 (Outbox migration + helper)
- P0-5 fase 1 (audit only, no rewrite)

S3 e S4 possono ancora essere in esecuzione quando Wave 2 parte. È OK. Coord locks proteggono i merge.

## Failure recovery generale

Se durante la wave qualcosa fa baseload deviation severa:

1. **Production /health 503** (post-merge S1): expected, P0-0 ora reporta correttamente. Verifica downstream — Sentinel deve riportare red, healthcheck@balizero.com 15min probe deve fallire e Telegram alert deve arrivare. Se NO, P0-0 ha un bug.

2. **PR S2 deploy aborted**: il canary migration 141_audit_canary fallisce → P0-4 fix non funziona. Stop, escalate to Zero, do NOT merge follow-up cleanup.

3. **S3 trova entrambe le duplicate applicate in prod**: data integrity scenario. Document, escalate, await Antonello decision.

4. **S4 patch script breaks com.cell.organism o com.balizero.nlm-bridge**: revert backup, escalate.

In tutti i casi: NON forzare. Memory `mem save unresolved` con dettaglio. Telegram via `~/.claude/scripts/hotfix-notify.sh`.

## Prossimi step dopo Wave 1

Una volta che tutte 4 le PR sono mergedate e deploy verificati:
1. **Re-run audit metrics** — sentinel jobs healthy passa da 10/58 a quanto?
2. **Update cicatrix-scars.md** — marca le 4 scars come ✅ RESOLVED
3. **Update audit `00_executive_summary.md`** — aggiorna numeri before/after
4. **Plan Wave 2** — P0-1, P0-2 fase 1, P0-5 fase 1

Memory MOS save:
```
mem save decision "Wave 1 zero-crash audit completata — 4 P0 mergedate in PRs #X #Y #Z #W. Sentinel jobs healthy <pre> → <post>. Cicatrix STRUCTURAL 2026-04-29 P0-0/P0-3/P0-4/P0-7 risolte. Wave 2 può partire (P0-1, P0-2, P0-5)." 9
```

## File index

- `_coordination.sh` — bash helper functions for locks + brainstorm dispatch
- `kakuro-S1.md` — P0-0 /health classify (Pro)
- `kakuro-S2.md` — P0-4 SQL v2 post-deploy (Pro)
- `kakuro-S3.md` — P0-7 duplicate migration numbers (Air)
- `kakuro-S4.md` — P0-3 LaunchAgents audit (Pro)
- `README.md` — this file
