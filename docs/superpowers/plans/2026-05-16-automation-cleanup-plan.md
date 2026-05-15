---
date: 2026-05-16
domain: automations / infra-hygiene
status: DRAFT pending 4-LLM review
parent_research: research/automations/2026-05-16-automation-system-map.md
machine_scope: Pro (nuzantara@Nuzantara) + Mini (nuzantara@mini-pro2)
estimated_duration: ~6h total wall (3h Pro + 1h Mini + 2h verification)
autonomous_ops_level: L2 (active since 2026-04-21)
rollback_strategy: per-intervention, see each section
---

# Automation cleanup plan — 2026-05-16

## Premessa

Snapshot 2026-05-16 ha mappato 280 automazioni distinte. 21 BROKEN su Pro, 2 P1 BROKEN su Mini, 1 SEC regression Mini, 1 SPOF EventBus→Organism, ridondanze cross-surface. Piano qui sotto risolve nell'ordine di rischio decrescente, con verifiche oggettive a ogni step.

**Principi di esecuzione**:
1. **Snapshot prima di toccare**: `tar` dei plist coinvolti in `~/.automation-cleanup-2026-05-16/backup/` prima di ogni modifica.
2. **Una modifica per commit**: NO mega-PR. Atomicità per facilità rollback.
3. **Verify-not-trust**: dopo ogni `launchctl bootout`/`bootstrap`, verificare `launchctl list | grep <label>` + `tail -50` del log nel minuto successivo.
4. **Telegram alert disabilitato durante cleanup**: setting `system_settings.alert_dispatcher_enabled='false'` per finestra cleanup, ri-enable a fine.
5. **Rollback inline**: ogni intervento documenta il comando di rollback.

**Pre-flight**:
```bash
# 0.1 Snapshot LaunchAgents Pro + Mini
mkdir -p ~/.automation-cleanup-2026-05-16/backup/{pro-launchagents,mini-launchagents}
cp ~/Library/LaunchAgents/com.{nuzantara,balizero,cell,matagaruda}.*.plist ~/.automation-cleanup-2026-05-16/backup/pro-launchagents/
ssh mini 'tar czf - ~/Library/LaunchAgents/com.*.plist' > ~/.automation-cleanup-2026-05-16/backup/mini-launchagents.tgz

# 0.2 Snapshot crontab Pro + Mini
crontab -l > ~/.automation-cleanup-2026-05-16/backup/crontab-pro.txt
ssh mini 'crontab -l' > ~/.automation-cleanup-2026-05-16/backup/crontab-mini.txt

# 0.3 Disable Telegram alert dispatcher (avoid alarm storm during cleanup)
psql "$DATABASE_URL" -c "UPDATE system_settings SET value='false' WHERE key='alert_dispatcher_enabled';"

# 0.4 Git baseline
cd ~/Desktop/nuzantara && git status --porcelain | head -20  # ensure clean
git log -1 --oneline  # baseline commit
```

---

## FASE 1 — P0 Sicurezza (15 min, REVERTIBILE)

### F1.1 — Mini `com.matagaruda.sentinel.daily.plist` secrets leak

**Trauma**: Mode 0644 con 3× `CLAUDE_CODE_OAUTH_TOKEN_*` + `TELEGRAM_BOT_TOKEN` in `EnvironmentVariables`. Regressione cicatrix 2026-04-29 P0-3.

**Azioni**:
```bash
# Step 1: chmod restrictive
ssh mini 'chmod 0400 ~/Library/LaunchAgents/com.matagaruda.sentinel.daily.plist'
ssh mini 'ls -la ~/Library/LaunchAgents/com.matagaruda.sentinel.daily.plist'  # verify -r--------

# Step 2: estrai i token attualmente esposti per rotazione
ssh mini 'plutil -extract EnvironmentVariables json -o - ~/Library/LaunchAgents/com.matagaruda.sentinel.daily.plist' \
  | jq 'to_entries | map(select(.key | test("(TOKEN|SECRET|KEY|PASSWORD)"))) | from_entries' \
  > ~/.automation-cleanup-2026-05-16/exposed-secrets-mini.json
chmod 0400 ~/.automation-cleanup-2026-05-16/exposed-secrets-mini.json
```

