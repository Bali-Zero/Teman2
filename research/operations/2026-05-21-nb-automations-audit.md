---
date: 2026-05-21
domain: operations
client_case: internal — NB/NLM automation health audit
sources: 12 (LaunchAgents, logs, source code, MCP live queries, git history)
---

# NB Automations Health Audit — 2026-05-21

Audit completo di tutti i job che alimentano/curano i nostri NotebookLM. Lettura del codice, non dei docs. Worktree `audit-nb-automations-2026-05-21`.

## Verdict summary

| Componente                                | Stato                                                                         | Severità        |
| ----------------------------------------- | ----------------------------------------------------------------------------- | --------------- |
| **mata-garuda bridge (Fly→Pro NLM pipe)** | 🔴 **BROKEN** — 15gg di stall                                                 | **P0**          |
| NB-INTEL-\* (5 NB)                        | ⚠️ **DYING** — feed fermo dal 6-11 maggio                                     | P0 (corollario) |
| intel-lake-router (5min)                  | ✅ Healthy                                                                    | —               |
| intel-lake-nb-pusher (15min)              | ✅ Healthy (idle, no work in queue)                                           | —               |
| intel-lake-outbox-drain                   | ✅ Healthy (PR #667 ha fixato cicatrix jsonb)                                 | —               |
| intel-lake-shadow-validate (6h)           | ✅ Healthy (no divergence)                                                    | —               |
| intel-lake-e2e-probe (6h)                 | ⚠️ asyncpg `ConnectionDoesNotExistError` ultimo rc=1 21/05 18:30              | P2              |
| regulatory-watcher (daily 07:00)          | ✅ Healthy (cascata claude-sonnet-4-6 OK)                                     | —               |
| nb-curator weekly (Mode B Sun 04:00)      | ✅ Healthy (ultimo run 18/05 04:00 — Mode B health report scritto)            | —               |
| nb-intel-delta-watcher (hourly)           | ⚠️ Vede `sources=0` su Immigration perché bridge upstream è stuck             | P1 (sintomo)    |
| nb-mitochondrial-monitor (daily)          | ❓ Nessun log file — verifica se ha mai girato                                | P2              |
| matagaruda-kg-linker                      | ⚠️ Idle (entities_total=0 — bridge stuck downstream)                          | P1 (sintomo)    |
| matagaruda-nlm-feeder-stream (hourly)     | ⚠️ Idle (processed=0 da 14 cicli — bridge stuck upstream)                     | P1 (sintomo)    |
| matagaruda-sentinel.hourly                | ⚠️ pulse health=yellow/green alternato, `no_items` action (stessa root cause) | P2              |
| nlm-bridge (port 18790)                   | ⚠️ UP healthy ma `request_count=0` — orphan service nessun consumer           | P3 (waste)      |

## P0 — Bug root cause

### Cicatrix 2026-05-14 `jsonb_double_encoding_systemic` riprodotto in `bridge_outbox`

**File**: `apps/backend-rag/backend/services/bridge/outbox.py:52-56`

```python
row = await conn.fetchrow(
    "INSERT INTO bridge_outbox (type, payload) VALUES ($1, $2::jsonb) RETURNING id",
    event_type,
    json.dumps(payload, ensure_ascii=False),   # ← BUG: pre-encoding
)
```

**Pool config**: `apps/backend-rag/backend/app/setup/service_initializer.py:474-481` registra `set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads)`. Quindi quando l'INSERT passa `json.dumps(payload)` al pool, asyncpg **ri-applica** `json.dumps()` via codec → JSONB scalar literal `'"{\"foo\":\"bar\"}"'`.

**Downstream**:

1. `GET /api/bridge/events` (apps/backend-rag/backend/services/bridge/outbox.py:80-88) → `r["payload"]` decoded da asyncpg = una stringa JSON (non un dict).
2. `apps/mata-garuda/mata_garuda/bridge/nerve.py:165` → `**event.get("payload", {})` su una `str` → `TypeError: 'str' object is not a mapping`.
3. `nerve.py:179-190` → "Cursor NOT advanced" per all-or-nothing semantics → loop infinito di retry sugli stessi 50 eventi.

**Evidence**:

- `~/logs/matagaruda-bridge-err.log` = 47MB, 64,721 error lines OGGI (21/05).
- Ultimo errore `2026-05-21 23:28:53,865`. Ogni minuto: `fetched=50 published=0 errors=50`.
- Eventi stuck: id 1-50.

### Impatto downstream (P0 corollario)

Tutta la pipeline NB-INTEL dipende dal bridge:

| NB                   | UUID           | Latest source (live MCP query)    | Source count |
| -------------------- | -------------- | --------------------------------- | ------------ |
| NB-INTEL-Immigration | `1ed02e54-...` | `TEST e2e check 2026-05-06 22:50` | 80           |
| NB-INTEL-Press       | `9d262101-...` | "May 11th" (10gg fa)              | 215          |
| NB-INTEL-Regulation  | `a17f134e-...` | `01 December 2025` (5+ mesi!)     | 41           |
| NB-INTEL-Tax         | `7fb12c9c-...` | (non testato live)                | 17           |
| NB-INTEL-AIResearch  | `dc5d01cd-...` | (non testato live)                | 600          |

I 5 NB-INTEL **non ricevono nuove sorgenti dal 2026-05-06** = 15 giorni di stall. Antibody `nlm-feeder-resurrect-2026-05-06` aveva risolto il problema redis split-brain Pro/Mini, ma il bridge è regredito su un altro layer.

### Fix proposto

1. **Patch `outbox.py:52-56`** — rimuovere `json.dumps()` e lasciare che il codec del pool serializzi una volta sola:
   ```python
   row = await conn.fetchrow(
       "INSERT INTO bridge_outbox (type, payload) VALUES ($1, $2::jsonb) RETURNING id",
       event_type,
       payload,                       # raw dict — codec encodes once
   )
   ```
2. **Migration SQL** per riparare i row esistenti (specchio mig 174):
   ```sql
   UPDATE bridge_outbox
   SET payload = payload::text::jsonb
   WHERE jsonb_typeof(payload) = 'string';
   ```
3. **Test integration** `apps/backend-rag/backend/tests/services/bridge/test_outbox.py` deve fare round-trip insert→fetch e asserire `isinstance(r["payload"], dict)`.
4. **Defensive in nerve.py**: anche post-fix, aggiungere fallback se `payload` è `str`:
   ```python
   payload = event.get("payload", {})
   if isinstance(payload, str):
       payload = json.loads(payload)  # legacy double-encoded
   ```

## P1 — Sintomi che si risolveranno con il P0

- `matagaruda-bridge` cursor NOT advanced (loop infinito sullo stesso batch)
- `matagaruda-nlm-feeder-stream`: nulla da fed (bridge upstream vuoto)
- `matagaruda-kg-linker`: nessuna entity da linkare
- `nb-intel-delta-watcher`: alert "NB-INTEL-Immigration empty" giustamente acceso
- `intel-lake-nb-pusher`: pending=0 (corretto perché router non vede nuove righe da bridge)

## P2 — Findings minori

### `nb-mitochondrial-monitor.daily` — no log file

**Plist**: `~/Library/LaunchAgents/com.nuzantara.nb-mitochondrial-monitor.daily.plist` (mode `0444`, 1347B, mtime 7 mag).  
**LaunchAgent status**: `last exit code = (never exited)` → **mai bootstrap**. Verificare se mai loaded con `launchctl bootstrap gui/$(id -u) ...`.

### `intel-lake-e2e-probe.6h` — asyncpg connection reset

Ultimo run 2026-05-21 18:30:16 rc=1. Causa: `ConnectionDoesNotExistError: connection was closed in the middle of operation` su asyncpg connect al pg-proxy. Probabile cold-start/timeout proxy. Probe alert SEND failed → silent failure.

### nlm-bridge orphan

- `~/Library/LaunchAgents/com.balizero.nlm-bridge.plist` running su port 18790
- StandardOut path `/tmp/nlm-bridge.log` — volatile su reboot (anti-pattern noto cicatrix)
- `request_count = 0` dopo 16793s uptime (4h40m) → nessun client lo sta usando
- Verificare se è dead code residuo o ha consumer che dovrebbe agganciarsi ma non lo fa

### matagaruda-invalidation-sweep.stderr.log — pre-fix history

Errori `ConnectionRefusedError ('127.0.0.1', 15432)` fino al 2026-05-19. Da 19/05 in poi → OK (`invalidated=0 dry_run=False`). Già risolto, log da ruotare.

## P3 — Anti-pattern noti

- `/tmp/nlm-bridge.{log,err}` (cicatrix `STRUCTURAL: 53 LaunchAgents Pro, only 13% KeepAlive`).
- `matagaruda.bridge.adaptive.plist`: `RunAtLoad=false` + `KeepAlive` mancante. Funziona via `StartInterval=60`, ma non sopravvive a reboot fino al primo tick.

## Decision matrix per Antonello

| Decisione                                            | Effort | Rischio                               | Beneficio                                                                             |
| ---------------------------------------------------- | ------ | ------------------------------------- | ------------------------------------------------------------------------------------- |
| **Fix bridge_outbox (P0)** + migration repair + test | 1.5h   | low (pattern già validato in mig 174) | 5 NB-INTEL riprendono ingestion + bridge errato smette di scrivere 47MB/giorno di log |
| Decommissionare nlm-bridge se orphan                 | 15min  | nullo                                 | Smette di reservare port 18790 + processo idle                                        |
| Fix probe asyncpg retry con backoff                  | 30min  | low                                   | Probe alert riprende a notificare                                                     |
| Bootstrap nb-mitochondrial-monitor.daily             | 5min   | nullo se script esiste                | Nuovo signal canale                                                                   |

## Files toccati per analisi

- `apps/backend-rag/backend/services/bridge/outbox.py:52-88`
- `apps/backend-rag/backend/app/routers/bridge.py:89-103`
- `apps/backend-rag/backend/app/setup/service_initializer.py:474-516`
- `apps/mata-garuda/mata_garuda/bridge/nerve.py:140-192`
- `~/logs/matagaruda-bridge-err.log` (47MB), `~/logs/intel-lake-*.log`, `~/logs/nb-*.log`
- `~/Library/LaunchAgents/com.{balizero,matagaruda,nuzantara}.*.plist` (30 plist NB-touching)

## Cicatrix to write

Aggiungere a `.claude/rules/cicatrix-scars.md`:

```
### ⚠️ STRUCTURAL: bridge_outbox jsonb double-encoding — Fly→Pro NLM pipe stuck 15 days (2026-05-21)

_Discovered: 2026-05-21 ~23:30 WITA durante audit NB automations · Severity: **P0** · Fix pending_

**TRAUMA**: stesso pattern cicatrix 2026-05-14 `jsonb_double_encoding_systemic` ma in tabella diversa
(`bridge_outbox` vs intel-lake `events_outbox`). PR #667 + mig 174 hanno fixato events_outbox; bridge_outbox
mai toccato → mata-garuda-bridge stuck dal 2026-05-06 (15 giorni), 47MB/giorno error log, 5 NB-INTEL non
ricevono nuove sorgenti.

**ANTIBODY (pending)**: vedi research/operations/2026-05-21-nb-automations-audit.md §"Fix proposto"
```
