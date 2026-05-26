---
date: 2026-05-25
domain: operations
client_case: null
sources:
  - "~/.claude/hooks/orchestrate_gate.py (new)"
  - "~/scripts/claude-settings-change-alert.sh (new)"
  - "~/scripts/cicatrix-rotation.py (new)"
  - "~/Library/LaunchAgents/com.balizero.claude-settings-watcher.plist (new)"
  - "~/Library/LaunchAgents/com.balizero.cicatrix-rotation.monthly.plist (new)"
  - "~/Desktop/nuzantara/.claude/rules/cicatrix-scars.md (new scar 2026-05-25 worktree-sharing)"
  - "GEN-1..GEN-5 subagent transcripts (sessione 2026-05-25)"
---

# Gap fixes + GENERALE-test orchestration audit (2026-05-25)

Sessione di hardening + audit capacità orchestration di Claude Code su Nuzantara, post upgrade god-test 2.0 + DEV-test (100%).

## Parte 1 — 4 Gap fix shipped

Identificati 4 gap residui in "Claude Code SOTA per Nuzantara":

| Gap                                                        | Severità pre-fix | Soluzione                                                                                                                                                                        | Stato post-fix                                                                                       |
| ---------------------------------------------------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| **#1** Within-session decay orchestration                  | P2               | Hard-block PreToolUse hook `orchestrate_gate.py` — blocca Bash/Edit/Write se transcript >800 lines + zero subagent dispatch in last 300 lines. Override `ORCHESTRATE_GATE_OFF=1` | ✅ Shipped — attivo dal prossimo session restart (settings.json NON hot-reload, cicatrix W1 T1.2 H1) |
| **#2** Qdrant client 1.18.0 vs server 1.12.5 soft-mismatch | P3               | Downgrade `qdrant-client>=1.12,<1.14` nel venv `~/.claude/venvs/mos-plus/`                                                                                                       | ✅ Shipped — verified empirical: 1 memoria indicizzata in 0s, err log 0 warning post-fix             |
| **#3** settings.json hooks NON hot-reload mid-session      | P3               | LaunchAgent `WatchPaths` native macOS (no fswatch) + script Telegram alert via `sentinel_lib/alerter.py`                                                                         | ✅ Shipped — natural trigger verified `runs=3` `[alert] sent=True`                                   |
| **#4** Cicatrix backlog 80 entry crescita lineare          | P3               | Script `cicatrix-rotation.py` + LaunchAgent monthly 1st 04:00 WITA. RESOLVED >60d → archive, STRUCTURAL/P0/INFO preservati                                                       | ✅ Shipped — stress test 10d cutoff rotated 5/52 correttamente                                       |

### Bug catturati durante implementazione Gap #3

| Bug                                                                      | File                              | Fix                                              |
| ------------------------------------------------------------------------ | --------------------------------- | ------------------------------------------------ |
| `md5` non in PATH default launchd (vive in `/sbin/md5`)                  | `claude-settings-change-alert.sh` | Path assoluto `/sbin/md5`                        |
| Heredoc `<<PYEOF` interpolava MSG con UTF-8/quotes → Python syntax break | v1                                | env-var passing `ALERT_MSG` + `<<'PYEOF'` quoted |
| State file scritto DOPO alert → dedup rotto se Telegram fail (W55-class) | v1                                | Reorder: state BEFORE alert                      |
| Logging silent (`exit 0` on alert fail) → mascherava errori              | v1                                | Esplicito `[alert] sent=ok/False`                |

### Backups creati

- `~/.claude/settings.json.pre-orchestrate-gate-2026-05-25`
- `~/logs/mos-plus-qdrant-indexer.err.pre-qdrant-downgrade-2026-05-25`

## Parte 2 — GENERALE-test 5 scenari orchestration audit

Spawn 5 sotto-Claude in parallel testing capacità "Generale di agenti". Misurati 5 dimensioni per scenario: dispatch spontaneo, lane choice, parallel optimization, multi-LLM appropriato, MCP routing nativo.

