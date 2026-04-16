# Phase 1 — SINAPSI — Metriche before/after (2026-04-16)

> Companion to `docs/PHASE1_SINAPSI_STATUS_2026-04-16.md`.
> Verified live on Pro at 2026-04-16 ~07:30 WITA.

## Scopo

Il plan Phase 1 (`docs/superpowers/plans/2026-04-14-organism-phase1-sinapsi.md`)
prometteva metriche before/after. Questa è la prima registrazione formale —
baseline per dichiarare Fase 1 chiusa quando i numeri convergono.

Frase del plan: *"Numeri o non esiste"*. Eccoli.

## Redis streams

| Stream             | Before (plan)  | 2026-04-16 04:55 (audit) | 2026-04-16 ~07:30 | Notes                                          |
| ------------------ | -------------- | ------------------------ | ----------------- | ---------------------------------------------- |
| `garuda:raw`       | n/a            | 463                      | 473               | producer: harvesters; consumer: normalizer    |
| `nexus:gaps`       | 552 (unconsumed)| 828                     | 897               | producer: gap_detector 8 Cypher queries        |
| `intel:articles`   | n/a            | 0                        | 0                 | producer: NONE (War Room not wired — P0-3)     |
| `bridge:inbound`   | n/a            | n/a                      | 0                 | populated by bridge pull from Fly outbox       |
| `bridge:outbound`  | n/a            | n/a                      | 1                 | 1 manual test from Apr 14, stuck PEL           |

`nexus:gaps` cresce ~23 entries/h. La crescita è normale (gap_detector cron
twice-daily produce in burst). Lo stream NON viene trimato — entries restano
anche dopo XACK; `XLEN` non rappresenta il backlog reale.

## Gap consumer health

```
$ redis-cli XINFO GROUPS nexus:gaps
name              = gap-consumer
consumers         = 1
pending           = 0
last-delivered-id = 1776247206924-0
entries-read      = 780
```

- **Pending = 0** → ogni entry letta è stata ack'd. Il consumer NON è bloccato.
- **Entries-read = 780 / XLEN = 897** → 87% delle entries dello stream sono
  state lette dal consumer; le rimanenti 117 sono produzione recente (cron
  ogni 12h, prossimo run drena tutto).

### MA — c'è un problema invisibile in pre-fix

Le 780 entries lette **sono in formato legacy** (gap_type = `missing_attribute`
con `attribute=nip|lhkpn|...`, NOT canonical envelope `gap.missing_nip`). Pre-fix,
gap_consumer le mappava tutte come "unknown gap type" e le **scartava** con
ack silenzioso. La metrica `pending=0` è quindi fuorviante: il consumer ha
"processato" 780 entries draining 100% di esse senza dispatcher mai chiamato.

Histogram delle 897 entries totali (verificato 2026-04-16):

| `gap_type`           | `attribute`              | count | post-fix routing                      |
| -------------------- | ------------------------ | ----- | ------------------------------------- |
| `missing_attribute`  | `nip`                    | 260   | → `gap.missing_nip` → lhkpn_harvester |
| `missing_attribute`  | `profile`                | 195   | drained (no canonical mapping)        |
| `missing_attribute`  | `officials_or_documents` | 195   | drained                               |
| `missing_attribute`  | `procurement_link`       | 130   | → `gap.missing_procurement` → Phase 2 |
| `missing_attribute`  | `lhkpn`                  | 39    | → `gap.missing_lhkpn` → lhkpn         |
| `missing_attribute`  | `WORKS_AT:Kanim…`        | 39    | drained                               |
| `missing_attribute`  | `officials_struktur`     | 26    | → `gap.kanim_struktur` → reg_watcher  |
| `missing_attribute`  | `angkatan`               | 13    | → `gap.missing_angkatan` → lhkpn      |
| `missing_relation`   | (various)                | 390   | drained                               |
| `stale_attribute`    | (various)                | 195   | → `gap.stale_official` → reg_watcher  |

Post-fix:
- **663 entries (74%)** verranno effettivamente dispatched ad un agente
- **234 entries (26%)** verranno drained con log forensic (`gap_legacy.py`)
- Pre-fix: **0 entries dispatched, 100% silent drain**

## Bridge nerve

