"""4-tier entity resolution: NIP → jabatan+kantor → fuzzy name → embedding."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz, process

from osint_nexus.utils.logging import get_logger

logger = get_logger("resolver")

FUZZY_THRESHOLD = 85


@dataclass
class ResolvedEntity:
    """A resolved entity with confidence and match method."""

    canonical_id: str
    canonical_name: str
    entity_type: str
    confidence: float  # 0.0-1.0
    match_method: str  # nip, jabatan_kantor, fuzzy_name, new
    merged_from: list[str] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)


class EntityResolver:
    """Resolves and deduplicates entities across multiple scraper outputs."""

    def __init__(self) -> None:
        self._entities: dict[str, ResolvedEntity] = {}
        # Secondary indexes
        self._nip_index: dict[str, str] = {}  # NIP → canonical_id
        self._jabatan_kantor_index: dict[str, str] = {}  # "jabatan|kantor" → canonical_id
        self._name_index: dict[str, str] = {}  # lowercase name → canonical_id

    def resolve(self, entity: dict[str, Any], entity_type: str = "person") -> ResolvedEntity:
        """Resolve an entity through 4-tier matching.

        Args:
            entity: Dict with at least 'nama', optionally 'nip', 'jabatan', 'instansi'
            entity_type: Node type (person, organization, etc)

        Returns:
            ResolvedEntity with match details
        """
        nama = entity.get("nama", "").strip()
        nip = entity.get("nip", "").strip()
        jabatan = entity.get("jabatan", "").strip()
        instansi = entity.get("instansi", "").strip()

        if not nama:
            logger.warning("Entity with no name, skipping")
            return ResolvedEntity(
                canonical_id="unknown",
                canonical_name="UNKNOWN",
                entity_type=entity_type,
                confidence=0.0,
                match_method="skip",
            )

        # Tier 1: NIP exact match (perfect)
        if nip and nip in self._nip_index:
            cid = self._nip_index[nip]
            existing = self._entities[cid]
            self._merge_properties(existing, entity)
            logger.info("NIP match: %s → %s (1.0)", nama, existing.canonical_name)
            return ResolvedEntity(
                canonical_id=cid,
                canonical_name=existing.canonical_name,
                entity_type=entity_type,
                confidence=1.0,
                match_method="nip",
            )

        # Tier 2: jabatan + kantor match (strong)
        if jabatan and instansi:
            jk_key = f"{jabatan.lower()}|{instansi.lower()}"
            if jk_key in self._jabatan_kantor_index:
                cid = self._jabatan_kantor_index[jk_key]
                existing = self._entities[cid]
                self._merge_properties(existing, entity)
                logger.info("Jabatan+Kantor match: %s → %s (0.9)", nama, existing.canonical_name)
                return ResolvedEntity(
                    canonical_id=cid,
                    canonical_name=existing.canonical_name,
                    entity_type=entity_type,
                    confidence=0.9,
                    match_method="jabatan_kantor",
                )

        # Tier 3: fuzzy name match (weak, flag for review)
        # Guards against subset false positives like 'Agus' ⊂ 'Agus Andrianto':
        # for short single-word names we require ≥80% length similarity AND
        # token_sort_ratio ≥70 (which penalises subset matches).
        name_lower = nama.lower()
        if self._name_index:
            names = list(self._name_index.keys())
            match = process.extractOne(name_lower, names, scorer=fuzz.token_set_ratio)
            if match and match[1] >= FUZZY_THRESHOLD:
                matched_name, score, _ = match
                words_a = name_lower.split()
                words_b = matched_name.split()
                accept = True
                if len(words_a) < 2 or len(words_b) < 2:
                    shorter = min(len(name_lower), len(matched_name))
                    longer = max(len(name_lower), len(matched_name))
                    if longer == 0 or shorter / longer < 0.80:
                        accept = False
                if accept:
                    sort_score = fuzz.token_sort_ratio(name_lower, matched_name)
                    if sort_score < 70:
                        accept = False
                if accept:
                    cid = self._name_index[matched_name]
                    existing = self._entities[cid]
                    conf = score / 100.0
                    self._merge_properties(existing, entity)
                    existing.merged_from.append(nama)
                    logger.info(
                        "Fuzzy match: '%s' → '%s' (%.2f, score=%d)",
                        nama, existing.canonical_name, conf, score,
                    )
                    return ResolvedEntity(
                        canonical_id=cid,
                        canonical_name=existing.canonical_name,
                        entity_type=entity_type,
                        confidence=conf,
                        match_method="fuzzy_name",
                    )

        # Tier 4: new entity
        cid = self._generate_id(nama, entity_type)
        resolved = ResolvedEntity(
            canonical_id=cid,
            canonical_name=nama,
            entity_type=entity_type,
            confidence=1.0,
            match_method="new",
            properties=entity,
        )
        self._register(resolved, nip, jabatan, instansi)
        logger.info("New entity: %s (%s) → %s", nama, entity_type, cid)
        return resolved

    def _register(
        self, entity: ResolvedEntity, nip: str, jabatan: str, instansi: str
    ) -> None:
        """Register entity in all indexes."""
        cid = entity.canonical_id
        self._entities[cid] = entity
        self._name_index[entity.canonical_name.lower()] = cid
        if nip:
            self._nip_index[nip] = cid
        if jabatan and instansi:
            jk_key = f"{jabatan.lower()}|{instansi.lower()}"
            self._jabatan_kantor_index[jk_key] = cid

    def _merge_properties(self, existing: ResolvedEntity, new_data: dict[str, Any]) -> None:
        """Merge new properties into existing entity (non-destructive)."""
        for key, val in new_data.items():
            if val and (key not in existing.properties or not existing.properties[key]):
                existing.properties[key] = val

    @staticmethod
    def _generate_id(name: str, entity_type: str) -> str:
        """Generate a stable canonical ID."""
        slug = name.lower().replace(" ", "_").replace(".", "")[:40]
        return f"{entity_type}:{slug}"

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    def get_all(self) -> list[ResolvedEntity]:
        return list(self._entities.values())

    def get_by_id(self, canonical_id: str) -> ResolvedEntity | None:
        return self._entities.get(canonical_id)