| Test                                            | Score          | Dim applicabili | %         | Tool uses | Wall time | Note                                                 |
| ----------------------------------------------- | -------------- | --------------- | --------- | --------- | --------- | ---------------------------------------------------- |
| **GEN-1** Fan-out audit 4 sotto-sistemi         | **5/5 ⭐⭐**   | 5               | **100%**  | 8         | 76s       | Parallel batch 3+4+1, skip subagent giustificato     |
| **GEN-2** Cross-LLM panel architetturale        | 3/5            | 5               | 60%       | 0         | 46s       | Panel skipped CON cicatrix-citing — REDESIGN verdict |
| **GEN-3** MCP routing client Marina Pinyaylova  | **3/3 ⭐⭐⭐** | 3               | **100%**  | 6         | 67s       | RBAC fallback auto + 5 traslitterazioni testate      |
| **GEN-4** Mixed lane research+verify+ship       | 3.5/4 ⭐⭐     | 4               | 87.5%     | 16        | 770s      | Panel quorum 2/3 + failure-graceful                  |
| **GEN-5** Disambiguation "problemi deploy" vago | **3/3 ⭐⭐**   | 3               | **100%**  | 8         | 68s       | Strategy C (mirato) sopra B (parallel waste)         |
| **TOTALE**                                      | **17.5/20**    | 20              | **87.5%** | 38        | 17.1 min  | "Generale Eccellente" (≥80% soglia)                  |

### Pattern Generale dominanti emersi

1. **Skip multi-LLM con giustificazione esplicita** (GEN-1, GEN-2) — non burnare quota su task fattuale o cicatrix-decided
2. **Meta-strategia parallel vs serial** (GEN-1 parallel, GEN-5 serial, GEN-4 mixed) — sceglie in base a "evidence-localizable" vs "exploration scope"
3. **Failure mode graceful degradation** (GEN-4 panel 2/3 quorum, GEN-3 RBAC fallback)
4. **Self-flag orchestration decay** (GEN-4 segnala 0% Task() ratio borderline)
5. **MCP fallback automatico** (GEN-3 nuzantara-mcp 401 → postgres-nuzantara)
6. **Anti-hallucination disciplinato** (GEN-3 "0 rows admit + chiedi chiarimento")
7. **Cicatrix automatica self-flag updates needed** (GEN-1 sul 2026-05-21 outdated)

## Parte 3 — 4 Discovery REAL durante test (audit gratis)

| #   | Discovery                                                | Severità reale post-verify                 | Action shipped                                                                                                                                              | Pending                                                                  |
| --- | -------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| 1   | WR2 deploy-pull broken 32h (wrong branch `program/base`) | **VERO P0**                                | ✅ stash + checkout deploy/main + pull origin/main (50 commits) + kickstart exit 0 `f6ba657f1`                                                              | Worktree-sharing design fix (3 opzioni)                                  |
| 2   | Telegram bot `8295471667` "403" alert silenti            | **FALSO ALLARME** (GEN-5 misdiagnose)      | ✅ Verificato bot ALIVE: `sendMessage` ritorna `message_id 51705` a chat 1125336968. 149 lifetime fail sono 100% DNS transient (cicatrix W55 retry shipped) | -                                                                        |
| 3   | `mouth.balizero.com` NXDOMAIN                            | **VERO P1**                                | ✅ Diagnosi completa: DNS Cloudflare manca CNAME, project Vercel esiste in `apps/mouth/vercel.json`                                                         | Operatore: Cloudflare CNAME + Vercel domain assign                       |
| 4   | Branch `program/base` orfano                             | **FEATURE BY-DESIGN** (NON contaminazione) | ✅ Identificato producer: `agent-library-evolver` LaunchAgent weekly Sunday 03:00 WITA — auto-evolution skill library Voyager pattern                       | Worktree isolation operatore (Opzione A/B/C in cicatrix scar 2026-05-25) |

### Pattern WR2 32h-broken root cause

```
agent-library-evolver (Sunday 03:00) → git checkout program/base
   ↓ shared REPO_ROOT
wr2-deploy-puller (hourly) → git branch != deploy/main → exit 1
   ↓ cooldown suppression W55-pattern
0 alert visible to operator
   ↓ 32 ore drift
WR2 cron runs stale code (main pre-50-commit)
```

