# Anomaly Detection Patterns

Five graph-based anomaly detectors for the OSINT Nexus intelligence graph.
Each pattern is designed to surface structurally suspicious configurations
that may indicate hidden power dynamics, coordination, or compartmentalization.

---

## Pattern 1: Centrality Jump

### What it detects
Nodes whose edge count has grown disproportionately in a recent time window.
A proxy for "centrality increase" when temporal graph snapshots are unavailable.

### Why it matters
*Ref: project_osint_layer27_graph_analytics.md — Centrality Algorithms*

A sudden increase in connections signals a node rapidly gaining importance.
In the context of Indonesian bureaucratic networks, this often coincides with:
- A newly appointed Kakanwil consolidating loyalists (Layer 9: bapakisme)
- Pre-Pilkada (regional election) alliance building
- A broker accumulating new relationships ahead of procurement cycles

### Cypher Query (redacted)
```cypher
MATCH (n)-[r]-()
WHERE n:Official OR n:Person
WITH n,
     count(r) AS total_degree,
     sum(CASE
         WHEN date(coalesce(r.updated_at, r.created_at, r.date))
              >= date() - duration({days: $window_days})
         THEN 1 ELSE 0
     END) AS recent_edges
WHERE total_degree >= $min_degree
  AND recent_edges >= $min_recent_edges
WITH n, total_degree, recent_edges,
     toFloat(recent_edges) / total_degree AS recent_fraction
WHERE recent_fraction >= $fraction_threshold
RETURN elementId(n) AS node_id, total_degree, recent_edges, recent_fraction
ORDER BY recent_fraction DESC
```

### False Positive Modes
- **Data entry batch**: Scraper backfill creates many edges at once for old events
- **New node**: Recently added nodes naturally have 100% recent edges
- **High-activity hub**: Event organizers may legitimately accumulate edges fast

### Calibration Notes
- `window_days=30`: Captures monthly activity cycles
- `recent_edge_fraction_threshold=0.40`: Organic growth rarely exceeds 20% in 30d
- `min_degree=5`: Filters noise from sparse nodes
- `min_recent_edges=3`: Absolute floor prevents 1-of-2 false positives

---

## Pattern 2: Bridge Outlier

### What it detects
Nodes that act as the sole connection between two otherwise disjoint communities.
These are cut vertices whose removal would disconnect parts of the graph.

### Why it matters
*Ref: project_osint_layer27_graph_analytics.md — Community Detection*

Layer 27 notes that "cluster cross-Kanim = stessa angkatan o stessa arisan istri"
(cross-office clusters often form around shared graduation year or social circles).
A bridge between such clusters is a high-value intelligence target:
- Hidden brokers facilitating cross-faction deals
- Patron-client chains spanning administrative boundaries
- Cutout nodes designed to limit organizational exposure

### Cypher Query (redacted)
```cypher
-- With GDS Louvain:
CALL gds.louvain.write('anomaly_bridge', {writeProperty: '_community'})

MATCH (n)--(neighbor)
WHERE n._community IS NOT NULL AND neighbor._community IS NOT NULL
WITH n,
     collect(DISTINCT neighbor._community) AS neighbor_communities,
     count(DISTINCT neighbor) AS degree
WHERE size(neighbor_communities) >= 2
WITH n, neighbor_communities, degree,
     toFloat(size(neighbor_communities)) / sqrt(toFloat(degree)) AS bridge_score
WHERE bridge_score >= $score_threshold
RETURN elementId(n) AS node_id, communities_bridged, degree, bridge_score
```

### False Positive Modes
- **High-degree hubs**: Well-connected officials naturally span communities
- **Organizational bridges**: Kakanwil nodes bridge Kanim offices by design
- **Data sparsity**: Small communities may form around data gaps, not real factions

### Calibration Notes
- `min_community_size=3`: Ignores trivial 1-2 node clusters
- `bridge_score_threshold=0.5`: Normalized by sqrt(degree) to penalize pure hubs
- Falls back to pure Cypher heuristic if GDS plugin unavailable

---

## Pattern 3: Temporal Burst

### What it detects
Edge types (MET_WITH, ATTENDED, WON_CONTRACT, etc.) whose creation rate
spikes above their EWMA baseline in a 7-day window with z-score > 3.

### Why it matters
*Ref: project_osint_layer9_power_topology.md — Temporal Power Mapping*

Layer 9 identifies key temporal signals:
- "Ciclo Pilkada: pre-elezioni regionali = mutasi massicce = rimescolamento"
- Promotion clusters within 6 months of new boss = patron-client inference
- Sudden meeting bursts may precede policy changes or procurement cycles

### Cypher Query (redacted)
```cypher
MATCH ()-[r]->()
WHERE type(r) IN $edge_types
  AND coalesce(r.date, r.updated_at, r.created_at) IS NOT NULL
WITH type(r) AS edge_type,
     date(coalesce(r.date, r.updated_at, r.created_at)) AS edge_date,
     elementId(r) AS rel_id
RETURN edge_type, edge_date, collect(rel_id) AS rel_ids
ORDER BY edge_type, edge_date
```
*EWMA computation happens in Python (cannot be done efficiently in Cypher).*

