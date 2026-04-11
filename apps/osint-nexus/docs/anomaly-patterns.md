# OSINT Anomaly Patterns

Five graph-anomaly detectors implemented in
`osint_nexus/anomaly/detectors/`. Each detector produces ranked
`Alert` objects containing **opaque entity IDs only** — no names — so
the output is safe to process in automated pipelines and name
resolution is handled in a separate, Zero-only step.

All cipher examples below are **redacted** of real IDs. `$param` tokens
are Neo4j parameters the detector passes.

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

**Cypher (redacted).**

```cypher
MATCH (n)
WITH n, count { (n)-[]-() } AS total_degree
WHERE total_degree >= $min_degree
CALL {
  WITH n
  MATCH (n)-[r]-()
  WITH r ORDER BY coalesce(r.updated_at, r.created_at) DESC
  WITH collect(r) AS rels
  RETURN size([x IN rels WHERE toInteger(size(rels) * $recent_fraction) > 0]) AS recent_degree
}
RETURN toString(elementId(n)) AS node_id, total_degree, recent_degree
```

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

**Cypher (redacted).**

```cypher
// Step 1 — cypher projection
CALL gds.graph.project.cypher(
  'anomaly_bridge',
  'MATCH (n) RETURN id(n) AS id',
  'MATCH (a)-[]-(b) RETURN id(a) AS source, id(b) AS target'
) YIELD graphName;

// Step 2 — Louvain
CALL gds.louvain.stream('anomaly_bridge')
YIELD nodeId, communityId;

// Step 3 — articulation points (GDS 2.5+)
CALL gds.articulationPoints.stream('anomaly_bridge')
YIELD nodeId;

// Step 4 — per-cut neighbor community counts
UNWIND $cut_ids AS cid
MATCH (cut) WHERE toString(elementId(cut)) = cid
OPTIONAL MATCH (cut)-[]-(nbr)
RETURN cid, collect(DISTINCT nbr.community_id) AS comms;
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

**Cypher (redacted).**

```cypher
// Step 1 — weekly bucket counts per rel type
UNWIND $rel_types AS rt
MATCH ()-[r]->()
WHERE type(r) = rt
  AND coalesce(r.updated_at, r.created_at) IS NOT NULL
WITH rt, r, date.truncate('week', date(coalesce(r.updated_at, r.created_at))) AS bucket
RETURN rt AS rel_type, toString(bucket) AS bucket,
       count(r) AS edge_count,
       collect(DISTINCT coalesce(r.source, '')) AS sources
ORDER BY rt, bucket;

// Step 2 — for each burst bucket, fetch sample source/target IDs
UNWIND $buckets AS b
MATCH (src)-[r]->(tgt)
WHERE type(r) = b.rel_type
  AND date.truncate('week', date(coalesce(r.updated_at, r.created_at))) =
      date(b.bucket)
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
(KNOWS / MET_WITH / MARRIED_TO / PARENT_OF / SIBLING_OF / FREQUENTS),
this is not a coincidence. It is either a family-based alliance
bridging cohorts, a hidden patron-client arrangement, or a covert
alignment. The formal structure would route such ties via
POSTED_TO / PROMOTED_TO; the absence of those edges is the tell.

**Cypher (redacted).**

```cypher
MATCH (a:Official), (b:Official)
WHERE a.angkatan IS NOT NULL AND toString(a.angkatan) <> ''
  AND b.angkatan IS NOT NULL AND toString(b.angkatan) <> ''
  AND toInteger(a.angkatan) < toInteger(b.angkatan)
  AND abs(toInteger(a.angkatan) - toInteger(b.angkatan)) >= $min_gap
WITH a, b LIMIT 500
MATCH p = shortestPath(
  (a)-[rels:KNOWS|MET_WITH|MARRIED_TO|PARENT_OF|SIBLING_OF|FREQUENTS*..3]-(b)
)
WHERE none(r IN relationships(p) WHERE type(r) IN ['WORKS_AT','POSTED_TO','PROMOTED_TO'])
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

**Cypher (redacted).**

```cypher
// Step 1 — projection
CALL gds.graph.project.cypher(
  'anomaly_eigenvector',
  'MATCH (n) RETURN id(n) AS id',
  'MATCH (a)-[]-(b) RETURN id(a) AS source, id(b) AS target'
) YIELD graphName;

// Step 2 — eigenvector with percentiles
CALL gds.eigenvector.stream('anomaly_eigenvector',
  {maxIterations: 100, tolerance: 0.0001})
YIELD nodeId, score
WITH collect({id: nodeId, score: score}) AS nodes
UNWIND range(0, size(nodes) - 1) AS i
WITH nodes[i] AS n, i, size(nodes) AS total
RETURN toString(n.id) AS node_id, n.score AS score,
       1.0 - (1.0 * i / total) AS percentile
ORDER BY score DESC;

// Step 3 — neighbors of top-decile hubs
UNWIND $hub_ids AS hid
MATCH (hub) WHERE toString(elementId(hub)) = hid
OPTIONAL MATCH (hub)-[]-(neighbor)
RETURN hid, [n IN collect(DISTINCT neighbor) | toString(elementId(n))] AS neighbor_ids;
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
