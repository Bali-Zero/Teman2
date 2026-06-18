"""Normalizer and dedupe layer for Autonomous Lab research materials."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.services.autonomous_lab.planner import (
    AutonomousLabPlanner,
    NormalizedMaterial,
    ResearchMaterial,
)
from backend.services.autonomous_lab.receipt_safety import safe_sha256_fingerprint

NORMALIZER_CONTRACT_VERSION = "autonomous-lab-v1-normalizer"


@dataclass(frozen=True)
class MaterialCluster:
    """Receipt-safe dedupe cluster keyed by content fingerprint."""

    cluster_id: str
    content_fingerprint: str
    material_ids: tuple[str, ...]
    tags: tuple[str, ...]
    novelty_score: float

    @property
    def duplicate_count(self) -> int:
        """Return duplicate count after the representative item."""
        return max(0, len(self.material_ids) - 1)

    def to_receipt(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "content_fingerprint": self.content_fingerprint,
            "material_ids": list(self.material_ids),
            "tags": list(self.tags),
            "novelty_score": self.novelty_score,
            "duplicate_count": self.duplicate_count,
        }


@dataclass(frozen=True)
class NormalizedMaterialBatch:
    """Bounded output from normalize + dedupe."""

    version: str
    created_at: datetime
    materials: tuple[NormalizedMaterial, ...]
    clusters: tuple[MaterialCluster, ...]
    duplicate_count: int
    novelty_score: float

    @property
    def unique_material_ids(self) -> tuple[str, ...]:
        """Return the representative material id for every cluster."""
        return tuple(cluster.material_ids[0] for cluster in self.clusters)

    @property
    def material_count(self) -> int:
        """Return the number of normalized material envelopes."""
        return len(self.materials)

    @property
    def cluster_count(self) -> int:
        """Return the number of deduped material clusters."""
        return len(self.clusters)

    def to_receipt(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "materials": [material.to_receipt() for material in self.materials],
            "clusters": [cluster.to_receipt() for cluster in self.clusters],
            "unique_material_ids": list(self.unique_material_ids),
            "material_count": self.material_count,
            "cluster_count": self.cluster_count,
            "duplicate_count": self.duplicate_count,
            "novelty_score": self.novelty_score,
        }


def normalize_and_dedupe_materials(
    *,
    materials: list[ResearchMaterial],
    planner: AutonomousLabPlanner | None = None,
    created_at: datetime | None = None,
) -> NormalizedMaterialBatch:
    """Normalize materials and group exact content duplicates without raw text."""
    active_planner = planner or AutonomousLabPlanner()
    normalized = tuple(active_planner.normalize_material(material) for material in materials)
    clusters = _build_clusters(normalized)
    duplicate_count = sum(cluster.duplicate_count for cluster in clusters)
    novelty_score = _batch_novelty_score(clusters=clusters, material_count=len(normalized))
    return NormalizedMaterialBatch(
        version=NORMALIZER_CONTRACT_VERSION,
        created_at=created_at or datetime.now(tz=timezone.utc),
        materials=normalized,
        clusters=clusters,
        duplicate_count=duplicate_count,
        novelty_score=novelty_score,
    )


def _build_clusters(materials: tuple[NormalizedMaterial, ...]) -> tuple[MaterialCluster, ...]:
    grouped: dict[str, list[NormalizedMaterial]] = {}
    for material in materials:
        grouped.setdefault(material.content_fingerprint, []).append(material)

    clusters: list[MaterialCluster] = []
    for index, (fingerprint, group) in enumerate(sorted(grouped.items()), start=1):
        tags = tuple(sorted({tag for material in group for tag in material.tags}))
        material_ids = tuple(material.material_id for material in group)
        novelty_score = round(1.0 / len(group), 2)
        clusters.append(
            MaterialCluster(
                cluster_id=f"cluster-{index}-{safe_sha256_fingerprint(fingerprint, 8)}",
                content_fingerprint=fingerprint,
                material_ids=material_ids,
                tags=tags,
                novelty_score=novelty_score,
            )
        )
    return tuple(clusters)


def _batch_novelty_score(*, clusters: tuple[MaterialCluster, ...], material_count: int) -> float:
    if material_count == 0:
        return 0.0
    unique_ratio = len(clusters) / material_count
    tag_bonus = min(0.2, 0.02 * len({tag for cluster in clusters for tag in cluster.tags}))
    return round(min(1.0, unique_ratio + tag_bonus), 2)


__all__ = [
    "NORMALIZER_CONTRACT_VERSION",
    "MaterialCluster",
    "NormalizedMaterialBatch",
    "normalize_and_dedupe_materials",
]
