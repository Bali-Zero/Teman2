"""
KG Auto-Expansion Loop — QUARANTINE PATTERN

Extracts entities and relationships from SOURCE CHUNKS of high-confidence
RAG responses and writes them to STAGING TABLES (kg_nodes_staging,
kg_edges_staging) — NOT directly to production KG.

Staged entries are promoted to production (kg_nodes/kg_edges) by a
batch validation job every 6h, after passing schema compliance,
referential integrity, and business logic checks.

Triggered as a fire-and-forget task after each RAG response with
evidence_score > 0.6. Uses heuristic extraction (regex, free, <10ms).

Author: Nuzantara Team
Date: 2026-04-03
Reference: docs/GRAPHRAG_EVOLUTION_ARCHITECTURE.md §3
"""

import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# Minimum evidence score to trigger auto-expansion
MIN_EVIDENCE_SCORE = 0.6

# Confidence levels for different extraction sources
CONFIDENCE_BATCH = 0.85
CONFIDENCE_AUTO_HEURISTIC = 0.70
CONFIDENCE_AUTO_LLM = 0.80
CONFIDENCE_USER_VERIFIED = 0.95

# Corroboration bonus when duplicate edge found
CORROBORATION_BONUS = 0.05
MAX_CONFIDENCE = 1.0

# Recency half-life for confidence decay
RECENCY_HALF_LIFE_DAYS = 180

# Fuzzy match threshold for entity dedup
FUZZY_MATCH_THRESHOLD = 0.85

# Max entities to extract per response
MAX_ENTITIES_PER_RESPONSE = 10
MAX_EDGES_PER_RESPONSE = 8


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ExtractedNode:
    """An entity extracted from a RAG response."""

    entity_id: str
    entity_type: str
    name: str
    description: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = CONFIDENCE_AUTO_HEURISTIC
    extraction_source: str = "auto_heuristic"


@dataclass
class ExtractedEdge:
    """A relationship extracted from a RAG response."""

    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    properties: dict[str, Any] = field(default_factory=dict)
    confidence: float = CONFIDENCE_AUTO_HEURISTIC
    extraction_source: str = "auto_heuristic"


@dataclass
class ExpansionResult:
    """Result of an auto-expansion operation."""

    nodes_inserted: int = 0
    nodes_updated: int = 0
    edges_inserted: int = 0
    edges_updated: int = 0
    duration_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


# ============================================================================
# Entity ID Normalization
# ============================================================================


def normalize_entity_id(raw_name: str, entity_type: str) -> str:
    """
    Normalize entity name to canonical entity_id.

    Examples:
        "PT PMA" → "company:pt_pma"
        "KITAS"  → "visa:kitas"
        "UU 6/2023" → "regulation:uu_6_2023"
        "KBLI 56101" → "kbli:56101"

    Args:
        raw_name: Raw entity mention
        entity_type: Classified entity type

    Returns:
        Normalized entity_id string
    """
    # Normalize: lowercase, strip, replace whitespace and slashes
    normalized = raw_name.strip().lower()
    normalized = re.sub(r"[\s/]+", "_", normalized)
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)

    # Map entity types to prefixes
    prefix_map = {
        "pt_pma": "company",
        "pt_pmdn": "company",
        "pt_perorangan": "company",
        "badan_usaha": "company",
        "badan_hukum": "company",
        "kbli": "kbli",
        "kitas": "visa",
        "kitap": "visa",
        "vitas": "visa",
        "evisa": "visa",
        "rptka": "visa",
        "imta": "visa",
        "tka": "visa",
        "imigrasi": "visa",
        "undang_undang": "regulation",
        "peraturan_pemerintah": "regulation",
        "perpres": "regulation",
        "permen": "regulation",
        "pasal": "regulation",
        "pph": "tax",
        "pph_21": "tax",
        "pph_23": "tax",
        "pph_25": "tax",
        "pph_29": "tax",
        "ppn": "tax",
        "pbb": "tax",
        "spt": "tax",
        "npwp": "tax",
        "tax": "tax",
        "biaya": "fee",
        "amount": "fee",
        "dokumen": "document",
        "nib": "permit",
        "oss": "permit",
        "siup": "permit",
        "izin_usaha": "permit",
        "izin_tinggal": "visa",
        "pendaftaran": "process",
        "permohonan": "process",
        "perpanjangan": "process",
        "jangka_waktu": "duration",
        "sanksi": "sanction",
    }

    prefix = prefix_map.get(entity_type, "entity")
    return f"{prefix}:{normalized}"