| Metric                               | Pre-fix (≤2026-04-16 07:00) | Post-fix (PR #62)             |
| ------------------------------------ | --------------------------- | ----------------------------- |
| Cursor advancement                   | Stuck (every pull errored)  | Updates su ogni cycle clean   |
| `matagaruda-bridge-err.log` errors/h | ~60 (1/cycle)               | 0                             |
| Successful pulls/h (~)               | 0                           | 60 (cron StartInterval=60)    |
| Pull latency p50                     | n/a (timeout 15s)           | ~150ms                        |

Cursor file vuoto/inesistente: `~/.agent/decisions/bridge_cursor.json` viene
creato al primo pull con eventi reali. Fly outbox attualmente è vuoto, per cui
no events to fetch → cursor non scritto.

## LaunchAgents

| Agent                              | Loaded | Last fire status                           |
| ---------------------------------- | ------ | ------------------------------------------ |
| `com.matagaruda.bridge.adaptive`   | ✅     | Cron 60s, post-fix clean                   |
| `com.matagaruda.gap.consumer`      | ✅     | Idle (cron-triggered, fired ~3 ore fa)     |
| `com.matagaruda.watcher.daily`     | ✅     | Idle (daily 06:00 WITA)                    |
| `com.matagaruda.sentinel.daily`    | ✅     | Idle                                       |
| `com.garuda.consumer.daily`        | ✅     | Idle                                       |
| `com.garuda.gap-detector.twice-daily` | ✅  | Idle                                       |

Cleanup eseguito 2026-04-16: rimossi **8** file orfani
`*.plist.corrupted-20260412` da `~/Library/LaunchAgents/`. L'audit ne
menzionava 1 (gap-detector); diagnostica ha trovato gli altri 7 dalla stessa
corruzione di massa del 2026-04-12 (tutti con plist live sani come
controparte).

## Bridge IPv6 regression — diagnosi 2026-04-16

Tra il 14-15 Apr 2026 Fly.io ha iniziato a pubblicare record AAAA per
`nuzantara-rag.fly.dev` (`2a09:8280:1::b3:64d:0`). Il Pro non ha una route
IPv6 funzionante verso Fly's anycast. Sotto launchd's minimal env, curl's
Happy Eyeballs fallback è inaffidabile: alcune invocazioni scelgono v6 e
fanno hang per `--max-time` intero (15s); altre falliscono in 1ms.

Conseguenza: 48h di bridge silently broken. Audit ha visto bridge process
loaded e ha assunto healthy. **Process up, network broken**.

Fix in PR #62: aggiunto `-4` flag a entrambe le curl in
`apps/mata-garuda/mata_garuda/bridge/nerve.py`. Verifica:

```
$ dig AAAA nuzantara-rag.fly.dev → 2a09:8280:1::b3:64d:0
$ curl -6 …/health → (7) Couldn't connect (1ms)
$ curl -4 …/health → HTTP 200 (128ms)
```

## Cosa manca per chiudere Phase 1

In ordine:

1. **PR #62 merge** — bridge IPv4 fix (P0 emergency)
2. **PR corrente (questa)** — coerce legacy + metrics + cleanup (P1-4 + P1-5 + P1-6)
3. **P0-2 E2E test** — `tests/test_phase1_e2e.py` per gate definitivo
4. **P0-1 LPSE harvester** — secondo dei 2 harvester promessi nel doc madre
5. **P0-3 War Room → `intel:articles`** — wire del producer mancante (Cycle 1 ha 0 byte/giorno)

Quando questi 4 PR sono merged, eseguire **un secondo metrics snapshot**
chiamato `PHASE1_METRICS_2026-04-XX_FINAL.md` e validare:

- [ ] `nexus:gaps` entries-read si avvicina a XLEN (pending può restare 0)
- [ ] `intel:articles` XLEN > 0 (almeno 1 articolo prodotto da War Room)
- [ ] `bridge:inbound` riceve eventi (cursor avanza)
- [ ] `bridge:outbound` consumed con `bridge-push` group (ack delle entries reali)
- [ ] LPSE harvester registrato in `automation_catalog.json`
- [ ] Test e2e green in CI

Solo a quel punto Phase 1 è **closed**, e Phase 2 (RIFLESSI, plan già
scritto: `2026-04-14-organism-phase2-riflessi.md` 24 task 129 step) può
iniziare.

---

_Snapshot eseguito 2026-04-16 ~07:30 WITA da Claude Opus 4.6 su Pro
(Nuzantara host) sul branch `phase1-coerce-and-metrics`._
