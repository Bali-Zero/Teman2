# admin-dashboard-local

Pro-only operator dashboard. **Not deployed anywhere.**

- No Vercel config
- No Fly config
- `next.config.mjs` refuses to start unless `LOCAL_ONLY=1`
- every start command binds explicitly to `127.0.0.1:3100`
- Host validation is DNS-rebinding/origin hygiene; loopback socket binding is
  the actual network-isolation boundary
- owner surfaces use an expiring, exact-origin HMAC-signed Bearer token
  established by a high-entropy passphrase; the token exists only in React
  memory, so refresh deliberately relocks the surface
- DB-backed widgets read Postgres directly (local socket) or via a Fly tunnel
  (port 15432); GARUDA preview and login do not require a database

## Start

Run the canonical development launcher on Pro:

```bash
bash scripts/start-cockpit.sh
```

That activates `LOCAL_ONLY=1` and runs Next with webpack on the loopback socket
only. Configure the passphrase first with
`bash scripts/setup-cockpit-pin.sh`.

From the thin-client machine, keep the local and Pro ports identical:

```bash
ssh -M -S /tmp/garuda-internal-web.sock -fnNT \
  -L 127.0.0.1:3100:127.0.0.1:3100 \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  pro
```

Open `http://localhost:3100/garuda-voa` as the canonical browser URL. The
server permits loopback host variants (`localhost`, `127.0.0.1`, and `::1`),
but each cockpit-session token has an exact-origin audience: use the same
host and port that minted it. The socket intentionally binds to `127.0.0.1`.
Use `http://127.0.0.1:3100/garuda-voa` only as an explicit loopback
alternative, with a token minted for that exact origin. This does not
authorize a non-loopback origin.

For a local production-mode verification, from this directory:

```bash
LOCAL_ONLY=1 npm run build

LOCAL_ONLY=1 \
COCKPIT_REPO_ROOT="$(git rev-parse --show-toplevel)" \
COCKPIT_HMAC_KEY="$(<"$HOME/.config/zantara-cockpit/hmac.key")" \
COCKPIT_SESSION_KEY="$(<"$HOME/.config/zantara-cockpit/session.key")" \
npm run start
```

This remains a loopback-only local verification; it is not a deployment
procedure. GARUDA preview/login remain available without a database, while
DB-backed widgets still require their documented local connection.

## GARUDA VOA internal preview

`http://localhost:3100/garuda-voa` is an owner-only synthetic-data workbench.
Its same-origin API invokes the real Python GARUDA engine through a fixed
`execFile` module adapter. It never uploads, pays, writes CRM/portal data,
persists a GARUDA case payload, emits analytics, or sends anything externally.
Authentication and rate limiting are memory-only and perform no database
writes. The launcher derives `COCKPIT_REPO_ROOT` from the Git worktree that
contains the launcher; an environment or `.env` value cannot redirect it to a
sibling checkout. The Python child uses an absolute backend `PYTHONPATH` and a
fixed GARUDA cwd that is rejected if it contains a `.env` file.

## Data source

`app/lib/db.ts` chooses `DATABASE_URL_LOCAL` first; if missing, falls back
to `FLY_TUNNEL_URL`. If neither is set, the launcher prints a warning and
DB-backed routes remain unavailable until one is configured.

`setup-cockpit-pin.sh` preserves `hmac.key` for existing audit-chain records
and rotates the separate `session.key` whenever the passphrase is set or
changed. Both keys are file-backed with mode `0600`; neither can be overridden
by the optional app `.env` during launcher startup.

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
