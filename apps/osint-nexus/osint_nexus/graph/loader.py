"""Graph loader — MERGE entities and relationships into Neo4j."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from neo4j import AsyncGraphDatabase

from osint_nexus.config import NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from osint_nexus.parsers.lhkpn_parser import LhkpnReport
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

    # ── LHKPN Asset Nodes ──

    async def upsert_property(self, data: dict[str, Any]) -> None:
        """MERGE a Property node by property_id."""
        query = """
        MERGE (p:Property {property_id: $property_id})
        ON CREATE SET
            p.lokasi = $lokasi,
            p.luas_tanah_m2 = $luas_tanah_m2,
            p.luas_bangunan_m2 = $luas_bangunan_m2,
            p.tipe = $tipe,
            p.created_at = datetime(),
            p.source = 'lhkpn'
        ON MATCH SET
            p.updated_at = datetime()
        """
        params = {
            "property_id": data["property_id"],
            "lokasi": data.get("lokasi", ""),
            "luas_tanah_m2": data.get("luas_tanah_m2", 0),
            "luas_bangunan_m2": data.get("luas_bangunan_m2", 0),
            "tipe": data.get("tipe", ""),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)
            logger.info("Upserted Property: %s (%s)", params["lokasi"], params["property_id"][:12])

    async def upsert_vehicle(self, data: dict[str, Any]) -> None:
        """MERGE a Vehicle node by vehicle_id."""
        query = """
        MERGE (v:Vehicle {vehicle_id: $vehicle_id})
        ON CREATE SET
            v.jenis = $jenis,
            v.merk_model = $merk_model,
            v.tahun_perolehan = $tahun_perolehan,
            v.created_at = datetime(),
            v.source = 'lhkpn'
        ON MATCH SET
            v.updated_at = datetime()
        """
        params = {
            "vehicle_id": data["vehicle_id"],
            "jenis": data.get("jenis", ""),
            "merk_model": data.get("merk_model", ""),
            "tahun_perolehan": data.get("tahun_perolehan", 0),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)
            logger.info("Upserted Vehicle: %s %s", params["jenis"], params["merk_model"])

    async def upsert_bank_account(self, data: dict[str, Any]) -> None:
        """MERGE a BankAccount node by account_id."""
        query = """
        MERGE (b:BankAccount {account_id: $account_id})
        ON CREATE SET
            b.tipe = $tipe,
            b.created_at = datetime(),
            b.source = 'lhkpn'
        ON MATCH SET
            b.updated_at = datetime()
        """
        params = {
            "account_id": data["account_id"],
            "tipe": data.get("tipe", "kas_setara_kas"),
        }
        async with self._driver.session(database=self._db) as session:
            await session.run(query, params)
            logger.info("Upserted BankAccount: %s", params["account_id"][:12])

    # ── LHKPN Report Loader ──

    async def load_lhkpn_report(self, report: LhkpnReport) -> int:
        """Load a complete LHKPN report into Neo4j.

        Upserts the Official node, all asset nodes (Property, Vehicle,
        BankAccount), and creates OWNS relationships between them.

        Returns the count of asset nodes created/updated.
        """
        asset_count = 0

        # KPK PDFs use UPPERCASE names; normalize to title case so
        # "BUGIE KURNIAWAN" merges with existing "Bugie Kurniawan".
        official_name = report.nama.title()

        # 1. Upsert Official
        await self.upsert_official({
            "name": official_name,
            "jabatan": report.jabatan,
            "source": "lhkpn",
        })

        # 2. Properties
        rel_props = {
            "tahun": report.tahun,
            "source": "lhkpn",
        }
        for prop in report.tanah_bangunan:
            await self.upsert_property({
                "property_id": prop.property_id,
                "lokasi": prop.lokasi,
                "luas_tanah_m2": prop.luas_tanah_m2,
                "luas_bangunan_m2": prop.luas_bangunan_m2,
                "tipe": prop.tipe,
            })
            await self.create_relationship(
                from_name=official_name,
                from_label="Official",
                to_name="",
                to_label="Property",
                rel_type="OWNS",
                properties={
                    **rel_props,
                    "nilai": prop.nilai,
                    "sumber": prop.sumber,
                },
                match_by_id=("property_id", prop.property_id),
            )
            asset_count += 1

        # 3. Vehicles
        for v in report.kendaraan:
            await self.upsert_vehicle({
                "vehicle_id": v.vehicle_id,
                "jenis": v.jenis,
                "merk_model": v.merk_model,
                "tahun_perolehan": v.tahun_perolehan,
            })
            await self.create_relationship(
                from_name=official_name,
                from_label="Official",
                to_name="",
                to_label="Vehicle",
                rel_type="OWNS",
                properties={
                    **rel_props,
                    "nilai": v.nilai,
                    "sumber": v.sumber,
                },
                match_by_id=("vehicle_id", v.vehicle_id),
            )
            asset_count += 1

        # 4. Cash (BankAccount) — only if kas > 0
        if report.kas > 0:
            account_id = hashlib.sha256(
                f"{official_name}|kas_setara_kas".encode()
            ).hexdigest()[:16]
            await self.upsert_bank_account({
                "account_id": account_id,
                "tipe": "kas_setara_kas",
            })
            await self.create_relationship(
                from_name=official_name,
                from_label="Official",
                to_name="",
                to_label="BankAccount",
                rel_type="OWNS",
                properties={
                    **rel_props,
                    "nilai": report.kas,
                    "sumber": "",
                },
                match_by_id=("account_id", account_id),
            )
            asset_count += 1

        logger.info(
            "Loaded LHKPN report: %s (%d) — %d asset nodes",
            official_name, report.tahun, asset_count,
        )
        return asset_count

    # ── Relationship Operations ──

    async def create_relationship(
        self,
        from_name: str,
        from_label: str,
        to_name: str,
        to_label: str,
        rel_type: str,
        properties: dict[str, Any] | None = None,
        match_by_id: tuple[str, str] | None = None,
    ) -> None:
        """Create or update a relationship between two nodes.

        Drops self-loops (from_name == to_name) to avoid NER noise,
        only when matching by name (match_by_id is None).

        Args:
            match_by_id: Optional (id_field, id_value) tuple. When provided,
                the target node is matched by that ID field instead of name.
        """
        if match_by_id is None and from_name.strip().lower() == to_name.strip().lower():
            logger.debug("Skipping self-loop: %s -[%s]-> %s",
                         from_name, rel_type, to_name)
            return

        props = properties or {}
        props["updated_at"] = datetime.now(timezone.utc).isoformat()

        prop_string = ", ".join(f"r.{k} = ${k}" for k in props)

        # If tahun is in properties, include it in MERGE to create per-year rels
        merge_props = ""
        if "tahun" in props:
            merge_props = " {tahun: $tahun}"

        if match_by_id:
            id_field, id_value = match_by_id
            query = f"""
            MATCH (a:{from_label} {{name: $from_name}})
            MATCH (b:{to_label} {{{id_field}: $to_id}})
            MERGE (a)-[r:{rel_type}{merge_props}]->(b)
            SET {prop_string}
            """
            params = {"from_name": from_name, "to_id": id_value, **props}
        else:
            query = f"""
            MATCH (a:{from_label} {{name: $from_name}})
            MATCH (b:{to_label} {{name: $to_name}})
            MERGE (a)-[r:{rel_type}{merge_props}]->(b)
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
