# Admin Dashboard — Bali Zero Kita

Local-only Next.js dashboard to inspect and control Nuzantara data. Runs on port 3002 via `start_dashboard.sh`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string. Points at `localhost:15432`, the tunnel `start_dashboard.sh` opens. |
| `BACKEND_URL` | — | Backend API base, used by the portal-invite routes. Defaults to `http://localhost:8000` if unset. |
| `AUTONOMOUS_LAB_BACKEND_URL` | — | Backend base for the autonomous-lab views only. |

## Running

```bash
./start_dashboard.sh   # opens the Postgres + Qdrant fly proxies, then serves on port 3002
```

## Access

`middleware.ts` is the access boundary and it covers `/api/*` too: it verifies the
`nz_access_token` JWT and requires `role ∈ {admin, super_admin, owner}`. The one
exception is local dev — requests to `localhost` with `NODE_ENV !== "production"`
skip the check entirely, which is the normal way this dashboard is used.