**Rotazione (manuale, NON autonomous-ops)**:
- `CLAUDE_CODE_OAUTH_TOKEN_*` (3 token): regenerate via `claude /login` slot 1+2 + agent-specific. Bisogna **Antonello-in-loop** perché OAuth browser flow.
- `TELEGRAM_BOT_TOKEN`: rotation via @BotFather `/revoke` + new token. Aggiornare poi tutti i plist che lo referenziano (grep mostrerà ~15 plist).

**Verifica**:
```bash
ssh mini 'ls -la ~/Library/LaunchAgents/com.matagaruda.sentinel.daily.plist'  # expect 0400
ssh mini 'launchctl print gui/501/com.matagaruda.sentinel.daily | head -30'  # service still loaded
ssh mini 'find ~/Library/LaunchAgents -name "com.matagaruda.*.plist" -perm +044 -ls'  # expect empty
```

**Rollback**: `ssh mini 'chmod 0644 ...'` (NON consigliato — cicatrix). Vero rollback: rotation **prima** di restore mode.

**Decision gate**: F1.2 procede SOLO se Antonello conferma di aver avviato la rotazione (anche se non completata) — chmod 0400 da solo è valore zero se token già leakati.

### F1.2 — Audit completo Mini per altri plist 0644+secrets

```bash
ssh mini 'for f in ~/Library/LaunchAgents/com.*.plist; do
  mode=$(stat -f "%Lp" "$f" 2>/dev/null)
  if [ "$mode" = "644" ] && grep -lE "TOKEN|SECRET|API_KEY|PASSWORD" "$f" > /dev/null 2>&1; then
    echo "EXPOSED: $f (mode $mode)"
  fi
done' | tee ~/.automation-cleanup-2026-05-16/mini-exposed-audit.txt
```

Per ogni risultato non-vuoto: `chmod 0400` + log in audit file.

---

## FASE 2 — P0 Disponibilità (30 min, REVERTIBILE)

### F2.1 — Unload `wr2.canva-renderer` (cicatrix stale)

**Trauma**: cicatrix 2026-05-13 dice "Production cron disabled 2026-05-13: kill switch + `launchctl bootout`". Plist `.disabled-2026-05-16-renderer-off` esiste su disco MA il plist attivo è ancora loaded con exit=1 `socket.gaierror`.

**Verifica stato attuale**:
```bash
launchctl list | grep wr2.canva-renderer  # se appare = ancora loaded
ls ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer*  # quanti file?
psql "$DATABASE_URL" -c "SELECT key,value FROM system_settings WHERE key='wr2_canva_renderer_enabled';"
# expect 'false' per cicatrix
```

**Azioni**:
```bash
# Step 1: kill switch (se non già false)
psql "$DATABASE_URL" -c "UPDATE system_settings SET value='false' WHERE key='wr2_canva_renderer_enabled';"

# Step 2: bootout
launchctl bootout gui/$(id -u)/com.balizero.wr2.canva-renderer

# Step 3: move plist a directory disabled (NON delete — preservare per orchestrator refactor)
mkdir -p ~/Library/LaunchAgents/.disabled-2026-05-16-cleanup/
mv ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist ~/Library/LaunchAgents/.disabled-2026-05-16-cleanup/

# Step 4: verifica
launchctl list | grep wr2.canva-renderer  # expect empty
tail -20 ~/Library/Logs/com.balizero.wr2.canva-renderer.log  # confirm no new entries
```

**Rollback**:
```bash
mv ~/Library/LaunchAgents/.disabled-2026-05-16-cleanup/com.balizero.wr2.canva-renderer.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.canva-renderer.plist
psql "$DATABASE_URL" -c "UPDATE system_settings SET value='true' WHERE key='wr2_canva_renderer_enabled';"
```

### F2.2 — Diagnosi `cell.organism` exit=1

**Trauma**: cicatrix family `Backend prod down 2026-04-29` (drive_poll_service AttributeError pattern: silent attribute-missing crash).

