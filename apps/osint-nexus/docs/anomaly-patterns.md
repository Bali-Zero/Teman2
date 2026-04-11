# OSINT Anomaly Patterns

Five graph-anomaly detectors implemented in
`osint_nexus/anomaly/detectors/`. Each detector produces ranked
`Alert` objects containing **opaque entity IDs only** — no names — so
the output is safe to process in automated pipelines and name
resolution is handled in a separate, Zero-only step.

All cipher examples below are **redacted** of real IDs. `$param` tokens
are Neo4j parameters the detector passes.

## Data preconditions & informational alerts

Three of the five detectors are **semantically blocked** on a fresh
OSINT graph with no history / no variance. Running them would produce
100% false positives. Each detector carries a `precheck(session)`
method that inspects the live graph and returns `ok=False` with a
human-readable reason if the preconditions fail. The runner surfaces
these blocks as **informational alerts** — one per blocked detector,
marked `informational=True`, score 0, ranked AFTER real alerts — so
operators can tell "zero anomalies" apart from "detector skipped
because the graph is too young".

| Detector            | Precondition                                         |
| ------------------- | ---------------------------------------------------- |
| `centrality_jump`   | `max(updated_at) - min(updated_at) >= min_history_days` (default 30) |
| `temporal_burst`    | `max(updated_at) - min(updated_at) >= min_history_days` (default 30) |
| `angkatan_disjoint` | `>= 2` distinct `Official.angkatan` years AND spread `>= min_angkatan_gap` |

`bridge_outlier` and `eigenvector_reverse` have no semantic
precondition — they run on any graph with nodes and edges.

## GDS API version

All GDS queries target **Neo4j GDS 2.13+**. The `bridge_outlier` and
`eigenvector_reverse` detectors use the current
`gds.graph.project` Cypher-aggregation function (projection returned
from a Cypher query via `WITH gds.graph.project(...) AS g`). The
legacy `gds.graph.project.cypher` procedure is deprecated and will be
removed; we migrated off it so the detectors do not break on future
GDS upgrades.

Projections explicitly declare `undirectedRelationshipTypes: ['*']`
because `gds.articulationPoints` rejects directed projections with
`IllegalArgumentException: Articulation Points algorithm requires
relationship projections to be UNDIRECTED`.

GDS stream procedures return an INTEGER `nodeId` (Neo4j's internal
id), not the modern `elementId` string. The detectors unwrap them via
`gds.util.asNode(nodeId)` and return `elementId(...)` so downstream
parameterized `MATCH ... WHERE elementId(n) = $id` queries can match
reliably.

---

## 1. `centrality_jump` — sudden edge mass into a node

**Why it matters.** Layer 27 "Centrality Algorithms" / Layer 9
"Ciclo Pilkada: pre-elezioni regionali = mutasi massicce =
rimescolamento". A node whose centrality jumps above its peer mean
indicates a new broker forming, often before the formal mutasi SK
becomes public.

**Data gap.** The graph has no temporal snapshots. We use a
**structural proxy**: treat the most-recently-written
`recent_fraction` of edges (by `r.updated_at`) as "today" and compare
each node's recency ratio to the population mean ± sigma.

**Data precondition.** Needs at least `min_history_days` (default 30)
of temporal spread on `r.updated_at`. Below that threshold the
"recent" slice is effectively the whole history and the z-test has
zero variance. The detector returns a single informational alert
instead of running in this state. On the current Kemenkumham graph
(spread = 3 days, Apr 2026) the detector is BLOCKED; once the scraper
runs for a month of real history, it will unblock automatically. The
legacy `coalesce(r.updated_at, r.created_at)` fallback was removed
because `r.created_at` is always NULL in the live graph — dead code.

**Cypher (redacted).**

```cypher
MATCH (n)
WITH n, count { (n)-[]-() } AS total_degree
WHERE total_degree >= $min_degree
CALL (n, total_degree) {
  MATCH (n)-[r]-()
  WHERE r.updated_at IS NOT NULL
  WITH r, datetime(r.updated_at) AS ts
  ORDER BY ts DESC
  WITH collect(r) AS rels,
       toInteger(ceil(total_degree * $recent_fraction)) AS k
  RETURN size(rels[..k]) AS recent_degree
}
RETURN toString(elementId(n)) AS node_id, total_degree, recent_degree
```

