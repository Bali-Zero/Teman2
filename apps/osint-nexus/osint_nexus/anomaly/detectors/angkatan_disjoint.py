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
to exist only via the formal hierarchy (WORKS_AT / GOVERNED_DURING /
SUPERVISES / COMMANDS / ...). If two officials from different
angkatan appear to be linked in <= max_path_len hops via
**non-official** edges (family ties, social events, mutual
acquaintances), this is statistically unusual and worth flagging —
it's either:

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
3. The non-official rel list excludes the OFFICIAL family of rel
   types at query time so the whole path must traverse "human" edges.
4. Symmetric-pair dedupe on (min, max) of the pair ID.
5. Evidence path shows the full path node IDs so the analyst can
   judge whether the bridge is meaningful.

Data precondition
-----------------
The live Kemenkumham schema as of Apr 2026 has 170 :Official nodes
with ``angkatan`` set — all to the same integer (2000). With
``min_angkatan_gap >= 3`` the pair query is empty by construction, so
the detector produces zero alerts not because no cross-cohort ties
exist, but because the cohort data simply hasn't been scraped yet.
We surface this as an informational alert via ``precheck`` so the
operator can tell the two states apart.

Relationship-type families
--------------------------
Derived from the REAL live graph (see ``thresholds._FAMILY_REL_TYPES``
and ``thresholds._SOCIAL_REL_TYPES``). The OLD hard-coded list
(``KNOWS``, ``SIBLING_OF``, ``FREQUENTS``) referenced rel types that
do not exist in the graph — the detector silently matched nothing.

Cypher strategy
---------------
```cypher
MATCH (a:Official), (b:Official)
WHERE a.angkatan IS NOT NULL AND a.angkatan <> ''
  AND b.angkatan IS NOT NULL AND b.angkatan <> ''
  AND toInteger(a.angkatan) < toInteger(b.angkatan)
  AND abs(toInteger(a.angkatan) - toInteger(b.angkatan)) >= $min_gap
MATCH p = shortestPath(
  (a)-[rels:<rel_union>*..$max]-(b)
)
WHERE none(r IN rels WHERE type(r) IN $official_rels)
WITH a, b, p
RETURN ...
```
"""

from __future__ import annotations

from typing import Any

from osint_nexus.anomaly.alert import Alert
from osint_nexus.anomaly.base import Detector, PreconditionResult, SessionLike
from osint_nexus.anomaly.thresholds import DEFAULT_THRESHOLDS


class AngkatanDisjointDetector(Detector):
    name = "angkatan_disjoint"

    @classmethod
    def default_thresholds(cls) -> dict[str, Any]:
        return dict(DEFAULT_THRESHOLDS["angkatan_disjoint"])

    _PRECHECK_Q = """
    // angkatan_disjoint_precheck — distinct cohorts + spread
    MATCH (n:Official) WHERE n.angkatan IS NOT NULL
    RETURN count(DISTINCT toInteger(n.angkatan)) AS distinct_years,
           min(toInteger(n.angkatan)) AS min_y,
           max(toInteger(n.angkatan)) AS max_y,
           count(n) AS total_officials
    """

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
    WHERE none(r IN relationships(p) WHERE type(r) IN $official_rels)
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
        rel_union = "|".join(rels) if rels else "MET_WITH|MARRIED_TO"
        max_hops = int(self._thresholds.get("max_path_len", 3))
        return self._PAIR_Q_TEMPLATE.format(rel_union=rel_union, max_hops=max_hops)

    def precheck(self, session: SessionLike) -> PreconditionResult:
        """Verify there is enough angkatan variance to run the pair query."""
        if session is None:  # pragma: no cover - runner never passes None here
            return PreconditionResult.success()
        min_gap = int(self._thresholds.get("min_angkatan_gap", 3))
        try:
            records = list(session.run(self._PRECHECK_Q))
        except Exception as exc:  # pragma: no cover - defensive
            return PreconditionResult(
                ok=False,
                reason=f"precheck query failed: {type(exc).__name__}",
                stat={"error": type(exc).__name__},
            )
        if not records:
            return PreconditionResult(
                ok=False,
                reason="no Official nodes with angkatan",
                stat={
                    "distinct_years": 0,
                    "total_officials": 0,
                    "min_angkatan_gap": min_gap,
                },
            )
        rec = records[0]
        distinct_years = int(rec.get("distinct_years") or 0)
        total_officials = int(rec.get("total_officials") or 0)
        min_y = rec.get("min_y")
        max_y = rec.get("max_y")
        spread = 0
        if min_y is not None and max_y is not None:
            spread = int(max_y) - int(min_y)
        stat = {
            "distinct_years": distinct_years,
            "total_officials": total_officials,
            "min_y": int(min_y) if min_y is not None else None,
            "max_y": int(max_y) if max_y is not None else None,
            "spread": spread,
            "min_angkatan_gap": min_gap,
        }
        if distinct_years < 2:
            return PreconditionResult(
                ok=False,
                reason=(
                    f"angkatan variance too low: {distinct_years} distinct years, "
                    f"spread {spread}"
                ),
                stat=stat,
            )
        if spread < min_gap:
            return PreconditionResult(
                ok=False,
                reason=(
                    f"angkatan variance too low: {distinct_years} distinct years, "
                    f"spread {spread}"
                ),
                stat=stat,
            )
        return PreconditionResult(ok=True, stat=stat)

    def run(self, session: SessionLike) -> list[Alert]:
        if session is None:
            return []

        th = self._thresholds
        min_gap = int(th.get("min_angkatan_gap", 3))
        max_path = int(th.get("max_path_len", 3))
        min_score = float(th.get("min_score", 0.6))
        official_rels = list(th.get("official_rels", []))

        query = self._build_query()
        records = list(session.run(
            query,
            {"min_gap": min_gap, "official_rels": official_rels},
        ))
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
