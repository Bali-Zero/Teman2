# SOTA Social dashboard — Grafana setup

One-time setup for the `SOTA Social — Loop 90gg Editorial KPIs` dashboard
(`infra/grafana/social-sota-dashboard.json`).

## Prerequisites

- Grafana 10+ instance reachable from Pro (recommended: self-hosted on the
  same network that reaches `nuzantara-postgres` over Tailscale).
- PostgreSQL datasource pointing at `nuzantara-postgres` with **read-only**
  credentials. The dashboard runs SELECT against `war_room_posts` and
  `m13_post_metrics` only.

## Step 1 — Create read-only PG role

```sql
-- Run as superuser on nuzantara-postgres
CREATE ROLE grafana_ro WITH LOGIN PASSWORD '<strong-random>';
GRANT CONNECT ON DATABASE nuzantara TO grafana_ro;
GRANT USAGE ON SCHEMA public TO grafana_ro;
GRANT SELECT ON war_room_posts, m13_post_metrics TO grafana_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO grafana_ro;
```

Store the password in `~/.nuzantara-secrets.env` as
`GRAFANA_PG_RO_PASSWORD=...` — the Grafana provisioning file below reads it
via `$GRAFANA_PG_RO_PASSWORD`.

## Step 2 — Provision datasource

`/etc/grafana/provisioning/datasources/nuzantara.yaml`:

```yaml
apiVersion: 1
datasources:
  - name: Postgres
    uid: nuzantara_postgres
    type: postgres
    access: proxy
    url: nuzantara-postgres.internal:5432
    user: grafana_ro
    database: nuzantara
    jsonData:
      sslmode: require
      postgresVersion: 1500
      timescaledb: false
    secureJsonData:
      password: $GRAFANA_PG_RO_PASSWORD
```

Restart Grafana: `systemctl restart grafana-server`.
Verify the uid matches `nuzantara_postgres` — the dashboard JSON references
this exact uid via the `${DS_POSTGRES}` template variable default.

## Step 3 — Import the dashboard

From the Grafana UI: `+ → Import → Upload JSON`, select
`infra/grafana/social-sota-dashboard.json`.

Alternative (provisioning file):

`/etc/grafana/provisioning/dashboards/sota.yaml`:

```yaml
apiVersion: 1
providers:
  - name: sota
    orgId: 1
    folder: SOTA
    type: file
    allowUiUpdates: false
    options:
      path: /var/lib/grafana/dashboards/sota
```

Copy `social-sota-dashboard.json` to
`/var/lib/grafana/dashboards/sota/` and restart. Dashboards provisioned
this way are read-only in the UI (edits must go through git).

## What each panel shows

| Panel | Source tables | What it answers |
|---|---|---|
| LEARN rate 7d | `m13_post_metrics + war_room_posts WHERE pillar='learn'` | Is education content still engaging? |
| LEAD rate 7d | same, `pillar='lead'` | Is the funnel still converting attention → DM/profile visit? |
| COMMUNITY rate 7d | same, `pillar='community'` | Is depth (replies + saves) holding? |
| Posting heatmap 30d | `war_room_posts.published_at` | Validates `06_cadence_engine.json` — are we posting at 07/12/19 WITA? |
| Top 10 last 7d | both, `LATERAL` latest metrics | Leaderboard — cross-check with M13 weekly report. |

Thresholds on LEARN panel follow `10_m13_measurer_config.md`:
- green ≥ 4%
- yellow 2–4%
- red < 2% (same band used by `scripts/m13_weekly_report.py` breach markers)

## Kill-switch coordination

When `wr2_publisher_enabled_<channel>` is flipped to `false` by the
Telegram `/publisher off <channel>` command (router
`/api/research/control/publisher`, Task 30), the LEARN/LEAD/COMMUNITY
panels will drop for that channel within the 5-minute refresh. Use the
Top-10 panel to identify which post triggered the breach.

## Troubleshooting

- **All panels empty at first import** — Loop must be running for at
  least 24h to populate `m13_post_metrics` (populated every 6h by
  `com.balizero.sota.m13-collect` launchagent).
- **Heatmap only shows a few cells** — Expected during Loop day 1–7.
  The 30-day window needs a month of data for full saturation.
- **LATERAL query slow on top-10** — Add index
  `CREATE INDEX IF NOT EXISTS ix_m13_pm_post_captured ON m13_post_metrics(post_id, captured_at DESC)`.
- **Datasource shows "unauthorized"** — re-check `grafana_ro` GRANTs
  (Step 1) and `$GRAFANA_PG_RO_PASSWORD` env var presence on the
  grafana-server process.

## Deploy checklist

- [ ] `grafana_ro` role created on nuzantara-postgres.
- [ ] `GRAFANA_PG_RO_PASSWORD` in `~/.nuzantara-secrets.env`.
- [ ] Datasource provisioned, uid = `nuzantara_postgres`.
- [ ] Dashboard imported, visible under folder `SOTA`.
- [ ] Refresh = 5m, Timezone = Asia/Makassar.
- [ ] Index `ix_m13_pm_post_captured` present (or ignored if table < 10k rows).