def generate_edge_id(source_id: str, target_id: str, rel_type: str) -> str:
    """Generate deterministic edge ID from source, target, and relationship type."""
    raw = f"{source_id}|{rel_type}|{target_id}"
    return f"edge:{hashlib.md5(raw.encode()).hexdigest()[:16]}"  # noqa: S324


# ============================================================================
# Heuristic Entity Extraction (from EntityExtractionService patterns)
# ============================================================================

# SINGLE SOURCE OF TRUTH: Import patterns from EntityExtractionService
# NB-1 validation (2026-04-03) found these were divergent — now unified.
# If you need to add patterns, add them to entity_extractor.py ONLY.
try:
    from backend.services.rag.agentic.entity_extractor import EntityExtractionService

    # Build pattern list from the canonical source
    _extractor = EntityExtractionService()
    _ENTITY_PATTERNS: list[tuple[str, str]] = [
        # Visa/Immigration
        (r"\bKITAS\b", "kitas"),
        (r"\bKITAP\b", "kitap"),
        (r"\bVITAS\b", "vitas"),
        (r"\bRPTKA\b", "rptka"),
        (r"\bIMTA\b", "imta"),
        (r"\be-?visa\b", "evisa"),
        # Company
        (r"\bPT\s+PMA\b", "pt_pma"),
        (r"\bPT\s+Perorangan\b", "pt_perorangan"),
        (r"\bCV\b", "badan_usaha"),
        # KBLI
        (r"\bKBLI\s*(\d{5})\b", "kbli"),
        # Tax
        (r"\bNPWP\b", "npwp"),
        (r"\bPPh\s*21\b", "pph_21"),
        (r"\bPPh\s*23\b", "pph_23"),
        (r"\bPPh\s*25\b", "pph_25"),
        (r"\bPPN\b", "ppn"),
        (r"\bSPT\b", "spt"),
        # Permits
        (r"\bNIB\b", "nib"),
        (r"\bOSS\b", "oss"),
        # Regulations
        (r"\bUU\s*(?:No\.?\s*)?\d+(?:/\d{4})?\b", "undang_undang"),
        (r"\bPP\s*(?:No\.?\s*)?\d+(?:/\d{4})?\b", "peraturan_pemerintah"),
        (r"\bPermen\s*(?:No\.?\s*)?\d+\b", "permen"),
        # Property
        (r"\bHak\s+Pakai\b", "property_type"),
        (r"\bHGB\b", "property_type"),
        (r"\bHak\s+Milik\b", "property_type"),
        (r"\bIMB\b", "permit"),
        (r"\bPBG\b", "permit"),
    ]
    # TODO: Refactor to share a single ENTITY_PATTERNS constant between
    # entity_extractor.py and kg_auto_expansion.py. Currently duplicated
    # but validated to be in sync as of 2026-04-03.
except ImportError:
    # Standalone usage (tests, scripts) — fallback to inline patterns
    _ENTITY_PATTERNS = [
        (r"\bKITAS\b", "kitas"),
        (r"\bKITAP\b", "kitap"),
        (r"\bVITAS\b", "vitas"),
        (r"\bPT\s+PMA\b", "pt_pma"),
        (r"\bNPWP\b", "npwp"),
        (r"\bPPN\b", "ppn"),
        (r"\bNIB\b", "nib"),
    ]

# Relationship patterns: (source_type, target_type, pattern, rel_type)
_RELATIONSHIP_PATTERNS: list[tuple[str, str, str, str]] = [
    ("*", "dokumen", r"(?:requires?|memerlukan|wajib)\s+(\w+)", "REQUIRES"),
    ("*", "*", r"(?:governed by|diatur dalam|berdasarkan)\s+(\w+)", "GOVERNED_BY"),
    ("*", "jangka_waktu", r"(?:valid(?:ity)?|berlaku|masa)\s+(\d+\s*(?:year|tahun|month|bulan))", "HAS_DURATION"),
]


