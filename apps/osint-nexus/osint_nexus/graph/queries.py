"""Tactical Neo4j queries — pathfinding, anomaly detection, power scoring."""

from __future__ import annotations

from typing import Any

from osint_nexus.utils.logging import get_logger

logger = get_logger("graph.queries")


class TacticalQueries:
    """Pre-built intelligence queries against the OSINT graph."""

    def __init__(self, driver, database: str = "neo4j") -> None:
        self._driver = driver
        self._db = database

    async def shortest_path(
        self, from_name: str, to_name: str, max_hops: int = 6
    ) -> list[dict[str, Any]]:
        """Find shortest path between any two entities."""
        query = f"""
        MATCH (a {{name: $from_name}}), (b {{name: $to_name}})
        MATCH p = shortestPath((a)-[*..{max_hops}]-(b))
        RETURN [n IN nodes(p) | {{name: n.name, labels: labels(n)}}] AS nodes,
               [r IN relationships(p) | {{type: type(r), props: properties(r)}}] AS rels,
               length(p) AS hops
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(
                query, {"from_name": from_name, "to_name": to_name}
            )
            return [dict(r) async for r in result]

    async def all_paths(
        self, from_name: str, to_name: str, max_hops: int = 6
    ) -> list[dict[str, Any]]:
        """Find all paths (up to max_hops) between two entities."""
        query = f"""
        MATCH (a {{name: $from_name}}), (b {{name: $to_name}})
        MATCH p = allShortestPaths((a)-[*..{max_hops}]-(b))
        RETURN [n IN nodes(p) | {{name: n.name, labels: labels(n)}}] AS nodes,
               [r IN relationships(p) | type(r)] AS rel_types,
               length(p) AS hops
        ORDER BY hops
        LIMIT 10
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(
                query, {"from_name": from_name, "to_name": to_name}
            )
            return [dict(r) async for r in result]

    async def approachability(self, target_name: str) -> list[dict[str, Any]]:
        """Find shared interests and bridge persons to approach a target."""
        query = """
        MATCH (t:Official {name: $name})-[:ENJOYS|MEMBER_OF|FREQUENTS|ACTIVE_IN]->(i)
        OPTIONAL MATCH (b:Person)-[:ENJOYS|MEMBER_OF|FREQUENTS|ACTIVE_IN]->(i)
        WHERE b <> t AND b.relationship_to_us IS NOT NULL
        RETURN t.name AS target, i.name AS shared_interest,
               labels(i)[0] AS interest_type,
               b.name AS bridge_person,
               b.relationship_to_us AS our_connection
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, {"name": target_name})
            return [dict(r) async for r in result]

    async def financial_anomaly(
        self, threshold_multiplier: float = 15.0,
    ) -> list[dict[str, Any]]:
        """Detect officials with assets >> declared LHKPN income."""
        query = """
        MATCH (o:Official)-[:OWNS]->(a:Asset)
        WHERE a.estimated_value IS NOT NULL AND o.lhkpn_total IS NOT NULL
           AND toFloat(a.estimated_value) > toFloat(o.lhkpn_total) * $threshold
        RETURN o.name AS official, o.jabatan AS jabatan,
               a.name AS asset, a.estimated_value AS asset_value,
               o.lhkpn_total AS declared,
               toFloat(a.estimated_value) / toFloat(o.lhkpn_total) AS ratio
        ORDER BY ratio DESC
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, {"threshold": threshold_multiplier})
            return [dict(r) async for r in result]

    async def procurement_ring(self) -> list[dict[str, Any]]:
        """Detect vendor-official family connections in tenders."""
        query = """
        MATCH (v:Local_Vendor)-[:WON_CONTRACT]->(t:Tender)
        MATCH (t)-[:AWARDED_BY]->(k:Kanim_Office)
        MATCH (o:Official)-[:WORKS_AT]->(k)
        MATCH (v)-[:OWNED_BY|CONTROLS]->()<-[:MARRIED_TO|PARENT_OF|SIBLING_OF]-(o)
        RETURN o.name AS official, o.jabatan AS jabatan,
               v.name AS vendor, t.nama_paket AS tender,
               t.nilai_kontrak AS value
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query)
            return [dict(r) async for r in result]

    async def rapid_promotion(self, months: int = 6) -> list[dict[str, Any]]:
        """Find officials promoted suspiciously fast after a new boss arrives."""
        query = """
        MATCH (o:Official)-[p:PROMOTED_TO]->(pos)
        MATCH (boss:Official)-[a:POSTED_TO]->(pos2)
        WHERE pos.kantor = pos2.kantor
          AND duration.between(date(a.date), date(p.date)).months < $months
          AND o.angkatan = boss.angkatan
          AND o <> boss
        RETURN o.name AS promoted, boss.name AS new_boss,
               o.angkatan AS angkatan, p.date AS promotion_date,
               a.date AS boss_arrival
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, {"months": months})
            return [dict(r) async for r in result]

    async def notaris_hub(self, min_connections: int = 2) -> list[dict[str, Any]]:
        """Find notaries creating companies for multiple officials' families."""
        query = """
        MATCH (n:Notaris)-[:CREATED]->(pt)
        MATCH (pt)<-[:OWNS|CONTROLS]-(p:Person)
        MATCH (p)-[:MARRIED_TO|PARENT_OF|SIBLING_OF]-(o:Official)
        WITH n, collect(DISTINCT o.name) AS officials, collect(DISTINCT pt.name) AS companies
        WHERE size(officials) >= $min
        RETURN n.name AS notaris, officials, companies, size(officials) AS official_count
        ORDER BY official_count DESC
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, {"min": min_connections})
            return [dict(r) async for r in result]

    async def power_score(self, name: str) -> dict[str, Any]:
        """Calculate a power/influence score for an official."""
        query = """
        MATCH (o:Official {name: $name})
        OPTIONAL MATCH (o)-[r]-(connected)
        WITH o, count(r) AS degree,
             count(CASE WHEN type(r) IN ['WORKS_AT', 'POSTED_TO'] THEN 1 END) AS positions,
             count(CASE WHEN type(r) IN ['KNOWS', 'MET_WITH', 'ATTENDED'] THEN 1 END) AS social,
             count(CASE WHEN type(r) IN ['OWNS', 'CONTROLS'] THEN 1 END) AS assets
        RETURN o.name AS name, o.jabatan AS jabatan, o.kantor AS kantor,
               degree, positions, social, assets,
               degree * 1.0 + positions * 2.0 + social * 0.5 + assets * 1.5 AS power_score
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, {"name": name})
            record = await result.single()
            return dict(record) if record else {}

    async def network_map(self, name: str, depth: int = 2) -> list[dict[str, Any]]:
        """Get full network around an entity up to N hops."""
        query = f"""
        MATCH (center {{name: $name}})
        MATCH p = (center)-[*1..{depth}]-(connected)
        UNWIND nodes(p) AS n
        UNWIND relationships(p) AS r
        WITH DISTINCT n, r
        RETURN collect(DISTINCT {{name: n.name, labels: labels(n), jabatan: n.jabatan}}) AS nodes,
               collect(DISTINCT {{from: startNode(r).name, to: endNode(r).name, type: type(r)}}) AS edges
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query, {"name": name})
            record = await result.single()
            return dict(record) if record else {"nodes": [], "edges": []}
