# Admin Dashboard — Bali Zero Kita

Local-only ops dashboard. Runs on port 3002 via `start_dashboard.sh`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `BACKEND_URL` | ✅ | Backend API URL. Defaults to `https://nuzantara-rag.fly.dev` if unset. |

## Running

```bash
./start_dashboard.sh   # starts on port 3002 via fly proxy
```
