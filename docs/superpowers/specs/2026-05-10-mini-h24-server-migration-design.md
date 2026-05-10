---
title: Mini-Pro2 come server H24 — migrazione cron Pro→Mini
date: 2026-05-10
author: Antonello Siano (design + decisioni); brainstorming Claude Opus 4.7 + Gemini 3.1 Pro + DeepSeek Reasoner + GPT-5.4 Codex
status: design draft pending Antonello approval
---

# Mini-Pro2 come server H24 — migrazione cron Pro→Mini

## §1 — Obiettivo, vincoli, non-goal

**Obiettivo**: trasformare Mini-Pro2 nel "server di casa Bali Zero" che gira H24
indipendentemente dal Pro. Pro torna macchina dev libera di spegnersi/riavviarsi
senza fermare niente di critico (notifiche regolatorie, digest competitor, OSINT,
cron Codex, ecc.).

**Vincoli HARD (non negoziabili)**:
1. **Zero duplicazione job**: ogni LaunchAgent gira su una macchina sola.
   Doppio-trigger di un job non-idempotente (Brevo, social, Telegram broadcast)
   = email doppia ai clienti, post doppio sui social = blocker reputazionale.
2. **Mini RAM 24 GB**: macOS riserva 4–6 GB; restano ~18 GB per OS+brew+Ollama+
   50 cron. Picchi di concorrenza vanno controllati con semaforo.
3. **Mini NO Postgres, NO Qdrant**: solo redis. Job che leggono Postgres@17/Qdrant
   Pro restano sul Pro o vanno wrappati per puntare a `Nuzantara.local:5432`
   (network-exposed) — fuori scope di questo spec.
4. **Sync 4 daemon attuali + git-pull-main devono restare verdi**: memory-sync
   (5 min), claude-config-sync (1 h), secrets-sync-mini (24 h), drive-sync (12 h),
   git-pull-main (5 min su Mini).

**Non-goal di questo spec**:
- Non migriamo WR2 microservices live (queue-server, supervisor, pg-proxy,
  canva-renderer, observatory, organism cells). Richiederebbero Postgres+Qdrant
  su Mini → fuori scope.
- Non installiamo Postgres replica né Qdrant mirror su Mini.
- Non tocchiamo OAuth Codex/Gemini/NLM auth se già funzionano (verifica only).
- Non duplichiamo il modello Ollama `gemma4:26b` né `deepseek-r1:32b` (non entrano
  in 24 GB).

## §2 — Stato attuale (verificato 2026-05-10 09:30–10:00 WITA)

### Pro
- Load avg 14.93. RAM 47/48 GB used (462 MB unused). Compressor 13 GB.
- Ollama 3 modelli pinned 100% GPU "Forever": qwen3.5:9b (9.2 GB) + qwen3:8b
  (6 GB) + gemma4:26b (19 GB) = ~34 GB GPU.
- 127 LaunchAgent: 60 com.balizero, 44 com.nuzantara, 14 com.matagaruda, +
  cell/garuda/siano/openclaw. ~95 risultano attivi a `launchctl list`.
