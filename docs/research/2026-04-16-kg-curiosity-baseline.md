# KG Curiosity Loop — T0 Baseline

**Date:** 2026-04-16
**Measured by:** Claude Opus 4.6 (Air)
**Source:** coverage_matrix.json (2026-04-12) + KG health_check

## T0 Numbers

| Metric | Value | Notes |
|--------|-------|-------|
| Gap topics total | 56 | 7 domains × 8 topics |
| Gap topics at GAP | 56 | 100% — all domains fully uncovered |
| Gap topics at STALE | 0 | |
| Gap topics at AGING | 0 | |
| Gap topics at FRESH | 0 | |
| Coverage health avg | 0.0% | |
| KG nodes | 108,068 | |
| KG edges | 242,827 | |
| Ontological density | 2.247 | edges/nodes ratio |
| kg_proposals rows | 0 | Table created, empty |

## By Domain

| Domain | Topics | GAP | Health |
|--------|--------|-----|--------|
| immigration | 8 | 8 | 0% |
| company | 8 | 8 | 0% |
| tax | 8 | 8 | 0% |
| property | 8 | 8 | 0% |
| operations | 8 | 8 | 0% |
| editorial | 8 | 8 | 0% |
| lifestyle | 8 | 8 | 0% |

## Target (30 days)

| Metric | T0 | T+30 Target | Notes |
|--------|-----|-------------|-------|
| Gap topics at GAP | 56 | < 30 | ~46% closure |
| Ontological density | 2.247 | 2.260+ | +0.5% minimum |
| Proposals created | 0 | 100+ | ~3/day |
| Proposals applied | 0 | 50+ | 50% approval rate |
| Coverage health avg | 0% | 30%+ | Mix of FRESH/AGING |

## Measurement Method

- `coverage_matrix.json` updated by `gap_scanner.py` Layer B
- KG density via `kg_store.health_check()` or `kg-propose stats`
- Proposals via `kg-propose stats`
- Weekly comparison: `mem save fact "Curiosity T+N: gaps=X, density=Y, proposals=Z"`
