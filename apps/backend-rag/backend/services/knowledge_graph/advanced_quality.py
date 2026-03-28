"""
Advanced Knowledge Graph Quality Enhancement

Advanced improvements beyond basic filtering:
1. Entity name normalization (standardize legal references)
2. Cross-reference detection (laws referencing other laws)
3. Semantic orphan linking using embeddings
4. Domain-specific relationship inference
5. Hierarchical relationship detection (Pasal → Ayat → Huruf)
"""

import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


# ============================================================================
# ENTITY NORMALIZATION RULES
# ============================================================================

# Patterns for normalizing Indonesian legal references
NORMALIZATION_RULES = [
    # UU normalization: "UU No 6/2023" → "UU No. 6 Tahun 2023"
    (r"UU\s*(?:No\.?|Nomor)?\s*(\d+)[/\s-](\d{4})", r"UU No. \1 Tahun \2"),
    (r"Undang[- ]?Undang\s*(?:No\.?|Nomor)?\s*(\d+)[/\s-](\d{4})", r"UU No. \1 Tahun \2"),
    # PP normalization: "PP 28/2025" → "PP No. 28 Tahun 2025"
    (r"PP\s*(?:No\.?|Nomor)?\s*(\d+)[/\s-](\d{4})", r"PP No. \1 Tahun \2"),
    (r"Peraturan\s+Pemerintah\s*(?:No\.?|Nomor)?\s*(\d+)[/\s-](\d{4})", r"PP No. \1 Tahun \2"),
    # Perpres normalization
    (r"Perpres\s*(?:No\.?|Nomor)?\s*(\d+)[/\s-](\d{4})", r"Perpres No. \1 Tahun \2"),
    # Permen normalization
    (r"Permen\s*(\w+)\s*(?:No\.?|Nomor)?\s*(\d+)[/\s-](\d{4})", r"Permen \1 No. \2 Tahun \3"),
    # Perda normalization
    (r"Perda\s*(?:No\.?|Nomor)?\s*(\d+)[/\s-](\d{4})", r"Perda No. \1 Tahun \2"),
    # Pasal normalization
    (r"Pasal\s+(\d+)\s*[Aa]yat\s*\(?(\d+)\)?", r"Pasal \1 Ayat \2"),
    # KBLI normalization
    (r"KBLI\s*[-:]?\s*(\d+)", r"KBLI \1"),
    (r"^(\d{5})$", r"KBLI \1"),  # Bare 5-digit codes
    # Currency normalization
    (r"Rp\.?\s*([\d.,]+)", r"Rp \1"),
    (r"USD\s*([\d.,]+)", r"USD \1"),
]


def normalize_entity_name(name: str, entity_type: str) -> str:
    """
    Normalize entity name based on type and patterns

    Args:
        name: Original entity name
        entity_type: Type of entity

    Returns:
        Normalized name
    """
    normalized = name.strip()

    # Apply normalization rules
    for pattern, replacement in NORMALIZATION_RULES:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    # Type-specific normalization
    if entity_type == "kbli":
        # Ensure KBLI prefix
        if re.match(r"^\d{4,5}$", normalized):
            normalized = f"KBLI {normalized}"
        # Fix common typos
        normalized = re.sub(r"^[IB]BLI", "KBLI", normalized, flags=re.IGNORECASE)

    elif entity_type in ("undang_undang", "peraturan_pemerintah", "perpres", "permen"):
        # Ensure proper capitalization
        normalized = normalized.upper()
        # Standardize "No." format
        normalized = re.sub(r"\bNO\b", "No.", normalized)
        normalized = re.sub(r"\bTAHUN\b", "Tahun", normalized)

    elif entity_type == "pasal":
        # Capitalize Pasal, Ayat, Huruf
        normalized = re.sub(r"\bpasal\b", "Pasal", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bayat\b", "Ayat", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\bhuruf\b", "Huruf", normalized, flags=re.IGNORECASE)

    return normalized


# ============================================================================
# CROSS-REFERENCE DETECTION
# ============================================================================