**Investigazione** (READ-ONLY, no modifiche):
```bash
# Step 1: log recente
tail -100 ~/Library/Logs/com.cell.organism.{out,err} 2>/dev/null

# Step 2: ultima exit history
launchctl print gui/$(id -u)/com.cell.organism | grep -E "last exit|state|spawn"

# Step 3: traceback se esiste
grep -A 30 "Traceback\|Exception\|Error:" ~/Library/Logs/com.cell.organism.err | tail -60

# Step 4: script entrypoint check
plutil -extract ProgramArguments json -o - ~/Library/LaunchAgents/com.cell.organism.plist
# e.g. /Users/nuzantara/.../organism/main.py — verifica syntax + import chain
cd ~/Desktop/nuzantara/apps/cell && python -c "from cell.organism import main; print('OK')" 2>&1
```

**Decision gate**: se traceback è una nota AttributeError/ImportError (cicatrix family) → fixa file + bump commit. Se è ImportError per package mancante → `pip install` nel venv giusto. Se è ECONNREFUSED Postgres → dipende da F3 (cluster pg-proxy).

**Rollback non applicabile**: investigation step, no modifiche.

### F2.3 — Watchdog per `pg-to-organism-bridge.py` (SPOF EventBus→Organism)

**Trauma**: unico ponte tra EventBus PG e Redis stream `organism:events`. Se muore, supervisor cieco.

**Azione**: creare LaunchAgent watchdog (segue pattern `~/scripts/openclaw-children-watchdog.sh` del cicatrix 2026-05-02).

```bash
cat > ~/scripts/pg-organism-bridge-watchdog.sh <<'EOF'
#!/bin/bash
set -euo pipefail
# Watchdog: if pg-organism-bridge silently dead OR no event in last 30 min when channels active → Telegram alert
LOG=~/logs/pg-organism-bridge-watchdog.log
STATE=~/.agent/decisions/state/pg_organism_bridge.state

PID=$(pgrep -f "pg-organism-bridge.py" | head -1)
if [ -z "$PID" ]; then
  echo "$(date) ALERT: pg-organism-bridge NOT RUNNING" >> "$LOG"
  curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
    -d "chat_id=$TELEGRAM_OWNER_CHAT_ID&text=⚠️ pg-organism-bridge DOWN — Symbiosis SPOF" || true
  exit 1
fi

# Lag check: Redis stream organism:events should have an entry in last 30 min if channels are firing
LAST_EVENT=$(redis-cli -h "${GARUDA_REDIS_HOST:-127.0.0.1}" XREVRANGE organism:events + - COUNT 1 2>/dev/null | head -1 || echo "")
echo "$(date) PID=$PID last=$LAST_EVENT" >> "$LOG"
EOF
chmod +x ~/scripts/pg-organism-bridge-watchdog.sh

cat > ~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.nuzantara.pg-organism-bridge-watchdog</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>/Users/nuzantara/scripts/pg-organism-bridge-watchdog.sh</string></array>
  <key>StartInterval</key><integer>300</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>/Users/nuzantara/logs/pg-organism-bridge-watchdog.out</string>
  <key>StandardErrorPath</key><string>/Users/nuzantara/logs/pg-organism-bridge-watchdog.err</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
EOF
chmod 0400 ~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist  # secrets via env, not in plist

# Token via shell env at load time
launchctl setenv TELEGRAM_BOT_TOKEN "$TELEGRAM_BOT_TOKEN"
launchctl setenv TELEGRAM_OWNER_CHAT_ID "1125336968"
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.pg-organism-bridge-watchdog.plist

# Enroll in organs_registry.yaml
# (manual edit of YAML — see F6.1)
```

**Verifica** (300s dopo):
```bash
tail -20 ~/logs/pg-organism-bridge-watchdog.log  # expect "PID=NNNNN last=..." entries every 5 min
```

**Rollback**: `launchctl bootout gui/$(id -u)/com.nuzantara.pg-organism-bridge-watchdog && rm <plist> <sh>`

---

## FASE 3 — P1 Cluster pg-proxy + Mini (45 min)

### F3.1 — Verifica cluster `15432` self-heal

**Trauma**: 12 organi BROKEN cluster `15432` (wr2 supervisor + watchdog + daily-metrics + topic-selector + connector + dossier-compiler + learner-nightly + fact-extractor + sota.m13-checkpoint + federation-alert-dispatcher + cell-observatory + pg-organism-bridge). pg-proxy ora verde — errori transienti.

**Azione**: NESSUNA modifica. Solo monitoraggio 24h.

