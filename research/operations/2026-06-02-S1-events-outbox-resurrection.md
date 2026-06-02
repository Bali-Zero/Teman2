---
date: 2026-06-02
domain: compliance
client_case: none
session: S1-events-outbox-resurrection (ONDA 1, Codex-heavy)
sources:
  - research/operations/2026-05-31-system-audit-FROZEN.json (§prod_data_postgres.events_outbox — baseline)
  - apps/backend-rag/backend/services/events/event_bus.py (PG_CHANNEL_MAP, replay window)
  - apps/backend-rag/backend/services/events/outbox.py (publish/acknowledge/replay_unconsumed)
  - apps/backend-rag/backend/services/events/handlers/_core.py (consumers)
  - packages/cell-core/cell_core/observatory.py (cell_pulse_sustained_red emitter)
  - scripts/pg-to-organism-bridge.py (cell pulse consumer)
artifact: research/operations/S1-outbox-resurrection-FROZEN.json
---

# S1 — events_outbox: i 6 canali morti (5 in scope)

> **Topologia**: orchestrator-worker pipeline. 5 assalitori (1/canale, Workflow fan-out) →
> 5 devils-advocate replay-risk analysts (con `codex exec --sandbox read-only` come spalla) →
> ri-verifica indipendente dell'orchestratore (anti-allucinazione) → meccanico unico (git serial).
>
> **⚠️ DATO LIVE NON DISPONIBILE**: il MCP `postgres-nuzantara` era DOWN per tutta la sessione
> (`SELECT 1` → `MCP error -32603`). Tutti i conteggi `events_outbox` qui sono il **baseline
> 2026-05-31** (aggregato 3× riproducibile), NON una lettura live di questo turn. La macchina
> (Air-M5) non esegue né l'EventBus Fly né i daemon Pro. **Ogni fix è NEEDS-ANTONELLO-on-Pro
> dopo re-verifica live.**

---

## 0. La scoperta centrale (load-bearing, vale per TUTTI i canali)

**L'auto-replay di `events_outbox` è hard-cappato a `max_age_minutes=60`.**

- `event_bus.py:421-425` — `_replay_outbox_on_reconnect` chiama
  `replay_unconsumed(..., channel=pg_channel, max_age_minutes=60)` per ogni canale.
- `outbox.py:331-333` — filtra `created_at > NOW() - INTERVAL '60 minutes'`.

**Implicazione**: qualunque evento non-consumato più vecchio di 60 minuti **non verrà MAI
ri-replayato** alla riconnessione del listener, indipendentemente da quanti restart fai. Quindi
tutti i ~492 eventi stale (>24h, alcuni 16 giorni) sono **orfani permanenti a prescindere dalla
vitalità del consumer attuale**.

> **Conseguenza operativa**: "riavviare il consumer" da solo **NON drena mai il backlog**. Serve
> un drain manuale one-shot con finestra allargata, OPPURE mark-consumed-and-drop. Questa è una
> decisione molto più pesante di "riavvia il daemon" — e cambia il framing di ogni canale sotto.

**Aggravante 1** — la dedup guard in-handler (`handlers/_core.py:32-46`, `_DEDUP_WINDOW_S=10`) è
una finestra **in-memory di 10 secondi**, fredda dopo ogni restart → ZERO protezione contro il
replay di eventi vecchi di giorni. L'idempotenza deve venire da chiavi naturali o da check su
`_outbox_id` in ogni handler, non da questa guard.

**Aggravante 2 (perché è rimasto silente fino a 16 giorni)** — l'init dell'EventBus è
best-effort/swallowed (`app_factory.py` ~263: cattura `Exception`, logga
`⚠️ Failed to initialize EventBus`, continua a servire HTTP). Un EventBus morto è **invisibile a
`/health`**. `get_unconsumed_count` esiste (`outbox.py:450`) ma non è health-gated né allertato.

---

## 1. Tabella 5-canali × verdetto

