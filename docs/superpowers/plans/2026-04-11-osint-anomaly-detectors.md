# OSINT Anomaly Detectors — Implementation Plan

**Branch:** `feat/osint-gds-anomaly`
**Worktree:** `.worktrees/osint-anomaly`
**Date:** 2026-04-11
**Owner:** Zero only (OSINT = blindato — feedback_osint_blindato.md)

---

## Goal

Implement 5 graph-anomaly detectors over the OSINT Neo4j dataset using
Neo4j GDS library. Each detector produces ranked alerts with evidence
paths. Runs locally on Pro/Air. No entity names in logs. No network calls.

## Context (verified)

- Data already in Neo4j: `Official`, `Kanim_Office`, `Local_Vendor`,
  `PMA_Company`, `Notaris`, `Tender`, `Asset`, `Event`, `Person`,
  `Alumni_Group`, `Property`, `Vehicle`, `BankAccount`.
- Edges: `WORKS_AT`, `POSTED_TO`, `PROMOTED_TO`, `WON_CONTRACT`, `OWNS`,
  `MET_WITH`, `ATTENDED`, `ALUMNI`, `MEMBER_OF`, `FREQUENTS`, `KNOWS`,
  `MARRIED_TO`, `PARENT_OF`, `SIBLING_OF`, `PROXY_FOR`, `AWARDED_BY`.
- All relationships get `r.updated_at` set on every upsert (loader.py:394).
- No dedicated event_date/from_date on most edges — `date` property
  appears only in queries.py rapid_promotion (PROMOTED_TO.date).
- Neo4j driver pinned `neo4j>=5.20` in `apps/osint-nexus/pyproject.toml`.
  Tests venv ships `neo4j==6.1.0`, compatible with `session.run()` API.
- PyYAML already present in tests venv; thresholds loaded from YAML.

## Data Gaps Found During Brainstorming

| Detector            | Need                          | Available?                          | Resolution                             |
| ------------------- | ----------------------------- | ----------------------------------- | -------------------------------------- |
| centrality_jump     | temporal graph snapshots      | NO — no snapshot storage            | PROXY: split graph by rel.updated_at |
| bridge_outlier      | GDS Louvain + articulation    | YES (GDS 2.x has both)              | native                                 |
| temporal_burst      | real event dates              | PARTIAL — only updated_at on MET_WITH/ATTENDED | FALLBACK: use updated_at, document bias |
| angkatan_disjoint   | Official.angkatan + alumni grp | YES                                | native                                 |
| eigenvector_reverse | GDS eigenvector               | YES                                 | native                                 |

Note on GDS: we target GDS 2.6+ which exposes `gds.eigenvector`,
`gds.louvain`, `gds.pageRank`, `gds.betweenness`, and community-based
projections. Articulation points is 2.5+. All detectors use **Cypher
projections** (`gds.graph.project.cypher`) not typed projections, so
they work on any node/rel labels.

## Architecture

```
apps/osint-nexus/osint_nexus/anomaly/
  __init__.py
  alert.py             # Alert dataclass (ID-only, no names)
  base.py              # Detector ABC
  thresholds.py        # YAML loader + defaults
  runner.py            # Orchestrator: run all, dedupe, rank
  detectors/
    __init__.py
    centrality_jump.py
    bridge_outlier.py
    temporal_burst.py
    angkatan_disjoint.py
    eigenvector_reverse.py
apps/osint-nexus/scripts/run_anomaly_scan.py    # CLI
apps/osint-nexus/config/anomaly_thresholds.yaml # calibrated defaults
apps/osint-nexus/tests/anomaly/
  conftest.py          # pick testcontainers-neo4j if present, else fake session
  fake_session.py      # Minimal in-memory Cypher-compatible mock
  test_alert.py
  test_thresholds.py
  test_centrality_jump.py
  test_bridge_outlier.py
  test_temporal_burst.py
  test_angkatan_disjoint.py
  test_eigenvector_reverse.py
  test_runner.py
apps/osint-nexus/docs/anomaly-patterns.md
apps/osint-nexus/docs/anomaly-runbook.md
```

## Non-goals

- No name-resolution: alerts expose **entity IDs only** (element_id or
  derived sha256 of `(label, name)`). Resolution is done elsewhere.
- No cloud, no external API. Pure Cypher + Python + stdlib + PyYAML.
- No schema migration: detectors are read-only against the graph.

## Alert Schema