```bash
# Snapshot exit codes adesso
for label in wr2.supervisor wr2.supervisor-watchdog wr2.daily-metrics wr2.topic-selector wr2.connector wr2.dossier-compiler wr2.learner-nightly wr2.fact-extractor sota.m13-checkpoint federation-alert-dispatcher cell-observatory pg-organism-bridge; do
  exit_code=$(launchctl print gui/$(id -u)/com.{nuzantara,balizero,cell}.$label 2>/dev/null | grep -E "^\s+last exit" | head -1)
  echo "$label: $exit_code"
done | tee ~/.automation-cleanup-2026-05-16/pg-proxy-cluster-baseline.txt

# Schedule re-check 24h
echo "0 13 17 5 * tail -20 ~/Library/Logs/com.{nuzantara,balizero,cell}.{wr2.supervisor,wr2.daily-metrics,pg-organism-bridge}.err | tee -a ~/.automation-cleanup-2026-05-16/pg-proxy-cluster-24h.txt" | crontab -
```

**Decision gate 24h dopo**: se exit=0 su prossimo run di ciascuno → cluster self-healed, no action. Se exit ≠ 0 ancora → triage individuale (probabile bug specifico per organ).

### F3.2 — Mini `kg-query-api` crash loop fix

**Trauma**: `OSError: [Errno 49] Can't assign requested address` binding Tailscale IP `100.93.236.6:8990`. KeepAlive=true + ThrottleInterval=15s = silent restart loop dal 2026-05-13.

**Root cause hypothesis**: launchd starta servizio prima che tailscaled abbia bind l'IP `100.93.236.6` (race condition boot-time).

**Fix proposto**: bind `0.0.0.0:8990` invece di specifico Tailscale IP, oppure aggiungere sleep-guard.

**Azioni** (richiede SSH Mini):
```bash
ssh mini 'cat ~/Library/LaunchAgents/com.matagaruda.kg-query-api.plist' > /tmp/kg-query-api.plist

# Opzione A (preferita): bind wildcard
# Identifica file Python che bind, e.g. apps/mata-garuda/.../kg_query_api.py
ssh mini 'grep -r "100.93.236.6" ~/Desktop/nuzantara/apps/mata-garuda/ --include="*.py" -l'

# Edit: cambia "100.93.236.6" → "0.0.0.0" nel file Python
# Commit, push, ssh mini git pull
```

**Opzione B (fallback)**: launchd wrapper con sleep-guard:
```bash
#!/bin/bash
# wait for tailscaled ready
until ifconfig | grep -q "100.93.236.6"; do sleep 2; done
exec python3 -m mata_garuda.kg_query_api
```

**Verifica**:
```bash
ssh mini 'launchctl print gui/501/com.matagaruda.kg-query-api | grep "last exit code"'
ssh mini 'tail -30 ~/Library/Logs/com.matagaruda.kg-query-api.err'
# expect: nessun OSError [Errno 49] in last 5 min
```

**Rollback**: revert commit + ssh mini git pull.

### F3.3 — Mini `fly-pg-tunnel` DNS fail

**Trauma**: `api.fly.io: no such host` errors. Pattern lessons `fly CLI token regression cascade 2026-05-14`.

**Fix**: wrapper Mini necessita patch `-t $FLY_API_TOKEN` esplicito (stesso pattern di `~/scripts/fly-pg-proxy-wrapper.sh` su Pro).

```bash
ssh mini 'cat ~/scripts/fly-pg-tunnel-wrapper.sh' > /tmp/fly-pg-tunnel-mini.sh
# Cerca riga `fly proxy` senza `-t` → aggiungi `-t "$FLY_API_TOKEN"` esplicito
# Se token non in env: leggi da ~/.fly/config.yml o da secrets
```

**Verifica**:
```bash
ssh mini 'tail -30 ~/Library/Logs/com.nuzantara.fly-pg-tunnel.err | grep "no such host" | wc -l'
# expect 0 in last 5 min after fix
```

---

## FASE 4 — P1 Script mancanti + GH workflows (30 min)

### F4.1 — `scripts/legal_radar.py` missing

```bash
# Verifica git history
cd ~/Desktop/nuzantara && git log --all --diff-filter=D -- scripts/legal_radar.py | head -10

# Se trovato: ripristina dal commit dove esisteva
# Se mai esistito: commenta crontab entry
```

