# Live Verification — 2026-04-12

Baseline vs fixed anomaly scan against the local Neo4j 5.26.24 + GDS
2.13.9 OSINT graph (1606 nodes / 2249 edges / 45 relationship types,
Kemenkumham-NR pilot). Same YAML thresholds, same CLI, same
credentials. Only the code changed.

## Commands

```bash
NEO4J_URI=bolt://localhost:17687 \
NEO4J_USER=neo4j \
NEO4J_PASSWORD=osint-nexus-2026 \
PYTHONPATH=apps/osint-nexus \
python3.11 apps/osint-nexus/scripts/run_anomaly_scan.py \
  --output /tmp/anomaly_scan_<baseline|fixed>.json
```

## Baseline (pre-fix, commit d2b65810b)

```
detectors active: [centrality_jump, bridge_outlier, temporal_burst,
                   angkatan_disjoint, eigenvector_reverse]
WARNING: detector bridge_outlier failed: ClientError
WARNING: detector temporal_burst failed: CypherSyntaxError
scan complete: 0 alerts
```

| Detector              | Status                                                                                                                              |
| --------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `centrality_jump`     | ran, deprecation warning on `CALL { ... }` scope, recency predicate `size([x IN rels WHERE toInteger(size(rels)*0.2)>0])` nonsense, 0 alerts |
| `bridge_outlier`      | **ClientError** — `gds.articulationPoints` rejected the directed projection ("relationship projections must be UNDIRECTED"); also a stale `anomaly_bridge` projection from a prior crashed run compounded the issue |
| `temporal_burst`      | **CypherSyntaxError** — `date(coalesce(r.updated_at, r.created_at))` failed at parse time because `r.updated_at` is an ISO datetime string, not a date                                                               |
| `angkatan_disjoint`   | deprecation warnings on `KNOWS` / `SIBLING_OF` / `FREQUENTS` (rel types do not exist in the live graph), 0 alerts by construction   |
| `eigenvector_reverse` | ran, deprecation warning on `gds.graph.project.cypher`, 0 alerts — see "known limitation" below                                     |

Total: **0 alerts**, 2 crashes, 6 deprecation warnings.

## Fixed

```
detectors active: [centrality_jump, bridge_outlier, temporal_burst,
                   angkatan_disjoint, eigenvector_reverse]
INFO: detector centrality_jump blocked: temporal spread too narrow: 3 days, need 30
INFO: detector temporal_burst blocked: temporal spread too narrow: 3 days, need 30
INFO: detector angkatan_disjoint blocked: angkatan variance too low: 1 distinct years, spread 0
scan complete: 10 alerts
```

| Detector              | Status                                                                  |
| --------------------- | ----------------------------------------------------------------------- |
| `centrality_jump`     | **blocked** by precheck (3 days of history < 30). 1 informational alert |
| `bridge_outlier`      | **ran successfully**. 7 real alerts (top score 0.946)                   |
| `temporal_burst`      | **blocked** by precheck (3 days of history < 30). 1 informational alert |
| `angkatan_disjoint`   | **blocked** by precheck (1 distinct cohort). 1 informational alert      |
| `eigenvector_reverse` | ran successfully, 0 alerts (see "known limitation")                     |

Total: **10 alerts** (7 real bridge_outlier + 3 informational), 0 crashes, 0 deprecation warnings.

## Top bridge_outlier findings (real alerts)

| Score | Entity elementId   | Rationale                      |
| ----- | ------------------ | ------------------------------ |
| 0.946 | `...:5`            | BO-CUT-BETWEEN-COMMUNITIES     |
| 0.914 | `...:66`           | BO-CUT-BETWEEN-COMMUNITIES     |
| 0.865 | `...:3`            | BO-CUT-BETWEEN-COMMUNITIES     |
| 0.667 | `...:184`          | BO-CUT-BETWEEN-COMMUNITIES     |
| 0.655 | `...:242`          | BO-CUT-BETWEEN-COMMUNITIES     |
| 0.647 | `...:26`           | BO-CUT-BETWEEN-COMMUNITIES     |
| 0.612 | `...:14`           | BO-CUT-BETWEEN-COMMUNITIES     |

151 articulation points detected across 95 Louvain communities (top-5
sized 116, 106, 56, 48, 37). Only 7 pass the balance/diversity scoring
floor of 0.6 — expected: most cut vertices hang off small trivial
branches.

## Known limitations after the fix

1. **`eigenvector_reverse` produces zero alerts on this graph.** The
   GDS `gds.eigenvector.stream` algorithm converges to 0.0 for every
   node. This is a graph-structure issue (OWNS-dominated ownership
   bipartite, weakly connected), NOT a detector bug. `gds.pageRank`
   works fine on the same projection and returns values up to ~53. A
   future patch could switch `eigenvector_reverse` to a PageRank-based
   variant — tracked as a follow-up in `anomaly-patterns.md`.

2. **The three data-gated detectors will stay blocked** until the
   upstream OSINT scraper catches up on history and cohort data. The
   preconditions are:
   - `temporal_burst` / `centrality_jump`: at least 30 days of
     temporal spread on `r.updated_at` (currently 3 days — one
     ingestion batch on 2026-04-07).
   - `angkatan_disjoint`: at least 2 distinct
     `Official.angkatan` years with spread >= 3 (currently: all 170
     Officials have `angkatan=2000`, spread 0).

Once the scraper runs for a month and populates polimigras cohort
history, all three will unblock automatically — no code change needed.

## Offline test count

Before fix: **38 passing** (0 new precheck tests, detectors green on
scripted FakeSession).

After fix: **54 passing** (38 preserved + 16 new across
`test_precheck.py`, `test_runner_precheck.py`, and the extended
`test_runner.py`). All run in <1 second without Neo4j.
