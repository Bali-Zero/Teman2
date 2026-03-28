"""
Knowledge Graph Quality Filter
Post-processing module to improve KG extraction quality

Improvements:
1. Filter noise entities (short names, generic terms)
2. Fix entity type misclassifications
3. Merge duplicates with fuzzy matching
4. Dynamic confidence scoring based on evidence
5. Orphan reduction through relationship inference
"""

import logging
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from backend.services.knowledge_graph.extractor import (
    ExtractedEntity,
    ExtractedRelation,
    ExtractionResult,
)
from backend.services.knowledge_graph.ontology import EntityType, RelationType

logger = logging.getLogger(__name__)


# ============================================================================
# NOISE PATTERNS - Entities to filter out
# ============================================================================

# Short generic terms that are not useful entities
NOISE_TERMS = {
    # Indonesian generic terms
    "dan",
    "atau",
    "yang",
    "dari",
    "untuk",
    "dengan",
    "dalam",
    "pada",
    "ini",
    "itu",
    "tersebut",
    "bahwa",
    "oleh",
    "ke",
    "di",
    "tidak",
    # Budget allocation codes (not laws)
    "dak",
    "dau",
    "dbh",
    "apbn",
    "apbd",
    # Generic English
    "the",
    "and",
    "for",
    "with",
    "from",
    # Numbers and dates only
    "tahun",
    "bulan",
    "hari",
}

# Patterns for invalid entity names
NOISE_PATTERNS = [
    r"^[A-Z]{1,3}$",  # Single letters or very short acronyms
    r"^\d+$",  # Numbers only
    r"^[!@#$%^&*()]+$",  # Punctuation only
    r"^(rp|usd|eur|idr)[\d.,]+$",  # Currency amounts as names
    r"^huruf\s+[a-z]$",  # "Huruf A", "Huruf B", etc.
]

# Entity types that should not contain generic government terms
SPECIFIC_ENTITY_TYPES = {
    EntityType.UNDANG_UNDANG,
    EntityType.PERATURAN_PEMERINTAH,
    EntityType.PERPRES,
    EntityType.PERMEN,
    EntityType.PERDA,
    EntityType.SURAT_EDARAN,
}

# Generic terms that should NOT be classified as laws
NOT_A_LAW = {
    "dak",
    "dau",
    "dbh",
    "apbn",
    "apbd",
    "pip",
    "dipa",
    "peraturan perundang-undangan",
    "perundang-undangan",
    "hukum",
    "undang-undang pertamina",
    "undang-undang dasar",
}


# ============================================================================
# ENTITY TYPE CORRECTION RULES
# ============================================================================

ENTITY_TYPE_CORRECTIONS = {
    # DAK/DAU are budget allocations, not laws
    "dak": EntityType.BIAYA,
    "dau": EntityType.BIAYA,
    "dbh": EntityType.BIAYA,
    "apbn": EntityType.BIAYA,
    "apbd": EntityType.BIAYA,
    # Common acronyms
    "nib": EntityType.NIB,
    "npwp": EntityType.NPWP,
    "siup": EntityType.IZIN_USAHA,
    "tdp": EntityType.IZIN_USAHA,
    "imb": EntityType.IZIN_USAHA,
    "imta": EntityType.IZIN_USAHA,
    "rptka": EntityType.IZIN_USAHA,
    "kitas": EntityType.VISA,
    "kitap": EntityType.VISA,
    "visa": EntityType.VISA,
}


# ============================================================================
# QUALITY FILTER CLASS
# ============================================================================


@dataclass
class QualityStats:
    """Statistics from quality filtering"""

    entities_input: int = 0
    entities_filtered: int = 0
    entities_corrected: int = 0
    duplicates_merged: int = 0
    relations_inferred: int = 0

    def to_dict(self) -> dict[str, Any]:
        """To dict."""
        return {
            "entities_input": self.entities_input,
            "entities_filtered": self.entities_filtered,
            "entities_corrected": self.entities_corrected,
            "duplicates_merged": self.duplicates_merged,
            "relations_inferred": self.relations_inferred,
        }