| Canale | Unconsumed | Stale | In PG_CHANNEL_MAP | Consumer atteso | Causa morte | Replay verdict | Strategia raccomandata |
|---|---|---|---|---|---|---|---|
| `client_changed` | 178 | 215h | **YES** (`event_bus.py:49`) | EventBus in-process (proc `rag` Fly), handler `on_client_changed` (`_core.py:341`) | runtime/lifecycle gap + finestra 60-min | **SAFE_WITH_CONDITIONS** | mark-consumed (drop) **oppure** replay con ramo-INSERT saltato |
| `practice_changed` | 78 | 38h | **YES** (`event_bus.py:48`) | EventBus 3 subscriber + `PracticeStatusListener` (LISTEN separato) | runtime ack-starvation + finestra (PARTIAL) | **SAFE_WITH_CONDITIONS** | mark-consumed (drop) |
| `cell_pulse_sustained_red` | 50 | 64h | **NO** ⚠️ | `scripts/pg-to-organism-bridge.py:73` (fire-and-forget, **non acka mai**) | strutturale: bridge non acka + canale fuori mappa → righe **immortali by-design** | **UNSAFE** | mark-consumed (drop) — allarmi "red" stale; replay → falsi restart-actuator |
| `intel_lake_event` | 24 | 378h | **YES** (`event_bus.py:147`) | EventBus in-process `IntelLakeRouter.route_event` | producer silente dal 2026-05-14 (intel.nightly disk-full) + finestra | **SAFE_WITH_CONDITIONS** | replay-safe via finestra allargata (UPDATE idempotente `WHERE routing_status='unrouted'`) **oppure** mark-consumed |
| `war_room_event` | 5 | 378h | **YES** (`event_bus.py:60`) | **NESSUNO — stillborn** (`publisher/subscriber.py` mai creato; subscribe solo nel test) | consumer mai esistito in prod (superato da `wr2_carousel_events_outbox` mig 199) | **SAFE_WITH_CONDITIONS** | mark-consumed (drop) — canale abbandonato; **NON costruire publisher** per drenare (rischio re-publish IG/LinkedIn/blog) |

> `whatsapp_message_received` (gate-off atteso, wa-mirror local-only cutover 2026-05-24) = benigno,
> **fuori scope, non toccato**.

---

## 2. Tre pattern di morte distinti (non è "un daemon morto")

La diagnosi del FROZEN.json 2026-05-31 ("broad multi-consumer gate-off") era corretta nella forma
ma il dettaglio rivela **tre cause strutturalmente diverse**:

### Pattern A — Consumer vivo nel codice, ucciso dal runtime + finestra di replay
`client_changed`, `practice_changed`. Il canale è in mappa, l'handler è subscribed e presente. La
morte è: (1) l'EventBus in-process (solo sul process-group `rag` Fly) si è fermato a metà maggio
(restart/suspend/task morto), e (2) la finestra 60-min ha reso impossibile il recupero al
reconnect. `client_changed` si congela esattamente al 2026-05-21 18:13 — **prima** del cutover
wa-mirror, quindi il cutover NON è la causa.

### Pattern B — Stillborn (consumer mai nato)
`war_room_event`. Il canale è in mappa, l'EventBus LISTEN e riceve il NOTIFY, ma `emit()` trova
`handlers=[]` → no-op. Il subscriber di produzione (`publisher/subscriber.py`, citato nel docstring
`orchestrator.py:11-12` come "Sprint 9") **non è mai stato creato** (`ls` assente, `git log` vuoto).
L'unico `subscribe("war_room.event", ...)` nel repo è in un **test**
(`test_outbox_callsite_integration.py:197`). Il path è stato di fatto **superato** da
`wr2_carousel_events_outbox` (migration 199, consumer `war_room/wr2_outbox_consumer.py`).

### Pattern C — Strutturale: canale fuori mappa + consumer fire-and-forget che non acka
`cell_pulse_sustained_red`. Emesso da `observatory.py:207` (`INSERT INTO events_outbox` +
`pg_notify`) ma il canale **NON è in PG_CHANNEL_MAP** (solo `cell_pulse_observed` lo è). L'unico
consumer è `pg-to-organism-bridge.py` — un relay LISTEN→Redis/JSONL fire-and-forget che **non
scrive mai `consumed_at`**. Risultato: le 50 righe sono **immortali per design** — nessun code path
le marcherà mai consumed. Non è un daemon morto, è un buco architetturale.