**Decision gate**: dipende da git history. Antonello-in-loop se git mostra file deleted intenzionalmente vs orphan reference.

### F4.2 — `bali-zero-akta/scripts/run_overnight.sh` missing

Idem F4.1.

### F4.3 — 4 GH workflow failing

```bash
gh run list --workflow=docs-guardian.yml --limit=3 --json status,conclusion,databaseId,displayTitle
gh run list --workflow=docs-sync.yml --limit=3 --json status,conclusion,databaseId
gh run list --workflow=restore-drill.yml --limit=3
gh run list --workflow=wr2-master-template-guard.yml --limit=3

# Per ciascuno, leggi log dell'ultimo failed run
gh run view <run_id> --log-failed | head -100
```

**Triage per workflow**:
- `docs-guardian`: probabile docsync drift (scripts/docs_sync.py disallinea regen)
- `docs-sync`: stesso albero
- `restore-drill`: backup Tigris test — verifica `FLY_API_TOKEN` (cicatrix 2026-05-14)
- `wr2-master-template-guard`: cicatrix WR2 master template — `DAHJLYRn_3E` failed example design

Per ognuno: capire causa, fix mirato, riavviare workflow. Ogni fix in commit separato.

---

## FASE 5 — P1 Triple-collision crontab (10 min)

### F5.1 — Spread `30 20 * * *` UTC quad-collision

**Trauma**: 4 job stessa ora (nlm-nb1-refresh, garuda-indexer, db-nlm-sync, curiosity_loop) → spike I/O contemporaneo, contention OAuth quota, log entanglement.

**Fix**:
```
# Prima
30 20 * * * /path/to/nlm-nb1-refresh.sh
30 20 * * * /path/to/garuda-indexer.sh
30 20 * * * /path/to/db-nlm-sync.sh
30 20 * * * /path/to/curiosity_loop.sh

# Dopo (spread 3 min each)
30 20 * * * /path/to/nlm-nb1-refresh.sh
33 20 * * * /path/to/garuda-indexer.sh
36 20 * * * /path/to/db-nlm-sync.sh
39 20 * * * /path/to/curiosity_loop.sh
```

**Atto**:
```bash
crontab -l > /tmp/crontab-pre-spread.txt
# Edit manuale: sed -i sostituzioni
crontab /tmp/crontab-after-spread.txt
crontab -l | grep -E "(nlm-nb1-refresh|garuda-indexer|db-nlm-sync|curiosity_loop)"
```

**Verifica**: 24h dopo, log files dei 4 mostrano start time differenziati.

**Rollback**: `crontab /tmp/crontab-pre-spread.txt`.

---

## FASE 6 — P2 Genoma + Symbiosis hardening (90 min)

### F6.1 — Enroll 15 organi Pro orphan in `organs_registry.yaml`

**Lista** (da `/tmp/automation-map-pro-launchagents.md` + `/tmp/automation-map-cron-actions.md` cross-ref):

