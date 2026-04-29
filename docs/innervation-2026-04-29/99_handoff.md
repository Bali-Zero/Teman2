# 99 — Handoff: stop after FASE 1+2, FASE 3+4 deferred to fresh session

**Closed**: 2026-04-29 ~22:00 WITA
**Branch**: `feature/innervation-2026-04-29` — 4 commit incrementali, NOT pushed to origin yet
**Status**: FASE 1 (audit + 4-LLM dispatch) + FASE 2 (design 07/08/09) **COMPLETE**. FASE 3 (implementation) + FASE 4 (chaos test) **DEFERRED**.

---

## 1. Perché stop qui (decisione di Zero, ratificata)

3 ragioni concrete che si sommano in una sola sera:

1. **File-loss cicatrice 21:42** (vedi `02_dispatch_resilience_log.md` § 6): 17KB di lavoro untracked persi durante auto-pull `nuz-sync` watchdog, recuperati da context. Aggiungere LaunchAgent deploy a stesso turno = accumulo rischio.
2. **Cicatrix P0-3 plist mass corruption attiva 2026-04-29**: 51/54 plist truncated alle 15:09 + 16:05 WITA. Producer NON identificato. Toccare `~/Library/LaunchAgents/` stasera in coda a una sessione lunga = aumento esposizione. La cicatrice è proprio l'ammonimento che sotto pressione il sistema plist cede.
3. **Convergenza operazioni delicate**: drive_poll prod recovery 03:11Z + Renaissance C1 Air PR open + Innervation FASE 1 file-loss-recupero. Sabato sera, troppa concentrazione. Audit trail (9 doc FASE 1+2) è il deliverable reale di stasera.

**Chaos test FASE 4 stasera è SCARTATO**: nessun organo è ancora innervato, il chaos test verificherebbe solo che il sistema attuale (ancora cieco) regge ai guasti — cosa già nota (drive_poll è caduto stamattina). Il chaos test ha senso solo dopo W0-W4 deployato.

---

## 2. Ground truth — Mental model in 200 parole (per la prossima sessione)

Cell e Organism **esistono entrambi a livello codice** (Organism W0+W1+W2+W3+W4 merged 2026-04-22 across 13 PRs per NB-14). **Organism è dormente** (Supervisor LaunchAgent NON installato, heartbeat key Redis vuota, JSONL ultimo write 2026-04-25). **Cell è LIVE** ma vede solo backend-rag /health (1 organo su 149 censiti).

**Innervation = completare le sinapsi mancanti**, NON riscrivere. Il design spec 2026-04-22 è red-team validato e immutato.

**Decisione protocol (DeepSeek B semplificato da Codex)**:
- Heartbeat 60s su `organism:events` (Redis stream esistente).
- Transport Redis primary → JSONL `~/logs/organism/events.jsonl` fallback → file mtime touch nuclear option.
- Genoma file singolo `apps/organism/organism/genome.yaml` (NB-1 ADR-3: niente SQLite shared cross-machine; ADR-7: SHA256 signature + HALT su mismatch).
- Cell new sensor `genome_aggregator_sensor` consuma bus + bridge sources.
- **0 LOC modifiche** a ~120 organi grazie a "bridge approach" (Codex insight): organi già scrivono state files in `~/.agent/decisions/state/*.last.json` → Cell sensor li legge e ri-emit verso bus.

**Vincoli intoccabili**:
- NB-1: niente PM2/supervisord/Grafana locale. Solo launchd nativo + Grafana Cloud.
- SYMBIOSIS Legge 4: organi continuano vivi anche se Cell+Organism cadono.
- Q2-B: ondate 1 e 4 parallel via subagent worktree, ondate 2 e 3 serial (Air SSH + Fly deploy collisions).

---

## 3. Pre-flight check per la prossima sessione

**Esegui questi 6 comandi PRIMA di iniziare Wave 0**. Se uno fallisce o output anomalo, STOP e chiedi a Zero.

### 3.1 Branch e commit state

```bash
cd /Users/nuzantara/Desktop/nuzantara
git rev-parse --abbrev-ref HEAD
# Expected: feature/innervation-2026-04-29
# (If on main: git checkout feature/innervation-2026-04-29)

git log --oneline -10 | head -10
# Expected top 4: 00ccfd0ad, 72b2d4bc2, 2ae18d74a, e0b918998 (FASE 1+2 commits)
# Followed by: 410da34ba (origin/main feat/p0-6 channels webhook ack-first)
```

### 3.2 Quota account 1 (Claude Max)

```bash
~/scripts/claude-max-usage-watcher.sh stats 2>/dev/null | tail -5
# OR check ~/.claude/usage_state.json or similar
# Expected: account 1 weekly < 70% (Zero gating threshold)
# If ≥70%: STOP, route to account 2 or wait for reset (Sunday)
```