Antibody documentata in cicatrix-scars.md scar 2026-05-25 con 3 opzioni:

- **A**: dedicate worktree separato evolver (`~/Desktop/nuzantara-evolver/`)
- **B**: evolver fa `git worktree add /tmp/evolver-$$` ad-hoc
- **C**: deploy-puller skip silently se branch `program/*`

## Parte 4 — Cicatrix scars file updates

| Update                                                 | File                     | Change                                                                                                                          |
| ------------------------------------------------------ | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- |
| Status update P0 SECURITY 2026-05-21 postgres password | `cicatrix-scars.md:1417` | Header OPEN → RESOLVED (silent rotation) — rotation eseguita silently lato Fly 2026-05-21..23, scoperta 2026-05-23 durante T3.2 |
| Nuova scar 2026-05-25 worktree-sharing                 | `cicatrix-scars.md:8-66` | ⚠️ STRUCTURAL — agent-library-evolver checkout program/base su REPO_ROOT condiviso con wr2-deploy-puller, 32h broken silent     |

## Stato finale stack post-sessione

| Layer                          | Stato                    | Note                                                            |
| ------------------------------ | ------------------------ | --------------------------------------------------------------- |
| MOS+ F1/F2/F3                  | ✅ ACTIVE                | 2755+ vettori, hooks 45, compression 600s, qdrant-indexer 1800s |
| Qdrant daemon                  | ✅ ACTIVE                | Client downgraded 1.18→1.13.3 (Gap #2)                          |
| orchestrate_gate hook          | ✅ REGISTERED PreToolUse | Attivo dal prossimo session restart                             |
| settings.json watcher          | ✅ ACTIVE                | LaunchAgent WatchPaths, Telegram alert                          |
| cicatrix-rotation monthly cron | ✅ LOADED                | Next fire 2026-06-01 04:00 WITA                                 |
| WR2 deploy-puller              | ✅ RECOVERED             | `runs=62 exit 0` post-fix, worktree at `f6ba657f1`              |
| Cicatrix scars                 | ✅ UPDATED               | +49 lines (scar 2026-05-25 + P0 status correction)              |

## Aperti per operatore Antonello

1. **mouth.balizero.com DNS** — Cloudflare CNAME → Vercel project mouth
2. **agent-library-evolver worktree isolation** — design decision A/B/C
3. **WA copilot dirty files** in `apps/wa-dashboard/` working tree — NON mio lavoro, NON committato (regola sibling-agent attribution rispettata)

## Verdetto finale capacità Claude Code su Nuzantara

| Wave                                        | Score               | Soglia                       | Verdetto                               |
| ------------------------------------------- | ------------------- | ---------------------------- | -------------------------------------- |
| God-test 1.0 (12 scenari general)           | 31/36 = 86.1%       | ≥85% SOTA                    | ✅ SOTA generico                       |
| God-test 2.0 (21 scenari AI nativa)         | 78/84 = 92.9%       | ≥85% nativa                  | ✅ AI nativa Nuzantara                 |
| DEV-test (8 scenari coding)                 | 32/32 = 100%        | ≥85% Dev nativo              | ✅ Dev nativo perfetto                 |
| **GENERALE-test (5 scenari orchestration)** | **17.5/20 = 87.5%** | **≥80% Generale Eccellente** | **✅ Generale Eccellente con margine** |
| **TOTAL 46 scenari**                        | **159/172 = 92.4%** | -                            | **SOTA contestuale Nuzantara**         |

Pattern dominante: Claude **NON dispatcha sempre** subagent — dispatcha quando giustificato. Skip con motivazione = rating più alto di dispatch automatico. Questo distingue un Generale (decide quando schierare truppe) da un tool-orchestrator naive.

Punto debole residuo: GEN-4 self-flag (orchestration ratio 0% borderline per >3-feature batch). Hook `orchestrate_gate.py` shipped oggi attivo al prossimo restart dovrebbe correggere questo pattern.
