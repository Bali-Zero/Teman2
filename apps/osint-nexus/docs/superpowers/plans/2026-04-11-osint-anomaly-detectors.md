# OSINT Anomaly Detectors — Implementation Plan

**Date:** 2026-04-11
**Branch:** feat/osint-gds-anomaly
**Author:** Claude Code (Air)

## Data Feasibility Analysis

### Available Temporal Signals
- Edge properties: `date`, `updated_at`, `created_at` on PROMOTED_TO, POSTED_TO, WON_CONTRACT, MET_WITH, ATTENDED
- Node properties: `created_at`, `updated_at` on Official, Person, etc.
- No formal graph snapshots (no versioned subgraph dumps)

### Pattern Assessment

| # | Pattern | Data Available | Status | Notes |
|---|---------|---------------|--------|-------|
| 1 | centrality_jump | No temporal snapshots | **PROXY** | Use edge creation timestamps as structural proxy for "recent edge mass" |
| 2 | bridge_outlier | Full graph structure | **DONE** | GDS Louvain + bridge detection via Cypher |
| 3 | temporal_burst | Edge dates exist | **DONE** | 7-day window vs EWMA baseline on dated edges |
| 4 | angkatan_disjoint_alliance | angkatan field + ALUMNI edges | **DONE** | Domain-specific: Layer 9 bapakisme/patron patterns |
| 5 | eigenvector_reverse | Full graph structure | **DONE** | Pure structural — GDS eigenvector centrality |

### Architecture Decisions
1. **GDS via Cypher projection** — no Python GDS client, avoids version pin
2. **Graceful GDS fallback** — if GDS plugin not installed, use pure Cypher approximations
3. **ID-only logging** — OPSEC: never log names, only internal Neo4j IDs or hashed refs
4. **YAML thresholds** — all magic numbers in `thresholds.yaml`, overridable per-run

### Key Proxy Decision: centrality_jump
Since we lack temporal graph snapshots, we proxy "centrality change" with:
- Count edges created in the last N days (default: 30) per node
- Compare against node's total edge count
- A node where >40% of edges are "recent" AND degree > median = centrality_jump candidate
- This captures the same signal (sudden importance increase) without needing snapshots

### GDS Fallback Strategy
For environments without GDS plugin:
- **Louvain** → Label Propagation via pure Cypher (slower but works)
- **Eigenvector** → iterative PageRank approximation via Cypher
- **Betweenness** → degree + shortest-path sampling (approximate)
