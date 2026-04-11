"""Angkatan-disjoint alliance detector.

Justification
-------------
Memory cite: ``project_osint_layer9_power_topology.md``, Informal
Power section — "Angkatan (Polimigras Depok): stessa angkatan =
fratellanza a vita, loyalty cross-ufficio" and "Kakanwil mutasi →
entro 6 mesi i loyalis vengono promossi/spostati. Pattern detection:
SK mutasi post-mutasi Kakanwil, chi si muove entro 6 mesi = kelompok".

Corollary: because the angkatan cohort is the primary loyalty unit,
short links between officials from *different* cohorts are expected
to exist only via the formal hierarchy (POSTED_TO / PROMOTED_TO /
WORKS_AT). If two officials from different angkatan appear to be
linked in ≤3 hops via **non-official** edges (family ties, social
events, mutual acquaintances), this is statistically unusual and
worth flagging — it's either:

* a family-based alliance bridging cohorts (strong tie),
* a patron-client arrangement hidden in social edges, or
* a covert alignment worth naming.

None of these are visible in the formal structure, which is the
whole point of OSINT graph analysis.

False positive mitigation
-------------------------
1. ``min_angkatan_gap`` — ignore near-cohorts (gap < 3 years) because
   those effectively share a cohort for loyalty purposes.
2. ``max_path_len`` — longer paths are too weak a signal.
3. The non-official rel list excludes WORKS_AT/POSTED_TO/PROMOTED_TO
   at query time so the whole path must traverse "human" edges.
4. Symmetric-pair dedupe on (min, max) of the pair ID.
5. Evidence path shows the full path node IDs so the analyst can
   judge whether the bridge is meaningful.

Data requirements
-----------------
* ``Official.angkatan`` must be set (scraped from bio / pelantikan
  news). Officials without angkatan are skipped.
* At least one non-official edge must exist in the graph between
  them. The detector is silent on a graph that only has formal
  hierarchy edges.

Cypher strategy
---------------
```cypher
// angkatan_disjoint_pairs — composite query
MATCH (a:Official), (b:Official)
WHERE a.angkatan IS NOT NULL AND a.angkatan <> ''
  AND b.angkatan IS NOT NULL AND b.angkatan <> ''
  AND toInteger(a.angkatan) < toInteger(b.angkatan)
  AND abs(toInteger(a.angkatan) - toInteger(b.angkatan)) >= $min_gap
MATCH p = shortestPath(
  (a)-[rels:KNOWS|MET_WITH|MARRIED_TO|PARENT_OF|SIBLING_OF|FREQUENTS*..$max]-(b)
)
WHERE none(r IN rels WHERE type(r) IN ['WORKS_AT','POSTED_TO','PROMOTED_TO'])
WITH a, b, p
RETURN toString(elementId(a)) AS a_id,
       toString(elementId(b)) AS b_id,
       toInteger(a.angkatan) AS a_angkatan,
       toInteger(b.angkatan) AS b_angkatan,
       abs(toInteger(a.angkatan) - toInteger(b.angkatan)) AS gap,
       length(p) AS path_len,
       [r IN relationships(p) | type(r)] AS path_rel_types,
       [n IN nodes(p) | toString(elementId(n))] AS path_node_ids
```
"""

from __future__ import annotations

from typing import Any

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector, SessionLike
from osint_nexus.anomaly.thresholds import DEFAULT_THRESHOLDS


class AngkatanDisjointDetector(Detector):
    name = "angkatan_disjoint"

    @classmethod
    def default_thresholds(cls) -> dict[str, Any]:
        return dict(DEFAULT_THRESHOLDS["angkatan_disjoint"])

    _PAIR_Q_TEMPLATE = """
    // angkatan_disjoint_pairs — composite query
    MATCH (a:Official), (b:Official)
    WHERE a.angkatan IS NOT NULL AND toString(a.angkatan) <> ''
      AND b.angkatan IS NOT NULL AND toString(b.angkatan) <> ''
      AND toInteger(a.angkatan) < toInteger(b.angkatan)
      AND abs(toInteger(a.angkatan) - toInteger(b.angkatan)) >= $min_gap
    WITH a, b
    LIMIT 500
    MATCH p = shortestPath(
      (a)-[rels:{rel_union}*..{max_hops}]-(b)
    )
    WHERE none(r IN relationships(p) WHERE type(r) IN ['WORKS_AT','POSTED_TO','PROMOTED_TO'])
    RETURN toString(elementId(a)) AS a_id,
           toString(elementId(b)) AS b_id,
           toInteger(a.angkatan) AS a_angkatan,
           toInteger(b.angkatan) AS b_angkatan,
           abs(toInteger(a.angkatan) - toInteger(b.angkatan)) AS gap,
           length(p) AS path_len,
           [r IN relationships(p) | type(r)] AS path_rel_types,
           [n IN nodes(p) | coalesce(toString(elementId(n)), toString(id(n)))] AS path_node_ids
    """

    def _build_query(self) -> str:
        rels: list[str] = list(self._thresholds.get("non_official_rels", []))
        rel_union = "|".join(rels) if rels else "KNOWS|MET_WITH"
        max_hops = int(self._thresholds.get("max_path_len", 3))
        return self._PAIR_Q_TEMPLATE.format(rel_union=rel_union, max_hops=max_hops)

    def run(self, session: SessionLike) -> list[Alert]:
        if session is None:
            return []

        th = self._thresholds
        min_gap = int(th.get("min_angkatan_gap", 3))
        max_path = int(th.get("max_path_len", 3))
        min_score = float(th.get("min_score", 0.6))

        query = self._build_query()
        records = list(session.run(query, {"min_gap": min_gap}))
        if not records:
            return []

        seen: set[tuple[str, str]] = set()
        alerts: list[Alert] = []
        for rec in records:
            a_id = str(rec["a_id"])
            b_id = str(rec["b_id"])
            pair = tuple(sorted((a_id, b_id)))
            if pair in seen:
                continue
            seen.add(pair)

            gap = int(rec.get("gap") or 0)
            if gap < min_gap:
                continue
            path_len = int(rec.get("path_len") or 0)
            if path_len == 0 or path_len > max_path:
                continue

            # Score combines "gap size" and "path shortness". Large gap
            # + very short path → ~1.0. Small gap + long path → low.
            gap_factor = min(1.0, gap / 10.0)
            path_factor = 1.0 - (path_len - 1) / max(max_path, 1)
            score = (gap_factor + path_factor) / 2.0
            if score < min_score:
                continue

            path_node_ids = [str(n) for n in rec.get("path_node_ids", []) if n]
            path_rel_types = list(rec.get("path_rel_types", []))
            confidence = 0.5 + 0.1 * min(5, len(path_rel_types))
            primary = f"{pair[0]}~{pair[1]}"

            alerts.append(
                self._mk_alert(
                    primary_entity_id=primary,
                    score=score,
                    confidence=min(1.0, confidence),
                    evidence_path=path_node_ids,
                    rationale_id=f"AD-GAP{gap}-PATH{path_len}",
                )
            )
        return alerts
