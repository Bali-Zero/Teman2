---
date: 2026-05-26
domain: wr2
client_case: Bali Zero internal — WR2 cron fleet empirical audit (35 LaunchAgent)
sources:
  - launchctl print gui/501/<Label> (35 LaunchAgent, run 2026-05-26 15:53 WITA)
  - ~/Library/LaunchAgents/com.balizero.wr2.*.plist (ProgramArguments + StartInterval + StartCalendarInterval + Label key)
  - /Users/nuzantara/logs/wr2_*.{err,log} (stderr/stdout mtime + tail)
  - /Users/nuzantara/.openclaw/workspace/logs/war-room-v2/*.error.log
  - /Users/nuzantara/.openclaw/bin/wr2/ (empirically MISSING)
  - /Users/nuzantara/Desktop/nuzantara-deploy/scripts/wr2_*.py (target script existence check)
cron_count: 35
hot_count: 2
warm_count: 16
cold_count: 17
healthy_count: 3
broken_count: 6
script_missing_count: 17
idle_by_design_count: 9
gate_off_wanted_count: 1
---

# WR2 cron fleet — empirical audit 2026-05-26 15:53 WITA

## Summary

| Verdict                               | Count | Note                                                                                                               |
| ------------------------------------- | ----- | ------------------------------------------------------------------------------------------------------------------ |
| **SCRIPT-MISSING (wrapper)**          | 17    | `~/.openclaw/bin/wr2/wr2-script-wrapper.sh` (e fratelli) NON installato                                            |
| **IDLE-BY-DESIGN (scheduled future)** | 9     | Plist con StartCalendarInterval/StartInterval, runs=0, exit=(never exited) — attendono prima esecuzione schedulata |
| **IDLE-BROKEN (last exit fail)**      | 6     | runs≥1 con exit≠0 ricorrente (DATABASE_URL, EX_IOERR, EX_CONFIG)                                                   |
| **HEALTHY (running)**                 | 2     | pg-proxy + queue-server, listener always-on                                                                        |
| **HEALTHY (idle between runs)**       | 1     | canva-oauth-watchdog, ultimo exit 0                                                                                |

**Priority cluster**: `HOT=2` (pg-proxy + queue-server), `WARM=16`, `COLD=17`.

**Cluster del 1 GATE-OFF-WANTED**: `canva-renderer` (exit 78 EX_CONFIG da wrapper missing, sotto kill-switch `wr2_canva_renderer_enabled != true` cicatrix 2026-05-13 → architettura bypass voluto). Classificato come SCRIPT-MISSING per esattezza causale.

## Root cause cluster

### Cluster A — Missing wrapper (`~/.openclaw/bin/wr2/` directory not deployed) — 17 cron

Sintomo: `program = /Users/nuzantara/.openclaw/bin/wr2/wr2-{script,cron,canva-renderer}-wrapper.sh` ma `~/.openclaw/bin/wr2/` non esiste sul filesystem.

Documentazione esplicita in `infra/openclaw/wr2/README.md`:

> The actual executable files live OUTSIDE this repo at `~/.openclaw/bin/wr2/`. This directory is the **versioned mirror** that documents what the deployed version should contain.

Sync mai eseguito. La dir `~/.openclaw/bin/` esiste con solo `nuzantara-mcp-env`, ma sotto-dir `wr2/` assente.

Affected cron (17):

WARM (8): `daily-metrics`, `draft-generator`, `fact-checker`, `fact-extractor`, `image-generator`, `supervisor`, `supervisor-watchdog`, `topic-selector` — target script Python esiste in `nuzantara-deploy/scripts/`, manca solo il bridge wrapper.

COLD (9): `canva-apply`, `canva-gc.weekly`, `canva-renderer`, `connector`, `dossier-compiler`, `learner-nightly`, `newsletter`, `oracle`, `strategos` — di cui 6 puntano a `backend.services.*_cli` Python module che NON ESISTE nel repo (`connector_cli`, `dossier_compiler_cli`, `learner_cli`, `newsletter_cli`, `oracle_cli`, `strategos_cli`). Questi 6 sono COLD-dead anche dopo fix wrapper, perché il target module è codebase debt orfana.

Fix proposto (≤5min wall, idempotent):

```bash
mkdir -p ~/.openclaw/bin/wr2
cp ~/Desktop/nuzantara/infra/openclaw/wr2/wr2-script-wrapper.sh ~/.openclaw/bin/wr2/
chmod +x ~/.openclaw/bin/wr2/wr2-script-wrapper.sh
# wr2-cron-wrapper.sh: esiste in scripts/, link OR copy
ln -sf ~/Desktop/nuzantara/scripts/wr2-cron-wrapper.sh ~/.openclaw/bin/wr2/wr2-cron-wrapper.sh
# wr2-canva-renderer-wrapper.sh: NON esiste in repo, da scrivere O retire canva-renderer plist
```

⚠️ Risk: dopo `mkdir + cp`, 17 cron diventano executable simultaneamente. Mitigation: prima test single-tick `launchctl kickstart -k com.balizero.wr2.<single-label>` per ognuno dei 8 WARM, verifica exit 0 prima di sbloccare i 9 COLD.

### Cluster B — DATABASE_URL_LOCAL / DATABASE_URL missing — 4 cron

Sintomo: cron HA wrapper esistente (bash direct, no `~/.openclaw/bin/wr2/`) ma exit 1 / exit 2 ricorrente con stderr `DATABASE_URL not set` o `DATABASE_URL_LOCAL not set in ~/.nuzantara-secrets.env`.

Affected: `pg-queue-sync` (exit 1 × 15), `sla-worker` (EX_IOERR × 4), `canva-lease-watchdog` (exit 2 × 14 ricorrente CRITICAL DATABASE_URL not set), `plist-watchdog` (exit 1 × 10).

Fix: aggiungere `DATABASE_URL_LOCAL=postgres://backend_rag_v2:<password>@127.0.0.1:15432/nuzantara_rag?sslmode=disable` a `~/.nuzantara-secrets.env` (mode 0400, gitignored). pg-proxy LaunchAgent già running (PID stabile), tunnel pronto. Operator-only (secret editing fuori scope agent).

### Cluster C — Trend-hunter EX_IOERR — 1 cron

`trend-hunter` exit 74 EX_IOERR runs=1, schedule 2h. Da diagnosticare separatamente (probabile IO/network upstream — log non analizzato in dettaglio in questo audit).

### Cluster D — Deploy-puller exit 1 — 1 cron

`deploy-puller` runs=3 exit=1. Cicatrix-family W50/W51/W52 (deploy-path desync, branch race `program/base`). Working tree `nuzantara-deploy` attualmente su branch `chore-cicatrix-rebase` invece di `deploy/main` (atteso) — possibile causa exit=1 corrente.

### Cluster E — Bottleneck design-driven (subagent bridge missing)

Dei 9 subagent `~/.claude/agents/wr2-*.md` (design-architect, brief-interpreter, storyboarder, layout-composer, critic, ig-metrics-analyst, image-prompt-author, external-bench), **NESSUNO è cron-spawned**. Sono dispatch-via-`Agent` tool da interactive Claude Code (orchestrator-only).

Il framework "carousel runs autonomously" è **incompleto by design**: manca il bridge da `topic-queue event → spawn Claude Agent design-architect via subprocess CLI`. I `supervisor` + `queue-server` esistono come listener queue, ma niente produce eventi → idle.

I 2 HOT cron (pg-proxy + queue-server) sono sufficienti per il primo carousel via interactive Agent dispatch in questa sessione. Bypass-design del cron autonomy. Workflow autonomous resta open issue.

## HOT path per primo carousel

| Cron           | Why HOT                                                                                                                                                                   |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `pg-proxy`     | localhost:15432 → Fly nuzantara-postgres. Senza, ogni script che tocca DB fallisce. Running stabile, runs=1.                                                              |
| `queue-server` | Python listener `/Users/nuzantara/.claude/skills/bali-zero-brand/_damar-queue-server.py`. Always-on, runs=1. Permette POST carousel-task se workflow autonomous attivato. |

Per il **primo carousel** non servono altri cron. Il design-architect verrà chiamato come Agent dispatch dall'interactive session, e produce slides+critic verdict in-process.

## Tabella completa 35 cron

Sorted by Priority (HOT first → WARM → COLD), then by label.

| Priority | Label (suffix)            | State           | Last exit      | Runs | Schedule   | Verdict                           | Target script                                 | Last log         |
| -------- | ------------------------- | --------------- | -------------- | ---- | ---------- | --------------------------------- | --------------------------------------------- | ---------------- |
| HOT      | pg-proxy                  | running         | (never exited) | 1    | keep-alive | HEALTHY                           | —                                             | 2026-05-26 13:28 |
| HOT      | queue-server              | running         | (never exited) | 1    | keep-alive | HEALTHY                           | —                                             | 2026-05-19 12:24 |
| WARM     | canva-oauth-watchdog      | not running     | 0              | 1    | 6h         | HEALTHY (idle between runs)       | —                                             | 2026-05-08 04:34 |
| WARM     | daily-metrics             | not running     | (never exited) | 0    | 06:00      | SCRIPT-MISSING (wrapper)          | wr2_daily_metrics.py                          | 2026-05-19 06:00 |
| WARM     | deploy-puller             | not running     | 1              | 3    | 1h         | IDLE-BROKEN (last exit fail)      | —                                             | 2026-05-08 08:09 |
| WARM     | draft-generator           | not running     | (never exited) | 0    | manual     | SCRIPT-MISSING (wrapper)          | wr2_draft_generator.py                        | 2026-05-24 05:58 |
| WARM     | fact-checker              | not running     | (never exited) | 0    | manual     | SCRIPT-MISSING (wrapper)          | wr2_fact_checker.py                           | 2026-05-23 15:24 |
| WARM     | fact-extractor            | not running     | (never exited) | 0    | manual     | SCRIPT-MISSING (wrapper)          | wr2_fact_extractor.py                         | 2026-05-23 15:24 |
| WARM     | ig-metrics-analyst.weekly | not running     | (never exited) | 0    | Mon 06:07  | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-11 06:07 |
| WARM     | ig-scraper.daily          | not running     | (never exited) | 0    | 03:00      | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-09 03:00 |
| WARM     | image-generator           | not running     | (never exited) | 0    | manual     | SCRIPT-MISSING (wrapper)          | wr2_image_generator.py                        | 2026-05-23 15:18 |
| WARM     | measurer                  | not running     | (never exited) | 0    | 6h         | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-26 11:41 |
| WARM     | pg-queue-sync             | not running     | 1              | 15   | 600s       | IDLE-BROKEN (last exit fail)      | —                                             | 2026-05-26 15:48 |
| WARM     | plist-watchdog            | not running     | 1              | 10   | 900s       | IDLE-BROKEN (last exit fail)      | —                                             | 2026-05-20 03:05 |
| WARM     | sla-worker                | not running     | 74: EX_IOERR   | 4    | 1800s      | IDLE-BROKEN (last exit fail)      | —                                             | 2026-05-26 15:28 |
| WARM     | supervisor                | spawn scheduled | 78: EX_CONFIG  | 1    | keep-alive | SCRIPT-MISSING (wrapper)          | wr2_supervisor.py                             | 2026-05-25 19:29 |
| WARM     | supervisor-watchdog       | spawn scheduled | 78: EX_CONFIG  | 1    | keep-alive | SCRIPT-MISSING (wrapper)          | wr2_supervisor_watchdog.py                    | 2026-05-26 13:26 |
| WARM     | topic-selector            | not running     | (never exited) | 0    | 05:10      | SCRIPT-MISSING (wrapper)          | wr2_topic_selector.py                         | 2026-05-24 05:10 |
| COLD     | canva-apply               | not running     | (never exited) | 0    | manual     | SCRIPT-MISSING (wrapper)          | wr2_canva_desktop_apply.py                    | 2026-05-23 15:37 |
| COLD     | canva-gc.weekly           | not running     | (never exited) | 0    | Mon 04:30  | SCRIPT-MISSING (wrapper)          | wr2_canva_garbage_collector.py                | 2026-05-18 04:30 |
| COLD     | canva-lease-watchdog      | not running     | 2              | 14   | 600s       | IDLE-BROKEN (last exit fail)      | (CRITICAL: DATABASE_URL not set ×14)          | 2026-05-26 15:48 |
| COLD     | canva-renderer            | spawn scheduled | 78: EX_CONFIG  | 1    | 300s       | SCRIPT-MISSING (wrapper)          | (wrapper canva-renderer-wrapper.sh)           | 2026-05-24 22:02 |
| COLD     | canva-token-watchdog      | not running     | (never exited) | 0    | 09:00      | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-24 09:00 |
| COLD     | connector                 | not running     | (never exited) | 0    | 04:00      | SCRIPT-MISSING (wrapper)          | backend.services.cognitive.connector_cli ✗    | 2026-05-24 04:00 |
| COLD     | dossier-compiler          | not running     | (never exited) | 0    | 04:30      | SCRIPT-MISSING (wrapper)          | backend.services.intel.dossier_compiler_cli ✗ | 2026-05-24 04:31 |
| COLD     | e2e-probe.daily           | not running     | (never exited) | 0    | 04:00      | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-21 04:00 |
| COLD     | external-bench.monthly    | not running     | (never exited) | 0    | Mon 07:00  | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-18 07:00 |
| COLD     | hardening                 | not running     | (never exited) | 0    | 6h         | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-26 11:41 |
| COLD     | learner-nightly           | not running     | (never exited) | 0    | 03:00      | SCRIPT-MISSING (wrapper)          | backend.services.learner.learner_cli ✗        | 2026-05-15 07:51 |
| COLD     | newsletter                | not running     | (never exited) | 0    | Mon 09:00  | SCRIPT-MISSING (wrapper)          | backend.services.newsletter.newsletter_cli ✗  | 2026-05-04 09:46 |
| COLD     | oracle                    | not running     | (never exited) | 0    | Sun 22:30  | SCRIPT-MISSING (wrapper)          | backend.services.cognitive.oracle_cli ✗       | 2026-05-17 22:33 |
| COLD     | reflexion.weekly          | not running     | (never exited) | 0    | Sun 02:30  | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-09 02:13 |
| COLD     | strategos                 | not running     | (never exited) | 0    | Sun 22:00  | SCRIPT-MISSING (wrapper)          | backend.services.cognitive.strategos_cli ✗    | 2026-05-03 22:00 |
| COLD     | trend-hunter              | not running     | 74: EX_IOERR   | 1    | 2h         | IDLE-BROKEN (last exit fail)      | —                                             | 2026-05-26 15:28 |
| COLD     | voyager.weekly            | not running     | (never exited) | 0    | Sun 02:00  | IDLE-BY-DESIGN (scheduled future) | —                                             | 2026-05-10 02:00 |

Tutti i label hanno prefix `com.balizero.wr2.` omesso per leggibilità.

## Open issues (sessioni dedicate fix)

| #    | Issue                                                                                                          | Effort | Risk                            | Affected                                                                    |
| ---- | -------------------------------------------------------------------------------------------------------------- | ------ | ------------------------------- | --------------------------------------------------------------------------- |
| OI-1 | Sync `infra/openclaw/wr2/` → `~/.openclaw/bin/wr2/` per 11 cron WARM/HOT (script python esiste)                | 30min  | Medium (test single-cron prima) | 8 WARM + 3 COLD canva-\*                                                    |
| OI-2 | Aggiungere `DATABASE_URL_LOCAL` a `~/.nuzantara-secrets.env`                                                   | 5min   | Low (operator-only)             | 4 cron                                                                      |
| OI-3 | Implementare `wr2-canva-renderer-wrapper.sh` OR retire `com.balizero.wr2.canva-renderer.plist` (gate-off 13gg) | 60min  | Medium                          | 1 cron (canva-renderer)                                                     |
| OI-4 | Decidere fate dei 6 cron COLD con `backend.services.*_cli` target inesistente (codebase debt orfana)           | 30min  | Low                             | connector, dossier-compiler, learner-nightly, newsletter, oracle, strategos |
| OI-5 | Bridge `topic-queue event → spawn Claude Agent design-architect` (workflow autonomous gap)                     | 4h     | High (definisce workflow shape) | All carousel pipeline                                                       |
| OI-6 | Diagnosi `trend-hunter` EX_IOERR                                                                               | 30min  | Low                             | 1 cron                                                                      |
| OI-7 | Diagnosi `deploy-puller` exit 1 + branch race `chore-cicatrix-rebase` vs `deploy/main`                         | 30min  | Low                             | 1 cron                                                                      |

## Raccomandazioni next-action

1. **Primo carousel WR2 procede SENZA fix cron**. Sufficiente HOT pg-proxy + queue-server. Subagent dispatchato via interactive Claude Code session (gestito separatamente).
2. **Sessione dedicata "WR2 cron repair"**: prioritizzare OI-2 (5min secret editing, Antonello-only) + OI-1 (sync wrapper, unlock 11 cron). OI-3 + OI-4 sono decisioni architetturali (retire vs revive), candidate per 4-LLM panel review prima di shippare.
3. **OI-5 (subagent autonomous bridge)** è il vero gap di prodotto: senza, WR2 resta semi-manual. Architettura: `cron supervisor → subprocess.run(["claude", "--print", "--model", "claude-opus-4-7", "--prompt", template])` → output → queue-server → carousel renderable. 4-LLM panel obbligatorio.