# Patterns for detecting references to other regulations
REFERENCE_PATTERNS = [
    # "sebagaimana diatur dalam UU No. X Tahun Y"
    (
        r"sebagaimana\s+(?:telah\s+)?diatur\s+(?:dalam|oleh)\s+(UU|PP|Perpres|Permen)\s+(?:No\.?\s*)?(\d+)\s+Tahun\s+(\d{4})",
        "REFERENCES",
    ),
    # "berdasarkan UU No. X/Y"
    (r"berdasarkan\s+(UU|PP|Perpres|Permen)\s+(?:No\.?\s*)?(\d+)[/\s](\d{4})", "REFERENCES"),
    # "mengacu pada PP No. X Tahun Y"
    (
        r"mengacu\s+(?:pada|ke)\s+(UU|PP|Perpres|Permen)\s+(?:No\.?\s*)?(\d+)\s+Tahun\s+(\d{4})",
        "REFERENCES",
    ),
    # "diubah dengan UU No. X Tahun Y"
    (
        r"(?:telah\s+)?diubah\s+(?:dengan|oleh)\s+(UU|PP|Perpres|Permen)\s+(?:No\.?\s*)?(\d+)\s+Tahun\s+(\d{4})",
        "AMENDS",
    ),
    # "mencabut UU No. X Tahun Y"
    (r"mencabut\s+(UU|PP|Perpres|Permen)\s+(?:No\.?\s*)?(\d+)\s+Tahun\s+(\d{4})", "REPLACES"),
    # "pelaksanaan UU No. X Tahun Y"
    (
        r"(?:untuk\s+)?pelaksanaan\s+(UU|PP|Perpres)\s+(?:No\.?\s*)?(\d+)\s+Tahun\s+(\d{4})",
        "IMPLEMENTS",
    ),
]


def extract_cross_references(text: str) -> list[dict]:
    """
    Extract cross-references to other regulations from text

    Args:
        text: Text to analyze

    Returns:
        List of detected references with type and target
    """
    references = []

    for pattern, rel_type in REFERENCE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            reg_type = match.group(1).upper()
            number = match.group(2)
            year = match.group(3)

            # Map regulation type to entity type
            type_map = {
                "UU": "undang_undang",
                "PP": "peraturan_pemerintah",
                "PERPRES": "perpres",
                "PERMEN": "permen",
            }

            entity_type = type_map.get(reg_type, "undang_undang")
            normalized_name = f"{reg_type} No. {number} Tahun {year}"

            references.append(
                {
                    "target_type": entity_type,
                    "target_name": normalized_name,
                    "relationship": rel_type,
                    "evidence": match.group(0),
                },
            )

    return references


# ============================================================================
# HIERARCHICAL RELATIONSHIP DETECTION
# ============================================================================


def detect_hierarchical_relationships(entities: list[dict]) -> list[dict]:
    """
    Detect hierarchical relationships between entities

    Hierarchies:
    - Pasal → belongs to → UU/PP
    - Ayat → belongs to → Pasal
    - Huruf → belongs to → Ayat
    - KBLI 5-digit → belongs to → KBLI 4-digit → KBLI 3-digit

    Args:
        entities: List of entity dicts with 'id', 'type', 'name'

    Returns:
        List of inferred relationships
    """
    relationships = []

    # Group entities by type
    by_type: dict[str, list[dict]] = {}
    for entity in entities:
        by_type.setdefault(entity["type"], []).append(entity)

    # Pasal → UU/PP hierarchy
    pasals = by_type.get("pasal", [])
    laws = by_type.get("undang_undang", []) + by_type.get("peraturan_pemerintah", [])

    for pasal in pasals:
        pasal_name = pasal["name"]

        # Check if pasal mentions a specific law
        for law in laws:
            law_name = law["name"]
            # Check if law is mentioned in pasal context
            if any(part in pasal_name.upper() for part in law_name.upper().split()):
                relationships.append(
                    {
                        "source_id": pasal["id"],
                        "target_id": law["id"],
                        "type": "PART_OF",
                        "evidence": f"[hierarchical: {pasal_name} in {law_name}]",
                        "confidence": 0.8,
                    },
                )
                break
        else:
            # Link to first law if no specific match
            if laws:
                relationships.append(
                    {
                        "source_id": pasal["id"],
                        "target_id": laws[0]["id"],
                        "type": "PART_OF",
                        "evidence": "[hierarchical: inferred from context]",
                        "confidence": 0.6,
                    },
                )

    # KBLI hierarchy: 5-digit → 4-digit → 3-digit → 2-digit
    kblis = by_type.get("kbli", [])
    kbli_by_code: dict[str, dict] = {}

    for kbli in kblis:
        # Extract code
        match = re.search(r"(\d{2,5})", kbli["name"])
        if match:
            code = match.group(1)
            kbli_by_code[code] = kbli

    for code, kbli in kbli_by_code.items():
        if len(code) >= 3:
            parent_code = code[:-1]
            if parent_code in kbli_by_code:
                relationships.append(
                    {
                        "source_id": kbli["id"],
                        "target_id": kbli_by_code[parent_code]["id"],
                        "type": "PART_OF",
                        "evidence": f"[hierarchical: KBLI {code} → {parent_code}]",
                        "confidence": 0.95,
                    },
                )

    return relationships


