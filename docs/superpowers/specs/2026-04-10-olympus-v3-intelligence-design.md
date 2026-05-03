# Olympus v3 — Intelligence Layer Design

**Date:** 2026-04-10
**Status:** Approved
**Closes:** GAP-2, GAP-3 residual, GAP-5, GAP-6 from PostgreSQL production audit

## Context

Olympus v2 maintains the DB (vacuum, reindex, partitioning, feedback loop). v3 makes it **observable** by populating `olympus_insights` (table exists since migration 100, currently empty) with real intelligence and adding a composite Health Score to the heartbeat.

## Architecture

2 new files, 3 modified files. No new tables — migration 104 adds columns to `olympus_heartbeats`.

```
backend/services/olympus/
├── guardian.py          # MOD: wires InsightsCollector, health score
├── heartbeat.py         # MOD: +cache_hit, +table_sizes, +idx_ratio, +health_score
├── pulse.py             # MOD: +autovacuum_advisor, partition-aware cleanup
├── models.py            # MOD: +HeartbeatSnapshot fields, +InsightRecord model
├── insights.py          # NEW: Query Intelligence + Bloat Intelligence
├── rules_engine.py      # unchanged
├── alerts.py            # unchanged
```

## Migration 104

Adds columns to `olympus_heartbeats`:

| Column | Type | Default |
|---|---|---|
| `cache_hit_ratio` | NUMERIC(5,2) | NULL |
| `top_tables_by_size` | JSONB | NULL |
| `idx_scan_ratio` | NUMERIC(5,2) | NULL |
| `health_score` | SMALLINT | NULL |

All nullable — backward compatible with existing partition data.

## Feature 1: Extended Heartbeat (GAP-6)

New metrics collected every 5 minutes in `heartbeat.py`:

### cache_hit_ratio
```sql
SELECT round(100.0 * sum(blks_hit) / nullif(sum(blks_hit + blks_read), 0), 2)
FROM pg_stat_database WHERE datname = current_database()
```

### top_tables_by_size
```sql
SELECT relname, pg_total_relation_size(relid) AS total_bytes
FROM pg_stat_user_tables ORDER BY pg_total_relation_size(relid) DESC LIMIT 5
```

### idx_scan_ratio
```sql
SELECT round(100.0 * sum(idx_scan) / nullif(sum(seq_scan + idx_scan), 0), 2)
FROM pg_stat_user_tables WHERE seq_scan + idx_scan > 0
```

### health_score (0-100)

Composite score computed from heartbeat metrics:

| Component | Weight | Full score condition | Scaling |
|---|---|---|---|
| Cache hit ratio | 25 | >= 95% | Linear below |
| Pool utilization | 20 | < 50% | Linear above |
| Dead tuple ratio | 20 | < 2% | Linear above |
| Index scan ratio | 15 | > 80% | Linear below |
| Long queries | 10 | == 0 | -2pt per query, min 0 |
| Lock waits | 10 | == 0 | -5pt per lock, min 0 |

Alert when score drops below 60.

## Feature 2: Query Intelligence (GAP-2)

New class `InsightsCollector` in `insights.py`. Runs during pulse (every 6h).

### Dependency check
```sql
SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
```
If not available → log warning, skip entirely. Rest of v3 works.

### Collection
1. Query top 10 by `total_exec_time` from `pg_stat_statements`
2. Save each as `olympus_insights` record with `insight_type = 'pattern'`
3. Compare with previous insights (same `queryid`): if `mean_exec_time` increases >30% → save as `insight_type = 'anomaly'` + alert

### Stats reset
Track last reset timestamp in `olympus_rules` (new rule `pgss_last_reset`). Reset weekly via `SELECT pg_stat_statements_reset()`.

## Feature 3: Bloat Intelligence (GAP-6)

Same `InsightsCollector` class, separate method. Runs during pulse.

1. Compare `pg_total_relation_size` with previous pulse's `top_tables_by_size` heartbeat data → compute growth rate (bytes/day)
2. Table growing >5MB/day → insight `recommendation`: "consider partitioning"
3. Indexes with `idx_scan = 0` AND `pg_relation_size > 1MB` → insight `recommendation`: "unused index, candidate for DROP"
4. Tables with `idx_scan / (seq_scan + idx_scan) < 0.5` AND `pg_relation_size > 10MB` → insight `recommendation`: "missing index suggested"

## Feature 4: Autovacuum Advisor (GAP-3 residual)

New method in `pulse.py`: `autovacuum_advisor()`.

1. Read `reloptions` from `pg_class` for each table
2. If table has no custom autovacuum settings AND `n_dead_tup > 10000` → PulseAction with `outcome="proposed"` (logged, not executed)
3. Include fillfactor suggestion if table has high update ratio (from `pg_stat_user_tables`: `n_tup_upd / (n_tup_ins + n_tup_upd) > 0.5`)

## Feature 5: Partition-Aware Cleanup (GAP-5)

Modified `cleanup_audit_trail` in `pulse.py`:

1. Check if `api_audit_trail` is partitioned: `SELECT relkind FROM pg_class WHERE relname = 'api_audit_trail'` — `'p'` means partitioned
2. If partitioned: find partitions older than retention days, `DETACH PARTITION` + `DROP TABLE`
3. If not partitioned (current state): continue with `DELETE` as now — backward compatible

Note: Converting `api_audit_trail` to partitioned is a separate future migration, not in v3 scope.

## Models

New in `models.py`:

```python
class InsightRecord(BaseModel):
    insight_type: str  # pattern | anomaly | recommendation
    title: str
    content: str
    evidence: dict[str, Any]
    source: str  # "query_intelligence" | "bloat_intelligence" | "autovacuum_advisor"
    confidence: float = 1.0
    applicable_to: list[str] = []  # table/index names
```

Extended `HeartbeatSnapshot`:
```python
cache_hit_ratio: float | None = None
top_tables_by_size: list[dict[str, Any]] = []
idx_scan_ratio: float | None = None
health_score: int | None = None
```

## Out of Scope

- Automatic index creation (too risky without human review)
- `olympus_skills` activation (Voyager pattern — needs months of insights data, defer to v4)
- Converting `api_audit_trail` to partitioned table (separate migration)
- PgBouncer configuration changes (manual)

## Testing

Same strategy as v2: mock `asyncpg.Pool`, unit tests for each method. Target: +15 tests (~43 total).

Test files:
- `test_insights.py` — InsightsCollector (query intelligence, bloat intelligence, pg_stat_statements fallback)
- `test_heartbeat.py` — Extended metrics + health score calculation
- `test_pulse.py` — Autovacuum advisor + partition-aware cleanup
