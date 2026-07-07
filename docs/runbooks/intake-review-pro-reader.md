# Runbook — Intake-Review Pro Reader (Fix #1)

> **Status**: code shipped (reader app + LaunchAgent + Fly proxy split). The Cloudflare
> Tunnel + Fly secrets are **operator steps** — until they are set, the change is INERT
> (`/api/intake/review*` keeps falling back to the Fly `rag` process, which shows an empty
> queue). This runbook is how to turn it on.

## Why this exists

`kita.balizero.com/review` calls `GET /api/intake/review/queue`. On Fly the `api` process
proxies `/api/intake/review*` to the `rag` process, which reads the **Fly-managed Postgres**
where `intake_queue=0`. But the intake **worker runs on the Pro** and writes proposals ONLY
to the **local Pro Postgres `nuzantara_dev`** (`scripts/wa_media_pull_worker.py`,
`backend/services/intake/worker.py`). Producer (Pro) and consumer (Fly) read two different
physical DBs → the review queue was always empty for the team.

Fix #1 runs a **reader on the Pro** (where the data is) and points the Fly proxy at it over a
**Cloudflare Tunnel**.

## Law 2 (UU PDP) — the honest framing

The intake queue is PII (KTP/passport/akta/OCR/names). This fix does **NOT** persist that PII
on Fly Postgres or cache it at Cloudflare. The reader runs on the Pro; only **encrypted TLS
transit** passes through Fly + Cloudflare (which do not store it) on the way to the
authenticated browser — exactly how `crm/clients` already works. Every reader response carries
`Cache-Control: no-store, private` so no edge caches PII.

## Architecture

```
browser (adit, cookie JWT)
   │  https://kita.balizero.com/api/intake/review/queue
   ▼
Fly  api process ── rag_proxy.is_intake_review_route() exact match ──► get_intake_client()
   │                                                                    (httpx, tight 3/5s timeout)
   │   + CF-Access-Client-Id/Secret (service token)
   │   + forwards user Cookie/Authorization unchanged
   ▼
Cloudflare Tunnel  https://intake-review.balizero.com  (CF Access protected)
   ▼
Pro  cloudflared ──► http://127.0.0.1:18795
   ▼
Pro  intake_review_reader (uvicorn)
        HybridAuthMiddleware (same JWT_SECRET_KEY) → request.state.user → RBAC identical
        intake_review.router  → asyncpg pool → LOCAL nuzantara_dev
```

If the Pro is offline, the proxy maps every failure to an explicit **503 "intake review reader
offline"** within ~3-5s — it never hangs on the 300s RAG timeout and never DoS-es the rest of
the API.

## Components (in this PR)

| Path | Role |
|---|---|
| `apps/backend-rag/backend/app/intake_review_reader.py` | the reader app (HybridAuthMiddleware + intake_review router + no-store + /healthz) |
| `scripts/intake_review_reader_run.sh` | LaunchAgent wrapper — sources the 0600 env-file then execs uvicorn |
| `infra/launchagents/com.nuzantara.intake-review-reader.plist` | KeepAlive daemon, NO secrets in plist |
| `apps/backend-rag/backend/app/rag_proxy.py` | Fly proxy split — exact-boundary route to the intake target + 503 mapping |
| `apps/backend-rag/backend/tests/unit/app/test_rag_proxy_intake_split.py` | 9 proxy unit tests |

## Env-file (Pro) — `~/.cell-bridge-state/intake-review-reader.env` (chmod 0600)

Create it on the Pro, **NEVER commit it**. The wrapper refuses to start if the file is missing
or world-readable (mode must be 600 or 400). Keys:

```sh
JWT_SECRET_KEY=<the Fly JWT_SECRET_KEY secret — MUST match Fly so cookie/Bearer JWT validates>
API_KEYS=<any non-empty value; settings requires it, the reader is JWT-only in practice>
INTAKE_REVIEW_DATABASE_URL=postgresql://nuzantara@127.0.0.1:5432/nuzantara_dev
INTAKE_REVIEW_BRIDGE_SECRET=<shared X-Bridge-Auth secret, also added by the Fly proxy (optional layer)>
```

Get the Fly `JWT_SECRET_KEY`:

```sh
fly secrets list -a nuzantara-rag            # confirms it exists (value is masked)
# value lives in the Fly secret store; copy it into the env-file out-of-band.
```

Then:

```sh
mkdir -p ~/.cell-bridge-state
$EDITOR ~/.cell-bridge-state/intake-review-reader.env
chmod 600 ~/.cell-bridge-state/intake-review-reader.env
```

## Cloudflare Tunnel (Pro)

The Pro's router is ISP-locked (no port-forward), so `cloudflared` makes an OUTBOUND
connection — zero open ports.

```sh
# 1. Install + login (once)
brew install cloudflared
cloudflared tunnel login                      # browser → authorise balizero.com zone

# 2. Create the tunnel
cloudflared tunnel create intake-review-pro
# note the tunnel UUID + credentials file path it prints

# 3. Route a hostname to it
cloudflared tunnel route dns intake-review-pro intake-review.balizero.com

# 4. config.yml (~/.cloudflared/config.yml)  — target MUST be 127.0.0.1 (IPv4), NOT localhost
cat > ~/.cloudflared/config.yml <<'CFG'
tunnel: <TUNNEL_UUID>
credentials-file: /Users/nuzantara/.cloudflared/<TUNNEL_UUID>.json
ingress:
  - hostname: intake-review.balizero.com
    service: http://127.0.0.1:18795
  - service: http_status:404
CFG

# 5. Run cloudflared as its own LaunchAgent (separate from this reader).
cloudflared tunnel run intake-review-pro
```

### Cloudflare Access (service token)

Protect `intake-review.balizero.com` with a **Cloudflare Access** application + a
**Service Token**. The Fly proxy presents the token via `CF-Access-Client-Id` /
`CF-Access-Client-Secret`. Create the service token in the Cloudflare Zero Trust dashboard
(Access → Service Auth → Service Tokens), scope the Access app to that token, and **disable
caching** on the hostname (the reader already sends `no-store`, this is belt-and-suspenders).

## Install the reader LaunchAgent (Pro)

```sh
cp infra/launchagents/com.nuzantara.intake-review-reader.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.nuzantara.intake-review-reader.plist
launchctl kickstart -k gui/$(id -u)/com.nuzantara.intake-review-reader
# verify
curl -fsS http://127.0.0.1:18795/healthz        # → {"status":"ok","db":true,"jwt":true}
tail -f ~/logs/intake-review-reader.log
```

## Fly secrets (operator)

```sh
fly secrets set -a nuzantara-rag \
  INTAKE_REVIEW_WORKER_URL=https://intake-review.balizero.com \
  CF_ACCESS_CLIENT_ID=<service-token-id> \
  CF_ACCESS_CLIENT_SECRET=<service-token-secret>
```

Setting `INTAKE_REVIEW_WORKER_URL` is the switch that activates the split. Unset/empty → the
proxy falls back to the RAG process (current behaviour).

## E2E acceptance test

1. **adit (non-admin)** logs into `kita.balizero.com`, opens `/review`:
   `GET /api/intake/review/queue` → **his ~12 items** (`received_by='adit@balizero.com'`), not 0.
2. **admin (asya/zero)** → the full queue (~89 items).
3. **Pro reader stopped** (`launchctl kill TERM …`): `/review` returns **503 "intake review
   reader offline"** within ~5s, and the rest of the API (e.g. `/api/crm/clients`) is unaffected.
4. **claim/approve/reject** work end-to-end. With `INTAKE_WRITER_ENABLED=0` (forced by the
   wrapper) approvals are **dry-run** — no CRM write.
5. `/api/intake/review-metrics` (if/when added) and `/api/intake/gate` are NOT routed to the Pro
   tunnel (they stay on Fly).

## Kill switch / rollback

- Disable the split without redeploy: `fly secrets unset -a nuzantara-rag INTAKE_REVIEW_WORKER_URL`
  → proxy reverts to the RAG process immediately.
- Stop the reader: `launchctl bootout gui/$(id -u)/com.nuzantara.intake-review-reader`.

## Scars referenced

- **W65 / 2026-04-29 plist-secret-644**: no secret in the plist — wrapper sources a 0600 env-file.
- **Law 2 / UU PDP**: PII reader runs on the Pro; no persistence on Fly/CF; encrypted transit only.