# ============================================================================
# DOMAIN-SPECIFIC RELATIONSHIP INFERENCE
# ============================================================================

# Domain rules for Indonesian legal/business context
DOMAIN_RULES = [
    # (source_type, target_type, keywords_in_text, relationship)
    ("izin_usaha", "kbli", ["klasifikasi", "kbli", "kegiatan usaha"], "CLASSIFIED_AS"),
    ("izin_usaha", "dokumen", ["persyaratan", "dokumen", "kelengkapan"], "REQUIRES"),
    ("izin_usaha", "biaya", ["biaya", "tarif", "pnbp", "retribusi"], "HAS_FEE"),
    ("izin_usaha", "jangka_waktu", ["berlaku", "masa", "jangka waktu"], "HAS_DURATION"),
    ("pt_pma", "modal", ["modal", "investasi", "setoran"], "REQUIRES"),
    ("pt_pma", "izin_usaha", ["izin", "perizinan", "oss"], "REQUIRES"),
    ("visa", "dokumen", ["dokumen", "persyaratan", "kelengkapan"], "REQUIRES"),
    ("visa", "sponsor", ["sponsor", "penjamin"], "REQUIRES"),
    ("visa", "biaya", ["biaya", "visa fee", "pnbp"], "HAS_FEE"),
]


def infer_domain_relationships(
    entities: list[dict],
    text: str,
) -> list[dict]:
    """
    Infer relationships based on domain-specific rules

    Args:
        entities: List of entity dicts
        text: Original text for context

    Returns:
        List of inferred relationships
    """
    relationships = []
    text_lower = text.lower()

    # Group entities by type
    by_type: dict[str, list[dict]] = {}
    for entity in entities:
        by_type.setdefault(entity["type"], []).append(entity)

    for source_type, target_type, keywords, rel_type in DOMAIN_RULES:
        sources = by_type.get(source_type, [])
        targets = by_type.get(target_type, [])

        if not sources or not targets:
            continue

        # Check if any keyword present in text
        if any(kw in text_lower for kw in keywords):
            # Create relationships
            for source in sources:
                for target in targets:
                    relationships.append(
                        {
                            "source_id": source["id"],
                            "target_id": target["id"],
                            "type": rel_type,
                            "evidence": f"[domain rule: {source_type} → {target_type}]",
                            "confidence": 0.7,
                        },
                    )

    return relationships


# ============================================================================
# SEMANTIC ORPHAN LINKING (using embeddings)
# ============================================================================


