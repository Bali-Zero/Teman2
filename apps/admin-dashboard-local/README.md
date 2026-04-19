# admin-dashboard-local

Pro-only LLM cost dashboard. **Not deployed anywhere.**

- No Vercel config
- No Fly config
- `next.config.mjs` refuses to start unless `LOCAL_ONLY=1`
- Reads Postgres directly (local socket) or via Fly tunnel (port 15432)

## Start

```bash
bash scripts/start-cost-dashboard.sh
```

That activates `LOCAL_ONLY=1`, runs `next dev -p 3100`, and opens
`http://localhost:3100/cost-dashboard` in your default browser.

## Data source

`app/lib/db.ts` chooses `DATABASE_URL_LOCAL` first; if missing, falls back
to `FLY_TUNNEL_URL`. If neither is set, startup fails with a clear error.

## What it shows

6 widgets at `/cost-dashboard`:

- **KPI cards** — today / last 7d / last 30d spend
- **Timeline** — daily cost, stacked by provider (last 30d)
- **Top endpoints** — top 10 by total cost (last 7d)
- **Model mix** — input tokens by provider (last 7d)
- **Recommendations panel** — pending `llm_cost_recommendations` (migration 119), with "mark reviewed" button
- **Anomaly banner** — red banner if any pending `spike_flag=true`

All SQL is read-only except `PATCH /api/llm-costs/recommendations/:id`
which updates the single row `status='reviewed'`.
