# Runbook — Intel Lake pipeline (operatore non-dev)

> Pipeline OSINT: producer scraper → outbox → router → NotebookLM. Versione 2026-05-20 dopo Phase B+C+D del piano perfect-production.

## 1. Cosa controllare giornalmente (2 min)

Apri il dashboard `https://kita.balizero.com/admin/observability` (Pro-only). Cerca il pannello "Intel Lake":

| Spia             | Verde                    | Giallo                      | Rosso                          |
| ---------------- | ------------------------ | --------------------------- | ------------------------------ |
| outbox depth     | < 100 messaggi in coda   | 100-1000 — degrado, ma vivo | > 1000 — drain bloccato        |
| router activity  | ultimo classificato < 1h | 1-6h fa                     | > 6h fa — router morto         |
| nb-push activity | ultimo push < 12h        | 12-24h fa                   | > 24h fa — NotebookLM bloccato |
| probe last pass  | < 12h fa                 | 12-24h fa                   | > 24h fa o `FAILED`            |

Se tutto verde → **non fare nulla**. Il sistema sta lavorando.

## 2. Quando arriva alert Telegram

L'alert arriva al `TELEGRAM_PROBE_CHAT_ID` (canale dedicato, NON la tua chat owner). Tre formati:

| Alert                                       | Significato                        | Azione                      |
| ------------------------------------------- | ---------------------------------- | --------------------------- |
| `🔴 intel-lake e2e probe FAILED rc=N`       | Il probe sintetico è caduto        | Vedi §3 — fail-mode         |
| `⚠️ outbox-drain rejected N items`          | Backend ha rifiutato dati producer | Vedi `intel_lake_audit_log` |
| `🔴 intel-lake-router 3+ failures in 30min` | Router Pro-local crashato 3 volte  | Vedi §4 — router fail       |

**Cooldown**: ogni tipo di alert ha 30min cooldown — non spamma. Se vedi 1 solo alert in 30min e poi silenzio = il fix è stato applicato OR il problema si è autorisolto.

## 3. Fail-mode "intel-lake e2e probe FAILED"

```bash
# 1. Leggi gli ultimi 50 righe di log
tail -50 ~/logs/intel-lake-probe-cron.log

# 2. Identifica quale hop ha fallito
grep "hop[1-5]" ~/logs/intel-lake-probe-cron.log | tail -10
```

| Hop fallito  | Causa probabile                               | Azione                                                                                                |
| ------------ | --------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| hop1 POST    | Fly down / token rotato / proxy giù           | `curl -sf https://nuzantara-rag.fly.dev/health` — se 503 → Antonello                                  |
| hop2 outbox  | Trigger PG `notify_intel_lake_event` rotta    | Migration 146 controllo; chiedi ad Antonello                                                          |
| hop3 routing | Router Pro-local non gira                     | `launchctl print gui/$(id -u)/com.balizero.intel-lake-router.5min` — se `state ≠ running` → Antonello |
| hop4 nb-push | NB UUID `7e6ae978-...` cancellato dal sandbox | Ricrea via Antonello                                                                                  |
| hop5 cleanup | Probe rimosso a metà                          | Cleanup manuale: vedi `docs/runbooks/synthetic-probe-cleanup.md`                                      |

## 4. Router fail (3 crashi in 30min)

Antonello-only. Comandi:

```bash
# Re-bootstrap router
launchctl bootout gui/$(id -u)/com.balizero.intel-lake-router.5min
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.intel-lake-router.5min.plist

# Verifica
launchctl print gui/$(id -u)/com.balizero.intel-lake-router.5min | grep -E "state|last exit"
# Atteso: state = running, last exit code = 0
```

## 5. Rollback nuclear

Se TUTTO è rotto e devi fermare l'ingestion Intel Lake (per esempio: nuova regulation rivela leak PII):

```bash
# Stop tutti i 5 LaunchAgent Intel Lake
for label in intel-lake.outbox-drain.minute intel-lake-router.5min intel-lake-nb-pusher.5min intel-lake.e2e-probe.6h intel.nightly; do
    launchctl bootout gui/$(id -u)/com.balizero.${label} 2>/dev/null
done

# Conferma stop
launchctl list | grep balizero.intel-lake
# Atteso: lista vuota

# Stop probe pure
launchctl bootout gui/$(id -u)/com.balizero.intel-lake.e2e-probe.6h
launchctl bootout gui/$(id -u)/com.balizero.wr2.e2e-probe.daily
```

Backend Fly rimane su (`/health` continua a rispondere). Solo producer Pro-local sono fermi. Ri-attivazione: re-bootstrap singolarmente quando OK.

## 6. Riferimenti

- Endpoint: `GET https://nuzantara-rag.fly.dev/api/intel/health/pipeline`
- Plist cronici: `~/nuzantara/infra/launchagents/com.balizero.intel-lake.e2e-probe.6h.plist`
- Probe script: `~/nuzantara/scripts/probes/intel_lake_e2e_probe.py`
- Cleanup emergency: `docs/runbooks/synthetic-probe-cleanup.md`
- Cicatrici (cosa è andato storto in passato): `.claude/rules/cicatrix-scars.md`