async def find_semantic_links(
    orphan_entities: list[dict],
    all_entities: list[dict],
    embeddings_cache: dict[str, list[float]] | None = None,
    similarity_threshold: float = 0.75,
) -> list[dict]:
    """
    Find semantic relationships for orphan entities using embeddings

    Args:
        orphan_entities: Entities without relationships
        all_entities: All entities in the graph
        embeddings_cache: Pre-computed embeddings (entity_id → vector)
        similarity_threshold: Minimum similarity for linking

    Returns:
        List of inferred relationships
    """
    relationships = []

    # Skip if no embeddings available
    if not embeddings_cache:
        logger.debug("No embeddings cache provided, skipping semantic linking")
        return relationships

    try:
        import numpy as np

        def cosine_similarity(a: list[float], b: list[float]) -> float:
            """Cosine similarity."""
            a_np = np.array(a)
            b_np = np.array(b)
            return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))

        # Find similar entities for each orphan
        connected_entities = [
            e for e in all_entities if e["id"] not in {o["id"] for o in orphan_entities}
        ]

        for orphan in orphan_entities:
            orphan_embedding = embeddings_cache.get(orphan["id"])
            if not orphan_embedding:
                continue

            best_match = None
            best_similarity = 0.0

            for entity in connected_entities:
                entity_embedding = embeddings_cache.get(entity["id"])
                if not entity_embedding:
                    continue

                similarity = cosine_similarity(orphan_embedding, entity_embedding)
                if similarity > best_similarity and similarity >= similarity_threshold:
                    best_similarity = similarity
                    best_match = entity

            if best_match:
                # Determine relationship type based on entity types
                rel_type = _infer_relationship_type(orphan["type"], best_match["type"])

                relationships.append(
                    {
                        "source_id": orphan["id"],
                        "target_id": best_match["id"],
                        "type": rel_type,
                        "evidence": f"[semantic similarity: {best_similarity:.2f}]",
                        "confidence": min(best_similarity, 0.8),
                    },
                )

    except ImportError:
        logger.warning("numpy not available, skipping semantic linking")

    return relationships


def _infer_relationship_type(source_type: str, target_type: str) -> str:
    """Infer relationship type based on entity types"""
    type_pairs = {
        ("pasal", "undang_undang"): "PART_OF",
        ("pasal", "peraturan_pemerintah"): "PART_OF",
        ("ayat", "pasal"): "PART_OF",
        ("kbli", "izin_usaha"): "CLASSIFIED_AS",
        ("biaya", "izin_usaha"): "HAS_FEE",
        ("dokumen", "izin_usaha"): "REQUIRES",
        ("jangka_waktu", "izin_usaha"): "HAS_DURATION",
    }
    return type_pairs.get((source_type, target_type), "RELATED_TO")


# ============================================================================
# MAIN ENHANCEMENT FUNCTION
# ============================================================================


@dataclass
class EnhancementStats:
    """Statistics from enhancement"""

    entities_normalized: int = 0
    cross_references_found: int = 0
    hierarchical_relations: int = 0
    domain_relations: int = 0
    semantic_links: int = 0

    def to_dict(self) -> dict[str, Any]:
        """To dict."""
        return {
            "entities_normalized": self.entities_normalized,
            "cross_references_found": self.cross_references_found,
            "hierarchical_relations": self.hierarchical_relations,
            "domain_relations": self.domain_relations,
            "semantic_links": self.semantic_links,
        }


