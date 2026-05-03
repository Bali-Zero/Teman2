# Observability — MCP workflow chains

The nuzantara-mcp server runs eight deterministic workflow chains (see
`apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py`). Before this document,
a failed chain was visible only in the LAM episodic memory and in local logs —
no dashboard, no alert, no historical baseline. This directory closes that gap
with the minimum surface needed to spot regressions and size chain timeouts.

## What we export

The MCP process emits four Prometheus-shaped series via
`prometheus_client`, written to a shared textfile:

| Metric                      | Type      | Labels                      | Semantics                                                                |
| --------------------------- | --------- | --------------------------- | ------------------------------------------------------------------------ |
| `chain_runs_total`          | Counter   | `chain`, `status`           | One increment per chain completion. `status ∈ {success, partial, exception}` |
| `chain_duration_seconds`    | Histogram | `chain`, `status`           | Wall-clock duration per run, bucketed 0.1s..300s                         |
| `chain_steps_total`         | Counter   | `chain`, `status`           | One increment per step within a chain run                                |
| `chain_step_errors_total`   | Counter   | `chain`, `step`, `error_type` | Only emitted when a step's `status == "error"`; error text bucketed to ≤10 values |

All labels are cardinality-bounded:

- `chain` — 8 values (fixed chain names)
- `step` — ~15 step names per chain, declared in the chain source
- `status` — `ok`, `error`, `skipped` for steps; `success`, `partial`, `exception` for runs
- `error_type` — 8 bucketed buckets (`timeout`, `network`, `not_found`, `auth`, `server_error`, `validation`, `other`, `unknown`)

Error arguments are **never** used as labels or values — they often carry
CRM/OSINT data and would both explode cardinality and violate Legge 2.

## How the data reaches Grafana

MCP is stdio-only — we cannot host a `/metrics` endpoint the way FastAPI
would. Instead we dump the registry atomically to a textfile on every chain
run, and a sidecar scrapes that file:

```
   ┌────────────────┐
   │ nuzantara-mcp  │ ── writes ──► $NUZANTARA_MCP_METRICS_PATH (default:
   │  (stdio only)  │               ~/.nuzantara/metrics/chains.prom)
   └────────────────┘                             │
                                                  ▼
                                       ┌────────────────────┐
                                       │  Grafana Agent     │ (or
                                       │  node_exporter     │ `node_exporter
                                       │  --textfile dir=…  │  --collector.textfile`)
                                       └──────────┬─────────┘
                                                  │
                                                  ▼
                                       ┌────────────────────┐
                                       │     Prometheus     │
                                       └──────────┬─────────┘
                                                  │
                                                  ▼
                                       ┌────────────────────┐
                                       │      Grafana       │
                                       └────────────────────┘
```

The textfile path is overridable via `NUZANTARA_MCP_METRICS_PATH`. The file
is rewritten on every chain completion (`_reflect_and_save` hook) so scrape
intervals of 15-30s see the latest snapshot.

## Setup — Grafana Agent sidecar

If you already run Grafana Agent on the Pro, add a scrape target:

```yaml
# /etc/grafana-agent.yaml
integrations:
  prometheus_remote_write:
    - url: https://prometheus.example/api/v1/write
  node_exporter:
    textfile_directory: /Users/nuzantara/.nuzantara/metrics
    enabled: true
```

If you run Prometheus directly, point the textfile collector at the same
directory — the file's `.prom` extension is enough for node_exporter to pick
it up.

## Importing the dashboard

1. Open Grafana → Dashboards → New → Import.
2. Upload `grafana-chains.json`.
3. Select the Prometheus data source that scrapes the textfile.
4. The dashboard variable `chain` lets you filter to a single chain or leave
   on "All".

The dashboard ships with four panels:

1. **Chain run rate (per minute)** — baseline traffic, split by outcome.
2. **Chain error rate** — `partial+exception / total`. Crosses 0.1 → investigate; 0.3 → page.
3. **Chain duration p95** — histogram quantile per chain. Feeds timeout sizing.
4. **Step-level errors** — table sorted by error count, grouped by `(chain, step, error_type)`.

## Initial baseline (fill after one week of runs)

| Chain                             | Expected runs/day | p95 duration | p99 duration | Error rate |
| --------------------------------- | ----------------- | ------------ | ------------ | ---------- |
| `chain_daily_ops_autopilot`       | 1                 | TBD          | TBD          | TBD        |
| `chain_new_client_onboarding`     | 0–10 (on-demand)  | TBD          | TBD          | TBD        |
| `chain_practice_lifecycle_check`  | 1                 | TBD          | TBD          | TBD        |
| `chain_intel_pipeline`            | 1 (03:00 WITA)    | TBD          | TBD          | TBD        |
| `chain_weekly_report`             | 1 (Mon)           | TBD          | TBD          | TBD        |
| `chain_client_health_monitor`     | 4                 | TBD          | TBD          | TBD        |
| `chain_compliance_autopilot`      | 1                 | TBD          | TBD          | TBD        |
| `chain_journey_accelerator`       | On-demand         | TBD          | TBD          | TBD        |

Fill these in after the first week. Once the table is live, the dashboard
serves its purpose: the next regression shows up as a number that does not
match the baseline, not as a post-hoc discovery in the LAM log.

## Extending the dashboard

The four panels are the observability floor, not the ceiling. Once a chain
runs repeatedly enough to establish a baseline, add:

- **Per-step latency heatmap** — requires emitting `chain_step_duration_seconds`;
  that depends on each chain adopting the `track_chain` context manager which
  today only wraps the reflection hook.
- **Anomaly alerts** — Alertmanager rules on `error rate > baseline + 2σ`.
- **Cross-chain correlation** — Alloy or Grafana's Explore to correlate a
  chain error spike with upstream dependency latency (Qdrant, Postgres).

## Code references

- Metrics module: `apps/nuzantara-mcp/nuzantara_mcp/workflows/metrics.py`
- Reflection hook (emission point): `apps/nuzantara-mcp/nuzantara_mcp/workflows/chains.py` (`_reflect_and_save`)
- Tests: `apps/nuzantara-mcp/tests/test_chain_metrics.py`
