"""
Coreference Resolution for Legal Knowledge Graphs
Based on CORE-KG and LINK-KG (arXiv 2025) best practices

Resolves references like:
- "peraturan tersebut" -> UU No. 6 Tahun 2023
- "izin dimaksud" -> NIB
- "undang-undang ini" -> UU No. 25 Tahun 2007
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import anthropic

from .extractor import ExtractedEntity
from .ontology import EntityType

logger = logging.getLogger(__name__)


@dataclass
class EntityMention:
    """A mention of an entity in text"""
    text: str                     # The mention text
    entity_id: str | None = None  # Resolved entity ID
    entity_type: EntityType | None = None
    position: int = 0             # Position in text
    is_pronoun: bool = False      # Is this a pronoun/reference
    confidence: float = 0.8


@dataclass
class EntityCluster:
    """Cluster of mentions referring to same entity"""
    canonical_id: str
    canonical_name: str
    entity_type: EntityType
    mentions: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)


class CoreferenceResolver:
    """
    Type-aware Coreference Resolution for Indonesian Legal Documents

    Based on CORE-KG paper, uses:
    1. Type-aware mention clustering
    2. Prompt cache for consistency across chunks
    3. LLM-based disambiguation for ambiguous cases
    """

    # Indonesian legal pronouns and references
    REFERENCE_PATTERNS = {
        # Regulation references
        "regulation": [
            r"peraturan\s+(?:tersebut|dimaksud|ini|itu)",
            r"undang-undang\s+(?:tersebut|dimaksud|ini|itu)",
            r"(?:PP|UU|Perpres|Permen)\s+(?:tersebut|dimaksud)",
            r"ketentuan\s+(?:tersebut|dimaksud|ini)",
            r"pasal\s+(?:tersebut|dimaksud)",
            r"ayat\s+(?:tersebut|dimaksud)",
        ],
        # Permit references
        "permit": [
            r"izin\s+(?:tersebut|dimaksud|ini|itu)",
            r"perizinan\s+(?:tersebut|dimaksud)",
            r"(?:NIB|SIUP|KITAS|IMTA)\s+(?:tersebut|dimaksud)",
            r"dokumen\s+(?:tersebut|dimaksud)",
        ],
        # Entity references
        "entity": [
            r"perusahaan\s+(?:tersebut|dimaksud|bersangkutan)",
            r"badan\s+(?:usaha|hukum)\s+(?:tersebut|dimaksud)",
            r"pelaku\s+usaha\s+(?:tersebut|dimaksud)",
            r"pihak\s+(?:tersebut|dimaksud|bersangkutan)",
            r"(?:PT|CV)\s+(?:tersebut|dimaksud)",
        ],
        # Institution references
        "institution": [
            r"instansi\s+(?:tersebut|dimaksud|terkait|berwenang)",
            r"kementerian\s+(?:tersebut|dimaksud|terkait)",
            r"lembaga\s+(?:tersebut|dimaksud|terkait)",
            r"pejabat\s+(?:tersebut|dimaksud|berwenang)",
        ],
    }

    # Common Indonesian legal abbreviations and their expansions
    ABBREVIATION_MAP = {
        "UU": "Undang-Undang",
        "PP": "Peraturan Pemerintah",
        "Perpres": "Peraturan Presiden",
        "Permen": "Peraturan Menteri",
        "Perda": "Peraturan Daerah",
        "NIB": "Nomor Induk Berusaha",
        "SIUP": "Surat Izin Usaha Perdagangan",
        "TDP": "Tanda Daftar Perusahaan",
        "NPWP": "Nomor Pokok Wajib Pajak",
        "KITAS": "Kartu Izin Tinggal Terbatas",
        "KITAP": "Kartu Izin Tinggal Tetap",
        "IMTA": "Izin Mempekerjakan Tenaga Kerja Asing",
        "RPTKA": "Rencana Penggunaan Tenaga Kerja Asing",
        "OSS": "Online Single Submission",
        "BKPM": "Badan Koordinasi Penanaman Modal",
        "DJP": "Direktorat Jenderal Pajak",
        "PPh": "Pajak Penghasilan",
        "PPN": "Pajak Pertambahan Nilai",
        "PBB": "Pajak Bumi dan Bangunan",
        "PT": "Perseroan Terbatas",
        "CV": "Commanditaire Vennootschap",
        "PMA": "Penanaman Modal Asing",
        "PMDN": "Penanaman Modal Dalam Negeri",
    }

    def __init__(
        self,
        use_llm: bool = True,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
    ):
        """
        Initialize Coreference Resolver

        Args:
            use_llm: Use LLM for disambiguation
            model: Claude model to use
            api_key: Anthropic API key
        """
        self.use_llm = use_llm
        self.model = model

        if use_llm:
            self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

        # Entity cache for cross-chunk consistency (Prompt Cache)
        self.entity_cache: dict[str, EntityCluster] = {}

        # Compile reference patterns
        self._compile_patterns()

        logger.info(f"CoreferenceResolver initialized, use_llm={use_llm}")

    def _compile_patterns(self):
        """Compile regex patterns for efficiency"""
        self.compiled_patterns = {}
        for ref_type, patterns in self.REFERENCE_PATTERNS.items():
            self.compiled_patterns[ref_type] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

    def find_references(self, text: str) -> list[EntityMention]:
        """
        Find all pronoun/reference mentions in text

        Args:
            text: Text to analyze

        Returns:
            List of reference mentions
        """
        mentions = []

        for ref_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    mentions.append(EntityMention(
                        text=match.group(),
                        position=match.start(),
                        is_pronoun=True,
                        entity_type=self._ref_type_to_entity_type(ref_type),
                    ))

        return sorted(mentions, key=lambda m: m.position)

    def _ref_type_to_entity_type(self, ref_type: str) -> EntityType | None:
        """Map reference type to entity type"""
        mapping = {
            "regulation": EntityType.UNDANG_UNDANG,
            "permit": EntityType.NIB,
            "entity": EntityType.BADAN_HUKUM,
            "institution": EntityType.KEMENTERIAN,
        }
        return mapping.get(ref_type)

    def normalize_entity_name(self, name: str) -> str:
        """
        Normalize entity name for clustering

        Args:
            name: Raw entity name

        Returns:
            Normalized name
        """
        # Uppercase and clean whitespace
        normalized = re.sub(r"\s+", " ", name.strip().upper())

        # Normalize regulation format
        # "UU No 6/2023" -> "UU NO. 6 TAHUN 2023"
        reg_match = re.match(
            r"(UU|PP|PERPRES|PERMEN)\s*(?:NO\.?\s*)?(\d+)\s*[/\s]*(?:TAHUN\s*)?(\d{4})",
            normalized,
            re.IGNORECASE,
        )
        if reg_match:
            reg_type = reg_match.group(1).upper()
            number = reg_match.group(2)
            year = reg_match.group(3)
            normalized = f"{reg_type} NO. {number} TAHUN {year}"

        return normalized

    def cluster_entities(
        self, entities: list[ExtractedEntity]
    ) -> dict[str, EntityCluster]:
        """
        Cluster entities by canonical name

        Args:
            entities: List of extracted entities

        Returns:
            Dictionary of entity clusters by canonical ID
        """
        clusters: dict[str, EntityCluster] = {}

        for entity in entities:
            canonical_name = self.normalize_entity_name(entity.name)
            canonical_id = f"{entity.type.value}_{canonical_name.lower().replace(' ', '_')}"

            if canonical_id not in clusters:
                clusters[canonical_id] = EntityCluster(
                    canonical_id=canonical_id,
                    canonical_name=canonical_name,
                    entity_type=entity.type,
                    mentions=[entity.mention],
                    attributes=entity.attributes.copy(),
                )
            else:
                # Add mention if not already present
                if entity.mention not in clusters[canonical_id].mentions:
                    clusters[canonical_id].mentions.append(entity.mention)
                # Merge attributes
                clusters[canonical_id].attributes.update(entity.attributes)

        return clusters

    def update_cache(self, clusters: dict[str, EntityCluster]):
        """
        Update entity cache with new clusters

        Args:
            clusters: New entity clusters
        """
        for cid, cluster in clusters.items():
            if cid in self.entity_cache:
                # Merge mentions
                existing = self.entity_cache[cid]
                for mention in cluster.mentions:
                    if mention not in existing.mentions:
                        existing.mentions.append(mention)
                existing.attributes.update(cluster.attributes)
            else:
                self.entity_cache[cid] = cluster

    def get_cache_context(self) -> str:
        """Get cache context for LLM prompts"""
        if not self.entity_cache:
            return "No entities in cache."

        lines = ["Known entities:"]
        for cid, cluster in self.entity_cache.items():
            mentions = ", ".join(cluster.mentions[:3])
            lines.append(f"  - {cluster.canonical_name} [{cluster.entity_type.value}]: {mentions}")

        return "\n".join(lines[:20])  # Limit size

    async def resolve_reference(
        self,
        reference: EntityMention,
        context: str,
        candidates: list[ExtractedEntity] | None = None,
    ) -> str | None:
        """
        Resolve a reference to an entity using LLM

        Args:
            reference: The reference mention to resolve
            context: Text context around the reference
            candidates: Candidate entities to resolve to

        Returns:
            Resolved entity ID or None
        """
        if not self.use_llm:
            return self._resolve_heuristic(reference, candidates)

        # Build candidate list from cache and provided candidates
        all_candidates = []

        if candidates:
            for c in candidates:
                all_candidates.append(f"{c.id}: {c.name} [{c.type.value}]")

        for cid, cluster in self.entity_cache.items():
            all_candidates.append(f"{cid}: {cluster.canonical_name} [{cluster.entity_type.value}]")

        if not all_candidates:
            return None

        prompt = f"""Resolve the reference in Indonesian legal text.