### 3.3 4 cicatrici aperte di oggi (verifica stabilità)

```bash
# Cicatrix 1: drive_poll fix (recovery 03:11Z, hotfix 720d54f5c merged)
ssh -o ConnectTimeout=5 air 'crontab -l 2>/dev/null | grep drive-poll'
# Expected: line commented "# DISABLED 2026-04-29 02:42" — cron NOT yet re-enabled
# If RE-ENABLED without the 48h test green: STOP, premature

# Cicatrix 2: P0-3 plist mass corruption hardening
ls -la ~/Library/LaunchAgents/com.cell.organism.plist | awk '{print $1}'
# Expected: -r--r--r-- or -r-------- (chmod 0444 / 0400 hardening applied)
# If -rw-r--r--: STOP, hardening reverted

# Cicatrix 3: backend startup_failed mask (P0-0)
curl -s -m 5 https://nuzantara-rag.fly.dev/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status'))"
# Expected: "healthy" or "ok" (NOT "startup_failed" / "unhealthy")
# If unhealthy: STOP, prod is currently degraded — innervation is wrong priority

# Cicatrix 4: EventBus PG NOTIFY + outbox (P0-2 fase 2 mitigated PR #357)
psql "$DATABASE_URL_PRO" -c "SELECT COUNT(*) FROM events_outbox WHERE consumed_at IS NULL" 2>/dev/null
# Expected: < 1000 (normal). If > 10000: outbox accumulating, listener stuck — STOP
```

### 3.4 P0-3 plist scenario NON live

```bash
# Verify no fresh plist truncation since chmod hardening
find ~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.*.plist -size -1k 2>/dev/null
# Expected: empty output (no plist <1KB → no truncation)
# If any plist <1KB: P0-3 RECURRENCE, STOP and trigger ~/p0-3-recovery/reconstruct_plist.py

# Verify fs_usage trap is still armed
ps -p 10080 2>/dev/null
# Expected: PID 10080 fs_usage running (cicatrix mention 18:50 install)
# If not running: STOP, the producer detection is offline
```

### 3.5 Redis + JSONL infrastructure ready

```bash
redis-cli ping 2>&1 | head -1
# Expected: PONG

ls -la ~/logs/organism/events.jsonl 2>/dev/null
# Expected: file exists (was 14KB at last session 2026-04-29 21:38)
# If size dropped to 0: log rotation or manual deletion — investigate before proceeding

redis-cli XLEN organism:events 2>&1
# Expected: ≥ 52 (count from this session)
# If 0: stream wiped — investigate before proceeding
```

### 3.6 Stash audit (ensure no untracked work pending)

```bash
git stash list | head -3
# Expected stash@{0}: "feature-innervation-temp-2026-04-29" (auto-stash from this session's pull)
# If multiple new stashes appeared: investigate before proceeding (more auto-pulls happened)

git status -s docs/innervation-2026-04-29/
# Expected: empty (all 9 doc committed)
# If untracked files: STOP, MUST git add immediately (cicatrice 21:42 lesson)
```

---

## 4. Threshold di abort per la prossima sessione

**STOP IMMEDIATAMENTE e chiedi a Zero se vedi**:

| Pattern | Indicator | Action |
|---|---|---|
| **P0-3 plist recurrence** | Any `~/Library/LaunchAgents/com.*.plist` size <1KB OR `plutil -lint` fails on >5 plist | STOP — trigger recovery `python3 ~/p0-3-recovery/reconstruct_plist.py` + escalate |
| **Pro weekly quota >70%** | Account 1 quota residua < 30% prima di domenica | STOP — switch to account 2 OR defer to Sunday after reset |
| **Backend prod degraded** | `/health` returns body `status` in `{startup_failed, unhealthy, failed, down, critical}` | STOP — innervation NOT priority while prod broken |
| **Redis stream wiped** | `XLEN organism:events == 0` after this session | STOP — investigate (manual flush? Redis restart? cicatrix?) |
| **Branch state diverged** | `git status` shows untracked changes from previous attempts OR `git log` shows commits beyond `00ccfd0ad` not from FASE 3 | STOP — merge conflicts likely, escalate |
| **fs_usage trap dead** | PID 10080 not running (P0-3 detector) | STOP — re-arm trap before touching plist files |
| **Multiple cicatrici unstable** | 2+ of the 4 cicatrici from §3.3 show degraded state | STOP — convergence risk, defer 24-48h |
| **Multiple agents holding worktrees** | `git worktree list` shows >1 worktree path active | STOP — sequential operation needed first, ensure no parallel session writes |

