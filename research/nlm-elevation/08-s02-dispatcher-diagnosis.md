---
date: 2026-04-25
type: diagnosis
task: S0.2 dispatcher heartbeat writer
status: complete
---

# S0.2 Diagnosi: chi scrive `.last.json` con ts stale

## Domanda originale

Perché i file `~/.agent/decisions/state/nlm_nb*.last.json` hanno `mtime` fresco (aggiornato ogni 5 min) ma `ts` interno stale (14 aprile 2026)? Il monitoraggio downstream crede "è vivo" mentre il sistema è morto da 10 giorni.

## Metodo

1. Ricerca writer via `grep -rln "\.last\.json.*write"` → 5 candidati Python.
2. Ispezione di ciascuno: solo `scripts/nlm_nb1_daily_refresh.py` scrive esplicitamente `nlm_nb1_daily_refresh.last.json` (riga 445).
3. Ispezione `nuzantara-sentinel.py` (il principale consumer di state): **legge** `.last.json` (riga 212) ma **non scrive**. Scrive solo `SENTINEL_STATUS_FILE` globale (riga 812).
4. Monitor live su `daily_ops.last.json`: osservato tick alle 03:30:04, 03:35:00, 03:45:04 WITA (ogni 5 min). `lsof` non cattura il writer (scrittura sub-secondo).
5. Processi attivi alle 03:35: `openclaw-gateway` (PID 39517, Node.js), `nuzantara-sentinel` **NON** tra i processi → sentinel scrive solo al tick se lanciato via launchctl, ma non è mai stato il writer dei `.last.json`.
6. Il binario `~/.openclaw/bin/openclaw` è wrapper bash che lancia `~/.openclaw/lib/node_modules/openclaw/dist/entry.js` (Node.js). `grep` nei bundle JS minified non trova letterale "openclaw-bridge" ma trova pattern `decisions/state` in `cron-cli-CZvdx9PH.js` e `gateway-cli-ChUE8Mp7.js`.

## Root cause

**Il writer è `openclaw-gateway`** (daemon Node.js). Ogni 5 min (tick allineato con sentinel `StartInterval=300`), gateway itera tutti i job in `~/.openclaw/cron/jobs.json` e scrive uno `.last.json` per ciascuno in `~/.agent/decisions/state/`.

Il contenuto scritto **non è un heartbeat reale** dell'esecuzione: è una **proiezione** di `jobs.json.state.lastRunAtMs`. Struttura prodotta:

```json
{
  "job": "nlm-nb3-company-setup",
  "ts": 1776105900,  // copia di lastRunAtMs/1000 da jobs.json
  "status": "failed",
  "host": "Nuzantara",
  "source": "openclaw-bridge",
  "last_error": "OpenClaw consecutiveErrors=0, lastStatus=pending",
  "duration_ms": 5
}
```

Il campo `source: "openclaw-bridge"` identifica il writer (gateway Node via formato trattino), da distinguere dalla stringa `_source: "openclaw_bridge"` (underscore) che appare in `nuzantara-sentinel.py::_collect_openclaw_states()` (riga 196) dove sentinel **sintetizza** stato in-memory per il suo processing interno. Sono due sistemi paralleli: il gateway scrive file, il sentinel li re-legge.

## Il vero bug

Il gateway **non è il bug**. Fa il suo dovere: proietta su disco lo stato che ha in `jobs.json`. Il bug è a monte: **`jobs.json.state.lastRunAtMs` di NB-2..NB-10 resta fermo al 14 aprile** perché:

1. Il cron effettivo di NB-2..NB-10 gira via crontab → `cron-runner.sh` → `run_nbN_pipeline.sh` → `python -m apps.evaluator.nlm_deep_research.pipeline`.
2. Questa catena **non notifica openclaw-gateway** del successo/fallimento: gateway non viene invocato da `cron-runner.sh`.
3. Solo i cron che girano **via `cron-agent.sh exec <name> <script>`** (come `nlm-nb1-daily-refresh`) aggiornano `lastRunAtMs` nel gateway, perché `cron-agent.sh` fa da ponte.
4. Risultato: gateway replica sul disco `.last.json` con timestamp sempre vecchio, ma `mtime` fresh perché il gateway stesso riscrive ogni 5 min.

Questa è la forma operativa del pattern "self-repair cieco" già documentato nella lesson del 2026-04-19: il monitoring vede `mtime` fresh e conclude "OK", ma il contenuto è stale da 10 giorni.

## Conferme di supporto

- **File aggiornati ogni 5 min su tutti i job** (non solo NLM): `core_guardian.last.json`, `daily_ops.last.json`, `compliance_ops.last.json` → 60+ file con stesso tick. Conferma che il writer è unico e sistematico.
- **`nlm_nb1_daily_refresh.last.json` è il solo file scritto DUE volte** (prima dallo script Python con ts reale, poi sovrascritto dal gateway con ts da jobs.json). Da verificare se c'è race — probabilmente no perché gateway usa atomic rename. Ma la semantica è confusa.
- **Contenuto `heartbeat_nb2_pipeline.json`** (scritto dal `heartbeat_monitor.py` ARCH-9): `{"pipeline":"nb2_pipeline","last_success":"2026-04-03T13:35:49..."}`. Ferma al 3 aprile! Il heartbeat_monitor è la fonte **di verità vera** per NB-2, ma nessuno la legge.

## Tre bug in uno

1. **Gateway `source_of_truth drift`**: gateway scrive `.last.json` con ts da `jobs.json` che è stale.
2. **Sentinel trusts wrong source**: sentinel legge `.last.json` (proiezione gateway) invece di `heartbeat_{name}.json` (ARCH-9 nativo).
3. **Pipeline script non aggiornano openclaw**: `run_nbN_pipeline.sh` non chiama `cron-agent.sh` né notifica gateway → `jobs.json` resta ignorante.

## Fix proposto (non applicato in questa sessione)

### Short-term (cosmetico ma safe)
- Al successo, `run_nbN_pipeline.sh` chiama `heartbeat_monitor.py --record nbN_pipeline` (già previsto nel wrapper NB-2, verifica su altri).
- Il `nuzantara-sentinel.py` legge `heartbeat_{name}.json` come primary source e `.last.json` come fallback. Piccola patch di 10 righe in `collect_state_files()`.

### Medium-term (architettonico)
- Deprecare scrittura `.last.json` da openclaw-gateway (è una proiezione, non heartbeat). Conservare solo `jobs.json` interno.
- Consolidare tutti gli heartbeat verso `heartbeat_{name}.json` (ARCH-9).
- Nuzantara-sentinel legge SOLO heartbeat ARCH-9.

### Long-term (allineato piano v2 Sprint 1)
- `freshness_monitor.py` estende heartbeat con UUID ingestion test (S1.2).
- Oracle gate su stale → rifiuta query su NB non fresh (S1.3).

## Decisione

**S0.2 è diagnosticato ma NON fixato in questa sessione.** Il fix richiede modifiche a 3 componenti: `nuzantara-sentinel.py` (preferire heartbeat ARCH-9), gli 8 wrapper `run_nbN_pipeline.sh` (chiamare heartbeat_monitor --record), possibile deprecation del path `.last.json` dal gateway (ma gateway è upstream Node binary, non editabile).

È lavoro da Sprint 1 concentrato, non da coda di Sprint 0. Ticket aperto: **T16 fix sentinel to prefer ARCH-9 heartbeat**.
