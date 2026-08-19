# admin-dashboard-local

Pro-only operator dashboard. **Not deployed anywhere.**

- No Vercel config
- No Fly config
- `next.config.mjs` refuses to start unless `LOCAL_ONLY=1`
- every start command binds explicitly to `127.0.0.1:3100`
- Host validation is DNS-rebinding/origin hygiene; loopback socket binding is
  the actual network-isolation boundary
- owner surfaces use an expiring HMAC-signed Bearer token established by a
  high-entropy passphrase; the token exists only in React memory, so refresh
  deliberately relocks the surface
- Reads Postgres directly (local socket) or via Fly tunnel (port 15432)

## Start

```bash
bash scripts/start-cockpit.sh
```

That activates `LOCAL_ONLY=1` and runs Next on loopback only. Configure the
passphrase first with `bash scripts/setup-cockpit-pin.sh`.

## GARUDA VOA internal preview

`http://127.0.0.1:3100/garuda-voa` is an owner-only synthetic-data workbench.
Its same-origin API invokes the real Python GARUDA engine through a fixed
`execFile` module adapter. It never uploads, pays, writes CRM/portal data,
persists a GARUDA case payload, emits analytics, or sends anything externally.
Authentication attempts do create payload-free audit rows. The launcher
derives `COCKPIT_REPO_ROOT` from the Git worktree that contains the launcher;
an environment or `.env` value cannot redirect it to a sibling checkout.

## Data source

`app/lib/db.ts` chooses `DATABASE_URL_LOCAL` first; if missing, falls back
to `FLY_TUNNEL_URL`. If neither is set, the launcher prints a warning and
DB-backed routes remain unavailable until one is configured.

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