`intel_lake_event` è il quarto pattern (producer-silent): consumer vivo e idempotente, ma il
producer (`intel.nightly`) è morto il 2026-05-14 per disco pieno → nessuna riga nuova da 16 giorni.

---

## 3. Replay risk — il vero pericolo per canale (verdetto adversarial)

| Canale | Side-effect non-idempotente al replay | Idempotenza | Perché il verdetto |
|---|---|---|---|
| `client_changed` | **Drive folder duplicate** (`_core.py:151` `_create_drive_folder` su INSERT), riga CRM-interaction duplicata (`_log_interaction`), bridge-outbox `crm.client_created` ri-emesso. NO email diretta. | dedup 10s in-memory (fredda dopo restart) → **non protegge** 9-giorni-replay | SAFE solo se si **salta il ramo INSERT** o si pre-controlla l'esistenza folder |
| `practice_changed` | bridge-outbox `crm.practice_completed/created` ri-emesso; commission accrual (`partners/events.py`) su status=completed; scan predittivi | guard naturale parziale | SAFE_WITH_CONDITIONS — meglio drop |
| `cell_pulse_sustained_red` | **falso `fly_machines_restart`** su nuzantara-rag (`organism/rules/base.yaml:89-95`): un allarme "red" di 64h fa che la regola `cell_sustained_red_restart` riavvii una macchina sana | nessuna (relay non idempotente) | **UNSAFE** — replay = restart spurio di produzione |
| `intel_lake_event` | nessun side-effect esterno: solo `UPDATE intel_items WHERE routing_status='unrouted'` (no-op se già routed) + audit-log INSERT (non guardato, ma solo rumore). NB push è un cron **separato** idempotente su `(item_id,nb_uuid,content_hash)` | idempotente su chiave naturale | SAFE_WITH_CONDITIONS — il replay è no-op |
| `war_room_event` | **se** si costruisse il publisher: doppio post IG (`graph.facebook.com`), doppio LinkedIn, doppio blog + git push, doppio X. Solo `draft_approved`/`post_published` triggererebbero publish; status interni no. | nessuna dedup su `_outbox_id`; guard solo SELECT con TOCTOU; **nessun UNIQUE(draft_id,platform)** | SAFE oggi (nessun consumer); UNSAFE se si wireasse un publisher |

---

## 4. Spec eseguibile (NEEDS-ANTONELLO — NON eseguito)

> Tutte le mutation sono fuori dallo scope read-only di questa sessione. Eseguire su Pro/Fly con
> MCP/psql attivi, dopo STEP 0.

### STEP 0 — re-verifica live (OBBLIGATORIO prima di ogni azione)
```sql
-- read-only, su Pro con postgres MCP attivo
SELECT channel,
       COUNT(*) FILTER (WHERE consumed_at IS NULL)                          AS unconsumed,
       MIN(created_at) FILTER (WHERE consumed_at IS NULL)                   AS oldest,
       MAX(created_at) FILTER (WHERE consumed_at IS NULL)                   AS newest,
       array_agg(DISTINCT payload->>'event_type')                          AS event_types
FROM events_outbox
WHERE channel IN ('client_changed','practice_changed','cell_pulse_sustained_red',
                  'intel_lake_event','war_room_event')
  AND consumed_at IS NULL
GROUP BY channel ORDER BY unconsumed DESC;
```
Se righe dell'ultima ora sono già consumed per `client_changed`/`practice_changed`/`intel_lake_event`,
il path live è sano e solo le righe vecchie sono orfane (più probabile).

### STEP 1 — diagnosi liveness consumer (Fly + Pro)
- EventBus Fly: `fly logs -a nuzantara-rag | grep -E 'EventBus|Failed to initialize EventBus|replayed'`
- bridge Pro: heartbeat `~/.organism/last_seen/pro.pg_organism_bridge.json` + mtime `~/.organism/events/pg-bridge.jsonl`.

### STEP 2 — drain/cleanup per canale (SCELTA per verdetto)
- **`cell_pulse_sustained_red` (UNSAFE → drop)**:
  `UPDATE events_outbox SET consumed_at=NOW(), consumed_by='manual:stale-red-drop-2026-06' WHERE channel='cell_pulse_sustained_red' AND consumed_at IS NULL;` — allarmi "red" di 64h su backend ora sano; replay = restart spurio. Pura metadata, zero side-effect.
