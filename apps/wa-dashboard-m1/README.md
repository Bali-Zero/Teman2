# wa-dashboard-m1 — Bali Zero WhatsApp local read-only webapp

Replica del pattern M1 single-page (`~/bin/wa-viewer/`) puntata al DB di produzione
(Fly Postgres `nuzantara-postgres.flycast`) via il proxy locale `fly-pg-proxy` su
`127.0.0.1:15432`. Read-only: zero INSERT/UPDATE.

## Layout

- **Conversazioni live**: 3 colonne WhatsApp-style, con team, thread e messaggi in read-only.
- **Zantara risolve**: vista shadow del caso selezionato: segnali letti, diagnosi, next best action, bozza e gate umano.
- **Training academy**: indice human-readable degli artefatti Zantara Client/Team/Owner Captain già generati e futuri.
- **Team**: metriche aggregate per operatore, senza testo raw o PII esposta.

## Run locale

```bash
cd apps/wa-dashboard-m1
npm install
npm run dev       # PORT=7790
open http://127.0.0.1:7790
```

Variabili env opzionali:
- `WA_DASHBOARD_DATABASE_URL` (default: pg-proxy localhost:15432 → Fly DB)
- `WA_MIRROR_ACCOUNTS_JSON` (default: `~/.wa-mirror.accounts.json`)
- `WA_TRAINING_CORPUS_DIR` (default: `../../research/personal/wa-corpus`)
- `PORT`, `HOST`

## Endpoint

| URL | Output |
|---|---|
| `GET /` | viewer.html |
| `GET /health.json` | `{ok, status, db_ok, db_now, db_error, team_size, db_url_host}` |
| `GET /data.json` | overview teams + convs (5s cache); degraded shell if DB is unavailable |
| `GET /training.json` | local training/shadow summary index from Markdown summaries only |
| `GET /thread.json?member=<phone>&conv=<key>` | 500 messaggi conv |
| `GET /metrics.json?window=<days>` | aggregati qualità per operatore (live, cache 60s) |
| `GET /metrics-history.json?days=<n>` | trend storico da `wa_team_daily_metrics` |
| `POST /metrics-rollup?window=<days>` | snapshot giornaliero → UPSERT (idempotente per giorno) |

## Zantara Training (tab "Training")

La terza vista legge in modo dinamico tutti i file `*_summary.md` sotto
`research/personal/wa-corpus`, quindi include sia i training già generati sia quelli
che verranno prodotti dai prossimi batch. Espone solo metriche e contratti dai
summary Markdown: non legge né mostra JSONL raw, SQLite, testo messaggi, telefoni,
email o ID caso.

La UI è costruita per capire a colpo d'occhio:

- cosa Zantara sta imparando: academy examples, replay scenarios, shadow drafts,
  owner approval signals, owner/team/client artifacts;
- quanto è pronta: conteggi aggregati per categoria e ultimi aggiornamenti;
- cosa non fa da sola: `whatsapp_sends=0`, `crm_mutations=0`, local-only,
  approval umano obbligatorio.

Il contratto operativo resta read-only/shadow: la dashboard non invia WhatsApp, non
scrive CRM, non muta training artifacts e non espone dati raw.

## Zantara Risolve

La vista "Zantara risolve" non chiama un modello e non inventa una soluzione:
traduce i segnali già presenti nella conversazione selezionata in una diagnosi
operativa leggibile. In local Pro mode può mostrare PII dentro la UI locale
perché non lascia la macchina. Per ogni caso mostra:

- tipo conversazione: cliente CRM, prospect/lead, gruppo cliente o thread interno;
- segnali disponibili: CRM match, owner operativo, priorità, unread, gruppo;
- contesto reale locale: ultimo inbound/outbound del thread caricato;
- ragionamento operativo: contesto, blocco probabile, decisione richiesta;
- prossima azione e bozza shadow;
- gate umano: invio WhatsApp e scritture CRM restano manuali.

