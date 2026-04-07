"""Graph loader — MERGE entities and relationships into Neo4j."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from neo4j import AsyncGraphDatabase

from osint_nexus.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from osint_nexus.resolver.entity_resolver import ResolvedEntity
from osint_nexus.utils.logging import get_logger

logger = get_logger("graph.loader")


class GraphLoader:
    """Loads resolved entities and relationships into Neo4j."""

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
    ) -> None:
        self._driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        self._db = NEO4J_DATABASE

    async def close(self) -> None:
        await self._driver.close()

    async def verify_connectivity(self) -> bool:
        try:
            await self._driver.verify_connectivity()
            logger.info("Neo4j connected: %s", NEO4J_URI)
            return True
        except Exception as e:
            logger.error("Neo4j connection failed: %s", e)
            return False

    # ── Node Operations ──

    async def upsert_official(self, data: dict[str, Any]) -> None:
        """MERGE an Official node by NIP or name."""
        query = """
        MERGE (o:Official {name: $name})
        ON CREATE SET
            o.nip = CASE WHEN $nip <> '' THEN $nip ELSE null END,
            o.jabatan = $jabatan,
            o.kantor = $kantor,
            o.pangkat = $pangkat,
            o.angkatan = $angkatan,
            o.asal = $asal,
            o.agama = $agama,
            o.ttl = $ttl,
            o.created_at = datetime(),
            o.source = $source
        ON MATCH SET
            o.jabatan = CASE WHEN $jabatan <> '' THEN $jabatan ELSE o.jabatan END,
            o.kantor = CASE WHEN $kantor <> '' THEN $kantor ELSE o.kantor END,
            o.pangkat = CASE WHEN $pangkat <> '' THEN $pangkat ELSE o.pangkat END,
            o.nip = CASE WHEN $nip <> '' THEN $nip ELSE o.nip END,
            o.updated_at = datetime()
        """
        params = {
            "name": data.get("name", ""),
            "nip": data.get("nip", ""),
            "jabatan": data.get("jabatan", ""),
            "kantor": data.get("kantor", ""),
            "pangkat": data.get("pangkat", ""),
            "angkatan": data.get("angkatan", ""),
            "asal": data.get("asal", ""),
            "agama": data.get("agama", ""),
            "ttl": data.get("ttl", ""),
            "source": data.get("source", "manual"),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)
            logger.info("Upserted Official: %s", params["name"])

    async def upsert_office(self, data: dict[str, Any]) -> None:
        """MERGE a Kanim_Office node."""
        query = """
        MERGE (k:Kanim_Office {name: $name})
        ON CREATE SET
            k.kota = $kota,
            k.tipe = $tipe,
            k.alamat = $alamat,
            k.created_at = datetime()
        ON MATCH SET
            k.updated_at = datetime()
        """
        params = {
            "name": data.get("name", ""),
            "kota": data.get("kota", ""),
            "tipe": data.get("tipe", ""),
            "alamat": data.get("alamat", ""),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)

    async def upsert_organization(self, data: dict[str, Any]) -> None:
        """MERGE an Organization node."""
        query = """
        MERGE (o:Organization {name: $name})
        ON CREATE SET
            o.tipe = $tipe,
            o.lokasi = $lokasi,
            o.created_at = datetime()
        ON MATCH SET
            o.updated_at = datetime()
        """
        params = {
            "name": data.get("name", ""),
            "tipe": data.get("tipe", ""),
            "lokasi": data.get("lokasi", ""),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)

    async def upsert_tender(self, data: dict[str, Any]) -> None:
        """MERGE a Tender node."""
        query = """
        MERGE (t:Tender {kode: $kode})
        ON CREATE SET
            t.nama_paket = $nama_paket,
            t.instansi = $instansi,
            t.hps = $hps,
            t.tahun = $tahun,
            t.pemenang = $pemenang,
            t.nilai_kontrak = $nilai_kontrak,
            t.created_at = datetime()
        ON MATCH SET
            t.pemenang = CASE WHEN $pemenang <> '' THEN $pemenang ELSE t.pemenang END,
            t.nilai_kontrak = CASE WHEN $nilai_kontrak <> '' THEN $nilai_kontrak ELSE t.nilai_kontrak END,
            t.updated_at = datetime()
        """
        params = {
            "kode": data.get("kode", data.get("nama_paket", "")[:50]),
            "nama_paket": data.get("nama_paket", ""),
            "instansi": data.get("instansi", ""),
            "hps": data.get("hps", ""),
            "tahun": data.get("tahun", ""),
            "pemenang": data.get("pemenang", ""),
            "nilai_kontrak": data.get("nilai_kontrak", ""),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)

    async def upsert_asset(self, data: dict[str, Any]) -> None:
        """MERGE an Asset node."""
        query = """
        MERGE (a:Asset {asset_id: $asset_id})
        ON CREATE SET
            a.name = $name,
            a.tipe = $tipe,
            a.estimated_value = $estimated_value,
            a.source = $source,
            a.created_at = datetime()
        """
        params = {
            "asset_id": data.get("asset_id", data.get("name", "")),
            "name": data.get("name", ""),
            "tipe": data.get("tipe", ""),
            "estimated_value": data.get("estimated_value", ""),
            "source": data.get("source", ""),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)

    async def upsert_person(self, data: dict[str, Any]) -> None:
        """MERGE a generic Person node (non-official)."""
        query = """
        MERGE (p:Person {name: $name})
        ON CREATE SET
            p.person_type = $person_type,
            p.relationship_to_us = $relationship_to_us,
            p.notes = $notes,
            p.created_at = datetime()
        ON MATCH SET
            p.updated_at = datetime()
        """
        params = {
            "name": data.get("name", ""),
            "person_type": data.get("person_type", "contact"),
            "relationship_to_us": data.get("relationship_to_us", ""),
            "notes": data.get("notes", ""),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)

    # ── Relationship Operations ──

    async def create_relationship(
        self,
        from_name: str,
        from_label: str,
        to_name: str,
        to_label: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create or update a relationship between two nodes."""
        props = properties or {}
        props["updated_at"] = datetime.now(timezone.utc).isoformat()

        prop_string = ", ".join(f"r.{k} = ${k}" for k in props)
        query = f"""
        MATCH (a:{from_label} {{name: $from_name}})
        MATCH (b:{to_label} {{name: $to_name}})
        MERGE (a)-[r:{rel_type}]->(b)
        SET {prop_string}
        """
        params = {"from_name": from_name, "to_name": to_name, **props}
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)
            logger.info(
                "Relationship: %s -[%s]-> %s", from_name, rel_type, to_name
            )

    # ── Bulk Operations ──

    async def load_resolved_entities(self, entities: list[ResolvedEntity]) -> int:
        """Load a batch of resolved entities into Neo4j."""
        count = 0
        for entity in entities:
            props = dict(entity.properties)
            props["name"] = entity.canonical_name
            props["source"] = props.get("source", entity.match_method)

            if entity.entity_type == "person":
                if props.get("nip") or props.get("jabatan"):
                    await self.upsert_official(props)
                else:
                    await self.upsert_person(props)
            elif entity.entity_type == "organization":
                await self.upsert_organization(props)
            elif entity.entity_type == "tender":
                await self.upsert_tender(props)

            count += 1

        logger.info("Loaded %d entities into Neo4j", count)
        return count

    async def get_node_count(self) -> dict[str, int]:
        """Get count of all node types."""
        query = """
        CALL {
            MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt
        }
        RETURN label, cnt ORDER BY cnt DESC
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.run(query)
            return {r["label"]: r["cnt"] async for r in result}
