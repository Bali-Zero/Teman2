# OSINT Anomaly Scan — Runbook

Operator-facing guide for running the anomaly scan, interpreting the
output, and tuning the thresholds. This is local-only tooling — see
`feedback_osint_blindato.md`.

## Pre-flight

Before the first run:

1. **Confirm Neo4j is local.** The CLI refuses any non-local URI
   unless you pass `--allow-remote`. Tailscale CGNAT (`100.x.x.x`) is
   allowed; anything else is not.

   ```
   echo $NEO4J_URI
   # Expected: bolt://localhost:17687 (or bolt://100.x.x.x:7687 on Tailscale)
   ```

2. **Confirm the graph has data.** Run:

   ```
   cypher-shell -a $NEO4J_URI -u $NEO4J_USER -p $NEO4J_PASSWORD \
     "MATCH (n) RETURN count(n) AS node_count"
   ```

3. **Confirm GDS plugin is installed.** The detectors use
   `gds.graph.project.cypher`, `gds.louvain`, `gds.articulationPoints`,
   and `gds.eigenvector`. All require GDS 2.5+.

   ```
   cypher-shell -a $NEO4J_URI -u $NEO4J_USER -p $NEO4J_PASSWORD \
     "RETURN gds.version() AS version"
   ```

## Running a scan

**Default (all detectors, default thresholds):**

```
cd apps/osint-nexus
PYTHONPATH=. python scripts/run_anomaly_scan.py
```

**With custom thresholds:**

```
PYTHONPATH=. python scripts/run_anomaly_scan.py \
  --config config/anomaly_thresholds.yaml
```

**Single detector:**

```
PYTHONPATH=. python scripts/run_anomaly_scan.py \
  --detector bridge_outlier
```

**Dry run (no session opened, good for CI):**

```
PYTHONPATH=. python scripts/run_anomaly_scan.py --dry-run
```

**Write output to a file:**

```
PYTHONPATH=. python scripts/run_anomaly_scan.py \
  --output /tmp/anomaly-$(date +%F).json
```

## Output shape

```json
{
  "count": 3,
  "alerts": [
    {
      "alert_id": "a1b2c3d4e5f60718",
      "pattern": "bridge_outlier",
      "primary_entity_id": "4:abc123:42",
      "score": 0.87,
      "confidence": 0.7,
      "evidence_path": ["4:abc123:42", "4:abc123:13", "4:abc123:55"],
      "rationale_id": "BO-CUT-BETWEEN-COMMUNITIES",
      "created_at": "2026-04-11T12:34:56+00:00"
    }
  ]
}
```

**Ranking.** Alerts are sorted by `score` descending, tie-broken by
`alert_id` ascending. Same-day re-runs produce identical IDs so
downstream systems can dedupe trivially.

**No names.** The output contains only opaque Neo4j element IDs. To
resolve names, run the Zero-only resolver in a separate process:

```
PYTHONPATH=. python osint_nexus/resolver/entity_resolver.py \
  --from /tmp/anomaly-$(date +%F).json
```

(This resolver exists elsewhere in the codebase and is **not**
invoked by `run_anomaly_scan.py` on purpose — separation of concerns
keeps the scanner safe to log.)

## Interpreting alerts

| `pattern`            | Read it as                                             |
| -------------------- | ------------------------------------------------------ |
| `centrality_jump`    | "This node's neighborhood grew unusually fast."        |
| `bridge_outlier`     | "This node is the ONLY bridge between two factions."   |
| `temporal_burst`     | "This edge class spiked above baseline in one week."   |
| `angkatan_disjoint`  | "Two cross-cohort officials are suspiciously close."   |
| `eigenvector_reverse`| "This hub knows nobody else important (lone handler)." |

**Score bands** (across all patterns):

- **0.85 – 1.00** — Review same day. Probable real signal.
- **0.70 – 0.85** — Review within the week.
- **0.60 – 0.70** — Background noise unless correlated with another
  detector on the same entity.
- **< 0.60** — Default `min_score` gates suppress these.

**Confidence** is separate from score. It reflects *data quality* for
the alert:

- High confidence (>0.8): large evidence path, dense local graph,
  abundant historical data.
- Low confidence (<0.4): sparse graph, few neighbors, short history.
  Treat the alert as "interesting hypothesis, not actionable".

## Tuning thresholds

Edit `config/anomaly_thresholds.yaml`. Reload on next run — no restart
needed.

**Guidelines:**

1. **Default to precision.** Lower thresholds produce more alerts but
   mostly garbage. An analyst reviews every alert by hand.
2. **Change one parameter at a time.** Run the scan, review 10 top
   alerts, adjust, re-run. Do not batch-tune.
3. **Never edit defaults in `thresholds.py`.** Put overrides in the
   YAML. The defaults are a safe baseline for new machines.
4. **For dev/test graphs**, lower `min_score` to 0.4 and
   `min_community_size` / `min_neighbors` to 2 so the detectors fire
   on synthetic data. DO NOT ship those settings to production.

## Operational safety (OPSEC)

1. **Never run with `--allow-remote` against a shared cloud Neo4j.**
   OSINT data is Zero-only.
2. **Never pipe the JSON output to a remote sink** (Telegram, Slack,
   email, cloud). Write to a local file. Resolve to names on the same
   machine, still locally. Publish nothing.
3. **Never add `n.name` to a detector RETURN clause.** If you need
   to, you are resolving, not detecting — use the separate resolver.
4. **Never log the full `evidence_path`** at `INFO` level. Use
   `DEBUG` only and strip it in aggregation sinks.
5. **Clean up GDS projections** after a scan. The detectors do this
   automatically on success, but crashed runs may leave stale
   projections:

   ```
   cypher-shell -a $NEO4J_URI -u $NEO4J_USER -p $NEO4J_PASSWORD \
     "CALL gds.graph.list() YIELD graphName RETURN graphName"
   # For each anomaly_* projection:
   cypher-shell ... "CALL gds.graph.drop('anomaly_bridge', false)"
   ```

## Troubleshooting

**"refusing to run against non-local NEO4J_URI"**
→ Set `NEO4J_URI=bolt://localhost:17687` or pass `--allow-remote`.

**"neo4j driver not installed"**
→ `pip install "neo4j>=5.20"` in the active venv.

**"dry-run ok (session not opened)"**
→ You passed `--dry-run`. Drop the flag to actually scan.

**Empty alert list on a non-empty graph**
→ Either the thresholds are too strict (try lowering `min_score` to
  0.4 as a sanity check) or the graph has no `Official.angkatan` /
  GDS plugin missing / no edges with `updated_at`. Check each detector
  in isolation via `--detector NAME`.

**GDS error "graph already exists"**
→ A previous scan crashed. Run the cleanup Cypher above and retry.

## Testing

```
cd apps/osint-nexus
PYTHONPATH=. pytest tests/anomaly -q
```

All tests run against a hermetic `FakeSession` — no Neo4j required.
Live-tier tests are marked `@pytest.mark.neo4j` and only run if
`NEO4J_URL` is set.

```
NEO4J_URL=bolt://localhost:17687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=osint-nexus-2026 \
PYTHONPATH=. pytest tests/anomaly -q -m neo4j
```

## Follow-up

The `centrality_jump` detector currently uses a structural proxy
(recent-edge mass) because the graph has no true temporal snapshots.
A proper implementation would require:

1. Snapshot the graph on a cadence (daily projection dump into
   SQLite or Parquet).
2. Run Betweenness / PageRank on each snapshot.
3. Compare per-node deltas across snapshots.

This is a follow-up item; it would increase signal quality for
`centrality_jump` without changing the other four detectors.
