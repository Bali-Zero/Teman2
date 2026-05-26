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