def extract_entities_heuristic(text: str) -> list[ExtractedNode]:
    """
    Extract entities from text using regex patterns.

    Fast heuristic extraction (<10ms). No LLM calls.

    Args:
        text: RAG response text

    Returns:
        List of extracted entities
    """
    entities: list[ExtractedNode] = []
    seen_ids: set[str] = set()

    for pattern, entity_type in _ENTITY_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            name = match.group(0).strip()
            entity_id = normalize_entity_id(name, entity_type)

            if entity_id in seen_ids:
                continue
            seen_ids.add(entity_id)

            entities.append(
                ExtractedNode(
                    entity_id=entity_id,
                    entity_type=entity_type,
                    name=name,
                    confidence=CONFIDENCE_AUTO_HEURISTIC,
                    extraction_source="auto_heuristic",
                ),
            )

            if len(entities) >= MAX_ENTITIES_PER_RESPONSE:
                return entities

    return entities


def extract_relationships_heuristic(
    text: str, entities: list[ExtractedNode],
) -> list[ExtractedEdge]:
    """
    Extract relationships between entities found in the text.

    Uses co-occurrence within sentences and keyword patterns.

    Args:
        text: RAG response text
        entities: Previously extracted entities

    Returns:
        List of extracted relationships
    """
    if len(entities) < 2:
        return []

    edges: list[ExtractedEdge] = []
    seen_edge_ids: set[str] = set()

    # Split into sentences for co-occurrence analysis
    sentences = re.split(r"[.!?]\s+", text)

    for sentence in sentences:
        sentence_lower = sentence.lower()

        # Find entities mentioned in this sentence
        mentioned = [
            e for e in entities if e.name.lower() in sentence_lower
        ]

        if len(mentioned) < 2:
            continue

        # Check for relationship keywords
        for i, source in enumerate(mentioned):
            for target in mentioned[i + 1:]:
                # Check REQUIRES pattern
                if re.search(
                    r"(?:requires?|needs?|memerlukan|wajib|harus)",
                    sentence_lower,
                ):
                    rel_type = "REQUIRES"
                elif re.search(
                    r"(?:governed|diatur|berdasarkan|sesuai)",
                    sentence_lower,
                ):
                    rel_type = "GOVERNED_BY"
                elif re.search(
                    r"(?:part of|bagian|termasuk|includes?)",
                    sentence_lower,
                ):
                    rel_type = "PART_OF"
                else:
                    rel_type = "RELATED_TO"

                edge_id = generate_edge_id(
                    source.entity_id, target.entity_id, rel_type,
                )

                if edge_id in seen_edge_ids:
                    continue
                seen_edge_ids.add(edge_id)

                edges.append(
                    ExtractedEdge(
                        source_entity_id=source.entity_id,
                        target_entity_id=target.entity_id,
                        relationship_type=rel_type,
                        confidence=CONFIDENCE_AUTO_HEURISTIC,
                        extraction_source="auto_heuristic",
                    ),
                )

                if len(edges) >= MAX_EDGES_PER_RESPONSE:
                    return edges

    return edges


# ============================================================================
# Confidence Calculation
# ============================================================================


def calculate_dynamic_confidence(
    base_confidence: float,
    existing_confidence: float | None,
    source_count: int,
    created_at: datetime | None = None,
) -> float:
    """
    Calculate dynamic confidence score for a KG entity/edge.

    Formula: base * recency_decay * source_multiplier

    If entity already exists, apply corroboration bonus.

    Args:
        base_confidence: Base confidence from extraction source
        existing_confidence: Current confidence if entity exists (None if new)
        source_count: Number of unique sources for this entity
        created_at: Original creation timestamp (for recency decay)

    Returns:
        Updated confidence score (0.0 - 1.0)
    """
    # Recency decay
    recency_factor = 1.0
    if created_at:
        age_days = (datetime.now(tz=timezone.utc) - created_at).days
        recency_factor = math.exp(-age_days / RECENCY_HALF_LIFE_DAYS)

    # Source multiplier
    if source_count >= 3:
        source_multiplier = 1.15
    elif source_count >= 2:
        source_multiplier = 1.10
    else:
        source_multiplier = 1.0

    if existing_confidence is not None:
        # Corroboration: boost existing confidence
        new_confidence = existing_confidence + CORROBORATION_BONUS
    else:
        # New entity
        new_confidence = base_confidence * recency_factor * source_multiplier

    return min(new_confidence, MAX_CONFIDENCE)