## REFERENCE TO RESOLVE
"{reference.text}"

## CONTEXT
{context[:500]}

## CANDIDATE ENTITIES
{chr(10).join(all_candidates[:15])}

## INSTRUCTIONS
1. Determine which entity the reference "{reference.text}" refers to
2. Consider the context and type compatibility
3. Return ONLY the entity ID (e.g., "e1" or "undang_undang_uu_no._6_tahun_2023")
4. If no match, return "NONE"

## ANSWER (just the ID):"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=50,
                temperature=0.0,
                messages=[{"role": "user", "content": prompt}],
            )

            result = response.content[0].text.strip()

            if result == "NONE" or not result:
                return None

            return result

        except Exception as e:
            logger.error(f"LLM resolution failed: {e}")
            return self._resolve_heuristic(reference, candidates)

    def _resolve_heuristic(
        self,
        reference: EntityMention,
        candidates: list[ExtractedEntity] | None = None,
    ) -> str | None:
        """
        Heuristic-based reference resolution (fallback)

        Uses type matching and recency (last mentioned entity of matching type)
        """
        if not candidates and not self.entity_cache:
            return None

        ref_type = reference.entity_type

        # Check candidates first
        if candidates:
            for c in reversed(candidates):  # Most recent first
                if c.type == ref_type:
                    return c.id

        # Check cache
        for cid, cluster in self.entity_cache.items():
            if cluster.entity_type == ref_type:
                return cid

        return None

    async def resolve_all_references(
        self,
        text: str,
        entities: list[ExtractedEntity],
    ) -> dict[str, str]:
        """
        Resolve all references in text

        Args:
            text: Full text
            entities: Extracted entities from this text

        Returns:
            Dictionary mapping reference text to resolved entity ID
        """
        references = self.find_references(text)
        resolutions: dict[str, str] = {}

        for ref in references:
            # Get context around reference
            start = max(0, ref.position - 200)
            end = min(len(text), ref.position + 200)
            context = text[start:end]

            resolved_id = await self.resolve_reference(ref, context, entities)
            if resolved_id:
                resolutions[ref.text] = resolved_id

        return resolutions

    def deduplicate_entities(
        self, entities: list[ExtractedEntity]
    ) -> list[ExtractedEntity]:
        """
        Deduplicate entities by merging similar ones

        Args:
            entities: List of entities to deduplicate

        Returns:
            Deduplicated list
        """
        clusters = self.cluster_entities(entities)

        # Create deduplicated entity list
        deduplicated = []
        for cluster in clusters.values():
            # Create single entity from cluster
            deduplicated.append(ExtractedEntity(
                id=cluster.canonical_id,
                type=cluster.entity_type,
                name=cluster.canonical_name,
                mention=cluster.mentions[0] if cluster.mentions else cluster.canonical_name,
                attributes=cluster.attributes,
                confidence=0.9,
            ))

        return deduplicated

    def clear_cache(self):
        """Clear the entity cache"""
        self.entity_cache.clear()

    def get_cache_stats(self) -> dict[str, Any]:
        """Get statistics about the entity cache"""
        type_counts: dict[str, int] = {}
        total_mentions = 0

        for cluster in self.entity_cache.values():
            type_name = cluster.entity_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
            total_mentions += len(cluster.mentions)

        return {
            "total_entities": len(self.entity_cache),
            "total_mentions": total_mentions,
            "by_type": type_counts,
        }