- Brew services: ollama, postgresql@17, redis, syncthing.
- Repo Pro su `bcfa95dda chore(wr2): pipeline hardening` (#568).

### Mini (Mini-Pro2.local, 192.168.110.44 LAN, 100.93.236.6 Tailscale)
- Load idle. RAM 24 GB. Ollama installed, **0 modelli caricati ora**.
- 6 modelli pulled (28 GB su disco): qwen3:8b, qwen3.5:9b, qwen2.5vl:7b,
  qwen2.5:7b, bge-m3, nomic-embed-text. **Mancano** gemma4:26b (17 GB) e
  deepseek-r1:32b (19 GB) — non entrano comunque in 24 GB.
- Brew services: solo redis. Postgres NON attivo (brew formula non installata
  o mai started). Qdrant non installato.
- 14 LaunchAgent già caricati; alcuni rilevanti:
  - `com.matagaruda.kg-query-api` ATTIVO PID 1087
  - `com.nuzantara.fly-pg-tunnel` ATTIVO PID 1093
  - `com.nuzantara.git-pull-main.5min` cron 5 min (last pull 07:25 OK su
    `bcfa95dda`)
  - `com.balizero.indexing-sweep.daily` (presunta migrazione passata da Pro)
  - Vari matagaruda (intel-bridge, ner-worker, normalizer, sentinel)
  - `com.nuzantara.ollama-warm-pin` registrato MA `ollama ps` vuoto =
    warm-pin non sta caricando nulla
- Repo Mini su `main`, allineato `0/0` con `origin/main`.

### Sync Pro→Mini (verificati live)
| Daemon | Last run | Esito |
|---|---|---|
| memory-sync-bidirectional | 09:47:10 | 273 file = 273 file ✅ |
| claude-config-sync | 09:26:50 | paths_changed=0 ✅ |
| secrets-sync-mini | 04:30:03 | 5/5 file unchanged ✅ |
| nuzantara-drive-sync | sleep | "(never exited)" — normale, prossimo fire 18:00 |
| git-pull-main.5min (su Mini) | 07:25:58 | OK pulled to bcfa95dda ✅ |

### Gap noti su Mini
- **Claude OAuth Keychain**: già loggato (sto girando Claude su Mini ora).
- **Codex/Gemini/NLM auth**: Gemini ✅ (`google_accounts.json` presente), Codex ✅
  (`auth.json` presente). NLM da verificare (mai usato su Mini secondo memory).
- **Postgres + Qdrant**: assenti; non migriamo job che li richiedono.
- **TCC**: `claude` binary su Mini **NON** ha Full Disk Access per `~/Desktop`.
  Tutti gli script di automation devono stare in `~/scripts/` e chiamare i
  payload veri tramite bridge (pattern già usato da `mini-git-pull-bridge.sh`).
- **Mini SSH peer su Pro**: lo script legacy Pro→Mini SSH peer marcato come
  `UNREACHABLE` (Codex panel feedback). Da verificare: subnet split Pro 192.168.0.x
  / Mini 192.168.110.x → Tailscale 100.93.236.6 è l'unico vettore stabile, vedi
  memory `discovery_pro_mini_subnet_split_2026_05_06`.

## §3 — Tassonomia delle 127 automation Pro (5 cluster)

### Cluster A — CO-LOCATED CON STATO PRO (NON migrare, ~25 plist)
Long-running residents che parlano con `postgresql@17` + `redis` + organism cells
locali del Pro. Migrazione singola = rete spezzata.

WR2: `wr2.queue-server`, `wr2.supervisor`, `wr2.supervisor-watchdog`,
`wr2.pg-proxy`, `wr2.canva-renderer`, `wr2.canva-oauth-watchdog`,
`wr2.deploy-puller`, `wr2.plist-watchdog`, `wr2.measurer`, `wr2.sla-worker`,
`wr2.fact-extractor`, `wr2.fact-checker`, `wr2.image-generator`,
`wr2.draft-generator`, `wr2.trend-hunter`, `wr2.hardening`.

Cell/Organism: `cell.organism`, `cell-observatory`, `observatory-server`,
`observatory-export`, `observatory`, `nuzantara.organism.*`, `pg-organism-bridge`,
`cell-observatory-prune`, `cell-observatory-selfcheck`.

Bridges/dispatchers Pro-bound: `meta-dispatcher`, `intel-dedup-gateway`,
`nlm-bridge`, `claude-max-api`, `prime-tunnel`, `automap-server/telegram/watchdog`,
`heartbeat-bridge`, `federation-alert-dispatcher`, `nuzantara.sentinel-aggregate`,
`sentinel-meta-watchdog`, `launchagent-state-bridge`, `openclaw-children-watchdog`,
`supervisor-liveness-watchdog`, `zombie-hunter`, `cpu-monitor`, `disk-monitor`,
`login-healthcheck`, `fly-restart-loop-detector`, `launchd-env-loader`,
`openclaw.gateway`, `flowkit.gateway`, `post-publish-poller`,
`post-publish-webhook`, `cron-log-sentinel`, `research-sentinel`.

→ **Restano sul Pro.** Punto.

### Cluster B — SYNC PRO↔MINI (5, già live)
Già descritti §2. Mantengo, aggiungo solo health-check.

### Cluster C — CRON BATCH ZERO-DEPS-PRO (~50 candidati, target di questo spec)

Cron periodici che chiamano solo: `claude` CLI (OAuth Mini), API esterne
(Telegram, Brevo, Canva, web fetch), file system locale, Ollama (qwen3:8b,
qwen2.5vl:7b, bge-m3 — quelli già su Mini).

| Famiglia | Job | Schedule | RAM picco | Note |
|---|---|---|---|---|
| siano | osint.news.daily | 06:00 | 300 MB | scraper |
| siano | osint.backup.daily | 23:00 | 100 MB | rsync |
| garuda | consumer.daily | 06:00 | 200 MB | local file |
| garuda | gap-detector.twice-daily | 06:00+18:00 | 200 MB | local file |
| matagaruda | daily-briefing | 07:00 | 100 MB | claude+Telegram |
| matagaruda | kita-feed.daily | 05:00 | 200 MB | scraper |
| matagaruda | weekly-digest | weekly 08:00 | 100 MB | claude+email Brevo |
| matagaruda | invalidation-sweep | 04:00 | 50 MB | rm cache |
| matagaruda | watcher.daily | 06:00 | 200 MB | scraper |
| matagaruda | reg-alert.30min | every 30 min | 50 MB | curl+Telegram |
| matagaruda | nlm-expander.weekly | weekly 09:00 | 300 MB | nlm CLI |
| matagaruda | wr-topic | calendar | 100 MB | claude CLI |
| matagaruda | public-channel | calendar | 100 MB | API |
| matagaruda | wr2-bridge.hourly | 1 h | 100 MB | claude+Pro pg? **VERIFY** |
| matagaruda | nlm-feeder-stream.hourly | 1 h | 200 MB | nlm CLI |
| matagaruda | bridge.adaptive | 1 min | 30 MB | needs Pro org? **VERIFY** |
| matagaruda | gap.consumer | 10 min | 100 MB | claude+local |
| matagaruda | kg-linker | 1 h | 100 MB | local |
| balizero | regulatory-watcher.daily | 07:00 | 300 MB | claude+gemini+nlm+Telegram |
| balizero | competitor-monitor.monthly | 1° del mese | 7 GB | qwen2.5vl:7b ✅ Mini |
| balizero | competitor-signal-router.weekly | weekly 06:00 | 100 MB | claude |
| balizero | intel.nightly | 01:00 | 300 MB | scraper |
| balizero | intel-radar-daily-digest | 18:00 | 200 MB | claude |
| balizero | seo-cell.daily | 19:00 | 200 MB | curl+Lighthouse |
| balizero | seo-cell.28d-check | 29° del mese | 200 MB | curl+Lighthouse |
| balizero | setup-team.daily | 06:00 | 100 MB | claude |
| balizero | renewal-alerts | 08:00 | 100 MB | sqlite+Telegram |
| balizero | yield-optimizer.weekly | weekly 04:00 | 200 MB | qwen3:8b ✅ Mini |
| balizero | client-value-predictor | 09:00 | 300 MB | claude+sqlite |
| balizero | bz-daily-visual-pipeline | 05:00 | 500 MB | claude+canva |
| balizero | wr2.canva-gc.weekly | weekly 04:00 | 100 MB | curl Canva |
| balizero | wr2.daily-metrics | 06:00 | 200 MB | curl |
| balizero | wr2.ig-scraper.daily | 03:00 | 500 MB | playwright |
| balizero | wr2.reflexion.weekly | weekly 02:00 | 300 MB | claude |
| balizero | wr2.voyager.weekly | weekly 02:00 | 300 MB | claude |
| balizero | wr2.learner-nightly | 03:00 | 500 MB | claude |
| nuzantara | nb-intel-delta-watcher.hourly | 1 h | 200 MB | nlm CLI |
| nuzantara | nb-mitochondrial-monitor.daily | 02:00 | 200 MB | nlm CLI |
| nuzantara | claude-max-usage-watcher | 1 h | 30 MB | curl |
| nuzantara | cost-advisor-daily-cap | 08:00 | 50 MB | curl |
| nuzantara | cost-advisor-weekly | weekly 07:00 | 50 MB | curl |
| nuzantara | outbox-prune.daily | 03:00 | 50 MB | rm |
| nuzantara | automations-reference | 23:00 | 100 MB | doc gen |
| nuzantara | dlq-autopilot | 30 min | 100 MB | sqlite |

**Eccezioni dentro Cluster C** (richiedono refactor o restano sul Pro):
- `translate.hourly` (gemma4:26b 17 GB) → resta sul Pro o riscritto con qwen3.5:9b.
- `wr2.oracle/strategos/dossier-compiler/connector` → query Postgres@17 Pro,
  restano sul Pro.
- `vector-reindex-check` → curl Qdrant Pro, resta sul Pro.
- `indexing-sweep.daily` → KB local Pro, resta sul Pro.
- `sota.m13-*` → da grep, probabile dep Postgres Pro, da verificare.
- Famiglia `matagaruda` `wr2-bridge.hourly` e `bridge.adaptive` → marcati VERIFY
  in tabella, da grep prima del cluster.

### Cluster D — CODEX OVERNIGHT (~7 plist)
Tutti via `~/scripts/cron-runner.sh` → `codex exec --full-auto`.
- `codex-overnight-feeder` (21:00)
- `codex-overnight-runner` (22:00)
- `codex-research-actor` (06:00)
- `codex-coverage-improver` (03:00)
- `codex-autofix-ci` (calendar)
- `codex-openclaw-analysis` (07:00)
- `codex-spalla-calibrate` (06:00)

Migrabili dopo aver verificato Codex auth Mini. **Critico**: Codex modifica codice
nel repo → conflitto fatale con `git-pull-main.5min` se gira contemporaneamente.
Lock condiviso obbligatorio.

### Cluster E — WR2 microservices LIVE (NON migrare ora)
Vedi §1 non-goal. Richiederebbe Postgres+Qdrant su Mini. Fuori scope.

## §4 — Critiche del panel multi-LLM (integrate)

Brainstorming 2026-05-10 con Gemini 3.1 Pro + DeepSeek Reasoner + GPT-5.4 Codex.
Sintesi delle critiche convergenti che hanno modificato il design:

### 4.1 Race condition `git-pull-main` ↔ job in esecuzione (Gemini, Codex)
> "Se cron job parte nel millisecondo in cui git sta sovrascrivendo i `.py`,
> ottieni `ModuleNotFoundError` o sintassi corrotta."
>
> "Codex modifica codice + git-pull = split-brain repo."

**Fix**: lock condiviso `/tmp/repo-mutating.lock` su Mini. `git-pull-main.5min`
prende il lock prima del pull (10s timeout). Ogni script in Cluster C/D in
fase 1 di startup verifica il lock con `flock --timeout 30 /tmp/repo-mutating.lock`
e attende (max 30s) o esce. Codex prende lock per tutta la sua run.

### 4.2 Anti-duplicazione via `comm` è fragile (Gemini, DeepSeek, Codex)
> "`launchctl list` mostra solo job attivi, non disabilitati con file `.disabled`.
> Se Pro spento bruscamente, comm dà falsi negativi → email Brevo doppia ai clienti."

**Fix doppio**:
- (a) Inventario YAML centralizzato `~/Desktop/nuzantara/config/job-ownership.yaml`
  formato `<label>: { owner: pro|mini, side_effects: [brevo|telegram|social|none],
  idempotent: bool, last_migrated: ISO8601, git_sha: <hash> }`. Source-of-truth
  che ogni `launchctl bootstrap` consulta — rifiuta bootstrap se `owner` non
  matcha la macchina.
- (b) Lock distribuito Redis per job con `side_effects` non vuoti. Sia Pro che
  Mini montano redis; per cross-machine i job critici puntano a `Nuzantara.local:6379`
  (Pro redis bind-LAN). Job acquisisce `SET <label>:running 1 NX EX 7200` prima
  di partire — se SET fallisce, job esce silenzioso (qualcun altro l'ha già preso).
- (c) Daily health-check su Mini: `comm` Pro-vs-Mini launchctl list, alert
  Telegram se overlap.

### 4.3 RAM 24 GB stretta → semaforo concorrenza (Gemini, DeepSeek)
> "macOS riserva 4-6 GB. Modello 7B ~5-6 GB. 2 job Ollama paralleli = swap."
> "Se carichi tutti 6 modelli = ~17 GB. Resta ~7 GB per OS+Redis+50 job."

**Fix**:
- `OLLAMA_KEEP_ALIVE=0` env var globale Mini (modello unload dopo ogni inference).
- Semaforo file-based: `/tmp/ollama-slot-{1,2,3}.lock`. Job Ollama-bound prende
  uno slot via `flock`; se tutti occupati, attende (max 5 min) o esce.
- Smear orari: niente più 4 job alle 06:00. Distribuzione su 06:00/06:15/06:30/06:45.
- Codex single-thread (mai 2 codex paralleli).

### 4.4 PATH launchd non eredita .zshrc (Gemini)
**Fix**: ogni plist migrato deve avere `EnvironmentVariables.PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/sbin:/usr/sbin`. Verify post-bootstrap con
`launchctl print gui/$(id -u)/<label> | grep PATH`. Se manca → reject migrazione.

### 4.5 Log retention non migrata (Gemini)
**Fix**: nuovo plist `com.nuzantara.log-prune.daily.plist` su Mini, gira 03:00
WITA, esegue `find ~/logs/ ~/.cache/<*>/ -mtime +30 -delete` + `find /tmp/<job>-* -mtime +7 -delete`.

### 4.6 Path condivisi nascosti (DeepSeek, Codex)
> "Job Cluster C che legge da `../../data/` — se Mini scrive e Pro rilegge,
> quando Pro spento si rompe."
>
> "Pattern grep prima: `localhost|127\.0\.0\.1|/Users/nuzantara/agents|pg_|psql|qdrant|:5432|:6333|:11434|fly ssh|ssh pro|ssh air|/opt/homebrew|OLLAMA|psycopg|supabase|REDIS_URL|DATABASE_URL|QDRANT_URL`"

**Fix**: pre-flight obbligatorio per ogni job — script `~/scripts/mini-migration/preflight-job.sh <label>`
che esegue grep dentro lo script + ogni `.env` referenziato. Se trova match → reject migrazione,
job classificato dipendente Pro.

### 4.7 Secrets sync daily troppo lento (Codex)
> "Job migrato oggi può girare stanotte con env vecchia se token ruotato."

**Fix**: dopo ogni `launchctl bootstrap` su Mini, kickstart `secrets-sync-mini`
on-demand: `launchctl kickstart -k gui/$(id -u)/com.nuzantara.secrets-sync-mini`.

### 4.8 Telegram come unica verifica è debole (Codex)
> "Rate-limit, fallisce prima dell'alert."

**Fix**: ogni job Mini deve scrivere heartbeat file `~/heartbeat/<label>.ts`
(timestamp ISO8601 + exit code) al termine. Plist daily `com.nuzantara.heartbeat-watchdog.daily`
gira 09:00 WITA, alerta Telegram se job daily/weekly mancano l'heartbeat
nell'ultima finestra schedulata.

### 4.9 Idempotency key per side-effect esterni (Codex)
> "Brevo/social/Canva possono essere triggerati 2× durante transizione."

**Fix**: per i job in `job-ownership.yaml` con `side_effects ≠ none` e `idempotent: false`,
wrapper `~/scripts/mini-migration/idempotent-runner.sh <label>` che:
- genera idempotency key `${label}_${schedule_window}` (es. `weekly-digest_2026-W19`)
- consulta Redis `GET ${idempotency_key}` — se exists, exit 0 silenzioso
- altrimenti `SET ${idempotency_key} 1 EX 86400` poi exec script
- protegge da doppio-trigger durante migrazione.

### 4.10 Rollback policy granulare per schedule (DeepSeek)
> "2 fail consecutivi su weekly = buco di 2 settimane."

**Fix**: rollback automatico su 1 fail per weekly/monthly, 2 fail per daily/hourly.
Rollback = re-enable plist Pro (rinomina `.disabled` → `.plist`, bootstrap), disable
plist Mini, alert Telegram critico.

## §5 — Sequenza di migrazione (FUSA dai 3 panel)

Gemini propone "stateless API → file/Git → Ollama → Codex". DeepSeek propone
"canary 1×3 giorni → hourly → Ollama lightweight → daily+codex". Codex propone
"osservabilità → 5 canary uno per famiglia → batch reversibile → side-effect →
Ollama → Codex".

**Sequenza adottata** (sintesi):

### Fase 0 — Osservabilità + guardrail (settimana 1)
**Nessuna migrazione di job vera.** Solo infrastruttura di sicurezza.
1. Crea `config/job-ownership.yaml` (commit nel repo) con tutte le 127 label e
   classifica iniziale (`owner: pro` per tutte).
2. Implementa `scripts/mini-migration/preflight-job.sh` (grep dependencies).
3. Implementa `scripts/mini-migration/migrate-job.sh` (fa: preflight + lock check
   + secrets-sync kickstart + plist transfer + bootstrap + verify).
4. Implementa `scripts/mini-migration/rollback-job.sh`.
5. Implementa `scripts/mini-migration/overlap-detector.sh` (cron daily 09:00 su
   Mini, alert Telegram).
6. Implementa `idempotent-runner.sh` wrapper.
7. Implementa `heartbeat-watchdog.daily` plist.
8. Implementa `log-prune.daily` plist su Mini.
9. Patch `git-pull-main` per usare `flock /tmp/repo-mutating.lock`.
10. Verifica TCC: documenta che `claude`/`codex`/`ollama` su Mini hanno o no
    Full Disk Access. Bridge files in `~/scripts/` per ogni script in `~/Desktop/`.

### Fase 1 — Canary (settimana 2)
Migra **5 job uno per famiglia**, scelti secondo criteri:
- no Ollama
- no DB/Postgres/Qdrant (preflight pulito)
- side-effect reversibile o nullo (no Brevo, no social broadcast)
- output observable (log + Telegram di test)
- almeno 2 fire window in 3 giorni di osservazione

Candidati canary:
- `siano.osint.backup.daily` (rsync, side-effect: file su disco)
- `garuda.consumer.daily` (local file)
- `matagaruda.invalidation-sweep` (rm cache locale)
- `cost-advisor-daily-cap` (curl read-only)
- `claude-max-usage-watcher` (curl read-only)

**Gate Fase 1 → Fase 2**: 3 giorni con 0 errori sui 5 canary, heartbeat watchdog
verde, overlap-detector pulito.

### Fase 2 — Hourly + daily web/API senza side-effect critici (settimana 3)
Job che leggono web e producono log/digest, senza email Brevo o post social.
- `nb-intel-delta-watcher.hourly`
- `claude-max-usage-watcher.hourly`
- `wr2.daily-metrics`
- `siano.osint.news.daily`
- `garuda.gap-detector.twice-daily`
- `matagaruda.kg-linker` (1 h)
- `matagaruda.gap.consumer` (10 min)
- `intel.nightly`
- `intel-radar-daily-digest`
- `seo-cell.daily`
- `automations-reference.daily`
- `outbox-prune.daily`
- `dlq-autopilot.30min`
- `cost-advisor-weekly`
- `setup-team.daily`

**Gate Fase 2 → Fase 3**: 7 giorni con tasso errore ≤2%, overlap-detector pulito,
load Mini ≤6.

### Fase 3 — Side-effect esterni (settimana 4)
Job che mandano email/Telegram broadcast/Canva — richiedono `idempotent-runner`.
- `regulatory-watcher.daily` (Telegram broadcast)
- `matagaruda.daily-briefing` (Telegram)
- `matagaruda.kita-feed.daily` (Telegram)
- `matagaruda.weekly-digest` (Brevo email)
- `matagaruda.reg-alert.30min` (Telegram)
- `matagaruda.public-channel` (API push)
- `matagaruda.wr-topic` (claude+API)
- `matagaruda.nlm-feeder-stream.hourly` (nlm CLI)
- `nb-mitochondrial-monitor.daily` (nlm CLI)
- `bz-daily-visual-pipeline` (claude+canva)
- `wr2.canva-gc.weekly` (canva)
- `renewal-alerts` (Telegram per cliente — CRITICO idempotency)
- `seo-cell.28d-check`
- `siano.osint.backup.daily`

### Fase 4 — Ollama-bound con semaforo (settimana 5)
- `competitor-monitor.monthly` (qwen2.5vl:7b)
- `competitor-signal-router.weekly` (claude+local)
- `yield-optimizer.weekly` (qwen3:8b)
- `client-value-predictor` (claude+sqlite)
- `wr2.reflexion.weekly` (claude)
- `wr2.voyager.weekly` (claude)
- `wr2.learner-nightly` (claude)
- `wr2.ig-scraper.daily` (playwright + qwen2.5vl?)

### Fase 5 — Codex overnight (settimana 6)
Per ultimo: i 7 plist Codex. Verifica Codex auth Mini, lock condiviso obbligatorio,
zero parallelismo. Disabilita codex Pro contestualmente.

## §6 — Procedura `migrate-job.sh <label>` (deterministica)

```
1. preflight-job.sh <label> → exit 1 se grep dipendenze trova match
2. flock --timeout 60 /tmp/repo-mutating.lock → exit 1 se non lo prende
3. cat config/job-ownership.yaml → assert owner == "pro" → set owner = "mini"
4. ssh pro launchctl print gui/$UID/<label> → assert state == active
5. rsync pro:~/Library/LaunchAgents/<label>.plist mini:~/Library/LaunchAgents/<label>.plist
6. patch plist Mini: EnvironmentVariables.PATH = /opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
   patch ProgramArguments[2] (script path): if /Users/nuzantara/Desktop/nuzantara-deploy → /Users/nuzantara/Desktop/nuzantara
   patch StandardOutPath/StandardErrorPath: /Users/nuzantara/logs/<label>.log
   wrap script in idempotent-runner.sh se side_effects != none
7. ssh pro launchctl bootout gui/$UID/<label> → wait 30s
8. ssh pro mv ~/Library/LaunchAgents/<label>.plist ~/Library/LaunchAgents/<label>.plist.disabled-2026-05-10-migrated-to-mini
9. mini launchctl bootstrap gui/$UID/~/Library/LaunchAgents/<label>.plist
10. mini launchctl print gui/$UID/<label> → assert state == active, PATH OK, environment OK
11. mini launchctl kickstart -k gui/$UID/com.nuzantara.secrets-sync-mini → wait completion
12. mini launchctl kickstart -k gui/$UID/<label> → manual fire test
13. tail -f ~/logs/<label>.log per 60s → assert exit 0
14. heartbeat file ~/heartbeat/<label>.ts esiste e <60s old
15. update job-ownership.yaml + git commit + git push origin main
16. memo append project_mini_migration_2026_05_10.md
17. release flock
```

**Failure mode** in qualsiasi step: rollback automatico via `rollback-job.sh <label>`
+ alert Telegram critico + memo + flock release.

## §7 — Risk register (consolidato)

| Rischio | Likelihood | Impact | Mitigazione |
|---|---|---|---|
| Job dipendenza nascosta non vista preflight (es. modulo Python che apre psql) | medium | high | preflight grep AGGRESSIVO + dry-run + canary 3 giorni + rollback |
| OOM Mini con job Ollama paralleli | medium | high | OLLAMA_KEEP_ALIVE=0 + semaforo 3 slot + smear orari + max 1 codex |
| Race git-pull ↔ job esecuzione | high | medium | flock /tmp/repo-mutating.lock |
| Doppio-trigger non-idempotente (Brevo doppia email) | medium | critical | inventory YAML + Redis idempotency key + lock distribuito |
| TCC blocca claude su ~/Desktop Mini | high | medium | bridge files in ~/scripts/, no script diretto in ~/Desktop |
| OAuth Codex/Gemini/NLM Mini scade | medium | medium | watcher + rifresh interactive 1×/mese |
| Pro spento mentre job Mini fa query Pro pg/qdrant | low se preflight | high | preflight rejecta → mai migrato |
| Mini riavvio accidentale | low | high | Energy Saver Server H24 mode già attivo, KeepAlive=false sui cron |
| Plist patch fallisce e job parte con env Pro | low | high | step 10 verify post-bootstrap, rollback se mismatch |
| Secrets ruotati sul Pro non arrivano a Mini in tempo | medium | medium | kickstart secrets-sync post-bootstrap |
| Log saturano disco Mini | low | medium | log-prune.daily Mini |
| Telegram alert fallisce silenzio job morto | medium | medium | heartbeat-watchdog.daily |
| Rollback weekly job arriva 2 settimane dopo failure | medium | high | rollback su 1 fail per weekly/monthly |
| Inventory YAML out-of-sync col reale | medium | medium | overlap-detector.sh daily |
| Mini network down (subnet split) durante migrazione | low | high | Tailscale fallback già configurato (memory_sync_lan_tailscale_fallback) |

## §8 — Success criteria

Dopo Fase 5 completa (~6 settimane):
- Pro load avg ≤ 8 (da 14.93)
- Pro RAM unused ≥ 4 GB (da 462 MB)
- Zero overlap rilevato dall'overlap-detector negli ultimi 14 giorni
- ≥ 50 cron migrati a Mini, documentati in `project_mini_migration_2026_05_10.md`
- `job-ownership.yaml` 100% in sync con `launchctl list` su entrambe le macchine
- Antonello può `sudo shutdown -r now` su Pro alle 22:00 e tornare alle 08:00
  trovando: WR2 fermo (atteso, è Cluster A non migrato), tutti i digest notturni
  Telegram arrivati (Cluster C girato su Mini), zero errori critici
- Heartbeat-watchdog daily 09:00 verde da 7 giorni consecutivi

## §9 — Open questions per Antonello

1. Idempotency key Redis distribuito — vuoi che Mini punti a `Nuzantara.local:6379`
   (Pro redis LAN-exposed) per condividere lock con Pro durante la transizione?
   Trade-off: dipendenza network ma garantisce zero overlap. Alternativa:
   ogni macchina ha il suo redis locale isolato, accettiamo che durante la
   finestra di migrazione (15 min) un job potrebbe partire 2× e affidiamo
   l'idempotency al wrapper file-based.

2. `wr2.reflexion/voyager/learner` weekly e `wr2.ig-scraper.daily` — sono
   classificati Cluster C in §3 ma potrebbero scrivere in Postgres@17 Pro.
   Confermi che migrarli è ok dopo grep di verifica, o li tieni Cluster A?

3. Codex overnight Fase 5 — ChatGPT Plus usa 1 device slot per login Codex.
   Hai capacity per 2 slot (Pro + Mini) o devo loggare-out Pro prima di loggare
   Mini? In tal caso, durante Fase 5 i codex Pro restano spenti → conferma OK.

4. `translate.hourly` (gemma4:26b) — la riscrivo io con qwen3.5:9b o resta sul Pro
   come eccezione documentata?

5. Timing complessivo 6 settimane — ti va o vuoi accelerare/decelerare?