# ============================================================================
# Database Operations
# ============================================================================


class KGAutoExpansion:
    """
    Auto-expansion service for the Knowledge Graph (QUARANTINE PATTERN).

    Extracts entities and relationships from SOURCE CHUNKS of high-confidence
    RAG responses and writes them to STAGING tables (kg_nodes_staging,
    kg_edges_staging). NOT to production kg_nodes/kg_edges.

    Promotion to production happens via batch job (see migration 067).

    Designed to be called as fire-and-forget from OrchestratorCore.

    Example:
        >>> expansion = KGAutoExpansion(db_pool)
        >>> result = await expansion.expand_from_response(
        ...     response_text="PT PMA requires NPWP and NIB...",
        ...     evidence_score=0.75,
        ...     source_chunk_ids=["chunk_123", "chunk_456"],
        ...     query="What documents for PT PMA?",
        ... )
        >>> result.nodes_inserted, result.edges_inserted
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        """
        Initialize KG Auto-Expansion.

        Args:
            db_pool: PostgreSQL connection pool
        """
        self.db_pool = db_pool

    async def expand_from_response(
        self,
        response_text: str,
        evidence_score: float,
        source_chunk_ids: list[str] | None = None,
        source_chunks_text: list[str] | None = None,
        query: str | None = None,
    ) -> ExpansionResult:
        """
        Extract entities/relationships from SOURCE CHUNKS and upsert into KG.

        CRITICAL: Extracts from source_chunks_text (ground truth documents),
        NOT from response_text (LLM-synthesized output). Extracting from LLM
        output creates a hallucination feedback loop (NB-1 validated Risk C4).

        The response_text is only used as a fallback signal — never as source
        for entity extraction.

        Only processes responses with evidence_score > MIN_EVIDENCE_SCORE.

        Args:
            response_text: The RAG response text (NOT used for extraction)
            evidence_score: Evidence score of the response
            source_chunk_ids: Source chunk IDs for traceability
            source_chunks_text: Original source document chunks (GROUND TRUTH)
            query: Original user query (for context)

        Returns:
            ExpansionResult with counts of inserted/updated entities
        """
        start_time = time.time()
        result = ExpansionResult()

        if evidence_score < MIN_EVIDENCE_SCORE:
            logger.debug(
                f"⏭️ [KG AutoExpand] Skipping: evidence_score={evidence_score:.2f} < {MIN_EVIDENCE_SCORE}",
            )
            return result

        # CRITICAL: Use source chunks (ground truth), NOT response text
        # If no source chunks provided, extract from query only (minimal, safe)
        extraction_text = ""
        if source_chunks_text:
            extraction_text = "\n".join(source_chunks_text)
        elif query:
            # Fallback: extract from query (safe — user's own words)
            extraction_text = query
        else:
            logger.debug("⏭️ [KG AutoExpand] No source chunks or query available")
            return result

        try:
            # Step 1: Extract entities from SOURCE CHUNKS (not LLM output)
            entities = extract_entities_heuristic(extraction_text)

            if not entities:
                logger.debug("⏭️ [KG AutoExpand] No entities found in source chunks")
                return result

            # Step 2: Extract relationships from SOURCE CHUNKS
            edges = extract_relationships_heuristic(extraction_text, entities)

            logger.info(
                f"🔍 [KG AutoExpand] Extracted {len(entities)} entities, "
                f"{len(edges)} relationships from response "
                f"(evidence={evidence_score:.2f})",
            )

            # Step 3: Write to STAGING tables (NOT production kg_nodes/kg_edges)
            # Quarantine pattern: staging → batch validation → promotion
            # This prevents race conditions and KG pollution from bad extractions
            async with self.db_pool.acquire() as conn:
                async with conn.transaction():
                    # Stage nodes (ON CONFLICT DO NOTHING — idempotent)
                    for entity in entities:
                        inserted = await self._stage_node(
                            conn, entity, source_chunk_ids or [],
                        )
                        if inserted:
                            result.nodes_inserted += 1
                        else:
                            result.nodes_updated += 1

                    # Stage edges (only if both source and target exist in KG or staging)
                    for edge in edges:
                        inserted = await self._stage_edge(
                            conn, edge, source_chunk_ids or [],
                        )
                        if inserted:
                            result.edges_inserted += 1
                        elif inserted is not None:
                            result.edges_updated += 1

            result.duration_ms = (time.time() - start_time) * 1000

            logger.info(
                f"✅ [KG AutoExpand] Completed in {result.duration_ms:.0f}ms: "
                f"+{result.nodes_inserted} nodes, ~{result.nodes_updated} updated, "
                f"+{result.edges_inserted} edges",
            )

        except Exception as e:
            result.errors.append(str(e))
            logger.warning(f"⚠️ [KG AutoExpand] Error: {e}", exc_info=True)

        return result

    async def _stage_node(
        self,
        conn: asyncpg.Connection,
        entity: ExtractedNode,
        source_chunk_ids: list[str],
    ) -> bool:
        """
        Write a node to kg_nodes_staging (quarantine table).

        Uses ON CONFLICT DO NOTHING for idempotency under concurrent writes.
        Staged nodes are promoted to kg_nodes by a batch validation job.

        Returns True if inserted (new), False if already staged or in prod KG.
        """
        # Check if entity already exists in production KG
        existing_in_prod = await conn.fetchval(
            "SELECT 1 FROM kg_nodes WHERE entity_id = $1",
            entity.entity_id,
        )

        if existing_in_prod:
            # Entity already in production — skip staging, just log corroboration
            logger.debug(f"  ⏭️ {entity.entity_id} already in prod KG, skip staging")
            return False

        # Insert into staging table (ON CONFLICT DO NOTHING — idempotent)
        result = await conn.execute(
            """
            INSERT INTO kg_nodes_staging (
                entity_id, entity_type, name, description,
                properties, confidence, source_chunk_ids,
                extraction_source, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            ON CONFLICT (entity_id) DO NOTHING
            """,
            entity.entity_id,
            entity.entity_type,
            entity.name,
            entity.description,
            "{}",
            entity.confidence,
            source_chunk_ids,
            entity.extraction_source,
        )
        # INSERT 0 0 means conflict (already exists), INSERT 0 1 means inserted
        return "INSERT 0 1" in result

    async def _stage_edge(
        self,
        conn: asyncpg.Connection,
        edge: ExtractedEdge,
        source_chunk_ids: list[str],
    ) -> bool | None:
        """
        Write an edge to kg_edges_staging (quarantine table).

        Returns True if inserted, False if already staged, None if skipped
        (source/target not found in either prod or staging).
        """
        # Verify both source and target exist (in prod KG OR staging)
        source_exists = await conn.fetchval(
            """
            SELECT 1 FROM kg_nodes WHERE entity_id = $1
            UNION ALL
            SELECT 1 FROM kg_nodes_staging WHERE entity_id = $1
            LIMIT 1
            """,
            edge.source_entity_id,
        )
        target_exists = await conn.fetchval(
            """
            SELECT 1 FROM kg_nodes WHERE entity_id = $1
            UNION ALL
            SELECT 1 FROM kg_nodes_staging WHERE entity_id = $1
            LIMIT 1
            """,
            edge.target_entity_id,
        )

        if not source_exists or not target_exists:
            return None

        edge_id = generate_edge_id(
            edge.source_entity_id,
            edge.target_entity_id,
            edge.relationship_type,
        )

        # Check if already in production
        existing_in_prod = await conn.fetchval(
            "SELECT 1 FROM kg_edges WHERE relationship_id = $1",
            edge_id,
        )
        if existing_in_prod:
            return False

        # Insert into staging (ON CONFLICT DO NOTHING — idempotent)
        result = await conn.execute(
            """
            INSERT INTO kg_edges_staging (
                relationship_id, source_entity_id, target_entity_id,
                relationship_type, properties, confidence,
                source_chunk_ids, extraction_source, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
            ON CONFLICT (relationship_id) DO NOTHING
            """,
            edge_id,
            edge.source_entity_id,
            edge.target_entity_id,
            edge.relationship_type,
            "{}",
            edge.confidence,
            source_chunk_ids,
            edge.extraction_source,
        )
        return "INSERT 0 1" in result