class KGQualityFilter:
    """
    Post-processing filter to improve KG quality

    Features:
    - Noise filtering (short names, generic terms)
    - Entity type correction
    - Duplicate merging with fuzzy matching
    - Relationship inference for orphans
    - Dynamic confidence scoring
    """

    def __init__(
        self,
        min_name_length: int = 4,
        fuzzy_threshold: float = 0.85,
        infer_relationships: bool = True,
    ) -> None:
        """
        Initialize quality filter

        Args:
            min_name_length: Minimum entity name length
            fuzzy_threshold: Similarity threshold for fuzzy matching (0-1)
            infer_relationships: Whether to infer relationships for orphans
        """
        self.min_name_length = min_name_length
        self.fuzzy_threshold = fuzzy_threshold
        self.infer_relationships = infer_relationships
        self.stats = QualityStats()

        # Compile noise patterns
        self._noise_patterns = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]

    def filter_result(self, result: ExtractionResult) -> ExtractionResult:
        """
        Apply quality filtering to an extraction result

        Args:
            result: ExtractionResult to filter

        Returns:
            Filtered ExtractionResult
        """
        self.stats.entities_input += len(result.entities)

        # Step 1: Filter noise entities
        filtered_entities = []
        for entity in result.entities:
            if self._is_valid_entity(entity):
                # Apply type corrections
                corrected = self._correct_entity_type(entity)
                filtered_entities.append(corrected)
            else:
                self.stats.entities_filtered += 1
                logger.debug(f"Filtered noise entity: {entity.name} ({entity.type.value})")

        # Step 2: Merge duplicates
        merged_entities = self._merge_duplicates(filtered_entities)

        # Step 3: Update relations to use merged entity IDs
        entity_id_map = self._build_entity_id_map(result.entities, merged_entities)
        updated_relations = self._update_relation_ids(result.relations, entity_id_map)

        # Step 4: Filter orphan relations (referencing non-existent entities)
        valid_entity_ids = {e.id for e in merged_entities}
        valid_relations = [
            r
            for r in updated_relations
            if r.source_id in valid_entity_ids and r.target_id in valid_entity_ids
        ]

        # Step 5: Infer relationships for orphans
        if self.infer_relationships:
            inferred = self._infer_relationships(merged_entities, valid_relations, result.raw_text)
            valid_relations.extend(inferred)
            self.stats.relations_inferred += len(inferred)

        # Step 6: Apply dynamic confidence
        for entity in merged_entities:
            entity.confidence = self._calculate_confidence(entity, valid_relations)

        return ExtractionResult(
            chunk_id=result.chunk_id,
            entities=merged_entities,
            relations=valid_relations,
            raw_text=result.raw_text,
        )

    def _is_valid_entity(self, entity: ExtractedEntity) -> bool:
        """Check if entity is valid (not noise)"""
        name = entity.name.strip()
        name_lower = name.lower()

        # Check minimum length
        if len(name) < self.min_name_length:
            return False

        # Check noise terms
        if name_lower in NOISE_TERMS:
            return False

        # Check noise patterns
        for pattern in self._noise_patterns:
            if pattern.match(name):
                return False

        # Check for misclassified laws
        if entity.type in SPECIFIC_ENTITY_TYPES:
            if name_lower in NOT_A_LAW:
                return False
            # Must contain a number or year for specific regulations
            if not re.search(r"\d", name):
                # Allow some general terms
                if len(name) < 20:
                    return False

        # Check for OCR errors (contains ! or weird characters)
        return not re.search(r"[!@#$%^&*()\[\]{}|\\<>]", name)

    def _correct_entity_type(self, entity: ExtractedEntity) -> ExtractedEntity:
        """Correct misclassified entity types"""
        name_lower = entity.name.lower().strip()

        # Check correction rules
        for term, correct_type in ENTITY_TYPE_CORRECTIONS.items():
            if name_lower == term or name_lower.startswith(term + " "):
                if entity.type != correct_type:
                    logger.debug(
                        f"Corrected entity type: {entity.name} "
                        f"{entity.type.value} -> {correct_type.value}"
                    )
                    entity.type = correct_type
                    self.stats.entities_corrected += 1
                break

        # Correct KBLI typos
        if entity.type == EntityType.KBLI:
            # Fix common OCR errors
            if name_lower.startswith("ibli") or name_lower.startswith("bbli"):
                entity.name = "K" + entity.name[1:]
                self.stats.entities_corrected += 1

        return entity

    def _merge_duplicates(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Merge duplicate entities using fuzzy matching"""
        if not entities:
            return []

        # Group by type first
        by_type: dict[EntityType, list[ExtractedEntity]] = {}
        for entity in entities:
            by_type.setdefault(entity.type, []).append(entity)

        merged = []
        for _entity_type, type_entities in by_type.items():
            merged.extend(self._merge_entities_of_type(type_entities))

        return merged

    def _merge_entities_of_type(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Merge entities of the same type"""
        if len(entities) <= 1:
            return entities

        # Sort by name length (longer = more specific = canonical)
        entities = sorted(entities, key=lambda e: len(e.name), reverse=True)

        merged: list[ExtractedEntity] = []
        used = set()

        for i, entity in enumerate(entities):
            if i in used:
                continue

            canonical = entity

            # Find similar entities
            for j, other in enumerate(entities[i + 1 :], start=i + 1):
                if j in used:
                    continue

                similarity = self._similarity(canonical.name, other.name)
                if similarity >= self.fuzzy_threshold:
                    # Merge attributes
                    canonical.attributes.update(other.attributes)
                    # Keep higher confidence
                    canonical.confidence = max(canonical.confidence, other.confidence)
                    used.add(j)
                    self.stats.duplicates_merged += 1
                    logger.debug(f"Merged duplicate: {other.name} -> {canonical.name}")

            merged.append(canonical)

        return merged

    def _similarity(self, a: str, b: str) -> float:
        """Calculate string similarity"""
        a_norm = a.upper().strip()
        b_norm = b.upper().strip()
        return SequenceMatcher(None, a_norm, b_norm).ratio()

    def _build_entity_id_map(
        self,
        original: list[ExtractedEntity],
        merged: list[ExtractedEntity],
    ) -> dict[str, str]:
        """Build mapping from original IDs to merged IDs"""
        id_map = {}
        merged_names = {e.name.upper(): e.id for e in merged}

        for entity in original:
            name_upper = entity.name.upper()
            if name_upper in merged_names:
                id_map[entity.id] = merged_names[name_upper]
            else:
                # Find by fuzzy match
                for merged_name, merged_id in merged_names.items():
                    if self._similarity(name_upper, merged_name) >= self.fuzzy_threshold:
                        id_map[entity.id] = merged_id
                        break

        return id_map

    def _update_relation_ids(
        self,
        relations: list[ExtractedRelation],
        id_map: dict[str, str],
    ) -> list[ExtractedRelation]:
        """Update relation IDs using the entity ID map"""
        updated = []
        for relation in relations:
            new_source = id_map.get(relation.source_id, relation.source_id)
            new_target = id_map.get(relation.target_id, relation.target_id)

            relation.source_id = new_source
            relation.target_id = new_target
            updated.append(relation)

        return updated

    def _infer_relationships(
        self,
        entities: list[ExtractedEntity],
        existing_relations: list[ExtractedRelation],
        text: str,
    ) -> list[ExtractedRelation]:
        """
        Infer relationships for orphan entities based on co-occurrence

        Heuristics:
        - If KBLI and IZIN_USAHA appear together -> CLASSIFIED_AS
        - If UNDANG_UNDANG and PASAL appear together -> PART_OF
        - If BIAYA and IZIN_USAHA appear together -> HAS_FEE
        """
        inferred = []

        # Get orphan entities
        connected_ids = set()
        for rel in existing_relations:
            connected_ids.add(rel.source_id)
            connected_ids.add(rel.target_id)

        orphans = [e for e in entities if e.id not in connected_ids]

        if not orphans:
            return []

        # Build type index
        by_type: dict[EntityType, list[ExtractedEntity]] = {}
        for entity in entities:
            by_type.setdefault(entity.type, []).append(entity)

        # Inference rules
        rules = [
            # (source_type, target_type, relation_type)
            (EntityType.IZIN_USAHA, EntityType.KBLI, RelationType.CLASSIFIED_AS),
            (EntityType.PASAL, EntityType.UNDANG_UNDANG, RelationType.PART_OF),
            (EntityType.PASAL, EntityType.PERATURAN_PEMERINTAH, RelationType.PART_OF),
            (EntityType.BIAYA, EntityType.IZIN_USAHA, RelationType.HAS_FEE),
            (EntityType.JANGKA_WAKTU, EntityType.IZIN_USAHA, RelationType.HAS_DURATION),
            (EntityType.DOKUMEN, EntityType.IZIN_USAHA, RelationType.REQUIRES),
        ]

        for orphan in orphans:
            for source_type, target_type, rel_type in rules:
                if orphan.type == source_type:
                    # Find a target entity
                    targets = by_type.get(target_type, [])
                    if targets:
                        # Use the first target (most specific)
                        target = targets[0]

                        # Check if relation already exists
                        exists = any(
                            r.source_id == orphan.id
                            and r.target_id == target.id
                            and r.type == rel_type
                            for r in existing_relations + inferred
                        )

                        if not exists:
                            inferred.append(
                                ExtractedRelation(
                                    source_id=orphan.id,
                                    target_id=target.id,
                                    type=rel_type,
                                    evidence="[inferred from co-occurrence]",
                                    confidence=0.6,  # Lower confidence for inferred
                                )
                            )
                            break  # Only one inference per orphan

        return inferred

    def _calculate_confidence(
        self,
        entity: ExtractedEntity,
        relations: list[ExtractedRelation],
    ) -> float:
        """
        Calculate dynamic confidence based on evidence quality

        Factors:
        - Name specificity (longer = more specific = higher confidence)
        - Number of relationships (more = higher confidence)
        - Has attributes (higher confidence)
        """
        base_confidence = 0.5

        # Name specificity bonus (up to 0.2)
        name_len = len(entity.name)
        if name_len > 50:
            base_confidence += 0.2
        elif name_len > 20:
            base_confidence += 0.15
        elif name_len > 10:
            base_confidence += 0.1

        # Relationship bonus (up to 0.2)
        rel_count = sum(
            1 for r in relations if r.source_id == entity.id or r.target_id == entity.id
        )
        if rel_count > 3:
            base_confidence += 0.2
        elif rel_count > 1:
            base_confidence += 0.15
        elif rel_count > 0:
            base_confidence += 0.1

        # Attributes bonus (up to 0.1)
        if entity.attributes:
            base_confidence += 0.1

        return min(base_confidence, 0.95)  # Cap at 0.95

    def get_stats(self) -> dict[str, Any]:
        """Get filtering statistics"""
        return self.stats.to_dict()

    def reset_stats(self) -> Any:
        """Reset statistics"""
        self.stats = QualityStats()


# ============================================================================
# BATCH QUALITY FILTER
# ============================================================================


async def apply_quality_filter_to_batch(
    results: list[ExtractionResult],
    min_name_length: int = 4,
    fuzzy_threshold: float = 0.85,
    infer_relationships: bool = True,
) -> tuple[list[ExtractionResult], QualityStats]:
    """
    Apply quality filtering to a batch of extraction results

    Args:
        results: List of ExtractionResults
        min_name_length: Minimum entity name length
        fuzzy_threshold: Similarity threshold for fuzzy matching
        infer_relationships: Whether to infer relationships

    Returns:
        Tuple of (filtered_results, stats)
    """
    quality_filter = KGQualityFilter(
        min_name_length=min_name_length,
        fuzzy_threshold=fuzzy_threshold,
        infer_relationships=infer_relationships,
    )

    filtered_results = []
    for result in results:
        filtered = quality_filter.filter_result(result)
        filtered_results.append(filtered)

    return filtered_results, quality_filter.stats
