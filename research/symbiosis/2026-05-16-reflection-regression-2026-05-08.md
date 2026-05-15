---
date: 2026-05-16
domain: symbiosis
client_case: Pilastro 1 Riflessione — regressione silente lhkpn_harvester dal 2026-05-08
sources: 11
status: draft
parent_doc: research/symbiosis/2026-05-16-lifecycle-state-snapshot.md (Pilastro 1 gap D)
severity: P1 (Pilastro 1 dichiarato live, in pratica −85% throughput, no alert)
root_cause_layers: 3 (cascading)
---

# Reflection regression 2026-05-08 — root cause + fix proposal

## TL;DR

Pilastro 1 Riflessione "live" in SYMBIOSIS.md ma `lhkpn_harvester` ha smesso di riflettere il **2026-05-08 12:33** (oggi è 8 giorni di silenzio). Causa: **3 problemi cascading**, due architettonici e uno operativo, nessuno con alert.

1. **Envelope schema drift** (architectural): il gap-detector OSINT-Nexus emette gap con `gap_type='missing_relation'` / `'missing_attribute'` / `'stale_attribute'` (flat envelope), ma il dispatcher `gap_consumer.py` si aspetta `gap_type='gap.missing_nip'` etc. (prefisso `gap.` + tassonomia diversa). Tutti i nuovi gap vanno in `gap_legacy.py` → "Legacy gap drained: no canonical mapping" → ACK skip → **2137 warning silenziosi** in `~/logs/matagaruda-gap-consumer-err.log`.
2. **Docker Desktop spento** (operational): dal 2026-05-10 18:00 il container `osint-neo4j` (porta 17687) è giù → `garuda-gap-detector.sh` exit 4 "FATAL: Neo4j unreachable" → stream `nexus:gaps` fermo (ultimo entry 2026-05-12 18:00).
3. **Missing Telegram alert** (governance): né `garuda-gap-detector.sh` né `gap_consumer.py` emettono alert su exit !=0 o WARNING flood. Pilastro 1 collapse invisibile.

**Effetto combinato**: gap-detector morto + dispatcher disallineato + no alert = Pilastro 1 "live but degraded" −85% throughput documentato in `2026-05-16-lifecycle-state-snapshot.md`.

## Empirical timeline (verificato live)

### Reflection cadence per agent

