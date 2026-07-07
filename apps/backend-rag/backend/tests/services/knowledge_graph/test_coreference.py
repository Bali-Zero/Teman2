from __future__ import annotations

import pytest

from backend.services.knowledge_graph.coreference import (
    CoreferenceResolver,
    EntityCluster,
    EntityMention,
)
from backend.services.knowledge_graph.extractor import ExtractedEntity
from backend.services.knowledge_graph.ontology import EntityType


def entity(
    entity_id: str,
    entity_type: EntityType,
    name: str,
    mention: str,
    attributes: dict[str, str] | None = None,
) -> ExtractedEntity:
    return ExtractedEntity(
        id=entity_id,
        type=entity_type,
        name=name,
        mention=mention,
        attributes=attributes or {},
    )


def test_find_references_detects_legal_reference_mentions_in_position_order() -> None:
    resolver = CoreferenceResolver(use_llm=False)
    text = (
        "UU No. 6 Tahun 2023 berlaku. Peraturan tersebut mensyaratkan NIB. "
        "Izin dimaksud diterbitkan OSS."
    )

    references = resolver.find_references(text)

    assert [ref.text.lower() for ref in references] == ["peraturan tersebut", "izin dimaksud"]
    assert references[0].entity_type == EntityType.UNDANG_UNDANG
    assert references[1].entity_type == EntityType.NIB
    assert all(ref.is_pronoun for ref in references)
    assert references[0].position < references[1].position


def test_normalize_entity_name_cleans_spacing_case_and_regulation_format() -> None:
    resolver = CoreferenceResolver(use_llm=False)

    assert resolver.normalize_entity_name("  PT   Bali Zero  ") == "PT BALI ZERO"
    assert resolver.normalize_entity_name("UU No 6/2023") == "UU NO. 6 TAHUN 2023"
    assert resolver.normalize_entity_name("PP 35 Tahun 2021") == "PP NO. 35 TAHUN 2021"


def test_cluster_entities_merges_mentions_and_attributes_by_canonical_name() -> None:
    resolver = CoreferenceResolver(use_llm=False)
    entities = [
        entity("e1", EntityType.UNDANG_UNDANG, "UU No 6/2023", "UU No 6/2023", {"year": "2023"}),
        entity(
            "e2",
            EntityType.UNDANG_UNDANG,
            "UU No. 6 Tahun 2023",
            "Undang-Undang Cipta Kerja",
            {"topic": "Cipta Kerja"},
        ),
    ]

    clusters = resolver.cluster_entities(entities)

    assert list(clusters) == ["undang_undang_uu_no._6_tahun_2023"]
    cluster = clusters["undang_undang_uu_no._6_tahun_2023"]
    assert cluster.canonical_name == "UU NO. 6 TAHUN 2023"
    assert cluster.mentions == ["UU No 6/2023", "Undang-Undang Cipta Kerja"]
    assert cluster.attributes == {"year": "2023", "topic": "Cipta Kerja"}


def test_update_cache_merges_existing_clusters_without_duplicate_mentions() -> None:
    resolver = CoreferenceResolver(use_llm=False)
    resolver.entity_cache["nib_nib"] = EntityCluster(
        canonical_id="nib_nib",
        canonical_name="NIB",
        entity_type=EntityType.NIB,
        mentions=["NIB"],
        attributes={"source": "old"},
    )

    resolver.update_cache(
        {
            "nib_nib": EntityCluster(
                canonical_id="nib_nib",
                canonical_name="NIB",
                entity_type=EntityType.NIB,
                mentions=["NIB", "Nomor Induk Berusaha"],
                attributes={"source": "new"},
            ),
        },
    )

    cached = resolver.entity_cache["nib_nib"]
    assert cached.mentions == ["NIB", "Nomor Induk Berusaha"]
    assert cached.attributes == {"source": "new"}


def test_get_cache_context_returns_bounded_human_readable_context() -> None:
    resolver = CoreferenceResolver(use_llm=False)

    assert resolver.get_cache_context() == "No entities in cache."

    resolver.update_cache(
        {
            "oss": EntityCluster(
                canonical_id="oss",
                canonical_name="OSS",
                entity_type=EntityType.OSS,
                mentions=["OSS", "Online Single Submission", "system OSS", "extra mention"],
            ),
        },
    )

    context = resolver.get_cache_context()
    assert "Known entities:" in context
    assert "OSS [oss]" in context
    assert "extra mention" not in context


@pytest.mark.asyncio
async def test_resolve_reference_uses_heuristic_when_llm_is_disabled() -> None:
    resolver = CoreferenceResolver(use_llm=False)
    reference = EntityMention(
        text="peraturan tersebut",
        entity_type=EntityType.UNDANG_UNDANG,
        is_pronoun=True,
    )
    candidates = [
        entity("old", EntityType.UNDANG_UNDANG, "UU No 25 Tahun 2007", "UU 25/2007"),
        entity("recent", EntityType.UNDANG_UNDANG, "UU No 6 Tahun 2023", "UU 6/2023"),
    ]

    assert await resolver.resolve_reference(reference, "context", candidates) == "recent"


@pytest.mark.asyncio
async def test_resolve_all_references_returns_only_resolved_mentions() -> None:
    resolver = CoreferenceResolver(use_llm=False)
    text = "UU No. 6 Tahun 2023 berlaku. Peraturan tersebut mengatur izin tersebut."
    candidates = [
        entity("uu-6", EntityType.UNDANG_UNDANG, "UU No 6 Tahun 2023", "UU No. 6 Tahun 2023"),
        entity("nib-1", EntityType.NIB, "NIB", "NIB"),
    ]

    resolutions = await resolver.resolve_all_references(text, candidates)

    assert resolutions == {
        "Peraturan tersebut": "uu-6",
        "izin tersebut": "nib-1",
    }


def test_deduplicate_entities_returns_one_entity_per_cluster() -> None:
    resolver = CoreferenceResolver(use_llm=False)
    deduplicated = resolver.deduplicate_entities(
        [
            entity("a", EntityType.NIB, "NIB", "NIB", {"issuer": "OSS"}),
            entity("b", EntityType.NIB, "nib", "Nomor Induk Berusaha", {"valid": "yes"}),
        ],
    )

    assert len(deduplicated) == 1
    assert deduplicated[0].id == "nib_nib"
    assert deduplicated[0].name == "NIB"
    assert deduplicated[0].confidence == 0.9
    assert deduplicated[0].attributes == {"issuer": "OSS", "valid": "yes"}


def test_clear_cache_and_get_cache_stats() -> None:
    resolver = CoreferenceResolver(use_llm=False)
    resolver.update_cache(
        {
            "nib": EntityCluster(
                canonical_id="nib",
                canonical_name="NIB",
                entity_type=EntityType.NIB,
                mentions=["NIB", "Nomor Induk Berusaha"],
            ),
            "oss": EntityCluster(
                canonical_id="oss",
                canonical_name="OSS",
                entity_type=EntityType.OSS,
                mentions=["OSS"],
            ),
        },
    )

    assert resolver.get_cache_stats() == {
        "total_entities": 2,
        "total_mentions": 3,
        "by_type": {"nib": 1, "oss": 1},
    }

    resolver.clear_cache()

    assert resolver.get_cache_stats() == {
        "total_entities": 0,
        "total_mentions": 0,
        "by_type": {},
    }
