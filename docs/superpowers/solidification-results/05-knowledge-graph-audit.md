# SOLIDIFICATION 05 — Knowledge Graph Audit & Plan

**Date:** 2026-04-06
**Component:** Knowledge Graph (108K nodes, 243K edges, PostgreSQL)

## Findings: 1 CRITICAL, 6 HIGH, 7 MEDIUM, 3 LOW

## Code Fixes Applied

| Fix | Severity | What |
|-----|----------|------|
| 2.1 | CRITICAL | Wrapped persist_results in conn.transaction() — node+edge inserts now atomic |
| 5.1 | HIGH | Fixed KITAS→VISA and KITAP→VISA type correction bug (should be KITAS/KITAP) |
| 7.1 | HIGH | Property subgraph: replaced phantom `property_type:X` ID with real KG name lookup |
| 7.2 | HIGH | Tax subgraph: replaced phantom `company:X` ID + wrong `HAS_TAX` with real lookup + `TAX_OBLIGATION` |
| 6.1 | HIGH | Removed false deprecation warning from CoreferenceResolver init |

## Deferred

- 3.1 HIGH: Staging promotion job (migration_077 promised but never implemented)
- 1.2 MEDIUM: Standardize relationship_id format between GraphService and pipeline
- 2.2 HIGH: advanced_quality.py transaction safety
- 8.1 MEDIUM: BFS traversal connection hold + node count cap
- 4.1 MEDIUM: Unify orphan-inference rules between quality_filter and advanced_quality