1. `com.nuzantara.pg-organism-bridge-watchdog` (creato F2.3)
2-5. 4 agenti orphan (`client-case-quote-generator`, `email-template-builder`, `wr2-external-bench`, `wr2-image-prompt-author`) — se mantenuti, enroll. Se retired, F8.
6-11. 6 watchdog/*observatory* non enrolled (lista da Pro launchd report `## Duplicates suspected`)
12-16. 5 cron-agent-python (compliance-ops, oss-monitor, intel-radar-daily-digest + 2 altri)

**Atto**: edit YAML, una sezione per organ:
```yaml
- id: <component>.<subcomponent>
  description: <one-liner>
  runtime: pro_launchd  # or mini_launchd | fly_machine
  schedule: <cron or interval>
  severity_on_silence: warn  # or critical | none
  emit_channels: []  # PG channels this organ publishes to (empty if leaf consumer)
  consume_channels: []
  owner: zero
  test: <test path or "manual">
```

**Verifica**: `python apps/organism/organism/scripts/validate_registry.py` (se esiste) o grep `^- id:` count → 118 + 15 = 133.

### F6.2 — Symbiosis L3 hardening

**6 producers Redis pub/sub non-compliant**:
- kg_cache invalidation
- ConfirmationService
- WebSocket fan-out

**Decision tree**:
- Se downstream consumer accetta perdita eventi (es. UI cache invalidation è OK riloadare manualmente): documentare eccezione in `SYMBIOSIS.md` come "grandfathered, no durability needed: cache-only" + commento inline.
- Se downstream consumer NON tollera perdita: migrazione a `events_outbox` + `pg_notify` con replay. Lavoro più sostanziale (~2h).

**Atto fase iniziale**: solo documentazione eccezioni. Migrazione vera è fase successiva, separato.

### F6.3 — `partner_commission_changed` orphan channel

**Trauma**: producer attivo (mig 146), 0 consumers cablati. Eventi accumulano in `events_outbox` senza ack.

**Decisione richiesta** (Antonello):
- Opzione A: cablare consumer in `apps/backend-rag/backend/services/events/handlers/_core.py` (registra handler)
- Opzione B: ritirare producer (drop trigger mig 146 con nuova migration)

**Fino a decisione**: lo lasciamo orphan ma aggiungiamo prune cron settimanale per evitare growth unbounded (`prune_consumed(older_than_days=7, channel='partner_commission_changed')`).

---

## FASE 7 — P2 Cross-surface duplicati Pro vs CI (20 min)

**Decisione canonica per ciascuno**:

| Job | Pro crontab | GH Actions | Decision raccomandata |
|---|---|---|---|
| `fly-watcher` | active | active | **GH Actions canonico** (CI/HA, no host dipendenza) → spegnere crontab Pro |
| `fly-cost-alert` | active | active | idem |
| `sentry-quota` | active | active | idem |
| `fly-restart-detector` | active | active | **Pro crontab canonico** (cicatrix 2026-04-29 dice deve girare su host con accesso fly logs, GH Actions può perdere context) → spegnere GH workflow |

**Atto**:
```bash
# 3 disable Pro crontab:
crontab -l | sed '/fly-watcher\|fly-cost-alert\|sentry-quota/s/^/# DISABLED 2026-05-16 (GH canonical) /' | crontab -

# 1 disable GH workflow:
gh workflow disable fly-restart-detector.yml
```

**Verifica**: 24h dopo, ciascuno job ha esattamente 1 invocazione per tick (non 2).

---

## FASE 8 — P2 Active-active residuo + observatory parallel impls + agenti orphan (30 min)

### F8.1 — Decisione `matagaruda.sentinel` Pro hourly vs Mini daily

**Opzioni**:
- A. **Pro-only hourly**: copre già daily (24× il volume). Spegni Mini daily.
- B. **Split scope**: Mini=digest giornaliero (aggregato), Pro=alert orario (real-time).

**Raccomandazione**: Opzione B se i due brain hanno output distinti (verificare con `diff <(pro_output) <(mini_output)`). Altrimenti A.

### F8.2 — Observatory parallel impls

**`com.balizero.observatory*`** vs **`com.nuzantara.cell-observatory*`** — leggere README di entrambi, decidere canonica.

**Hint**: cicatrix `Consiglio v1 quarantined 2026-05-06` ha pattern simile (mata-garuda prototype + backend-rag live impl). Probabile: `nuzantara.cell-observatory` è canonica (LIVE, enrolled), `balizero.observatory` è legacy quarantine.

**Atto**: `launchctl bootout` + move plist legacy a `.disabled-2026-05-16/`.

### F8.3 — 4 agenti orphan

| Agent | Decisione raccomandata |
|---|---|
| `client-case-quote-generator` | Wire-in: ha use case ("quote case for [client]") chiaro — propose to Antonello |
| `email-template-builder` | Wire-in: utile per Brevo template generation |
| `wr2-external-bench` | Wire-in cron mensile (1st Monday) — già spec'd nel system prompt agent |
| `wr2-image-prompt-author` | Wire-in pipeline WR2 Step 4.5 (tra storyboarder e layout-composer) — spec dice "Used by wr2-design-architect" ma non chiamato |

Per ciascuno: invocazione test, verificare output, decidere keep+enroll vs retire.

---

## FASE 9 — Post-cleanup verification (1h)

```bash
# 9.1 Re-run mapping
# (lanciare di nuovo i 5 sub-agent paralleli, confrontare con baseline 2026-05-16)

# 9.2 Compliance metrics
psql "$DATABASE_URL" -c "
  SELECT channel, count(*) as unconsumed
  FROM events_outbox WHERE consumed_at IS NULL
  GROUP BY channel ORDER BY unconsumed DESC;
"  # expect: minor accumulation, no channel >1k

# 9.3 Health snapshot
for f in /tmp/automation-map-*.md; do
  echo "=== $f ==="
  grep -E "BROKEN|STALE" "$f" | wc -l
done

# 9.4 Re-enable Telegram alert
psql "$DATABASE_URL" -c "UPDATE system_settings SET value='true' WHERE key='alert_dispatcher_enabled';"

# 9.5 Smoke test: trigger one WR2 carousel run end-to-end
# (skill /wr2 design carousel for [test topic])

# 9.6 Commit summary
cd ~/Desktop/nuzantara
git add -A docs/ apps/organism/organism/organs_registry.yaml
git commit -m "$(cat <<EOF
chore(automations): cleanup snapshot 2026-05-16

- F1: chmod 0400 Mini sentinel + audit (P0 SEC cicatrix 2026-04-29)
- F2: unload wr2.canva-renderer + diagnose cell.organism + watchdog pg-organism-bridge
- F3: monitor pg-proxy cluster + fix Mini kg-query-api + fly-pg-tunnel
- F4: script mancanti + 4 GH workflow failing
- F5: spread 20:30 quad-collision
- F6: enroll 15 organi orphan + L3 hardening doc
- F7: decision cross-surface duplicati
- F8: observatory canonica + agenti orphan

Refs: research/automations/2026-05-16-automation-system-map.md
EOF
)"
```

---

## Dipendenze tra fasi

```
F1 (SEC) ─┬─→ F2 (DISP) ──→ F3 (cluster monitor + Mini fix)
          │
          └─→ F6 (Genoma) ←── F2.3 (watchdog enroll)

F4 (script + GH) ── indipendente
F5 (quad-collision) ── indipendente
F7 (cross-surface) ── indipendente
F8 (orphans) ─── depende su F1 (security) prima

F9 (verify) ── tutto, dopo
```

**Parallelizzabile**: F4, F5, F7 possono girare in parallelo a F2-F3.

## Rischi e mitigation

| Rischio | Probabilità | Impatto | Mitigation |
|---|---|---|---|
| Telegram alarm storm durante cleanup | Media | Basso | F0.3 disable dispatcher, F9.4 re-enable |
| Rotazione token rompe altri servizi | Media | Alto | F1 ordina rotation prima di chmod, Antonello-in-loop |
| `cell.organism` fix richiede deploy Fly | Media | Medio | F2.2 investigation-only, no deploy in questa wave |
| `kg-query-api` bind 0.0.0.0 espone porta | Bassa | Medio | Verifica firewall Mini, IP locked to Tailscale subnet |
| pg-proxy cluster NON self-heals dopo 24h | Bassa | Medio | F3.1 decision gate, triage individuale se needed |
| Spread crontab rompe upstream timing dependency | Bassa | Basso | F5 mantiene tutti a 20:30-20:39 UTC window |
| Workflow GH re-fail dopo fix | Media | Basso | F4.3 triage individuale, ogni fix in PR separata |

## Out of scope (esplicito)

- **Migrazione Redis pub/sub → events_outbox** dei 6 channel non-compliant: troppo lavoro per questa wave, fase successiva
- **Refactor `pg-to-organism-bridge` per HA pair**: il watchdog F2.3 è mitigation sufficiente per ora
- **Rotation manuale OAuth Claude Code**: richiede browser flow, Antonello-task
- **Audit secrets Pro plist 0644** (non-Mini): già verificato 2026-04-29, no regression
- **Rinominare `partner.commission_changed` → `partner_commission_changed`** per fix EventBus emit_pg validation: separate PR

## Approvazione

Questo piano **richiede approval Antonello** prima esecuzione (autonomous-ops L2 non copre rotation token o modifiche estese organs_registry).

Prossimo step: **review 4-LLM panel** (Gemini + Codex + DeepSeek + NotebookLM NB-1) per:
1. Killer flaw detection
2. Ordine fasi (potrebbe esserci dipendenza che ho mancato)
3. Verifica che cicatrix-scars siano correttamente referenziati
4. Risk register completeness