| Agent | reflection < 2026-05-08 | reflection ≥ 2026-05-08 | last reflection |
|---|---:|---:|---|
| `lhkpn_harvester` | 94 | **6** (ultima il 12:33 dell'8 mag) | **2026-05-08 12:33:13** |
| `Regulation Watcher` | 19 | 7 | 2026-05-14 23:55:08 (live) |

(Source: `apps/mata-garuda/data/knowledge.db` `knowledge` table `type='reflection'`)

### Gap-detector run history

`~/logs/garuda-gap-detector.log` `grep "==="` mostra:

- 2026-04-26 → 2026-05-05: 20 run consecutivi OK
- **2026-05-06 07:00**: prima FATAL Neo4j (intermittente)
- 2026-05-06 18:00 → 2026-05-10 18:00: alternati OK / FATAL
- **2026-05-10 18:00**: ultimo run senza FATAL successivo
- **2026-05-11 07:00 onwards**: tutti FATAL (Neo4j unreachable o Redis unreachable)

### nexus:gaps stream state

`redis-cli XINFO GROUPS nexus:gaps`:
- Consumer group `gap-consumer`: pending=91, last-delivered-id=`1778580005447-0`, **entries-read=4059, lag=0**
- Last entry timestamp: `1778580005447-0` → 2026-05-12 18:00:05 (ms unix epoch)

Stream contenuto totale 4059 entries, breakdown gap_type:
- `missing_relation`: 1759
- `missing_attribute`: 1415
- `stale_attribute`: 885

**Zero entries con i gap_type attesi dal dispatcher** (`gap.missing_nip`, `gap.missing_lhkpn`, `gap.missing_angkatan`, `gap.stale_official`, `gap.orphan_org`, `gap.missing_office`, `gap.kanim_struktur`, `gap.missing_procurement`).

### Logs evidence

`~/logs/matagaruda-gap-consumer-err.log` campione:
```
2026-05-12 18:14:34,861 WARNING mata_garuda.workers.gap_legacy:
  Legacy gap drained: msg_id=1778580005400-0 gap_type='' attribute=None
  entity='Tuan Sing Holdings Limited' — no canonical mapping
```

Count totale `Unknown gap type` o `Legacy gap drained`: **2137** warnings.

## Layer-by-layer root cause

### Layer 1 — Architectural: envelope schema drift OSINT-Nexus vs mata-garuda

Il gap-detector vive in `~/Desktop/OSINT-Nexus/bridge/gap_detector.py` (OSINT repo separato), il dispatcher in `~/Desktop/nuzantara/apps/mata-garuda/mata_garuda/workers/gap_consumer.py`. I due repo sono evoluti separatamente.

**Dispatcher `GAP_DISPATCH` table** (`gap_consumer.py:51-60`):

```python
GAP_DISPATCH: dict[str, Optional[str]] = {
    "gap.missing_nip":          "lhkpn_harvester",
    "gap.missing_lhkpn":        "lhkpn_harvester",
    "gap.missing_angkatan":     "lhkpn_harvester",
    "gap.stale_official":       "regulation_watcher",
    "gap.orphan_org":           "regulation_watcher",
    "gap.missing_office":       "regulation_watcher",
    "gap.kanim_struktur":       "regulation_watcher",
    "gap.missing_procurement":  None,
}
```

**Stream payload reale (XREVRANGE)**:
```
gap_type → "missing_relation"     (1759 entries)
gap_type → "missing_attribute"    (1415 entries)
gap_type → "stale_attribute"      (885 entries)
```

Quando gap_consumer chiama `gap_type not in GAP_DISPATCH` → `WARNING Unknown gap type ... ACKing to skip`. In più `gap_legacy.py` cattura quelli con `gap_type=''` (stringa vuota) come "Legacy gap drained — no canonical mapping".

Quando è successo il drift: tra 2026-05-07 e 2026-05-08 (ultima reflection lhkpn è 2026-05-08 12:33). Probabile refactor unilaterale in OSINT-Nexus che ha cambiato la tassonomia gap_type. Da verificare con `git log` in `~/Desktop/OSINT-Nexus`.

### Layer 2 — Operational: Docker Desktop spento

`docker info` → `ERROR: Cannot connect to the Docker daemon` (Docker Desktop NOT running).
`pgrep -f "Docker Desktop"` → nessun risultato.
`docker-compose.yml` in OSINT-Nexus definisce container `osint-neo4j` con `restart: unless-stopped` MA Docker host è giù.

**Conseguenza**: `garuda-gap-detector.sh:23` esegue:
```bash
if ! /usr/bin/nc -z localhost 17687 2>/dev/null; then
    echo "[gap-detector] FATAL: Neo4j unreachable on port 17687" >> "$LOG"
    exit 4
fi
```
→ exit 4 ogni 12h dal 2026-05-11.

### Layer 3 — Governance: no alert su Pilastro 1 collapse

Nessun Telegram notifier:
- `garuda-gap-detector.sh` exit 4 non triggera nulla (launchd `StandardErrorPath` solo file)
- `gap_consumer.py` 2137 "Legacy gap drained" warning solo a log, no aggregato
- `lhkpn_harvester` reflection drop 94→6 non monitorato da niente

SYMBIOSIS.md Pilastro 7 "Misura" ha IA + FE + TTR + densità ontologica, ma **niente metrica per reflection rate per agent**. Pilastro 1 si è degradato sotto i radar.

## Why Regulation Watcher è ancora live

`Regulation Watcher` riflette 1×/day costantemente. Verifico: `reflection_Regulation Watcher` è invocato da una cron diversa (`com.matagaruda.reg-alert.30min` o weekly digest) che NON dipende da `nexus:gaps`. Il dispatcher gap → regulation_watcher è teorico nel codice ma il reflection cycle live di Regulation Watcher viene da una pipeline parallela (regulatory-watcher daemon). Quindi un solo path di reflection sopravvive — il path gap-driven è morto.

## Fix proposal (3 layer, ordine di esecuzione)

### Fix 1 (CHEAP, 5min) — Avviare Docker Desktop + verifica Neo4j

```bash
open -a "Docker Desktop"
sleep 30
docker ps | grep osint-neo4j   # expect running OR
cd ~/Desktop/OSINT-Nexus && docker compose up -d neo4j
sleep 10
nc -z localhost 17687 && echo "Neo4j OK"
```

Triggera prossimo gap-detector run alle 07:00/18:00 WITA next.

**Effetto**: stream `nexus:gaps` riprende ad accumulare. Ma NON risolve il dispatch mismatch — i nuovi gap continueranno a essere "Legacy gap drained".

### Fix 2 (MEDIUM, 1-2h) — Riallineare envelope OSINT-Nexus → mata-garuda

Due scelte mutuamente esclusive (decisione Antonello):

**Opzione A (preferibile)**: aggiungere alias mapping in `gap_consumer.py:GAP_DISPATCH` per i tipi che effettivamente arrivano:
```python
GAP_DISPATCH: dict[str, Optional[str]] = {
    # New OSINT-Nexus taxonomy (post-2026-05-08)
    "missing_attribute":   "lhkpn_harvester",  # nip/lhkpn/angkatan all subsumed
    "missing_relation":    "regulation_watcher",
    "stale_attribute":     "regulation_watcher",
    # Legacy compat (pre-2026-05-08)
    "gap.missing_nip":          "lhkpn_harvester",
    "gap.missing_lhkpn":        "lhkpn_harvester",
    # ... (resto del dict come è)
}
```
Pro: 1 file edit, backward compat, nessun touch OSINT-Nexus.
Con: lhkpn_harvester deve gestire un `attribute` field per discriminare nip vs lhkpn vs angkatan internamente (probabilmente già lo fa via `_gap_type` injection).

**Opzione B**: refactor OSINT-Nexus `gap_detector.py` per emettere gap_type con prefisso `gap.` e tassonomia originale. Più invasivo, tocca repo separato non-Bali-Zero.

Raccomando A.

### Fix 3 (CHEAP, 30min) — Alert su Pilastro 1 degradation

Aggiungere a `~/scripts/garuda-gap-detector.sh` post-exit-trap:
```bash
EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    "$HOME/.claude/scripts/hotfix-notify.sh" \
        "🚨 gap-detector FATAL (exit=$EXIT_CODE) — Pilastro 1 down" 2>/dev/null || true
fi
exit $EXIT_CODE
```

E un cron giornaliero che conta reflection per agent ultime 24h, alert se `< 50% della baseline 7d`:

```bash
# new ~/scripts/matagaruda-reflection-health-check.sh (daily 09:00 WITA)
DB="$HOME/Desktop/nuzantara/apps/mata-garuda/data/knowledge.db"
BASELINE=$(sqlite3 "$DB" "SELECT COUNT(*) FROM knowledge WHERE type='reflection' AND created_at > datetime('now','-7 days')")
TODAY=$(sqlite3 "$DB" "SELECT COUNT(*) FROM knowledge WHERE type='reflection' AND created_at > datetime('now','-24 hours')")
EXPECTED=$((BASELINE / 7))
if [ "$TODAY" -lt $((EXPECTED / 2)) ]; then
    "$HOME/.claude/scripts/hotfix-notify.sh" \
        "📉 Reflection rate $TODAY/24h vs baseline $EXPECTED/day — Pilastro 1 degrading"
fi
```

## Refusals enforced by Autonomous Ops L2

- **NO autonomous restart Docker Desktop** — `open -a` non distruttivo ma è azione operatore-side e potrebbe far partire workflow non desiderati (Subhi container, ecc.). Antonello deve approvare timing.
- **NO autonomous fix opzione A senza brainstorm 4-LLM** (CLAUDE.md feedback 2026-05-13 review spec rule). Layer 2 fix è cambiamento di schema dispatch, non trivial.
- **NO edit `~/scripts/garuda-gap-detector.sh`** senza approval — è script operator-side fuori repo (stesso pattern Tier A doc-only 2026-05-12).
- **NO touch OSINT-Nexus repo** — repo separato, fuori scope Nuzantara.

## Sources

1. `apps/mata-garuda/data/knowledge.db` table `knowledge` (live query reflection by date+agent)
2. `apps/mata-garuda/mata_garuda/workers/gap_consumer.py:51-60` `GAP_DISPATCH` dict
3. `apps/mata-garuda/mata_garuda/workers/gap_consumer.py:114-126` unknown gap handling
4. `apps/mata-garuda/mata_garuda/workers/gap_legacy.py` legacy drain logger
5. `redis-cli XINFO GROUPS nexus:gaps` + `XRANGE` (live state 2026-05-16)
6. `~/scripts/garuda-gap-detector.sh:23` Neo4j precheck logic
7. `~/Library/LaunchAgents/com.garuda.gap-detector.twice-daily.plist` schedule 07:00+18:00 WITA
8. `~/logs/garuda-gap-detector.log` run history 2026-04-26 → 2026-05-15
9. `~/logs/matagaruda-gap-consumer-err.log` 2137 "Legacy gap drained" warnings
10. `~/Desktop/OSINT-Nexus/docker-compose.yml` neo4j container definition (17687→7687)
11. `docker info` + `pgrep "Docker Desktop"` empirical Docker host status