### False Positive Modes
- **Scraper bursts**: A new data source produces many edges at once for historical events
- **Seasonal patterns**: Year-end ceremonies, national holidays cluster events naturally
- **Single-source bias**: One document listing many attendees inflates a single date

### Calibration Notes
- `z_threshold=3.0`: p<0.003 under normality — very unlikely by chance
- `ewma_span_days=30`: Monthly smoothing window
- `min_baseline_days=14`: Requires 2+ weeks of history for stable EWMA
- `edge_types`: Focus on high-signal types; exclude WORKS_AT (too stable)

---

## Pattern 4: Angkatan Disjoint Alliance

### What it detects
Two officials from different Polimigras angkatan (graduation years) connected
by an unexpectedly short path through non-official edges (family, patron, social).

### Why it matters
*Ref: project_osint_layer9_power_topology.md — Angkatan (Polimigras Depok)*

Layer 9 establishes that angkatan loyalty is the dominant alliance structure:
"stessa angkatan = fratellanza a vita, loyalty cross-ufficio". Cross-angkatan
alliances via informal channels signal:
- Active bapakisme (patron-client) relationships
- Strategic marriage alliances between factions
- Hidden coordination that bypasses the natural angkatan boundary

This is the most domain-specific detector and the highest-value signal.

### Cypher Query (redacted)
```cypher
MATCH (a:Official), (b:Official)
WHERE a.angkatan IS NOT NULL AND b.angkatan IS NOT NULL
  AND a.angkatan <> b.angkatan
  AND abs(toInteger(a.angkatan) - toInteger(b.angkatan)) >= $min_gap
  AND elementId(a) < elementId(b)  -- symmetric dedup
MATCH p = shortestPath(
    (a)-[:MARRIED_TO|PARENT_OF|SIBLING_OF|PATRON_OF|KNOWS|FREQUENTS|MEMBER_OF*..3]-(b)
)
RETURN elementId(a), a.angkatan, elementId(b), b.angkatan,
       length(p) AS path_length,
       [r IN relationships(p) | type(r)] AS edge_types
ORDER BY path_length ASC
```

### False Positive Modes
- **Geographic proximity**: Officials in the same Kanim may share social circles regardless of angkatan
- **Extended family**: Distant relatives connected through 3 hops may be coincidental
- **Data incompleteness**: Missing angkatan values create blind spots

### Calibration Notes
- `max_path_length=3`: 4+ hops dilute the signal significantly
- `min_angkatan_gap=1`: Set to 3+ for stricter signals (adjacent years may overlap in classes)
- `non_official_edge_types`: Excludes WORKS_AT, POSTED_TO (structural, not suspicious)
- Score = 1/path_length: shorter paths = more anomalous

---

## Pattern 5: Eigenvector Reverse

### What it detects
Nodes with high eigenvector centrality whose ALL 1-hop neighbors have
low eigenvector scores. A "lone hub" pattern indicating deliberate
compartmentalization.

### Why it matters
*Ref: project_osint_layer27_graph_analytics.md — Centrality Algorithms*

Layer 27 defines eigenvector centrality as measuring who is "referenziato
da nodi importanti" (referenced by important nodes). A node that scores
high despite connecting only to unimportant nodes is structurally anomalous:
- A handler controlling low-level operatives who are kept invisible
- A cutout node designed to limit organizational exposure
- A patron whose clients deliberately maintain low profiles

Layer 9 (bapakisme): Patrons may operate through intermediaries with no
visible power, making the patron appear isolated while controlling resources.

### Cypher Query (redacted)
```cypher
-- With GDS eigenvector:
CALL gds.eigenvector.write('anomaly_eigen', {writeProperty: '_eigen', maxIterations: 50})

MATCH (n) WHERE n._eigen >= $high_threshold
MATCH (n)--(neighbor)
WHERE neighbor._eigen IS NOT NULL
WITH n, n._eigen AS node_score,
     collect(neighbor._eigen) AS neighbor_scores,
     count(neighbor) AS num_neighbors
WHERE num_neighbors >= $min_neighbors
  AND all(s IN neighbor_scores WHERE s <= $low_threshold)
RETURN elementId(n), node_score, num_neighbors,
       reduce(acc=0.0, s IN neighbor_scores | acc+s) / num_neighbors AS avg_neighbor
```

### False Positive Modes
- **Leaf nodes**: High-degree leaves connected to one hub get inflated scores
- **Data entry artifacts**: Recently added nodes may have artificially isolated neighborhoods
- **Small graphs**: In sparse graphs, degree-based proxy may produce unreliable eigenvector estimates

### Calibration Notes
- `top_percentile=0.10`: Only examines top 10% of eigenvector scores
- `neighbor_max_percentile=0.25`: "All neighbors low" = below 25th percentile
- `min_neighbors=2`: Filters isolates and single-connection nodes
- Falls back to degree/max_degree proxy if GDS plugin unavailable
