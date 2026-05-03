"""Entity Linker — Cross-source entity resolution for GraphRAG 2.0

Links Qdrant vector document chunks to KG entities by:
1. Scanning document content for entity mentions (regex patterns)
2. Fuzzy matching mentions against kg_nodes (trigram similarity >= 0.85)
3. Storing links in kg_entity_mentions table

This enables graph-aware retrieval: when hybrid search returns documents,
we can look up which KG entities they mention and pull in graph context.

Usage:
    linker = EntityLinker(db_pool, qdrant_client)
    stats = await linker.link_collection("legal_unified_hybrid_hybrid", batch_size=100)
    logger.info("Linked %d mentions", stats['mentions_created'])
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

# Entity extraction patterns (shared with kg_enhanced_retrieval.py)
# These detect Indonesian legal/business entities in text
_ENTITY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Laws and regulations
    ("undang_undang", re.compile(r"UU\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})", re.IGNORECASE)),
    ("peraturan_pemerintah", re.compile(r"PP\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})", re.IGNORECASE)),
    ("perpres", re.compile(r"Perpres\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})", re.IGNORECASE)),
    ("permen", re.compile(r"Permen\w*\s*(?:No\.?\s*)?(\d+)\s*(?:Tahun\s*)?(\d{4})", re.IGNORECASE)),
    # CONTEXT-style prefixes observed in legal_unified payloads:
    # `PP - NO 6624 - TAHUN 2021`, `UU - NO 11 - TAHUN 2020`
    ("ctx_law", re.compile(
        r"\b(UU|PP|Perpres|Permen\w*)\s*-\s*NO\s+(\d+)\s*-\s*TAHUN\s+(\d{4})",
        re.IGNORECASE,
    )),
    # KBLI codes
    ("kbli", re.compile(r"KBLI\s*(\d{4,5})", re.IGNORECASE)),
    # Visa types
    ("visa", re.compile(r"\b(KITAS|KITAP|VITAS|KUNJUNGAN|B211A?|C312|VOA)\b", re.IGNORECASE)),
    # Permits
    ("izin", re.compile(r"\b(NIB|SIUP|TDP|NPWP|IMB|AMDAL|OSS|RPTKA|IMTA)\b", re.IGNORECASE)),
    # Company types
    ("company", re.compile(r"\b(PT\s*PMA|PT\s*PMDN|PT\s*Perorangan|CV)\b", re.IGNORECASE)),
    # Tax types
    ("tax", re.compile(r"\b(PPh\s*\d{1,2}|PPN|PBB|BPHTB|SPT)\b", re.IGNORECASE)),
    # Government bodies
    ("gov", re.compile(r"\b(BKPM|DJP|Kemenkumham|Kemenaker|Imigrasi|BPN)\b", re.IGNORECASE)),
]

# Law-number normalisation: stored `kg_nodes.name` uses many inconsistent
# forms (`UU 13/2003`, `UU No. 11 Tahun 2020`, `UU 13 2003`, ...). We expand
# each detected mention into every known variant before doing the lookup.
_LAW_NORM_RE = re.compile(
    r"^(UU|PP|PERPRES|PERMEN\w*)\s+(?:NO\.?\s+)?(\d+)\s+(?:TAHUN\s+)?(\d{4})$",
)
_LAW_CTX_RE = re.compile(
    r"^(UU|PP|PERPRES|PERMEN\w*)\s*-\s*NO\s+(\d+)\s*-\s*TAHUN\s+(\d{4})$",
)


def _match_key_variants(mention_text: str) -> list[str]:
    """Return lower-cased lookup keys for a mention, covering known forms.

    Feeds the in-memory `LOWER(name) -> entity_id` dictionary used by
    `EntityLinker.link_text`. The first hit wins.
    """
    base = mention_text.strip()
    out = [base]
    upper = base.upper()

    collapsed = re.sub(r"\s+", " ", base)
    if collapsed != base:
        out.append(collapsed)

    m = _LAW_NORM_RE.match(upper) or _LAW_CTX_RE.match(upper)
    if m:
        law, num, year = m.group(1), m.group(2), m.group(3)
        out.extend(
            [
                f"{law} {num}/{year}",
                f"{law} No. {num} Tahun {year}",
                f"{law} NO. {num} TAHUN {year}",
                f"{law} No {num} Tahun {year}",
                f"{law} {num} {year}",
            ],
        )

    km = re.match(r"KBLI\s*(\d{4,5})", upper)
    if km:
        out.append(f"KBLI {km.group(1)}")

    seen: set[str] = set()
    deduped: list[str] = []
    for variant in out:
        key = variant.lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(key)
    return deduped


def extract_mentions(text: str) -> list[dict[str, str]]:
    """Extract entity mentions from text using regex patterns.

    Returns list of dicts with 'type', 'text', 'normalized' keys.
    """
    mentions: list[dict[str, str]] = []
    seen: set[str] = set()

    for entity_type, pattern in _ENTITY_PATTERNS:
        for match in pattern.finditer(text):
            mention_text = match.group(0).strip()
            normalized = mention_text.upper().replace(".", "").replace(" ", "_")

            if normalized not in seen:
                seen.add(normalized)
                mentions.append({
                    "type": entity_type,
                    "text": mention_text,
                    "normalized": normalized,
                })

    return mentions


class EntityLinker:
    """Links Qdrant document chunks to KG entities."""

    def __init__(
        self,
        db_pool: Any,
        qdrant_client: Any | None = None,
    ) -> None:
        self._pool = db_pool
        self._qdrant = qdrant_client
        # Lazy in-memory index: LOWER(name) -> (entity_id, entity_type).
        # Populated on first exact-match call; each lookup is O(1) vs a
        # SQL round-trip per mention. Invalidated by `reload_name_index`.
        self._name_index: dict[str, tuple[str, str]] | None = None

    async def _load_name_index(self) -> dict[str, tuple[str, str]]:
        """Load kg_nodes name -> (entity_id, entity_type) into memory."""
        rows = await self._pool.fetch(
            "SELECT entity_id, name, entity_type FROM kg_nodes",
        )
        idx: dict[str, tuple[str, str]] = {}
        for row in rows:
            key = (row["name"] or "").strip().lower()
            if key and key not in idx:
                idx[key] = (row["entity_id"], row["entity_type"])
        logger.info(
            "EntityLinker name index loaded: %d kg_nodes rows, %d unique keys",
            len(rows),
            len(idx),
        )
        return idx

    async def reload_name_index(self) -> None:
        """Force the in-memory name index to be rebuilt on next use."""
        self._name_index = None

    async def _fuzzy_match_entity(
        self,
        mention_text: str,
        entity_type: str | None = None,
        threshold: float = 0.85,
    ) -> dict[str, Any] | None:
        """Find best matching KG entity for a mention using trigram similarity.

        Args:
            mention_text: The text mention to match
            entity_type: Optional type filter
            threshold: Minimum similarity (default 0.85)

        Returns:
            Matched entity dict or None
        """
        async with self._pool.acquire() as conn:
            if entity_type:
                row = await conn.fetchrow(
                    "SELECT entity_id, name, entity_type, "
                    "similarity(name, $1) as sim "
                    "FROM kg_nodes "
                    "WHERE entity_type = $2 AND similarity(name, $1) >= $3 "
                    "ORDER BY sim DESC LIMIT 1",
                    mention_text,
                    entity_type,
                    threshold,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT entity_id, name, entity_type, "
                    "similarity(name, $1) as sim "
                    "FROM kg_nodes "
                    "WHERE similarity(name, $1) >= $2 "
                    "ORDER BY sim DESC LIMIT 1",
                    mention_text,
                    threshold,
                )

            if row:
                return {
                    "entity_id": row["entity_id"],
                    "name": row["name"],
                    "entity_type": row["entity_type"],
                    "similarity": row["sim"],
                }
            return None

    async def _exact_match_entity(
        self,
        mention_text: str,
    ) -> dict[str, Any] | None:
        """Match a mention against `kg_nodes.name` via the in-memory index.

        On first call, loads the full `kg_nodes` table into a dict once
        (~100K rows, ~20MB). Subsequent lookups are O(1) per variant
        instead of a SQL round-trip per mention.
        """
        if self._name_index is None:
            self._name_index = await self._load_name_index()

        for key in _match_key_variants(mention_text):
            hit = self._name_index.get(key)
            if hit is not None:
                entity_id, entity_type = hit
                return {
                    "entity_id": entity_id,
                    "name": key,
                    "entity_type": entity_type,
                    "similarity": 1.0,
                }
        return None

    async def _resolve_mentions(
        self,
        mentions: list[dict[str, str]],
        collection_name: str,
        point_id: str,
        enable_fuzzy: bool,
    ) -> list[tuple[str, str, str, str, str, float, str]]:
        """Resolve mentions to kg_nodes and return insert-ready rows.

        Each row matches the INSERT column order:
            (mention_id, entity_id, collection_name, point_id,
             mention_text, confidence, match_type).
        """
        rows: list[tuple[str, str, str, str, str, float, str]] = []
        for mention in mentions:
            text = mention["text"]
            entity = await self._exact_match_entity(text)
            match_type = "exact"
            if not entity and enable_fuzzy:
                entity = await self._fuzzy_match_entity(text, entity_type=None, threshold=0.85)
                match_type = "fuzzy"
            if not entity:
                continue
            mid = hashlib.md5(
                f"{entity['entity_id']}:{collection_name}:{point_id}".encode(),
            ).hexdigest()
            rows.append(
                (
                    mid,
                    entity["entity_id"],
                    collection_name,
                    point_id,
                    text[:500],
                    float(entity.get("similarity", 0.85)),
                    match_type,
                ),
            )
        return rows

    async def link_text(
        self,
        text: str,
        collection_name: str,
        point_id: str,
        enable_fuzzy: bool = True,
    ) -> int:
        """Extract and link entity mentions from a single text chunk.

        Returns the number of mentions linked (idempotent vs re-runs via the
        UNIQUE (entity_id, collection_name, point_id) index).
        """
        mentions = extract_mentions(text)
        if not mentions:
            return 0
        rows = await self._resolve_mentions(mentions, collection_name, point_id, enable_fuzzy)
        if not rows:
            return 0
        try:
            async with self._pool.acquire() as conn:
                await conn.executemany(
                    "INSERT INTO kg_entity_mentions "
                    "(mention_id, entity_id, collection_name, point_id, "
                    "mention_text, confidence, match_type) "
                    "VALUES ($1, $2, $3, $4, $5, $6, $7) "
                    "ON CONFLICT (entity_id, collection_name, point_id) DO NOTHING",
                    rows,
                )
        except Exception as e:
            logger.debug("Failed to batch-insert %d mentions: %s", len(rows), e)
            return 0
        return len(rows)

    async def link_collection(
        self,
        collection_name: str,
        batch_size: int = 100,
        limit: int | None = None,
        enable_fuzzy: bool = True,
    ) -> dict[str, Any]:
        """Scan a Qdrant collection and link entity mentions to KG nodes.

        Args:
            collection_name: Qdrant collection to scan
            batch_size: Points per scroll batch
            limit: Max points to process (None = all)
            enable_fuzzy: If False, skip the trigram fallback (one SQL round-
                trip per mention miss) — exact in-memory match only.

        Returns:
            Stats dict with points_processed, mentions_created, elapsed_s
        """
        if not self._qdrant:
            logger.error("No Qdrant client configured for entity linking")
            return {"error": "no_qdrant_client"}

        start = time.time()
        points_processed = 0
        mentions_created = 0
        offset = None

        logger.info("Starting entity linking for collection: %s", collection_name)

        while True:
            try:
                # Scroll through collection
                results, next_offset = await self._qdrant.scroll(
                    collection_name=collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
            except Exception as e:
                logger.error("Qdrant scroll failed: %s", e)
                break

            if not results:
                break

            for point in results:
                content = ""
                payload = point.payload or {}
                # Try common content field names
                for field in ("content", "text", "chunk_text", "document"):
                    if field in payload and payload[field]:
                        content = str(payload[field])
                        break

                if not content:
                    continue

                point_id = str(point.id)
                linked = await self.link_text(
                    content,
                    collection_name,
                    point_id,
                    enable_fuzzy=enable_fuzzy,
                )
                mentions_created += linked
                points_processed += 1

                if limit and points_processed >= limit:
                    break

            if limit and points_processed >= limit:
                break

            offset = next_offset
            if offset is None:
                break

            if points_processed % 500 == 0:
                logger.info(
                    "Entity linking progress: %d points, %d mentions (%.1fs)",
                    points_processed,
                    mentions_created,
                    time.time() - start,
                )

        elapsed = time.time() - start
        stats = {
            "collection": collection_name,
            "points_processed": points_processed,
            "mentions_created": mentions_created,
            "elapsed_s": round(elapsed, 1),
        }
        logger.info("Entity linking complete: %s", stats)
        return stats

    async def get_linked_entities_for_docs(
        self,
        point_ids: list[str],
        collection_name: str,
    ) -> list[dict[str, Any]]:
        """Query-time: find KG entities linked to search result documents.

        Args:
            point_ids: Qdrant point IDs from search results
            collection_name: Collection the points belong to

        Returns:
            List of entity dicts with entity_id, name, entity_type, confidence
        """
        if not point_ids:
            return []

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT n.entity_id, n.name, n.entity_type, "
                "n.description, m.confidence "
                "FROM kg_entity_mentions m "
                "JOIN kg_nodes n ON n.entity_id = m.entity_id "
                "WHERE m.collection_name = $1 AND m.point_id = ANY($2) "
                "ORDER BY m.confidence DESC",
                collection_name,
                point_ids,
            )

        return [
            {
                "entity_id": r["entity_id"],
                "name": r["name"],
                "entity_type": r["entity_type"],
                "description": r["description"],
                "confidence": r["confidence"],
            }
            for r in rows
        ]