- **`war_room_event` (abbandonato → drop)**:
  `UPDATE events_outbox SET consumed_at=NOW(), consumed_by='manual:abandoned-war_room_event-2026-06' WHERE channel='war_room_event' AND consumed_at IS NULL;` — **NON** costruire `publisher/subscriber.py` per drenare (re-publish IG/LinkedIn/blog di contenuti vecchi 16gg).
- **`client_changed` / `practice_changed` (SAFE_WITH_CONDITIONS)**: preferito **drop** (le notifiche descrivono cambi-riga già riflessi nello stato attuale; il vero valore — folder/interaction — è auto-provisioning una-tantum). Se si vuole replay, **saltare il ramo INSERT** (Drive folder + interaction) o pre-controllare `google_drive_folder_id`.
- **`intel_lake_event` (SAFE_WITH_CONDITIONS)**: replay sicuro via script admin one-shot
  `replay_unconsumed(conn, dispatch_fn, channel='intel_lake_event', max_age_minutes=40000)`
  (UPDATE guardato + `acknowledge` idempotenti); attesi per lo più no-op 304. OSINT Law 2 — resta su Pro.

### STEP 3 — prevenzione (PR separata, code-only, review)
1. **Parametrizzare** `event_bus.py:425` con env `EVENTBUS_REPLAY_MAX_AGE_MIN` (default 60) — per drain controllato senza patch del default (W36 stale-actuator guard preservato).
2. **Stale-unconsumed alerter**: cron/health che fa `get_unconsumed_count(channel)` e alerta Telegram se `> N` con `created_at < NOW()-INTERVAL '2 hours'` (chiude il blind-spot GREEN-while-orphaning).
3. **EventBus liveness in `/health`**: `get_stats()` (`event_bus.py:536-548`) già espone running+pg_connected, ma non è health-gated.
4. **`cell_pulse_sustained_red`**: o aggiungerlo a PG_CHANNEL_MAP con un consumer che acka, o far ackare al bridge le righe outbox che relaya (oggi è la sola immortalità strutturale).
5. **`war_room_event`**: correggere il docstring fuorviante `orchestrator.py:11-12` (subscriber Sprint-9 mai creato) e annotare il canale come observability/abbandonato in `event_bus.py:56-60`.

---

## 5. Checklist verifica (anti-allucinazione, fatta in-turn)

- [x] `max_age_minutes=60` hard-cap — letto `event_bus.py:421-425` + `outbox.py:331-333` questo turn
- [x] `cell_pulse_sustained_red` NON in PG_CHANNEL_MAP — grep `event_bus.py:47-150` (solo `cell_pulse_observed:105`)
- [x] `intel_lake_event` IS in mappa a riga 147 (smentito l'hint del brief)
- [x] `pg-to-organism-bridge.py` fire-and-forget — nessun `consumed_at`/`UPDATE events_outbox`/`acknowledge` (LISTEN:235 + redis XADD:204)
- [x] `observatory.py:76-80,207` `INSERT INTO events_outbox` per `cell_pulse_sustained_red`
- [x] `war_room.event` subscribe solo nel test `test_outbox_callsite_integration.py:197`; `publisher/subscriber.py` assente
- [x] `client.changed`/`practice.status_changed` handlers registrati `_core.py:341-342`
- [x] PII scan FROZEN.json: 0 email, 0 telefoni, 0 NPWP-like, 0 client_id literal

---

## 6. Verità non-allucinata vs NEEDS-ANTONELLO

**Verificato nel codice (autoritativo, in-turn)**: tutti i mapping PG_CHANNEL_MAP, registrazioni
handler, fire-and-forget del bridge, finestra di replay 60-min, emitter observatory, stillborn
war_room. Questi sono fatti del code-as-truth, indipendenti dallo stato del DB.

**NEEDS-ANTONELLO-on-Pro (non verificabile da Air-M5 con MCP down)**: conteggi/timestamp live di
`events_outbox`; liveness dell'EventBus Fly e del `pg-organism-bridge` Pro; e **l'esecuzione di
qualunque mutation/drain/prune** (Symbiosis Law 5 — le decisioni strutturali passano da Zero).