The `CALL (n, total_degree) { ... }` form is the scoped-subquery
syntax required by Neo4j 5.23+ (the unscoped `CALL { ... }` is
deprecated). The recent slice is a real `rels[..k]` top-k, not the
nonsensical always-empty / always-full predicate the previous
version used.

**False positive modes.**

- Batch ingestion spikes (lhkpn_batch) boost many nodes at once. Ratio
  comparison to the peer population mean absorbs this because the
  whole peer group shifts together — so no single node sticks out.
- Node with naturally skewed distribution (e.g. a notaris that just
  got a new tender cluster): mitigated by the `min_degree` gate and
  the minimum `min_score = 0.55`.

**Calibration.** `sigma_multiplier = 2.5` is a k-sigma unilateral
threshold that gives ~0.6% false-positive rate under Gaussian
assumption. Degree deltas are heavy-tailed, so 1.96 (95%) would fire
constantly. Raise to 3.0 for very noisy graphs. Lower to 2.0 only if
alert volume is acceptable.

**Status: DONE (proxy)** — the implementation is a structural proxy
because temporal snapshots are not stored. See
[Follow-up](#follow-up) in the runbook.

---

## 2. `bridge_outlier` — cut vertex between communities

**Why it matters.** Layer 27 Community Detection: "Louvain: Fazioni
naturali (spesso NON corrispondono a struktur formal). Sorpresa
tipica: cluster cross-Kanim = stessa angkatan o stessa arisan istri."
An articulation point sitting between two Louvain communities is a
single point of failure in factional communication — the classic
"broker" who knows both sides.

**GDS API version.** Uses `gds.graph.project` aggregation function
(GDS 2.13+), NOT the deprecated `gds.graph.project.cypher` procedure.
`undirectedRelationshipTypes: ['*']` is MANDATORY — the GDS
`articulationPoints` algorithm rejects directed projections.

**Cypher (redacted).**

```cypher
// Step 0 — idempotent drop (a crashed prior run would leave the
// projection behind otherwise, blocking the next scan forever)
CALL gds.graph.drop('anomaly_bridge', false) YIELD graphName;

// Step 1 — aggregation-function projection, undirected
MATCH (source)
OPTIONAL MATCH (source)-[r]-(target)
WITH source, target WHERE target IS NOT NULL
WITH gds.graph.project(
  'anomaly_bridge',
  source,
  target,
  {},
  {undirectedRelationshipTypes: ['*']}
) AS g
RETURN g.graphName, g.nodeCount, g.relationshipCount;

// Step 2 — Louvain. gds.util.asNode(nodeId) unwraps the integer
// GDS nodeId back to an element id the rest of the pipeline can match.
CALL gds.louvain.stream('anomaly_bridge')
YIELD nodeId, communityId
RETURN elementId(gds.util.asNode(nodeId)) AS node_id, communityId;

// Step 3 — articulation points (GDS 2.5+)
CALL gds.articulationPoints.stream('anomaly_bridge')
YIELD nodeId
RETURN elementId(gds.util.asNode(nodeId)) AS node_id;

// Step 4 — per-cut neighbors (community map is kept in-memory on
// the client side; we do NOT query n.community_id because Louvain
// is streamed — nothing is ever written back to the nodes)
UNWIND $cut_ids AS cid
MATCH (cut) WHERE toString(elementId(cut)) = cid
OPTIONAL MATCH (cut)-[]-(nbr)
RETURN cid, [n IN collect(DISTINCT nbr) WHERE n IS NOT NULL
             | toString(elementId(n))] AS neighbor_ids;
```

**False positive modes.**

- Small "communities" of 1-2 nodes hanging off a real community create
  spurious cuts. Mitigated by `min_community_size` (default 3).
- Intra-community articulation points exist but are not interesting.
  Mitigated by requiring the cut to span ≥ `min_communities` distinct
  labels.
- Lopsided cuts (one large community + one dangling leaf) are
  deprioritized via the balance-ratio term in the score.

**Calibration.** The scoring multiplies a balance term
`min(sizes) / max(sizes)` by a diversity boost `0.5 + n_comms/3`, then
clamps at `min_score = 0.6`. A symmetric cut between 2 large
communities scores near 1.0; a cut between 3 equally sized
communities scores highest.

**Status: DONE.**

---

## 3. `temporal_burst` — edge class volume spike

**Why it matters.** Layer 27 Anomaly Detection Patterns 3 and 5:
sudden bursts in `MET_WITH` / `ATTENDED` edges often precede or
follow a mutasi. Kleinberg-style z-score test over an EWMA baseline is
the standard approach for streaming burst detection.

**Data gap.** Edges do not carry a real-world event date — only
`r.updated_at` (when the loader wrote them). That means bursts can
reflect *intake* patterns, not real-world events. We document this
limitation and offer `source_exclude` so operators can silence known
batch loaders.

**Data precondition.** EWMA burst detection on a series shorter than
`min_history_days` (default 30) produces 100% false positives — the
baseline has no memory and every bucket is "bursty" by definition.
The detector returns a single informational alert instead of running
in this state. The legacy `coalesce(r.updated_at, r.created_at)`
fallback was removed because `r.created_at` is always NULL in the
live graph.

**Cypher (redacted).**

```cypher
// Step 0 — precheck
MATCH ()-[r]->() WHERE r.updated_at IS NOT NULL
WITH datetime(r.updated_at) AS ts
RETURN min(ts) AS min_ts, max(ts) AS max_ts, count(*) AS total,
       duration.inDays(min(ts), max(ts)).days AS spread_days;

// Step 1 — weekly bucket counts per rel type (scoped subquery)
// Note datetime() around r.updated_at — it's an ISO string, not a date,
// so date(...) would raise CypherSyntaxError "Text cannot be parsed to
// a Date". The old query hit exactly that bug.
UNWIND $rel_types AS rt
CALL (rt) {
  MATCH ()-[r]->()
  WHERE type(r) = rt
    AND r.updated_at IS NOT NULL
  WITH r, date.truncate('week', datetime(r.updated_at)) AS bucket
  WITH bucket, count(r) AS edge_count,
       collect(DISTINCT coalesce(r.source, '')) AS sources
  RETURN toString(bucket) AS bucket, edge_count, sources
}
RETURN rt AS rel_type, bucket, edge_count, sources
ORDER BY rel_type, bucket;

// Step 2 — for each burst bucket, fetch sample source/target IDs
UNWIND $buckets AS b
MATCH (src)-[r]->(tgt)
WHERE type(r) = b.rel_type
  AND r.updated_at IS NOT NULL
  AND date.truncate('week', datetime(r.updated_at)) = date(b.bucket)
RETURN b.rel_type, b.bucket,
       collect(DISTINCT toString(elementId(src)))[..10] AS source_ids,
       collect(DISTINCT toString(elementId(tgt)))[..10] AS target_ids;
```

**EWMA formula.**

```
ewma_t = alpha * x_t + (1 - alpha) * ewma_{t-1}
var_t  = alpha * (x_t - ewma_{t-1})^2 + (1 - alpha) * var_{t-1}
z_t    = (x_t - ewma_{t-1}) / sqrt(var_{t-1})
```

**False positive modes.**

- Scrape-induced bursts → `source_exclude` drops buckets dominated by
  listed sources.
- Tiny absolute counts passing z-test → `min_edges_in_window`
  (default 5) floor.
- Single-bucket series (detector needs ≥3 to compute an EWMA).

**Calibration.** `z_threshold = 3.0` is Kleinberg's published value.
`ewma_alpha = 0.3` gives the baseline enough memory to smooth over
scrape cadence while still reacting within 3-4 buckets to a sustained
shift. Change only with test-set feedback.

**Status: DONE (limitation documented).**

---

## 4. `angkatan_disjoint` — cross-cohort short non-official path

**Why it matters.** Layer 9 Network & Power Topology: "Angkatan
(Polimigras Depok): stessa angkatan = fratellanza a vita, loyalty
cross-ufficio". If two officials from *different* angkatan cohorts
(gap ≥ 3 years) are ≤3 hops apart via *only* non-official edges
(family, social, political affiliation), this is not a coincidence.
It is either a family-based alliance bridging cohorts, a hidden
patron-client arrangement, or a covert alignment. The formal
structure would route such ties via WORKS_AT / GOVERNED_DURING /
SUPERVISES / COMMANDS / PART_OF / OPERATES / UBO_OF / LEGAL_OWNER_OF
/ DE_FACTO_OWNER / FOUNDED / LISTED_AS / OPERATED_BY; the absence of
those edges on the path is the tell.

**Rel-type families.** Derived from the REAL live Kemenkumham schema
(Apr 2026, 45 relationship types). The old default list (`KNOWS`,
`SIBLING_OF`, `FREQUENTS`) referenced rel types that do not exist in
the graph — the detector was matching the empty set. The new default
list is `FAMILY_OF`, `PARENT_OF`, `MARRIED_TO`, `DIVORCED_FROM`,
`FAMILY_ALLIANCE`, `MET_WITH`, `ALLY_OF`, `ALUMNI`, `SAME_PARTY`,
`RUNNING_MATE`, `ENDORSES`, `PARTNERS_WITH`, `PUBLIC_CONFLICT`. Both
lists are configurable via `thresholds.yaml` → `angkatan_disjoint`.

**Data precondition.** Requires at least 2 distinct
`Official.angkatan` values with spread `>= min_angkatan_gap` in the
live graph. On the current Kemenkumham graph all 170 Officials have
`angkatan = 2000` (single cohort), so the detector is BLOCKED by
precheck. Once the scraper populates multi-cohort data (polimigras
angkatan history), the detector will unblock automatically.

**Cypher (redacted).**

```cypher
// Step 0 — precheck
MATCH (n:Official) WHERE n.angkatan IS NOT NULL
RETURN count(DISTINCT toInteger(n.angkatan)) AS distinct_years,
       min(toInteger(n.angkatan)) AS min_y,
       max(toInteger(n.angkatan)) AS max_y;

// Step 1 — pair query (rel union list is templated into the
// variable-length relationship pattern; the official list is passed
// as a Neo4j parameter via $official_rels for defence-in-depth)
MATCH (a:Official), (b:Official)
WHERE a.angkatan IS NOT NULL AND toString(a.angkatan) <> ''
  AND b.angkatan IS NOT NULL AND toString(b.angkatan) <> ''
  AND toInteger(a.angkatan) < toInteger(b.angkatan)
  AND abs(toInteger(a.angkatan) - toInteger(b.angkatan)) >= $min_gap
WITH a, b LIMIT 500
MATCH p = shortestPath(
  (a)-[rels:FAMILY_OF|PARENT_OF|MARRIED_TO|DIVORCED_FROM|FAMILY_ALLIANCE
           |MET_WITH|ALLY_OF|ALUMNI|SAME_PARTY|RUNNING_MATE|ENDORSES
           |PARTNERS_WITH|PUBLIC_CONFLICT*..3]-(b)
)
WHERE none(r IN relationships(p) WHERE type(r) IN $official_rels)
RETURN toString(elementId(a)) AS a_id, toString(elementId(b)) AS b_id,
       toInteger(a.angkatan) AS a_angkatan, toInteger(b.angkatan) AS b_angkatan,
       abs(toInteger(a.angkatan) - toInteger(b.angkatan)) AS gap,
       length(p) AS path_len,
       [r IN relationships(p) | type(r)] AS path_rel_types,
       [n IN nodes(p) | toString(elementId(n))] AS path_node_ids;
```

**False positive modes.**

- Near-cohorts (gap < 3 years) are effectively one loyalty unit.
  Filtered via `min_angkatan_gap`.
- Very long paths (gap > 3 hops) are noise. Filtered via `max_path_len`.
- Symmetric pair duplication (a,b) and (b,a) → sorted-tuple dedupe in
  the detector.
- Officials with empty `angkatan` are filtered at query time.

**Calibration.** `min_angkatan_gap = 3` because polimigras batches
produce tight cohorts — a 3-year gap spans 1-2 intake classes.
`max_path_len = 3` is the shortest meaningful non-official bridge
(A → mutual friend → B).

**Status: DONE.**

---

## 5. `eigenvector_reverse` — compartmentalized lone hub

**Why it matters.** Layer 27 Centrality: PageRank = "Chi è DAVVERO
importante". In healthy power structures, high-eigenvector nodes
cluster — important people know important people. A node with high
eigenvector score whose neighbors are ALL in the bottom quartile is a
**compartmentalized dependency structure**: a handler who never lets
their contacts meet each other. In OSINT terms: a cut-out or fixer.

**GDS API version.** Uses `gds.graph.project` aggregation function
(GDS 2.13+), NOT the deprecated `gds.graph.project.cypher` procedure.
The projection is undirected so neighborhood counts are symmetric.

**Cypher (redacted).**

```cypher
// Step 0 — idempotent drop
CALL gds.graph.drop('anomaly_eigenvector', false) YIELD graphName;

// Step 1 — aggregation-function projection, undirected
MATCH (source)
OPTIONAL MATCH (source)-[r]-(target)
WITH source, target WHERE target IS NOT NULL
WITH gds.graph.project(
  'anomaly_eigenvector',
  source,
  target,
  {},
  {undirectedRelationshipTypes: ['*']}
) AS g
RETURN g.graphName;

// Step 2 — eigenvector stream with per-row percentiles.
// gds.util.asNode(nodeId) unwraps the GDS integer id into a node
// so elementId(...) produces the string id our downstream neighbor
// query can match on.
CALL gds.eigenvector.stream('anomaly_eigenvector',
  {maxIterations: 100, tolerance: 0.0001})
YIELD nodeId, score
WITH elementId(gds.util.asNode(nodeId)) AS node_id, score
WITH collect({id: node_id, score: score}) AS nodes
UNWIND range(0, size(nodes) - 1) AS i
WITH nodes[i] AS n, i, size(nodes) AS total
RETURN n.id AS node_id, n.score AS score,
       1.0 - (1.0 * i / total) AS percentile
ORDER BY score DESC;

// Step 3 — neighbors of top-decile hubs
UNWIND $hub_ids AS hid
MATCH (hub) WHERE toString(elementId(hub)) = hid
OPTIONAL MATCH (hub)-[]-(neighbor)
RETURN hid, [n IN collect(DISTINCT neighbor) WHERE n IS NOT NULL
             | toString(elementId(n))] AS neighbor_ids;
```

**False positive modes.**

- 2-3 neighbor hubs look "lone" trivially → `min_neighbors = 4`.
- Hubs that aren't actually hubs (mid-graph nodes) → `hub_top_percentile = 0.90`.
- Balanced graphs where everyone is "low" → the percentile computation
  is relative, so this does not false-positive by itself.

**Calibration.** Score is geometric mean of `hub_percentile` and
`lone_ratio`, both in [0,1]. Default `lone_hub_min_ratio = 0.75` says
"at least 75% of neighbors must be in the bottom quartile". Raise to
0.90 for stricter OPSEC; lower to 0.6 only if you're exploring.

**Status: DONE.**

---

## Shared conventions

**Alert shape.**

```python
@dataclass(frozen=True)
class Alert:
    alert_id: str            # sha256(pattern + entity_id + day)[:16]
    pattern: str             # e.g. "centrality_jump"
    primary_entity_id: str   # opaque ID, never a name
    score: float             # [0, 1] — higher = more anomalous
    confidence: float        # [0, 1] — data-quality weight
    evidence_path: list[str] # node IDs only, no names
    rationale_id: str        # short code e.g. "ER-LONE-HUB"
    created_at: str          # ISO UTC
```

**Day-bucket dedupe.** Same-day re-runs produce identical alert_ids,
so caller-side ticketing systems see a single alert — not a flood.

**No names in logs.** Detectors log their class name, a count, and a
`rationale_id`. They NEVER log `n.name`, `o.jabatan`, or any string
that could identify a target.
