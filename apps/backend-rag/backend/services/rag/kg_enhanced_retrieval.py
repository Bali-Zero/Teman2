"""
Knowledge Graph Enhanced Retrieval Service

Enhances RAG retrieval by:
1. Extracting entities from user query
2. Finding related entities in KG (1-2 hops)
3. Retrieving source chunks linked to those entities
4. Augmenting context with structured graph knowledge
"""

import logging
import re
from dataclasses import dataclass

import asyncpg

logger = logging.getLogger(__name__)


@dataclass
class KGContext:
    """Context from Knowledge Graph for RAG augmentation"""

    entities_found: list[dict]
    relationships: list[dict]
    source_chunk_ids: list[str]
    graph_summary: str
    confidence: float


class KGEnhancedRetrieval:
    """
    Service for KG-enhanced RAG retrieval.

    Usage in orchestrator:
        kg_context = await kg_retrieval.get_context_for_query(query)
        # Add kg_context.graph_summary to system prompt
        # Use kg_context.source_chunk_ids for chunk retrieval
    """

    # Common Indonesian legal/business entity patterns
    # Expanded Dec 2025 for better KG coverage
    ENTITY_PATTERNS = [
        # === LAWS AND REGULATIONS ===
        (r"UU\s*(?:No\.?\s*)?\d+(?:\s*(?:Tahun|/)?\s*\d{4})?", "undang_undang"),
        (r"PP\s*(?:No\.?\s*)?\d+(?:\s*(?:Tahun|/)?\s*\d{4})?", "peraturan_pemerintah"),
        (r"Perpres\s*(?:No\.?\s*)?\d+", "perpres"),
        (r"Permen\s*(?:No\.?\s*)?\d+", "permen"),
        (r"Perda\s*(?:No\.?\s*)?\d+", "perda"),
        (r"Perka\s*(?:No\.?\s*)?\d+", "perka"),  # Peraturan Kepala
        (r"Keppres\s*(?:No\.?\s*)?\d+", "keppres"),  # Keputusan Presiden
        (r"Kepmen\s*(?:No\.?\s*)?\d+", "kepmen"),  # Keputusan Menteri
        (r"Pasal\s+\d+", "pasal"),  # Article references
        # === BUSINESS CODES ===
        (r"KBLI\s*\d{5}", "kbli"),
        (r"NIB\s*\d+", "nib"),
        (r"NIB", "nib"),
        # === COMPANY TYPES ===
        (r"PT\s+PMA", "pt_pma"),
        (r"PT\s+PMDN", "pt_pmdn"),
        (r"PT\s+Perorangan", "pt_perorangan"),
        (r"(?:perusahaan|company)\s+(?:asing|foreign)", "pt_pma"),
        (r"(?:CV|Firma|Koperasi|Yayasan)", "badan_usaha"),
        (r"badan\s+hukum", "badan_hukum"),
        # === PERMITS AND LICENSES ===
        (r"OSS", "oss"),
        (r"SIUP", "siup"),
        (r"TDP", "tdp"),
        (r"NPWP", "npwp"),
        (r"IMB", "imb"),  # Izin Mendirikan Bangunan
        (r"AMDAL", "amdal"),  # Analisis Dampak Lingkungan
        (r"izin\s+(?:usaha|lokasi|lingkungan|prinsip)", "izin_usaha"),
        (r"izin\s+tinggal", "izin_tinggal"),
        (r"sertifikat\s+standar", "sertifikat"),
        # === VISAS AND IMMIGRATION ===
        (r"KITAS", "kitas"),
        (r"KITAP", "kitap"),
        (r"VITAS", "vitas"),
        (r"E-?VISA", "evisa"),
        (r"ITAS", "kitas"),  # Without K prefix
        (r"(?:visa\s+)?(?:kerja|work)", "kitas"),
        (r"RPTKA", "rptka"),
        (r"IMTA", "imta"),
        (r"TKA", "tka"),  # Tenaga Kerja Asing
        (r"tenaga\s+kerja\s+asing", "tka"),
        (r"imigrasi", "imigrasi"),
        (r"paspor", "paspor"),
        # === TAX TYPES ===
        (r"PPh\s*(?:Pasal\s*)?\d+", "pph"),
        (r"PPh\s*21", "pph_21"),
        (r"PPh\s*23", "pph_23"),
        (r"PPh\s*25", "pph_25"),
        (r"PPh\s*29", "pph_29"),
        (r"PPN", "ppn"),
        (r"PBB", "pbb"),
        (r"Bea\s+Materai", "bea_materai"),
        (r"pajak\s+(?:penghasilan|pertambahan)", "tax"),
        (r"faktur\s+pajak", "faktur_pajak"),
        (r"SPT", "spt"),
        # === PROCEDURES ===
        (r"pendaftaran", "pendaftaran"),
        (r"permohonan", "permohonan"),
        (r"perpanjangan", "perpanjangan"),
        (r"pencabutan", "pencabutan"),
        (r"perubahan", "perubahan"),
        # === SANCTIONS ===
        (r"sanksi\s+(?:administratif|pidana)", "sanksi"),
        (r"denda", "denda"),
        # === COSTS AND FEES ===
        (r"biaya", "biaya"),
        (r"tarif", "biaya"),
        (r"retribusi", "biaya"),
        (r"(?:Rp\.?\s*)?[\d.,]+(?:\s*(?:juta|ribu|miliar))?", "amount"),  # Money amounts
        # === TIME PERIODS ===
        (r"\d+\s*(?:hari|bulan|tahun)", "jangka_waktu"),
        (r"jangka\s+waktu", "jangka_waktu"),
    ]

    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize KG Enhanced Retrieval.

        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool
        logger.info("KGEnhancedRetrieval initialized")

    def extract_entities_from_query(self, query: str) -> list[tuple[str, str]]:
        """
        Extract potential entity mentions from user query.

        Returns:
            List of (mention, entity_type) tuples
        """
        entities = []
        query_upper = query.upper()

        for pattern, entity_type in self.ENTITY_PATTERNS:
            matches = re.finditer(pattern, query_upper, re.IGNORECASE)
            for match in matches:
                mention = match.group(0).strip()
                entities.append((mention, entity_type))

        # Deduplicate while preserving order
        seen = set()
        unique_entities = []
        for e in entities:
            if e[0] not in seen:
                seen.add(e[0])
                unique_entities.append(e)

        return unique_entities

    async def find_kg_entities(
        self, mentions: list[tuple[str, str]], limit_per_mention: int = 3
    ) -> list[dict]:
        """
        Find KG entities matching the extracted mentions.

        Uses fuzzy matching on entity name.
        """
        if not mentions:
            return []

        found_entities = []

        async with self.db_pool.acquire() as conn:
            for mention, entity_type in mentions:
                # Normalize mention for search
                search_term = mention.replace(".", "").replace(" ", "%").lower()

                # Search by name similarity and optionally by type
                rows = await conn.fetch(
                    """
                    SELECT entity_id, entity_type, name, confidence,
                           source_chunk_ids
                    FROM kg_nodes
                    WHERE LOWER(name) LIKE $1
                       OR entity_type = $2
                    ORDER BY confidence DESC
                    LIMIT $3
                """,
                    f"%{search_term}%",
                    entity_type,
                    limit_per_mention,
                )

                for row in rows:
                    entity = dict(row)
                    entity["matched_mention"] = mention
                    found_entities.append(entity)

        return found_entities

    async def get_related_entities(
        self, entity_ids: list[str], max_depth: int = 1, limit: int = 20
    ) -> tuple[list[dict], list[dict]]:
        """
        Get entities related to the given entities via KG edges.

        Returns:
            Tuple of (related_entities, relationships)
        """
        if not entity_ids:
            return [], []

        related_entities = []
        relationships = []
        visited_entity_ids = set(entity_ids)

        async with self.db_pool.acquire() as conn:
            frontier = entity_ids

            for depth in range(max_depth):
                if not frontier:
                    break

                # Get edges connected to frontier
                edges = await conn.fetch(
                    """
                    SELECT e.relationship_id, e.source_entity_id, e.target_entity_id,
                           e.relationship_type, e.confidence, e.source_chunk_ids,
                           s.name as source_name, s.entity_type as source_type,
                           t.name as target_name, t.entity_type as target_type
                    FROM kg_edges e
                    JOIN kg_nodes s ON e.source_entity_id = s.entity_id
                    JOIN kg_nodes t ON e.target_entity_id = t.entity_id
                    WHERE e.source_entity_id = ANY($1) OR e.target_entity_id = ANY($1)
                    ORDER BY e.confidence DESC
                    LIMIT $2
                """,
                    frontier,
                    limit,
                )

                next_frontier = []
                for edge in edges:
                    edge_dict = dict(edge)
                    relationships.append(edge_dict)

                    # Collect new entity IDs for next hop
                    for eid in [edge_dict["source_entity_id"], edge_dict["target_entity_id"]]:
                        if eid not in visited_entity_ids:
                            visited_entity_ids.add(eid)
                            next_frontier.append(eid)

                frontier = next_frontier

            # Fetch details of related entities
            if visited_entity_ids - set(entity_ids):
                new_ids = list(visited_entity_ids - set(entity_ids))
                rows = await conn.fetch(
                    """
                    SELECT entity_id, entity_type, name, confidence, source_chunk_ids
                    FROM kg_nodes
                    WHERE entity_id = ANY($1)
                """,
                    new_ids,
                )
                related_entities = [dict(r) for r in rows]

        return related_entities, relationships

    async def get_source_chunks(self, entity_ids: list[str]) -> list[str]:
        """
        Get all source chunk IDs linked to the given entities.
        """
        if not entity_ids:
            return []

        chunk_ids = set()

        async with self.db_pool.acquire() as conn:
            # Get chunks from entities
            rows = await conn.fetch(
                """
                SELECT source_chunk_ids
                FROM kg_nodes
                WHERE entity_id = ANY($1) AND source_chunk_ids IS NOT NULL
            """,
                entity_ids,
            )

            for row in rows:
                if row["source_chunk_ids"]:
                    chunk_ids.update(row["source_chunk_ids"])

            # Get chunks from relationships
            rows = await conn.fetch(
                """
                SELECT source_chunk_ids
                FROM kg_edges
                WHERE (source_entity_id = ANY($1) OR target_entity_id = ANY($1))
                  AND source_chunk_ids IS NOT NULL
            """,
                entity_ids,
            )

            for row in rows:
                if row["source_chunk_ids"]:
                    chunk_ids.update(row["source_chunk_ids"])

        return list(chunk_ids)

    def build_graph_summary(
        self, entities: list[dict], relationships: list[dict], query_mentions: list[tuple[str, str]]
    ) -> str:
        """
        Build a human-readable summary of the KG context for the LLM.
        """
        if not entities and not relationships:
            return ""

        lines = ["[KNOWLEDGE GRAPH CONTEXT]"]

        # Group entities by type
        entity_by_type = {}
        for e in entities:
            etype = e.get("entity_type", "unknown")
            if etype not in entity_by_type:
                entity_by_type[etype] = []
            entity_by_type[etype].append(e["name"])

        if entity_by_type:
            lines.append("\nEntities found:")
            for etype, names in entity_by_type.items():
                names_str = ", ".join(names[:5])
                if len(names) > 5:
                    names_str += f" (+{len(names) - 5} more)"
                lines.append(f"  - {etype}: {names_str}")

        # Key relationships
        if relationships:
            lines.append("\nKey relationships:")
            seen_rels = set()
            for rel in relationships[:15]:  # Limit to avoid context bloat
                rel_str = (
                    f"{rel['source_name']} --[{rel['relationship_type']}]--> {rel['target_name']}"
                )
                if rel_str not in seen_rels:
                    seen_rels.add(rel_str)
                    lines.append(f"  - {rel_str}")

        lines.append("")
        return "\n".join(lines)

    async def get_context_for_query(
        self, query: str, max_depth: int = 1, max_entities: int = 10
    ) -> KGContext:
        """
        Main entry point: Get KG context for a user query.

        Args:
            query: User's question
            max_depth: How many hops to traverse (1-2)
            max_entities: Max entities to include

        Returns:
            KGContext with entities, relationships, chunk IDs, and summary
        """
        # Step 1: Extract entity mentions from query
        mentions = self.extract_entities_from_query(query)

        if not mentions:
            logger.debug(f"No entity mentions found in query: {query[:100]}")
            return KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.0,
            )

        logger.info(f"Extracted {len(mentions)} entity mentions from query")

        # Step 2: Find matching KG entities
        kg_entities = await self.find_kg_entities(mentions)

        if not kg_entities:
            logger.debug("No KG entities matched the mentions")
            return KGContext(
                entities_found=[],
                relationships=[],
                source_chunk_ids=[],
                graph_summary="",
                confidence=0.0,
            )

        # Step 3: Get related entities (graph traversal)
        entity_ids = [e["entity_id"] for e in kg_entities]
        related_entities, relationships = await self.get_related_entities(
            entity_ids, max_depth=max_depth, limit=max_entities * 2
        )

        all_entities = kg_entities + related_entities

        # Step 4: Get source chunk IDs
        all_entity_ids = [e["entity_id"] for e in all_entities]
        chunk_ids = await self.get_source_chunks(all_entity_ids)

        # Step 5: Build summary for LLM
        graph_summary = self.build_graph_summary(all_entities, relationships, mentions)

        # Calculate confidence based on match quality
        avg_confidence = (
            sum(e.get("confidence", 0.5) for e in kg_entities) / len(kg_entities)
            if kg_entities
            else 0.0
        )

        logger.info(
            f"KG context: {len(all_entities)} entities, "
            f"{len(relationships)} relationships, {len(chunk_ids)} chunks"
        )

        return KGContext(
            entities_found=all_entities[:max_entities],
            relationships=relationships,
            source_chunk_ids=chunk_ids[:50],  # Limit chunk IDs
            graph_summary=graph_summary,
            confidence=avg_confidence,
        )