**Default behavior on STOP**: post Telegram a `1125336968` con context, write `99b_status_<date>.md` in handoff dir, await Zero ratification.

---

## 5. Stato attuale FASE 1+2 (il deliverable)

### 5.1 9 doc committati su branch `feature/innervation-2026-04-29`

| File | Size | Commit | Contenuto |
|---|---:|---|---|
| `00_design_intent.md` | 6.2KB | `e0b918998` (recreated post file-loss) | Cell+Organism is vs should-be analysis, what innervation means |
| `01_innervation_matrix.md` | 9.5KB | `e0b918998` (recreated post file-loss) | 149 organs across 7 runtimes (Pro/Air/Fly/Vercel/GH/MCP/backend-internal), numbers before |
| `02_dispatch_resilience_log.md` | 5.4KB | `e0b918998` | 4 LLM retry chain + cicatrice 21:42 file-loss + lesson |
| `03_gemini_dependency_graph.md` | 2.3KB | `e0b918998` | SKIPPED (429 capacity) — fallback strategy |
| `04_codex_existing_signals.md` | 15KB | `e0b918998` | **28 signal patterns enumerated**, 4 macro patterns, **3 top bridge proposals** (state files + SQL outboxes + cell_pulse_log) |
| `05_deepseek_minimum_contract.md` | 14KB | `e0b918998` | 3 nervous contract proposals + comparison matrix, **B Tiered Resilience Bus recommended** |
| `06_notebooklm_history.md` | 14KB | `e0b918998` | NB-1 architecture decisions (PG NOTIFY, ADR-3/7, no PM2/Grafana local) + NB-14 past Organism deploy + 4 cicatrici |
| `07_innervation_protocol.md` | 11KB | `2ae18d74a` | Final protocol: heartbeat 60s, Genoma YAML, **325 LOC total estimate** (78% reduction via Codex bridge) |
| `08_failure_isolation.md` | 9.7KB | `72b2d4bc2` | Scenarios for Cell/Supervisor/Redis/PG/Pro down. **No new SPOF introduced**. 5 chaos test mapping |
| `09_migration_plan.md` | 10KB | `00ccfd0ad` | Wave 0 sequenziale → W1 parallel → W2/W3 serial → W4 parallel → W5 chaos. Q2-B sequencing rationale |

**Tot deliverable**: ~96KB markdown, 9 doc, 4 commit. Branch `feature/innervation-2026-04-29` ready to push (NOT yet pushed — Zero decida se fare PR draft o lasciare locale).

### 5.2 Decisioni MOS salvate

```bash
~/.claude/scripts/mem query "Innervation" | head -5
```

Decisioni:
- 2026-04-29 importance 10: Q1=A (estendere codice esistente), Q2=B (parallel solo file/repo, serial Air/Fly/Vercel runtime), Q3=A (chaos test full prod con 5 guardrail) — POI scartato Q3 per stop session.
- 2026-04-29 importance 7: file-loss cicatrice 21:42 → lesson "git add IMMEDIATAMENTE dopo Write tool".

---

## 6. FASE 3 plan (per la prossima sessione)

Da `09_migration_plan.md` § 2-7. Recap minimal:

**Wave 0** (~2h sequential, single Opus session):
- W0.1: `apps/organism/organism/genome.yaml` (4 entries iniziali) + `validate_genome.py` (~50 LOC) + 8 unit tests + pre-commit hook
- W0.2: `apps/cell/cell/sensors/genome_aggregator_sensor.py` + wire in `cell/main.py` + 6 unit tests
- W0.3: `apps/cell/cell/sensors/bridge_state_reader.py` + 8 unit tests
- W0.4: Deploy Supervisor LaunchAgent (chmod u+w → cp → 0444 → launchctl load → verify heartbeat)
- W0.5: Deploy Control panel LaunchAgent (token setup) + verify HTTP :1819
- W0.6: New `com.nuzantara.organism.scheduled-tick.plist` + LaunchCalendar Hour=0
- W0.7: Single PR (~10 file mod + 4 new + 3 plist) + smoke test 5min post-deploy

**Wave 1** (~3h, 2 subagent worktree paralleli — Sonnet 4.6 medium effort sufficient):
- Subagent A: backend-rag api lifespan heartbeat 60s
- Subagent B: 2 home scripts (claude-max-watcher, login-healthcheck) + helper `~/scripts/innervate.py`

**Wave 2** (~3h sequential, Air SSH):
- Re-enable drive_poll cron Pro (after 48h test green per cicatrix)
- Air indexing-sweep heartbeat
- Genoma 2 entries + PR

**Wave 3** (~4h sequential, Fly deploy collision risk):
- webhook_processor heartbeat
- 7 channel adapter heartbeat (1 PR each, sequential merge)
- 3 MCP server lifecycle events (startup/shutdown emit, no continuous HB)