La stessa carta appare anche sopra il thread nella tab "Conversazioni live", così
messaggi e ragionamento restano nello stesso punto di lavoro.
La PII resta ammessa nella UI locale, non nei commit, PR, report condivisi, log
lunghi o chiamate cloud.

## Modalità degradata

`/health.json` e `/data.json` non tornano più 500 quando Postgres locale è offline:
la webapp resta aperta, mostra il team shell e mantiene disponibile la tab Training.
Le conversazioni e le metriche live richiedono comunque che il DB locale/proxy torni
raggiungibile.

## Team Quality (tab "Qualità Team")

Seconda vista della dashboard (toggle in header). Metriche aggregate per operatore
calcolate da `whatsapp_message_context`, attribuite per `team_member_phone` + alias
(parità con le colonne conversazioni — NON per email), in `metrics.cjs`:

- volume (msg / in / out), clienti distinti, copertura (active days), lunghezza media outbound
- response latency p50/p90, % risposte < 5 min
- % outbound after-hours (fuori 8–18 WITA)
- backlog: thread con ultimo msg inbound fermo > 24h (palla al team)
- volume group-chat

Storicizzazione: `POST /metrics-rollup` scrive uno snapshot/giorno in
`wa_team_daily_metrics` (creata idempotente al boot via `ensureMetricsSchema`). Ogni
riga porta `metrics_schema_version` — bumpala quando cambi una formula, così il trend
confronta solo righe pari-versione (anti state-schema-drift, superscar #9). Tutto
aggregato, Pro-bound, zero PII. La parte qualitativa-LLM resta on-demand, fuori da qui.

Scheduler giornaliero: `scripts/launchd/com.balizero.wa-team-metrics-rollup.plist`
(StartCalendarInterval 06:30 WITA, **no** KeepAlive — è un cron, non un daemon;
anti superscar #7). Heartbeat reale = la riga scritta nel DB (`computed_at`).

## Cosa NON fa (al momento)

- ❌ Send messaggi (read-only)
- ❌ Live SSE (refresh polling ogni 10s)
- ❌ Auth (deve girare solo su localhost via firewall macOS)
- ❌ Group resolve membership/sender CRM linking (mostra `sender_phone` raw)

## Differenze vs `~/bin/wa-viewer/`

| | wa-viewer (port 7777) | wa-dashboard-m1 (port 7790) |
|---|---|---|
| DB target | `nuzantara_dev` locale | Fly DB via pg-proxy |
| Stato dati | static import una-tantum | live production |
| Build | inline cjs | inline cjs (stesso pattern) |
| Schema | proprio | sola lettura su prod schema |
| Group support | sì | sì (riusato pattern) |

## Pre-requisiti

- `fly-pg-proxy` LaunchAgent attivo: `nc -z 127.0.0.1 15432`
- Node 20+
- File `~/.wa-mirror.accounts.json` esistente

## Cicatrix

- 2026-05-25: shipped da `feat/wa-dashboard-m1-readonly-2026-05-25` (worktree isolato).
- DB Fly contiene 67 messaggi reali 23-24/05 (verificato), bridge wa-mirror locali scrivono lì.
- DB locale `nuzantara_dev` contiene solo dati di import storico + test M1 sintetici.
- **2026-06-16 (doc-drift corretto)**: il deployment Pro ATTUALE punta a `nuzantara_dev`
  LOCALE — verificato via `/health.json` (`db_url_host=127.0.0.1:5432`) + plist
  `WA_DASHBOARD_DATABASE_URL`, NON a Fly. Il mirror vivo del team ora scrive nel locale
  (`source='wa_mirror'` ~20k msg, aggiornato in giornata); su Fly resta un residuo di
  1872 msg fermo al 24/05. L'intro "Fly via pg-proxy 15432" e la riga `WA_DASHBOARD_DATABASE_URL`
  qui sopra sono storiche — il default operativo reale è il pg locale.
