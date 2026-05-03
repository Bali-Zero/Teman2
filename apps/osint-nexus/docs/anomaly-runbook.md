# Anomaly Scan Runbook

How to run, interpret, and tune the OSINT Nexus anomaly detection system.

## Prerequisites

- Python 3.11+
- `neo4j` driver installed (`pip install neo4j`)
- Local Neo4j instance running (default: `bolt://localhost:17687`)
- Optional: Neo4j GDS plugin for Louvain and eigenvector (detectors fall back to Cypher without it)
- Optional: `pyyaml` for custom threshold config files

## Running a Scan

### Quick scan (all detectors, default thresholds)
```bash
cd apps/osint-nexus
python scripts/run_anomaly_scan.py
```

### With custom thresholds
```bash
python scripts/run_anomaly_scan.py --config path/to/thresholds.yaml
```

### Output to file
```bash
python scripts/run_anomaly_scan.py --output alerts.json
```

### Specific detectors only
```bash
python scripts/run_anomaly_scan.py --detectors centrality_jump,temporal_burst
```

### Custom Neo4j connection
```bash
NEO4J_URI=bolt://localhost:7687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=secret \
python scripts/run_anomaly_scan.py
```

## Interpreting Results

### Alert Structure
```json
{
    "id": "a1b2c3d4e5f6",
    "pattern": "centrality_jump",
    "score": 0.82,
    "confidence": 0.65,
    "evidence_path": ["node:4:abc123"],
    "explanation": "Node 4:abc123 has 8/10 edges (80%) created in last 30d",
    "detected_at": "2026-04-11T08:30:00+00:00",
    "meta": {
        "total_degree": 10,
        "recent_edges": 8,
        "recent_fraction": 0.8,
        "window_days": 30
    }
}
```

### Score × Confidence Matrix
| Score | Confidence | Priority | Action |
|-------|-----------|----------|--------|
| >0.7 | >0.7 | **CRITICAL** | Investigate immediately |
| >0.5 | >0.5 | HIGH | Review within 24h |
| >0.3 | >0.3 | MEDIUM | Queue for analysis |
| <0.3 | any | LOW | Log for pattern tracking |

### Per-Pattern Interpretation

**centrality_jump**: Check if the node is a real person gaining influence or a data entry artifact. Cross-reference with recent scraper runs.

**bridge_outlier**: Map the communities on each side. Are they different Kanim offices? Different angkatan clusters? The bridge type determines intelligence value.

**temporal_burst**: Check the burst date against known events (Pilkada, mutasi announcements, national holidays). Scraper backfills produce false positives.

**angkatan_disjoint_alliance**: The highest-signal detector. A 2-hop path via MARRIED_TO between officials of different angkatan is almost certainly significant. Verify angkatan values are correct (data quality check).

**eigenvector_reverse**: Map the hub's neighborhood. Are the low-centrality neighbors all in the same office? If yes, it may be a normal supervisor. If they span offices, it's worth investigating.

## Tuning Thresholds

### Config file format (YAML)
```yaml
centrality_jump:
  window_days: 30
  recent_edge_fraction_threshold: 0.40
  min_degree: 5
  min_recent_edges: 3

bridge_outlier:
  min_community_size: 3
  bridge_score_threshold: 0.5

temporal_burst:
  window_days: 7
  ewma_span_days: 30
  z_threshold: 3.0
  min_baseline_days: 14
  edge_types:
    - MET_WITH
    - ATTENDED
    - WON_CONTRACT
    - PROMOTED_TO
    - POSTED_TO

angkatan_disjoint_alliance:
  max_path_length: 3
  min_angkatan_gap: 1
  non_official_edge_types:
    - MARRIED_TO
    - PARENT_OF
    - SIBLING_OF
    - PATRON_OF
    - KNOWS
    - FREQUENTS
    - MEMBER_OF

eigenvector_reverse:
  top_percentile: 0.10
  neighbor_max_percentile: 0.25
  min_neighbors: 2
```

### Tuning Guidelines

1. **Too many alerts?** Raise thresholds:
   - `recent_edge_fraction_threshold` → 0.60
   - `z_threshold` → 4.0
   - `bridge_score_threshold` → 0.8
   - `min_angkatan_gap` → 3

2. **Too few alerts?** Lower thresholds:
   - `recent_edge_fraction_threshold` → 0.30
   - `z_threshold` → 2.5
   - `min_degree` → 3

3. **False positives from data entry?** Add scraper timestamps to edge properties and increase `min_baseline_days`.

4. **Missing GDS?** Detectors automatically fall back to pure Cypher. Results may differ slightly from GDS-powered analysis.

## Running Tests

```bash
# Unit tests (no Neo4j required)
cd apps/osint-nexus
python -m pytest tests/anomaly/ -v

# Integration tests (requires live Neo4j)
NEO4J_TEST_URI=bolt://localhost:17687 python -m pytest tests/anomaly/ -v -m neo4j
```

## OPSEC Reminders

- Alerts expose ONLY Neo4j element IDs — never entity names
- Resolve IDs to names only through the separate access-controlled resolve step
- Never log, export, or transmit alert data to external systems
- Keep threshold configs local — they reveal intelligence priorities
- All scans run locally on Pro/Air — never on cloud infrastructure