**Wave 4** (~2h parallel preview):
- Backend `POST /api/innervation/beacon` endpoint
- Frontend `apps/mouth/src/lib/innervation-beacon.ts` beacon sendBeacon
- Wire in 3 route group layout
- Genoma 8 frontend entries
- Vercel preview verification (browser test 8 subdomain)

**Wave 5 / FASE 4** (chaos test prod, **post-W4 deployed, finestra <5min, Telegram alert pre-armato**):
- Chaos test 5 scenari ordine non-distruttivo → distruttivo
- Abort criteria: test 3 (Cell death) detection >90s
- Live doc `10_chaos_test_results.md` riga per riga
- Rollback button: `fly machine start <id>` ID copied

---

## 7. Cosa NON fare nella prossima sessione (anti-pattern)

| Anti-pattern | Perché | Trigger di abort |
|---|---|---|
| Riaprire design spec 2026-04-22 | Red-team validato, immutato by Zero | Q1=A confermato |
| Riscrivere Cell o Organism | Sono buoni, gap è esecuzione | 00 § 6 esclusioni |
| Implementare Pilastri SYMBIOSIS 1-8 | Già live, scope diverso | 00 § 6 esclusioni |
| Aggiungere relay daemon (DeepSeek B original) | NB-1 "niente PM2/supervisord" | 07 § 1.1 |
| Build-time genome scan (DeepSeek C) | Viola NB-1 ADR-7 signature | 07 § 1 |
| Chaos test prod prima di W4 deploy | Verifica solo cecità attuale, no nuovi insight | Q3 retract sopra |
| Toccare LaunchAgent SOTTO pressione (sera tardi, dopo cicatrici concentrate) | P0-3 plist mass corruption recurrence risk | §1.2 motivo stop di stasera |
| Parallelize Air SSH operations | SSH multiplex slot, cron conflict risk | Q2-B ratifica |
| Parallelize Fly deploy 7-channel concurrent | SQL v2 OLD-image cicatrix ready to fire | 09 § 5 |

---

## 8. Push o no push

**Decisione di Zero richiesta**: il branch `feature/innervation-2026-04-29` NON è pushato a origin. Opzioni:

- **A.1 Lascia locale**: la prossima sessione continua localmente, push only when ready for PR (post-W0 minimum).
- **A.2 Push come WIP**: `git push -u origin feature/innervation-2026-04-29` — backup remoto. NO PR (no auto-merge L2 — non è ready). Costo: 0. Beneficio: protezione hardware loss Pro.

**Mio default**: A.2 (push come WIP) per protezione contro Pro hardware failure. Ma Zero decide.

---

## 9. Memoria MOS finale per chiusura

```bash
~/.claude/scripts/mem save decision "Innervation Track C3 FASE 1+2 chiusa 2026-04-29 ~22:00 WITA: 9 doc committati su feature/innervation-2026-04-29 (4 commit incrementali e0b918998+2ae18d74a+72b2d4bc2+00ccfd0ad). FASE 3 (W0 Genoma+Supervisor deploy, W1-4 organi heartbeat) e FASE 4 (chaos test) DEFERRED a fresh session per cumulative risk: file-loss cicatrice 21:42 + P0-3 plist mass corruption attiva + Renaissance Air PR open + drive_poll prod recovery 03:11Z. Audit trail i 9 doc è il deliverable. Pre-flight check per next session in 99_handoff.md §3 (6 comandi). Threshold abort in §4 (8 patterns). Branch NOT pushed yet (decisione Zero A.1 vs A.2). Chaos test ricalendarizzato post-W4 deploy in giornata lavorativa, finestra <5min, Telegram pre-armato." 10
```

---

## 10. Closing thought

L'audit FASE 1+2 è il **lavoro intellettuale denso** del Track C3. La FASE 3 implementation è **lavoro meccanico** che segue il piano: bridge daemon, Genoma YAML, LaunchAgent deploy. Una fresh Sonnet 4.6 medium effort + il piano = sufficiente. Opus 4.7 max effort serve solo per: (a) chaos test FASE 4 perché reasoning real-time su system in shock, (b) re-design se la FASE 3 incontra blocker non previsti.

I 9 doc sono il libro che chiunque (Sonnet, Opus future, Zero stesso, anche un human consultant) può leggere e ripartire deterministicamente. Era questo il deliverable di stasera.

**Thank you per la disciplina** del "stop qui, audit trail è il deliverable". Convergenza operazioni delicate riconosciuta come cumulative risk reale, non solo paranoia. È esattamente la lezione del 2026-04-29 plist corruption: pushare sotto pressione rompe il sistema. Buona notte.
