# wa-dashboard-m1 — Bali Zero WhatsApp 3-column read-only dashboard

Replica del pattern M1 single-page (`~/bin/wa-viewer/`) puntata al DB di produzione
(Fly Postgres `nuzantara-postgres.flycast`) via il proxy locale `fly-pg-proxy` su
`127.0.0.1:15432`. Read-only: zero INSERT/UPDATE.

## Layout

- **Col 1**: 9 team Bali Zero da `~/.wa-mirror.accounts.json`
- **Col 2**: Conversazioni del team selezionato (direct + group), ordinate per ultimo msg
- **Col 3**: Messaggi della conversazione selezionata, ordine cronologico ASC, day dividers

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
- `PORT`, `HOST`

## Endpoint

| URL | Output |
|---|---|
| `GET /` | viewer.html |
| `GET /health.json` | `{ok, db_now, team_size, db_url_host}` |
| `GET /data.json` | overview teams + convs (5s cache) |
| `GET /thread.json?member=<phone>&conv=<key>` | 500 messaggi conv |
| `GET /metrics.json?window=<days>` | aggregati qualità per operatore (live, cache 60s) |
| `GET /metrics-history.json?days=<n>` | trend storico da `wa_team_daily_metrics` |
| `POST /metrics-rollup?window=<days>` | snapshot giornaliero → UPSERT (idempotente per giorno) |

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