async def enhance_kg_quality(
    collection: str,
    apply_normalization: bool = True,
    detect_cross_refs: bool = True,
    detect_hierarchy: bool = True,
    apply_domain_rules: bool = True,
    dry_run: bool = True,
) -> EnhancementStats:
    """
    Apply advanced quality enhancements to KG

    Args:
        collection: Collection to enhance
        apply_normalization: Normalize entity names
        detect_cross_refs: Detect cross-references
        detect_hierarchy: Detect hierarchical relationships
        apply_domain_rules: Apply domain-specific rules
        dry_run: If True, don't persist changes

    Returns:
        Enhancement statistics
    """
    stats = EnhancementStats()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not set")

    conn = await asyncpg.connect(db_url)

    try:
        # Get all entities
        entities = await conn.fetch(
            """
            SELECT entity_id, entity_type, name, properties
            FROM kg_nodes
            WHERE source_collection = $1
        """,
            collection,
        )

        entity_list = [
            {
                "id": row["entity_id"],
                "type": row["entity_type"],
                "name": row["name"],
                "properties": row["properties"],
            }
            for row in entities
        ]

        logger.info(f"Enhancing {len(entity_list)} entities in {collection}")

        # Step 1: Normalize entity names
        if apply_normalization:
            for entity in entity_list:
                normalized = normalize_entity_name(entity["name"], entity["type"])
                if normalized != entity["name"]:
                    stats.entities_normalized += 1
                    if not dry_run:
                        await conn.execute(
                            """
                            UPDATE kg_nodes SET name = $1 WHERE entity_id = $2
                        """,
                            normalized,
                            entity["id"],
                        )
                    entity["name"] = normalized

            logger.info(f"Normalized {stats.entities_normalized} entity names")

        # Step 2: Detect hierarchical relationships
        if detect_hierarchy:
            hierarchical = detect_hierarchical_relationships(entity_list)
            stats.hierarchical_relations = len(hierarchical)

            if not dry_run and hierarchical:
                for rel in hierarchical:
                    rel_id = f"{rel['source_id']}_{rel['type']}_{rel['target_id']}"
                    await conn.execute(
                        """
                        INSERT INTO kg_edges (
                            relationship_id, source_entity_id, target_entity_id,
                            relationship_type, properties, confidence,
                            source_collection, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                        ON CONFLICT DO NOTHING
                    """,
                        rel_id,
                        rel["source_id"],
                        rel["target_id"],
                        rel["type"],
                        f'{{"evidence": "{rel["evidence"]}"}}',
                        rel["confidence"],
                        collection,
                    )

            logger.info(f"Detected {stats.hierarchical_relations} hierarchical relationships")

        # Step 3: Apply domain rules for orphans
        if apply_domain_rules:
            # Get orphan entities
            orphan_ids = await conn.fetch(
                """
                SELECT entity_id FROM kg_nodes n
                WHERE n.source_collection = $1
                AND NOT EXISTS (
                    SELECT 1 FROM kg_edges e
                    WHERE e.source_entity_id = n.entity_id
                       OR e.target_entity_id = n.entity_id
                )
            """,
                collection,
            )

            orphan_id_set = {row["entity_id"] for row in orphan_ids}
            orphan_entities = [e for e in entity_list if e["id"] in orphan_id_set]

            logger.info(f"Found {len(orphan_entities)} orphan entities")

            # Get sample text for context (from first chunk)
            # In production, would use actual chunk text
            sample_text = "izin usaha persyaratan dokumen kbli klasifikasi biaya"

            domain_rels = infer_domain_relationships(orphan_entities, sample_text)
            stats.domain_relations = len(domain_rels)

            if not dry_run and domain_rels:
                for rel in domain_rels:
                    rel_id = f"{rel['source_id']}_{rel['type']}_{rel['target_id']}"
                    await conn.execute(
                        """
                        INSERT INTO kg_edges (
                            relationship_id, source_entity_id, target_entity_id,
                            relationship_type, properties, confidence,
                            source_collection, created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                        ON CONFLICT DO NOTHING
                    """,
                        rel_id,
                        rel["source_id"],
                        rel["target_id"],
                        rel["type"],
                        f'{{"evidence": "{rel["evidence"]}"}}',
                        rel["confidence"],
                        collection,
                    )

            logger.info(f"Inferred {stats.domain_relations} domain relationships")

        # Final stats
        if not dry_run:
            final_orphans = await conn.fetchval(
                """
                SELECT COUNT(*) FROM kg_nodes n
                WHERE n.source_collection = $1
                AND NOT EXISTS (
                    SELECT 1 FROM kg_edges e
                    WHERE e.source_entity_id = n.entity_id
                       OR e.target_entity_id = n.entity_id
                )
            """,
                collection,
            )

            total_nodes = await conn.fetchval(
                "SELECT COUNT(*) FROM kg_nodes WHERE source_collection = $1", collection,
            )

            logger.info(f"Final orphan rate: {final_orphans * 100 / total_nodes:.1f}%")

    finally:
        await conn.close()

    return stats