```python
@dataclass(frozen=True)
class Alert:
    alert_id: str         # sha256(pattern+primary_entity_id+day_bucket)
    pattern: str          # e.g. "centrality_jump"
    primary_entity_id: str  # element_id or hashed node id
    score: float          # 0..1 normalized within pattern
    confidence: float     # 0..1 meta-confidence (data quality)
    evidence_path: list[str]   # node_ids only, no names
    rationale_id: str     # short code, e.g. "CJ-DEGREE-DELTA"
    created_at: str       # ISO UTC
```

**Why hashed IDs?** So dedupe is stable across runs even when neo4j
internal `element_id` changes (driver restart).

## Thresholds Strategy

- Each detector exposes tunable params via `thresholds.py`.
- Defaults calibrated on a 3-tier basis:
  1. **Synthetic graphs (in test)** — verify algo fires on IS-present
     and stays silent on NOT-present.
  2. **Statistical priors** — z-scores where defensible (temporal_burst
     uses z>3.0; centrality_jump uses k>2 sigma over mean delta).
  3. **Domain priors** — angkatan_disjoint gap constraints come from
     layer 9 memory ("angkatan = fratellanza a vita" → cross-angkatan +
     short non-official path is rare-by-design).
- YAML is the single source; Python provides sane fallbacks if file missing.

## Test Strategy

**Default tier (offline, fast, always green):**

- A minimal `FakeSession` class that reads a static in-memory graph and
  returns records for the *specific Cypher patterns* each detector
  emits. We don't build a full Cypher interpreter — we match on the
  query shape and pre-compute results deterministically. This is
  acceptable because each detector's Cypher is constant per detector.

- Each `test_<detector>.py` provides two graphs: ANOMALY-PRESENT and
  ANOMALY-ABSENT. Asserts:
  - precision = 1 on present (expected node IDs in result)
  - zero alerts on absent
  - ranking is stable (list order deterministic)

**Live tier (marker `@pytest.mark.neo4j`):**

- Uses testcontainers-neo4j OR a local neo4j+gds at `NEO4J_URL`. Skips
  if env var unset. Runs the exact same scenarios against a real GDS.
  CI never runs it; local operator runs manually with
  `pytest -m neo4j apps/osint-nexus/tests/anomaly`.

**Plus:**
- `test_alert.py` for dataclass immutability + stable hashing.
- `test_thresholds.py` for YAML load + default fallback.
- `test_runner.py` for dedupe + ranking on multi-detector output.

## TDD Sequence

1. Write `Alert` dataclass + test.
2. Write `thresholds.py` + test.
3. Write `base.py` (ABC) + `runner.py` + test runner on mocks.
4. For each detector (in order of simplicity):
   eigenvector_reverse → bridge_outlier → centrality_jump →
   temporal_burst → angkatan_disjoint.
   For each: test first, then Cypher, then implementation.
5. Write docs pages.
6. CLI entrypoint.

## Commits

- Commit 1: alert + thresholds + base + runner + runner test
- Commit 2: 5 detectors + their tests + docs/anomaly-patterns.md
- Commit 3: CLI + docs/anomaly-runbook.md + live-tier conftest

## Risks & Mitigations

- **Risk:** GDS version drift. _Mitigation:_ use `gds.version()` probe,
  fail fast with clear error listing required version.
- **Risk:** Projection memory blowup on full graph. _Mitigation:_ each
  detector passes a `limit_to_labels` param (default None). Runbook
  describes per-detector projection cost.
- **Risk:** temporal_burst false positives from batch ingestion spikes.
  _Mitigation:_ `source_exclude` config excludes ingestion sources
  (e.g. "lhkpn_batch") from burst counting.
- **Risk:** angkatan_disjoint misses when `angkatan` is empty string.
  _Mitigation:_ explicit IS NOT NULL AND <> '' guards. FP mitigation.

## Out of Scope

- Alert persistence / ticketing / Telegram delivery — runner returns a
  JSON blob to stdout. Caller pipes to whatever they want.
- Temporal snapshot database — documented as follow-up.
- Name-resolution UI.

## Definition of Done

- [ ] All 5 detector modules under `apps/osint-nexus/osint_nexus/anomaly/detectors/`
- [ ] Unit tests green: `pytest apps/osint-nexus/tests/anomaly -q -m "not neo4j"`
- [ ] CLI runs with `--dry-run` flag on an empty graph and exits 0
- [ ] `anomaly-patterns.md` covers all 5 patterns
- [ ] `anomaly-runbook.md` explains run/interpret/tune
- [ ] At least 3 commits on `feat/osint-gds-anomaly`
- [ ] No entity names in logs or alerts
- [ ] No files written outside the worktree
